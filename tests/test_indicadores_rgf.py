from decimal import Decimal
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.simulador.indicadores_rgf import _percentual, _resumo_anexo_06, obter_limite_mga_publicado
from src.simulador.database_models import Base, RGF, db


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


def test_limite_mga_le_valor_publicado_mais_recente_sem_confundir_percentual(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        monkeypatch.setattr(db, 'session', session)
        base = dict(exercicio=2026, periodicidade='Q', instituicao='Goias',
                    uf='GO', co_poder='E', anexo='RGF-Anexo 04', esfera='E',
                    cod_conta='LimiteGeralDefinidoPorResolucaoDoSenadoFederalParaAsOperacoesDeCreditoInternasEExternas',
                    conta='Limite geral')
        session.add_all([
            RGF(**base, periodo=1, coluna='VALOR', valor=Decimal('100')),
            RGF(**base, periodo=2, coluna='% SOBRE A RCL AJUSTADA', valor=Decimal('16')),
            RGF(**base, periodo=2, coluna='VALOR', valor=Decimal('200')),
        ])
        session.commit()
        assert obter_limite_mga_publicado(2026)['valor'] == 200
        assert obter_limite_mga_publicado(2026)['periodo'] == 2
    engine.dispose()
