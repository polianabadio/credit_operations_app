"""Saldo segundo um PVL público, separado da margem de inventário confirmado."""
from datetime import datetime, timezone
from .mensagens import mensagem_erro
from .logger import log
from decimal import Decimal, localcontext

from .fluxo_credito import CreditFlowLimitService
from .sadipem import SadipemApiError, SadipemPagamentosService, _client, _data


def obter_margem_publica(projecao, sadipem, client=None):
    """Nunca persiste/importa inventário nem soma fotografias de vários PVLs."""
    resultado = {'status': 'Indisponível', 'rows': [], 'snapshot': sadipem.get('snapshot'),
                 'coverageConfirmed': False, 'motivos': [], 'memoria_exata': []}
    snapshot = sadipem.get('snapshot') or {}
    if sadipem.get('motivo') in ('API_ERROR', 'CANCELLED', 'AMBIGUOUS_DATA'):
        resultado['motivos'].append('Consulta SADIPEM incompleta ou conflitante; não calcular saldo público.')
        return resultado

    ano = projecao.get('ano')
    referencia = _data(snapshot.get('dataProtocolo'))
    if (not snapshot.get('idPleito') or not ano or referencia.year != ano
            or referencia > datetime.now(timezone.utc).replace(tzinfo=None)):
        resultado['motivos'].append('Sem PVL público do exercício para essa referência.')
        return resultado
    try:
        contratadas = CreditFlowLimitService._valor(sadipem.get('liberacoesContratadasSadipem'))
        fonte_zero = None
        if contratadas is None:
            pagamentos = SadipemPagamentosService(client or _client).por_pvl(snapshot['idPleito'])
            relevantes = [p for p in pagamentos if str(p.get('ano')) == str(ano)]
            if (len(relevantes) == 1 and relevantes[0].get('id_pleito') == snapshot['idPleito']
                    and str(relevantes[0].get('indicador_liberacoes') or '').strip() == '0'):
                contratadas = Decimal(0)
                fonte_zero = 'opc-cronograma-pagamentos: indicador_liberacoes=0 (não possui liberações contratadas previstas)'
        if contratadas is None:
            resultado['motivos'].append('O PVL não informa liberações contratadas nem declaração explícita de ausência.')
            return resultado
        linhas = [l for l in sadipem.get('operacoesNaoContratadas', []) if l.get('ano') == ano]
        ids = [l.get('idPleitoNaoContratado') for l in linhas]
        if None in ids or len(ids) != len(set(ids)):
            raise ValueError('Identificadores conflitantes nas operações não contratadas.')
        valores = [CreditFlowLimitService._valor(l.get('liberacaoAnual')) for l in linhas]
        if any(v is None for v in valores):
            raise ValueError('Liberação de operação não contratada ausente.')
        nao_contratadas = sum(valores, Decimal(0))
        if projecao.get('positionOnly') is not True or projecao.get('parameterValidated') is not True:
            raise ValueError('Posição fiscal ou parâmetro de projeção não validado.')
        atual = next((l for l in projecao.get('rows', []) if l.get('ano') == ano), None)
        rcl = CreditFlowLimitService._valor(atual.get('rclProjetada')) if atual else None
        if rcl is None or rcl <= 0:
            raise ValueError('RCL projetada válida não disponível.')
        teto = rcl * Decimal('0.16')
        conhecido = contratadas + nao_contratadas
        exata = {'ano': ano, 'rclProjetada': str(rcl), 'tetoAnual': str(teto),
                 'liberacoesContratadas': str(contratadas), 'liberacoesNaoContratadasListadas': str(nao_contratadas),
                 'scheduledDisbursements': str(conhecido), 'margemEstimada': str(teto - conhecido),
                 'fonteZero': fonte_zero, 'naoContratadasListadas': len(linhas)}
        resultado.update(status='Referência pública', rows=[{k: float(Decimal(v)) if k not in
                         ('ano', 'fonteZero', 'naoContratadasListadas') else v for k, v in exata.items()}],
                         memoria_exata=[exata], consultadoEm=datetime.now(timezone.utc).isoformat(),
                         fonte='SADIPEM / opc-cronograma-liberacoes / opnc-pvl-tramitacao-deferido / opc-cronograma-pagamentos')
        resultado['motivos'].append('Saldo segundo as informações declaradas neste PVL; cobertura atual de todas as operações não confirmada.')
        if not linhas:
            resultado['motivos'].append('Nenhuma operação não contratada listada no PVL; isso não comprova inexistência fora dessa declaração.')
        return resultado
    except (SadipemApiError, ValueError, TypeError) as exc:
        log.warning('Não foi possível calcular a margem pública.', details=str(exc))
        resultado['motivos'].append(mensagem_erro(exc, 'Não foi possível consultar a margem na fonte oficial. Tente novamente mais tarde.'))
        return resultado


def integrar_referencia_publica(simulacao, referencia):
    """Usa liberações documentadas do PVL nos anos desconhecidos, sem validar cobertura."""
    if (referencia.get('status') != 'Referência pública'
            or simulacao.get('evaluationScope') != 'registered_inventory'):
        return simulacao
    por_ano = {linha['ano']: linha for linha in referencia.get('memoria_exata', [])}
    aplicados = []
    for linha in simulacao.get('rows', []):
        fonte = por_ano.get(linha['ano'])
        if not fonte or linha.get('scheduledDisbursements') is not None:
            continue
        rcl = CreditFlowLimitService._valor(linha.get('rclProjetada'))
        nova = CreditFlowLimitService._valor(linha.get('requestedOperation'))
        outras = CreditFlowLimitService._valor(fonte.get('scheduledDisbursements'))
        if rcl is None or rcl <= 0 or nova is None or outras is None:
            continue
        with localcontext() as contexto:
            contexto.prec = 50
            teto, mga = rcl * Decimal('0.16'), outras + nova
            razao = mga / rcl
            uso = razao / Decimal('0.16')
        linha.update(scheduledDisbursements=float(outras), mga=float(mga),
                     tetoAnual=float(teto), margemEstimada=float(teto - mga),
                     mgaRcl=float(razao), percentualMgaRcl=float(razao * 100),
                     limitUsage=float(uso), dadosCompletos=True,
                     verificationStatus='Referência pública', otherDisbursementsState='public_snapshot',
                     situacao='Não Enquadrado' if razao > Decimal('0.16') else 'Enquadrado',
                     status='acima_do_limite' if razao > Decimal('0.16') else 'dentro_do_limite',
                     availableForRequestedOperation=None)
        linha.setdefault('sources', {})['publicReference'] = {
            'snapshot': referencia.get('snapshot'), 'consultadoEm': referencia.get('consultadoEm'),
            'coverageConfirmed': False, 'motivos': referencia.get('motivos', []),
            'memoria_exata': fonte,
            'calculo_exato': {'rclProjetada': str(rcl), 'novaOperacao': str(nova),
                             'outrasLiberacoes': str(outras), 'mga': str(mga),
                             'tetoAnual': str(teto), 'mgaRcl': str(razao)}}
        aplicados.append(linha['ano'])
    if not aplicados:
        return simulacao
    linhas = simulacao['rows']
    completas = all(l.get('dadosCompletos') for l in linhas)
    critico = max(linhas, key=lambda l: l['mgaRcl']) if completas else None
    simulacao.update(publicReference=referencia, publicReferenceYears=aplicados,
                     validatedConclusion=False, maxRequestedAmountForSchedule=None,
                     capacityRestrictingYear=None, dataAvailability=completas,
                     criticalYear=critico['ano'] if critico else None,
                     maxMgaRcl=critico['mgaRcl'] if critico else None,
                     maxLimitUsage=critico['limitUsage'] if critico else None,
                     exceededYears=[l['ano'] for l in linhas if l.get('status') == 'acima_do_limite'],
                     verificationStatus='Referência pública' if completas else 'Dados incompletos',
                     globalStatus='Referência pública' if completas else 'Dados incompletos',
                     otherDisbursementsState='public_snapshot',
                     message='Inclui as liberações declaradas no PVL e a nova operação. '
                             'Cobertura integral não confirmada; anos sem informação permanecem desconhecidos.')
    simulacao['numericOutcome'] = ('Não Enquadrado' if simulacao['exceededYears'] else
                                  'Enquadrado' if completas else 'Projeção indisponível')
    simulacao['exercicios'] = linhas
    atual = next((l for l in linhas if l['ano'] == simulacao.get('ano')), None)
    if atual:
        simulacao.update({k: v for k, v in atual.items() if k not in
                          ('ano', 'sources', 'verificationStatus', 'otherDisbursementsState')})
    return simulacao
