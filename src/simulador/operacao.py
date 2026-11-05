"""Cronograma e bases anuais compartilhados entre as avaliações da operação."""
from decimal import Decimal, localcontext
from .fluxo_tlp import montar_periodos, calcular_fluxo_tlp, inteiro
from .indexadores import NOMES, taxa_valida, memoria_taxa
from .servico_divida import projetar_rcl, decimal_nao_negativo


def normalizar_prazos(entrada):
    entrada = dict(entrada)
    if 'amortizacao_meses' in entrada:
        carencia = inteiro(entrada.get('carencia_meses'), 'Carência em meses', 0, 599)
        amortizacao = inteiro(entrada.get('amortizacao_meses'), 'Amortização em meses', 1, 600)
        total = carencia + amortizacao
        if total > 600:
            raise ValueError('A soma da carência e da amortização deve ser de no máximo 600 meses.')
        if entrada.get('prazo_meses') not in (None, '') and inteiro(entrada['prazo_meses'], 'Prazo total', 1, 600) != total:
            raise ValueError('Prazo total diferente da soma de carência e amortização.')
        entrada['prazo_meses'] = total
    return entrada


def calcular_operacao(entrada, *, serie_ipca, rcl_base=None, referencia_rcl=None, fator_projecao=None):
    entrada = normalizar_prazos(entrada)
    indexador = entrada.get('indexador', 'IPCA')
    if indexador not in NOMES:
        raise ValueError('Indexador não atendido pelo simulador.')
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
    referencia_juros = entrada.get('referencia_juros_cambial', 'FIXA') if indexador == 'CAMBIAL' else indexador
    if indexador == 'CAMBIAL' and referencia_juros not in ('FIXA', 'SOFR'):
        raise ValueError('Escolha taxa fixa ou SOFR para os juros da operação cambial.')
    taxa_indice = taxa_valida(entrada.get('taxa_indexador')) if referencia_juros in ('CDI', 'SELIC', 'SOFR', 'TLP') else Decimal(0)
    if indexador in ('IPCA', 'TLP'):
        prefixada = decimal_nao_negativo(entrada['prefixada'], 'Taxa fixa')
        if indexador == 'TLP':
            with localcontext() as contexto:
                contexto.prec = 50
                prefixada = ((1 + prefixada / 100) * (1 + taxa_indice / 100) - 1) * 100
        with localcontext() as contexto:
            if indexador == 'TLP': contexto.prec = 50
            fluxo = calcular_fluxo_tlp(str(valor), entrada['data_liberacao'], entrada['prazo_meses'],
                                      entrada['carencia_meses'], str(prefixada), entrada['spread'],
                                      serie_ipca, ipca_ausente_zero=True)
    else:
        from .fluxo_indexado import calcular_fluxo_indexado
        fluxo = calcular_fluxo_indexado(str(valor), entrada['data_liberacao'], entrada['prazo_meses'],
                                        entrada['carencia_meses'], entrada['prefixada'], entrada['spread'],
                                        referencia_juros, str(taxa_indice))
    fluxo['prazos'] = {'carencia_meses': int(entrada['carencia_meses']),
                       'amortizacao_meses': int(entrada['prazo_meses']) - int(entrada['carencia_meses']),
                       'prazo_total_meses': int(entrada['prazo_meses'])}
    fluxo['indexador'] = indexador
    fluxo['referencia_juros'] = referencia_juros
    if referencia_juros in ('CDI', 'SELIC', 'SOFR', 'TLP'):
        fluxo['taxa_indexador'] = memoria_taxa(referencia_juros, taxa_indice, entrada.get('referencia_indexador_id'))
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
