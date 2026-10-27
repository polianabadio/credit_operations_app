"""Fluxo FCL/TLP: colunas B:O do modelo fornecido, com memória por mês.

Corrige L37 (referência a C17/L17) e encerra na última amortização,
sem executar a linha adicional com divisor de parcelas igual a zero.
"""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from .calendario_fcl import FERIADOS_FCL
from .encargos import calcular_encargos
from .servico_divida import decimal_nao_negativo


def data_iso(valor):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise ValueError('Informe uma data válida para a liberação.') from None


def deslocar_mes(data, meses):
    indice = data.year * 12 + data.month - 1 + meses
    ano, mes = divmod(indice, 12)
    return date(ano, mes + 1, min(data.day, monthrange(ano, mes + 1)[1]))


def util(data, feriados):
    return data.weekday() < 5 and data.isoformat() not in feriados


def proximo_util(data, feriados=FERIADOS_FCL):
    while not util(data, feriados):
        data += timedelta(days=1)
    return data


def dias_excel(inicio, fim, feriados=FERIADOS_FCL):
    """NETWORKDAYS(inicio, fim, feriados)-1, inclusive nas duas pontas."""
    if fim < inicio:
        raise ValueError('As datas do período estão fora de ordem.')
    total = 0
    while inicio <= fim:
        total += util(inicio, feriados)
        inicio += timedelta(days=1)
    return total - 1


def inteiro(valor, nome, minimo, maximo):
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or numero != int(numero) or not minimo <= numero <= maximo:
            raise ValueError()
        return int(numero)
    except (ValueError, TypeError, ArithmeticError):
        raise ValueError(f'{nome}: informe um número inteiro entre {minimo} e {maximo}.') from None


def montar_periodos(data_liberacao, prazo_meses, carencia_meses, feriados=FERIADOS_FCL):
    liberacao = data_iso(data_liberacao)
    prazo = inteiro(prazo_meses, 'Prazo total em meses', 1, 600)
    carencia = inteiro(carencia_meses, 'Carência em meses', 0, prazo - 1)
    if carencia and carencia % 3:
        raise ValueError('Neste modelo, a carência deve ser um múltiplo de 3 meses, com juros trimestrais.')
    referencia = liberacao.replace(day=15)
    if liberacao.day <= 15:
        referencia = deslocar_mes(referencia, -1)
    periodos = []
    inicio = liberacao
    # O modelo começa a amortização na linha 24; 24 + 216 - 1 = 239.
    quantidade = carencia + (prazo - carencia) - 1 if carencia else prazo
    for indice in range(quantidade):
        ref = deslocar_mes(referencia, indice)
        quebra = proximo_util(deslocar_mes(ref, 1), feriados)
        if inicio.year < 2009 or quebra.year > 2060:
            raise ValueError('As datas estão fora do calendário da planilha (2009 a 2060).')
        mes = indice + 1
        amortiza = mes >= carencia if carencia else True
        pagamento = amortiza or mes % 3 == 0
        # Série TXD00236 rotula no dia 15 a inflação do mês civil anterior (M-1).
        competencia = deslocar_mes(ref, -1).strftime('%Y-%m')
        periodos.append({'mes': mes, 'inicio': inicio, 'fim': quebra,
                         'referencia': ref, 'competencia_ipca': competencia,
                         'dup': dias_excel(inicio, quebra, feriados),
                         'dut': dias_excel(ref, quebra, feriados),
                         'pagamento': pagamento, 'amortiza': amortiza})
        inicio = quebra
    return periodos


def calcular_fluxo_tlp(valor, data_liberacao, prazo_meses, carencia_meses,
                       prefixada, spread, indices, repetir_ultimo=False,
                       hoje=None, feriados=FERIADOS_FCL, ipca_ausente_zero=True):
    """indices: mapa YYYY-MM -> IPCA mensal publicado (sem deslocamento de rótulo)."""
    saldo = decimal_nao_negativo(valor, 'Valor do empréstimo')
    if saldo <= 0:
        raise ValueError('Informe um valor positivo para o empréstimo.')
    periodos = montar_periodos(data_liberacao, prazo_meses, carencia_meses, feriados)
    prazo = inteiro(prazo_meses, 'Prazo total em meses', 1, 600)
    carencia = inteiro(carencia_meses, 'Carência em meses', 0, prazo - 1)
    serie = {}
    for mes, valor_indice in indices.items():
        try:
            if date.fromisoformat(mes + '-01').strftime('%Y-%m') != mes:
                raise ValueError()
            indice = Decimal(str(valor_indice))
            if not indice.is_finite() or indice <= -100:
                raise ValueError()
        except (ValueError, TypeError, ArithmeticError):
            raise ValueError('A série de inflação contém mês ou valor inválido.') from None
        serie[mes] = indice
    hoje = hoje or date.today()
    if any(mes >= hoje.strftime('%Y-%m') for mes in serie):
        raise ValueError('A série publicada contém inflação de um mês ainda não encerrado.')
    if not serie and not ipca_ausente_zero:
        raise ValueError('Não há inflação publicada disponível para calcular o fluxo.')
    ultimo_mes = max(serie, default=None)
    fator_acumulado = Decimal(1)
    parcelas = prazo - carencia
    linhas, anuais = [], {}
    total_juros = Decimal(0)
    total_amortizacao = Decimal(0)
    for periodo in periodos:
        competencia = periodo['competencia_ipca']
        estimado = competencia not in serie
        if estimado and not ipca_ausente_zero and (not repetir_ultimo or competencia <= ultimo_mes):
            raise ValueError(f'IPCA indisponível para {competencia}. Nenhum índice foi substituído por zero.')
        mes_utilizado = (None if ipca_ausente_zero else ultimo_mes) if estimado else competencia
        ipca = Decimal(0) if mes_utilizado is None else serie[mes_utilizado]
        fatores = calcular_encargos(saldo, ipca, prefixada, spread, periodo['dup'], periodo['dut'])
        fator_acumulado *= Decimal(fatores['fator_combinado'])
        juros = ((saldo * (fator_acumulado - 1)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                 if periodo['pagamento'] else Decimal(0))
        amortizacao = ((saldo / parcelas).quantize(Decimal('.01'), rounding=ROUND_DOWN)
                       if periodo['amortiza'] else Decimal(0))
        saldo_final = saldo - amortizacao
        linha = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in periodo.items()}
        linha.update(saldo_inicial=str(saldo), ipca=str(ipca), ipca_utilizado=mes_utilizado,
                     estimado=estimado, ipca_ausente_zero=estimado and ipca_ausente_zero, juros=str(juros), amortizacao=str(amortizacao),
                     pagamento_total=str(juros + amortizacao), saldo_final=str(saldo_final),
                     fator_acumulado=str(fator_acumulado), fatores=fatores)
        linhas.append(linha)
        if periodo['pagamento']:
            fator_acumulado = Decimal(1)
        if periodo['amortiza']:
            parcelas -= 1
        ano = periodo['fim'].year
        anual = anuais.setdefault(ano, {'juros': Decimal(0), 'amortizacao': Decimal(0)})
        anual['juros'] += juros
        anual['amortizacao'] += amortizacao
        total_juros += juros
        total_amortizacao += amortizacao
        saldo = saldo_final
    return {'linhas': linhas, 'anuais': [{'ano': ano, **{k: str(v) for k, v in valores.items()},
                                         'total': str(sum(valores.values()))} for ano, valores in anuais.items()],
            'juros_total': str(total_juros), 'amortizacao_total': str(total_amortizacao),
            'pagamento_total': str(total_juros + total_amortizacao), 'saldo_final': str(saldo),
            'data_final': periodos[-1]['fim'].isoformat(),
            'estimado': any(linha['estimado'] for linha in linhas),
            'ultima_competencia_publicada': ultimo_mes,
            'convencao': 'Modelo FCL: referência no dia 15, IPCA M-1, juros base 252; '
                         'juros trimestrais na carência e amortização mensal a partir do mês da carência.',
            'calendario': 'Feriados da planilha fornecida, 2009–2060.'}
