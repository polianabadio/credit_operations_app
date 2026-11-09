"""Fluxo semestral no formato da planilha de referência."""
from decimal import Decimal, ROUND_HALF_UP, localcontext

from .fluxo_tlp import data_iso, deslocar_mes, inteiro
from .indexadores import taxa_valida
from .servico_divida import decimal_nao_negativo, valor_monetario


def _centavos(valor):
    return valor.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def _texto(valores):
    return {chave: str(valor) for chave, valor in valores.items()}


def calcular_fluxo_semestral(entrada):
    indice = entrada.get('referencia_juros_cambial') if entrada['indexador'] == 'CAMBIAL' else entrada['indexador']
    if indice != 'SOFR':
        raise ValueError('O modelo da planilha semestral usa SOFR.')
    if any(decimal_nao_negativo(v, 'Outros encargos') for v in (entrada.get('encargos_anuais') or {}).values()):
        raise ValueError('A planilha semestral usa somente juros e comissão sobre o saldo a liberar.')
    inicio = data_iso(entrada['data_liberacao'])
    prazo = inteiro(entrada['prazo_meses'], 'Prazo total', 6, 600)
    carencia = inteiro(entrada['carencia_meses'], 'Carência', 0, prazo - 6)
    if prazo % 6 or carencia % 6:
        raise ValueError('Na planilha semestral, a carência e o prazo total são múltiplos de seis meses.')
    fim = deslocar_mes(inicio, prazo)
    if (inicio.year, fim.year) != (int(entrada['ano']), int(entrada['fim'])):
        raise ValueError('Confira o ano de referência e o ano do último vencimento.')

    moeda = entrada.get('moeda_contrato') or 'BRL'
    if entrada.get('moeda_entrada', moeda) != moeda:
        raise ValueError(f'Selecione {moeda} no campo Moeda para reproduzir os centavos da planilha.')
    taxa_cambio = decimal_nao_negativo(entrada.get('cotacao_contrato', '1') if moeda != 'BRL' else '1', 'Cotação')
    if not taxa_cambio:
        raise ValueError('Informe uma cotação positiva.')
    principal = valor_monetario(entrada.get('principal_semestral_original', entrada['valor']), 'Principal')
    principal_brl = valor_monetario(entrada['valor'], 'Principal em reais')
    informadas = entrada.get('liberacoes_semestrais')
    if not isinstance(informadas, dict) or len(informadas) > 100:
        raise ValueError('Informe as liberações do cronograma semestral.')
    liberacoes = {data_iso(d): valor_monetario(v, 'Liberação semestral') for d, v in informadas.items()}
    datas = [deslocar_mes(inicio, mes) for mes in range(0, prazo + 1, 6)]
    primeira_amortizacao = max(carencia // 6, 1)
    datas_liberacao = set(datas[:primeira_amortizacao])
    if (not principal or not principal_brl or not liberacoes.get(inicio)
            or len(liberacoes) != len(informadas) or not liberacoes.keys() <= datas_liberacao
            or sum(liberacoes.values()) != principal):
        raise ValueError('Informe liberações em centavos, desde a primeira data e dentro da carência, cuja soma seja igual ao empréstimo.')

    total_taxa = sum(taxa_valida(entrada.get(chave, '0')) for chave in ('taxa_indexador', 'prefixada', 'spread', 'spread_capital'))
    taxa_comissao = taxa_valida(entrada.get('comissao_credito', '0'))
    restantes = len(datas) - primeira_amortizacao
    saldo = recebido = amortizado = Decimal(0)
    linhas, semestres = [], []
    chaves = ('juros', 'amortizacao', 'juros_financeiros', 'comissao_credito', 'outros_encargos', 'liberacao', 'total')
    fiscais = {a: dict.fromkeys(chaves, Decimal(0)) for a in range(inicio.year, fim.year + 1)}
    resumo = {}

    def reais_acumulados(valor):
        return principal_brl if valor == principal else _centavos(valor * taxa_cambio)

    with localcontext() as contexto:
        contexto.prec = 50
        for periodo, (abertura, vencimento) in enumerate(zip(datas, datas[1:]), 1):
            dias = (vencimento - abertura).days
            liberacao = liberacoes.get(abertura, Decimal(0))
            liberacao_brl = reais_acumulados(recebido + liberacao) - reais_acumulados(recebido)
            recebido += liberacao
            juros = _centavos((saldo + liberacao) * total_taxa / 100 * dias / 365)
            comissao = _centavos((principal - recebido) * taxa_comissao / 200)
            amortizacao = _centavos(saldo / restantes) if periodo >= primeira_amortizacao else Decimal(0)
            amortizacao_brl = reais_acumulados(amortizado + amortizacao) - reais_acumulados(amortizado)
            amortizado += amortizacao
            valores = dict(liberacao=liberacao, amortizacao=amortizacao, juros_financeiros=juros,
                           comissao_credito=comissao, juros=juros + comissao, total=juros + comissao + amortizacao)
            anual = resumo.setdefault(abertura.year, dict.fromkeys(valores, Decimal(0)))
            for chave, valor in valores.items():
                anual[chave] += valor
            saldo_final = saldo + liberacao - amortizacao
            semestres.append(dict(inicio=abertura.isoformat(), fim=vencimento.isoformat(), dias=dias,
                                  **_texto(dict(saldo_inicial=saldo, saldo_final=saldo_final, **valores))))

            juros_brl, comissao_brl = (_centavos(v * taxa_cambio) for v in (juros, comissao))
            pagamentos = dict(amortizacao=amortizacao_brl, juros_financeiros=juros_brl, comissao_credito=comissao_brl,
                              juros=juros_brl + comissao_brl, total=juros_brl + comissao_brl + amortizacao_brl)
            fiscais[abertura.year]['liberacao'] += liberacao_brl
            for chave, valor in pagamentos.items():
                fiscais[vencimento.year][chave] += valor
            linhas.append(dict(inicio=abertura.isoformat(), fim=vencimento.isoformat(), dias_corridos=dias,
                               **_texto(dict(liberacao=liberacao_brl, saldo_inicial=_centavos(saldo * taxa_cambio),
                                             saldo_final=_centavos(saldo_final * taxa_cambio), outros_encargos=0,
                                             pagamento_total=pagamentos['total'], **pagamentos))))
            saldo = saldo_final
            if periodo >= primeira_amortizacao:
                restantes -= 1

    if saldo or amortizado != principal:
        raise ValueError('O fluxo semestral não encerrou o principal.')
    totais_brl = {chave: sum(l[chave] for l in fiscais.values()) for chave in chaves}
    totais = {chave: sum(l[chave] for l in resumo.values()) for chave in next(iter(resumo.values()))}
    return dict(modo='contratual', modelo_semestral=True, indexador=entrada['indexador'], referencia_juros=indice,
                metodo_sofr='simples', estimado=True, data_final=fim.isoformat(), saldo_final='0.00',
                quantidade_pagamentos_juros=len(semestres), quantidade_amortizacoes=len(datas) - primeira_amortizacao,
                prazos=dict(carencia_meses=carencia, amortizacao_meses=prazo - carencia, prazo_total_meses=prazo),
                juros_total=str(totais_brl['juros']), amortizacao_total=str(totais_brl['amortizacao']),
                pagamento_total=str(totais_brl['total']), juros_financeiros_total=str(totais_brl['juros_financeiros']),
                comissao_credito_total=str(totais_brl['comissao_credito']), outros_encargos_total='0.00',
                premissas=dict(base_juros='365', taxa_total=str(total_taxa), comissao_credito=str(taxa_comissao)),
                convencao='Taxa total simples em dias corridos/365. Comissão semestral sobre o saldo após a liberação.',
                calendario='Liberações na abertura de cada semestre e pagamentos no vencimento.',
                anuais=[dict(ano=a, **_texto(v)) for a, v in fiscais.items()], linhas=linhas,
                planilha=dict(moeda=moeda, semestres=semestres, anuais=[dict(ano=a, **_texto(v)) for a, v in resumo.items()],
                              totais=_texto(totais)))
