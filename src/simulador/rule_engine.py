from datetime import datetime
# Importe as novas funções de acesso a dados
from .data_access import (
    obter_dados_rreo_para_analise, 
    obter_dados_rgf_para_analise
)

from .config import carregar_modelo_yaml
from .logger import log
from .data_access import obter_registros_dtp
from .dtp import consolidar_dtp
from .dcl import avaliar_dcl
from .data_access import obter_registros_dcl
from .data_access import obter_rcl_ajustada_endividamento
from .data_access import (obter_servico_divida_exercicio_anterior,
                          CONTAS_SERVICO_DIVIDA, COLUNA_LIQUIDADA, COLUNA_RESTOS)
from .servico_divida import (avaliar_exercicio_anterior, projetar_anos,
                             avaliar_alternativas, decimal_nao_negativo)
from .parametros_simulacao import obter_fator_projecao

# --- CAMADA 2: MOTOR DE REGRAS ---

class RegraDeNegocio:
    """
    Classe base para todas as regras de negócio.
    Define um contrato que todas as regras devem seguir.
    """
    def __init__(self, ano, dados_rreo, dados_rgf, valor_requisitado=0.0):
        self.ano = ano
        self.dados_rreo = dados_rreo
        self.dados_rgf = dados_rgf
        self.valor_requisitado = valor_requisitado

    def avaliar(self):
        """
        Este método deve ser implementado por cada classe de regra filha.
        Ele executa o cálculo da regra e retorna um resultado padronizado.
        """
        raise NotImplementedError("O método 'avaliar' deve ser implementado na classe filha.")

class RegraDeOuroAnoAnterior(RegraDeNegocio):
    """
    Verifica se as operações de crédito do ano anterior foram maiores que as
    despesas de capital, conforme a Regra de Ouro.
    """
    def avaliar(self):
        # Usamos os dados do ano anterior, que já foram buscados
        ano_anterior = self.ano - 1
        dados_ano_anterior = self.dados_rreo.get(ano_anterior, {}).get('registros', [])
        
        if not dados_ano_anterior:
            # Se não há dados, não podemos avaliar. Pode ser uma aprovação padrão ou erro.
            return {'aprovado': True, 'dados_calculados': {
                'ano_analisado': ano_anterior, 'mensagem': 'Sem dados para o ano anterior.'}}

        # Define os filtros com base na lógica original
        colunas_despesa = ['DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)', 'INSCRITAS EM RESTOS A PAGAR NÃO PROCESSADOS (k)']
        contas_despesa_capital = ['AMORTIZAÇÃO DA DÍVIDA', 'INVERSÕES FINANCEIRAS', 'INVESTIMENTOS']
        
        colunas_operacao = ['Até o Bimestre (c)']
        contas_operacao_credito = ['OPERAÇÕES DE CRÉDITO']

        # Usa a função auxiliar para fazer os cálculos de forma limpa
        despesas_capital_total, despesas_capital_detalhe = _calcular_e_detalhar_soma(
            dados_ano_anterior, contas_despesa_capital, colunas_despesa
        )
        operacoes_credito_total, operacoes_credito_detalhe = _calcular_e_detalhar_soma(
            dados_ano_anterior, contas_operacao_credito, colunas_operacao
        )

        # A lógica da regra
        limite_disponivel = despesas_capital_total - operacoes_credito_total
        aprovado = limite_disponivel >= 0
        fontes = sorted({(reg.get('anexo'), reg.get('periodo')) for reg in dados_ano_anterior
                         if (reg['conta'] in contas_despesa_capital and reg['coluna'] in colunas_despesa)
                         or (reg['conta'] in contas_operacao_credito and reg['coluna'] in colunas_operacao)
                         if reg.get('anexo') and reg.get('periodo')})
        
        # Retorna o resultado padronizado
        return {
            'aprovado': aprovado,
            'dados_calculados': {
                'ano_analisado': ano_anterior,
                'fontes': [{'anexo': anexo, 'periodo': periodo} for anexo, periodo in fontes],
                'limite_disponivel': limite_disponivel,
                'despesas_capital': {
                    'total': despesas_capital_total,
                    'detalhe': despesas_capital_detalhe
                },
                'operacoes_credito': {
                    'total': operacoes_credito_total,
                    'detalhe': operacoes_credito_detalhe
                }
            }
        }
    
class RegraDeOuroAnoAtual(RegraDeNegocio):
    """
    Verifica a projeção da Regra de Ouro para o ano corrente.
    """
    def avaliar(self):
        # Desta vez, usamos os dados do ano corrente
        dados_ano_corrente = self.dados_rreo.get(self.ano, {}).get('registros', [])
        
        if not dados_ano_corrente:
            return {'aprovado': True, 'dados_calculados': {
                'ano_analisado': self.ano, 'mensagem': 'Sem dados para o ano corrente.'}}

        # Filtros para Despesas de Capital (idênticos à regra anterior)
        colunas_despesa = ['DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)', 'INSCRITAS EM RESTOS A PAGAR NÃO PROCESSADOS (k)']
        contas_despesa_capital = ['AMORTIZAÇÃO DA DÍVIDA', 'INVERSÕES FINANCEIRAS', 'INVESTIMENTOS']
        
        # Filtros para Operações de Crédito
        colunas_operacao = ['PREVISÃO ATUALIZADA (a)']
        contas_operacao_credito = ['OPERAÇÕES DE CRÉDITO']

        # Cálculos usando a função auxiliar
        despesas_capital_total, despesas_capital_detalhe = _calcular_e_detalhar_soma(
            dados_ano_corrente, contas_despesa_capital, colunas_despesa
        )
        operacoes_credito_total, operacoes_credito_detalhe = _calcular_e_detalhar_soma(
            dados_ano_corrente, contas_operacao_credito, colunas_operacao
        )

        # Lógica da regra
        limite_disponivel = despesas_capital_total - operacoes_credito_total
        aprovado = limite_disponivel >= self.valor_requisitado
        fontes = sorted({(reg.get('anexo'), reg.get('periodo')) for reg in dados_ano_corrente
                         if (reg['conta'] in contas_despesa_capital and reg['coluna'] in colunas_despesa)
                         or (reg['conta'] in contas_operacao_credito and reg['coluna'] in colunas_operacao)
                         if reg.get('anexo') and reg.get('periodo')})
        
        # Retorno padronizado
        return {
            'aprovado': aprovado,
            'dados_calculados': {
                'ano_analisado': self.ano,
                'fontes': [{'anexo': anexo, 'periodo': periodo} for anexo, periodo in fontes],
                'limite_disponivel': limite_disponivel,
                'margem_apos_operacao': limite_disponivel - self.valor_requisitado,
                'receitas_totais_consideradas': operacoes_credito_total + self.valor_requisitado,
                'valor_requisitado_na_analise': self.valor_requisitado,
                'despesas_capital': {
                    'total': despesas_capital_total,
                    'detalhe': despesas_capital_detalhe
                },
                'operacoes_credito': {
                    'total': operacoes_credito_total,
                    'detalhe': operacoes_credito_detalhe
                }
            }
        }

class RegraDoDispendio115RCL(RegraDeNegocio):
    """
    Verifica a projeção da Regra de Ouro para o ano corrente.
    """
    def avaliar(self):
        # Desta vez, usamos os dados do ano corrente
       
        
        # Retorno padronizado
        return {
            'aprovado': 0,
            'dados_calculados': {
                'limite_disponivel': 0,
                'valor_requisitado_na_analise': self.valor_requisitado,
                'despesas_capital': {
                    'total': 0,
                    'detalhe': 0
                },
                'operacoes_credito': {
                    'total': 0,
                    'detalhe': 0
                }
            }
        }


# --- FUNÇÕES AUXILIARES DO MOTOR DE REGRAS ---
def _calcular_e_detalhar_soma(registros: list, filtros_conta: list, filtros_coluna: list):
    """
    Função auxiliar que calcula a soma E detalha os componentes dessa soma.

    Retorna uma tupla contendo: (soma_total, dicionario_com_detalhes)
    """
    soma = 0.0
    detalhes = {conta: 0.0 for conta in filtros_conta} # Inicializa o dicionário de detalhes

    for reg in registros:
        # Verifica se o registro corresponde aos filtros de conta e coluna
        if reg['conta'] in filtros_conta and reg['coluna'] in filtros_coluna:
            valor_reg = reg['valor']
            soma += valor_reg
            # Acumula o valor para a conta específica no dicionário de detalhes
            detalhes[reg['conta']] += valor_reg
            
    return soma, detalhes

def _formatar_resultado_regra(nome_regra, regra_info, resultado_avaliacao):
    """
    Formata o dicionário de saída para uma regra, combinando os dados do YAML
    com os resultados calculados pelo motor de regras.
    """
    aprovado = resultado_avaliacao.get('aprovado', False)
    info_validacao = regra_info.get("validacao", {}).get(aprovado, {})
    
    resultado = {
        "nome": nome_regra.replace("_", " "), # Deixa o nome mais amigável
        "status": "Cumprida" if aprovado else "Violada",
        "descricao": info_validacao.get("descricao", "Descrição não encontrada."),
        "proximo_passo": info_validacao.get("proximo_passo", ""),
        "base_normativa": regra_info.get("base_normativa", ""),
        "objetivo": regra_info.get("objetivo", ""),
        "dados_calculados": resultado_avaliacao.get('dados_calculados', {})
    }
    if nome_regra == 'Regra_de_Ouro_Ano_Anterior':
        resultado['tipo'] = 'regra_ouro_anterior'
        resultado['nome'] = 'Regra de Ouro — Exercício Anterior'
    elif nome_regra == 'Regra_de_Ouro_Ano_Atual':
        resultado['tipo'] = 'regra_ouro_atual'
        resultado['nome'] = 'Regra de Ouro — Exercício Atual'
    return resultado


# --- REGISTRO DE REGRAS ---
# Este dicionário mapeia o nome da regra no YAML para a classe Python correspondente.
REGISTRY = {
    "Regra_de_Ouro_Ano_Anterior": RegraDeOuroAnoAnterior,
    "Regra_de_Ouro_Ano_Atual": RegraDeOuroAnoAtual,
}

# Ordem visual independente da etapa de cálculo e do status de cada regra.
ORDEM_EXIBICAO = {
    'regra_ouro_anterior': 0,
    'regra_ouro_atual': 1,
    'dtp': 2,
    'servico_divida': 3,
    'dcl': 4,
}

# --- CAMADA 3: ORQUESTRAÇÃO E INTERFACE PÚBLICA ---
def _resultado_servico_divida(ano, entrada=None):
    """Compõe a memória da regra sem aprovar quando faltarem lançamentos."""
    rcl_historica = obter_rcl_ajustada_endividamento(ano - 1)
    despesas = obter_servico_divida_exercicio_anterior(ano - 1)
    rcl_atual = obter_rcl_ajustada_endividamento(ano)
    despesas_referencia = obter_servico_divida_exercicio_anterior(ano)
    if entrada is not None and not isinstance(entrada, dict):
        raise ValueError('Dados da regra inválidos')
    dados = {
        'ano_historico': ano - 1, 'periodo_historico': despesas['periodo'] if despesas else None,
        'rcl_historica': float(rcl_historica['valor']) if rcl_historica else None,
        'periodo_rcl_historica': rcl_historica['periodo'] if rcl_historica else None,
        'rcl_atual': float(rcl_atual['valor']) if rcl_atual else None,
        'periodo_rcl_atual': rcl_atual['periodo'] if rcl_atual else None,
        'ano_atual': ano,
    }
    if despesas_referencia:
        referencia_juros = despesas_referencia['contas'][CONTAS_SERVICO_DIVIDA[0]]
        referencia_amortizacao = despesas_referencia['contas'][CONTAS_SERVICO_DIVIDA[1]]
        dados['referencia_rreo_atual'] = {
            'ano': ano, 'periodo': despesas_referencia['periodo'],
            'juros_encargos': str(referencia_juros[COLUNA_LIQUIDADA] +
                                  (referencia_juros[COLUNA_RESTOS] or 0)),
            'amortizacao': str(referencia_amortizacao[COLUNA_LIQUIDADA] +
                                (referencia_amortizacao[COLUNA_RESTOS] or 0)),
            'origem': 'SICONFI/RREO-Anexo 01',
        }
    base = {'tipo': 'servico_divida', 'nome': 'Projeção do Serviço da Dívida',
            'dados_calculados': dados}
    def pendente(motivo):
        return {**base, 'aprovado': None, 'status': 'Sem informação', 'descricao': motivo}
    if not rcl_historica or not despesas:
        return pendente('Faltam dados do último RREO do exercício anterior para avaliar o serviço da dívida.')
    if rcl_historica['periodo'] != despesas['periodo']:
        return pendente('RCL e despesas do exercício anterior pertencem a bimestres diferentes.')
    juros = despesas['contas'][CONTAS_SERVICO_DIVIDA[0]]
    amortizacao = despesas['contas'][CONTAS_SERVICO_DIVIDA[1]]
    historico = avaliar_exercicio_anterior(
        rcl_historica['valor'], juros[COLUNA_LIQUIDADA], amortizacao[COLUNA_LIQUIDADA],
        juros[COLUNA_RESTOS], amortizacao[COLUNA_RESTOS])
    dados['historico'] = {chave: float(valor) for chave, valor in historico.items()
                          if chave != 'aprovado'}
    dados['historico']['aprovado'] = historico['aprovado']
    dados['memoria_exata'] = {
        'rcl_historica': str(rcl_historica['valor']),
        'juros_liquidados': str(juros[COLUNA_LIQUIDADA]),
        'amortizacao_liquidada': str(amortizacao[COLUNA_LIQUIDADA]),
        'restos_juros': str(juros[COLUNA_RESTOS] or 0),
        'restos_amortizacao': str(amortizacao[COLUNA_RESTOS] or 0),
        'servico_historico': str(historico['servico_divida']),
        'limite_historico': str(historico['limite']),
        'comparacao_historica': '<',
    }
    if not historico['aprovado']:
        return {**base, 'aprovado': False, 'status': 'Violada',
                'descricao': 'Serviço da Dívida do ano anterior é superior ou igual a 11,5% da RCL do exercício.'}
    if not rcl_atual:
        return pendente('Exercício anterior aprovado; falta a RCL atual para projetar os exercícios futuros.')
    fator = decimal_nao_negativo((entrada or {}).get('fator', obter_fator_projecao()),
                                 'fator de projeção')
    if fator == 0:
        raise ValueError('Fator de projeção deve ser positivo')
    dados['fator'] = str(fator)
    if not entrada or not entrada.get('hipotese_1'):
        return pendente('Exercício anterior aprovado. Preencha o fluxo da operação pretendida.')
    fim = entrada.get('ano_fim_contrato')
    if not isinstance(fim, int) or isinstance(fim, bool) or not ano <= fim <= ano + 50:
        raise ValueError('Ano de fim do contrato inválido')
    anos_esperados = set(range(ano, fim + 1))
    linhas_1 = entrada['hipotese_1']
    if not isinstance(linhas_1, list) or {r.get('ano') for r in linhas_1} != anos_esperados or len(linhas_1) != len(anos_esperados):
        raise ValueError('A Hipótese 1 deve conter todos os anos do contrato, sem repetição')
    primeira = projetar_anos(rcl_atual['valor'], linhas_1, ano_base=ano - 1, fator=fator)
    futuro = avaliar_alternativas(primeira)
    def memoria_hipotese(resultado):
        if resultado is None:
            return None
        return {'aprovado': resultado['aprovado'],
                'media_percentual': float(resultado['media_percentual'] * 100),
                'linhas': [{chave: float(valor) if chave != 'ano' else valor
                            for chave, valor in linha.items()} for linha in resultado['linhas']]}
    if futuro['aprovado'] is None and ano > 2027:
        dados['hipotese_1'] = memoria_hipotese(futuro['hipotese_1'])
        return {**base, 'aprovado': False, 'status': 'Violada',
                'descricao': 'Hipótese 1 reprovada; o período alternativo até 2027 não se aplica.'}
    segunda = None
    if futuro['aprovado'] is None and entrada.get('hipotese_2'):
        linhas_2 = entrada['hipotese_2']
        if not isinstance(linhas_2, list) or any(not isinstance(r.get('ano'), int) or
                not ano <= r['ano'] <= 2027 for r in linhas_2):
            raise ValueError('A Hipótese 2 aceita somente exercícios até 2027')
        if any(r.get('juros_encargos') is None or r.get('amortizacao') is None for r in linhas_2):
            dados['hipotese_1'] = memoria_hipotese(futuro['hipotese_1'])
            return pendente('Hipótese 1 reprovada. Complete os lançamentos da Hipótese 2.')
        segunda = projetar_anos(rcl_atual['valor'], linhas_2, ano_base=ano - 1, fator=fator)
        futuro = avaliar_alternativas(primeira, segunda)
    dados['hipotese_1'] = memoria_hipotese(futuro['hipotese_1'])
    dados['hipotese_2'] = memoria_hipotese(futuro['hipotese_2'])
    for indice, memoria in ((1, futuro['hipotese_1']), (2, futuro['hipotese_2'])):
        if memoria:
            dados['memoria_exata'][f'hipotese_{indice}'] = {
                'media': str(memoria['media_percentual']),
                'linhas': [{chave: str(valor) for chave, valor in linha.items()}
                           for linha in memoria['linhas']],
            }
    if futuro['aprovado'] is None:
        return pendente('Hipótese 1 reprovada. Preencha a Hipótese 2 até dezembro de 2027.')
    return {**base, 'aprovado': futuro['aprovado'],
            'status': 'Cumprida' if futuro['aprovado'] else 'Violada',
            'descricao': ('Uma das hipóteses ficou abaixo de 11,5%; prosseguir para Dívida Consolidada.'
                          if futuro['aprovado'] else 'As duas hipóteses atingiram ou ultrapassaram 11,5%.')}


def analisar_operacao(ano, valor_requisitado=0.0, servico_input=None):
    """
    Orquestra a análise de uma operação de crédito.
    (Versão Refatorada)
    """
    try:
        if not ano:
            ano = datetime.now().year
        
        # --- CAMADA 1: ACESSO A DADOS ---
        # 1. Carrega o modelo de regras e os dados do banco
        modelo_regras = carregar_modelo_yaml()
        dados_rreo = obter_dados_rreo_para_analise(ano)
        dados_rgf = obter_dados_rgf_para_analise(ano)

        # Linha de debug opcional
        {"""print("\n--- DADOS COLETADOS ---")
        print(f"Dados RREO para {ano}: {len(dados_rreo[ano]['registros'])} registros")
        print(f"Dados RREO para {ano-1}: {len(dados_rreo[ano-1]['registros'])} registros")
        print(f"Dados RGF para {ano}: {len(dados_rgf[ano]['registros'])} registros")
        print(f"Dados RGF para {ano-1}: {len(dados_rgf[ano-1]['registros'])} registros")
        print("-----------------------\n")"""}

        regras_cumpridas = []
        regras_violadas = []
        regras_sem_informacao = []
        regras_ordenadas = []
        servico_divida_aprovado = None
        servico_divida_avaliado = False

        def adicionar_resultado(resultado, destino):
            destino.append(resultado)
            regras_ordenadas.append(resultado)
        
        # 2. Itera sobre as etapas e regras definidas no YAML
        for etapa_nome, regras_da_etapa in modelo_regras.items():
            print(f"\n--- Processando: {etapa_nome} ---")
            for regra in regras_da_etapa:
                # O YAML tem uma lista de dicionários com uma única chave (o nome da regra)
                nome_regra_yaml = list(regra.keys())[0]
                regra_info_yaml = regra[nome_regra_yaml]

                if nome_regra_yaml in ('Regra_do_Dispendio_115_RCL_Estimada',
                                       'Regra_do_Servico_da_Divida_115_RCL_Estimada'):
                    try:
                        resultado_servico = _resultado_servico_divida(ano, servico_input)
                    except ValueError as exc:
                        try:
                            resultado_servico = _resultado_servico_divida(ano)
                        except ValueError:
                            resultado_servico = {
                                'tipo': 'servico_divida',
                                'nome': 'Projeção do Serviço da Dívida',
                                'dados_calculados': {'ano_historico': ano - 1, 'ano_atual': ano},
                            }
                        resultado_servico.update(status='Sem informação', aprovado=None,
                                                 descricao=f'Dados inválidos ou ambíguos: {exc}')
                    resultado_servico['base_normativa'] = regra_info_yaml.get('base_normativa', '')
                    destino = (regras_sem_informacao if resultado_servico['aprovado'] is None else
                               regras_cumpridas if resultado_servico['aprovado'] else regras_violadas)
                    adicionar_resultado(resultado_servico, destino)
                    servico_divida_aprovado = resultado_servico['aprovado']
                    servico_divida_avaliado = True
                    log.info('Regra do Serviço da Dívida avaliada.',
                             modulo='rule_engine.py', funcao='analisar_operacao',
                             ano=ano, status=resultado_servico['status'])
                    continue

                if nome_regra_yaml == 'Divida_Consolidada':
                    if servico_divida_avaliado and servico_divida_aprovado is not True:
                        continue
                    resultado_dcl = avaliar_dcl(ano, obter_registros_dcl(ano))
                    if resultado_dcl is not None:
                        destino = (regras_sem_informacao if resultado_dcl['aprovado'] is None else
                                   regras_cumpridas if resultado_dcl['aprovado'] else regras_violadas)
                        adicionar_resultado(resultado_dcl, destino)
                    continue

                if nome_regra_yaml == 'Despesa_com_Pessoal':
                    resultado_dtp = consolidar_dtp(ano, obter_registros_dtp(ano))
                    if resultado_dtp is not None:
                        if resultado_dtp['aprovado']:
                            adicionar_resultado(resultado_dtp, regras_cumpridas)
                        else:
                            adicionar_resultado(resultado_dtp, regras_violadas)
                    continue

                # 3. Encontra a classe correspondente no nosso Registro
                ClasseDaRegra = REGISTRY.get(nome_regra_yaml)

                if ClasseDaRegra:
                    # 4. Instancia, avalia e formata o resultado
                    log.info(f"Avaliando regra: '{nome_regra_yaml}'", modulo="rule_engine.py", funcao="analisar_operacao", etapa=etapa_nome)
                    instancia_regra = ClasseDaRegra(ano, dados_rreo, dados_rgf, valor_requisitado)
                    resultado_avaliacao = instancia_regra.avaliar()
                    log.debug(f"Resultado da avaliação: {'Aprovado' if resultado_avaliacao['aprovado'] else 'Reprovado'}", modulo="rule_engine.py", funcao="analisar_operacao", regra=nome_regra_yaml, dados_brutos=resultado_avaliacao)
                    resultado_formatado = _formatar_resultado_regra(
                        nome_regra_yaml, regra_info_yaml, resultado_avaliacao
                    )
                    
                    # 5. Adiciona o resultado à lista correta
                    if resultado_avaliacao['aprovado']:
                        adicionar_resultado(resultado_formatado, regras_cumpridas)
                        print(f"  [OK] Regra '{nome_regra_yaml}' cumprida.")
                    else:
                        adicionar_resultado(resultado_formatado, regras_violadas)
                        print(f"  [FALHA] Regra '{nome_regra_yaml}' violada.")

                else:
                    print(f"  [AVISO] A classe para a regra '{nome_regra_yaml}' não foi implementada ou registrada.")

        regras_ordenadas.sort(key=lambda regra: ORDEM_EXIBICAO.get(regra.get('tipo'), len(ORDEM_EXIBICAO)))
        return {
            "status": "Análise completa.",
            "regras_cumpridas": regras_cumpridas,
            "regras_violadas": regras_violadas,
            "regras_sem_informacao": regras_sem_informacao,
            "regras_ordenadas": regras_ordenadas,
            "circuit_breaker": any(r.get('tipo') in ('dtp', 'dcl', 'servico_divida') for r in regras_violadas),
            # outros dados globais se o frontend precisar
        }
    except Exception as e:
        log.critical(f"Erro fatal na análise da operação: {e}")
        return {"status": f"Erro: {e}", "regras_cumpridas": [], "regras_violadas": []}

# Configuração para rodar o script diretamente

from .config import configurar_banco_dados

if __name__ == "__main__":
    if not configurar_banco_dados():
        print("Falha na configuração do banco de dados.")
        exit(1)

    # Teste rápido
    resultado = analisar_operacao(2025, 50000.0)
    print(resultado)
