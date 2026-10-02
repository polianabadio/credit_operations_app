from decimal import Decimal
import pytest
from src.simulador.dtp import consolidar_dtp, classificar_percentual_dtp, SUCESSO, FALHA


def item(valor, **extras):
    r = dict(exercicio=2026, uf='GO', esfera='E', anexo='RGF-Anexo 01',
             coluna='% sobre a RCL Ajustada', co_poder='E', periodo=1,
             valor=Decimal(str(valor)) if valor is not None else None,
             instituicao='Governo de Goiás', conta='DESPESA TOTAL COM PESSOAL - DTP',
             cod_conta='DespesaComPessoalTotal', rotulo='Padrão')
    r.update(extras)
    return r


def completo(linhas, periodo=1):
    return linhas + [item(0, instituicao=f'Instituição adicional {i}', periodo=periodo)
                     for i in range(5)]


@pytest.mark.parametrize('valor,aprovado', [(59.99, True), (60, True), (60.01, False), (0, True)])
def test_limite_total(valor, aprovado):
    r = consolidar_dtp(2026, completo([item(valor)]))
    assert r['aprovado'] is aprovado
    assert r['descricao'] == (SUCESSO if aprovado else FALHA)


def test_soma_poderes_e_nao_avalia_isoladamente():
    r = consolidar_dtp(2026, completo([item(40), item(21, co_poder='J')]))
    assert r['dados_calculados']['percentual'] == 61
    assert r['aprovado'] is False
    assert len(r['dados_calculados']['poderes']) == 2


def test_mesmo_quadrimestre_sem_completar_com_anteriores():
    r = consolidar_dtp(2026, completo([item(40), item(5, co_poder='J'),
        item(2, co_poder='L', periodo=2), item(3, co_poder='M', periodo=2), item(None, periodo=3)]))
    d = r['dados_calculados']
    assert d['percentual'] == 45
    assert d['quadrimestre'] == 1
    assert {p['poder'] for p in d['poderes']} == {'Executivo', 'Judiciário'}
    assert all(p['quadrimestre'] == 1 for p in d['poderes'])


def test_variacoes_de_nome_e_codigo():
    nomes = ['DESPESA TOTAL COM PESSOAL - DTP (VI) = (III a + III b)',
             'DESPESA TOTAL COM PESSOAL - DTP (VII)',
             'despesa total com pessoal (VIII)', ' DESPESA   TOTAL COM PESSOAL ']
    linhas = [item(10, conta=nome, cod_conta=f'outro{i}', instituicao=f'Órgão {i}')
              for i, nome in enumerate(nomes)]
    assert consolidar_dtp(2026, completo(linhas))['dados_calculados']['percentual'] == 40


@pytest.mark.parametrize('nome', [None, '', 'DESPESA BRUTA COM PESSOAL', 'LIMITE MÁXIMO',
                                  'LIMITE PRUDENCIAL', 'LIMITE DE ALERTA'])
def test_nao_inclui_outras_contas(nome):
    assert consolidar_dtp(2026, [item(50, conta=nome)]) is None


@pytest.mark.parametrize('campo,valor', [('uf', 'SP'), ('esfera', 'M'), ('exercicio', 2025),
                                      ('anexo', 'RGF-Anexo 02'), ('coluna', 'VALOR')])
def test_filtros(campo, valor):
    assert consolidar_dtp(2026, [item(10, **{campo: valor})]) is None


def test_deduplicacao_preserva_instituicoes_distintas():
    r = consolidar_dtp(2026, completo([item(10), item(10), item(2, instituicao='Outro órgão')]))
    assert r['dados_calculados']['percentual'] == 12


def test_vazio():
    assert consolidar_dtp(2026, []) is None


def test_orquestrador(monkeypatch):
    from src.simulador import rule_engine as engine
    monkeypatch.setattr(engine, 'carregar_modelo_yaml', lambda: {'Etapa': [{'Despesa_com_Pessoal': {}}]})
    monkeypatch.setattr(engine, 'obter_dados_rreo_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_dados_rgf_para_analise', lambda ano: {})
    monkeypatch.setattr(engine, 'obter_registros_dtp', lambda ano: completo([item(40), item(21, co_poder='J')]))
    r = engine.analisar_operacao(2026)
    assert r['circuit_breaker'] is True
    assert len(r['regras_violadas']) == 1


def test_seis_linhas_da_mesma_instituicao_nao_completam_periodo():
    assert consolidar_dtp(2026, [item(10, cod_conta=str(i)) for i in range(6)]) is None


def test_escolhe_mais_recente_com_seis_instituicoes():
    r = consolidar_dtp(2026, completo([item(40)]) + completo([item(50, periodo=2)], 2))
    assert r['dados_calculados']['quadrimestre'] == 2
    assert r['dados_calculados']['percentual'] == 50


def test_cinco_instituicoes_ou_sexta_sem_valor_nao_completam():
    linhas = [item(10, instituicao=str(i)) for i in range(5)]
    assert consolidar_dtp(2026, linhas + [item(None, instituicao='sexta')]) is None


@pytest.mark.parametrize('valor,faixa', [
    ('54', 'dentro_limite'), ('54.01', 'alerta'),
    ('57', 'alerta'), ('57.01', 'prudencial'),
    ('60', 'prudencial'), ('60.01', 'maximo'),
])
def test_faixas_globais_nos_marcos(valor, faixa):
    assert classificar_percentual_dtp(Decimal(valor), 'Estado consolidado')['faixa'] == faixa


def test_limites_individuais_de_goias():
    executivo = classificar_percentual_dtp(43.74, 'Executivo')
    legislativo = classificar_percentual_dtp(3.23, 'Legislativo')
    assert executivo['limite_maximo'] == 48.6
    assert executivo['limite_alerta'] == 43.74
    assert executivo['faixa'] == 'dentro_limite'
    assert legislativo['limite_maximo'] == 3.4
    assert legislativo['faixa'] == 'alerta'


def test_alerta_individual_nao_reprova_total_global():
    linhas = [
        item(40.58, instituicao='Executivo'),
        item(2.73, co_poder='L', instituicao='Legislativo'),
        item(5.46, co_poder='J', instituicao='Judiciario'),
        item(1.77, co_poder='M', instituicao='Ministerio Publico'),
        item(0, instituicao='Outra instituicao 1'),
        item(0, instituicao='Outra instituicao 2'),
    ]
    dados = consolidar_dtp(2026, linhas)
    assert dados['aprovado'] is True
    assert dados['dados_calculados']['percentual'] == 50.54
    poderes = {p['poder']: p for p in dados['dados_calculados']['poderes']}
    assert poderes['Judiciário']['faixa'] == 'alerta'
    assert poderes['Legislativo']['faixa'] == 'dentro_limite'
