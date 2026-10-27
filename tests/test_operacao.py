from decimal import Decimal
import pytest
from src.simulador.operacao import calcular_operacao


def entrada():
    return dict(ano=2026, fim=2027, valor='1000', tipo_liberacao='unica',
                data_liberacao='2026-10-15', prazo_meses='12', carencia_meses='0',
                prefixada='7', spread='3.38', fator='1.05')


def test_bases_compartilham_pagamentos_e_rcl():
    resultado = calcular_operacao(entrada(), serie_ipca={}, rcl_base='10000')
    assert resultado['bases_fluxo'][0]['liberacaoNovaOperacao'] == '1000'
    assert resultado['bases_fluxo'][1]['liberacaoNovaOperacao'] == '0'
    assert Decimal(resultado['bases_fluxo'][0]['rclProjetada']) == Decimal('10500')
    assert Decimal(resultado['bases_fluxo'][1]['rclProjetada']) == Decimal('11025')
    pagamentos = resultado['servico_input']['hipotese_1']
    assert sum(Decimal(item['amortizacao']) for item in pagamentos) == Decimal('1000')
    assert sum(Decimal(item['juros_encargos']) for item in pagamentos) == Decimal(resultado['fluxo']['juros_total'])


def test_sem_rcl_nao_inventa_receita():
    resultado = calcular_operacao(entrada(), serie_ipca={})
    assert all(item['rclProjetada'] is None for item in resultado['bases_fluxo'])


@pytest.mark.parametrize('alteracoes', [dict(tipo_liberacao='cronograma'), dict(fim=2028), dict(fator='0'), dict(valor='0')])
def test_rejeita_condicoes_inconsistentes(alteracoes):
    with pytest.raises(ValueError):
        calcular_operacao({**entrada(), **alteracoes}, serie_ipca={})
