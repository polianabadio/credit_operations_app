import json

from src.simulador import capag_referencias as referencias


def test_referencia_independente_preserva_percentuais_e_proveniencia(tmp_path, monkeypatch):
    caminho = tmp_path / 'referencias.json'
    item = {'ente': 52, 'ano_referencia': 2024, 'tipo': 'referencia_estadual',
            'documento': 'Relatório estadual', 'pagina': 29,
            'fonte': 'https://goias.gov.br/economia/relatorio.pdf', 'consultado_em': '2026-10-29',
            'indicadores': {'endividamento': '68.99', 'poupanca_corrente': '87.10', 'liquidez_relativa': '15.44'}}
    caminho.write_text(json.dumps({'referencias': [item]}), encoding='utf-8')
    monkeypatch.setattr(referencias, 'get_config_file_path', lambda _: caminho)
    resultado = referencias.obter_referencias_indicadores()
    assert resultado[0]['indicadores'] == item['indicadores']
    assert resultado[0]['tipo'] == 'referencia_estadual'
    assert 'nota' not in resultado[0]
    item['indicadores']['liquidez_relativa'] = 'NaN'
    caminho.write_text(json.dumps({'referencias': [item]}), encoding='utf-8')
    assert referencias.obter_referencias_indicadores() == []


def test_referencia_ausente_ou_incompleta_nao_e_zero(tmp_path, monkeypatch):
    caminho = tmp_path / 'referencias.json'
    monkeypatch.setattr(referencias, 'get_config_file_path', lambda _: caminho)
    assert referencias.obter_referencias_indicadores() == []
    caminho.write_text('{"referencias":[{"ente":52}]}', encoding='utf-8')
    assert referencias.obter_referencias_indicadores() == []


def test_notas_documentais_preservam_ano_referencia_e_ano_publicacao(tmp_path, monkeypatch):
    caminho = tmp_path / 'referencias.json'
    monkeypatch.setattr(referencias, 'get_config_file_path', lambda _: caminho)
    item = {'ente': 52, 'tipo': 'serie_retrospectiva', 'documento': 'Relatório Fiscal 2017',
            'ano_documento': 2017, 'pagina': 74, 'consultado_em': '2026-10-29',
            'fonte': 'https://cdn.tesouro.gov.br/relatorio.pdf', 'notas': {'2012': 'B', '2016': 'C'}}
    caminho.write_text(json.dumps({'notas_documentais': [item]}), encoding='utf-8')
    dados = referencias.obter_notas_documentais()
    assert [(x['ano'], x['nota']) for x in dados] == [(2012, 'B'), (2016, 'C')]
    assert all(x['ano_documento'] == 2017 for x in dados)
    assert all('indicadores' not in x for x in dados)
    item['notas']['2012'] = 'X'
    caminho.write_text(json.dumps({'notas_documentais': [item]}), encoding='utf-8')
    assert referencias.obter_notas_documentais() == []
