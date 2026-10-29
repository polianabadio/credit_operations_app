from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.simulador.data_access import obter_posicao_monetaria_siconfi, obter_historico_divida_rcl
from src.simulador.database_models import RGF, RREO, db


@pytest.fixture
def sessao(monkeypatch):
    engine = create_engine('sqlite://')
    RGF.__table__.create(engine)
    RREO.__table__.create(engine)
    with Session(engine) as session:
        monkeypatch.setattr(db, 'session', session)
        yield session
    engine.dispose()


def rgf(sessao, conta='DÍVIDA CONSOLIDADA - DC (I)', valor='123.45', **campos):
    dados = dict(exercicio=2026, periodo=2, periodicidade='Q', instituicao='Goiás',
                 uf='GO', esfera='E', co_poder='E', anexo='RGF-Anexo 02',
                 conta=conta, coluna='Até o 2º Quadrimestre',
                 valor=Decimal(valor) if valor is not None else None)
    dados.update(campos)
    sessao.add(RGF(**dados))
    sessao.commit()


def test_selecao_exclui_outras_ufs_poderes_percentuais_e_saldos_anteriores(sessao):
    rgf(sessao)
    rgf(sessao, valor='999', uf='SP')
    rgf(sessao, valor='999', co_poder='L')
    rgf(sessao, valor='999', periodicidade='S')
    rgf(sessao, valor='999', exercicio=2027)
    rgf(sessao, valor='999', coluna='SALDO DO EXERCÍCIO ANTERIOR')
    rgf(sessao, valor='999', coluna='% sobre a RCL')
    rgf(sessao, conta='Disponibilidade de Caixa Bruta', valor='0')
    dados = {i['chave']: i for i in obter_posicao_monetaria_siconfi(2026)}
    assert dados['divida_consolidada']['valor'] == '123.45'
    assert dados['divida_consolidada']['ano'] == 2026
    assert dados['caixa_bruto']['valor'] == '0.00'
    assert dados['rcl']['valor'] is None


def test_nao_recua_quando_ultimo_anexo_tem_valor_nulo_ausente_ou_duplicado(sessao):
    rgf(sessao, valor='100', periodo=1, coluna='Até o 1º Quadrimestre')
    rgf(sessao, valor=None)
    assert obter_posicao_monetaria_siconfi(2026)[0]['valor'] is None
    rgf(sessao, valor='200')
    dado = obter_posicao_monetaria_siconfi(2026)[0]
    assert dado['valor'] is None
    assert dado['estado'] == 'ambiguo'
    rgf(sessao, conta='OUTRA CONTA', exercicio=2026, periodo=3)
    dado = obter_posicao_monetaria_siconfi(2026)[0]
    assert dado['periodo'] == 3
    assert dado['valor'] is None


def test_rreo_preserva_acumulado_periodo_proprio_e_centavos(sessao):
    rgf(sessao)
    for conta, coluna, valor in [
        ('RECEITAS CORRENTES', 'Até o Bimestre (c)', '1000.37'),
        ('RECEITAS CORRENTES', 'PREVISÃO ATUALIZADA (a)', '9999'),
        ('DESPESAS CORRENTES', 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)', '901.23'),
        ('DESPESAS CORRENTES', 'DESPESAS PAGAS ATÉ O BIMESTRE (j)', '800'),
    ]:
        sessao.add(RREO(exercicio=2025, periodo=6, demonstrativo='RREO',
                        instituicao='Goiás', uf='GO', esfera='E', anexo='RREO-Anexo 01',
                        conta=conta, coluna=coluna, valor=Decimal(valor)))
    sessao.commit()
    dados = {i['chave']: i for i in obter_posicao_monetaria_siconfi(2026)}
    assert dados['receitas_correntes']['valor'] == '1000.37'
    assert dados['despesas_correntes']['valor'] == '901.23'
    assert dados['receitas_correntes']['ano'] == 2025
    assert dados['receitas_correntes']['periodo'] == 6
    assert dados['divida_consolidada']['ano'] == 2026


def test_sem_dados_nao_inventa_saldos(sessao):
    dados = obter_posicao_monetaria_siconfi(2026)
    assert len(dados) == 5
    assert all(i['valor'] is None and i['ano'] is None for i in dados)


def test_historico_mesmo_periodo_por_ano_com_rcl_antiga_e_proporcao_decimal(sessao):
    rgf(sessao, valor='100.00', exercicio=2015, periodo=3, coluna='Até o 3º Quadrimestre')
    rgf(sessao, conta='RECEITA CORRENTE LÍQUIDA - RCL', valor='200.00',
        exercicio=2015, periodo=3, coluna='Até o 3º Quadrimestre')
    rgf(sessao, valor='999', exercicio=2015, periodo=3, coluna='SALDO DO EXERCÍCIO ANTERIOR')
    rgf(sessao, valor='999', exercicio=2015, periodo=3, coluna='% sobre a RCL')
    rgf(sessao, valor='999', uf='SP')
    rgf(sessao, valor='999', co_poder='L')
    rgf(sessao, valor='999', exercicio=2027)
    rgf(sessao, valor='0')
    rgf(sessao, conta='RECEITA CORRENTE LÍQUIDA - RCL (IV)', valor='300')
    historico = obter_historico_divida_rcl(2026)
    assert [i['ano'] for i in historico] == [2015, 2026]
    assert historico[0]['percentual_dc_rcl'] == '50.0'
    assert historico[0]['parcial'] is False
    assert historico[1]['divida_consolidada'] == '0.00'
    assert Decimal(historico[1]['percentual_dc_rcl']) == 0
    assert historico[1]['periodo'] == 2
    assert historico[1]['parcial'] is True


def test_historico_nao_recua_nem_calcula_razao_com_componentes_ausentes(sessao):
    rgf(sessao, valor='100', periodo=1, coluna='Até o 1º Quadrimestre')
    rgf(sessao, conta='RECEITA CORRENTE LÍQUIDA - RCL (IV)', valor='200',
        periodo=1, coluna='Até o 1º Quadrimestre')
    rgf(sessao, valor=None)
    item = obter_historico_divida_rcl(2026)[0]
    assert item['periodo'] == 2
    assert item['divida_consolidada'] is None
    assert item['rcl'] is None
    assert item['percentual_dc_rcl'] is None
    rgf(sessao, valor='100')
    item = obter_historico_divida_rcl(2026)[0]
    assert item['divida_consolidada'] is None
    assert item['componentes']['divida_consolidada']['estado'] == 'ambiguo'


def test_historico_nao_divide_por_rcl_zero(sessao):
    rgf(sessao)
    rgf(sessao, conta='RECEITA CORRENTE LÍQUIDA - RCL (IV)', valor='0')
    item = obter_historico_divida_rcl(2026)[0]
    assert item['rcl'] == '0.00'
    assert item['percentual_dc_rcl'] is None


def test_historico_dcl_usa_percentual_publicado_do_mesmo_periodo(sessao):
    rgf(sessao)
    rgf(sessao, conta='RECEITA CORRENTE LÍQUIDA - RCL (IV)', valor='200')
    rgf(sessao, conta='% da DCL sobre a RCL AJUSTADA (III/VI)', valor='34.64')
    rgf(sessao, conta='% da DCL sobre a RCL AJUSTADA (III/VI)', valor='99',
        coluna='SALDO DO EXERCÍCIO ANTERIOR')
    item = obter_historico_divida_rcl(2026)[0]
    assert item['percentual_dcl_rcl'] == '34.64'
    assert item['base_dcl_rcl'] == 'RCL ajustada'
    assert Decimal(item['percentual_dc_rcl']) != Decimal(item['percentual_dcl_rcl'])
    rgf(sessao, conta='% da DCL sobre a RCL AJUSTADA (III/VI)', valor='34.64')
    item = obter_historico_divida_rcl(2026)[0]
    assert item['percentual_dcl_rcl'] is None
    assert item['componentes']['percentual_dcl_rcl']['estado'] == 'ambiguo'


def test_historico_dcl_preserva_base_antiga_zero_negativo_e_ausencia(sessao):
    rgf(sessao, conta='% da DCL sobre a RCL (III/RCL)', valor='-3.21',
        exercicio=2015, periodo=3, coluna='Até o 3º Quadrimestre')
    rgf(sessao, conta='% da DCL sobre a RCL AJUSTADA (III/VI)', valor='0')
    dados = obter_historico_divida_rcl(2026)
    assert dados[0]['percentual_dcl_rcl'] == '-3.21'
    assert dados[0]['base_dcl_rcl'] == 'RCL'
    assert dados[1]['percentual_dcl_rcl'] == '0.00'
    rgf(sessao, conta='OUTRA CONTA', periodo=3)
    assert obter_historico_divida_rcl(2026)[1]['percentual_dcl_rcl'] is None
