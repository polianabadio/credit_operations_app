from decimal import Decimal
import pytest
from src.simulador.operacao import calcular_operacao
from src.simulador.cambio import entrada_em_reais


def entrada():
    return dict(ano=2026, fim=2027, valor='1000', indexador='CAMBIAL', moeda_contrato='USD',
                cotacao_contrato='4.98860', fator='2', modo_calculo='anual_informado',
                cronograma_anual=[dict(ano=2026,liberacao='400',amortizacao='0',juros_encargos='10'),
                                  dict(ano=2027,liberacao='600',amortizacao='1000',juros_encargos='20')])


def test_fluxo_declarado_sem_datas_mensais_ou_taxa_recalculada():
    convertido, ref = entrada_em_reais(entrada())
    dados = calcular_operacao(convertido, serie_ipca={})
    assert dados['fluxo']['modo'] == 'anual_informado'
    assert Decimal(ref['valor_brl']) == Decimal('4988.60')
    assert Decimal(dados['bases_fluxo'][0]['liberacaoNovaOperacao']) == Decimal('1995.44')
    assert Decimal(dados['bases_fluxo'][1]['liberacaoNovaOperacao']) == Decimal('2993.16')
    assert Decimal(dados['servico_input']['linhas'][0]['juros_encargos']) == Decimal('49.89')
    assert dados['servico_input']['linhas'][0]['demais_operacoes'] is None
    assert Decimal(dados['fluxo']['amortizacao_total']) == Decimal('4988.60')
    assert dados['fluxo']['memoria_cronograma']['linhas_originais'] == entrada()['cronograma_anual']


@pytest.mark.parametrize('mutacao', ['ausente', 'duplicado', 'vazio', 'negativo', 'soma', 'antecipado', 'centavos'])
def test_rejeita_cronograma_integro_apenas_na_aparencia(mutacao):
    e = entrada()
    if mutacao == 'ausente': e['cronograma_anual'].pop()
    if mutacao == 'duplicado': e['cronograma_anual'][1]['ano'] = 2026
    if mutacao == 'vazio': e['cronograma_anual'][0]['juros_encargos'] = ''
    if mutacao == 'negativo': e['cronograma_anual'][0]['juros_encargos'] = '-1'
    if mutacao == 'soma': e['cronograma_anual'][1]['amortizacao'] = '999'
    if mutacao == 'antecipado':
        e['cronograma_anual'][0]['amortizacao'] = '1000'
        e['cronograma_anual'][1]['amortizacao'] = '0'
    if mutacao == 'centavos': e['cronograma_anual'][0]['juros_encargos'] = '1.001'
    with pytest.raises(ValueError): entrada_em_reais(e)


def test_concilia_centavos_sem_perder_principal_e_registra_residuo():
    e=entrada();e['valor']='1';e['cotacao_contrato']='1.333'
    e['cronograma_anual'][0].update(liberacao='.5',amortizacao='0')
    e['cronograma_anual'][1].update(liberacao='.5',amortizacao='1')
    convertido, _=entrada_em_reais(e)
    assert sum(Decimal(l['liberacao']) for l in convertido['cronograma_anual']) == Decimal('1.33')
    assert convertido['memoria_cronograma']['ajustes_conversao_brl']['liberacao']=='-0.01'
    calcular_operacao(convertido,serie_ipca={})
