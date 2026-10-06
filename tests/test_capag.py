import pytest
import requests

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.simulador import capag
from src.simulador.capag import extrair_nota_go, extrair_indicadores_go
from src.simulador.database_models import CapagPublicada, CapagIndicadores


def test_capag_usa_classificacao_da_coluna_h_para_go():
    csv = ('UF;Indicador 1;Nota 1;Indicador 2;Nota 2;Indicador 3;Nota 3;'
           'Classificação da CAPAG\n'
           'DF;1;A;2;B;3;C;B\n'
           'GO;1;A;2;B;3;C;A+\n')
    assert extrair_nota_go(csv.encode('utf-8')) == 'A+'


def test_capag_nao_inventa_nota_ausente():
    with pytest.raises(ValueError, match='não foi encontrado'):
        extrair_nota_go(b'UF;1;2;3;4;5;6;7\nDF;1;2;3;4;5;6;A\n')


def test_capag_le_percentuais_e_notas_da_mesma_linha():
    conteudo = ('UF;Indicador 1;Nota 1;Indicador 2;Nota 2;Indicador 3;Nota 3;CAPAG\n'
                'DF;1;C;2;C;3;C;C\n'
                'GO;68,54;B;87,10;B;15,44;A;B+\n').encode('utf-8')
    dados = extrair_indicadores_go(conteudo)
    assert dados['nota'] == 'B+'
    assert dados['indicadores']['endividamento'] == {'valor': Decimal('68.54'), 'nota': 'B'}
    assert dados['indicadores']['poupanca_corrente'] == {'valor': Decimal('87.10'), 'nota': 'B'}
    assert dados['indicadores']['liquidez_relativa'] == {'valor': Decimal('15.44'), 'nota': 'A'}


def test_capag_usa_ultima_publicacao_completa_e_persiste_referencia(monkeypatch):
    csv_completo = ('UF;Indicador 1;Nota 1;Indicador 2;Nota 2;Indicador 3;Nota 3;CAPAG\n'
                    'GO;68,54;B;87,10;B;15,44;A;B+\n').encode('utf-8')
    csv_incompleto = b'UF;1;2;3;4;5;6;7\nGO;;B;87,10;B;15,44;A;B+\n'
    pacote = {'result': {'resources': [
        {'name': 'Capag Estados 2026', 'format': 'CSV', 'url': 'https://fonte/2026'},
        {'name': 'Capag Estados 2025', 'format': 'CSV', 'url': 'https://fonte/2025',
         'description': 'Capag dos Estados Ano Base 2024'},
    ]}}

    class Resposta:
        def __init__(self, conteudo=None, json=None):
            self.content = conteudo
            self._json = json

        def raise_for_status(self):
            pass

        def json(self):
            return self._json

    def get(url, **_):
        if url == capag.PACOTE:
            return Resposta(json=pacote)
        return Resposta(conteudo=csv_incompleto if url.endswith('2026') else csv_completo)

    engine = create_engine('sqlite://')
    sessao = Session(bind=engine)
    monkeypatch.setattr(capag.db, 'session', sessao)
    monkeypatch.setattr(capag.requests, 'get', get)
    assert capag.atualizar_capag() == 'B+'
    dto = capag.obter_capag()
    assert dto['ano'] == 2025
    assert dto['ano_base'] == 2024
    assert dto['url'] == 'https://fonte/2025'
    assert dto['indicadores']['liquidez_relativa'] == {'valor': 15.44, 'nota': 'A'}
    assert sessao.query(CapagPublicada).count() == 1
    assert sessao.query(CapagIndicadores).count() == 1
    sessao.close()


def test_falha_de_rede_na_capag_nao_dispara_download_de_todo_historico(monkeypatch):
    urls = []

    class Pacote:
        def raise_for_status(self):
            pass

        def json(self):
            return {'result': {'resources': [
                {'name': 'Capag Estados 2026', 'format': 'CSV', 'url': 'https://fonte/2026'},
                {'name': 'Capag Estados 2025', 'format': 'CSV', 'url': 'https://fonte/2025'},
            ]}}

    def get(url, **_):
        if url == capag.PACOTE:
            return Pacote()
        urls.append(url)
        raise requests.Timeout('Consulta indisponível')

    monkeypatch.setattr(capag.requests, 'get', get)
    with pytest.raises(requests.Timeout):
        capag.atualizar_capag()
    assert urls == ['https://fonte/2026']
