from unittest.mock import Mock

import pytest
import requests
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from src.simulador import data_updater as updater
from src.simulador.database_models import Base, RREO, RGF


@pytest.fixture
def ambiente(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        monkeypatch.setattr(updater.db, 'session', session)
        monkeypatch.setattr(updater, 'log', Mock())
        monkeypatch.setattr(updater, '_aguardar_limite_api', lambda: None)
        monkeypatch.setattr(updater, 'sleep', lambda segundos: None)
        yield engine, session
    engine.dispose()


PARAMS = {'co_tipo_demonstrativo': 'RREO', 'co_esfera': 'E', 'id_ente': 52}
PERIODO = {'an_exercicio': 2026, 'nr_periodo': 4, 'no_anexo': 'RREO-Anexo 01'}
URL = 'https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo'


def registro(conta='Receita'):
    return dict(exercicio=2026, periodo=4, demonstrativo='RREO', instituicao='Goias',
                uf='GO', esfera='E', anexo='RREO-Anexo 01', coluna=None,
                conta=conta, valor=100)


def executar():
    return updater._atualizar_dados_siconfi(RREO, 'rreo', PARAMS, [PERIODO])


def test_resposta_vazia_e_sucesso_sem_dados(ambiente, requests_mock):
    requests_mock.get(URL, json={'items': [], 'hasMore': False})
    resultado = updater._resultado_atualizacao('RREO', *executar())
    assert resultado['status'] == 'success'
    assert len(resultado['avisos']) == 1
    assert not resultado['falhas']


@pytest.mark.parametrize('resposta', [{'status_code': 503}, {'exc': requests.Timeout},
                                    {'json': {'mensagem': 'erro'}}])
def test_falha_tecnica_nao_vira_aviso(ambiente, requests_mock, resposta):
    requests_mock.get(URL, **resposta)
    resultado = updater._resultado_atualizacao('RREO', *executar())
    assert resultado['status'] == 'error'
    assert resultado['falhas'][0]['motivo']


def test_paginacao_e_duplicatas_por_periodo(ambiente, requests_mock):
    engine, session = ambiente
    consultas = []
    event.listen(engine, 'before_cursor_execute',
                 lambda conn, cursor, statement, params, context, many: consultas.append(statement))
    requests_mock.get(URL, [{'json': {'items': [registro()], 'hasMore': True}},
                           {'json': {'items': [registro(), registro('Outra')], 'hasMore': False}}])
    assert not executar()[1]
    assert requests_mock.request_history[1].qs['offset'] == ['1']
    assert session.query(RREO).count() == 2
    assert not executar()[1]
    assert session.query(RREO).count() == 2


def test_republicacao_substitui_valores_e_linhas_do_periodo(ambiente, requests_mock):
    from datetime import datetime, timedelta
    from src.simulador.database_models import SincronizacaoSiconfi

    requests_mock.get(URL, [
        {'json': {'items': [registro(), registro('Linha retirada')], 'hasMore': False}},
        {'json': {'items': [{**registro(), 'valor': 125}], 'hasMore': False}},
    ])
    assert not executar()[1]
    session = ambiente[1]
    assert session.query(RREO).count() == 2
    session.query(SincronizacaoSiconfi).update({
        'consultado_em': datetime.now() - timedelta(hours=2)})
    session.commit()
    assert not executar()[1]
    linhas = session.query(RREO).all()
    assert len(linhas) == 1
    assert linhas[0].conta == 'Receita'
    assert linhas[0].valor == 125
    assert requests_mock.call_count == 2


def test_resposta_vazia_apos_publicacao_remove_periodo_antigo(ambiente, requests_mock):
    from datetime import datetime, timedelta
    from src.simulador.database_models import SincronizacaoSiconfi

    requests_mock.get(URL, [
        {'json': {'items': [registro()], 'hasMore': False}},
        {'json': {'items': [], 'hasMore': False}},
    ])
    assert not executar()[1]
    session = ambiente[1]
    assert session.query(RREO).count() == 1
    session.query(SincronizacaoSiconfi).update({
        'consultado_em': datetime.now() - timedelta(hours=2)})
    session.commit()
    assert not executar()[1]
    assert session.query(RREO).count() == 0


def test_republicacao_rgf_preserva_outro_poder(ambiente, requests_mock):
    from datetime import datetime, timedelta
    from src.simulador.database_models import SincronizacaoSiconfi

    params = {'in_periodicidade': 'Q', 'co_tipo_demonstrativo': 'RGF',
              'co_esfera': 'E', 'id_ente': 52}
    periodo = {'an_exercicio': 2026, 'nr_periodo': 2,
               'no_anexo': 'RGF-Anexo 04', 'co_poder': 'E'}
    url = 'https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf'
    linha = dict(exercicio=2026, periodo=2, periodicidade='Q',
                 instituicao='Goias', uf='GO', co_poder='E', esfera='E',
                 anexo='RGF-Anexo 04', rotulo='Apuracao', coluna='VALOR',
                 cod_conta='OperacoesCredito', conta='Operacoes de credito', valor=100)
    outra = {**linha, 'co_poder': 'L', 'valor': 50}
    session = ambiente[1]
    session.add(RGF(**outra))
    session.commit()
    requests_mock.get(url, [
        {'json': {'items': [linha], 'hasMore': False}},
        {'json': {'items': [{**linha, 'valor': 125}], 'hasMore': False}},
    ])
    def consultar():
        return updater._atualizar_dados_siconfi(RGF, 'rgf', params, [periodo])
    assert not consultar()[1]
    session.query(SincronizacaoSiconfi).update({
        'consultado_em': datetime.now() - timedelta(hours=2)})
    session.commit()
    assert not consultar()[1]
    assert sorted((row.co_poder, row.valor) for row in session.query(RGF).all()) == [
        ('E', 125), ('L', 50)]


def test_falha_na_segunda_pagina_nao_salva_dados_parciais(ambiente, requests_mock):
    requests_mock.get(URL, [{'json': {'items': [registro()], 'hasMore': True}},
                           {'status_code': 500}])
    assert executar()[1]
    assert ambiente[1].query(RREO).count() == 0


def test_consulta_todos_periodos_e_inclui_ano_atual():
    for endpoint, quantidade in [('rreo', 6), ('rgf', 3)]:
        periodos = updater._periodos_para_consulta(endpoint)
        ano = updater.datetime.now().year
        assert {p['an_exercicio'] for p in periodos} == set(range(2021, ano + 1))
        assert {p['nr_periodo'] for p in periodos if p['an_exercicio'] == ano} == set(range(1, quantidade + 1))


def test_atualizacao_normal_do_rreo_inclui_anexo_03(monkeypatch):
    recebidos = []
    monkeypatch.setattr(updater, '_atualizar_dados_siconfi',
                        lambda modelo, endpoint, params, periodos, progresso:
                        (recebidos.extend(periodos) or [], [], []))
    updater.atualizar_operacoes_rreo('now')
    assert any(p['no_anexo'] == 'RREO-Anexo 03' for p in recebidos)
    ultimo_bimestre_concluido = (updater.datetime.now().month - 1) // 2
    assert {p['nr_periodo'] for p in recebidos if p['no_anexo'] == 'RREO-Anexo 03'} == set(
        range(1, ultimo_bimestre_concluido + 1))


def test_atualizacao_automatica_nao_consulta_periodos_futuros():
    for endpoint, meses_por_periodo in (('rreo', 2), ('rgf', 4)):
        atual = updater._periodos_para_consulta(endpoint, 'now')
        assert {p['nr_periodo'] for p in atual} == set(
            range(1, (updater.datetime.now().month - 1) // meses_por_periodo + 1))
        anterior = updater._periodos_para_consulta(endpoint, 'past')
        assert all(p['an_exercicio'] < updater.datetime.now().year for p in anterior)


def test_cache_com_linhas_ausentes_refaz_consulta(ambiente, requests_mock):
    from datetime import datetime
    import json
    from src.simulador.database_models import SincronizacaoSiconfi
    session = ambiente[1]
    chave = json.dumps(['rreo', {**PARAMS, **PERIODO}], sort_keys=True)
    session.add(SincronizacaoSiconfi(chave=chave, consultado_em=datetime.now(), quantidade=1))
    session.commit()
    requests_mock.get(URL, json={'items': [registro()], 'hasMore': False})
    assert not executar()[1]
    assert requests_mock.call_count == 1
    assert session.query(RREO).count() == 1


def test_analise_nao_mistura_periodos(ambiente):
    from src.simulador.data_access import obter_dados_rreo_para_analise
    session = ambiente[1]
    antigo = registro()
    antigo.update(periodo=1, valor=10)
    session.add_all([RREO(**antigo), RREO(**registro())])
    session.commit()
    resultado = obter_dados_rreo_para_analise(2026)[2026]
    assert resultado['max_periodo'] == 4
    assert [r['valor'] for r in resultado['registros']] == [100.0]


def test_reutiliza_importacao_confirmada_sem_requisicao(ambiente, requests_mock):
    requests_mock.get(URL, json={'items': [registro()], 'hasMore': False})
    executar()
    executar()
    assert requests_mock.call_count == 1


def test_cache_expirado_busca_novamente(ambiente, requests_mock):
    from datetime import datetime, timedelta
    from src.simulador.database_models import SincronizacaoSiconfi
    requests_mock.get(URL, json={'items': [], 'hasMore': False})
    executar()
    executar()
    assert requests_mock.call_count == 1
    session = ambiente[1]
    session.query(SincronizacaoSiconfi).update({'consultado_em': datetime.now() - timedelta(hours=2)})
    session.commit()
    executar()
    assert requests_mock.call_count == 2


def test_periodo_historico_sem_dados_nao_e_refeito_a_cada_abertura(ambiente, requests_mock):
    from datetime import datetime, timedelta
    from src.simulador.database_models import SincronizacaoSiconfi
    periodo_antigo = {**PERIODO, 'an_exercicio': datetime.now().year - 1}
    requests_mock.get(URL, json={'items': [], 'hasMore': False})
    def consultar():
        return updater._atualizar_dados_siconfi(RREO, 'rreo', PARAMS, [periodo_antigo])
    consultar()
    session = ambiente[1]
    session.query(SincronizacaoSiconfi).update({
        'consultado_em': datetime.now() - timedelta(hours=2)})
    session.commit()
    consultar()
    assert requests_mock.call_count == 1
    session.query(SincronizacaoSiconfi).update({
        'consultado_em': datetime.now() - timedelta(days=8)})
    session.commit()
    consultar()
    assert requests_mock.call_count == 2


def test_periodos_mais_recentes_sao_consultados_primeiro():
    periodos = updater._periodos_para_consulta('rreo', 'past')
    ano_mais_recente = updater.datetime.now().year - 1
    assert periodos[0]['an_exercicio'] == ano_mais_recente
    assert periodos[0]['nr_periodo'] == 6


def test_falha_nao_impede_nova_tentativa(ambiente, requests_mock):
    requests_mock.get(URL, [{'status_code': 500}, {'status_code': 500},
                           {'status_code': 500},
                           {'json': {'items': [registro()], 'hasMore': False}}])
    assert executar()[1]
    assert not executar()[1]
    assert requests_mock.call_count == 4


def test_falha_temporaria_e_recuperada_na_mesma_atualizacao(ambiente, requests_mock):
    requests_mock.get(URL, [{'status_code': 503},
                           {'json': {'items': [registro()], 'hasMore': False}}])
    assert not executar()[1]
    assert requests_mock.call_count == 2


def test_reservas_da_api_mantem_intervalo_sem_bloquear_outras_threads(monkeypatch):
    from threading import Event, Thread

    primeira_dormindo = Event()
    liberar_primeira = Event()
    chamadas = []
    monkeypatch.setattr(updater, '_ultima_requisicao', 0.0)
    monkeypatch.setattr(updater, 'monotonic', lambda: 10.0)

    def dormir(segundos):
        chamadas.append(segundos)
        if len(chamadas) == 1:
            primeira_dormindo.set()
            assert liberar_primeira.wait(2)

    monkeypatch.setattr(updater, 'sleep', dormir)
    primeira = Thread(target=updater._aguardar_limite_api)
    segunda = Thread(target=updater._aguardar_limite_api)
    try:
        primeira.start()
        assert primeira_dormindo.wait(2)
        segunda.start()
        segunda.join(2)
        assert not segunda.is_alive()
        assert chamadas == [0, 1]
    finally:
        liberar_primeira.set()
        primeira.join(2)
        segunda.join(2)
