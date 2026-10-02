import pytest

from src.simulador import rule_engine


@pytest.mark.parametrize('valor_requisitado,status_atual', [(0, 'Cumprida'), (200, 'Violada')])
def test_resultados_seguem_ordem_do_modelo_independentemente_do_status(
        monkeypatch, valor_requisitado, status_atual):
    modelo = {'Primeira_Etapa': [
        {'Regra_de_Ouro_Ano_Anterior': {'validacao': {True: {}, False: {}}}},
        {'Regra_de_Ouro_Ano_Atual': {'validacao': {True: {}, False: {}}}},
    ]}
    registros = {
        2025: {'registros': [
            {'conta': 'INVESTIMENTOS', 'coluna': 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)',
             'valor': 100},
        ]},
        2026: {'registros': [
            {'conta': 'INVESTIMENTOS', 'coluna': 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)',
             'valor': 100},
        ]},
    }
    monkeypatch.setattr(rule_engine, 'carregar_modelo_yaml', lambda: modelo)
    monkeypatch.setattr(rule_engine, 'obter_dados_rreo_para_analise', lambda ano: registros)
    monkeypatch.setattr(rule_engine, 'obter_dados_rgf_para_analise', lambda ano: {})

    resultado = rule_engine.analisar_operacao(2026, valor_requisitado)

    assert [(regra['tipo'], regra['status']) for regra in resultado['regras_ordenadas']] == [
        ('regra_ouro_anterior', 'Cumprida'),
        ('regra_ouro_atual', status_atual),
    ]


@pytest.mark.parametrize('dtp_aprovada,servico_aprovado', [(True, False), (False, True)])
def test_dtp_aparece_antes_do_servico_mesmo_quando_calculada_depois(
        monkeypatch, dtp_aprovada, servico_aprovado):
    monkeypatch.setattr(rule_engine, 'carregar_modelo_yaml', lambda: {
        'Primeira_Etapa': [{'Regra_do_Servico_da_Divida_115_RCL_Estimada': {}}],
        'Terceira_Etapa': [{'Despesa_com_Pessoal': {}}],
    })
    monkeypatch.setattr(rule_engine, 'obter_dados_rreo_para_analise', lambda ano: {})
    monkeypatch.setattr(rule_engine, 'obter_dados_rgf_para_analise', lambda ano: {})
    monkeypatch.setattr(rule_engine, 'obter_registros_dtp', lambda ano: [])
    monkeypatch.setattr(rule_engine, '_resultado_servico_divida', lambda ano, entrada: {
        'tipo': 'servico_divida', 'nome': 'Projeção do Serviço da Dívida',
        'aprovado': servico_aprovado,
        'status': 'Cumprida' if servico_aprovado else 'Violada',
    })
    monkeypatch.setattr(rule_engine, 'consolidar_dtp', lambda ano, registros: {
        'tipo': 'dtp', 'nome': 'Despesa Total com Pessoal - DTP',
        'aprovado': dtp_aprovada,
        'status': 'Cumprida' if dtp_aprovada else 'Violada',
    })

    resultado = rule_engine.analisar_operacao(2026)

    assert [regra['tipo'] for regra in resultado['regras_ordenadas']] == ['dtp', 'servico_divida']
