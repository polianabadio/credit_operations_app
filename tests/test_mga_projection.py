from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.simulador import mga_projection as mga
from src.simulador.database_models import Base, CoberturaMga, OperacaoCredito, db
from src.simulador.fluxo_credito import CreditFlowLimitService


@pytest.fixture
def memoria(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        monkeypatch.setattr(db, 'session', session)
        monkeypatch.setattr(mga, 'obter_parametro_mga', lambda *args: {
            'multiplier': '1.10', 'source': 'Fonte de teste', 'validated': True,
            'effectiveFrom': '2026-01-01', 'meaning': 'Teste'})
        yield session
    engine.dispose()


def painel(periodo=6):
    return {'exercicio': 2026, 'rcl': {'valor': 1000, 'periodo': periodo,
            'origem': 'SICONFI/RREO', 'anexo': 'RREO-Anexo 03'}}


def operacao(identificador='A', valores=None, situacao='contratada', completo=True):
    valores = valores or [(2026, 80), (2027, 100)]
    return {'identificador': identificador, 'fonte': 'Documento conferido',
            'situacao': situacao, 'valorTotal': 1000, 'anoInicio': 2026, 'anoFim': 2027,
            'cronogramaCompleto': completo,
            'liberacoes': [{'ano': a, 'valor': v} for a, v in valores]}


@pytest.mark.parametrize('valor,status', [(0, 'Enquadrado'), (160, 'Enquadrado'),
                                          (Decimal('160.01'), 'Não Enquadrado')])
def test_limite_exato_e_zero(valor, status):
    r = CreditFlowLimitService().avaliar(2026, rcl_projetada={2026: 1000},
        liberacoes_contratadas={2026: 0}, liberacoes_nao_contratadas={2026: 0},
        liberacoes_analisadas={2026: valor})
    assert r['globalStatus'] == status
    assert r['criticalYear'] == 2026
    assert r['maxLimitUsage'] == pytest.approx(float(valor) / 160)


def test_projecao_proporcional_e_multiplos_anos():
    valores = CreditFlowLimitService.projetar_rcl_anual(1000, '1.21', 2026, 3, 2028)
    assert valores[2026] == pytest.approx(Decimal(1100))
    assert valores[2027] == pytest.approx(Decimal(1331))
    assert valores[2028] == pytest.approx(Decimal('1610.51'))


def test_memoria_soma_liberacoes_e_simulacao_nao_persiste(memoria):
    mga.salvar_operacao(operacao(valores=[(2026, 30), (2026, 50), (2027, 100)]))
    mga.salvar_operacao(operacao('B', [(2026, 20), (2027, 0)], 'a_contratar'))
    mga.confirmar_cobertura(2026, 2027, 'Inventário conferido')
    r = mga.obter_projecao(painel(), [{'ano': 2026, 'liberacaoNovaOperacao': 60},
                                    {'ano': 2027, 'liberacaoNovaOperacao': 100}])
    assert r['rows'][0]['mga'] == 160
    assert r['rows'][0]['situacao'] == 'Enquadrado'
    assert r['rows'][1]['mga'] == 200
    assert r['globalStatus'] == 'Não Enquadrado'
    assert r['exceededYears'] == [2027]
    assert r['criticalYear'] == 2027
    assert r['rows'][1]['rclProjetada'] == 1100
    assert len(r['rows'][0]['sources']['operations']) == 2
    assert r['sources']['rclSource'] == 'SICONFI/RREO'
    assert memoria.query(OperacaoCredito).count() == 2
    assert mga.obter_projecao(painel())['rows'][0]['mga'] == 100


def test_ausencia_cobertura_nao_equivale_zero(memoria):
    r = mga.obter_projecao(painel())
    assert r['globalStatus'] == 'Dados incompletos'
    assert r['rows'][0]['scheduledDisbursements'] is None
    assert r['maxMgaRcl'] is None
    mga.confirmar_cobertura(2026, 2028, 'Inventário sem operações')
    r = mga.obter_projecao(painel())
    assert r['rows'][0]['mga'] == 0
    assert r['globalStatus'] == 'Enquadrado'


def test_null_solicitado_cobertura_limitada_e_edicao(memoria):
    mga.salvar_operacao(operacao())
    mga.confirmar_cobertura(2026, 2027, 'Inventário')
    r = mga.obter_projecao(painel(), [{'ano': 2026, 'liberacaoNovaOperacao': None},
                                    {'ano': 2028, 'liberacaoNovaOperacao': 1}])
    assert not r['dataAvailability']
    assert r['rows'][0]['requestedOperation'] is None
    assert r['rows'][2]['scheduledDisbursements'] is None
    mga.salvar_operacao(operacao(valores=[(2026, 0), (2027, 0)]))
    assert memoria.query(CoberturaMga).count() == 0
    assert memoria.query(OperacaoCredito).count() == 1


def test_cronograma_incompleto_nao_pode_ser_confirmado(memoria):
    with pytest.raises(ValueError):
        mga.salvar_operacao(operacao(valores=[(2026, 10)]))
    mga.salvar_operacao(operacao(valores=[(2026, 10)], completo=False))
    with pytest.raises(ValueError):
        mga.confirmar_cobertura(2026, 2027, 'Inventário')


def test_todos_anos_e_status_inativos(memoria):
    mga.salvar_operacao(operacao())
    mga.salvar_operacao(operacao('Cancelada', [(2026, 900), (2027, 0)], 'cancelada'))
    mga.confirmar_cobertura(2026, 2028, 'Inventário')
    r = mga.obter_projecao(painel(), [{'ano': 2028, 'liberacaoNovaOperacao': 10}])
    assert [l['ano'] for l in r['rows']] == [2026, 2027, 2028]
    assert r['rows'][0]['mga'] == 80
    assert r['rows'][2]['mga'] == 10
    assert r['globalStatus'] == 'Enquadrado'
    assert r['criticalYear'] == 2027


@pytest.mark.parametrize('valor', [-1, 'NaN', 'Infinity'])
def test_valor_invalido_nao_persiste(memoria, valor):
    with pytest.raises(ValueError):
        mga.salvar_operacao(operacao(valores=[(2026, valor), (2027, 0)]))
    assert memoria.query(OperacaoCredito).count() == 0


def test_rcl_ausente_preserva_liberacoes_conhecidas(memoria):
    mga.confirmar_cobertura(2026, 2027, 'Inventário vazio conferido')
    r = mga.obter_projecao({'exercicio': 2026, 'rcl': None},
                          [{'ano': 2026, 'liberacaoNovaOperacao': 80}])
    assert r['rows'][0]['mga'] == 80
    assert r['rows'][0]['mgaRcl'] is None
    assert r['rows'][0]['margemEstimada'] is None
    assert r['globalStatus'] == 'Dados incompletos'


def referencia_simulacao(monkeypatch):
    consultados = []
    def consultar(ano):
        consultados.append(ano)
        return {'valor': 1000, 'periodo': 6, 'origem': 'SICONFI/RREO', 'anexo': 'RREO-Anexo 03'}
    monkeypatch.setattr(mga, 'obter_rcl_ajustada_endividamento', consultar)
    return consultados


def test_simulacao_unica_usa_valor_requisitado_e_ano_escolhido(memoria, monkeypatch):
    anos = referencia_simulacao(monkeypatch)
    r = mga.avaliar_simulacao_mga(2027, 80)
    assert anos == [2027]
    assert r['requestedTotal'] == 80
    assert r['rows'][0]['requestedOperation'] == 80
    assert r['rows'][0]['mgaRcl'] == .08
    assert r['evaluationScope'] == 'requested_operation_only'
    assert r['maxRequestedAmountForSchedule'] is None
    assert r['verificationStatus'] == 'Cenário parcial'
    assert 'hipótese' in r['sources']['scheduledOperationsSource'].lower()
    assert memoria.query(CoberturaMga).count() == 0


def test_simulacao_contrato_multi_ano_e_capacidade(memoria, monkeypatch):
    referencia_simulacao(monkeypatch)
    r = mga.avaliar_simulacao_mga(2026, 300, {'scope': 'operation_only', 'mode': 'annual_schedule',
        'rows': [{'ano': 2026, 'liberacaoNovaOperacao': 100}, {'ano': 2027, 'liberacaoNovaOperacao': 200}]})
    assert r['criticalYear'] == 2027
    assert r['maxRequestedAmountForSchedule'] is None
    assert r['globalStatus'] == 'Cenário parcial'
    assert r['numericOutcome'] == 'Não Enquadrado'


def test_simulacao_nao_duplica_valor_e_exige_cronograma_coerente(memoria, monkeypatch):
    referencia_simulacao(monkeypatch)
    with pytest.raises(ValueError, match='Valor requisitado'):
        mga.avaliar_simulacao_mga(2026, 300, {'scope': 'operation_only', 'mode': 'annual_schedule',
            'rows': [{'ano': 2026, 'liberacaoNovaOperacao': 300}, {'ano': 2027, 'liberacaoNovaOperacao': 300}]})
    with pytest.raises(ValueError, match='Preencha'):
        mga.avaliar_simulacao_mga(2026, 300, {'scope': 'operation_only', 'mode': 'annual_schedule',
            'rows': [{'ano': 2026, 'liberacaoNovaOperacao': None}]})


def test_simulacao_inventario_ausente_permanece_desconhecido(memoria, monkeypatch):
    referencia_simulacao(monkeypatch)
    r = mga.avaliar_simulacao_mga(2026, 80, {'scope': 'inventory', 'mode': 'single_year'})
    assert not r['dataAvailability']
    assert r['rows'][0]['scheduledDisbursements'] is None
    assert r['maxRequestedAmountForSchedule'] is None


def test_capacidade_completa_distribuicao_e_ano_restritivo(memoria, monkeypatch):
    referencia_simulacao(monkeypatch)
    mga.confirmar_cobertura(2026, 2027, 'Inventário vazio conferido')
    r = mga.avaliar_simulacao_mga(2026, 300, {'scope': 'inventory', 'mode': 'annual_schedule',
        'releaseStart': 2026, 'releaseEnd': 2027,
        'rows': [{'ano': 2026, 'liberacaoNovaOperacao': 100}, {'ano': 2027, 'liberacaoNovaOperacao': 200}]})
    assert r['verificationStatus'] == 'Acima do limite'
    assert r['validatedConclusion']
    assert r['maxRequestedAmountForSchedule'] == 264
    assert r['capacityRestrictingYear'] == 2027
    assert r['rows'][1]['margemEstimada'] == -24


def test_integral_ano_liberacao_independente(memoria, monkeypatch):
    referencia_simulacao(monkeypatch)
    r = mga.avaliar_simulacao_mga(2026, 80, {'scope': 'operation_only', 'mode': 'single_year', 'releaseStart': 2028})
    assert [l['requestedOperation'] for l in r['rows']] == [0, 0, 80]
    assert r['releaseStart'] == r['releaseEnd'] == 2028
    assert r['verificationStatus'] == 'Cenário parcial'
    assert r['numericOutcome'] == 'Enquadrado'
    assert not r['validatedConclusion']


def test_um_centavo_diferente_e_centavos_excedentes_rejeitados(memoria, monkeypatch):
    referencia_simulacao(monkeypatch)
    for valor in ('80.01', '79.99', '80.001'):
        with pytest.raises(ValueError):
            mga.avaliar_simulacao_mga(2026, 80, {'scope': 'inventory', 'mode': 'annual_schedule',
                'rows': [{'ano': 2026, 'liberacaoNovaOperacao': valor}]})


def test_identificador_exclui_nova_operacao_da_memoria(memoria, monkeypatch):
    referencia_simulacao(monkeypatch)
    mga.salvar_operacao(operacao('PVL-novo', [(2026, 80), (2027, 0)]))
    mga.confirmar_cobertura(2026, 2027, 'Inventário')
    r = mga.avaliar_simulacao_mga(2026, 80, {'scope': 'inventory', 'mode': 'single_year',
        'operationIdentifier': 'PVL-novo'})
    assert r['rows'][0]['mga'] == 80
    assert r['rows'][0]['scheduledDisbursements'] == 0


def test_taxa_decimal_percentual_multiplicador_e_pendencias():
    from src.simulador.mga_parameters import obter_parametro_mga
    p = obter_parametro_mga(2026)
    assert p['validated'] and p['multiplier'] == '1.02031208231'
    assert not obter_parametro_mga(2025)['validated']
    for unidade, valor in [('rate', '.03'), ('percent', '3'), ('multiplier', '1.03')]:
        p = obter_parametro_mga(2026, {'unit': unidade, 'value': valor})
        assert Decimal(p['multiplier']) == Decimal('1.03')
        assert not p['validated']
    p = obter_parametro_mga(2026, {'unit': 'percent', 'value': '2.031208231'})
    assert p['validated']


def test_parametro_sem_origem_confirmada_impede_conclusao(memoria, monkeypatch):
    referencia_simulacao(monkeypatch)
    from src.simulador.mga_parameters import obter_parametro_mga
    monkeypatch.setattr(mga, 'obter_parametro_mga', obter_parametro_mga)
    mga.confirmar_cobertura(2026, 2026, 'Inventário')
    r = mga.avaliar_simulacao_mga(2026, 80, {'scope': 'inventory', 'mode': 'single_year',
        'projectionParameter': {'unit': 'rate', 'value': '.03', 'source': 'Hipótese'}})
    assert r['verificationStatus'] == 'Dados incompletos'
    assert not r['parameterValidated']
    assert r['maxRequestedAmountForSchedule'] is None


def test_dezembro_anterior_e_base_atual_sem_dupla_atualizacao(memoria, monkeypatch):
    def referencia(ano):
        return None if ano == 2026 else {'valor': 1000, 'exercicio': 2025, 'periodo': 6,
            'origem': 'SICONFI/RREO', 'anexo': 'RREO-Anexo 03'}
    monkeypatch.setattr(mga, 'obter_rcl_ajustada_endividamento', referencia)
    r = mga.avaliar_simulacao_mga(2026, 80)
    assert r['rows'][0]['rclProjetada'] == 1100
    assert r['sources']['proportionalMonths'] == 12
    assert r['sources']['rclExercise'] == 2025


def test_razao_15_porcento_e_uso_9375():
    r = CreditFlowLimitService().avaliar(2026, rcl_projetada={2026: 1000},
        liberacoes_contratadas={2026: 0}, liberacoes_nao_contratadas={2026: 0},
        liberacoes_analisadas={2026: 150})
    assert r['maxMgaRcl'] == .15
    assert r['maxLimitUsage'] == .9375
