"""Cenários SAC com as datas FCL e juros constantes informados na operação.

CDI/Selic: taxas efetivas anuais em 252 dias úteis. SOFR: hipótese simples
ACT/360, taxa overnight constante, sem alegar Term SOFR ou curva futura.
"""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, localcontext
from .fluxo_tlp import montar_periodos, inteiro
from .indexadores import taxa_valida
from .servico_divida import decimal_nao_negativo


def calcular_fluxo_indexado(valor, data, prazo, carencia, prefixada, spread, indexador, taxa='0'):
    saldo = decimal_nao_negativo(valor, 'Valor do empréstimo')
    if saldo <= 0:
        raise ValueError('Informe um valor positivo para o empréstimo.')
    prefixada, spread, taxa = map(taxa_valida, (prefixada, spread, taxa))
    if indexador not in ('FIXA', 'CDI', 'SELIC', 'SOFR', 'CAMBIAL'):
        raise ValueError('Indexador não atendido neste fluxo.')
    if indexador in ('FIXA', 'CAMBIAL'): taxa = Decimal(0)
    periodos = montar_periodos(data, prazo, carencia)
    parcelas = inteiro(prazo, 'Prazo total', 1, 600) - int(carencia)
    linhas, anuais = [], {}
    juros_total = amortizacao_total = Decimal(0)
    acumulado = Decimal(1)
    corridos_acumulados = 0
    with localcontext() as contexto:
        contexto.prec = 50
        for periodo in periodos:
            corridos = (periodo['fim'] - periodo['inicio']).days
            if indexador == 'SOFR':
                corridos_acumulados += corridos
                acumulado = 1 + (taxa + prefixada + spread) / 100 * Decimal(corridos_acumulados) / 360
                fator = 1 + (taxa + prefixada + spread) / 100 * Decimal(corridos) / 360
            else:
                expoente = Decimal(periodo['dup']) / 252
                fator = ((1 + taxa / 100) * (1 + prefixada / 100) * (1 + spread / 100)) ** expoente
                acumulado *= fator
            juros = (saldo * (acumulado - 1)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if periodo['pagamento'] else Decimal(0)
            amortizacao = (saldo / parcelas).quantize(Decimal('.01'), rounding=ROUND_DOWN) if periodo['amortiza'] else Decimal(0)
            linha = {k: v.isoformat() if hasattr(v, 'isoformat') else v for k, v in periodo.items()}
            linha.update(saldo_inicial=str(saldo), ipca='0', ipca_utilizado=None,
                         indice_utilizado=f'{taxa}% a.a.', taxa_indexador=str(taxa), indexador=indexador,
                         estimado=indexador in ('CDI', 'SELIC', 'SOFR'), ipca_ausente_zero=False,
                         juros=str(juros), amortizacao=str(amortizacao), pagamento_total=str(juros + amortizacao),
                         saldo_final=str(saldo - amortizacao), fator_acumulado=str(acumulado),
                         fatores={'fator_combinado': str(fator)}, dias_corridos=corridos)
            linhas.append(linha)
            anual = anuais.setdefault(periodo['fim'].year, {'juros': Decimal(0), 'amortizacao': Decimal(0)})
            anual['juros'] += juros; anual['amortizacao'] += amortizacao
            juros_total += juros; amortizacao_total += amortizacao; saldo -= amortizacao
            if periodo['amortiza']: parcelas -= 1
            if periodo['pagamento']: acumulado = Decimal(1); corridos_acumulados = 0
    return {'linhas': linhas, 'anuais': [{'ano': a, **{k: str(v) for k, v in valores.items()}, 'total': str(sum(valores.values()))} for a, valores in anuais.items()],
            'juros_total': str(juros_total), 'amortizacao_total': str(amortizacao_total),
            'pagamento_total': str(juros_total + amortizacao_total), 'saldo_final': str(saldo),
            'data_final': periodos[-1]['fim'].isoformat(), 'estimado': indexador in ('CDI', 'SELIC', 'SOFR'),
            'indexador': indexador, 'ultima_competencia_publicada': None,
            'convencao': ('Cenário SOFR overnight constante: juros simples ACT/360; taxas e spread somados.' if indexador == 'SOFR' else
                          'Cenário com taxas anuais constantes e composição de fatores em 252 dias úteis.') +
                         ' Datas e amortizações seguem o calendário FCL; juros trimestrais na carência.',
            'calendario': 'Feriados da planilha fornecida, 2009–2060.'}
