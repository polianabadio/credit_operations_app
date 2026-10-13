from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.simulador.data_access import (
    COLUNA_LIQUIDADA,
    COLUNA_RCL_12_MESES,
    COLUNA_RESTOS,
    CONTA_RCL_ENDIVIDAMENTO,
    CONTAS_SERVICO_DIVIDA,
    obter_rcl_ajustada_endividamento,
    obter_rcl_caed,
    obter_servico_divida_exercicio_anterior,
)
from src.simulador.data_updater import _periodos_para_consulta
from src.simulador.database_models import RREO, Base, db


@pytest.fixture
def sessao(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        monkeypatch.setattr(db, 'session', session)
        yield session
    engine.dispose()


def registro(periodo, valor, **campos):
    dados = {'exercicio': 2026, 'periodo': periodo, 'demonstrativo': 'RREO',
             'instituicao': 'Goiás', 'uf': 'GO', 'esfera': 'E', 'anexo': 'RREO-Anexo 03',
             'conta': CONTA_RCL_ENDIVIDAMENTO, 'coluna': COLUNA_RCL_12_MESES,
             'valor': valor}
    dados.update(campos)
    return RREO(**dados)


def test_busca_ultimo_valor_correto_de_go(sessao):
    sessao.add_all([
        registro(1, 100), registro(4, 400),
        registro(5, 999, uf='TO'),
        registro(6, 999, coluna='PREVISÃO ATUALIZADA'),
        registro(6, None),
    ])
    sessao.commit()
    resultado = obter_rcl_ajustada_endividamento(2026)
    assert resultado['valor'] == Decimal('400.00')
    assert resultado['periodo'] == 4
    assert resultado['origem'] == 'SICONFI/RREO'


def test_aceita_variacao_de_acentos_e_espacos(sessao):
    sessao.add(registro(3, 250, conta=CONTA_RCL_ENDIVIDAMENTO.replace('LÍQUIDA', 'LIQUIDA'),
                        coluna='TOTAL  (ULTIMOS 12 MESES)'))
    sessao.commit()
    assert obter_rcl_ajustada_endividamento(2026)['valor'] == Decimal('250.00')


def test_ausencia_nao_vira_zero(sessao):
    assert obter_rcl_ajustada_endividamento(2026) is None


def test_duplicidade_no_ultimo_periodo_nao_gera_valor_arbitrario(sessao):
    sessao.add_all([registro(3, 100), registro(3, 200)])
    sessao.commit()
    with pytest.raises(ValueError, match='ambígua'):
        obter_rcl_ajustada_endividamento(2026)


def test_sincronizacao_inclui_anexo_03_do_rreo_e_anexos_fiscais_rgf():
    assert 'RREO-Anexo 03' in {p['no_anexo'] for p in _periodos_para_consulta('rreo', 'now')}
    assert {'RGF-Anexo 03', 'RGF-Anexo 04', 'RGF-Anexo 06'} <= {
        p['no_anexo'] for p in _periodos_para_consulta('rgf', 'now')}


def test_servico_usa_ultimo_bimestre_e_restos_opcionais(sessao):
    sessao.add_all([
        registro(5, 9, anexo='RREO-Anexo 01', conta=CONTAS_SERVICO_DIVIDA[0], coluna=COLUNA_LIQUIDADA),
        registro(6, 10, anexo='RREO-Anexo 01', conta=CONTAS_SERVICO_DIVIDA[0], coluna=COLUNA_LIQUIDADA),
        registro(6, 20, anexo='RREO-Anexo 01', conta=CONTAS_SERVICO_DIVIDA[1], coluna=COLUNA_LIQUIDADA),
        registro(6, 3, anexo='RREO-Anexo 01', conta=CONTAS_SERVICO_DIVIDA[0], coluna=COLUNA_RESTOS),
    ])
    sessao.commit()
    resultado = obter_servico_divida_exercicio_anterior(2026)
    assert resultado['periodo'] == 6
    assert resultado['contas'][CONTAS_SERVICO_DIVIDA[0]][COLUNA_LIQUIDADA] == Decimal('10.00')
    assert resultado['contas'][CONTAS_SERVICO_DIVIDA[0]][COLUNA_RESTOS] == Decimal('3.00')
    assert resultado['contas'][CONTAS_SERVICO_DIVIDA[1]][COLUNA_RESTOS] is None


def test_servico_sem_liquidacao_obrigatoria_fica_pendente(sessao):
    sessao.add(registro(6, 3, anexo='RREO-Anexo 01', conta=CONTAS_SERVICO_DIVIDA[0], coluna=COLUNA_RESTOS))
    sessao.commit()
    assert obter_servico_divida_exercicio_anterior(2026) is None


def test_fator_legado_persistido_nao_e_usado_ou_sobrescrito(sessao):
    from src.simulador.database_models import ParametroSimulacao
    from src.simulador.parametros_simulacao import (
        obter_fator_projecao,
        salvar_fator_projecao,
    )
    sessao.add(ParametroSimulacao(chave='fator_projecao_rcl', valor='2.031208231'))
    sessao.commit()
    assert obter_fator_projecao('2026-10-07')['valor'] == '1.02031208231'
    assert obter_fator_projecao('2026-04-21') is None
    assert obter_fator_projecao('2027-01-01') is None
    assert obter_fator_projecao() is None
    assert salvar_fator_projecao('3,5%') == '3.5'
    assert obter_fator_projecao('2026-10-07')['taxa_percentual'] == '3.5'
    assert obter_fator_projecao('2026-10-07')['valor'] == '1.035'
    sessao.expire_all()
    assert obter_fator_projecao('2026-10-07')['taxa_percentual'] == '3.5'
    for invalido in ('NaN', 'Infinity', '-1', '101', ''):
        with pytest.raises(ValueError):
            salvar_fator_projecao(invalido)
    assert obter_fator_projecao('2026-10-07')['taxa_percentual'] == '3.5'
    assert sessao.get(ParametroSimulacao, 'fator_projecao_rcl').valor == '2.031208231'


def test_caed_data_base_real_e_filtros(sessao):
    sessao.add_all([registro(3, 300), registro(4, 400), registro(5, 500),
                    registro(4, 999, uf='TO'), registro(4, 999, esfera='M')])
    sessao.commit()
    r = obter_rcl_caed(2026, '2026-10-07')
    assert r['valor'] == Decimal('400.00')
    assert r['data_base'] == '2026-08-31'
    assert r['data_referencia'] == '2026-10-07'
    assert r['ente'] == 52 and r['uf'] == 'GO' and r['esfera'] == 'E'


def test_caed_dezembro_anterior_e_periodo_ainda_aberto(sessao):
    sessao.add_all([registro(6, 100, exercicio=2025), registro(1, 200)])
    sessao.commit()
    assert obter_rcl_caed(2026, '2026-02-15')['exercicio'] == 2025
    assert obter_rcl_caed(2026, '2026-02-28')['exercicio'] == 2026


def test_caed_nulo_recente_nao_recua_ou_converte_zero(sessao):
    sessao.add_all([registro(3, 300), registro(4, None)])
    sessao.commit()
    assert obter_rcl_caed(2026, '2026-10-07') is None


def test_caed_duplicidade_ou_exercicio_incompativel(sessao):
    sessao.add_all([registro(4, 100), registro(4, 100)])
    sessao.commit()
    with pytest.raises(ValueError, match='ambígua'):
        obter_rcl_caed(2026, '2026-10-07')
    with pytest.raises(ValueError, match='exercício'):
        obter_rcl_caed(2026, '2025-10-07')
