from decimal import Decimal
import pytest
from src.simulador.operacao import calcular_operacao


def entrada():
    return dict(ano=2026, fim=2027, valor='1000', tipo_liberacao='unica',
                data_liberacao='2026-10-15', prazo_meses='12', carencia_meses='0',
                prefixada='7', spread='3.38', fator='5')


def test_bases_compartilham_pagamentos_e_rcl():
    resultado = calcular_operacao(entrada(), serie_ipca={}, rcl_base='10000',
        referencia_rcl={'exercicio': 2025, 'periodo': 6}, fator_projecao=fator())
    assert resultado['bases_fluxo'][0]['liberacaoNovaOperacao'] == '1000'
    assert resultado['bases_fluxo'][1]['liberacaoNovaOperacao'] == '0'
    assert Decimal(resultado['bases_fluxo'][0]['rclProjetada']) == Decimal('10500')
    assert Decimal(resultado['bases_fluxo'][1]['rclProjetada']) == Decimal('11025')
    pagamentos = resultado['servico_input']['linhas']
    assert sum(Decimal(item['amortizacao']) for item in pagamentos) == Decimal('1000')
    assert sum(Decimal(item['juros_encargos']) for item in pagamentos) == Decimal(resultado['fluxo']['juros_total'])


def test_sem_rcl_nao_inventa_receita():
    resultado = calcular_operacao(entrada(), serie_ipca={})
    assert all(item['rclProjetada'] is None for item in resultado['bases_fluxo'])


@pytest.mark.parametrize('alteracoes', [dict(tipo_liberacao='cronograma'), dict(fim=2028), dict(fator='-1'), dict(valor='0')])
def test_rejeita_condicoes_inconsistentes(alteracoes):
    with pytest.raises(ValueError):
        calcular_operacao({**entrada(), **alteracoes}, serie_ipca={})


def fator():
    return {'valor': '1.05', 'fonte': 'Parâmetro local do usuário',
            'vigencia_inicio': '2026-04-22', 'referencia_validada_ate': '2026-12-31',
            'data_referencia': '2026-10-28'}


def test_projecao_respeita_bimestre_da_receita():
    resultado = calcular_operacao(entrada(), serie_ipca={}, rcl_base='10000',
        referencia_rcl={'exercicio': 2026, 'periodo': 3}, fator_projecao=fator())
    from decimal import localcontext
    with localcontext() as contexto:
        contexto.prec = 50
        esperado = Decimal('10000') * Decimal('1.05') ** Decimal('0.5')
    assert Decimal(resultado['bases_fluxo'][0]['rclProjetada']) == esperado


def test_taxa_zero_preserva_receita():
    resultado = calcular_operacao({**entrada(), 'fator': '0'}, serie_ipca={}, rcl_base='10000',
        referencia_rcl={'exercicio': 2025, 'periodo': 6}, fator_projecao=fator())
    assert all(Decimal(l['rclProjetada']) == 10000 for l in resultado['bases_fluxo'])


def test_receita_sem_referencia_nao_inventa_projecao():
    with pytest.raises(ValueError, match='referência'):
        calcular_operacao(entrada(), serie_ipca={}, rcl_base='10000')


def test_pagamentos_nao_confirmam_cobertura_das_demais_operacoes():
    resultado = calcular_operacao(entrada(), serie_ipca={})
    servico = resultado['servico_input']
    assert 'hipotese_1' not in servico and 'fator' not in servico
    assert all(l['demais_operacoes'] is None for l in servico['linhas'])
    assert not servico.get('cobertura_demais')
