"""Cálculos reproduzíveis do limite de serviço da dívida.

As fontes contábeis devem ser confirmadas antes de produzir um parecer automático.
"""

from decimal import Decimal, InvalidOperation


LIMITE = Decimal("0.115")
FATOR_MEDIA_GEOMETRICA_10_ANOS = Decimal("2.031208231")


def decimal_nao_negativo(valor, campo):
    if valor is None or isinstance(valor, bool):
        raise ValueError(f"{campo}: dado ausente ou inválido")
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{campo}: dado ausente ou inválido") from None
    if not numero.is_finite() or numero < 0:
        raise ValueError(f"{campo}: dado ausente ou inválido")
    return numero


def avaliar_exercicio_anterior(rcl, juros_encargos, amortizacao,
                               restos_juros=None, restos_amortizacao=None):
    """Avalia o histórico com comparação estrita; restos ausentes são opcionais."""
    rcl = decimal_nao_negativo(rcl, "RCL")
    juros = decimal_nao_negativo(juros_encargos, "juros e encargos")
    amortizacao = decimal_nao_negativo(amortizacao, "amortização")
    restos_juros = decimal_nao_negativo(restos_juros, "restos de juros") if restos_juros is not None else Decimal(0)
    restos_amortizacao = (decimal_nao_negativo(restos_amortizacao, "restos de amortização")
                          if restos_amortizacao is not None else Decimal(0))
    if rcl == 0:
        raise ValueError("RCL deve ser positiva")
    servico = juros + amortizacao + restos_juros + restos_amortizacao
    limite = rcl * LIMITE
    return {
        "rcl": rcl, "juros_encargos": juros, "amortizacao": amortizacao,
        "restos_juros": restos_juros, "restos_amortizacao": restos_amortizacao,
        "servico_divida": servico, "limite": limite,
        "margem": limite - servico,
        "percentual": servico / rcl,
        "aprovado": servico < limite,
    }


def projetar_anos(rcl_base, linhas, *, ano_base, fator=FATOR_MEDIA_GEOMETRICA_10_ANOS):
    """Projeta a RCL atual pelo fator da média geométrica de dez anos."""
    rcl = decimal_nao_negativo(rcl_base, "RCL base")
    fator = decimal_nao_negativo(fator, "fator")
    if rcl == 0 or fator == 0:
        raise ValueError("RCL base e fator devem ser positivos")
    if not isinstance(ano_base, int) or isinstance(ano_base, bool):
        raise ValueError("Ano base inválido")
    if not linhas:
        raise ValueError("Informe ao menos um exercício")
    anos = set()
    saida = []
    for linha in linhas:
        ano = linha.get("ano")
        if not isinstance(ano, int) or isinstance(ano, bool) or ano <= ano_base or ano in anos:
            raise ValueError("Ano de projeção inválido ou repetido")
        anos.add(ano)
        juros = decimal_nao_negativo(linha.get("juros_encargos"), "juros e encargos")
        amortizacao = decimal_nao_negativo(linha.get("amortizacao"), "amortização")
        rcl_projetada = rcl * fator ** (ano - ano_base)
        servico = juros + amortizacao
        saida.append({
            "ano": ano, "juros_encargos": juros, "amortizacao": amortizacao,
            "servico_divida": servico, "rcl_projetada": rcl_projetada,
            "limite": rcl_projetada * LIMITE,
            "margem": rcl_projetada * LIMITE - servico,
            "percentual": servico / rcl_projetada,
        })
    return sorted(saida, key=lambda item: item["ano"])


def avaliar_hipotese(linhas_projetadas):
    if not linhas_projetadas:
        raise ValueError("Informe ao menos um exercício")
    media = sum((linha["percentual"] for linha in linhas_projetadas), Decimal(0)) / len(linhas_projetadas)
    return {
        "linhas": linhas_projetadas, "media_percentual": media,
        "limite_percentual": LIMITE,
        "aprovado": media < LIMITE,
    }


def avaliar_alternativas(primeira, segunda=None):
    """Aplica OR sequencial; a segunda hipótese só é avaliada se necessária."""
    resultado_1 = avaliar_hipotese(primeira)
    if resultado_1["aprovado"]:
        return {"aprovado": True, "hipotese_1": resultado_1, "hipotese_2": None,
                "proxima_etapa": "Divida_Consolidada"}
    if segunda is None:
        return {"aprovado": None, "hipotese_1": resultado_1, "hipotese_2": None,
                "proxima_etapa": None}
    if any(linha["ano"] > 2027 for linha in segunda):
        raise ValueError("A hipótese 2 termina em 31/12/2027")
    resultado_2 = avaliar_hipotese(segunda)
    aprovado = resultado_2["aprovado"]
    return {"aprovado": aprovado, "hipotese_1": resultado_1,
            "hipotese_2": resultado_2,
            "proxima_etapa": "Divida_Consolidada" if aprovado else None}
