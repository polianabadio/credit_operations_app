from decimal import Decimal

from src.simulador.fluxo_credito import CreditFlowLimitService


def test_referencia_publicada_nao_vira_teto_projetado_ou_margem():
    resultado = CreditFlowLimitService().avaliar(
        2026, rcl_referencia=Decimal('1000'), teto_referencia_publicado=160)
    assert resultado['tetoReferencia'] == 160
    assert resultado['rclProjetada'] is None
    assert resultado['tetoAnual'] is None
    assert resultado['mga'] is None
    assert resultado['margemEstimada'] is None
    assert resultado['status'] == 'comprometimento_nao_disponivel'


def test_cronograma_vazio_informado_e_zero_conhecido_sao_validos():
    servico = CreditFlowLimitService()
    incompleto = servico.avaliar(2026, rcl_projetada={2026: 1000},
                                liberacoes_contratadas={2026: 0})
    assert incompleto['mga'] is None
    completo = servico.avaliar(2026, rcl_projetada={2026: 1000},
                              liberacoes_contratadas={2026: 0},
                              liberacoes_nao_contratadas={2026: 0})
    assert completo['mga'] == 0
    assert completo['margemEstimada'] == 160
    assert completo['status'] == 'dentro_do_limite'


def test_projecao_por_exercicio_soma_operacao_analisada_e_respeita_threshold():
    resultado = CreditFlowLimitService(percentual_atencao='0.14').avaliar(
        2026, rcl_projetada={2026: 1000, 2027: 1200},
        liberacoes_contratadas={2026: 80, 2027: 100},
        liberacoes_nao_contratadas={2026: 30, 2027: 20},
        liberacoes_analisadas={2026: 40, 2027: 100})
    atual, futuro = resultado['exercicios']
    assert atual['mga'] == 150
    assert atual['percentualMgaRcl'] == 15
    assert atual['margemEstimada'] == 10
    assert atual['status'] == 'proximo_ao_limite'
    assert futuro['tetoAnual'] == 192
    assert futuro['mga'] == 220
    assert futuro['margemEstimada'] == -28
    assert futuro['status'] == 'acima_do_limite'
