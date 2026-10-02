"""
Módulo Principal de Configuração da Aplicação

Este módulo contém as configurações necessárias para a aplicação Eel,
incluindo configurações de banco de dados e outras configurações gerais.
"""

import os
import sys
import yaml
from pathlib import Path
import configparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .database_models import db, Base
from .logger import log


def get_asset_path(relative_path):
    """
    Obtém o caminho absoluto para um recurso (asset), funcionando tanto em
    modo de desenvolvimento quanto no executável do PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Estamos rodando em um bundle do PyInstaller
        base_path = Path(sys._MEIPASS)
    else:
        # Estamos rodando em modo normal
        # Assumimos que config.py está em src/simulador, então subimos 2 níveis
        base_path = Path(__file__).resolve().parents[2]
    return base_path / relative_path

def get_config_file_path(filename="settings.ini"):
    data_dir = os.environ.get('SIMULADOR_DATA_DIR')
    if data_dir:
        return Path(data_dir).expanduser().resolve() / filename
    if getattr(sys, 'frozen', False):
        # Estamos rodando empacotado (exe)
        # sys.executable é o caminho completo para o .exe
        exe_path = Path(sys.executable)
        # O diretório pai do .exe é onde queremos o .ini
        config_dir = exe_path.parent
    else:
        # Estamos rodando como script .py
        # __file__ é o caminho para config.py (src/simulador/config.py)
        # Subimos 2 níveis para chegar à raiz do projeto onde está app.py
        config_dir = Path(__file__).resolve().parents[2]

    return config_dir / filename

# Caminho para o arquivo de configurações
CONFIG_FILE_PATH = get_config_file_path()

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.parser = configparser.ConfigParser()
        self.load()

    def load(self):
        """Carrega as configurações do arquivo .ini."""
        if not self.config_path.exists():
            # Se o arquivo não existir, podemos criar um padrão, mas por enquanto vamos assumir que ele existe.
            log.warning(f"AVISO: Arquivo de configuração '{self.config_path}' não encontrado.")
            self._create_default_config()
            return
        else: 
            self.parser.read(self.config_path, encoding='utf-8')
            log.info(f"Configurações carregadas de '{self.config_path}'")

    def _create_default_config(self):
        """Define e salva as configurações padrão no parser."""
        self.parser['database'] = {
            'type': 'sqlite',
            'host': 'localhost', 'port': '5432', 'name': 'simulador_db', 'user': 'postgres', 'password': '',
            # IMPORTANTE: Caminho relativo ao executável
            'path': 'instance/database.db' 
        }
        self.parser['updater'] = { 'anos_historico': '3' }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.save()

    def save(self):
        """Salva as configurações atuais no arquivo .ini."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.parser.write(f)
            log.info(f"Configurações salvas em '{self.config_path}'")
        except Exception as e:
            log.error(f"Não foi possível salvar as configurações em {self.config_path}", details=str(e))

    def get_db_config(self) -> dict:
        """Retorna a configuração do banco de dados como um dicionário."""
        if 'database' in self.parser:
            return dict(self.parser['database'])
        return {}

    def get_db_engine_url(self) -> str:
        """Constrói a URL de conexão do SQLAlchemy a partir das configurações."""
        db_cfg = self.get_db_config()
        db_type = db_cfg.get('type', 'sqlite')

        try:
            if db_type == 'sqlite':
                path = get_config_file_path(db_cfg.get('path', 'instance/database.db'))
                path.parent.mkdir(parents=True, exist_ok=True)
                return f"sqlite:///{path}"
            elif db_type == 'postgresql':
                    return f"postgresql+psycopg2://{db_cfg['user']}:{db_cfg['password']}@{db_cfg['host']}:{db_cfg['port']}/{db_cfg['name']}"
            
            elif db_type == 'mysql':
                    return f"mysql+pymysql://{db_cfg['user']}:{db_cfg['password']}@{db_cfg['host']}:{db_cfg['port']}/{db_cfg['name']}"
        
            raise ValueError(f"Tipo de banco de dados '{db_type}' não suportado.")
        except KeyError as e:
            log.critical(f"Parâmetro de configuração do banco de dados ausente no settings.ini: {e}")
            raise

    def set_db_config(self, config_dict: dict):
        """Atualiza a seção [database] e salva o arquivo."""
        if 'database' not in self.parser:
            self.parser.add_section('database')
        
        for key, value in config_dict.items():
            self.parser.set('database', key, str(value))
        self.save()

# Instância global do nosso gerenciador de configurações
config_manager = ConfigManager(CONFIG_FILE_PATH)

# Diretório base da aplicação
BASE_DIR = get_asset_path('')
DATA_DIR = Path(os.environ['SIMULADOR_DATA_DIR']).expanduser().resolve() if os.environ.get('SIMULADOR_DATA_DIR') else BASE_DIR

# Configurações de upload
UPLOAD_FOLDER = DATA_DIR / "uploads"
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

# Configurações do Eel
EEL_WEB_FOLDER = get_asset_path('src/web')
EEL_SIZE = (1200, 800)
EEL_POSITION = "center"

# Configurações da aplicação
APP_NAME = "Simulador de Operações de Crédito"
APP_VERSION = "2.1.0"
DEBUG = True

# Criar diretórios necessários
def criar_diretorios():
    """Cria os diretórios necessários para a aplicação."""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(DATA_DIR / "instance", exist_ok=True)

# Configurações de logging
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'default',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'default',
            'filename': DATA_DIR / 'app.log',
            'mode': 'a',
        }
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['console', 'file']
    }
}

def carregar_modelo_yaml():
    """
    Carrega o arquivo modelo.yaml e retorna seu conteúdo como dicionário.
    
    Returns:
        dict: Conteúdo do modelo.yaml
    """
    try:
        modelo_path = BASE_DIR / "modelo.yaml"
        with open(modelo_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"Erro ao carregar modelo.yaml: {e}")
        return {}

def configurar_banco_dados():
    """Configura e inicializa o banco de dados SQLAlchemy."""
    try:
        DATABASE_URL = config_manager.get_db_engine_url()
        engine = create_engine(DATABASE_URL, echo=False)
        Session = sessionmaker(bind=engine)
        db.session = Session()
        # Cria tabelas se não existirem
        Base.metadata.create_all(engine)
        log.success("Conexão principal com o banco de dados estabelecida com sucesso.", details=f'Caminho do banco: {DATABASE_URL}')
        return True
    except Exception as e:
        log.critical("ERRO CRÍTICO AO CONECTAR AO BANCO DE DADOS.", details=str(e))
        return False
