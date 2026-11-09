"""Cenário de desembolsos em etapas, amortização constante e juros periódicos.

Premissas explícitas de simulação, sem reconstrução de cláusulas de um contrato.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
from .fluxo_tlp import data_iso, deslocar_mes, inteiro
from .calendario_fcl import FERIADOS_FCL
from .servico_divida import decimal_nao_negativo
from .indexadores import taxa_valida

CENTAVO = Decimal('.01')


def cronograma_datas(entrada):
    if entrada.get('calendario_pagamentos') == 'fixo':
        from .calendario_contratual import calendario_fixo
        c = calendario_fixo(entrada)
        return c['inicio'], c['fim'], c['amortizacoes'], c['juros']
    inicio = data_iso(entrada['data_liberacao'])
    prazo = inteiro(entrada['prazo_meses'], 'Prazo total', 1, 600)
    carencia = inteiro(entrada['carencia_meses'], 'Carência', 0, prazo - 1)
    pa = inteiro(entrada.get('periodicidade_amortizacao', 6), 'Periodicidade da amortização', 1, 12)
    pj = inteiro(entrada.get('periodicidade_juros', 6), 'Periodicidade dos juros', 1, 12)
    if pa not in (1, 3, 6, 12) or pj not in (1, 3, 6, 12):
        raise ValueError('Escolha periodicidade mensal, trimestral, semestral ou anual.')
    offsets = list(range(carencia or pa, prazo + 1, pa))
    if not offsets or offsets[-1] != prazo: offsets.append(prazo)
    amortizacoes = {deslocar_mes(inicio, m) for m in offsets}
    juros = {deslocar_mes(inicio, m) for m in range(pj, prazo + 1, pj)}
    fim = deslocar_mes(inicio, prazo)
    juros.add(fim)
    return inicio, fim, amortizacoes, juros


def calcular_fluxo_contratual(entrada):
    inicio, fim, datas_amortizacao, datas_juros = cronograma_datas(entrada)
    calendario = None
    if entrada.get('calendario_pagamentos') == 'fixo':
        from .calendario_contratual import calendario_fixo
        calendario = calendario_fixo(entrada)
    elif entrada.get('calendario_pagamentos') not in (None, 'aniversario'):
        raise ValueError('Calendário de pagamentos inválido.')
    primeira_liberacao = calendario['primeira_liberacao'] if calendario else inicio
    inicio_comissao = calendario['inicio_comissao'] if calendario else inicio
    principal = decimal_nao_negativo(entrada['valor'], 'Valor da operação')
    if principal <= 0 or principal != principal.quantize(CENTAVO):
        raise ValueError('Informe um principal positivo em centavos.')
    if inicio.year != int(entrada['ano']): raise ValueError('O início deve pertencer ao exercício escolhido.')
    if fim.year != int(entrada['fim']):
        raise ValueError(f'O prazo informado termina em {fim.strftime("%d/%m/%Y")}. Ajuste o ano final para {fim.year}.')
    mes = inteiro(entrada.get('mes_liberacoes', 7), 'Mês das liberações anuais', 1, 12)
    liberacoes = {}
    if entrada.get('tipo_liberacao') == 'unica':
        liberacoes[primeira_liberacao] = principal
    elif entrada.get('tipo_liberacao') == 'cronograma':
        mapa = entrada.get('liberacoes') or {}
        if {int(a) for a in mapa} != set(range(inicio.year, fim.year + 1)):
            raise ValueError('Informe as liberações de todos os anos, inclusive zeros.')
        if len(mapa) != fim.year - inicio.year + 1: raise ValueError('Ano de liberação duplicado.')
        for a, valor in mapa.items():
            valor = decimal_nao_negativo(valor, 'Liberação anual')
            if valor != valor.quantize(CENTAVO): raise ValueError('Informe liberações em centavos.')
            if not valor: continue
            d = primeira_liberacao if int(a) == primeira_liberacao.year else date(int(a), mes, 15)
            if not inicio <= d <= fim: raise ValueError('Há liberação fora do prazo da operação.')
            if d < primeira_liberacao: raise ValueError('Há liberação anterior à primeira liberação informada.')
            if calendario and d > calendario['limite_desembolso']:
                raise ValueError('Há liberação após o prazo para desembolsos contado da vigência.')
            liberacoes[d] = valor
        if sum(liberacoes.values()) != principal: raise ValueError('A soma das liberações deve corresponder ao principal.')
    else: raise ValueError('Escolha liberação única ou em vários anos.')
    if calendario and max(liberacoes) > calendario['limite_desembolso']:
        raise ValueError('Há liberação após o prazo para desembolsos contado da vigência.')
    indice = entrada.get('referencia_juros_cambial', 'FIXA') if entrada.get('indexador') == 'CAMBIAL' else entrada.get('indexador')
    if indice not in ('FIXA', 'CDI', 'SELIC', 'SOFR'):
        raise ValueError('O cenário por etapas atende taxa fixa, CDI, Selic e SOFR. IPCA/TLP conservam o modelo FCL de liberação única.')
    taxa = taxa_valida(entrada.get('taxa_indexador', '0')) if indice in ('CDI','SELIC','SOFR') else Decimal(0)
    fixa, captacao, capital, comissao = (taxa_valida(entrada.get(k, '0')) for k in ('prefixada','spread','spread_capital','comissao_credito'))
    base = str(entrada.get('base_juros', '360' if indice == 'SOFR' else '252'))
    metodo_sofr = entrada.get('metodo_sofr', 'composta_projetada' if calendario and indice == 'SOFR' else 'simples')
    if metodo_sofr not in ('simples','composta_projetada'):
        raise ValueError('Método SOFR inválido.')
    if indice == 'SOFR' and metodo_sofr == 'composta_projetada' and base != '360':
        raise ValueError('A projeção do Índice SOFR composto usa dias corridos e base 360.')
    if base not in ('360','365','252'): raise ValueError('Base de juros inválida.')
    if base == '252' and (inicio.year < 2009 or fim.year > 2060):
        raise ValueError('A base de 252 dias usa o calendário FCL disponível de 2009 a 2060.')
    custos = {}
    for a, v in (entrada.get('encargos_anuais') or {}).items():
        ano = int(a); valor = decimal_nao_negativo(v, 'Outros encargos anuais')
        if not inicio.year <= ano <= fim.year: raise ValueError('Encargo fora do horizonte.')
        if valor != valor.quantize(CENTAVO): raise ValueError('Informe encargos em centavos.')
        d = min(date(ano,12,31), fim)
        if d < inicio and valor: raise ValueError('Encargo anterior ao início.')
        custos[d] = valor
    eventos = sorted({inicio,fim,*datas_amortizacao,*datas_juros,*liberacoes,*custos,
                      *([inicio_comissao] if inicio <= inicio_comissao <= fim else [])})
    linhas, anuais = [], {a:dict(juros=Decimal(0),amortizacao=Decimal(0),juros_financeiros=Decimal(0),comissao_credito=Decimal(0),outros_encargos=Decimal(0),liberacao=Decimal(0)) for a in range(inicio.year,fim.year+1)}
    saldo = recebido = amortizado = juros_acumulados = comissao_acumulada = Decimal(0)
    juros_sofr = juros_adicionais = Decimal(0)
    restantes = len(datas_amortizacao)
    anterior = inicio
    with localcontext() as contexto:
        contexto.prec = 50
        efetiva = (1+taxa/100)*(1+fixa/100)*(1+captacao/100)*(1+capital/100)
        nominal = taxa+fixa+captacao+capital
        if indice != 'SOFR':
            descricao_juros = 'Taxas efetivas compostas. '
        elif metodo_sofr == 'composta_projetada':
            descricao_juros = 'SOFR composta diariamente em projeção constante; spreads simples separados. '
        else:
            taxa_formatada = format(nominal.normalize(), 'f').replace('.', ',')
            descricao_juros = f'Juros simples sobre a taxa total de {taxa_formatada}% a.a. (SOFR + taxa fixa adicional + spreads), base {base}. '
        for d in eventos:
            dias = (d-anterior).days
            if base == '252':
                dias_base = sum(1 for i in range(1,dias+1) if (anterior+timedelta(days=i)).weekday()<5 and (anterior+timedelta(days=i)).isoformat() not in FERIADOS_FCL)
            else: dias_base = dias
            saldo_inicial = saldo
            fator_sofr = (1 + taxa/100/360)**dias if indice == 'SOFR' and metodo_sofr == 'composta_projetada' else None
            if fator_sofr is not None:
                # Índice sintético projetado: overnight constante e composição diária.
                # Spreads são acréscimos simples, não entram no índice SOFR.
                juros_sofr += (saldo+juros_sofr)*(fator_sofr-1)
                juros_adicionais += saldo*(fixa+captacao+capital)/100*Decimal(dias)/360
                juros_acumulados = juros_sofr+juros_adicionais
            elif indice == 'SOFR': juros_acumulados += saldo*nominal/100*Decimal(dias_base)/Decimal(base)
            else: juros_acumulados += (saldo+juros_acumulados)*(efetiva**(Decimal(dias_base)/Decimal(base))-1)
            dias_comissao = max(0,(d-max(anterior,inicio_comissao)).days)
            comissao_acumulada += (principal-recebido)*comissao/100*Decimal(dias_comissao)/360
            liberacao = liberacoes.get(d,Decimal(0)); recebido += liberacao; saldo += liberacao
            amortizacao = Decimal(0)
            if d in datas_amortizacao:
                amortizacao = min(saldo, ((principal-amortizado)/restantes).quantize(CENTAVO,rounding=ROUND_HALF_UP))
                if restantes == 1: amortizacao=saldo
                saldo-=amortizacao;amortizado+=amortizacao;restantes-=1
            j = c = Decimal(0)
            if d in datas_juros:
                j=juros_acumulados.quantize(CENTAVO,rounding=ROUND_HALF_UP);juros_acumulados=Decimal(0)
                juros_sofr=juros_adicionais=Decimal(0)
                c=comissao_acumulada.quantize(CENTAVO,rounding=ROUND_HALF_UP);comissao_acumulada=Decimal(0)
            outros=custos.get(d,Decimal(0)); encargos=j+c+outros
            anual=anuais[d.year]
            for chave,v in [('juros',encargos),('amortizacao',amortizacao),('juros_financeiros',j),('comissao_credito',c),('outros_encargos',outros),('liberacao',liberacao)]: anual[chave]+=v
            linhas.append(dict(inicio=anterior.isoformat(),fim=d.isoformat(),saldo_inicial=str(saldo_inicial),liberacao=str(liberacao),saldo_final=str(saldo),juros=str(encargos),juros_financeiros=str(j),comissao_credito=str(c),outros_encargos=str(outros),amortizacao=str(amortizacao),pagamento_total=str(encargos+amortizacao),dias_corridos=dias,dias_base=dias_base,dias_comissao=dias_comissao,fator_sofr_projetado=str(fator_sofr) if fator_sofr is not None else None))
            anterior=d
        juros_total=sum(v['juros'] for v in anuais.values());amortizacao_total=sum(v['amortizacao'] for v in anuais.values())
        if saldo or recebido != principal or amortizacao_total != principal: raise ValueError('O fluxo não encerrou integralmente o principal.')
        return dict(modo='contratual',linhas=linhas,anuais=[dict(ano=a,**{k:str(v) for k,v in vs.items()},total=str(vs['juros']+vs['amortizacao'])) for a,vs in anuais.items()],
            juros_total=str(juros_total),amortizacao_total=str(amortizacao_total),pagamento_total=str(juros_total+amortizacao_total),saldo_final=str(saldo),data_final=fim.isoformat(),
            juros_financeiros_total=str(sum(v['juros_financeiros'] for v in anuais.values())),comissao_credito_total=str(sum(v['comissao_credito'] for v in anuais.values())),outros_encargos_total=str(sum(v['outros_encargos'] for v in anuais.values())),
            quantidade_amortizacoes=len(datas_amortizacao),quantidade_pagamentos_juros=len(datas_juros),indexador=entrada.get('indexador'),referencia_juros=indice,estimado=True,
            prazos=dict(carencia_meses=int(entrada['carencia_meses']),amortizacao_meses=int(entrada['prazo_meses'])-int(entrada['carencia_meses']),prazo_total_meses=int(entrada['prazo_meses'])),
            premissas=dict(base_juros=base,periodicidade_amortizacao=entrada.get('periodicidade_amortizacao',6),periodicidade_juros=entrada.get('periodicidade_juros',6),mes_liberacoes=mes,comissao_credito=str(comissao),spread_capital=str(capital),spread_captacao=str(captacao),taxa_fixa=str(fixa),taxa_indexador=str(taxa)),
            metodo_sofr=metodo_sofr if indice=='SOFR' else None,
            datas_contratuais={k:v.isoformat() for k,v in calendario.items() if hasattr(v,'isoformat')} if calendario else None,
            memoria_exata=dict(entrada=entrada,liberacoes=[dict(data=d.isoformat(),valor=str(v)) for d,v in sorted(liberacoes.items())],
                               metodo_sofr=metodo_sofr,origem_sofr='Projeção sintética com a taxa overnight escolhida constante; não é série histórica nem curva futura publicada.' if metodo_sofr=='composta_projetada' else 'Taxa constante simples'),
            convencao=('Calendário contratual: prazo final contado da assinatura, carência contada da vigência; primeira e última amortizações ajustadas para vencimento de juros anterior quando necessário. Comissão a partir da assinatura mais os dias informados. ' if calendario else 'Calendário de aniversários da primeira liberação. ')+descricao_juros+ 'Parcela limitada ao saldo disponível, com redistribuição do principal nas restantes. Comissão sobre saldo não desembolsado, ACT/360. Outros encargos no fim de cada ano ou na data final.',
            calendario='Datas de aniversário sem ajuste bancário. Base 252 usa dias úteis do calendário FCL; bases 360/365 usam dias corridos.')
