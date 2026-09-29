"""Indicador DCL/RCL: compara os dois percentuais, sem somá-los."""
from decimal import Decimal
import unicodedata

NOME = '% da DCL sobre a RCL AJUSTADA (III/VI)'


def normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    return ' '.join(''.join(c for c in texto if not unicodedata.combining(c)).upper().split())


def avaliar_dcl(ano, registros):
    linhas = [r for r in registros if r['exercicio'] == ano
              and normalizar(r['conta']) == normalizar(NOME)]
    if not linhas:
        return None
    periodo = max(r['periodo'] for r in linhas)
    valores = {}
    for rotulo in ('Saldo do exercício anterior', f'Até o {periodo}º Quadrimestre'):
        encontrados = {Decimal(str(r['valor'])) for r in linhas
                       if r['periodo'] == periodo and r['valor'] is not None
                       and normalizar(r['coluna']) == normalizar(rotulo)}
        # Ausência ou conflito não pode virar aprovação nem valor zero.
        valores[rotulo] = next(iter(encontrados)) if len(encontrados) == 1 else None
    completo = all(v is not None for v in valores.values())
    aprovado = all(v <= Decimal('200') for v in valores.values()) if completo else None
    return {
        'tipo': 'dcl', 'nome': NOME, 'aprovado': aprovado,
        'status': 'Sem informação' if aprovado is None else 'Cumprida' if aprovado else 'Violada',
        'descricao': ('Dados insuficientes para avaliar os dois percentuais.' if aprovado is None else
                      'APROVADO: ambos os percentuais são menores ou iguais a 200%.' if aprovado else
                      'RECUSADO: um ou ambos os percentuais ultrapassam 200%.'),
        'dados_calculados': {'ano': ano, 'quadrimestre': periodo,
                            'valores': [{'rotulo': k, 'percentual': float(v) if v is not None else None}
                                        for k, v in valores.items()]}
    }
