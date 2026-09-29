from unittest.mock import Mock

import pytest
import requests
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from src.simulador import data_updater as updater
from src.simulador.database_models import Base, RREO


@pytest.fixture
def ambiente(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        monkeypatch.setattr(updater.db, 'session', session)
        monkeypatch.setattr(updater, 'log', Mock())
        monkeypatch.setattr(updater, '_aguardar_limite_api', lambda: None)
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


def test_paginacao_duplicatas_e_uma_consulta_por_periodo(ambiente, requests_mock):
    engine, session = ambiente
    consultas = []
    event.listen(engine, 'before_cursor_execute',
                 lambda conn, cursor, statement, params, context, many: consultas.append(statement))
    requests_mock.get(URL, [{'json': {'items': [registro()], 'hasMore': True}},
                           {'json': {'items': [registro(), registro('Outra')], 'hasMore': False}}])
    assert not executar()[1]
    assert requests_mock.request_history[1].qs['offset'] == ['1']
    assert sum(sql.startswith('SELECT') and 'FROM rreo' in sql for sql in consultas) == 1
    assert session.query(RREO).count() == 2
    assert not executar()[1]
    assert session.query(RREO).count() == 2


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


def test_falha_nao_impede_nova_tentativa(ambiente, requests_mock):
    requests_mock.get(URL, [{'status_code': 500}, {'json': {'items': [registro()], 'hasMore': False}}])
    assert executar()[1]
    assert not executar()[1]
    assert requests_mock.call_count == 2
