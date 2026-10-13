"""Testa a função da ponte sem importar app.py ou iniciar banco/sincronização."""
import ast
from pathlib import Path
from types import SimpleNamespace


def test_falha_mga_preserva_resultados_das_regras():
    arvore = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    funcao = next(no for no in arvore.body if isinstance(no, ast.FunctionDef)
                  and no.name == 'analisar_operacao_py')
    funcao.decorator_list = []
    chamadas = []
    def analisar(*args):
        chamadas.append(args)
        return {'status': 'Análise completa.', 'regras_ordenadas': [{'tipo': 'dtp'}]}
    def falhar(*args):
        raise ValueError('Cronograma incompleto')
    ambiente = {'analisar_operacao': analisar, 'avaliar_simulacao_mga': falhar,
                'log': SimpleNamespace(**{nome: lambda *a, **k: None
                                         for nome in ('info', 'success', 'error')})}
    exec(compile(ast.Module(body=[funcao], type_ignores=[]), 'ponte_isolada', 'exec'), ambiente)
    resultado = ambiente['analisar_operacao_py'](2026, 100)
    assert chamadas == [(2026, 100, None)]
    assert resultado['status'] == 'Análise completa.'
    assert resultado['regras_ordenadas'] == [{'tipo': 'dtp'}]
    assert resultado['mgaProjection']['validatedConclusion'] is False
    assert resultado['mgaProjection']['verificationStatus'] == 'Dados incompletos'
