from decimal import Decimal
from types import SimpleNamespace

from src.simulador.indicadores_rgf import _percentual, _resumo_anexo_06


def linha(conta, coluna, valor):
    return SimpleNamespace(conta=conta, coluna=coluna, valor=Decimal(str(valor)))


def test_garantias_usa_quadrimestre_atual_e_nao_soma_saldos():
    linhas = [
        linha('% do TOTAL DAS GARANTIAS sobre a RCL AJUSTADA (V/VIII)',
              'Até o 1º Quadrimestre', 3),
        linha('% do TOTAL DAS GARANTIAS sobre a RCL AJUSTADA (V/VIII)',
              'Até o 2º Quadrimestre', 4),
    ]
    assert _percentual(linhas, 'TOTAL GARANTIAS CONCEDIDAS', 2, 'garantias') == 4


def test_operacoes_usa_percentual_publicado():
    linhas = [linha('TOTAL CONSIDERADO PARA FINS DA APURAÇÃO DO CUMPRIMENTO DO LIMITE',
                    '% SOBRE A RCL AJUSTADA', 8.5)]
    assert _percentual(linhas, 'TOTAL CONSIDERADO PARA FINS DA APURACAO', 2, 'mga') == Decimal('8.5')


def test_aro_usa_zero_publicado_e_nao_inventa_ausente():
    linhas = [linha('OPERAÇÕES DE CRÉDITO POR ANTECIPAÇÃO DA RECEITA ORÇAMENTÁRIA',
                    '% SOBRE A RCL AJUSTADA', 0)]
    assert _percentual(linhas, 'OPERACOES DE CREDITO POR ANTECIPACAO', 1, 'aro') == 0
    assert _percentual([], 'OPERACOES DE CREDITO POR ANTECIPACAO', 1, 'aro') is None


def test_resumo_rgf_06_aceita_zero_explicito_mas_nao_limite():
    linhas = [
        linha('Operações de Crédito - Operações de Crédito Internas e Externas',
              '% SOBRE A RCL AJUSTADA', 0),
        linha('Limite Definido pelo Senado Federal para Operações de Crédito Externas e Internas',
              '% SOBRE A RCL AJUSTADA', 16),
        linha('Operações de Crédito por Antecipação da Receita',
              '% SOBRE A RCL AJUSTADA', 0),
    ]
    assert _resumo_anexo_06(linhas, 'mga') == 0
    assert _resumo_anexo_06(linhas, 'aro') == 0
