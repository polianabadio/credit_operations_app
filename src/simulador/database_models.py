from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime
from sqlalchemy.orm import declarative_base

# Base para os modelos declarativos
Base = declarative_base()

# Objeto db para a sessão, será inicializado em app.py
class Database:
    def __init__(self):
        self.session = None

db = Database()


class SincronizacaoSiconfi(Base):
    __tablename__ = 'sincronizacao_siconfi'
    chave = Column(String(1000), primary_key=True)
    consultado_em = Column(DateTime, nullable=False)
    quantidade = Column(Integer, nullable=False)


class ParametroSimulacao(Base):
    __tablename__ = 'parametro_simulacao'
    chave = Column(String(100), primary_key=True)
    valor = Column(String(100), nullable=False)


class CapagPublicada(Base):
    __tablename__ = 'capag_publicada'
    uf = Column(String(2), primary_key=True)
    nota = Column(String(10), nullable=False)
    ano_publicacao = Column(Integer, nullable=False)
    fonte = Column(String(1000), nullable=False)
    consultado_em = Column(DateTime, nullable=False)

class RREO(Base):
    __tablename__ = 'rreo'

    id = Column(Integer, primary_key=True)
    exercicio = Column(Integer, nullable=False)
    demonstrativo = Column(String(30), nullable=False)
    periodo = Column(Integer, nullable=False)
    instituicao = Column(String(100), nullable=False)
    uf = Column(String(2), nullable=False)
    anexo = Column(String(50), nullable=False)
    esfera = Column(String(2), nullable=False)
    rotulo = Column(String(100))
    coluna = Column(String(150))
    cod_conta = Column(String(150))
    conta = Column(String(150))
    valor = Column(Numeric(15,2))

class RGF(Base):
    __tablename__ = 'rgf'

    id = Column(Integer, primary_key=True)
    exercicio = Column(Integer, nullable=False)
    periodo = Column(Integer, nullable=False)
    periodicidade = Column(String(5), nullable=False)
    instituicao = Column(String(100), nullable=False)
    uf = Column(String(2), nullable=False)
    co_poder = Column(String(2), nullable=False)
    anexo = Column(String(50), nullable=False)
    esfera = Column(String(2), nullable=False)
    rotulo = Column(String(100))
    coluna = Column(String(255))
    cod_conta = Column(String(255))
    conta = Column(String(255))
    valor = Column(Numeric(15,2))
