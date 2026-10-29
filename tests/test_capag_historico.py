from datetime import datetime

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.simulador.capag import atualizar_historico_capag, extrair_nota_historica
from src.simulador.database_models import CapagHistorico


@pytest.mark.parametrize('csv,nota', [
    ('UF;Indicador 1;Indicador 2;Indicador 3;Classificação da CAPAG;;\nGO;93,35%;95,10%;1820,59%;C;;', 'C'),
    ('Dados gerais em 03/10/2019;;;;;;;\nUF;Indicador 1;Nota 1;Indicador 2;Nota 2;Indicador 3;Nota 3;Classificação da CAPAG\nGO;1;B;2;C;3;C;C', 'C'),
    ('UF;Indicador 1;Nota 1;Indicador 2;Nota 2;Indicador 3;Nota 3;Classificação da CAPAG;Observação\nGO;-;-;-;-;-;-;C;Revisão RRF', 'C'),
])
def test_layouts_historicos_preservam_nota_publicada(csv, nota):
    assert extrair_nota_historica(csv.encode('utf-8-sig'))['nota'] == nota


def test_percentuais_historicos_distinguem_razao_percentual_negativo_e_ausencia():
    cabecalho = 'UF;Indicador 1;Nota 1;Indicador 2;Nota 2;Indicador 3;Nota 3;Classificação da CAPAG\n'
    dados = extrair_nota_historica((cabecalho + 'GO;0,923696551;B;0,962577285;C;-10,21893677;C;C').encode())
    assert dados['indicadores'] == {'endividamento': '92.369655100', 'poupanca_corrente': '96.257728500', 'liquidez_relativa': '-1021.89367700'}
    dados = extrair_nota_historica((cabecalho + 'GO;0%;A;95,10%;B;-;C;C').encode())
    assert dados['indicadores'] == {'endividamento': '0', 'poupanca_corrente': '95.10'}


def test_historico_rejeita_conflito_e_nao_inventa_cabecalho():
    with pytest.raises(ValueError):
        extrair_nota_historica(b'GO;1;A;2;B;3;A;B')
    with pytest.raises(ValueError):
        extrair_nota_historica(b'UF;Classificacao da CAPAG\nGO;B\nGO;C')


def test_cache_revisao_falha_e_ano_ausente(monkeypatch):
    engine = create_engine('sqlite://')
    recursos = [{'name': 'CAPAG Estados 2024', 'format': 'CSV', 'url': 'https://fonte/2024'},
                {'name': 'CAPAG Estados 2024 - Revisão', 'format': 'CSV', 'url': 'https://fonte/revisao', 'description': 'Ano base 2023'},
                {'name': 'CAPAG Estados 2025', 'format': 'CSV', 'url': 'https://fonte/2025'}]
    chamadas = []

    class Resposta:
        content = b'UF;Classificacao da CAPAG;Observacao\nGO;C;Revisao oficial'
        def raise_for_status(self):
            pass

    def get(url, **kwargs):
        chamadas.append(url)
        if url.endswith('2025'):
            raise requests.Timeout('indisponivel')
        return Resposta()

    monkeypatch.setattr('src.simulador.capag.requests.get', get)
    atualizar_historico_capag(engine, {'resources': recursos})
    with Session(engine) as sessao:
        linha = sessao.get(CapagHistorico, (2024, 'GO'))
        assert linha.revisao and linha.ano_base == 2023
        assert linha.observacao == 'Revisao oficial'
        assert sessao.get(CapagHistorico, (2025, 'GO')) is None
    atualizar_historico_capag(engine, {'resources': recursos})
    assert chamadas.count('https://fonte/revisao') == 1
    assert 'https://fonte/2024' not in chamadas
    with Session(engine) as sessao:
        linha = sessao.get(CapagHistorico, (2024, 'GO'))
        linha.consultado_em = datetime(2020, 1, 1)
        sessao.commit()
    def falhar(*args, **kwargs):
        raise requests.Timeout('indisponivel')
    monkeypatch.setattr('src.simulador.capag.requests.get', falhar)
    atualizar_historico_capag(engine, {'resources': recursos})
    with Session(engine) as sessao:
        assert sessao.get(CapagHistorico, (2024, 'GO')).nota == 'C'
        assert sessao.get(CapagHistorico, (2024, 'GO')).revisao
