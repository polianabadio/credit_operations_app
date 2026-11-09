from decimal import Decimal
from datetime import date
import pytest
from src.simulador.fluxo_contratual import calcular_fluxo_contratual
from src.simulador.operacao import calcular_operacao
from src.simulador.cambio import entrada_em_reais
from src.simulador.resumo_limites import demonstrar_dcl, demonstrar_mga


def entrada(**alteracoes):
    e=dict(ano=2026,fim=2027,valor='1000',modelo_fluxo='contratual',indexador='FIXA',tipo_liberacao='unica',data_liberacao='2026-01-01',prazo_meses='12',carencia_meses='0',amortizacao_meses='12',prefixada='10',spread='0',spread_capital='0',comissao_credito='0',periodicidade_amortizacao='12',periodicidade_juros='12',base_juros='365',fator='2')
    return {**e,**alteracoes}


def test_fixa_efetiva_com_encargos_separados():
    f=calcular_fluxo_contratual(entrada(encargos_anuais={2026:'5'}))
    assert Decimal(f['saldo_final'])==0
    assert Decimal(f['juros_financeiros_total'])==100
    assert Decimal(f['outros_encargos_total'])==5
    assert Decimal(f['juros_total'])==105
    assert Decimal(f['pagamento_total'])==1105


def test_sofr_nominal_semestral_independente():
    f=calcular_fluxo_contratual(entrada(indexador='SOFR',taxa_indexador='3.69',prefixada='0',spread='1.21',periodicidade_juros='6',base_juros='360'))
    assert [Decimal(l['juros_financeiros']) for l in f['linhas'] if Decimal(l['juros_financeiros'])] == [Decimal('24.64'),Decimal('25.04')]
    assert Decimal(f['juros_total'])==Decimal('49.68')
    assert f['quantidade_amortizacoes']==1 and f['quantidade_pagamentos_juros']==2


def test_prazos_sce_38_amortizacoes_49_juros_com_ultima_data_real():
    f=calcular_fluxo_contratual(entrada(fim=2050,valor='90366254',prazo_meses='294',carencia_meses='72',amortizacao_meses='222',periodicidade_amortizacao='6',periodicidade_juros='6',data_liberacao='2026-01-01'))
    assert f['quantidade_amortizacoes']==38 and f['quantidade_pagamentos_juros']==49
    assert f['data_final']=='2050-07-01'
    assert Decimal(f['amortizacao_total'])==Decimal('90366254')
    assert Decimal(f['saldo_final'])==0
    assert min(l['fim'] for l in f['linhas'] if Decimal(l['amortizacao'])>0)=='2032-01-01'


def test_etapas_juros_somente_saldo_recebido_e_comissao_nao_liberado():
    e=entrada(fim=2028,prazo_meses='24',carencia_meses='18',amortizacao_meses='6',periodicidade_amortizacao='6',periodicidade_juros='6',indexador='SOFR',taxa_indexador='10',prefixada='0',base_juros='360',tipo_liberacao='cronograma',liberacoes={2026:'500',2027:'500',2028:'0'},comissao_credito='.75')
    f=calcular_fluxo_contratual(e)
    primeira=next(l for l in f['linhas'] if Decimal(l['juros_financeiros'])>0)
    assert Decimal(primeira['juros_financeiros'])==Decimal('25.14') # 500 * 10% * 181/360
    assert Decimal(primeira['comissao_credito'])==Decimal('1.89') # 500 ainda não recebido
    assert f['memoria_exata']['liberacoes'][1]['data']=='2027-07-15'
    assert Decimal(f['amortizacao_total'])==1000
    assert Decimal(f['saldo_final'])==0
    saida=calcular_operacao(e,serie_ipca={})
    assert [Decimal(l['liberacaoNovaOperacao']) for l in saida['bases_fluxo']]==[500,500,0]
    assert sum(Decimal(l['juros_encargos']) for l in saida['servico_input']['linhas'])==Decimal(f['juros_total'])


def test_amortizacao_nunca_antecipa_dinheiro_nao_desembolsado():
    f=calcular_fluxo_contratual(entrada(fim=2028,prazo_meses=24,carencia_meses=0,periodicidade_amortizacao=6,tipo_liberacao='cronograma',liberacoes={2026:'100',2027:'900',2028:'0'}))
    assert all(Decimal(l['saldo_final'])>=0 for l in f['linhas'])
    assert Decimal(f['amortizacao_total'])==1000


@pytest.mark.parametrize('alteracao',[dict(liberacoes={2026:'1'},tipo_liberacao='cronograma'),dict(periodicidade_juros=2),dict(fim=2030),dict(comissao_credito='-1'),dict(mes_liberacoes=13),dict(indexador='IPCA')])
def test_rejeita_condicoes_invalidas(alteracao):
    with pytest.raises(ValueError):calcular_fluxo_contratual(entrada(**alteracao))


def registros():
    return [dict(exercicio=2026,periodo=2,coluna='Até o 2º Quadrimestre',conta=conta,valor=valor) for conta,valor in [('DÍVIDA CONSOLIDADA LÍQUIDA (DCL) (III)',1000),('RECEITA CORRENTE LÍQUIDA AJUSTADA PARA CÁLCULO DOS LIMITES DE ENDIVIDAMENTO (VI)',1000)]]


def test_dcl_cenario_nao_substitui_posicao_publicada_nem_inventa_outras():
    d=demonstrar_dcl(2026,registros(),1000)
    assert d['percentual'] is None and d['aprovado'] is None
    d=demonstrar_dcl(2026,registros(),1000,0,True,'Fonte declarada')
    assert Decimal(d['percentual'])==200 and d['resultado_numerico']=='Dentro do limite'
    assert d['aprovado'] is None # nunca transforma demonstração em autorização
    assert demonstrar_dcl(2026,registros()+[registros()[0]],1000,0)['percentual'] is None
    mais=registros()+[dict(exercicio=2026,periodo=3,coluna='Até o 3º Quadrimestre',conta='DÍVIDA CONSOLIDADA LÍQUIDA (DCL) (III)',valor=None)]
    assert demonstrar_dcl(2026,mais,1000,0)['dcl_publicada'] is None


def test_mga_mesma_rcl_nao_confunde_percentual_isolado_com_total():
    bases=[dict(ano=2026,liberacaoNovaOperacao='160',rclProjetada='1000')]
    r=demonstrar_mga(bases)
    assert r['linhas'][0]['percentual_nova_operacao']=='16.00' and r['linhas'][0]['percentual'] is None
    r=demonstrar_mga(bases,{2026:'0'},True,'Fonte')
    assert r['cobertura_confirmada'] and r['anos_acima']==[]
    assert demonstrar_mga(bases,{2026:'.01'})['anos_acima']==[2026]

@pytest.mark.parametrize('referencia',['SOFR','FIXA'])
def test_spreads_capital_e_captacao_nao_sao_comissao(referencia):
    # SOFR: (3.69+1+1.9)*365/360. Fixa: (1.10*1.03*1.03-1)*1000.
    if referencia=='SOFR':
        e=entrada(indexador='SOFR',taxa_indexador='3.69',prefixada='0',spread='1',spread_capital='1.9',base_juros='360')
        f=calcular_fluxo_contratual(e)
        assert Decimal(f['juros_financeiros_total'])==((Decimal('1000')*Decimal('.0659')*365/360).quantize(Decimal('.01')))
    else:
        f=calcular_fluxo_contratual(entrada(spread='3',spread_capital='3'))
        assert Decimal(f['juros_financeiros_total'])==Decimal('166.99')
    assert Decimal(f['comissao_credito_total'])==0
