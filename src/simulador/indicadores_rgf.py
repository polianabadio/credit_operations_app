"""Indicadores publicados no RGF do Executivo de Goiás (Anexos 03 e 04)."""

from decimal import Decimal
import unicodedata

from .database_models import RGF, db


def _normalizar(texto):
    sem_acentos = ''.join(c for c in unicodedata.normalize('NFKD', texto or '')
                           if not unicodedata.combining(c))
    return ' '.join(sem_acentos.upper().split())


def _coluna_atual(linhas, periodo):
    if len(linhas) <= 1:
        return linhas
    ordinal = f'ATE O {periodo}'
    atuais = [r for r in linhas if ordinal in _normalizar(r.coluna)]
    if len(atuais) == 1:
        return atuais
    atuais = [r for r in linhas if 'ATE O QUADRIMESTRE DE REFERENCIA' in _normalizar(r.coluna)]
    return atuais if len(atuais) == 1 else []


def _percentual(linhas, prefixo, periodo, nome):
    """Usa a porcentagem publicada; só calcula se a própria tabela trouxer RCL."""
    candidatos = [r for r in linhas if _normalizar(r.conta).startswith(prefixo)
                  and r.valor is not None]
    if nome == 'garantias':
        percentuais = [r for r in linhas if _normalizar(r.conta).startswith(
            '% DO TOTAL DAS GARANTIAS SOBRE A RCL AJUSTADA') and r.valor is not None]
    else:
        percentuais = [r for r in candidatos if '%' in _normalizar(r.coluna)]
    percentuais = _coluna_atual(percentuais, periodo)
    if len(percentuais) == 1:
        return percentuais[0].valor
    if len(percentuais) > 1:
        return None
    valores = _coluna_atual([r for r in candidatos if '%' not in _normalizar(r.coluna)], periodo)
    rcls = _coluna_atual([r for r in linhas if _normalizar(r.conta).startswith(
        'RECEITA CORRENTE LIQUIDA AJUSTADA PARA CALCULO DOS LIMITES DE ENDIVIDAMENTO')
        and r.valor is not None and '%' not in _normalizar(r.coluna)], periodo)
    if len(valores) != 1 or len(rcls) != 1 or rcls[0].valor <= 0:
        return None
    return valores[0].valor / rcls[0].valor * Decimal('100')


def _resumo_anexo_06(linhas, nome):
    """Lê apenas o percentual explícito do quadro de operações de crédito."""
    trecho = ('OPERACOES DE CREDITO INTERNAS E EXTERNAS' if nome == 'mga'
              else 'OPERACOES DE CREDITO POR ANTECIPACAO DA RECEITA')
    candidatos = [r for r in linhas if trecho in _normalizar(r.conta)
                  and 'LIMITE' not in _normalizar(r.conta)
                  and '%' in _normalizar(r.coluna) and r.valor is not None]
    if len(candidatos) != 1:
        return None
    return candidatos[0].valor


def obter_indicadores_rgf(ano):
    """Não mistura quadrimestres nem substitui dado ausente por zero."""
    resultado = {}
    contas = {
        'garantias': ('RGF-Anexo 03', 'TOTAL GARANTIAS CONCEDIDAS'),
        'mga': ('RGF-Anexo 04', 'TOTAL CONSIDERADO PARA FINS DA APURACAO DO CUMPRIMENTO DO LIMITE'),
        'aro': ('RGF-Anexo 04', 'OPERACOES DE CREDITO POR ANTECIPACAO DA RECEITA ORCAMENTARIA'),
    }
    for nome, (anexo, conta) in contas.items():
        linhas = db.session.query(RGF).filter(
            RGF.exercicio == ano, RGF.uf == 'GO', RGF.esfera == 'E',
            RGF.periodicidade == 'Q', RGF.co_poder == 'E', RGF.anexo == anexo,
            RGF.valor.isnot(None)).all()
        for periodo in sorted({r.periodo for r in linhas}, reverse=True):
            grupo = [r for r in linhas if r.periodo == periodo]
            percentual = _percentual(grupo, conta, periodo, nome)
            if percentual is not None:
                resultado[nome] = {'valor': float(percentual), 'ano': ano,
                                   'periodo': periodo, 'anexo': anexo,
                                   'origem': 'SICONFI/RGF'}
                break
    if 'mga' not in resultado or 'aro' not in resultado:
        resumo = db.session.query(RGF).filter(
            RGF.exercicio == ano, RGF.uf == 'GO', RGF.esfera == 'E',
            RGF.periodicidade == 'Q', RGF.co_poder == 'E',
            RGF.anexo == 'RGF-Anexo 06', RGF.valor.isnot(None)).all()
        for nome in ('mga', 'aro'):
            if nome in resultado:
                continue
            for periodo in sorted({r.periodo for r in resumo}, reverse=True):
                percentual = _resumo_anexo_06(
                    [r for r in resumo if r.periodo == periodo], nome)
                if percentual is not None:
                    resultado[nome] = {'valor': float(percentual), 'ano': ano,
                                       'periodo': periodo, 'anexo': 'RGF-Anexo 06',
                                       'origem': 'SICONFI/RGF'}
                    break
    return resultado
