from decimal import Decimal
import pytest
from src.simulador import cambio
from src.simulador.operacao import calcular_operacao


def operacao(**mais):
    return dict(ano=2026,fim=2027,modelo_fluxo='contratual',valor='1000',indexador='CAMBIAL',moeda_contrato='USD',cotacao_contrato='5.432123',tipo_liberacao='cronograma',liberacoes={'2026':'400','2027':'600'},data_liberacao='2026-01-01',prazo_meses='18',carencia_meses='12',amortizacao_meses='6',periodicidade_amortizacao='6',periodicidade_juros='6',base_juros='360',prefixada='4',spread='1',comissao_credito='.75',mes_liberacoes='1',fator='2',**mais)


@pytest.mark.parametrize('fixo',[False,True])
def test_real_e_dolar_produzem_o_mesmo_fluxo_sem_converter_duas_vezes(fixo):
    extras=dict(calendario_pagamentos='fixo',data_assinatura='2026-01-01',data_vigencia='2026-01-01',primeiro_vencimento_juros='2026-03-15',dias_inicio_comissao=60,prazo_desembolso_meses=60) if fixo else {}
    dolar,ref=cambio.entrada_em_reais(operacao(**extras,moeda_entrada='USD',encargos_anuais={'2026':'1.11','2027':'2.22'}))
    reais=operacao(moeda_entrada='BRL',**extras)
    reais['valor']=dolar['valor'];reais['liberacoes']=dolar['liberacoes'];reais['encargos_anuais']=dolar['encargos_anuais']
    brl,memoria=cambio.entrada_em_reais(reais)
    assert brl['valor']==dolar['valor']
    assert brl['liberacoes']==dolar['liberacoes']
    assert memoria['moeda_entrada']=='BRL'
    assert Decimal(memoria['valor_original'])==1000
    a=calcular_operacao(dolar,serie_ipca={});b=calcular_operacao(brl,serie_ipca={})
    assert a['bases_fluxo']==b['bases_fluxo']
    for chave in ('juros_total','amortizacao_total','pagamento_total','saldo_final'):
        assert a['fluxo'][chave]==b['fluxo'][chave]


def test_base_canonica_preserva_centavos_apos_trocar_unidade():
    e=operacao(moeda_entrada='USD',valor_base_brl='1.33',liberacoes_base_brl={'2026':'.66','2027':'.67'})
    e.update(valor='1',cotacao_contrato='1.333',liberacoes={'2026':'.50','2027':'.50'})
    brl,_=cambio.entrada_em_reais(e)
    assert Decimal(brl['valor'])==Decimal('1.33')
    assert {a:Decimal(v) for a,v in brl['liberacoes'].items()}=={'2026':Decimal('.66'),'2027':Decimal('.67')}
    e['valor_base_brl']='100'
    with pytest.raises(ValueError):cambio.entrada_em_reais(e)


def test_snapshot_manual_nao_usa_api_e_preserva_a_cotacao():
    ref=cambio.registrar_cotacao_contratual('USD','4.98860')
    assert ref['id']=='manual:USD:4.98860'
    assert cambio.referencia(ref['id'])['taxa_brl']=='4.98860'
    valores=cambio.converter_valores(['90366254'],ref['id'],'BRL')
    assert valores[0]['brl']=='450801094.70'
    assert cambio.converter_valores([valores[0]['brl']],'BRL',ref['id'])[0]['valor']=='90366254.00'


def test_moeda_de_preenchimento_nao_pode_divergir_do_snapshot():
    e=operacao(moeda_entrada='EUR',cotacao_id='BRL')
    with pytest.raises(ValueError):cambio.entrada_em_reais(e)
    with pytest.raises(ValueError):cambio.entrada_em_reais(dict(valor='1',moeda_entrada='USD',cotacao_id='BRL'))


@pytest.mark.parametrize('id',['manual:BRL:5','manual:USD:0','manual:USD:NaN','manual:USD:5:extra'])
def test_rejeita_referencias_manuais_invalidas(id):
    with pytest.raises(ValueError):cambio.referencia(id)

def test_conversao_de_campos_concilia_o_total_das_liberacoes_em_reais():
    id=cambio.registrar_cotacao_contratual('USD','1.333')['id']
    campos=[dict(tipo='principal',valor='1'),dict(tipo='liberacao',valor='.50'),dict(tipo='liberacao',valor='.50')]
    r=cambio.converter_entradas(campos,id,'BRL',True)
    assert r['ajuste_liberacoes_brl']=='-0.01'
    assert sum(Decimal(v['brl']) for v in r['valores'][1:])==Decimal(r['valores'][0]['brl'])
    volta=cambio.converter_entradas([dict(valor=v['valor'],base_brl=v['brl'],tipo=c['tipo']) for c,v in zip(campos,r['valores'])],'BRL',id,True)
    assert [v['brl'] for v in volta['valores']]==[v['brl'] for v in r['valores']]
    assert [Decimal(v['valor']) for v in volta['valores']]==[Decimal('1'),Decimal('.5'),Decimal('.5')]


def test_converter_moeda_nao_completa_cronograma_com_soma_errada():
    id=cambio.registrar_cotacao_contratual('USD','1.333')['id']
    r=cambio.converter_entradas([dict(tipo='principal',valor='2'),dict(tipo='liberacao',valor='.5'),dict(tipo='liberacao',valor='.5')],id,'BRL',True)
    assert r['ajuste_liberacoes_brl']=='0'
    assert sum(Decimal(v['brl']) for v in r['valores'][1:])!=Decimal(r['valores'][0]['brl'])
