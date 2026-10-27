"""Consulta de inflação publicada, sem substituir previsões por índices realizados."""
from datetime import datetime
from decimal import Decimal
import requests
from datetime import date
from time import monotonic

_cache_serie = {}


def _consultar_bcb(url, **kwargs):
    for tentativa in range(3):
        try:
            resposta = requests.get(url, **kwargs)
            resposta.raise_for_status()
            return resposta
        except requests.RequestException as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            transitorio = status is None or status == 429 or status >= 500
            if not transitorio or tentativa == 2:
                raise ValueError(
                    'Não foi possível consultar o IPCA no Banco Central. '
                    'Tente simular novamente em alguns instantes.'
                ) from exc


def obter_serie_ipca(inicio, hoje=None):
    """Busca intervalos de até dez anos; nunca solicita índices futuros."""
    hoje = hoje or date.today()
    inicio = date.fromisoformat(inicio + '-01')
    # Inclui um índice anterior para permitir a hipótese de repetição no futuro.
    inicio = min(inicio, date(hoje.year - 1, hoje.month, 1))
    chave = (inicio.isoformat(), hoje.isoformat())
    armazenado = _cache_serie.get(chave)
    if armazenado and monotonic() - armazenado[0] < 3600:
        return dict(armazenado[1])
    serie = {}
    while inicio <= hoje:
        fim = min(date(inicio.year + 9, 12, 31), hoje)
        resposta = _consultar_bcb('https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados',
                                params={'formato': 'json', 'dataInicial': inicio.strftime('%d/%m/%Y'),
                                        'dataFinal': fim.strftime('%d/%m/%Y')}, timeout=20)
        registros = resposta.json()
        if not isinstance(registros, list):
            raise ValueError('O Banco Central não retornou uma série de inflação válida.')
        for registro in registros:
            mes = datetime.strptime(registro['data'], '%d/%m/%Y').date()
            if mes.strftime('%Y-%m') >= hoje.strftime('%Y-%m'):
                continue
            indice = Decimal(registro['valor'])
            if not indice.is_finite() or indice <= -100:
                raise ValueError('O Banco Central retornou um índice inválido.')
            serie[mes.strftime('%Y-%m')] = str(indice)
        inicio = date(fim.year + 1, 1, 1)
    _cache_serie[chave] = (monotonic(), dict(serie))
    return serie


def consultar_ipca(mes):
    try:
        referencia = datetime.strptime(mes, "%Y-%m")
        if referencia.strftime("%Y-%m") != mes:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Escolha o mês da inflação que deseja consultar.")
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados"
    inicio = referencia.strftime("01/%m/%Y")
    resposta = _consultar_bcb(url, params={"formato": "json", "dataInicial": inicio,
                                       "dataFinal": inicio}, timeout=15)
    registros = resposta.json()
    if not isinstance(registros, list) or not registros:
        raise ValueError("O IPCA deste mês ainda não está disponível na consulta. Para uma previsão, informe uma estimativa e identifique essa hipótese na sua avaliação.")
    registro = next((r for r in registros if r.get("data") == inicio), None)
    if registro is None:
        raise ValueError("Não foi encontrado um índice publicado para o mês escolhido.")
    valor = Decimal(registro["valor"])
    if not valor.is_finite() or valor <= -100:
        raise ValueError("O serviço retornou um índice inválido.")
    return {"valor": str(valor), "mes": mes, "fonte": "IBGE, divulgado pelo Banco Central (série 433)",
            "consultado_em": datetime.now().isoformat(timespec="seconds"), "url": url}
