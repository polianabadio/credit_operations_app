"""Memória auditável de operações e projeção MGA, sem somar snapshots SADIPEM."""
import json
from datetime import datetime, timezone
from decimal import Decimal

from .data_access import obter_rcl_ajustada_endividamento
from .database_models import (
    CoberturaMga,
    LiberacaoCredito,
    OperacaoCredito,
    SincronizacaoSiconfi,
    db,
)
from .fluxo_credito import CreditFlowLimitService
from .mga_parameters import obter_parametro_mga

ENTE = 'Estado de Goiás'
SITUACOES = ('solicitada', 'a_contratar', 'contratada', 'cancelada', 'encerrada')


def ano_valido(valor):
    ano = int(valor)
    if str(ano) != str(valor) or not 2020 <= ano <= 2100:
        raise ValueError('Informe um exercício inteiro entre 2020 e 2100.')
    return ano


def salvar_operacao(entrada):
    identificador = str(entrada.get('identificador') or '').strip()
    fonte = str(entrada.get('fonte') or '').strip()
    situacao = entrada.get('situacao')
    if not identificador or len(identificador) > 150 or not fonte or len(fonte) > 1000 or situacao not in SITUACOES:
        raise ValueError('Identificação, fonte e situação da operação são obrigatórias.')
    inicio, fim = ano_valido(entrada['anoInicio']), ano_valido(entrada['anoFim'])
    if fim < inicio:
        raise ValueError('Ano final anterior ao inicial.')
    total = CreditFlowLimitService._valor(entrada.get('valorTotal'))
    if total is None:
        raise ValueError('Informe o valor total em reais.')
    linhas = entrada.get('liberacoes')
    if not isinstance(linhas, list) or len(linhas) > 500:
        raise ValueError('Informe o cronograma de liberações.')
    valores = {}
    for linha in linhas:
        ano = ano_valido(linha['ano'])
        valor = CreditFlowLimitService._valor(linha.get('valor'))
        if not inicio <= ano <= fim or valor is None:
            raise ValueError('Liberação ausente ou fora do período da operação.')
        valores[ano] = valores.get(ano, Decimal(0)) + valor
    if sum(valores.values(), Decimal(0)) > total:
        raise ValueError('As liberações excedem o valor total da operação.')
    completo = entrada.get('cronogramaCompleto') is True
    if completo and set(valores) != set(range(inicio, fim + 1)):
        raise ValueError('Cronograma completo exige cada exercício, inclusive zeros conhecidos.')
    agora = datetime.now(timezone.utc)
    try:
        operacao = db.session.query(OperacaoCredito).filter_by(identificador=identificador).one_or_none()
        if operacao is None:
            operacao = OperacaoCredito(identificador=identificador)
            db.session.add(operacao)
        operacao.fonte, operacao.situacao = fonte, situacao
        operacao.tipo = 'Operação de crédito'
        operacao.contratada = situacao == 'contratada'
        operacao.valor_total, operacao.ano_inicio, operacao.ano_fim = total, inicio, fim
        operacao.ente, operacao.moeda = ENTE, 'BRL'
        operacao.cronograma_completo, operacao.atualizado_em = completo, agora
        db.session.flush()
        db.session.query(LiberacaoCredito).filter_by(operacao_id=operacao.id).delete()
        for ano, valor in valores.items():
            db.session.add(LiberacaoCredito(operacao_id=operacao.id, ano=ano, valor=valor,
                                           fonte=fonte, atualizado_em=agora))
        # Cadastro alterado requer nova confirmação do inventário completo.
        db.session.query(CoberturaMga).filter_by(ente=ENTE).delete()
        db.session.commit()
        return operacao.id
    except Exception:
        db.session.rollback()
        raise


def confirmar_cobertura(inicio, fim, fonte):
    inicio, fim = ano_valido(inicio), ano_valido(fim)
    fonte = str(fonte or '').strip()
    if fim < inicio or not fonte or len(fonte) > 1000:
        raise ValueError('Informe período e fonte da conferência do inventário.')
    operacoes = db.session.query(OperacaoCredito).filter_by(ente=ENTE).all()
    if any(not op.cronograma_completo for op in operacoes
           if op.situacao not in ('cancelada', 'encerrada') and op.ano_fim >= inicio and op.ano_inicio <= fim):
        raise ValueError('Existem operações relevantes com cronograma incompleto.')
    try:
        cobertura = db.session.get(CoberturaMga, ENTE) or CoberturaMga(ente=ENTE)
        cobertura.ano_inicio, cobertura.ano_fim, cobertura.fonte = inicio, fim, fonte
        cobertura.atualizado_em = datetime.now(timezone.utc)
        db.session.add(cobertura)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def listar_memoria():
    operacoes = db.session.query(OperacaoCredito).filter_by(ente=ENTE).order_by(OperacaoCredito.identificador).all()
    return [{'id': op.id, 'identificador': op.identificador, 'situacao': op.situacao,
             'fonte': op.fonte, 'valorTotal': float(op.valor_total), 'anoInicio': op.ano_inicio,
             'anoFim': op.ano_fim, 'cronogramaCompleto': op.cronograma_completo,
             'atualizadoEm': op.atualizado_em.isoformat(),
             'liberacoes': [{'ano': l.ano, 'valor': float(l.valor)} for l in
                           db.session.query(LiberacaoCredito).filter_by(operacao_id=op.id).order_by(LiberacaoCredito.ano).all()]}
            for op in operacoes]


def obter_projecao(painel, linhas=None, *, cenario_isolado=False, parametro=None, excluir_identificador=None):
    servico = CreditFlowLimitService()
    base = painel.get('rcl') or {}
    ano = painel.get('exercicio') or datetime.now(timezone.utc).year
    inicio = int(ano)
    solicitada = None
    if linhas is not None:
        if not isinstance(linhas, list) or not 1 <= len(linhas) <= 81:
            raise ValueError('Informe o cronograma da operação pleiteada.')
        solicitada = {}
        for linha in linhas:
            exercicio = ano_valido(linha['ano'])
            if exercicio < inicio:
                raise ValueError('Liberação anterior à referência fiscal.')
            valor = servico._valor(linha.get('liberacaoNovaOperacao'))
            anterior = solicitada.get(exercicio, Decimal(0))
            solicitada[exercicio] = None if valor is None or anterior is None else anterior + valor
    operacoes = [] if cenario_isolado else db.session.query(OperacaoCredito).filter_by(ente=ENTE).all()
    operacoes = [op for op in operacoes if op.situacao not in ('cancelada', 'encerrada')
                 and op.ano_fim >= inicio and op.identificador != excluir_identificador]
    liberacoes = db.session.query(LiberacaoCredito).join(OperacaoCredito).filter(
        OperacaoCredito.ente == ENTE, LiberacaoCredito.ano >= inicio).all()
    por_operacao_ano = {(l.operacao_id, l.ano): l for l in liberacoes}
    fim = max([inicio, *(op.ano_fim for op in operacoes), *(solicitada or {})])
    cobertura = db.session.get(CoberturaMga, ENTE)
    contratadas, outras = {}, {}
    contribuicoes = {ano: [] for ano in range(inicio, fim + 1)}
    for ano, contribuicao in contribuicoes.items():
        conhecido = cenario_isolado or (cobertura is not None and cobertura.ano_inicio <= ano <= cobertura.ano_fim)
        somas = {True: Decimal(0), False: Decimal(0)}
        for op in operacoes:
            if not op.ano_inicio <= ano <= op.ano_fim:
                continue
            liberacao = por_operacao_ano.get((op.id, ano))
            if not op.cronograma_completo or liberacao is None:
                conhecido = False
            else:
                somas[op.contratada] += liberacao.valor
                contribuicao.append({'operationId': op.id, 'identificador': op.identificador,
                                          'amount': float(liberacao.valor), 'source': liberacao.fonte,
                                          'updatedAt': liberacao.atualizado_em.isoformat()})
        contratadas[ano] = somas[True] if conhecido else None
        outras[ano] = somas[False] if conhecido else None
    if solicitada is not None:
        # Cronograma da hipótese é um conjunto explícito de liberações; anos sem evento são zero.
        solicitada = {ano: solicitada.get(ano, Decimal(0)) for ano in contribuicoes}
    parametro = parametro or obter_parametro_mga(inicio)
    fator = parametro['multiplier']
    ano_base = int(base.get('exercicio') or inicio)
    periodo = base.get('periodo')
    meses = 12 * (inicio - ano_base) + 12 - 2 * periodo if periodo in range(1, 7) else None
    rcl_base = base.get('valor')
    # Dezembro do próprio exercício já é o fechamento; dezembro anterior implica 12 meses.
    rcl = (servico.projetar_rcl_anual(rcl_base, fator, inicio, periodo, fim)
           if base.get('periodo') in range(1, 7) else None)
    if rcl is not None and ano_base != inicio:
        rcl = {a: v * Decimal(fator) ** (inicio - ano_base) for a, v in rcl.items()}
    resultado = servico.avaliar(inicio, rcl_referencia=base.get('valor'), rcl_projetada=rcl,
                                liberacoes_contratadas=contratadas, liberacoes_nao_contratadas=outras,
                                liberacoes_analisadas=solicitada)
    consultas = db.session.query(SincronizacaoSiconfi).all()
    # Reutiliza o registro da sincronização fiscal; não realiza outra consulta HTTP.
    datas = []
    for consulta in consultas:
        try:
            endpoint, parametros = json.loads(consulta.chave)
        except (ValueError, TypeError):
            continue
        if not isinstance(parametros, dict):
            continue
        if (endpoint == 'rreo' and parametros.get('an_exercicio') == ano_base
                and parametros.get('nr_periodo') == base.get('periodo')
                and parametros.get('no_anexo') == base.get('anexo')):
            datas.append(consulta.consultado_em)
    fontes = {'rclSource': base.get('origem'), 'rclReferencePeriod': base.get('periodo'),
              'rclBaseValue': base.get('valor'), 'rclExercise': ano_base,
              'rclStatement': 'RREO', 'rclAnnex': base.get('anexo'),
              'rclQueriedAt': max(datas).isoformat() if datas else None,
              'projectionFactor': float(Decimal(fator) - 1),
              'projectionMultiplier': float(fator),
              'projectionFactorSource': parametro['source'],
              'projectionFactorEffectiveFrom': parametro['effectiveFrom'],
              'projectionFactorValidated': parametro['validated'],
              'projectionFactorMeaning': parametro['meaning'],
              'proportionalMonths': meses,
              'scheduledOperationsSource': 'Hipótese explícita: somente a nova operação, demais liberações iguais a zero' if cenario_isolado else cobertura.fonte if cobertura else None,
              'scheduledOperationsUpdatedAt': None if cenario_isolado else cobertura.atualizado_em.isoformat() if cobertura else None}
    resultado['sources'] = fontes
    for linha in resultado['rows']:
        linha['sources'] = {**fontes, 'operations': contribuicoes[linha['ano']],
                            'requestedOperationSource': 'Cronograma da simulação' if solicitada is not None else None}
    motivos = []
    if rcl is None:
        motivos.append('RCL fiscal válida não disponível.')
    if any(v is None for v in contratadas.values()):
        motivos.append('Informe as liberações das demais operações para concluir a verificação.')
    if not parametro['validated']:
        motivos.append('Parâmetro de projeção da RCL pendente de validação para esta referência.')
    if solicitada is not None and any(v is None for v in solicitada.values()):
        motivos.append('Há liberações da operação pleiteada sem valor informado.')
    resultado['unavailabilityReasons'] = motivos
    resultado['message'] = ('O montante global das operações de crédito ultrapassa o limite de 16% da RCL em pelo menos um exercício.'
                            if resultado['exceededYears'] else ' '.join(motivos))
    resultado['evaluationScope'] = 'requested_operation_only' if cenario_isolado else 'registered_inventory'
    resultado['numericOutcome'] = resultado['globalStatus']
    resultado['parameterValidated'] = parametro['validated']
    resultado['verificationStatus'] = ('Cenário parcial' if cenario_isolado else
        'Dados incompletos' if motivos else
        'Acima do limite' if resultado['exceededYears'] else 'Dentro do limite')
    resultado['validatedConclusion'] = not cenario_isolado and not motivos
    resultado['otherDisbursementsState'] = ('assumed_zero' if cenario_isolado else
        'missing' if any(v is None for v in contratadas.values()) else 'confirmed')
    resultado['positionOnly'] = linhas is None
    if cenario_isolado:
        resultado['message'] = ('Considera apenas a nova operação; demais liberações não incluídas. '
                                + resultado['message'])
        resultado['globalStatus'] = 'Cenário parcial'
    elif motivos:
        resultado['globalStatus'] = 'Dados incompletos'
    for linha in resultado['rows']:
        linha['verificationStatus'] = ('Dados incompletos' if not linha['dadosCompletos'] or not parametro['validated'] else
            'Acima do limite' if linha['mgaRcl'] > .16 else 'Dentro do limite')
        linha['otherDisbursementsState'] = resultado['otherDisbursementsState']
    return resultado


def avaliar_simulacao_mga(ano, valor_requisitado, entrada=None):
    """Usa os mesmos parâmetros da simulação geral, sem gravar seu cronograma."""
    ano = ano_valido(ano)
    total = CreditFlowLimitService._valor(valor_requisitado)
    if total is None:
        raise ValueError('Informe o Valor requisitado da simulação.')
    entrada = entrada or {'scope': 'operation_only', 'mode': 'single_year'}
    if entrada.get('scope') not in ('operation_only', 'inventory'):
        raise ValueError('Base da simulação MGA inválida.')
    inicio = ano_valido(entrada.get('releaseStart', ano))
    fim = ano_valido(entrada.get('releaseEnd', inicio))
    if inicio < ano or fim < inicio:
        raise ValueError('Período de liberação inválido.')
    if total != total.quantize(Decimal('.01')):
        raise ValueError('Valor requisitado: informe no máximo duas casas decimais.')
    if entrada.get('mode') == 'single_year':
        fim = inicio
        linhas = [{'ano': inicio, 'liberacaoNovaOperacao': total}]
    elif entrada.get('mode') == 'annual_schedule':
        linhas = entrada.get('rows')
        if not isinstance(linhas, list) or not linhas:
            raise ValueError('Informe o cronograma anual do contrato.')
        valores = [CreditFlowLimitService._valor(l.get('liberacaoNovaOperacao')) for l in linhas]
        if any(v is None for v in valores):
            raise ValueError('Preencha todas as liberações anuais do contrato, inclusive zeros conhecidos.')
        if any(v != v.quantize(Decimal('.01')) for v in valores):
            raise ValueError('Liberações: informe no máximo duas casas decimais.')
        if sum(valores, Decimal(0)) != total:
            raise ValueError('A soma das liberações do contrato deve ser igual ao Valor requisitado.')
        anos = [ano_valido(l['ano']) for l in linhas]
        if len(anos) != len(set(anos)):
            raise ValueError('Informe somente uma liberação consolidada por exercício.')
        if 'releaseEnd' in entrada and set(anos) != set(range(inicio, fim + 1)):
            raise ValueError('Preencha cada ano do período de liberação, inclusive zeros conhecidos.')
        inicio, fim = min(anos), max(anos)
    else:
        raise ValueError('Modo do cronograma MGA inválido.')
    referencia = obter_rcl_ajustada_endividamento(ano)
    exercicio_referencia = ano
    if referencia is None:
        referencia = obter_rcl_ajustada_endividamento(ano - 1)
        exercicio_referencia = ano - 1
        if referencia and referencia['periodo'] != 6:
            referencia = None
    painel = {'exercicio': ano, 'rcl': None if referencia is None else {
        'valor': float(referencia['valor']), 'periodo': referencia['periodo'],
        'exercicio': referencia.get('exercicio', exercicio_referencia),
        'anexo': referencia['anexo'], 'origem': referencia['origem']}}
    parametro = obter_parametro_mga(ano, entrada.get('projectionParameter'))
    resultado = obter_projecao(painel, linhas, cenario_isolado=entrada['scope'] == 'operation_only',
        parametro=parametro, excluir_identificador=entrada.get('operationIdentifier'))
    resultado['releaseStart'], resultado['releaseEnd'] = inicio, fim
    resultado['scheduleMode'] = entrada['mode']
    resultado['excludedOperationIdentifier'] = entrada.get('operationIdentifier')
    resultado['requestedTotal'] = float(total)
    capacidades = []
    for linha in resultado['rows']:
        restante = (linha['tetoAnual'] - linha['scheduledDisbursements']
                    if resultado['validatedConclusion'] and linha['tetoAnual'] is not None
                    and linha['scheduledDisbursements'] is not None else None)
        linha['availableForRequestedOperation'] = restante
        if total > 0 and linha['requestedOperation']:
            capacidades.append((linha['ano'], max(Decimal(0), Decimal(str(restante))) * total /
                Decimal(str(linha['requestedOperation']))) if restante is not None else None)
    if entrada['mode'] == 'single_year':
        capacidades = [(inicio, Decimal(str(next(l['availableForRequestedOperation'] for l in resultado['rows']
                        if l['ano'] == inicio))))] if resultado['validatedConclusion'] else []
    restricao = min(capacidades, key=lambda item: item[1]) if capacidades and None not in capacidades else None
    resultado['maxRequestedAmountForSchedule'] = (float(max(Decimal(0), restricao[1]).quantize(
        Decimal('.01'), rounding='ROUND_DOWN')) if restricao and total > 0 else None)
    resultado['capacityRestrictingYear'] = restricao[0] if restricao and total > 0 else None
    if resultado['validatedConclusion'] and any(l['scheduledDisbursements'] > l['tetoAnual'] for l in resultado['rows']):
        resultado['maxRequestedAmountForSchedule'] = 0 if total > 0 else None
    return resultado
