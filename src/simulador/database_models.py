from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base

# Base para os modelos declarativos
Base = declarative_base()

# Objeto db para a sessão, será inicializado em app.py
class Database:
    def __init__(self):
        self.session = None

db = Database()


class OperacaoCredito(Base):
    __tablename__ = 'operacao_credito'
    id = Column(Integer, primary_key=True)
    identificador = Column(String(150), nullable=False, unique=True)
    fonte = Column(String(1000), nullable=False)
    situacao = Column(String(40), nullable=False)
    tipo = Column(String(100), nullable=False)
    contratada = Column(Boolean, nullable=False)
    valor_total = Column(Numeric(20, 2), nullable=False)
    ano_inicio = Column(Integer, nullable=False)
    ano_fim = Column(Integer, nullable=False)
    ente = Column(String(100), nullable=False, default='Estado de Goiás')
    moeda = Column(String(10), nullable=False, default='BRL')
    cronograma_completo = Column(Boolean, nullable=False, default=False)
    atualizado_em = Column(DateTime, nullable=False)


class LiberacaoCredito(Base):
    __tablename__ = 'liberacao_credito'
    __table_args__ = (UniqueConstraint('operacao_id', 'ano'),)
    id = Column(Integer, primary_key=True)
    operacao_id = Column(Integer, ForeignKey('operacao_credito.id'), nullable=False)
    ano = Column(Integer, nullable=False)
    valor = Column(Numeric(20, 2), nullable=False)
    fonte = Column(String(1000), nullable=False)
    atualizado_em = Column(DateTime, nullable=False)


class CoberturaMga(Base):
    __tablename__ = 'cobertura_mga'
    ente = Column(String(100), primary_key=True)
    ano_inicio = Column(Integer, nullable=False)
    ano_fim = Column(Integer, nullable=False)
    fonte = Column(String(1000), nullable=False)
    atualizado_em = Column(DateTime, nullable=False)


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


class CapagIndicadores(Base):
    __tablename__ = 'capag_indicadores'
    uf = Column(String(2), primary_key=True)
    ano_publicacao = Column(Integer, nullable=False)
    ano_base = Column(Integer)
    fonte = Column(String(1000), nullable=False)
    consultado_em = Column(DateTime, nullable=False)
    endividamento = Column(Numeric(18, 6), nullable=False)
    nota_endividamento = Column(String(10), nullable=False)
    poupanca_corrente = Column(Numeric(18, 6), nullable=False)
    nota_poupanca_corrente = Column(String(10), nullable=False)
    liquidez_relativa = Column(Numeric(18, 6), nullable=False)
    nota_liquidez_relativa = Column(String(10), nullable=False)

class CapagHistorico(Base):
    __tablename__ = 'capag_historico'
    ano_publicacao = Column(Integer, primary_key=True)
    uf = Column(String(2), primary_key=True)
    ano_base = Column(Integer)
    nota = Column(String(10), nullable=False)
    fonte = Column(String(1000), nullable=False)
    revisao = Column(Boolean, nullable=False, default=False)
    observacao = Column(String(4000))
    consultado_em = Column(DateTime, nullable=False)


class CapagHistoricoIndicadores(Base):
    __tablename__ = 'capag_historico_indicadores'
    ano_publicacao = Column(Integer, primary_key=True)
    uf = Column(String(2), primary_key=True)
    fonte = Column(String(1000), nullable=False)
    valores = Column(String(4000), nullable=False)


class CapagComplemento(Base):
    """Campos adicionais da mesma publicação, sem migrar tabelas existentes."""
    __tablename__ = 'capag_complemento'
    uf = Column(String(2), primary_key=True)
    ano_publicacao = Column(Integer, nullable=False)
    fonte = Column(String(1000), nullable=False)
    ranking = Column(String(20))
    observacao = Column(String(4000))


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
