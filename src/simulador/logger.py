# src/simulador/logger.py
'''Módulo de logging para a aplicação Eel.'''

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import List, Dict, Any
from enum import Enum

class LogLevel(Enum):
    """Níveis de log com cores associadas para o frontend."""
    DEBUG = ("DEBUG", "#6c757d")
    INFO = ("INFO", "#17a2b8")
    SUCCESS = ("SUCCESS", "#9ae6b4")
    WARNING = ("WARNING", "#faf089")
    ERROR = ("ERROR", "#feb2b2")
    CRITICAL = ("CRITICAL", "#d6bcfa")

class LoggerComponent:
    """Logger centralizado com suporte para logs estruturados e em tempo real."""
    
    def __init__(self, name: str = "SimuladorLogger"):
        self.name = name
        self.logs: List[Dict[str, Any]] = []
        self._setup_console_logger()
    
    def _setup_console_logger(self):
        """Configura um logger básico para o terminal do servidor."""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            if sys.stdout is not None:
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
            # No executável --windowed não há terminal. Guarde erros ao lado do exe.
            log_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
            try:
                handler = RotatingFileHandler(log_dir / 'app.log', maxBytes=1_000_000,
                                              backupCount=2, encoding='utf-8')
                handler.setLevel(logging.WARNING)
            except OSError:
                return
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _log(self, level: LogLevel, message: str, details: str = None, **kwargs):
        """
        Método principal para registrar e enviar a mensagem para o frontend,
        incluindo quaisquer dados de contexto extras passados via kwargs.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = {
            'timestamp': timestamp,
            'level': level.value[0],
            'color': level.value[1],
            'message': message,
            'details': details or "",
            'context': kwargs  # <--- Armazena todos os dados extras aqui
        }
        
        # Diagnósticos ficam no terminal do desenvolvedor.
        
        # Mapeia nosso nível customizado para um nível padrão do logging
        log_level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'SUCCESS': logging.INFO,  # Trata SUCCESS como INFO no terminal do backend
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        backend_log_level = log_level_map.get(level.value[0], logging.INFO)
        
        traceback_requested = kwargs.pop('traceback', False)
        context_str = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        full_message = f"{message} {details or ''} [{context_str}]"
        
        # Usa o nível mapeado para o logger do backend
        self.logger.log(backend_log_level, full_message, exc_info=traceback_requested)

    # --- Funções públicas atualizadas para aceitar **kwargs ---
    def debug(self, message: str, details: str = None, **kwargs): self._log(LogLevel.DEBUG, message, details, **kwargs)
    def info(self, message: str, details: str = None, **kwargs): self._log(LogLevel.INFO, message, details, **kwargs)
    def success(self, message: str, details: str = None, **kwargs): self._log(LogLevel.SUCCESS, message, details, **kwargs)
    def warning(self, message: str, details: str = None, **kwargs): self._log(LogLevel.WARNING, message, details, **kwargs)
    def error(self, message: str, details: str = None, **kwargs): self._log(LogLevel.ERROR, message, details, **kwargs)
    def critical(self, message: str, details: str = None, **kwargs): self._log(LogLevel.CRITICAL, message, details, **kwargs)

    # --- Funções de gerenciamento ---
    def clear_logs(self):
        self.logs.clear()
        self.info("O terminal de logs foi limpo pelo usuário.", modulo="logger.py")

    def get_all_logs(self):
        return self.logs

# --- Instância Global ---
log = LoggerComponent()
