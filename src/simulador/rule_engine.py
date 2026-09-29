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
            return {'aprovado': True, 'dados_calculados': {'mensagem': 'Sem dados para o ano anterior.'}}

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
        
        # Retorna o resultado padronizado
        return {
            'aprovado': aprovado,
            'dados_calculados': {
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
            return {'aprovado': True, 'dados_calculados': {'mensagem': 'Sem dados para o ano corrente.'}}

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
        
        # Retorno padronizado
        return {
            'aprovado': aprovado,
            'dados_calculados': {
                'limite_disponivel': limite_disponivel,
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
    
    return {
        "nome": nome_regra.replace("_", " "), # Deixa o nome mais amigável
        "status": "Cumprida" if aprovado else "Violada",
        "descricao": info_validacao.get("descricao", "Descrição não encontrada."),
        "proximo_passo": info_validacao.get("proximo_passo", ""),
        "base_normativa": regra_info.get("base_normativa", ""),
        "objetivo": regra_info.get("objetivo", ""),
        "dados_calculados": resultado_avaliacao.get('dados_calculados', {})
    }


# --- REGISTRO DE REGRAS ---
# Este dicionário mapeia o nome da regra no YAML para a classe Python correspondente.
REGISTRY = {
    "Regra_de_Ouro_Ano_Anterior": RegraDeOuroAnoAnterior,
    "Regra_de_Ouro_Ano_Atual": RegraDeOuroAnoAtual,
}

# --- CAMADA 3: ORQUESTRAÇÃO E INTERFACE PÚBLICA ---
def analisar_operacao(ano, valor_requisitado=0.0):
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
        
        # 2. Itera sobre as etapas e regras definidas no YAML
        for etapa_nome, regras_da_etapa in modelo_regras.items():
            print(f"\n--- Processando: {etapa_nome} ---")
            for regra in regras_da_etapa:
                # O YAML tem uma lista de dicionários com uma única chave (o nome da regra)
                nome_regra_yaml = list(regra.keys())[0]
                regra_info_yaml = regra[nome_regra_yaml]

                if nome_regra_yaml == 'Divida_Consolidada':
                    resultado_dcl = avaliar_dcl(ano, obter_registros_dcl(ano))
                    if resultado_dcl is not None:
                        destino = (regras_sem_informacao if resultado_dcl['aprovado'] is None else
                                   regras_cumpridas if resultado_dcl['aprovado'] else regras_violadas)
                        destino.append(resultado_dcl)
                    continue

                if nome_regra_yaml == 'Despesa_com_Pessoal':
                    resultado_dtp = consolidar_dtp(ano, obter_registros_dtp(ano))
                    if resultado_dtp is not None:
                        if resultado_dtp['aprovado']:
                            regras_cumpridas.append(resultado_dtp)
                        else:
                            regras_violadas.append(resultado_dtp)
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
                        regras_cumpridas.append(resultado_formatado)
                        print(f"  [OK] Regra '{nome_regra_yaml}' cumprida.")
                    else:
                        regras_violadas.append(resultado_formatado)
                        print(f"  [FALHA] Regra '{nome_regra_yaml}' violada.")

                else:
                    print(f"  [AVISO] A classe para a regra '{nome_regra_yaml}' não foi implementada ou registrada.")

        return {
            "status": "Análise completa.",
            "regras_cumpridas": regras_cumpridas,
            "regras_violadas": regras_violadas,
            "regras_sem_informacao": regras_sem_informacao,
            "circuit_breaker": any(r.get('tipo') in ('dtp', 'dcl') for r in regras_violadas),
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
