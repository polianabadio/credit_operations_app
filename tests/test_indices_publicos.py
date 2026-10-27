import pytest
from src.simulador.indices_publicos import consultar_ipca


def test_consulta_mes_exato(monkeypatch):
    class Resposta:
        def raise_for_status(self): pass
        def json(self): return [{"data": "01/09/2026", "valor": "0.82"}]
    def buscar(url, **kwargs):
        assert kwargs["params"]["dataInicial"] == "01/09/2026"
        assert kwargs["timeout"] == 15
        return Resposta()
    monkeypatch.setattr("src.simulador.indices_publicos.requests.get", buscar)
    assert consultar_ipca("2026-09")["valor"] == "0.82"


def test_mes_sem_publicacao_nao_vira_zero(monkeypatch):
    class Resposta:
        def raise_for_status(self): pass
        def json(self): return []
    monkeypatch.setattr("src.simulador.indices_publicos.requests.get", lambda *a, **k: Resposta())
    with pytest.raises(ValueError, match="ainda"):
        consultar_ipca("2027-01")


@pytest.mark.parametrize("mes", [None, "", "2026-13", "2026-1"])
def test_rejeita_mes_invalido(mes):
    with pytest.raises(ValueError):
        consultar_ipca(mes)


def test_serie_divide_intervalos_e_preserva_mes_civil(monkeypatch):
    from datetime import date
    from src.simulador.indices_publicos import obter_serie_ipca, _cache_serie
    _cache_serie.clear()
    chamadas = []
    class Resposta:
        def raise_for_status(self): pass
        def json(self): return [{'data': '01/09/2026', 'valor': '.82'}]
    def buscar(url, **kwargs):
        chamadas.append(kwargs['params'])
        return Resposta()
    monkeypatch.setattr('src.simulador.indices_publicos.requests.get', buscar)
    assert obter_serie_ipca('2010-01', hoje=date(2026, 10, 16)) == {'2026-09': '0.82'}
    assert len(chamadas) == 2
    assert chamadas[0]['dataFinal'] == '31/12/2019'
    assert chamadas[1]['dataInicial'] == '01/01/2020'
    obter_serie_ipca('2010-01', hoje=date(2026, 10, 16))
    assert len(chamadas) == 2
    _cache_serie.clear()


def test_bcb_repete_falha_temporaria(monkeypatch):
    import requests
    from src.simulador.indices_publicos import _consultar_bcb
    chamadas = []
    resposta = requests.Response()
    resposta.status_code = 502
    def buscar(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) < 3:
            raise requests.HTTPError('detalhe tecnico', response=resposta)
        return type('Resposta', (), {'raise_for_status': lambda self: None})()
    monkeypatch.setattr('src.simulador.indices_publicos.requests.get', buscar)
    assert _consultar_bcb('https://example.test') is not None
    assert len(chamadas) == 3


def test_bcb_falha_com_mensagem_clara(monkeypatch):
    import requests
    from src.simulador.indices_publicos import _consultar_bcb
    def buscar(*args, **kwargs):
        raise requests.Timeout('URL e detalhes internos')
    monkeypatch.setattr('src.simulador.indices_publicos.requests.get', buscar)
    with pytest.raises(ValueError, match='Não foi possível consultar o IPCA') as erro:
        _consultar_bcb('https://example.test')
    assert 'URL' not in str(erro.value)
