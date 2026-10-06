"""Leitura fiscal do ente antes de simular uma nova operação."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from .data_access import (obter_rcl_ajustada_endividamento, obter_registros_dcl,
                          obter_registros_dtp, obter_dados_rreo_para_analise,
                          obter_servico_divida_exercicio_anterior, CONTAS_SERVICO_DIVIDA,
                          COLUNA_LIQUIDADA, COLUNA_RESTOS)
from .database_models import db, RREO, SincronizacaoSiconfi
from .dcl import avaliar_dcl
from .dtp import consolidar_dtp
from .indicadores_rgf import obter_indicadores_rgf, obter_limite_mga_publicado
from .fluxo_credito import CreditFlowLimitService
from .capag import obter_capag
from .rule_engine import RegraDeOuroAnoAnterior, RegraDeOuroAnoAtual
from .servico_divida import avaliar_exercicio_anterior


LIMITES_REFERENCIA = {
    'MGA/RCL': 16, 'CAED/RCL': 11.5, 'DCL/RCL': 200,
    'ARO/RCL': 7, 'Garantias/RCL': 22, 'DTP/RCL': 60,
}
INDICADORES_PAINEL = (
    'RCL', 'CAPAG', 'DCL/RCL', 'CAED/RCL', 'MGA/RCL',
    'ARO/RCL', 'Garantias/RCL', 'DTP/RCL',
    'Regra de Ouro anterior', 'Regra de Ouro corrente',
)


def _ultimo_servico_realizado(ano_limite):
    """Usa o último exercício fechado com RCL e despesas do mesmo bimestre."""
    for ano in range(min(ano_limite, datetime.now().year - 1), 2020, -1):
        despesas = obter_servico_divida_exercicio_anterior(ano)
        rcl = obter_rcl_ajustada_endividamento(ano)
        if not despesas or not rcl or despesas['periodo'] != 6 or rcl['periodo'] != 6:
            continue
        juros = despesas['contas'][CONTAS_SERVICO_DIVIDA[0]]
        amortizacao = despesas['contas'][CONTAS_SERVICO_DIVIDA[1]]
        resultado = avaliar_exercicio_anterior(
            rcl['valor'], juros[COLUNA_LIQUIDADA], amortizacao[COLUNA_LIQUIDADA],
            juros[COLUNA_RESTOS], amortizacao[COLUNA_RESTOS])
        return {'valor': float(resultado['percentual'] * 100), 'limite': 11.5,
                'ano': ano, 'periodo': 6, 'anexo': 'RREO-Anexos 01 e 03',
                'origem': 'SICONFI/RREO', 'natureza': 'servico_realizado',
                'periodicidade': 'B', 'historico': True,
                'servico_divida': float(resultado['servico_divida']),
                'rcl': float(resultado['rcl'])}
    return None


def _ouro_previo(ano, registros, classe, tipo):
    linhas = registros.get(ano, {}).get('registros', [])
    despesas = {'AMORTIZAÇÃO DA DÍVIDA', 'INVERSÕES FINANCEIRAS', 'INVESTIMENTOS'}
    coluna_operacao = ('Até o Bimestre (c)' if tipo == 'regra_ouro_anterior'
                      else 'PREVISÃO ATUALIZADA (a)')
    tem_operacao = any(r['conta'] == 'OPERAÇÕES DE CRÉDITO'
                       and r['coluna'] == coluna_operacao for r in linhas)
    tem_despesas = all(any(r['conta'] == conta and r['coluna'] in (
        'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)',
        'INSCRITAS EM RESTOS A PAGAR NÃO PROCESSADOS (k)') for r in linhas)
        for conta in despesas)
    if not tem_operacao or not tem_despesas:
        return {'ano': ano, 'situacao': 'Dados insuficientes', 'dados_calculados': None}
    resultado = classe(ano if tipo == 'regra_ouro_atual' else ano + 1,
                       registros, {}, 0).avaliar()
    return {'ano': ano, 'situacao': 'Atendida' if resultado['aprovado'] else 'Não atendida',
            'dados_calculados': resultado['dados_calculados']}


def obter_painel_fiscal():
    ano_atual = datetime.now().year
    ano = db.session.query(func.max(RREO.exercicio)).filter(
        RREO.uf == 'GO', RREO.esfera == 'E', RREO.exercicio <= ano_atual).scalar()
    if ano is None:
        capag = obter_capag()
        return {'ente': 'Estado de Goiás', 'tipo_ente': 'Estado', 'exercicio': None,
                'ultima_consulta': None, 'rcl': None, 'dcl': None, 'dtp': None,
                'capag': capag, 'limite_mga_publicado': None,
                'fluxo_credito': None, 'regra_ouro': [],
                'fontes': [{'indicador': 'CAPAG', **capag}] if capag else [],
                'dados_disponiveis': int(capag is not None),
                'dados_indisponiveis': len(INDICADORES_PAINEL) - int(capag is not None),
                'limites_referencia': LIMITES_REFERENCIA}

    rcl = obter_rcl_ajustada_endividamento(ano)
    dcl = avaliar_dcl(ano, obter_registros_dcl(ano))
    dtp = consolidar_dtp(ano, obter_registros_dtp(ano))
    indicadores_rgf = obter_indicadores_rgf(ano)
    limite_mga_publicado = obter_limite_mga_publicado(ano)
    caed = _ultimo_servico_realizado(ano)
    capag = obter_capag()
    consulta = db.session.query(func.max(SincronizacaoSiconfi.consultado_em)).scalar()
    dados_rreo = obter_dados_rreo_para_analise(ano)
    ouro = [
        _ouro_previo(ano - 1, dados_rreo, RegraDeOuroAnoAnterior,
                     'regra_ouro_anterior'),
        _ouro_previo(ano, dados_rreo, RegraDeOuroAnoAtual,
                     'regra_ouro_atual'),
    ]
    rcl_dto = None if rcl is None else {
        'valor': float(rcl['valor']), 'ano': ano, 'periodo': rcl['periodo'],
        'anexo': rcl['anexo'], 'origem': rcl['origem'],
    }
    fluxo_credito = CreditFlowLimitService().avaliar(
        ano, rcl_referencia=rcl['valor'] if rcl else None,
        teto_referencia_publicado=(limite_mga_publicado['valor']
                                   if limite_mga_publicado else None),
        fontes=([{'tipo': 'RCL de referência', 'origem': rcl['origem'],
                  'anexo': rcl['anexo'], 'ano': ano, 'periodo': rcl['periodo']}]
                if rcl else []) + ([{'tipo': 'Teto de referência',
                                    **limite_mga_publicado}]
                                   if limite_mga_publicado else []))
    dcl_dto = None
    if dcl is not None:
        atual = next((v['percentual'] for v in dcl['dados_calculados']['valores']
                      if v['rotulo'].startswith('Até o ')), None)
        limite = Decimal('200')
        valor = Decimal(str(atual)) if atual is not None else None
        dcl_dto = {'valor': atual, 'limite': float(limite),
                   'utilizacao': float(valor / limite * 100) if valor is not None else None,
                   'margem': float(limite - valor) if valor is not None else None,
                   'situacao': ('Dados insuficientes' if valor is None else
                                'Dentro do limite' if valor <= limite else 'Limite excedido'),
                   'ano': ano, 'periodo': dcl['dados_calculados']['quadrimestre'],
                   'anexo': 'RGF-Anexo 02', 'origem': 'SICONFI/RGF'}
    dtp_dto = None if dtp is None else {
        'valor': dtp['dados_calculados']['percentual'],
        'limite': dtp['dados_calculados']['limite_percentual'],
        'utilizacao': dtp['dados_calculados']['percentual_limite_consumido'],
        'margem': dtp['dados_calculados']['margem_pontos_percentuais'],
        'situacao': 'Dentro do limite' if dtp['aprovado'] else 'Limite excedido',
        'ano': ano, 'periodo': dtp['dados_calculados']['quadrimestre'],
        'anexo': 'RGF-Anexo 01', 'origem': 'SICONFI/RGF',
    }
    for chave, limite in (('garantias', 22), ('mga', 16), ('aro', 7)):
        dado = indicadores_rgf.get(chave)
        if dado:
            valor = Decimal(str(dado['valor']))
            dado.update(limite=limite, utilizacao=float(valor / Decimal(limite) * 100),
                        margem=float(Decimal(limite) - valor),
                        situacao='Dentro do limite' if valor <= limite else 'Limite excedido')
    fontes = [
        {'indicador': 'RCL ajustada', **rcl_dto} if rcl_dto else None,
        {'indicador': 'DCL/RCL', **dcl_dto} if dcl_dto and dcl_dto['valor'] is not None else None,
        {'indicador': 'DTP', **dtp_dto} if dtp_dto else None,
    ]
    fontes = [fonte for fonte in fontes if fonte is not None]
    if limite_mga_publicado:
        fontes.append({'indicador': 'Limite de operações de crédito (16% da RCL)',
                       **limite_mga_publicado})
    for chave, rotulo in (('garantias', 'Garantias/RCL'),
                          ('mga', 'Operações de crédito/RCL'), ('aro', 'ARO/RCL')):
        if chave in indicadores_rgf and not indicadores_rgf[chave].get('historico'):
            fontes.append({'indicador': rotulo, **indicadores_rgf[chave]})
    if caed:
        fontes.append({'indicador': 'Serviço da dívida realizado/RCL', **caed})
    if capag:
        fontes.append({'indicador': 'CAPAG', **capag})
    for item in ouro:
        calculados = item['dados_calculados']
        if calculados:
            fontes.append({'indicador': f"Regra de Ouro — {item['ano']}",
                           'valor': calculados['limite_disponivel'],
                           'origem': 'SICONFI/RREO',
                           'anexo': ', '.join(sorted({f['anexo'] for f in calculados['fontes']})),
                           'ano': item['ano'],
                           'periodo': max((f['periodo'] for f in calculados['fontes']), default=None)})
    disponiveis = sum((rcl_dto is not None, dcl_dto is not None and dcl_dto['valor'] is not None,
                       dtp_dto is not None, *[item['dados_calculados'] is not None for item in ouro],
                       *[chave in indicadores_rgf for chave in ('garantias', 'mga', 'aro')],
                       capag is not None, caed is not None))
    return {
        'ente': 'Estado de Goiás', 'tipo_ente': 'Estado', 'exercicio': ano,
        'ultima_consulta': consulta.isoformat() if consulta else None,
        'rcl': rcl_dto, 'dcl': dcl_dto, 'dtp': dtp_dto, 'capag': capag,
        'caed': caed, 'limite_mga_publicado': limite_mga_publicado,
        'fluxo_credito': fluxo_credito,
        **indicadores_rgf,
        'regra_ouro': ouro, 'fontes': fontes,
        'limites_referencia': LIMITES_REFERENCIA,
        'dados_disponiveis': disponiveis,
        'dados_indisponiveis': len(INDICADORES_PAINEL) - disponiveis,
    }
