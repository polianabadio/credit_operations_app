"""Memória de encargos por trecho informado; não é limite fiscal do MIP."""
from decimal import Decimal, ROUND_HALF_UP
from .servico_divida import decimal_nao_negativo


def calcular_encargos(saldo, ipca, prefixada, spread, dias_uteis, dias_indice):
    saldo = decimal_nao_negativo(saldo, 'Saldo base')
    prefixada = decimal_nao_negativo(prefixada, 'Taxa prefixada')
    spread = decimal_nao_negativo(spread, 'Spread')
    dup = decimal_nao_negativo(dias_uteis, 'Dias úteis do trecho')
    dut = decimal_nao_negativo(dias_indice, 'Dias úteis do índice')
    try:
        ipca = Decimal(str(ipca))
    except Exception:
        raise ValueError('IPCA ausente ou inválido') from None
    if not ipca.is_finite() or ipca <= -100:
        raise ValueError('IPCA deve ser maior que -100%')
    if dut == 0 or dup > dut or dup != int(dup) or dut != int(dut):
        raise ValueError('Informe dias inteiros: 0 ≤ dias do trecho ≤ dias do índice, com denominador positivo')
    fator_ipca = (1 + ipca / 100) ** (dup / dut)
    fator_prefixado = (1 + prefixada / 100) ** (dup / 252)
    fator_spread = (1 + spread / 100) ** (dup / 252)
    fator = fator_ipca * fator_prefixado * fator_spread
    return {chave: str(valor) for chave, valor in {
        'fator_ipca': fator_ipca, 'fator_prefixado': fator_prefixado,
        'fator_spread': fator_spread, 'fator_combinado': fator,
        'encargos': (saldo * (fator - 1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
    }.items()}
