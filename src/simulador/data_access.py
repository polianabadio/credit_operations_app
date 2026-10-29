"""
Módulo da Camada de Acesso a Dados (Data Access Layer)

Este módulo centraliza todas as consultas ao banco de dados, retornando os dados
em estruturas Python nativas (dicionários e listas) para serem consumidos
pelo motor de regras.
"""
import unicodedata
from calendar import monthrange
from datetime import date
from decimal import Decimal, localcontext

from sqlalchemy import and_, func

from .database_models import RGF, RREO, db

CONTA_RCL_ENDIVIDAMENTO = (
    'RECEITA CORRENTE LÍQUIDA AJUSTADA PARA CÁLCULO DOS LIMITES DE '
    'ENDIVIDAMENTO (V) = (III - IV)'
)
COLUNA_RCL_12_MESES = 'TOTAL (ÚLTIMOS 12 MESES)'
CONTAS_SERVICO_DIVIDA = ('JUROS E ENCARGOS DA DÍVIDA', 'AMORTIZAÇÃO DA DÍVIDA')
COLUNA_LIQUIDADA = 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)'
COLUNA_RESTOS = 'INSCRITAS EM RESTOS A PAGAR NÃO PROCESSADOS (k)'


def _normalizar_rotulo(texto):
    sem_acentos = ''.join(c for c in unicodedata.normalize('NFKD', texto or '')
                           if not unicodedata.combining(c))
    return ' '.join(sem_acentos.upper().split())


def obter_rcl_ajustada_endividamento(ano):
    """Último total de 12 meses publicado por GO no RREO Anexo 03 do ano."""
    candidatos = db.session.query(RREO).filter(
        RREO.exercicio == ano, RREO.uf == 'GO', RREO.esfera == 'E',
        RREO.anexo == 'RREO-Anexo 03', RREO.valor.isnot(None)
    ).order_by(RREO.periodo.desc()).all()
    conta = _normalizar_rotulo(CONTA_RCL_ENDIVIDAMENTO)
    coluna = _normalizar_rotulo(COLUNA_RCL_12_MESES)
    encontrados = [linha for linha in candidatos
                   if _normalizar_rotulo(linha.conta) == conta
                   and _normalizar_rotulo(linha.coluna) == coluna]
    if not encontrados:
        return None
    ultimo_periodo = encontrados[0].periodo
    ultimos = [linha for linha in encontrados if linha.periodo == ultimo_periodo]
    if len(ultimos) != 1:
        raise ValueError(f'RCL ajustada ambígua para GO em {ano}, período {ultimo_periodo}')
    linha = ultimos[0]
    return {
        'valor': linha.valor, 'exercicio': linha.exercicio, 'periodo': linha.periodo,
        'uf': linha.uf, 'anexo': linha.anexo, 'conta': linha.conta,
        'coluna': linha.coluna, 'origem': 'SICONFI/RREO',
    }


def obter_rcl_caed(ano, data_referencia):
    """RCL de GO até a data-base; nulo/conflito recente não recua silenciosamente."""
    referencia = date.fromisoformat(data_referencia)
    if referencia.year != ano:
        raise ValueError('Data de referência deve pertencer ao exercício selecionado')
    periodo_maximo = referencia.month // 2
    # O bimestre do mês corrente só está fechado no seu último dia.
    if referencia.month % 2 == 0 and referencia.day < monthrange(ano, referencia.month)[1]:
        periodo_maximo -= 1
    linhas = db.session.query(RREO).filter(
        RREO.uf == 'GO', RREO.esfera == 'E', RREO.anexo == 'RREO-Anexo 03',
        ((RREO.exercicio == ano) & (RREO.periodo <= periodo_maximo)) |
        ((RREO.exercicio == ano - 1) & (RREO.periodo == 6))
    ).order_by(RREO.exercicio.desc(), RREO.periodo.desc()).all()
    encontrados = [l for l in linhas if
                   _normalizar_rotulo(l.conta) == _normalizar_rotulo(CONTA_RCL_ENDIVIDAMENTO)
                   and _normalizar_rotulo(l.coluna) == _normalizar_rotulo(COLUNA_RCL_12_MESES)]
    if not encontrados:
        return None
    ultimo = encontrados[0]
    candidatos = [l for l in encontrados if (l.exercicio, l.periodo) == (ultimo.exercicio, ultimo.periodo)]
    if len(candidatos) != 1:
        raise ValueError('RCL CAED ambígua no último período fiscal')
    if ultimo.valor is None:
        return None
    mes = ultimo.periodo * 2
    data_base = date(ultimo.exercicio, mes, monthrange(ultimo.exercicio, mes)[1])
    return {'valor': ultimo.valor, 'exercicio': ultimo.exercicio, 'periodo': ultimo.periodo,
            'uf': 'GO', 'esfera': 'E', 'ente': 52, 'anexo': ultimo.anexo,
            'conta': ultimo.conta, 'coluna': ultimo.coluna, 'origem': 'SICONFI/RREO',
            'data_base': data_base.isoformat(), 'data_referencia': referencia.isoformat()}


def obter_servico_divida_exercicio_anterior(ano):
    """Valores do último RREO Anexo 01 de GO; restos ausentes são opcionais."""
    linhas = db.session.query(RREO).filter(
        RREO.exercicio == ano, RREO.uf == 'GO', RREO.esfera == 'E',
        RREO.anexo == 'RREO-Anexo 01'
    ).all()
    if not linhas:
        return None
    periodo = max(linha.periodo for linha in linhas)
    contas = {}
    for conta in CONTAS_SERVICO_DIVIDA:
        componentes = {}
        for coluna in (COLUNA_LIQUIDADA, COLUNA_RESTOS):
            valores = [linha.valor for linha in linhas if linha.periodo == periodo
                       and _normalizar_rotulo(linha.conta) == _normalizar_rotulo(conta)
                       and _normalizar_rotulo(linha.coluna) == _normalizar_rotulo(coluna)
                       and linha.valor is not None]
            if len(valores) > 1:
                raise ValueError(f'Dado duplicado: {conta}, {coluna}, {ano}/{periodo}')
            if not valores and coluna == COLUNA_LIQUIDADA:
                return None
            componentes[coluna] = valores[0] if valores else None
        contas[conta] = componentes
    return {'exercicio': ano, 'periodo': periodo, 'anexo': 'RREO-Anexo 01',
            'origem': 'SICONFI/RREO', 'contas': contas}


def obter_registros_dcl(ano):
    rows = db.session.query(RGF).filter(
        RGF.exercicio == ano, RGF.uf == 'GO', RGF.esfera == 'E',
        RGF.periodicidade == 'Q', RGF.co_poder == 'E', RGF.anexo == 'RGF-Anexo 02'
    ).all()
    return [{campo: getattr(row, campo) for campo in
             ('exercicio', 'periodo', 'conta', 'coluna', 'valor')} for row in rows]


def obter_posicao_monetaria_siconfi(ano_limite):
    """Valores publicados em reais, sem derivação dos percentuais CAPAG.

    Cada anexo conserva seu último exercício/período. Ausência, nulo ou
    duplicidade nesse período não autoriza recuo para um saldo anterior.
    """
    grupos = {}
    for modelo, anexo in ((RGF, 'RGF-Anexo 02'), (RREO, 'RREO-Anexo 01')):
        consulta = db.session.query(modelo).filter(
            modelo.uf == 'GO', modelo.esfera == 'E', modelo.anexo == anexo,
            modelo.exercicio <= ano_limite)
        if modelo is RGF:
            consulta = consulta.filter(RGF.co_poder == 'E', RGF.periodicidade == 'Q')
        linhas = consulta.order_by(modelo.exercicio.desc(), modelo.periodo.desc()).all()
        referencia = (linhas[0].exercicio, linhas[0].periodo) if linhas else None
        grupos[anexo] = (referencia, [l for l in linhas
                                    if (l.exercicio, l.periodo) == referencia])
    especificacoes = (
        ('divida_consolidada', 'Dívida consolidada', 'RGF-Anexo 02',
         'DÍVIDA CONSOLIDADA - DC (I)', 'estoque'),
        ('rcl', 'RCL · últimos 12 meses', 'RGF-Anexo 02',
         'RECEITA CORRENTE LÍQUIDA - RCL (IV)', 'receita_12_meses'),
        ('receitas_correntes', 'Receitas correntes realizadas', 'RREO-Anexo 01',
         'RECEITAS CORRENTES', 'acumulado_exercicio'),
        ('despesas_correntes', 'Despesas correntes liquidadas', 'RREO-Anexo 01',
         'DESPESAS CORRENTES', 'acumulado_exercicio'),
        ('caixa_bruto', 'Disponibilidade de caixa bruta', 'RGF-Anexo 02',
         'Disponibilidade de Caixa Bruta', 'estoque'),
    )
    resultado = []
    for chave, nome, anexo, conta, natureza in especificacoes:
        referencia, linhas = grupos[anexo]
        ano, periodo = referencia if referencia else (None, None)
        coluna = (f'Até o {periodo}º Quadrimestre' if anexo.startswith('RGF')
                  else 'Até o Bimestre (c)' if chave == 'receitas_correntes'
                  else COLUNA_LIQUIDADA)
        encontrados = [l for l in linhas
                       if _normalizar_rotulo(l.conta) == _normalizar_rotulo(conta)
                       and _normalizar_rotulo(l.coluna) == _normalizar_rotulo(coluna)]
        linha = encontrados[0] if len(encontrados) == 1 else None
        valor = linha.valor if linha else None
        resultado.append({
            'chave': chave, 'nome': nome, 'valor': str(valor) if valor is not None else None,
            'ano': ano, 'periodo': periodo, 'periodicidade': 'Q' if anexo.startswith('RGF') else 'B',
            'anexo': anexo, 'conta': linha.conta if linha else conta,
            'coluna': linha.coluna if linha else coluna,
            'origem': 'SICONFI/RGF' if anexo.startswith('RGF') else 'SICONFI/RREO',
            'escopo': 'Executivo' if anexo.startswith('RGF') else 'Estado de Goiás',
            'natureza': natureza,
            'estado': 'ambiguo' if len(encontrados) > 1 else 'disponivel' if valor is not None else 'ausente',
        })
    return resultado


def obter_historico_divida_rcl(ano_limite):
    """DC e RCL publicada do mesmo RGF/período, uma posição por exercício."""
    linhas = db.session.query(RGF).filter(
        RGF.uf == 'GO', RGF.esfera == 'E', RGF.co_poder == 'E',
        RGF.periodicidade == 'Q', RGF.anexo == 'RGF-Anexo 02',
        RGF.exercicio <= ano_limite).order_by(RGF.exercicio, RGF.periodo.desc()).all()
    anos = {}
    for linha in linhas:
        anos.setdefault(linha.exercicio, []).append(linha)
    contas = {
        'divida_consolidada': {'DIVIDA CONSOLIDADA - DC (I)'},
        'rcl': {'RECEITA CORRENTE LIQUIDA - RCL', 'RECEITA CORRENTE LIQUIDA - RCL (IV)'},
        'percentual_dcl_rcl': {'% DA DCL SOBRE A RCL (III/RCL)', '% DA DCL SOBRE A RCL AJUSTADA (III/VI)'},
    }
    resultado = []
    for ano, grupo in anos.items():
        periodo = max(l.periodo for l in grupo)
        coluna = _normalizar_rotulo(f'Até o {periodo}º Quadrimestre')
        item = {'ano': ano, 'periodo': periodo, 'parcial': periodo < 3,
                'anexo': 'RGF-Anexo 02', 'origem': 'SICONFI/RGF', 'escopo': 'Executivo',
                'percentual_dc_rcl': None, 'componentes': {}}
        for chave, nomes in contas.items():
            encontrados = [l for l in grupo if l.periodo == periodo
                           and _normalizar_rotulo(l.conta) in nomes
                           and _normalizar_rotulo(l.coluna) == coluna]
            linha = encontrados[0] if len(encontrados) == 1 else None
            valor = linha.valor if linha else None
            item[chave] = str(valor) if valor is not None else None
            item['componentes'][chave] = {
                'conta': linha.conta if linha else None, 'coluna': linha.coluna if linha else None,
                'estado': 'ambiguo' if len(encontrados) > 1 else 'disponivel' if valor is not None else 'ausente'}
        conta_percentual = item['componentes']['percentual_dcl_rcl']['conta']
        item['base_dcl_rcl'] = ('RCL ajustada' if 'AJUSTADA' in _normalizar_rotulo(conta_percentual)
                                else 'RCL' if conta_percentual else None)
        if item['divida_consolidada'] is not None and item['rcl'] is not None and Decimal(item['rcl']) > 0:
            with localcontext() as contexto:
                contexto.prec = 50
                item['percentual_dc_rcl'] = str(Decimal(item['divida_consolidada']) / Decimal(item['rcl']) * 100)
        resultado.append(item)
    return resultado


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
        RREO.anexo,
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
            'periodo': r.periodo,
            'anexo': r.anexo,
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
