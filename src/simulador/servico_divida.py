"""Memória única do CAED: RSF 43/2001, art. 7º, II e § 4º."""
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

LIMITE = Decimal('0.115')


def decimal_nao_negativo(valor, campo):
    if valor is None or isinstance(valor, bool):
        raise ValueError(f'{campo}: dado ausente ou inválido')
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{campo}: dado ausente ou inválido') from None
    if not numero.is_finite() or numero < 0:
        raise ValueError(f'{campo}: dado ausente ou inválido')
    return numero


def valor_monetario(valor, campo):
    numero = decimal_nao_negativo(valor, campo)
    if numero * 100 != (numero * 100).to_integral_value():
        raise ValueError(f'{campo}: informe no máximo duas casas decimais')
    return numero


def memoria_decimal(valor):
    """Serializa memória exata sem converter Decimal em ponto flutuante."""
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, dict):
        return {str(k): memoria_decimal(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [memoria_decimal(v) for v in valor]
    return valor


def avaliar_exercicio_anterior(rcl, juros_encargos, amortizacao,
                               restos_juros=None, restos_amortizacao=None):
    """Diagnóstico observado, sem bloquear a conclusão prospectiva."""
    rcl = decimal_nao_negativo(rcl, 'RCL')
    juros = decimal_nao_negativo(juros_encargos, 'juros e encargos')
    amortizacao = decimal_nao_negativo(amortizacao, 'amortização')
    restos_juros = decimal_nao_negativo(restos_juros, 'restos de juros') if restos_juros is not None else Decimal(0)
    restos_amortizacao = (decimal_nao_negativo(restos_amortizacao, 'restos de amortização')
                          if restos_amortizacao is not None else Decimal(0))
    if rcl == 0:
        raise ValueError('RCL deve ser positiva')
    servico = juros + amortizacao + restos_juros + restos_amortizacao
    limite = rcl * LIMITE
    return {'rcl': rcl, 'juros_encargos': juros, 'amortizacao': amortizacao,
            'restos_juros': restos_juros, 'restos_amortizacao': restos_amortizacao,
            'servico_divida': servico, 'limite': limite, 'margem': limite - servico,
            'percentual': servico / rcl, 'aprovado': servico <= limite}


def projetar_rcl(rcl_base, exercicio_base, periodo, anos, fator):
    """Projeta do fim do bimestre fiscal até dezembro de cada exercício."""
    rcl = decimal_nao_negativo(rcl_base, 'RCL base')
    if rcl <= 0 or not isinstance(exercicio_base, int) or not isinstance(periodo, int) or not 1 <= periodo <= 6:
        raise ValueError('RCL ou data-base fiscal inválida')
    if not isinstance(fator, dict) or not all(fator.get(k) for k in (
            'valor', 'fonte', 'vigencia_inicio', 'referencia_validada_ate', 'data_referencia')):
        raise ValueError('Fator sem fonte, vigência ou data de referência')
    referencia = date.fromisoformat(fator['data_referencia'])
    if not date.fromisoformat(fator['vigencia_inicio']) <= referencia <= date.fromisoformat(fator['referencia_validada_ate']):
        raise ValueError('Fator fora da vigência documentada')
    multiplicador = decimal_nao_negativo(fator['valor'], 'multiplicador')
    if multiplicador <= 0:
        raise ValueError('Multiplicador deve ser positivo')
    with localcontext() as contexto:
        contexto.prec = 50
        saida = {}
        for ano in anos:
            meses = 12 * (ano - exercicio_base) + 12 - 2 * periodo
            if meses < 0:
                raise ValueError('Projeção anterior à data-base fiscal')
            saida[ano] = rcl * multiplicador ** (Decimal(meses) / 12)
        return saida


def avaliar_alternativas(linhas):
    """Ambas as alternativas são recortes do mesmo cronograma consolidado."""
    elegiveis = [l for l in linhas if l['operacao_pleiteada'] > 0]
    if not elegiveis:
        raise ValueError('Não há pagamentos previstos da operação pretendida')
    if any(l.get('percentual') is None for l in elegiveis):
        raise ValueError('Cronograma consolidado incompleto')
    def media(universo):
        return sum((l['percentual'] for l in universo), Decimal(0)) / len(universo)
    with localcontext() as contexto:
        contexto.prec = 50
        ate_2027 = [l for l in elegiveis if l['ano'] <= 2027]
        media_a = media(elegiveis)
        media_b = media(ate_2027) if ate_2027 else None
        alternativa = 'ATE_2027' if media_b is not None and media_b < media_a else 'TERMINO_OPERACAO'
        determinante = media_b if alternativa == 'ATE_2027' else media_a
        return {'media_termino': media_a, 'media_2027': media_b,
                'anos_termino': [l['ano'] for l in elegiveis],
                'anos_2027': [l['ano'] for l in ate_2027],
                'alternativa_utilizada': alternativa, 'percentual_determinante': determinante,
                'limite_percentual': LIMITE, 'aprovado': determinante <= LIMITE}


def avaliar_caed(ano, entrada, referencia, fator, motivos_iniciais=None):
    """Produz DTO e memória inclusive em ausência, conflito e retornos antecipados."""
    motivos = list(motivos_iniciais or [])
    dados = {'ano_atual': ano, 'rcl_fonte': memoria_decimal(referencia),
             'fator_atualizacao': memoria_decimal(fator), 'linhas': [],
             'media_termino': None, 'media_2027': None, 'alternativa_utilizada': None,
             'percentual_determinante': None, 'limite_percentual': 11.5,
             'motivos': motivos, 'cobertura': None,
             'memoria_exata': {'entrada': memoria_decimal(entrada), 'rcl': memoria_decimal(referencia),
                               'fator': memoria_decimal(fator), 'linhas': [], 'comparador': '<=',
                               'limite_percentual': str(LIMITE), 'precisao_decimal': 50}}
    def motivo(codigo, mensagem, campo=None):
        motivos.append({'codigo': codigo, 'mensagem': mensagem, 'campo': campo})
    def resultado(aprovado=None):
        estado = 'INCONCLUSIVO' if aprovado is None else 'ATENDE' if aprovado else 'NAO_ATENDE'
        return {'tipo': 'servico_divida', 'nome': 'Serviço da Dívida — CAED',
                'estado': estado, 'status': estado, 'aprovado': aprovado,
                'descricao': ('; '.join(m['mensagem'] for m in motivos) if aprovado is None else
                    'A média mais benéfica atende ao limite de 11,5%.' if aprovado else
                    'As médias aplicáveis excedem o limite de 11,5%.'), 'dados_calculados': dados}
    if not isinstance(entrada, dict):
        motivo('CRONOGRAMA_AUSENTE', 'Informe o cronograma único de pagamentos.')
        return resultado()
    try:
        if date.fromisoformat(entrada.get('data_referencia', '')).year != ano:
            raise ValueError('Exercício diferente')
    except (TypeError, ValueError):
        motivo('DATA_REFERENCIA_INVALIDA', 'Informe uma data de referência no exercício selecionado.')
    if any(k in entrada for k in ('hipotese_1', 'hipotese_2', 'fator', 'fator_atualizacao')):
        motivo('CONTRATO_LEGADO', 'Use o cronograma único; hipóteses independentes e fator legado não são aceitos.')
        return resultado()
    fim, linhas = entrada.get('ano_fim_contrato'), entrada.get('linhas')
    if (not isinstance(fim, int) or isinstance(fim, bool) or not ano <= fim <= ano + 50
            or not isinstance(linhas, list) or not linhas or len(linhas) > 51
            or any(not isinstance(l, dict) or not isinstance(l.get('ano'), int)
                   or isinstance(l.get('ano'), bool) for l in linhas)
            or len(linhas) != fim - ano + 1 or {l['ano'] for l in linhas} != set(range(ano, fim + 1))):
        motivo('CRONOGRAMA_INVALIDO', 'Preencha todos os anos do contrato, sem repetição.')
        return resultado()
    cobertura = entrada.get('cobertura_demais')
    dados['cobertura'] = memoria_decimal(cobertura)
    cobertura_valida = False
    if isinstance(cobertura, dict) and cobertura.get('completa') is True and str(cobertura.get('fonte') or '').strip():
        try:
            data_cobertura = date.fromisoformat(cobertura.get('data_referencia', ''))
            data_analise = date.fromisoformat(entrada.get('data_referencia', ''))
            cobertura_valida = data_cobertura <= data_analise
        except (ValueError, TypeError):
            pass
    if not cobertura_valida:
        motivo('COBERTURA_DEMAIS_AUSENTE', 'Confirme a cobertura das demais operações com fonte e data; ausência não é zero.')
    if not referencia:
        motivo('RCL_AUSENTE', 'RCL ajustada para endividamento não disponível.')
    if not fator:
        motivo('FATOR_NAO_VALIDADO', 'Fator sem fonte/vigência validada para a data de referência.')
    rcls = {}
    if referencia and fator:
        try:
            rcls = projetar_rcl(referencia['valor'], referencia['exercicio'], referencia['periodo'],
                               [l['ano'] for l in linhas], fator)
        except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
            motivo('RCL_OU_FATOR_INVALIDO', str(exc))
    exatas = []
    with localcontext() as contexto:
        contexto.prec = 50
        for linha in sorted(linhas, key=lambda l: l['ano']):
            exercicio = linha['ano']
            componentes = {}
            for chave in ('juros_encargos', 'amortizacao', 'demais_operacoes'):
                try:
                    componentes[chave] = valor_monetario(linha.get(chave), f'{chave} de {exercicio}')
                except ValueError as exc:
                    componentes[chave] = None
                    motivo('PAGAMENTO_AUSENTE_OU_INVALIDO', str(exc), f'{exercicio}.{chave}')
            juros, amortizacao, demais = (componentes[k] for k in ('juros_encargos', 'amortizacao', 'demais_operacoes'))
            pleiteada = juros + amortizacao if juros is not None and amortizacao is not None else None
            total = pleiteada + demais if pleiteada is not None and demais is not None else None
            rcl = rcls.get(exercicio)
            percentual = total / rcl if total is not None and rcl is not None else None
            exatas.append({'ano': exercicio, **componentes, 'operacao_pleiteada': pleiteada,
                           'caed_total': total, 'rcl_projetada': rcl, 'percentual': percentual,
                           'meses_projecao': (12 * (exercicio - referencia['exercicio']) + 12 - 2 * referencia['periodo']) if rcl is not None else None})
    dados['memoria_exata']['linhas'] = memoria_decimal(exatas)
    dados['linhas'] = [{k: float(v) if isinstance(v, Decimal) else v for k, v in l.items()} for l in exatas]
    if motivos:
        return resultado()
    try:
        alternativas = avaliar_alternativas(exatas)
    except ValueError as exc:
        motivo('SEM_PAGAMENTOS_ELEGIVEIS', str(exc))
        return resultado()
    dados['memoria_exata']['alternativas'] = memoria_decimal(alternativas)
    dados.update({k: float(v * 100) if isinstance(v, Decimal) else v
                  for k, v in alternativas.items() if k != 'aprovado'})
    return resultado(alternativas['aprovado'])
