"""
Aplicação Principal - Simulador de Operações de Crédito v2

Este é o arquivo principal da aplicação. Atua como a "ponte" entre o
backend (motor de regras, acesso a dados) e o frontend (JavaScript/Eel).
"""

import eel
from src.simulador.sync_job import iniciar_atualizacao, status_atualizacao


@eel.expose
def iniciar_atualizacao_siconfi():
    return iniciar_atualizacao()


@eel.expose
def status_atualizacao_siconfi():
    return status_atualizacao()

# Módulos da nossa arquitetura
from src.simulador.rule_engine import analisar_operacao
from src.simulador.parametros_simulacao import obter_fator_projecao, salvar_fator_projecao, obter_taxa_salva
from src.simulador.painel_fiscal import obter_painel_fiscal
from src.simulador.margem_publica import obter_margem_publica
from src.simulador.mga_projection import obter_projecao
from src.simulador.sadipem import obter_comprometimento_goias, simular_fluxo_goias
from src.simulador.data_updater import atualizar_operacoes_rreo, atualizar_operacoes_rgf
from src.simulador.database_models import db, RREO
from src.simulador.logger import log
from src.simulador.mensagens import mensagem_erro
from src.simulador.monitoring import get_system_status

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

# Módulos de configuração
from src.simulador.config import (
    EEL_WEB_FOLDER, EEL_SIZE, EEL_POSITION, APP_NAME, APP_VERSION, get_asset_path, 
    criar_diretorios, configurar_banco_dados, config_manager
) 

# --- CONFIGURAÇÃO INICIAL DA APLICAÇÃO ---

criar_diretorios()

if not configurar_banco_dados():
    log.error("Falha na configuração do banco de dados. Encerrando aplicação.")
    exit(1)

# ========== FUNÇÕES DE CONFIGURAÇÃO EXPOSTAS ==========

@eel.expose
def get_db_config():
    """Retorna a configuração atual do banco de dados para o frontend."""
    log.info("Frontend solicitou a configuração atual do banco de dados.", modulo="app.py")
    return config_manager.get_db_config()

@eel.expose
def save_db_config(config_data: dict):
    """Salva a nova configuração do banco de dados recebida do frontend."""
    try:
        log.info("Recebida nova configuração de banco de dados para salvar.", modulo="app.py")
        config_manager.set_db_config(config_data)
        log.success("Configuração do banco de dados salva com sucesso. É necessário reiniciar a aplicação.")
        # É importante notar que a aplicação precisará ser reiniciada para usar a nova conexão.
        return {'status': 'sucesso', 'mensagem': 'Configuração salva. Reinicie a aplicação para aplicá-la.'}
    except Exception as e:
        log.error("Falha ao salvar a configuração do banco de dados.", details=str(e))
        return {'status': 'erro', 'mensagem': mensagem_erro(e)}

@eel.expose
def test_db_connection(config_data: dict):
    """Testa uma conexão de banco de dados com as configurações fornecidas."""
    log.info("Testando conexão com o banco de dados...", modulo="app.py")
    try:
        # Lógica para construir a URL de teste (similar a get_db_engine_url)
        db_type = config_data.get('type', 'sqlite')
        if db_type == 'sqlite':
            test_url = f"sqlite:///{get_asset_path(config_data.get('path'))}"
        elif db_type == 'postgresql':
            user = config_data.get('user', '')
            password = config_data.get('password', '')
            host = config_data.get('host', 'localhost')
            port = config_data.get('port', '5432')
            name = config_data.get('name', 'postgres')
            test_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
        elif db_type == 'mysql':
            user = config_data.get('user', 'root')
            password = config_data.get('password', '')
            host = config_data.get('host', 'localhost')
            port = config_data.get('port', '3306')
            name = config_data.get('name', 'mysql')
            test_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"
        # lógica para outros bancos +++
        else:
            raise ValueError(f"Tipo de banco de dados '{db_type}' desconhecido para teste.")
        
        log.info("Configuração de teste preparada.", modulo="app.py")
        engine = create_engine(test_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        
        log.success("Teste de conexão bem-sucedido.")
        return {'status': 'sucesso', 'mensagem': 'Conexão bem-sucedida!'}
    except OperationalError as oe:
        log.warning("Teste de conexão falhou (OperationalError). Verifique as credenciais, host, porta e nome do banco.", details=str(oe.orig))
        return {'status': 'erro', 'mensagem': f'Falha na conexão: Verifique as credenciais, host, porta e nome do banco.'}
    except Exception as e:
        log.error("Teste de conexão falhou (Exception).", details=str(e))
        return {'status': 'erro', 'mensagem': 'Não foi possível acessar o banco de dados. Confira as configurações de acesso e tente novamente.'}

# ========== FUNÇÃO DE MONITORAMENTO EXPOSTA ==========

@eel.expose
def get_system_status_py():
    """
    Retorna um snapshot do status do sistema (BD, Recursos) para o frontend.
    """
    # Não precisamos logar aqui, pois a chamada será muito frequente (a cada X segundos)
    # Apenas logamos erros dentro do próprio módulo de monitoring.
    return get_system_status()

# ========== FUNÇÕES EXPOSTAS PARA O FRONTEND (API INTERNA) ==========

@eel.expose
def obter_dados_iniciais():
    """
    Busca informações iniciais para popular o frontend, como a lista de anos
    disponíveis para análise no banco de dados.
    """
    try:
        log.info("Buscando dados iniciais para o frontend.", modulo="app.py", funcao="obter_dados_iniciais")
        # Busca todos os anos distintos presentes na tabela RREO
        anos_query = db.session.query(RREO.exercicio).distinct().order_by(RREO.exercicio.desc()).all()
        anos_disponiveis = [ano[0] for ano in anos_query]
        log.success(f"Anos disponíveis encontrados: {len(anos_disponiveis)}, Primeiro ano: {(anos_disponiveis[-1:])}, Último ano: {(anos_disponiveis[:1])}", modulo="app.py", funcao="obter_dados_iniciais", anos=anos_disponiveis)
        
        return {
            "status": "sucesso",
            "anos_disponiveis": anos_disponiveis
        }
    except Exception as e:
        log.error(f"Erro ao obter dados iniciais: {e}")
        return {"status": "erro", "mensagem": mensagem_erro(e), "anos_disponiveis": []}

@eel.expose
def obter_fator_projecao_py():
    return str(obter_taxa_salva())


@eel.expose
def obter_painel_fiscal_py():
    try:
        painel = obter_painel_fiscal()
        if painel.get('exercicio') is not None:
            painel['fluxo_credito'] = obter_projecao(painel)
        return {'status': 'sucesso', 'painel': painel}
    except Exception as exc:
        log.error('Erro ao obter painel fiscal.', details=str(exc), modulo='app.py')
        return {'status': 'erro', 'mensagem': 'Não foi possível carregar o painel fiscal.'}


@eel.expose
def obter_comprometimento_sadipem_py():
    """Compõe a referência pública do Dashboard; o cliente HTTP mantém cache."""
    painel = obter_painel_fiscal()
    ano = painel.get('exercicio')
    if ano is None:
        return {'status': 'erro', 'mensagem': 'Exercício fiscal não disponível.'}
    painel['fluxo_credito'] = obter_projecao(painel)
    rcl = painel.get('rcl') or {}
    sadipem = obter_comprometimento_goias(ano, rcl.get('valor'))
    margem = obter_margem_publica(painel.get('fluxo_credito') or {}, sadipem)
    return {'status': 'sucesso', 'sadipem': sadipem, 'margemPublica': margem}


def _calcular_operacao_compartilhada(entrada):
    from src.simulador.operacao import calcular_operacao
    from src.simulador.fluxo_tlp import montar_periodos
    from src.simulador.indices_publicos import obter_serie_ipca
    from src.simulador.data_access import obter_rcl_caed
    from datetime import datetime, date
    periodos = montar_periodos(entrada['data_liberacao'], entrada['prazo_meses'], entrada['carencia_meses'])
    referencia = entrada.get('data_referencia') or date.today().isoformat()
    rcl = obter_rcl_caed(int(entrada['ano']), referencia)
    fator = obter_fator_projecao(referencia)
    dados = calcular_operacao(entrada, serie_ipca=obter_serie_ipca(periodos[0]['competencia_ipca']),
                              rcl_base=rcl['valor'] if rcl else None, referencia_rcl=rcl, fator_projecao=fator)
    dados['servico_input']['data_referencia'] = referencia
    from src.simulador.caed_publico import obter_pagamentos_caed, integrar_pagamentos_caed, obter_confirmacao
    pagamentos = obter_pagamentos_caed(int(entrada['ano']), int(entrada['fim']), referencia)
    dados['servico_input'] = integrar_pagamentos_caed(dados['servico_input'], pagamentos)
    confirmacao = obter_confirmacao(pagamentos, int(entrada['ano']), int(entrada['fim']))
    if confirmacao:
        dados['servico_input']['cobertura_demais'] = confirmacao
    dados['fluxo']['fonte_ipca'] = 'IBGE / Banco Central, série 433'
    dados['fluxo']['consultado_em'] = datetime.now().isoformat(timespec='seconds')
    return dados


@eel.expose
def avaliar_operacao_completa_py(entrada):
    try:
        dados = _calcular_operacao_compartilhada(entrada)
        dados['analise'] = analisar_operacao(int(entrada['ano']), float(dados['bases_fluxo'][0]['liberacaoNovaOperacao']), dados['servico_input'])
        return {'status': 'sucesso', 'resultado': dados}
    except Exception as exc:
        log.error('Erro no cálculo compartilhado da operação.', details=str(exc))
        log.error('Ação não concluída.', details=str(exc), modulo='app.py')
        return {'status': 'erro', 'mensagem': mensagem_erro(exc)}


@eel.expose
def simular_fluxo_credito_py(linhas):
    try:
        if isinstance(linhas, dict):
            dados = _calcular_operacao_compartilhada(linhas['operacao'])
            complementos = {int(item['ano']): item for item in linhas.get('complementos', [])}
            linhas = [{**item, 'liberacoesNaoContratadasManual': complementos.get(item['ano'], {}).get('liberacoesNaoContratadasManual')}
                      for item in dados['bases_fluxo']]

        return {'status': 'sucesso', 'exercicios': simular_fluxo_goias(linhas)}
    except (ValueError, KeyError, TypeError) as exc:
        log.error('Ação não concluída.', details=str(exc), modulo='app.py')
        return {'status': 'erro', 'mensagem': mensagem_erro(exc)}


@eel.expose
def salvar_fator_projecao_py(valor):
    try:
        return {'status': 'sucesso', 'fator': salvar_fator_projecao(valor)}
    except ValueError as exc:
        log.error('Ação não concluída.', details=str(exc), modulo='app.py')
        return {'status': 'erro', 'mensagem': mensagem_erro(exc)}


@eel.expose
def consultar_ipca_py(mes):
    from src.simulador.indices_publicos import consultar_ipca
    try:
        return {'status': 'sucesso', 'resultado': consultar_ipca(mes)}
    except ValueError as exc:
        log.error('Ação não concluída.', details=str(exc), modulo='app.py')
        return {'status': 'erro', 'mensagem': mensagem_erro(exc)}
    except Exception:
        return {'status': 'erro', 'mensagem': 'Não foi possível consultar o Banco Central agora. Tente novamente ou informe o índice e confira sua fonte.'}


@eel.expose
def calcular_fluxo_tlp_py(entrada):
    from src.simulador.fluxo_tlp import montar_periodos, calcular_fluxo_tlp
    from src.simulador.indices_publicos import obter_serie_ipca
    from datetime import datetime
    try:
        periodos = montar_periodos(entrada['data_liberacao'], entrada['prazo_meses'], entrada['carencia_meses'])
        if int(entrada['ano']) != int(entrada['data_liberacao'][:4]):
            raise ValueError('A data de recebimento deve pertencer ao ano informado nos dados do empréstimo.')
        if periodos[-1]['fim'].year != int(entrada['ano_final']):
            raise ValueError(f"O prazo termina em {periodos[-1]['fim'].year}. Confira o prazo ou o ano final nos dados do empréstimo.")
        serie = obter_serie_ipca(periodos[0]['competencia_ipca'])
        resultado = calcular_fluxo_tlp(entrada['valor'], entrada['data_liberacao'],
                                      entrada['prazo_meses'], entrada['carencia_meses'],
                                      entrada['prefixada'], entrada['spread'], serie,
                                      ipca_ausente_zero=True)
        resultado['fonte_ipca'] = 'IBGE / Banco Central, série 433'
        resultado['consultado_em'] = datetime.now().isoformat(timespec='seconds')
        return {'status': 'sucesso', 'resultado': resultado}
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        log.error('Ação não concluída.', details=str(exc), modulo='app.py')
        return {'status': 'erro', 'mensagem': mensagem_erro(exc)}
    except Exception:
        return {'status': 'erro', 'mensagem': 'Não foi possível obter a inflação publicada. Tente novamente. O cálculo não utilizou índices iguais a zero para preencher dados ausentes.'}


@eel.expose
def avaliar_encargos_tlp_py(entrada):
    """Avaliação adicional, independente do motor das regras fiscais existentes."""
    from src.simulador.encargos import calcular_encargos
    try:
        return {'status': 'sucesso', 'resultado': calcular_encargos(**entrada)}
    except (ValueError, TypeError, ArithmeticError) as exc:
        log.error('Ação não concluída.', details=str(exc), modulo='app.py')
        return {'status': 'erro', 'mensagem': mensagem_erro(exc)}


@eel.expose
def analisar_operacao_py(ano: int, valor_requisitado: float, servico_input=None):
    """
    Ponto de entrada principal para executar o motor de regras e retornar a análise completa.
    """
    try:
        log.info("Recebido pedido de análise do frontend.", modulo="app.py", funcao="analisar_operacao_py", ano=ano, valor_requisitado=valor_requisitado)
        # Esta chamada agora invoca nosso orquestrador inteligente
        resultado = analisar_operacao(ano, valor_requisitado, servico_input)
        log.success("Análise via orquestrador concluída com sucesso.")
        return resultado
    except Exception as e:
        log.error("Erro ao executar 'analisar_operacao'", details=str(e), modulo="app.py", funcao="analisar_operacao_py", traceback=True)
        return {"status": "erro", "mensagem": 'Não foi possível concluir a análise. Tente novamente. Se continuar, peça ajuda à equipe responsável pelo aplicativo.'}

@eel.expose
def atualizar_rreo_py(status='all'):
    """
    Dispara a rotina de atualização dos dados do RREO a partir da API do Siconfi.
    """
    try:
        log.info(f"Disparando atualização RREO.", modulo="app.py", funcao="atualizar_rreo_py", status=status)
        resultado = atualizar_operacoes_rreo(status)
        registrar = log.error if resultado['status'] == 'error' else log.warning if resultado['status'] == 'warning' else log.success
        registrar(resultado['message'], modulo="app.py", funcao="atualizar_rreo_py", status=status)
        return resultado
    except Exception as e:
        log.error(f"Erro na atualização RREO:", details=str(e), modulo="app.py", funcao="atualizar_rreo_py", traceback=True)
        return {"message": 'Não foi possível atualizar os dados agora. Verifique a conexão e tente novamente mais tarde.', "status": "error"}

@eel.expose
def atualizar_rgf_py(status='all'):
    """
    Dispara a rotina de atualização dos dados do RGF a partir da API do Siconfi.
    """
    try:
        log.info(f"Disparando atualização RGF.", modulo="app.py", funcao="atualizar_rgf_py", status=status)
        resultado = atualizar_operacoes_rgf(status)
        registrar = log.error if resultado['status'] == 'error' else log.warning if resultado['status'] == 'warning' else log.success
        registrar(resultado['message'], modulo="app.py", funcao="atualizar_rgf_py", status=status)
        return resultado
    except Exception as e:
        log.error(f"Erro na atualização RGF:", details=str(e), modulo="app.py", funcao="atualizar_rgf_py", traceback=True)
        return {"message": 'Não foi possível atualizar os dados agora. Verifique a conexão e tente novamente mais tarde.', "status": "error"}

@eel.expose
def obter_info_app():
    """
    Retorna informações básicas sobre a aplicação.
    """
    return { "nome": APP_NAME, "versao": APP_VERSION }


def main():
    """Função principal para inicializar a aplicação Eel."""
    try:
        eel.init(str(EEL_WEB_FOLDER))
        log.info(f"Aplicação '{APP_NAME} v{APP_VERSION}' iniciando...")
        # Porta livre por instância; tolera perdas breves da conexão com a janela.
        eel.start('main.html', size=EEL_SIZE, position=EEL_POSITION,
                  port=0, shutdown_delay=60.0)
    except Exception as e:
        log.critical(f"Não foi possível iniciar a aplicação Eel:", details=str(e), modulo="app.py", funcao="main", traceback=True)

if __name__ == '__main__':
    main()
