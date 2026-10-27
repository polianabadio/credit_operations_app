"""Cronograma e bases anuais compartilhados entre as avaliações da operação."""
from decimal import Decimal
from .fluxo_tlp import montar_periodos, calcular_fluxo_tlp
from .servico_divida import projetar_anos, decimal_nao_negativo


def calcular_operacao(entrada, *, serie_ipca, rcl_base=None):
    ano, fim = int(entrada['ano']), int(entrada['fim'])
    if not 1900 <= ano <= fim <= ano + 50:
        raise ValueError('Horizonte da operação inválido.')
    if entrada.get('tipo_liberacao') != 'unica':
        raise ValueError('O cálculo das parcelas TLP exige recebimento único. Liberações em várias datas ainda não são atendidas por este modelo.')
    valor = decimal_nao_negativo(entrada['valor'], 'valor da operação')
    if valor == 0:
        raise ValueError('O valor da operação deve ser positivo.')
    periodos = montar_periodos(entrada['data_liberacao'], entrada['prazo_meses'], entrada['carencia_meses'])
    if int(entrada['data_liberacao'][:4]) != ano or periodos[-1]['fim'].year != fim:
        raise ValueError('Confira a data de recebimento, o prazo e o ano final do empréstimo.')
    fator = decimal_nao_negativo(entrada['fator'], 'fator da RCL')
    if fator == 0:
        raise ValueError('O fator da RCL deve ser positivo.')
    fluxo = calcular_fluxo_tlp(str(valor), entrada['data_liberacao'], entrada['prazo_meses'],
                              entrada['carencia_meses'], entrada['prefixada'], entrada['spread'],
                              serie_ipca, ipca_ausente_zero=True)
    anuais = {int(item['ano']): item for item in fluxo['anuais']}
    pagamentos = [{'ano': exercicio, 'juros_encargos': anuais.get(exercicio, {}).get('juros', '0'),
                   'amortizacao': anuais.get(exercicio, {}).get('amortizacao', '0')}
                  for exercicio in range(ano, fim + 1)]
    rcls = {item['ano']: str(item['rcl_projetada']) for item in
            projetar_anos(rcl_base, pagamentos, ano_base=ano - 1, fator=fator)} if rcl_base is not None else {}
    bases = [{'ano': exercicio, 'liberacaoNovaOperacao': str(valor if exercicio == ano else Decimal(0)),
              'rclProjetada': rcls.get(exercicio)} for exercicio in range(ano, fim + 1)]
    return {'fluxo': fluxo, 'bases_fluxo': bases,
            'servico_input': {'fator': str(fator), 'ano_fim_contrato': fim,
                              'hipotese_1': pagamentos, 'hipotese_2': None}}
