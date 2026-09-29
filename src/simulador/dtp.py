"""DTP de Goiás: contribuições do mesmo quadrimestre e limite total de 60%."""
from decimal import Decimal

PODERES = {'E': 'Executivo', 'L': 'Legislativo', 'J': 'Judiciário',
           'M': 'Ministério Público', 'D': 'Defensoria Pública'}
SUCESSO = 'SUCESSO: Operação Aprovada / Concatenação Concluída'
FALHA = 'FALHA: Operação de Crédito Negada (Circuit Breaker)'


def _elegiveis(ano, registros):
    return [r for r in registros if r['exercicio'] == ano
            and r['uf'] == 'GO' and r['esfera'] == 'E'
            and r['anexo'] == 'RGF-Anexo 01'
            and r['coluna'] == '% sobre a RCL Ajustada'
            and 'DESPESA TOTAL COM PESSOAL' in ' '.join((r.get('conta') or '').upper().split())
            and r['co_poder'] in PODERES and r['valor'] is not None]


def avaliar_dtp(ano, registros):
    elegiveis = _elegiveis(ano, registros)
    resultados = []
    for codigo, nome in PODERES.items():
        linhas = [r for r in elegiveis if r['co_poder'] == codigo]
        periodo = max((r['periodo'] for r in linhas), default=None)
        unicas = {(r['instituicao'], r.get('cod_conta'), r['conta'],
                   r.get('rotulo'), r['coluna']): r for r in linhas if r['periodo'] == periodo}
        total = sum((Decimal(str(r['valor'])) for r in unicas.values()), Decimal('0'))
        aprovado = total <= Decimal('60') if unicas else None
        resultados.append({
            'aprovado': aprovado,
            'descricao': 'Sem informação' if aprovado is None else SUCESSO if aprovado else FALHA,
            'dados_calculados': {
                'ano': ano, 'quadrimestre': periodo, 'poder': nome,
                'percentual': float(total) if unicas else None,
                'componentes': [{'instituicao': r['instituicao'], 'conta': r['conta'],
                                 'percentual': float(r['valor'])} for r in unicas.values()]
            }
        })
    return resultados


def consolidar_dtp(ano, registros):
    elegiveis = _elegiveis(ano, registros)
    instituicoes = {}
    for r in elegiveis:
        nome = ' '.join((r.get('instituicao') or '').casefold().split())
        if nome:
            instituicoes.setdefault(r['periodo'], set()).add(nome)
    completos = [periodo for periodo, nomes in instituicoes.items() if len(nomes) >= 6]
    if not completos:
        return None
    periodo = max(completos)
    poderes = [r for r in avaliar_dtp(ano, [r for r in elegiveis if r['periodo'] == periodo])
               if r['aprovado'] is not None]
    total = sum((Decimal(str(r['dados_calculados']['percentual'])) for r in poderes), Decimal('0'))
    aprovado = total <= Decimal('60')
    return {
        'tipo': 'dtp', 'nome': 'Despesa Total com Pessoal - DTP',
        'status': 'Cumprida' if aprovado else 'Violada', 'aprovado': aprovado,
        'descricao': SUCESSO if aprovado else FALHA,
        'dados_calculados': {
            'ano': ano, 'quadrimestre': periodo, 'percentual': float(total),
            'limite_percentual': 60,
            'poderes': [{k: r['dados_calculados'][k] for k in
                        ('poder', 'ano', 'quadrimestre', 'percentual')} for r in poderes]
        }
    }
