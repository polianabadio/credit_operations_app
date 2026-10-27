from datetime import date
from decimal import Decimal
import math
import json
from pathlib import Path

import pytest

from src.simulador.fluxo_tlp import calcular_fluxo_tlp, montar_periodos, dias_excel, proximo_util


def calcular(**alteracoes):
    entrada = dict(valor='500000000', data_liberacao='2026-11-29', prazo_meses=240,
                   carencia_meses=24, prefixada=7, spread='3.38',
                   indices={'2026-09': '.82'}, repetir_ultimo=True,
                   hoje=date(2026, 10, 16), ipca_ausente_zero=False)
    entrada.update(alteracoes)
    return calcular_fluxo_tlp(**entrada)


def test_corte_dia_15_e_defasagem_menos_um():
    antes = montar_periodos('2026-11-15', 12, 0)[0]
    depois = montar_periodos('2026-11-16', 12, 0)[0]
    assert antes['referencia'] == date(2026, 10, 15)
    assert antes['competencia_ipca'] == '2026-09'
    assert depois['referencia'] == date(2026, 11, 15)
    assert depois['competencia_ipca'] == '2026-10'


def test_calendario_excel_inclusivo_feriado_e_fim_de_semana():
    assert proximo_util(date(2026, 11, 15)) == date(2026, 11, 16)
    assert proximo_util(date(2026, 1, 1)) == date(2026, 1, 2)
    assert dias_excel(date(2026, 1, 1), date(2026, 1, 5)) == 1
    assert dias_excel(date(2026, 1, 2), date(2026, 1, 5)) == 1


def test_modelo_24_216_sem_linha_adicional_com_divisor_zero():
    r = calcular()
    assert len(r['linhas']) == 239
    assert len([l for l in r['linhas'] if Decimal(l['amortizacao']) > 0]) == 216
    assert all(Decimal(l['amortizacao']) == 0 for l in r['linhas'][:23])
    assert [l['mes'] for l in r['linhas'][:23] if l['pagamento']] == [3, 6, 9, 12, 15, 18, 21]
    assert r['linhas'][23]['amortiza']
    assert Decimal(r['saldo_final']) == 0
    assert Decimal(r['amortizacao_total']) == 500000000
    assert sum(Decimal(a['total']) for a in r['anuais']) == Decimal(r['pagamento_total'])


def test_formula_independente_colunas_i_j_k_l_m_n_em_todas_as_linhas():
    r = calcular()
    saldo, acumulado, restantes = 500000000., 1., 216
    for linha in r['linhas']:
        dup, dut = linha['dup'], linha['dut']
        acumulado *= (1.0082 ** (dup / dut) * 1.07 ** (dup / 252)
                      * 1.0338 ** (dup / 252))
        juros = math.floor(saldo * (acumulado - 1) * 100 + .5) / 100 if linha['pagamento'] else 0
        amortizacao = math.trunc(round(saldo / restantes, 8) * 100) / 100 if linha['amortiza'] else 0
        assert abs(float(linha['juros']) - juros) <= .011
        assert abs(float(linha['amortizacao']) - amortizacao) <= .011
        if linha['pagamento']:
            acumulado = 1.
        if linha['amortiza']:
            restantes -= 1
        saldo = round(saldo - amortizacao, 2)
    assert saldo == 0


def test_reconciliacao_com_478_linhas_salvas_nas_duas_abas_da_planilha():
    fixture = json.loads((Path(__file__).parent / 'fixtures/fcl_tlp_valores_salvos.json').read_text(encoding='utf-8'))
    for caso in fixture['casos']:
        r = calcular(prefixada=caso['taxa'], indices={'2026-09': 0})
        for esperado, atual in zip(caso['linhas'], r['linhas'], strict=True):
            linha, saldo, fim, referencia, dup, dut, fator, juros, amortizacao = esperado
            assert atual['fim'] == fim
            assert atual['referencia'] == referencia
            assert atual['dup'] == dup
            assert atual['dut'] == dut
            assert abs(float(atual['saldo_inicial']) - saldo) < .00001
            assert float(atual['amortizacao']) == amortizacao
            if linha != 37:
                assert abs(float(atual['fator_acumulado']) - fator) < 1e-12
                assert float(atual['juros']) == juros
            else:
                # O arquivo usa C17/L17. O motor reinicia os fatores após pagar a linha36.
                assert float(atual['juros']) < juros


def test_primeiro_dia_nao_util_reproduz_networkdays_menos_um():
    linha = montar_periodos('2026-11-29', 240, 24)[0]
    assert linha['dup'] == 11  # 30/11 a 15/12: 12 dias úteis, menos 1 do Excel.
    assert linha['dut'] == 21


def test_juros_zero_centavos_residuais_e_amortizacao_final():
    r = calcular(valor='1000.01', prefixada=0, spread=0, indices={'2026-09': 0})
    assert Decimal(r['juros_total']) == 0
    assert Decimal(r['amortizacao_total']) == Decimal('1000.01')
    assert Decimal(r['saldo_final']) == 0


def test_futuro_sem_autorizacao_e_lacuna_historica_nao_viram_zero():
    with pytest.raises(ValueError, match='indisponível'):
        calcular(repetir_ultimo=False)
    with pytest.raises(ValueError, match='indisponível'):
        calcular(indices={'2026-12': '.5'}, hoje=date(2027, 1, 15))


def test_ipca_publicado_nao_e_estimativa_e_deflacao_permitida():
    periodos = montar_periodos('2026-01-16', 3, 0)
    indices = {p['competencia_ipca']: '-.2' for p in periodos}
    r = calcular(data_liberacao='2026-01-16', prazo_meses=3, carencia_meses=0,
                 prefixada=0, spread=0, indices=indices, repetir_ultimo=False)
    assert not r['estimado']
    assert Decimal(r['juros_total']) < 0


@pytest.mark.parametrize('alteracao', [dict(prazo_meses=24, carencia_meses=24),
    dict(carencia_meses=5), dict(prazo_meses=2.5), dict(valor=0),
    dict(indices={'2026-09': 'NaN'}), dict(data_liberacao='2060-11-29')])
def test_validacao(alteracao):
    with pytest.raises(ValueError):
        calcular(**alteracao)


def test_ipca_ausente_usa_zero_sem_zerar_taxa_fixa_e_spread():
    r = calcular(ipca_ausente_zero=True)
    assert r['linhas'][0]['ipca'] == '0'
    assert r['linhas'][0]['ipca_ausente_zero']
    assert r['linhas'][0]['ipca_utilizado'] is None
    primeira = next(l for l in r['linhas'] if l['pagamento'])
    assert primeira['juros'] == '10315076.96'
    assert next(a for a in r['anuais'] if a['ano'] == 2027)['juros'] == '48633915.92'


def test_zero_apenas_nos_meses_ausentes():
    r = calcular(data_liberacao='2026-01-16', prazo_meses=3, carencia_meses=0,
                 indices={'2025-12': '.5', '2026-02': '-.1'}, ipca_ausente_zero=True)
    assert [l['ipca'] for l in r['linhas']] == ['0.5', '0', '-0.1']
    assert [l['ipca_ausente_zero'] for l in r['linhas']] == [False, True, False]


def test_serie_vazia_com_consulta_bem_sucedida():
    r = calcular(indices={}, ipca_ausente_zero=True)
    assert all(l['ipca_ausente_zero'] for l in r['linhas'])
    assert Decimal(r['juros_total']) > 0
