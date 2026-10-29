"""Verifica respostas Eel sem importar app.py ou tocar no banco local."""
import ast
from pathlib import Path
from types import SimpleNamespace

from src.simulador.mensagens import mensagem_erro


def ponte(calcular):
    arvore = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    funcao = next(no for no in arvore.body if isinstance(no, ast.FunctionDef)
                  and no.name == 'avaliar_operacao_completa_py')
    funcao.decorator_list = []
    ambiente = {'_calcular_operacao_compartilhada': calcular,
                'mensagem_erro': mensagem_erro,
                'analisar_operacao': lambda *args: {'status': 'Análise completa.'},
                'log': SimpleNamespace(error=lambda *args, **kwargs: None)}
    exec(compile(ast.Module(body=[funcao], type_ignores=[]), 'ponte', 'exec'), ambiente)
    return ambiente['avaliar_operacao_completa_py']


def test_importacao_com_falha_nao_expoe_caminho():
    def falhar(entrada):
        raise ImportError("cannot import name 'projetar_anos' from 'src.simulador.servico_divida'")
    resultado = ponte(falhar)({})
    assert resultado['status'] == 'erro'
    assert 'Tente novamente' in resultado['mensagem']
    assert 'src.' not in resultado['mensagem']


def test_validacao_da_operacao_chega_ao_usuario():
    def falhar(entrada):
        raise ValueError('Confira a data de recebimento, o prazo e o ano final do empréstimo.')
    assert ponte(falhar)({})['mensagem'].startswith('Confira a data')


def test_resultado_continua_disponivel():
    resultado = ponte(lambda entrada: {'bases_fluxo': [{'liberacaoNovaOperacao': '1000'}],
                                      'servico_input': {'linhas': []}})({'ano': 2026})
    assert resultado['status'] == 'sucesso'
    assert resultado['resultado']['analise']['status'] == 'Análise completa.'
