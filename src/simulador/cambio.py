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
    if isinstance(identificador,str) and identificador.startswith('manual:'):
        partes=identificador.split(':')
        if len(partes)!=3: raise ValueError('Referência manual inválida.')
        return registrar_cotacao_contratual(partes[1],partes[2])
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


def converter_entradas(valores, origem_id, destino_id, conciliar_liberacoes=False):
    origem,destino=referencia(origem_id),referencia(destino_id)
    if not isinstance(valores,list) or len(valores)>1000: raise ValueError('Lista de entradas inválida.')
    with localcontext() as contexto:
        contexto.prec=50
        taxa_origem,taxa_destino=Decimal(origem['taxa_brl']),Decimal(destino['taxa_brl'])
        bases=[]
        for v in valores:
            preservada=_base_preservada(v,'base_brl',v['valor'],taxa_origem)
            bases.append(Decimal(preservada) if preservada is not None else (decimal_valido(v['valor'])*taxa_origem).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
        principal=next((i for i,v in enumerate(valores) if v.get('tipo')=='principal'),None)
        liberacoes=[i for i,v in enumerate(valores) if v.get('tipo')=='liberacao']
        ajuste=Decimal(0)
        if conciliar_liberacoes and principal is not None and liberacoes:
            soma_original=sum(decimal_valido(valores[i]['valor']) for i in liberacoes)
            soma_brl=sum(bases[i] for i in liberacoes)
            if soma_original==decimal_valido(valores[principal]['valor']) or soma_brl==bases[principal]:
                ajuste=bases[principal]-soma_brl
                restante=ajuste
                positivos=[i for i in liberacoes if bases[i]>0]
                if restante>0 and positivos:
                    bases[positivos[-1]]+=restante;restante=Decimal(0)
                for i in reversed(positivos):
                    if restante>=0:break
                    parcela=min(bases[i],-restante);bases[i]-=parcela;restante+=parcela
                if restante:raise ValueError('Não foi possível conciliar os centavos do cronograma convertido.')
        return {'valores':[dict(brl=str(v),valor=str((v/taxa_destino).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))) for v in bases],
                'ajuste_liberacoes_brl':str(ajuste)}


def _converter_cronograma_anual(original, copia, taxa):
    if original.get('modo_calculo') != 'anual_informado':
        return
    from .cronograma_anual import ler_cronograma
    registros = ler_cronograma(original)
    with localcontext() as contexto:
        contexto.prec = 50
        linhas = [{'ano': ano, **{chave: str((valor * taxa).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
                    for chave, valor in valores.items()}} for ano, valores in sorted(registros.items())]
        ajustes = {}
        # Resíduos da conversão em centavos são explicitados e conciliados na última linha positiva.
        for chave in ('liberacao', 'amortizacao'):
            diferenca = Decimal(copia['valor']) - sum(Decimal(l[chave]) for l in linhas)
            ultima = next(l for l in reversed(linhas) if registros[l['ano']][chave] > 0)
            ultima[chave] = str(Decimal(ultima[chave]) + diferenca)
            ajustes[chave] = str(diferenca)
        copia['cronograma_anual'] = linhas
        copia['memoria_cronograma'] = {'moeda_original': original.get('moeda_contrato'),
            'linhas_originais': original['cronograma_anual'], 'ajustes_conversao_brl': ajustes}


def _converter_custos_contratuais(original, copia, taxa):
    if original.get('modelo_fluxo') != 'contratual': return
    with localcontext() as contexto:
        contexto.prec = 50
        copia['encargos_anuais'] = {a:str((decimal_valido(v)*taxa).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) for a,v in (original.get('encargos_anuais') or {}).items()}
        for a,v in (original.get('encargos_base_brl') or {}).items():
            chave=a if a in copia['encargos_anuais'] else str(a)
            if chave in copia['encargos_anuais']:
                copia['encargos_anuais'][chave]=_base_preservada({'base':v},'base',original['encargos_anuais'][chave],taxa)

        if original.get('tipo_liberacao') == 'cronograma':
            originais=original.get('liberacoes') or {}
            for a,v in (original.get('liberacoes_base_brl') or {}).items():
                chave=a if a in copia['liberacoes'] else str(a)
                if chave in copia['liberacoes']:
                    copia['liberacoes'][chave]=_base_preservada({'base':v},'base',originais[chave],taxa)
            soma_original=sum(decimal_valido(v) for v in originais.values())
            soma_brl=sum(Decimal(v) for v in copia['liberacoes'].values())
            if soma_original!=decimal_valido(original['valor']) and soma_brl!=Decimal(copia['valor']):
                raise ValueError('A soma das liberações deve corresponder ao valor da operação na moeda de entrada.')
            ultima=next((a for a in reversed(sorted(originais,key=int)) if decimal_valido(originais[a])>0),None)
            if ultima is not None:
                diferenca=Decimal(copia['valor'])-sum(Decimal(v) for v in copia['liberacoes'].values())
                copia['liberacoes'][ultima]=str(Decimal(copia['liberacoes'][ultima])+diferenca)
                copia['ajuste_conversao_liberacoes_brl']=str(diferenca)
        copia['cronograma_original_moeda']=dict(liberacoes=original.get('liberacoes'),encargos_anuais=original.get('encargos_anuais'))


def registrar_cotacao_contratual(moeda, taxa):
    if moeda not in MOEDAS or moeda=='BRL': raise ValueError('Escolha uma moeda estrangeira válida.')
    taxa=decimal_valido(taxa)
    if taxa<=0: raise ValueError('Informe uma cotação contratual positiva.')
    dado=dict(moeda=moeda,taxa_brl=str(taxa),id=f'manual:{moeda}:{taxa}',fonte='Cotação contratual informada pelo usuário',data=None,constante=True)
    with _lock: _snapshots[dado['id']]=dict(dado)
    return dado


def _base_preservada(original, chave, valor, taxa):
    base=original.get(chave)
    if base is None: return None
    with localcontext() as contexto:
        contexto.prec=50
        base=decimal_valido(base)
        if (base/taxa).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=decimal_valido(valor):
            raise ValueError('A unidade de preenchimento mudou. Revise o valor informado.')
        return str(base)


def entrada_em_reais(entrada):
    copia = dict(entrada)
    if copia.get('tipo_liberacao') == 'semestral':
        moeda_nativa = copia.get('moeda_contrato') if copia.get('indexador') == 'CAMBIAL' else 'BRL'
        if copia.get('moeda_entrada', moeda_nativa) != moeda_nativa:
            raise ValueError(f'Selecione {moeda_nativa} no campo Moeda para reproduzir os centavos da planilha.')
        copia['principal_semestral_original'] = copia['valor']
    if copia.get('indexador') == 'CAMBIAL':
        moeda = copia.get('moeda_contrato')
        if moeda not in MOEDAS or moeda == 'BRL':
            raise ValueError('Escolha a moeda estrangeira do contrato.')
        taxa = decimal_valido(copia.get('cotacao_contrato'))
        if taxa <= 0:
            raise ValueError('Informe uma cotação contratual positiva em reais por unidade da moeda.')
        moeda_entrada=copia.get('moeda_entrada',moeda)
        if moeda_entrada==moeda: taxa_entrada=taxa
        elif moeda_entrada=='BRL': taxa_entrada=Decimal(1)
        else:
            ref_entrada=referencia(copia.get('cotacao_id'))
            if ref_entrada['moeda']!=moeda_entrada: raise ValueError('Atualize a moeda de preenchimento.')
            taxa_entrada=Decimal(ref_entrada['taxa_brl'])
        valor_digitado=decimal_valido(copia['valor'])
        with localcontext() as contexto:
            contexto.prec = 50
            base=_base_preservada(entrada,'valor_base_brl',valor_digitado,taxa_entrada) if 'moeda_entrada' in entrada else None
            copia['valor'] = base if base is not None else str((valor_digitado * taxa_entrada).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
            valor_original=valor_digitado if moeda_entrada==moeda else (Decimal(copia['valor'])/taxa).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            if 'liberacoes' in copia:
                copia['liberacoes'] = {ano: str((decimal_valido(v) * taxa_entrada).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) for ano,v in copia['liberacoes'].items()}
        copia.pop('valor_base_brl', None); copia.pop('cotacao_id', None)
        ref = {**registrar_cotacao_contratual(moeda,taxa), 'valor_original': str(valor_original),
               'valor_brl': copia['valor'], 'moeda_entrada':moeda_entrada,'valor_digitado':str(valor_digitado),
               'taxa_brl_preenchimento':str(taxa_entrada),
               'referencia_preenchimento': (dict(moeda=moeda,taxa_brl=str(taxa),fonte='Cotação contratual informada pelo usuário') if moeda_entrada==moeda else cotacao('BRL') if moeda_entrada=='BRL' else ref_entrada)}
        _converter_cronograma_anual(entrada, copia, taxa_entrada)
        _converter_custos_contratuais(entrada,copia,taxa_entrada)
        return copia, ref
    ref = referencia(copia.pop('cotacao_id', None))
    if copia.get('moeda_entrada') and copia['moeda_entrada']!=ref['moeda']:
        raise ValueError('Atualize a moeda de preenchimento antes de calcular.')
    if ref['moeda'] == 'BRL':
        _converter_cronograma_anual(entrada, copia, Decimal(1))
        _converter_custos_contratuais(entrada,copia,Decimal(1))
        return copia, ref
    valor = copia.pop('valor_base_brl', None)
    if valor is not None and copia.get('moeda_entrada'):
        valor=_base_preservada(entrada,'valor_base_brl',copia['valor'],Decimal(ref['taxa_brl']))
    if valor is None:
        valor = converter_valores([copia['valor']], ref['id'], 'BRL')[0]['brl']
    copia['valor'] = str(decimal_valido(valor))
    if 'liberacoes' in copia:
        anos = list(copia['liberacoes'])
        convertidos = converter_valores([copia['liberacoes'][ano] for ano in anos], ref['id'], 'BRL')
        copia['liberacoes'] = {ano: item['brl'] for ano, item in zip(anos, convertidos)}
    _converter_cronograma_anual(entrada, copia, Decimal(ref['taxa_brl']))
    _converter_custos_contratuais(entrada,copia,Decimal(ref['taxa_brl']))
    return copia, ref
