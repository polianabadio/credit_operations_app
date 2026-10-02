from decimal import Decimal

import pytest

from src.simulador.servico_divida import (
    avaliar_alternativas, avaliar_exercicio_anterior, avaliar_hipotese,
    projetar_anos,
)


def test_historico_e_igualdade_reprovada():
    aprovado = avaliar_exercicio_anterior("100", "5", "6.5")
    assert aprovado["limite"] == Decimal("11.500")
    assert aprovado["aprovado"] is False
    assert aprovado['margem'] == Decimal('0.000')
    assert avaliar_exercicio_anterior("100", "5", "6.49")["aprovado"] is True
    assert avaliar_exercicio_anterior("100", "5", "7")["aprovado"] is False
    com_restos = avaliar_exercicio_anterior("100", "5", "5", "0.5", "0.5")
    assert com_restos['servico_divida'] == Decimal('11.0')
    assert com_restos['aprovado'] is True


def test_limite_historico_usa_somente_rcl_e_percentual():
    historico = avaliar_exercicio_anterior('100', '15', '0')
    assert historico['rcl'] == Decimal('100')
    assert historico['limite'] == Decimal('11.500')
    assert historico['percentual'] == Decimal('0.15')
    assert historico['aprovado'] is False
    assert 'fator' not in historico
    assert 'rcl_ajustada_pelo_fator' not in historico


@pytest.mark.parametrize("rcl,juros,amortizacao", [(None, 1, 2), (100, None, 2), (100, 1, "nan"), (0, 1, 2)])
def test_historico_rejeita_dados_insuficientes(rcl, juros, amortizacao):
    with pytest.raises(ValueError):
        avaliar_exercicio_anterior(rcl, juros, amortizacao)


def test_projecao_multiplos_anos_sem_arredondamento():
    linhas = projetar_anos("100", [
        {"ano": 2027, "juros_encargos": "1.111", "amortizacao": "2.222"},
        {"ano": 2026, "juros_encargos": "1", "amortizacao": "1"},
    ], ano_base=2025)
    assert [linha["ano"] for linha in linhas] == [2026, 2027]
    assert linhas[1]["servico_divida"] == Decimal("3.333")
    assert linhas[1]["rcl_projetada"] == Decimal("100") * Decimal("2.031208231") ** 2
    assert linhas[1]['limite'] == linhas[1]['rcl_projetada'] * Decimal('0.115')
    assert linhas[1]['margem'] == linhas[1]['limite'] - linhas[1]['servico_divida']
    assert avaliar_hipotese(linhas)["media_percentual"] == (
        linhas[0]["percentual"] + linhas[1]["percentual"]
    ) / 2


def test_alternativas_or_sequencial():
    baixa = [{"ano": 2026, "percentual": Decimal("0.1")}]
    alta = [{"ano": 2026, "percentual": Decimal("0.2")}]
    assert avaliar_alternativas(baixa)["hipotese_2"] is None
    assert avaliar_alternativas(alta, baixa)["proxima_etapa"] == "Divida_Consolidada"
    assert avaliar_alternativas(alta, alta)["aprovado"] is False
    assert avaliar_alternativas(alta)["aprovado"] is None
    assert avaliar_alternativas([{"ano": 2026, "percentual": Decimal('0.115')}], baixa)['aprovado'] is True
    media = avaliar_hipotese([{'ano': 2026, 'percentual': Decimal('0.20')},
                             {'ano': 2027, 'percentual': Decimal('0.02')}])
    assert media['media_percentual'] == Decimal('0.11')
    assert media['aprovado'] is True
    with pytest.raises(ValueError, match="2027"):
        avaliar_alternativas(alta, [{"ano": 2028, "percentual": Decimal("0.1")}])


def test_fator_pode_ser_parametrizado():
    linhas = projetar_anos("100", [{"ano": 2026, "juros_encargos": 1, "amortizacao": 1}],
                          ano_base=2025, fator="1.05")
    assert linhas[0]["rcl_projetada"] == Decimal("105.00")


def test_projecao_de_um_ano_e_margem_negativa():
    linhas = projetar_anos('100', [
        {'ano': 2026, 'juros_encargos': '20', 'amortizacao': '0'},
    ], ano_base=2025, fator='1')
    assert linhas[0]['margem'] == Decimal('-8.500')
    assert avaliar_hipotese(linhas)['aprovado'] is False


def test_media_aprova_mesmo_com_um_ano_acima_do_limite():
    linhas = projetar_anos('100', [
        {'ano': 2026, 'juros_encargos': '20', 'amortizacao': '0'},
        {'ano': 2027, 'juros_encargos': '0', 'amortizacao': '0'},
    ], ano_base=2025, fator='1')
    assert linhas[0]['margem'] < 0
    assert linhas[1]['margem'] > 0
    assert avaliar_hipotese(linhas)['aprovado'] is True


@pytest.mark.parametrize('ano,juros,amortizacao', [
    (2025, '1', '1'), (2026, None, '1'), (2026, '-1', '1'),
])
def test_projecao_rejeita_ano_invalido_e_campo_vazio_ou_negativo(ano, juros, amortizacao):
    with pytest.raises(ValueError):
        projetar_anos('100', [
            {'ano': ano, 'juros_encargos': juros, 'amortizacao': amortizacao},
        ], ano_base=2025, fator='1')


def test_projecao_valor_alto_preserva_decimal():
    linhas = projetar_anos('1000000000000000.01', [
        {'ano': 2026, 'juros_encargos': '999999999999999.99', 'amortizacao': '0.01'},
    ], ano_base=2025, fator='1')
    assert linhas[0]['servico_divida'] == Decimal('1000000000000000.00')
    assert linhas[0]['margem'] == linhas[0]['limite'] - Decimal('1000000000000000.00')


def test_regra_aparece_na_analise_sem_aprovacao_indevida(monkeypatch):
    from src.simulador import rule_engine as engine
    monkeypatch.setattr(engine, 'carregar_modelo_yaml', lambda: {
        'Primeira_Etapa': [{'Regra_do_Dispendio_115_RCL_Estimada': {}}]})
    monkeypatch.setattr(engine, 'obter_dados_rreo_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_dados_rgf_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_rcl_ajustada_endividamento', lambda ano: {
        'valor': Decimal('100'), 'periodo': 6, 'origem': 'SICONFI/RREO'})
    monkeypatch.setattr(engine, 'obter_servico_divida_exercicio_anterior', lambda ano: None)
    monkeypatch.setattr(engine, 'obter_fator_projecao', lambda: '2.031208231')
    resultado = engine.analisar_operacao(2026)
    assert not resultado['regras_cumpridas']
    assert not resultado['regras_violadas']
    pendente = resultado['regras_sem_informacao'][0]
    assert pendente['tipo'] == 'servico_divida'
    assert pendente['status'] == 'Sem informação'
    assert pendente['dados_calculados']['rcl_historica'] == 100.0
    assert pendente['dados_calculados']['ano_historico'] == 2025
    assert pendente['dados_calculados']['rcl_atual'] == 100.0
    assert pendente['dados_calculados']['ano_atual'] == 2026


def test_regra_visivel_sem_rcl(monkeypatch):
    from src.simulador import rule_engine as engine
    monkeypatch.setattr(engine, 'carregar_modelo_yaml', lambda: {
        'Primeira_Etapa': [{'Regra_do_Dispendio_115_RCL_Estimada': {}}]})
    monkeypatch.setattr(engine, 'obter_dados_rreo_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_dados_rgf_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_rcl_ajustada_endividamento', lambda ano: None)
    monkeypatch.setattr(engine, 'obter_servico_divida_exercicio_anterior', lambda ano: None)
    monkeypatch.setattr(engine, 'obter_fator_projecao', lambda: '2.031208231')
    resultado = engine.analisar_operacao(2026)
    assert resultado['regras_sem_informacao'][0]['dados_calculados']['rcl_historica'] is None
    assert not resultado['circuit_breaker']


def test_fluxo_integrado_historico_e_hipoteses(monkeypatch):
    from src.simulador import rule_engine as engine
    from src.simulador.data_access import CONTAS_SERVICO_DIVIDA, COLUNA_LIQUIDADA, COLUNA_RESTOS
    monkeypatch.setattr(engine, 'obter_rcl_ajustada_endividamento', lambda ano: {
        'valor': Decimal('100'), 'periodo': 6, 'origem': 'SICONFI/RREO'})
    monkeypatch.setattr(engine, 'obter_fator_projecao', lambda: '1')
    def despesas(juros):
        return {'periodo': 6, 'contas': {
            CONTAS_SERVICO_DIVIDA[0]: {COLUNA_LIQUIDADA: Decimal(juros), COLUNA_RESTOS: None},
            CONTAS_SERVICO_DIVIDA[1]: {COLUNA_LIQUIDADA: Decimal('1'), COLUNA_RESTOS: None},
        }}
    monkeypatch.setattr(engine, 'obter_servico_divida_exercicio_anterior', lambda ano: despesas('10.5'))
    assert engine._resultado_servico_divida(2026)['aprovado'] is False  # igualdade
    monkeypatch.setattr(engine, 'obter_servico_divida_exercicio_anterior', lambda ano: despesas('1'))
    assert engine._resultado_servico_divida(2026)['aprovado'] is None
    entrada = {'ano_fim_contrato': 2027, 'fator': '1', 'hipotese_1': [
        {'ano': 2026, 'juros_encargos': '1', 'amortizacao': '1'},
        {'ano': 2027, 'juros_encargos': '1', 'amortizacao': '1'},
    ], 'hipotese_2': [{'ano': 2028, 'juros_encargos': '999', 'amortizacao': '999'}]}
    primeiro = engine._resultado_servico_divida(2026, entrada)
    assert primeiro['aprovado'] is True
    assert primeiro['nome'] == 'Projeção do Serviço da Dívida'
    assert primeiro['dados_calculados']['referencia_rreo_atual']['juros_encargos'] == '1'
    assert primeiro['dados_calculados']['hipotese_2'] is None  # nem valida a segunda
    entrada['fator'] = '2'
    com_fator = engine._resultado_servico_divida(2026, entrada)
    assert com_fator['dados_calculados']['historico']['limite'] == 11.5
    assert com_fator['dados_calculados']['hipotese_1']['linhas'][0]['rcl_projetada'] == 200.0
    assert com_fator['dados_calculados']['memoria_exata']['limite_historico'] == '11.500'
    entrada['fator'] = '1'
    entrada['hipotese_1'][0]['juros_encargos'] = '30'
    entrada['hipotese_1'][1]['juros_encargos'] = '30'
    entrada['hipotese_2'] = [{'ano': 2026, 'juros_encargos': None, 'amortizacao': None}]
    incompleta = engine._resultado_servico_divida(2026, entrada)
    assert incompleta['aprovado'] is None
    assert incompleta['dados_calculados']['hipotese_1']['aprovado'] is False
    entrada['hipotese_2'] = [{'ano': 2026, 'juros_encargos': '1', 'amortizacao': '1'}]
    assert engine._resultado_servico_divida(2026, entrada)['aprovado'] is True
    entrada['hipotese_2'][0]['juros_encargos'] = '30'
    assert engine._resultado_servico_divida(2026, entrada)['aprovado'] is False


def test_divida_consolidada_so_depois_do_servico(monkeypatch):
    from src.simulador import rule_engine as engine
    monkeypatch.setattr(engine, 'carregar_modelo_yaml', lambda: {'Etapa': [
        {'Regra_do_Dispendio_115_RCL_Estimada': {}}, {'Divida_Consolidada': {}}]})
    monkeypatch.setattr(engine, 'obter_dados_rreo_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_dados_rgf_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, '_resultado_servico_divida', lambda ano, entrada=None: {
        'tipo': 'servico_divida', 'nome': 'Serviço', 'aprovado': False,
        'status': 'Violada', 'descricao': 'Reprovada', 'dados_calculados': {}})
    monkeypatch.setattr(engine, 'obter_registros_dcl', lambda ano: pytest.fail('DCL executada antes da hora'))
    resultado = engine.analisar_operacao(2026)
    assert resultado['circuit_breaker'] is True
    assert len(resultado['regras_violadas']) == 1
