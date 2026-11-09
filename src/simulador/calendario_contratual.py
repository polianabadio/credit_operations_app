"""Datas explícitas para desembolsos em etapas; não presume um contrato assinado."""
from datetime import timedelta
from .fluxo_tlp import data_iso, deslocar_mes, inteiro


def calendario_fixo(entrada):
    assinatura = data_iso(entrada.get('data_assinatura'))
    vigencia = data_iso(entrada.get('data_vigencia'))
    liberacao = data_iso(entrada.get('data_liberacao'))
    primeiro = data_iso(entrada.get('primeiro_vencimento_juros'))
    if not assinatura <= vigencia <= liberacao:
        raise ValueError('Confira as datas: assinatura ≤ vigência ≤ primeira liberação.')
    if assinatura.year != int(entrada['ano']) or liberacao.year != int(entrada['ano']):
        raise ValueError('O exercício deve abranger a assinatura e a primeira liberação; não omita encargos de exercícios anteriores.')
    prazo = inteiro(entrada.get('prazo_meses'), 'Prazo total', 1, 600)
    carencia = inteiro(entrada.get('carencia_meses'), 'Carência', 0, prazo - 1)
    pa = inteiro(entrada.get('periodicidade_amortizacao'), 'Periodicidade da amortização', 1, 12)
    pj = inteiro(entrada.get('periodicidade_juros'), 'Periodicidade dos juros', 1, 12)
    if pa not in (1, 3, 6, 12) or pj not in (1, 3, 6, 12) or pa < pj or pa % pj:
        raise ValueError('No calendário fixo, a amortização deve coincidir com vencimentos de juros: escolha periodicidades compatíveis.')
    if not vigencia < primeiro <= deslocar_mes(vigencia, pj):
        raise ValueError('Informe o primeiro vencimento de juros após a vigência, dentro da periodicidade escolhida.')
    nominal = deslocar_mes(assinatura, prazo)
    juros = []
    n = 0
    while deslocar_mes(primeiro, n * pj) <= nominal:
        juros.append(deslocar_mes(primeiro, n * pj))
        n += 1
    if not juros:
        raise ValueError('Não há vencimento de juros dentro do prazo informado.')
    alvo = deslocar_mes(vigencia, carencia)
    if alvo > nominal:
        raise ValueError('A carência contada da vigência ultrapassa o prazo final contado da assinatura.')
    if carencia:
        anteriores = [d for d in juros if d <= alvo]
        if not anteriores:
            raise ValueError('A carência termina antes do primeiro vencimento. Confira o calendário.')
        primeira_amortizacao = anteriores[-1]
    else:
        primeira_amortizacao = juros[0]
    fim = juros[-1]
    if primeira_amortizacao > fim or liberacao > fim:
        raise ValueError('Confira os prazos de vigência, liberação e amortização.')
    amortizacoes = set(juros[juros.index(primeira_amortizacao)::pa // pj])
    amortizacoes.add(fim)
    if not amortizacoes.issubset(set(juros)):
        raise ValueError('As amortizações devem coincidir com os vencimentos de juros.')
    dias = inteiro(entrada.get('dias_inicio_comissao'), 'Dias para início da comissão', 0, 6000)
    prazo_desembolso = inteiro(entrada.get('prazo_desembolso_meses'), 'Prazo para desembolsos', 1, 600)
    return dict(inicio=assinatura, assinatura=assinatura, vigencia=vigencia,
                primeira_liberacao=liberacao, primeiro_vencimento_juros=primeiro,
                termino_nominal=nominal, primeira_amortizacao=primeira_amortizacao,
                fim=fim, amortizacoes=amortizacoes, juros=set(juros),
                inicio_comissao=assinatura + timedelta(days=dias),
                limite_desembolso=deslocar_mes(vigencia, prazo_desembolso))
