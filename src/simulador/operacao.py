"""Cronograma e bases anuais compartilhados entre as avaliações da operação."""
from decimal import Decimal, localcontext
from .fluxo_tlp import montar_periodos, calcular_fluxo_tlp
from .servico_divida import projetar_rcl, decimal_nao_negativo


def calcular_operacao(entrada, *, serie_ipca, rcl_base=None, referencia_rcl=None, fator_projecao=None):
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
    taxa = decimal_nao_negativo(entrada['fator'], 'taxa anual da RCL')
    if taxa > 100:
        raise ValueError('Informe uma taxa anual da RCL entre 0 e 100%.')
    fluxo = calcular_fluxo_tlp(str(valor), entrada['data_liberacao'], entrada['prazo_meses'],
                              entrada['carencia_meses'], entrada['prefixada'], entrada['spread'],
                              serie_ipca, ipca_ausente_zero=True)
    anuais = {int(item['ano']): item for item in fluxo['anuais']}
    pagamentos = [{'ano': exercicio, 'juros_encargos': anuais.get(exercicio, {}).get('juros', '0'),
                   'amortizacao': anuais.get(exercicio, {}).get('amortizacao', '0')}
                  for exercicio in range(ano, fim + 1)]
    rcls = {}
    if rcl_base is not None:
        if not referencia_rcl or not fator_projecao:
            raise ValueError('Falta a referência da receita usada na projeção. Atualize os dados fiscais e tente novamente.')
        with localcontext() as contexto:
            contexto.prec = 50
            fator_projecao = {**fator_projecao, 'valor': str(1 + taxa / Decimal(100)),
                              'taxa_percentual': str(taxa), 'fonte': 'Parâmetro local do usuário'}
        rcls = {exercicio: str(valor) for exercicio, valor in projetar_rcl(
            rcl_base, referencia_rcl['exercicio'], referencia_rcl['periodo'],
            range(ano, fim + 1), fator_projecao).items()}
    bases = [{'ano': exercicio, 'liberacaoNovaOperacao': str(valor if exercicio == ano else Decimal(0)),
              'rclProjetada': rcls.get(exercicio)} for exercicio in range(ano, fim + 1)]
    return {'fluxo': fluxo, 'bases_fluxo': bases,
            'referencia_rcl': referencia_rcl, 'fator_projecao': fator_projecao,
            'servico_input': {'ano_fim_contrato': fim,
                              'linhas': [{**linha, 'demais_operacoes': None} for linha in pagamentos]}}
