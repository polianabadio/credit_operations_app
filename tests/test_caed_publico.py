from src.simulador.caed_publico import obter_pagamentos_caed, integrar_pagamentos_caed
from src.simulador.caed_publico import registrar_confirmacao, obter_confirmacao
from src.simulador.caed_publico import obter_pagamentos_dashboard
from src.simulador.servico_divida import avaliar_caed
from tests.test_sadipem import PVL_ATUAL
from tests.test_servico_divida import entrada, referencia, fator


class Cliente:
    def __init__(self, registros, pvl=None):
        self.registros = registros
        self.pvl = pvl or PVL_ATUAL
        self.chamadas = []

    def listar(self, endpoint, params=None, *args):
        self.chamadas.append((endpoint, params))
        return [self.pvl] if endpoint == 'pvl' else self.registros


def consultar(registros, **kwargs):
    return obter_pagamentos_caed(2026, 2027, '2026-10-28', client=Cliente(registros, **kwargs))


def registro(ano=2026, valor='20', **kwargs):
    return {'id_pleito': 74460, 'ano': str(ano), 'demais_operacoes': valor,
            'operacao_pleiteada': '999999', 'total': '999999', **kwargs}


def test_utiliza_somente_demais_operacoes_do_mesmo_pvl():
    resultado = consultar([registro(), registro(2027, '0')])
    assert resultado['pagamentos'] == {2026: '20', 2027: '0'}
    assert resultado['snapshot']['idPleito'] == 74460
    assert resultado['cobertura_confirmada'] is False


def test_dashboard_reutiliza_snapshot_sem_prazo_da_nova_operacao():
    cliente = Cliente([registro(), registro(2050, '0'), registro('Restante a pagar', '300')])
    snapshot = {'idPleito': 74460, 'numeroPvl': 'PVL teste',
                'data': '2026-07-30', 'dataProtocolo': '2026-07-30'}
    dados = obter_pagamentos_dashboard(2026, {'snapshot': snapshot}, client=cliente,
                                       data_referencia='2026-10-29')
    assert dados['status'] == 'Disponível'
    assert dados['pagamentos'] == {2026: '20', 2050: '0'}
    assert dados['saldos_sem_ano'][0]['demais_operacoes'] == '300'
    assert dados['cobertura_confirmada'] is False
    assert cliente.chamadas == [('res-cronograma-pagamentos', {'id_pleito': 74460})]
    assert obter_pagamentos_dashboard(2026, {}, client=cliente)['pagamentos'] == {}


def test_ausente_duplicado_e_invalido_nao_viram_zero():
    assert consultar([])['pagamentos'] == {}
    assert consultar([registro(), registro()])['pagamentos'] == {}
    assert consultar([registro(valor=None)])['pagamentos'] == {}
    assert consultar([registro(valor='-1')])['pagamentos'] == {}
    assert consultar([registro(valor='1.001')])['pagamentos'] == {}


def test_saldo_restante_nao_e_ano_nem_e_rateado():
    resultado = consultar([registro(), registro(ano='Restante a pagar', valor='300')])
    assert resultado['pagamentos'] == {2026: '20'}
    assert resultado['saldos_sem_ano'] == [{'rotulo': 'Restante a pagar', 'demais_operacoes': '300'}]


def test_nao_mistura_pvls_nem_usa_snapshot_antigo_ou_futuro():
    assert consultar([registro(id_pleito=10)])['pagamentos'] == {}
    assert consultar([registro()], pvl={**PVL_ATUAL, 'data_protocolo': '2025-01-01'})['pagamentos'] == {}
    assert consultar([registro()], pvl={**PVL_ATUAL, 'data_status': '01/11/2026'})['pagamentos'] == {}


def test_integracao_preserva_valor_informado_e_ano_desconhecido():
    ent = entrada(('1', '1'), ['3', None])
    resultado = integrar_pagamentos_caed(ent, consultar([registro()]))
    assert resultado['linhas'][0]['demais_operacoes'] == '3'
    assert resultado['linhas'][1]['demais_operacoes'] is None
    assert ent['linhas'][1]['demais_operacoes'] is None


def test_calcula_media_publica_sem_inventar_cobertura():
    ent = entrada(('1', '1'), [None, None])
    ent.pop('cobertura_demais')
    publico = consultar([registro(valor='2'), registro(2027, '3')])
    ent = integrar_pagamentos_caed(ent, publico)
    resultado = avaliar_caed(2026, ent, referencia('1000'), fator())
    dados = resultado['dados_calculados']
    assert dados['media_termino'] == .35
    assert dados['linhas'][0]['caed_total'] == 3
    assert dados['linhas'][1]['caed_total'] == 4
    assert dados['resultado_numerico'] == 'ATENDE'
    assert resultado['aprovado'] is None and resultado['estado'] == 'INCONCLUSIVO'
    assert 'Pagamentos obtidos do PVL público' in resultado['descricao']
    assert dados['memoria_exata']['entrada']['referencia_publica_demais']['snapshot']['idPleito'] == 74460


def test_ano_sem_informacao_impede_media_publica():
    ent = entrada(('1', '1'), [None, None])
    ent.pop('cobertura_demais')
    resultado = avaliar_caed(2026, integrar_pagamentos_caed(ent, consultar([registro()])), referencia(), fator())
    assert resultado['dados_calculados']['media_termino'] is None
    assert resultado['aprovado'] is None


def test_confirmacao_explicita_nao_e_substituida_pela_referencia_publica():
    ent = integrar_pagamentos_caed(entrada(('1',), [None]), consultar([registro(valor='2')]))
    resultado = avaliar_caed(2026, ent, referencia('1000'), fator())
    assert resultado['estado'] == 'ATENDE'
    assert resultado['aprovado'] is True


def test_ponte_busca_e_integra_pagamentos_antes_de_avaliar(monkeypatch):
    import ast
    from pathlib import Path
    from decimal import Decimal
    import src.simulador.data_access as acesso
    import src.simulador.indices_publicos as indices
    import src.simulador.caed_publico as publico
    from tests.test_operacao import entrada as condicoes
    monkeypatch.setattr(acesso, 'obter_rcl_caed', lambda *args: referencia('10000'))
    monkeypatch.setattr(indices, 'obter_serie_ipca', lambda *args: {})
    fonte = consultar([registro(valor='20'), registro(2027, '30')])
    monkeypatch.setattr(publico, 'obter_pagamentos_caed', lambda *args: fonte)
    arvore = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    funcao = next(n for n in arvore.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_calcular_operacao_compartilhada')
    ambiente = {'obter_fator_projecao': lambda data: fator()}
    exec(compile(ast.Module(body=[funcao], type_ignores=[]), 'ponte', 'exec'), ambiente)
    calculo = ambiente[funcao.name]({**condicoes(), 'data_referencia': '2026-10-28'})
    linhas = calculo['servico_input']['linhas']
    assert [l['demais_operacoes'] for l in linhas] == ['20', '30']
    assert sum(Decimal(l['amortizacao']) for l in linhas) == 1000
    assert calculo['servico_input']['referencia_publica_demais']['snapshot']['idPleito'] == 74460


def test_confirmacao_explicita_vinculada_aos_valores_e_intervalo(tmp_path):
    from copy import deepcopy
    caminho = tmp_path / 'confirmacao.json'
    fonte = consultar([registro(valor='2'), registro(2027, '3')])
    assert obter_confirmacao(fonte, 2026, 2027, caminho) is None
    registrar_confirmacao(fonte, 2026, 2027, '2026-10-28', caminho)
    confirmacao = obter_confirmacao(fonte, 2026, 2027, caminho)
    assert confirmacao['completa'] is True
    ent = integrar_pagamentos_caed(entrada(('1', '1'), [None, None]), fonte)
    ent['cobertura_demais'] = confirmacao
    resultado = avaliar_caed(2026, ent, referencia('1000'), fator())
    assert resultado['estado'] == 'ATENDE' and resultado['aprovado'] is True
    outra_consulta = {**fonte, 'consultado_em': '2026-10-29'}
    assert obter_confirmacao(outra_consulta, 2026, 2027, caminho)
    alterada = deepcopy(fonte)
    alterada['pagamentos'][2027] = '4'
    assert obter_confirmacao(alterada, 2026, 2027, caminho) is None
    alterada = deepcopy(fonte)
    alterada['snapshot']['idPleito'] = 10
    assert obter_confirmacao(alterada, 2026, 2027, caminho) is None
    assert obter_confirmacao(fonte, 2026, 2028, caminho) is None


def test_confirmacao_recusa_anos_ausentes(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        registrar_confirmacao(consultar([registro()]), 2026, 2027, '2026-10-28', tmp_path / 'c.json')
