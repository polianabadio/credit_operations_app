from decimal import Decimal

from src.simulador import painel_fiscal as painel
from src.simulador.dcl import NOME


class ConsultaFake:
    def __init__(self, valor):
        self.valor = valor

    def filter(self, *args):
        return self

    def scalar(self):
        return self.valor


class SessaoFake:
    def __init__(self, ano, consulta=None):
        self.valores = iter((ano, consulta))

    def query(self, *args):
        return ConsultaFake(next(self.valores))


def test_painel_sem_dados_nao_inventa_indicadores(monkeypatch):
    monkeypatch.setattr(painel.db, 'session', SessaoFake(None))
    monkeypatch.setattr(painel, 'obter_capag', lambda: None)
    resposta = painel.obter_painel_fiscal()
    assert resposta['exercicio'] is None
    assert resposta['rcl'] is None
    assert resposta['dcl'] is None
    assert resposta['dados_disponiveis'] == 0
    assert resposta['fontes'] == []


def test_painel_reusa_dados_e_nao_inclui_nova_operacao(monkeypatch):
    monkeypatch.setattr(painel.db, 'session', SessaoFake(2026))
    monkeypatch.setattr(painel, 'obter_indicadores_rgf', lambda ano: {})
    monkeypatch.setattr(painel, 'obter_limite_mga_publicado', lambda ano: None)
    monkeypatch.setattr(painel, '_ultimo_servico_realizado', lambda ano: None)
    monkeypatch.setattr(painel, 'obter_capag', lambda: None)
    monkeypatch.setattr(painel, 'obter_rcl_ajustada_endividamento', lambda ano: {
        'valor': Decimal('100.00'), 'periodo': 4,
        'anexo': 'RREO-Anexo 03', 'origem': 'SICONFI/RREO'})
    monkeypatch.setattr(painel, 'obter_registros_dcl', lambda ano: [
        {'exercicio': ano, 'periodo': 2, 'conta': NOME,
         'coluna': rotulo, 'valor': valor}
        for rotulo, valor in [('Saldo do exercício anterior', 30),
                              ('Até o 2º Quadrimestre', 40)]])
    monkeypatch.setattr(painel, 'obter_registros_dtp', lambda ano: [])
    contas = ['AMORTIZAÇÃO DA DÍVIDA', 'INVERSÕES FINANCEIRAS',
              'INVESTIMENTOS', 'OPERAÇÕES DE CRÉDITO']
    linhas = [{'conta': conta,
               'coluna': 'PREVISÃO ATUALIZADA (a)' if conta == 'OPERAÇÕES DE CRÉDITO'
               else 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)',
               'valor': 1 if conta == 'OPERAÇÕES DE CRÉDITO' else 2,
               'anexo': 'RREO-Anexo 01', 'periodo': 4} for conta in contas]
    monkeypatch.setattr(painel, 'obter_dados_rreo_para_analise', lambda ano: {
        2025: {'registros': []}, 2026: {'registros': linhas}})
    resposta = painel.obter_painel_fiscal()
    assert resposta['rcl']['valor'] == 100
    assert resposta['dcl']['valor'] == 40
    assert resposta['dcl']['margem'] == 160
    assert resposta['dtp'] is None
    assert resposta['regra_ouro'][0]['situacao'] == 'Dados insuficientes'
    atual = resposta['regra_ouro'][1]
    assert atual['situacao'] == 'Atendida'
    assert atual['dados_calculados']['valor_requisitado_na_analise'] == 0
    assert resposta['dados_disponiveis'] == 3
