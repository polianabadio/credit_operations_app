"""
Módulo da Camada de Acesso a Dados (Data Access Layer)

Este módulo centraliza todas as consultas ao banco de dados, retornando os dados
em estruturas Python nativas (dicionários e listas) para serem consumidos
pelo motor de regras.
"""
from sqlalchemy import func, and_
from .database_models import db, RREO, RGF


def obter_registros_dcl(ano):
    rows = db.session.query(RGF).filter(
        RGF.exercicio == ano, RGF.uf == 'GO', RGF.esfera == 'E',
        RGF.periodicidade == 'Q', RGF.co_poder == 'E', RGF.anexo == 'RGF-Anexo 02'
    ).all()
    return [{campo: getattr(row, campo) for campo in
             ('exercicio', 'periodo', 'conta', 'coluna', 'valor')} for row in rows]


def obter_registros_dtp(ano):
    """Mantém todos os quadrimestres para selecionar o último com valores por poder."""
    rows = db.session.query(RGF).filter(
        RGF.exercicio == ano, RGF.uf == 'GO', RGF.esfera == 'E',
        RGF.periodicidade == 'Q', RGF.anexo == 'RGF-Anexo 01',
        RGF.coluna == '% sobre a RCL Ajustada', RGF.valor.isnot(None)
    ).all()
    return [{campo: getattr(row, campo) for campo in (
        'exercicio', 'periodo', 'co_poder', 'instituicao', 'uf', 'esfera',
        'anexo', 'coluna', 'cod_conta', 'conta', 'valor', 'rotulo'
    )} for row in rows]

def _ultimos_periodos(modelo, anos):
    """Seleciona o último período de cada ano/anexo, sem misturar acumulados."""
    return db.session.query(
        modelo.exercicio.label('exercicio'), modelo.anexo.label('anexo'),
        func.max(modelo.periodo).label('periodo')
    ).filter(modelo.exercicio.in_(anos)).group_by(modelo.exercicio, modelo.anexo).subquery()


def obter_dados_rreo_para_analise(ano_corrente: int):
    """
    Busca todos os dados necessários da tabela RREO para o ano corrente e o anterior.

    Esta função faz uma única consulta otimizada para buscar todos os registros
    relevantes e os organiza em um dicionário para fácil acesso.

    Args:
        ano_corrente (int): O ano base para a análise.

    Returns:
        dict: Um dicionário estruturado com os dados do RREO.
    """
    # Consultamos os dois anos de uma vez para eficiência
    anos_necessarios = [ano_corrente, ano_corrente - 1]
    
    ultimos = _ultimos_periodos(RREO, anos_necessarios)
    query_result = db.session.query(
        RREO.exercicio,
        RREO.periodo,
        RREO.coluna,
        RREO.conta,
        RREO.valor
    ).join(ultimos, and_(RREO.exercicio == ultimos.c.exercicio,
                         RREO.anexo == ultimos.c.anexo,
                         RREO.periodo == ultimos.c.periodo)).all()

    # Estrutura de dados para armazenar o resultado organizado
    dados_organizados = {
        ano_corrente: {'max_periodo': 0, 'registros': []},
        ano_corrente - 1: {'max_periodo': 0, 'registros': []}
    }

    if not query_result:
        return dados_organizados

    # Processamos o resultado em Python para organizar os dados
    max_periodo_corrente = 0
    max_periodo_anterior = 0

    for r in query_result:
        registro_dict = {
            'coluna': r.coluna,
            'conta': r.conta,
            'valor': float(r.valor or 0.0)
        }
        dados_organizados[r.exercicio]['registros'].append(registro_dict)

        # Encontra o período máximo para cada ano
        if r.exercicio == ano_corrente and r.periodo > max_periodo_corrente:
            max_periodo_corrente = r.periodo
        elif r.exercicio == (ano_corrente - 1) and r.periodo > max_periodo_anterior:
            max_periodo_anterior = r.periodo

    dados_organizados[ano_corrente]['max_periodo'] = max_periodo_corrente
    dados_organizados[ano_corrente - 1]['max_periodo'] = max_periodo_anterior
    
    return dados_organizados


def obter_dados_rgf_para_analise(ano_corrente: int):
    """
    Busca todos os dados necessários da tabela RGF para o ano corrente.

    Args:
        ano_corrente (int): O ano base para a análise.

    Returns:
        dict: Um dicionário com a lista de registros do RGF.
    """
    anos_necessarios = [ano_corrente, ano_corrente - 1]
    
    ultimos = _ultimos_periodos(RGF, anos_necessarios)
    query_result = db.session.query(
        RGF.exercicio,
        RGF.coluna,
        RGF.conta,
        RGF.valor
    ).join(ultimos, and_(RGF.exercicio == ultimos.c.exercicio,
                         RGF.anexo == ultimos.c.anexo,
                         RGF.periodo == ultimos.c.periodo)).all()
    
    # Estrutura de retorno consistente com a do RREO
    dados_organizados = {
        ano_corrente: {'registros': []},
        ano_corrente - 1: {'registros': []}
    }
    
    if not query_result:
        return dados_organizados
        
    for r in query_result:
        registro_dict = {
            'coluna': r.coluna,
            'conta': r.conta,
            'valor': float(r.valor or 0.0)
        }
        dados_organizados[r.exercicio]['registros'].append(registro_dict)

    return dados_organizados
