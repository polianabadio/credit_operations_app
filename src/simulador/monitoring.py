# src/simulador/monitoring.py
"""
MÃ³dulo de Monitoramento do Sistema.

Fornece funÃ§Ãµes para verificar o status dos serviÃ§os (como o BD)
e o uso de recursos do sistema (CPU, MemÃ³ria).
"""

import psutil
import os

from .logger import log

# ObtÃ©m o processo atual da aplicaÃ§Ã£o
processo_atual = psutil.Process(os.getpid())

def check_database_connection():
    """Contrato de monitoramento legado; verifica o cache, nÃ£o um banco."""
    from .database_models import db
    try:
        db.session.get_bind().ler()
        return {'status': 'Online', 'mensagem': 'Cache JSON disponÃ­vel.'}
    except Exception:
        return {'status': 'Offline', 'mensagem': 'NÃ£o foi possÃ­vel ler o cache JSON compartilhado.'}


def get_resource_usage():
    """
    ObtÃ©m o uso de CPU e MemÃ³ria do processo atual da aplicaÃ§Ã£o.
    """
    try:
        # Uso de MemÃ³ria
        mem_info = processo_atual.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)  # Converte de bytes para Megabytes
        
        # Uso de CPU
        # O primeiro chamado de cpu_percent(interval=None) retorna 0.0
        # Recomenda-se chamar com um pequeno intervalo ou deixar que o frontend calcule a mÃ©dia
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
    Agrega todas as verificaÃ§Ãµes de status em um Ãºnico objeto.
    """
    return {
        "database": check_database_connection(),
        "resources": get_resource_usage()
    }