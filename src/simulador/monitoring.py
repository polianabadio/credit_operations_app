# src/simulador/monitoring.py
"""
Módulo de Monitoramento do Sistema.

Fornece funções para verificar o status dos serviços (como o BD)
e o uso de recursos do sistema (CPU, Memória).
"""

import psutil
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from .config import config_manager
from .logger import log

# Obtém o processo atual da aplicação
processo_atual = psutil.Process(os.getpid())

def check_database_connection():
    """
    Verifica ativamente a conexão com o banco de dados configurado.
    Retorna um dicionário com o status.
    """
    try:
        # Pega a URL de conexão atual
        url = config_manager.get_db_engine_url()
        engine = create_engine(url)
        
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        
        return {
            "status": "Online",
            "mensagem": "Conexão com o banco de dados bem-sucedida."
        }
    except OperationalError as oe:
        log.warning("Monitoramento: Falha na conexão com o banco de dados.", details=str(oe.orig))
        return {
            "status": "Offline",
            "mensagem": "Falha na conexão. Verifique as configurações ou o status do servidor."
        }
    except Exception as e:
        log.error("Monitoramento: Erro inesperado ao verificar o banco de dados.", details=str(e))
        return {
            "status": "Erro",
            "mensagem": "Não foi possível verificar o acesso aos dados. Confira as configurações do banco e tente novamente."
        }

def get_resource_usage():
    """
    Obtém o uso de CPU e Memória do processo atual da aplicação.
    """
    try:
        # Uso de Memória
        mem_info = processo_atual.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)  # Converte de bytes para Megabytes
        
        # Uso de CPU
        # O primeiro chamado de cpu_percent(interval=None) retorna 0.0
        # Recomenda-se chamar com um pequeno intervalo ou deixar que o frontend calcule a média
        cpu_percent = processo_atual.cpu_percent(interval=None)
        
        return {
            "cpu_percent": f"{cpu_percent:.1f}",
            "memory_mb": f"{mem_mb:.1f}"
        }
    except Exception as e:
        log.error("Monitoramento: Erro ao obter uso de recursos.", details=str(e))
        return {
            "cpu_percent": "N/D",
            "memory_mb": "N/D"
        }

def get_system_status():
    """
    Agrega todas as verificações de status em um único objeto.
    """
    return {
        "database": check_database_connection(),
        "resources": get_resource_usage()
    }