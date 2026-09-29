import pytest
from src.simulador.dcl import avaliar_dcl, NOME


def registros(anterior, atual, periodo=1):
    return [dict(exercicio=2026, periodo=periodo, conta=NOME, coluna=coluna, valor=valor)
            for coluna, valor in [('SALDO DO EXERCÍCIO ANTERIOR', anterior), (f'Até o {periodo}º Quadrimestre', atual)]]


@pytest.mark.parametrize('anterior,atual,esperado', [
    (33.47, 32.48, True), (200, 200, True), (200.01, 10, False),
    (10, 200.01, False), (110, 110, True), (0, 0, True), (None, 10, None)])
def test_limite_por_percentual(anterior, atual, esperado):
    assert avaliar_dcl(2026, registros(anterior, atual))['aprovado'] is esperado


def test_usa_relatorio_mais_recente_sem_misturar_saldos():
    r = avaliar_dcl(2026, registros(300, 300) + registros(30, 40, 2))
    assert r['dados_calculados']['quadrimestre'] == 2
    assert [v['percentual'] for v in r['dados_calculados']['valores']] == [30, 40]
    assert r['aprovado'] is True


def test_nao_completa_relatorio_incompleto_com_periodo_antigo():
    r = avaliar_dcl(2026, registros(30, 40) + registros(30, None, 2))
    assert r['aprovado'] is None


def test_vazio_ou_outro_ano():
    assert avaliar_dcl(2026, []) is None
    assert avaliar_dcl(2025, registros(30, 40)) is None


@pytest.mark.parametrize('periodo', [1, 2, 3])
def test_seleciona_coluna_do_maior_quadrimestre(periodo):
    linhas = registros(30, 201, periodo)
    for anterior in range(1, periodo):
        linhas += registros(10, 20, anterior)
        linhas.append(dict(exercicio=2026, periodo=periodo, conta=NOME,
                           coluna=f'Até o {anterior}º Quadrimestre', valor=20))
    resultado = avaliar_dcl(2026, linhas)
    assert resultado['dados_calculados']['quadrimestre'] == periodo
    assert resultado['dados_calculados']['valores'][1] == {
        'rotulo': f'Até o {periodo}º Quadrimestre', 'percentual': 201.0}
    assert resultado['aprovado'] is False


def test_orquestracao(monkeypatch):
    from src.simulador import rule_engine as engine
    monkeypatch.setattr(engine, 'carregar_modelo_yaml', lambda: {'Etapa': [{'Divida_Consolidada': {}}]})
    monkeypatch.setattr(engine, 'obter_dados_rreo_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_dados_rgf_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_registros_dcl', lambda ano: registros(201, 40))
    r = engine.analisar_operacao(2026)
    assert r['circuit_breaker'] is True
    assert r['regras_violadas'][0]['tipo'] == 'dcl'
