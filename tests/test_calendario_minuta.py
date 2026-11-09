"""Conferência de cláusulas e cálculos fechados, sem app/cache/HTTP."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
import pytest
from src.simulador.calendario_contratual import calendario_fixo
from src.simulador.fluxo_contratual import calcular_fluxo_contratual
from src.simulador.operacao import calcular_operacao


def entrada(**mudancas):
    valores = ['692828.30','16108360.85','27066874.79','24932850.99','18397003.74','3168335.33']
    e = dict(ano=2026, fim=2050, valor='90366254', modelo_fluxo='contratual',
             indexador='SOFR', tipo_liberacao='cronograma', calendario_pagamentos='fixo',
             data_assinatura='2026-07-15',data_vigencia='2026-07-15',data_liberacao='2026-07-15',
             primeiro_vencimento_juros='2026-09-15',prazo_meses=294,carencia_meses=72,
             periodicidade_amortizacao=6,periodicidade_juros=6,mes_liberacoes=7,
             dias_inicio_comissao=60,prazo_desembolso_meses=60,
             taxa_indexador='3.69',prefixada='0',spread='1.21',spread_capital='0',
             comissao_credito='.75',base_juros='360',metodo_sofr='composta_projetada',
             liberacoes={str(a):valores[a-2026] if a<=2031 else '0' for a in range(2026,2051)})
    return {**e, **mudancas}


def test_datas_da_minuta_38_parcelas_e_ajuste_anterior():
    c = calendario_fixo(entrada())
    assert c['primeira_amortizacao'] == date(2032,3,15)
    assert c['termino_nominal'] == date(2051,1,15)
    assert c['fim'] == date(2050,9,15)
    assert c['inicio_comissao'] == date(2026,9,13)
    assert len(c['amortizacoes']) == 38 and len(c['juros']) == 49
    assert all(d.day == 15 and d.month in (3,9) for d in c['juros'])


def test_assinatura_vigencia_e_liberacao_sao_datas_distintas():
    c = calendario_fixo(entrada(data_assinatura='2026-06-01',data_vigencia='2026-08-01',data_liberacao='2026-08-15'))
    assert c['termino_nominal'] == date(2050,12,1)
    assert c['primeira_amortizacao'] == date(2032,3,15)
    assert c['inicio_comissao'] == date(2026,7,31)
    assert c['primeira_liberacao'] == date(2026,8,15)


@pytest.mark.parametrize('campos',[
    dict(data_assinatura=''),dict(data_vigencia=''),dict(primeiro_vencimento_juros=''),
    dict(data_assinatura='2026-08-01'),dict(data_vigencia='2026-08-01'),
    dict(primeiro_vencimento_juros='2026-07-15'),dict(primeiro_vencimento_juros='2027-09-15'),
    dict(periodicidade_amortizacao=3),dict(dias_inicio_comissao=-1),dict(prazo_desembolso_meses=0),
    dict(data_assinatura='2025-07-15')])
def test_dados_ausentes_ou_incoerentes_nao_geram_fluxo(campos):
    with pytest.raises(ValueError):
        calcular_fluxo_contratual(entrada(**campos))


def test_ultimo_ano_e_prazo_de_desembolso_sao_validados():
    with pytest.raises(ValueError, match='termina'):
        calcular_fluxo_contratual(entrada(fim=2051))
    with pytest.raises(ValueError, match='prazo para desembolsos'):
        calcular_fluxo_contratual(entrada(prazo_desembolso_meses=59))


def test_composta_e_spread_por_formula_fechada_primeiro_pagamento():
    f = calcular_fluxo_contratual(entrada())
    p = next(l for l in f['linhas'] if l['fim']=='2026-09-15')
    # 62 dias de 15/07 a 15/09. Comissão começa 13/09: apenas dois dias.
    with localcontext() as ctx:
        ctx.prec=50
        saldo=Decimal('692828.30')
        j=saldo*((1+Decimal('.0369')/360)**62-1)+saldo*Decimal('.0121')*62/360
        c=(Decimal('90366254')-saldo)*Decimal('.0075')*2/360
        assert Decimal(p['juros_financeiros']) == j.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        assert Decimal(p['comissao_credito']) == c.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    assert p['dias_comissao']==2


def test_taxa_total_simples_reproduz_primeiro_pagamento_corrigido():
    # N8 com a taxa total de J8 no PROFISCO III: US$ 692.828,30 por 181 dias.
    e = entrada(fim=2051, data_assinatura='2026-09-15', data_vigencia='2026-09-15',
                data_liberacao='2026-09-15', primeiro_vencimento_juros='2027-03-15',
                taxa_indexador='3.69495', spread='0.41', spread_capital='0.80',
                comissao_credito='0', base_juros='365', metodo_sofr='simples', fator='2')
    e['liberacoes']['2051'] = '0'
    resultado = calcular_operacao(e, serie_ipca={})
    fluxo = resultado['fluxo']
    primeira = next(linha for linha in fluxo['linhas'] if linha['fim'] == '2027-03-15')
    assert Decimal(primeira['juros_financeiros']) == Decimal('16851.79')
    assert '4,90495% a.a.' in fluxo['convencao']
    ano = next(linha for linha in fluxo['anuais'] if linha['ano'] == 2027)
    linha_caed = next(linha for linha in resultado['servico_input']['linhas'] if linha['ano'] == 2027)
    assert linha_caed['juros_encargos'] == ano['juros']


def test_oraculo_independente_diario_25_anos():
    # Benchmark obtido por outro cálculo diário isolado, em USD, com as mesmas
    # hipóteses explicitadas; não é o total do CSV SADIPEM.
    f = calcular_fluxo_contratual(entrada())
    assert Decimal(f['juros_financeiros_total'])==Decimal('55748822.76')
    assert Decimal(f['comissao_credito_total'])==Decimal('1672392.48')
    assert Decimal(f['juros_total'])==Decimal('57421215.24')
    assert Decimal(f['amortizacao_total'])==Decimal('90366254')
    assert Decimal(f['saldo_final'])==0
    assert f['data_final']=='2050-09-15'
    assert f['datas_contratuais']['termino_nominal']=='2051-01-15'
    assert 'sintética' in f['memoria_exata']['origem_sofr']


def test_sem_juros_comissao_ou_encargos_nao_cria_custos():
    f=calcular_fluxo_contratual(entrada(taxa_indexador='0',spread='0',comissao_credito='0'))
    assert Decimal(f['juros_total'])==0 and Decimal(f['saldo_final'])==0


def test_composicao_sofr_rejeita_base_incompativel():
    with pytest.raises(ValueError,match='base 360'):
        calcular_fluxo_contratual(entrada(base_juros='365'))


def test_vencimentos_preservam_ancora_de_fim_de_mes():
    c=calendario_fixo(entrada(data_assinatura='2026-01-01',data_vigencia='2026-01-01',
        data_liberacao='2026-01-01',primeiro_vencimento_juros='2026-01-31',
        prazo_meses=6,carencia_meses=2,periodicidade_juros=1,periodicidade_amortizacao=1))
    assert c['primeira_amortizacao']==date(2026,2,28)
    assert date(2026,3,31) in c['amortizacoes']
    assert date(2026,3,28) not in c['amortizacoes']
    assert c['fim']==date(2026,6,30)


def test_vigencia_posterior_nao_empurra_carencia_para_fora_do_prazo():
    with pytest.raises(ValueError,match='carência'):
        calendario_fixo(entrada(data_assinatura='2026-01-01',data_vigencia='2026-04-01',
            data_liberacao='2026-04-01',primeiro_vencimento_juros='2026-04-15',
            prazo_meses=6,carencia_meses=5,periodicidade_juros=1,periodicidade_amortizacao=1))
