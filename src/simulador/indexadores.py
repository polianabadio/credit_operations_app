"""Referências públicas para cenários de juros constantes, com ajuste manual."""
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
from threading import RLock
from time import monotonic
import requests

SERIES = {'CDI': 4389, 'SELIC': 1178, 'TLP': 27572}
NOMES = {'IPCA': 'IPCA', 'TLP': 'TLP', 'CDI': 'CDI', 'SELIC': 'Selic',
         'SOFR': 'SOFR overnight', 'FIXA': 'Sem indexação', 'CAMBIAL': 'Variação cambial'}
_lock = RLock()
_cache, _referencias = {}, {}


def taxa_valida(valor):
    try:
        taxa = Decimal(str(valor))
        if not taxa.is_finite() or not 0 <= taxa <= 1000:
            raise ValueError()
        return taxa
    except (ValueError, TypeError, ArithmeticError):
        raise ValueError('Informe uma taxa anual entre 0 e 1.000%.') from None


def consultar_taxa(indexador, session=None):
    if indexador not in (*SERIES, 'SOFR'):
        raise ValueError('Este indexador não usa uma taxa anual consultável.')
    with _lock:
        anterior = _cache.get(indexador)
        if anterior and monotonic() - anterior[0] < 3600:
            return dict(anterior[1])
    try:
        if indexador == 'SOFR':
            url = 'https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json'
            resposta = (session or requests).get(url, timeout=12)
            resposta.raise_for_status()
            linhas = resposta.json()['refRates']
            validas = [(date.fromisoformat(r['effectiveDate']), taxa_valida(r['percentRate']))
                       for r in linhas if r.get('type') == 'SOFR']
            fonte, base = 'Federal Reserve Bank of New York · SOFR overnight', 'ACT/360'
        else:
            url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIES[indexador]}/dados/ultimos/3'
            resposta = (session or requests).get(url, params={'formato': 'json'}, timeout=12)
            resposta.raise_for_status()
            validas = [(datetime.strptime(r['data'], '%d/%m/%Y').date(), taxa_valida(r['valor']))
                       for r in resposta.json()]
            fonte, base = f'Banco Central · SGS {SERIES[indexador]}', '252 dias úteis'
        validas = [(d, v) for d, v in validas if d <= date.today()]
        if not validas:
            raise ValueError()
        data, taxa = max(validas, key=lambda item: item[0])
    except (requests.RequestException, ValueError, TypeError, KeyError, ArithmeticError):
        raise ValueError('Não foi possível consultar a taxa. Tente atualizar ou informe uma taxa manual.') from None
    dado = {'indexador': indexador, 'valor': str(taxa), 'data': data.isoformat(), 'fonte': fonte,
            'url': url, 'base': base, 'consultado_em': datetime.now(timezone.utc).isoformat()}
    dado['id'] = sha256(f'{indexador}:{taxa}:{data}:{url}'.encode()).hexdigest()
    with _lock:
        _cache[indexador] = (monotonic(), dado)
        _referencias[dado['id']] = dict(dado)
    return dict(dado)


def memoria_taxa(indexador, valor, referencia_id=None):
    taxa = taxa_valida(valor)
    with _lock:
        original = dict(_referencias.get(referencia_id) or {})
    if original and original.get('indexador') != indexador:
        raise ValueError('A referência da taxa pertence a outro indexador.')
    return {'indexador': indexador, 'valor': str(taxa),
            'origem': 'API' if original and Decimal(original['valor']) == taxa else 'Informada pelo usuário',
            'referencia_api': original or None, 'hipotese': 'Taxa mantida constante durante a simulação'}
