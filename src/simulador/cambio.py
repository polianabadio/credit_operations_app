"""Câmbio de apresentação/entrada; os cálculos fiscais permanecem em BRL."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from hashlib import sha256
import os
import threading
import time
import requests

MOEDAS = {'BRL': 'Real', 'USD': 'Dólar americano', 'EUR': 'Euro', 'GBP': 'Libra esterlina',
          'JPY': 'Iene', 'CHF': 'Franco suíço', 'CAD': 'Dólar canadense',
          'AUD': 'Dólar australiano', 'CNY': 'Yuan'}
_cache = {}
_lock = threading.RLock()


def decimal_valido(valor):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ValueError('Valor monetário inválido.') from None
    if not numero.is_finite() or numero < 0:
        raise ValueError('Valor monetário inválido.')
    return numero


def cotacao(moeda, session=None):
    if moeda not in MOEDAS:
        raise ValueError('Moeda não disponível.')
    if moeda == 'BRL':
        return {'moeda': 'BRL', 'taxa_brl': '1', 'id': 'BRL', 'fonte': 'Moeda base', 'data': None}
    with _lock:
        anterior = _cache.get(moeda)
        if anterior and time.monotonic() - anterior[0] < 60:
            return dict(anterior[1])
        chave = os.getenv('FXRATESAPI_KEY')
        agora = datetime.now(timezone.utc)
        try:
            params = {'base': 'USD', 'currencies': ','.join(MOEDAS), 'resolution': '1m'}
            if chave:
                params['api_key'] = chave
            resposta = (session or requests).get(
                'https://api.fxratesapi.com/latest', params=params, timeout=12)
            resposta.raise_for_status()
            conteudo = resposta.json()
            momento = datetime.fromtimestamp(int(conteudo['timestamp']), timezone.utc)
            if (conteudo.get('success') is not True or conteudo['base'] != 'USD'
                    or (momento - agora).total_seconds() > 300):
                raise ValueError('Cotação inválida.')
            taxas = conteudo['rates']
            brl = decimal_valido(taxas['BRL'])
            if brl <= 0:
                raise ValueError('Cotação inválida.')
            preparados = {}
            with localcontext() as contexto:
                contexto.prec = 50
                for codigo in MOEDAS:
                    if codigo == 'BRL':
                        continue
                    if codigo not in taxas:
                        continue
                    denominador = decimal_valido(taxas[codigo])
                    if denominador <= 0:
                        raise ValueError('Cotação inválida.')
                    taxa_texto = str(brl / denominador)
                    dado = {'moeda': codigo, 'taxa_brl': taxa_texto, 'data': momento.isoformat(),
                            'consultado_em': agora.isoformat(), 'fonte': 'FXRatesAPI · referência média de mercado',
                            'id': sha256(f'FXRatesAPI:{codigo}:{taxa_texto}:{momento.isoformat()}'.encode()).hexdigest(),
                            'referencia_anterior': (agora - momento).total_seconds() > 86400,
                            'cache_segundos': 60,
                            'memoria_cambio': {'base': 'USD', 'BRL_por_USD': str(brl),
                                              'moeda_por_USD': str(denominador)}}
                    preparados[codigo] = dado
            if moeda not in preparados:
                raise ValueError('Moeda não disponível na resposta.')
        except (requests.RequestException, KeyError, TypeError, ValueError, OverflowError):
            raise ValueError('Cotação indisponível. Tente atualizar novamente; a moeda anterior foi mantida.') from None
        for codigo, dado in preparados.items():
            _cache[codigo] = (time.monotonic(), dado)
            # Conservar snapshots utilizados em operações abertas durante a sessão.
            _snapshots[dado['id']] = dict(dado)
        return dict(preparados[moeda])


_snapshots = {}


def referencia(identificador):
    if identificador in (None, 'BRL'):
        return cotacao('BRL')
    with _lock:
        if identificador not in _snapshots:
            raise ValueError('Atualize a cotação antes de simular nesta moeda.')
        return dict(_snapshots[identificador])


def converter_valores(valores, origem_id, destino_id):
    origem, destino = referencia(origem_id), referencia(destino_id)
    if not isinstance(valores, list) or len(valores) > 1000:
        raise ValueError('Lista de valores inválida.')
    with localcontext() as contexto:
        contexto.prec = 50
        saida = []
        for valor in valores:
            brl = (decimal_valido(valor) * Decimal(origem['taxa_brl'])).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            exibido = (brl / Decimal(destino['taxa_brl'])).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            saida.append({'brl': str(brl), 'valor': str(exibido)})
        return saida


def entrada_em_reais(entrada):
    copia = dict(entrada)
    ref = referencia(copia.pop('cotacao_id', None))
    if ref['moeda'] == 'BRL':
        return copia, ref
    valor = copia.pop('valor_base_brl', None)
    if valor is None:
        valor = converter_valores([copia['valor']], ref['id'], 'BRL')[0]['brl']
    copia['valor'] = str(decimal_valido(valor))
    if 'liberacoes' in copia:
        anos = list(copia['liberacoes'])
        convertidos = converter_valores([copia['liberacoes'][ano] for ano in anos], ref['id'], 'BRL')
        copia['liberacoes'] = {ano: item['brl'] for ano, item in zip(anos, convertidos)}
    return copia, ref
