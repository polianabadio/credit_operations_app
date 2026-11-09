"""Cronograma anual declarado; não infere parcelas ou taxas implícitas."""
from decimal import Decimal, localcontext
from .servico_divida import decimal_nao_negativo


def ler_cronograma(entrada):
    ano, fim = int(entrada['ano']), int(entrada['fim'])
    linhas = entrada.get('cronograma_anual')
    if not isinstance(linhas, list) or len(linhas) != fim - ano + 1:
        raise ValueError('Informe todos os anos do cronograma anual, inclusive zeros.')
    registros = {}
    with localcontext() as contexto:
        contexto.prec = 50
        for linha in linhas:
            exercicio = int(linha['ano'])
            if exercicio in registros or not ano <= exercicio <= fim:
                raise ValueError('Ano repetido ou fora do horizonte do cronograma anual.')
            valores = {}
            for chave in ('liberacao', 'amortizacao', 'juros_encargos'):
                if linha.get(chave) in (None, ''):
                    raise ValueError('Complete liberações, amortizações e encargos, inclusive zeros.')
                valor = decimal_nao_negativo(linha[chave], chave)
                if valor != valor.quantize(Decimal('.01')):
                    raise ValueError('Informe valores anuais em centavos.')
                valores[chave] = valor
            registros[exercicio] = valores
        principal = decimal_nao_negativo(entrada['valor'], 'valor da operação')
        if principal <= 0 or sum(v['liberacao'] for v in registros.values()) != principal:
            raise ValueError('A soma das liberações anuais deve corresponder ao valor da operação.')
        if sum(v['amortizacao'] for v in registros.values()) != principal:
            raise ValueError('A soma das amortizações anuais deve corresponder ao valor da operação.')
        saldo = Decimal(0)
        for exercicio in range(ano, fim + 1):
            valores = registros[exercicio]
            saldo += valores['liberacao'] - valores['amortizacao']
            if saldo < 0:
                raise ValueError('A amortização acumulada não pode superar as liberações acumuladas.')
        if registros[fim]['amortizacao'] + registros[fim]['juros_encargos'] <= 0:
            raise ValueError('O ano final deve conter o último pagamento informado.')
    return registros


def fluxo_anual(entrada):
    registros = ler_cronograma(entrada)
    with localcontext() as contexto:
        contexto.prec = 50
        juros = sum(v['juros_encargos'] for v in registros.values())
        amortizacao = sum(v['amortizacao'] for v in registros.values())
        return {'modo': 'anual_informado', 'indexador': entrada.get('indexador', 'FIXA'),
                'anuais': [{'ano': ano, 'juros': str(v['juros_encargos']), 'amortizacao': str(v['amortizacao']),
                            'total': str(v['juros_encargos'] + v['amortizacao'])} for ano, v in sorted(registros.items())],
                'juros_total': str(juros), 'amortizacao_total': str(amortizacao),
                'pagamento_total': str(juros + amortizacao), 'saldo_final': '0',
                'ano_final': int(entrada['fim']), 'linhas': [], 'estimado': False,
                'convencao': 'Valores anuais informados pelo usuário; juros, encargos e datas mensais não são reconstruídos.'}
