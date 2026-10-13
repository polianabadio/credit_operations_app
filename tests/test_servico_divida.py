from copy import deepcopy
from decimal import Decimal

import pytest

from src.simulador.parametros_simulacao import obter_fator_projecao
from src.simulador.servico_divida import (
    avaliar_caed,
    avaliar_exercicio_anterior,
    projetar_rcl,
)


def fator(valor='1', data='2026-12-31'):
    # Parâmetro controlado apenas para testes matemáticos isolados.
    return {**obter_fator_projecao(data), 'valor': valor}


def referencia(valor='100', periodo=6, ano=2026):
    return {'valor': Decimal(valor), 'exercicio': ano, 'periodo': periodo, 'uf': 'GO',
            'esfera': 'E', 'ente': 52, 'anexo': 'RREO-Anexo 03', 'origem': 'SICONFI/RREO',
            'data_base': f'{ano}-12-31', 'data_referencia': '2026-12-31'}


def entrada(valores=('10',), demais=None):
    demais = demais if demais is not None else ['0'] * len(valores)
    return {'data_referencia': '2026-12-31', 'ano_fim_contrato': 2025 + len(valores),
            'linhas': [{'ano': 2026 + i, 'juros_encargos': v, 'amortizacao': '0',
                        'demais_operacoes': demais[i]} for i, v in enumerate(valores)],
            'cobertura_demais': {'completa': True, 'fonte': 'Cronogramas conferidos, documento teste',
                                'data_referencia': '2026-12-31'}}


def calcular(entr=None, rcl=None, parametro=None):
    return avaliar_caed(2026, entr or entrada(), rcl or referencia(), parametro or fator())


@pytest.mark.parametrize('pagamento,estado', [('11500000', 'ATENDE'), ('11500001', 'NAO_ATENDE')])
def test_media_igual_115_e_115000001(pagamento, estado):
    r = calcular(entrada((pagamento,)), referencia('100000000'))
    assert r['estado'] == estado
    exata = r['dados_calculados']['memoria_exata']
    assert exata['comparador'] == '<='
    assert Decimal(exata['alternativas']['percentual_determinante']) == Decimal(pagamento) / Decimal(100000000)


def test_historico_igualdade_e_diagnostico():
    assert avaliar_exercicio_anterior('100', '5', '6.5')['aprovado'] is True
    assert avaliar_exercicio_anterior('100', '5', '6.51')['aprovado'] is False
    r = avaliar_exercicio_anterior('100', '4', '5', '1', '1')
    assert r['servico_divida'] == Decimal(11)
    assert 'fator' not in r


def test_um_ano_acima_media_abaixo():
    r = calcular(entrada(('20', '1')))
    assert r['estado'] == 'ATENDE'
    assert r['dados_calculados']['linhas'][0]['percentual'] > .115
    assert r['dados_calculados']['media_termino'] == 10.5


def test_soma_pleiteada_e_demais():
    entr = entrada(('5',), ['4'])
    entr['linhas'][0]['amortizacao'] = '2'
    r = calcular(entr)
    l = r['dados_calculados']['linhas'][0]
    assert (l['operacao_pleiteada'], l['demais_operacoes'], l['caed_total']) == (7, 4, 11)
    assert r['estado'] == 'ATENDE'


@pytest.mark.parametrize('alteracao', ['nulo', 'cobertura', 'fonte', 'data', 'futura'])
def test_ausencia_de_demais_nao_e_zero(alteracao):
    entr = entrada()
    if alteracao == 'nulo':
        entr['linhas'][0]['demais_operacoes'] = None
    elif alteracao == 'futura':
        entr['cobertura_demais']['data_referencia'] = '2027-01-01'
    else:
        chave = {'cobertura': 'completa', 'fonte': 'fonte', 'data': 'data_referencia'}[alteracao]
        entr['cobertura_demais'][chave] = False if chave == 'completa' else ''
    r = calcular(entr)
    assert r['estado'] == 'INCONCLUSIVO'
    assert r['aprovado'] is None
    assert r['dados_calculados']['memoria_exata']['linhas']
    assert r['dados_calculados']['motivos']


def test_alternativa_2027_mais_benefica_mesmo_cronograma():
    entr = entrada(('10', '10', '30'))
    antes = deepcopy(entr)
    r = calcular(entr)
    d = r['dados_calculados']
    assert r['estado'] == 'ATENDE'
    assert d['media_termino'] > 11.5
    assert d['media_2027'] == 10
    assert d['alternativa_utilizada'] == 'ATE_2027'
    assert d['anos_2027'] == [2026, 2027]
    assert d['anos_termino'] == [2026, 2027, 2028]
    assert entr == antes
    assert len(d['linhas']) == 3


def test_alternativa_termino_mais_benefica():
    r = calcular(entrada(('20', '20', '1', '1')))
    assert r['estado'] == 'ATENDE'
    assert r['dados_calculados']['alternativa_utilizada'] == 'TERMINO_OPERACAO'
    assert r['dados_calculados']['media_2027'] == 20


def test_exclui_anos_sem_pagamentos_da_pleiteada():
    r = calcular(entrada(('0', '12'), ['100', '0']))
    assert r['estado'] == 'NAO_ATENDE'
    assert r['dados_calculados']['anos_termino'] == [2027]
    assert r['dados_calculados']['media_termino'] == 12


def test_2027_nao_aplicavel_quando_pagamentos_so_depois():
    r = calcular(entrada(('0', '0', '10')))
    assert r['estado'] == 'ATENDE'
    assert r['dados_calculados']['media_2027'] is None
    assert r['dados_calculados']['anos_2027'] == []


def test_sem_pagamentos_e_inconclusivo():
    r = calcular(entrada(('0',)))
    assert r['estado'] == 'INCONCLUSIVO'
    assert r['dados_calculados']['motivos'][0]['codigo'] == 'SEM_PAGAMENTOS_ELEGIVEIS'


def test_projecao_fator_oficial_proporcional_e_dezembro():
    p = obter_fator_projecao('2026-10-07')
    assert p['valor'] == '1.02031208231'
    assert p['fonte'] and p['vigencia_inicio'] == '2026-04-22'
    assert projetar_rcl('100', 2026, 6, [2026], p)[2026] == Decimal(100)
    assert projetar_rcl('100', 2025, 6, [2026], p)[2026] == Decimal('102.03120823100')
    valores = projetar_rcl('100', 2026, 3, [2026, 2027], p)
    assert 100 < valores[2026] < 103
    assert valores[2027] == pytest.approx(valores[2026] * Decimal(p['valor']))
    assert projetar_rcl('100', 2026, 6, [2027], p)[2027] < 103


@pytest.mark.parametrize('chave', ['fonte', 'vigencia_inicio', 'referencia_validada_ate', 'data_referencia'])
def test_fator_sem_metadados_nao_usa_legado(chave):
    p = fator()
    p.pop(chave)
    r = avaliar_caed(2026, entrada(), referencia(), p)
    assert r['estado'] == 'INCONCLUSIVO'
    assert r['dados_calculados']['linhas'][0]['rcl_projetada'] is None


@pytest.mark.parametrize('valor', ['0', '-1', 'NaN', 'Infinity'])
def test_rcl_invalida(valor):
    r = avaliar_caed(2026, entrada(), referencia(valor), fator())
    assert r['estado'] == 'INCONCLUSIVO'


def test_rcl_e_fator_ausentes_preservam_memoria():
    r = avaliar_caed(2026, entrada(), None, None)
    assert r['estado'] == 'INCONCLUSIVO'
    assert r['dados_calculados']['memoria_exata']['linhas'][0]['caed_total'] == '10'


@pytest.mark.parametrize('alteracao', ['ano_faltante', 'repetido', 'hipotese_2', 'decimal', 'nulo', 'linha_invalida'])
def test_cronograma_invalido_nao_aprova(alteracao):
    entr = entrada(('10', '10'))
    if alteracao == 'ano_faltante':
        entr['linhas'].pop()
    elif alteracao == 'repetido':
        entr['linhas'][1]['ano'] = 2026
    elif alteracao == 'hipotese_2':
        entr['hipotese_2'] = []
    elif alteracao == 'decimal':
        entr['linhas'][0]['juros_encargos'] = '1.111'
    elif alteracao == 'nulo':
        entr['linhas'][0]['amortizacao'] = None
    else:
        entr['linhas'][0] = None
    r = calcular(entr)
    assert r['estado'] == 'INCONCLUSIVO'
    assert r['dados_calculados']['memoria_exata']['entrada'] == entr


def test_memoria_centavos_sem_float():
    entr = entrada(('999999999999999.99',))
    entr['linhas'][0]['amortizacao'] = '0.01'
    r = calcular(entr, referencia('10000000000000000.00'))
    assert r['dados_calculados']['memoria_exata']['linhas'][0]['caed_total'] == '1000000000000000.00'


@pytest.fixture
def motor(monkeypatch):
    from src.simulador import rule_engine as engine
    monkeypatch.setattr(engine, 'obter_rcl_caed', lambda ano, data: referencia())
    monkeypatch.setattr(engine, 'obter_fator_projecao', lambda data: fator())
    monkeypatch.setattr(engine, 'obter_rcl_ajustada_endividamento', lambda ano: referencia())
    def despesas(ano):
        if ano == 2026:
            pytest.fail('Despesas atuais opcionais não devem ser consultadas')
        return {'periodo': 6, 'contas': {
            engine.CONTAS_SERVICO_DIVIDA[0]: {engine.COLUNA_LIQUIDADA: Decimal(20), engine.COLUNA_RESTOS: None},
            engine.CONTAS_SERVICO_DIVIDA[1]: {engine.COLUNA_LIQUIDADA: Decimal(0), engine.COLUNA_RESTOS: None}}}
    monkeypatch.setattr(engine, 'obter_servico_divida_exercicio_anterior', despesas)
    monkeypatch.setattr(engine, 'carregar_modelo_yaml', lambda: {'Etapa': [
        {'Regra_do_Servico_da_Divida_115_RCL_Estimada': {}}, {'Divida_Consolidada': {}}]})
    monkeypatch.setattr(engine, 'obter_dados_rreo_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_dados_rgf_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_registros_dcl', lambda ano: [])
    return engine


def test_historico_reprovado_nao_bloqueia_prospectiva_e_dcl(motor, monkeypatch):
    monkeypatch.setattr(motor, 'obter_registros_dcl', lambda ano: [])
    r = motor.analisar_operacao(2026, 100, entrada())
    servico = r['regras_cumpridas'][0]
    assert servico['estado'] == 'ATENDE'
    assert servico['dados_calculados']['historico']['aprovado'] is False
    assert servico['dados_calculados']['memoria_exata']['historico']
    assert r['circuit_breaker'] is False


@pytest.mark.parametrize('estado,entr', [('NAO_ATENDE', entrada(('20',))), ('INCONCLUSIVO', None)])
def test_dcl_independente_da_conclusao_prospectiva(motor, monkeypatch, estado, entr):
    chamadas = []
    monkeypatch.setattr(motor, 'obter_registros_dcl', lambda ano: chamadas.append(ano) or [])
    r = motor.analisar_operacao(2026, 100, entr)
    servico = r['regras_ordenadas'][0]
    assert servico['estado'] == estado
    assert r['circuit_breaker'] is (estado == 'NAO_ATENDE')
    assert chamadas == [2026]
    assert 'historico' in servico['dados_calculados']['memoria_exata']


def test_historico_ambiguo_e_opcional(motor, monkeypatch):
    def falhar(ano):
        raise ValueError('Duplicidade')
    monkeypatch.setattr(motor, 'obter_servico_divida_exercicio_anterior', falhar)
    r = motor._resultado_servico_divida(2026, entrada())
    assert r['estado'] == 'ATENDE'
    assert r['dados_calculados']['historico_motivos']


@pytest.mark.parametrize('erro,codigo', [(ValueError('Conflito'), 'DADO_FISCAL_INVALIDO_OU_AMBIGUO'), (RuntimeError('BD'), 'ERRO_TECNICO_FISCAL')])
def test_erros_fiscais_nao_aprovam(motor, monkeypatch, erro, codigo):
    def falhar(*args):
        raise erro
    monkeypatch.setattr(motor, 'obter_rcl_caed', falhar)
    r = motor._resultado_servico_divida(2026, entrada())
    assert r['estado'] == 'INCONCLUSIVO'
    assert r['dados_calculados']['motivos'][0]['codigo'] == codigo
    assert r['dados_calculados']['memoria_exata']['linhas']


def test_erro_tecnico_na_regra_nao_derruba_ou_aprova_analise(motor, monkeypatch):
    def falhar(*args):
        raise TypeError('Falha técnica')
    monkeypatch.setattr(motor, '_resultado_servico_divida', falhar)
    r = motor.analisar_operacao(2026, 100, entrada())
    assert r['status'] == 'Análise completa.'
    assert r['regras_sem_informacao'][0]['estado'] == 'INCONCLUSIVO'
    assert r['regras_sem_informacao'][0]['dados_calculados']['memoria_exata']['entrada']
