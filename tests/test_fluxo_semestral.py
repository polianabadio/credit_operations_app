from decimal import Decimal

from src.simulador.cambio import entrada_em_reais
from src.simulador.fluxo_tlp import deslocar_mes, data_iso
from src.simulador.operacao import calcular_operacao


def test_profisco_corrigido_reproduz_planilha_e_mantem_ano_fiscal():
    inicio = '2026-09-15'
    desembolsos = ('692828.30', '5623374.15', '10484986.70', '12319345.26', '14747529.53',
                   '13443010.44', '11489840.55', '10884242.35', '7512761.39', '3168335.33')
    entrada = dict(ano=2026, fim=2051, valor='90366254.00', moeda_contrato='USD', moeda_entrada='USD',
                   cotacao_contrato='4.98860', indexador='CAMBIAL', referencia_juros_cambial='SOFR',
                   modelo_fluxo='contratual', tipo_liberacao='semestral', data_liberacao=inicio,
                   carencia_meses=72, amortizacao_meses=222, taxa_indexador='3.69495', prefixada='0',
                   spread='0.41', spread_capital='0.80', comissao_credito='0.50', fator='2.031208231',
                   liberacoes_semestrais={deslocar_mes(data_iso(inicio), i * 6).isoformat(): valor
                                         for i, valor in enumerate(desembolsos)})
    brl, _ = entrada_em_reais(entrada)
    resultado = calcular_operacao(brl, serie_ipca={})
    fluxo = resultado['fluxo']
    planilha = fluxo['planilha']
    assert len(planilha['semestres']) == 49
    assert fluxo['quantidade_amortizacoes'] == 38
    assert fluxo['data_final'] == '2051-03-15'
    assert planilha['semestres'][0]['juros_financeiros'] == '16851.79'
    assert planilha['semestres'][0]['comissao_credito'] == '224183.56'
    assert [linha['juros'] for linha in planilha['anuais']] == (
        '241035.35 961130.32 2056414.20 3227100.26 4125874.92 4444563.19 4374577.62 '
        '4141292.37 3908007.14 3684628.53 3441436.65 3208151.42 2974866.17 2748931.01 '
        '2508295.70 2275010.45 2041725.21 1813233.50 1575154.73 1341869.49 1108584.24 '
        '877535.99 642013.76 408728.52 175443.29').split()
    assert planilha['anuais'][6]['amortizacao'] == '4756118.64'
    assert planilha['totais']['total'] == '148671858.03'
    assert fluxo['amortizacao_total'] == '450801094.70'
    assert Decimal(resultado['servico_input']['linhas'][0]['juros_encargos']) == 0
    assert Decimal(resultado['servico_input']['linhas'][-1]['amortizacao']) > 0
    assert sum(Decimal(l['liberacaoNovaOperacao']) for l in resultado['bases_fluxo']) == Decimal('450801094.70')
