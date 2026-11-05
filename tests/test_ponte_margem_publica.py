"""Verifica a composição Eel sem importar app.py nem inicializar o banco."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock


class PonteMargemPublicaTest(unittest.TestCase):
    def test_dashboard_e_consulta_usam_projecao_e_memoria_publica(self):
        arvore = ast.parse((Path(__file__).parents[1] / 'app.py').read_text(encoding='utf-8-sig'))
        nomes = {'obter_painel_fiscal_py', 'obter_comprometimento_sadipem_py', '_consultar_comprometimento_sadipem'}
        funcoes = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in nomes]
        for funcao in funcoes:
            funcao.decorator_list = []
        painel = {'exercicio': 2026, 'rcl': {'valor': 1000}}
        projecao = {'positionOnly': True, 'parameterValidated': True, 'rows': []}
        sadipem = {'snapshot': {'idPleito': 1}}
        margem = {'status': 'Referência pública', 'rows': [{'margemEstimada': -10}]}
        contexto = {
            'obter_painel_fiscal': lambda: dict(painel),
            'obter_projecao': Mock(return_value=projecao),
            'obter_comprometimento_goias': Mock(return_value=sadipem),
            'obter_margem_publica': Mock(return_value=margem),
            'obter_pagamentos_dashboard': Mock(return_value={'status': 'Disponível', 'pagamentos': {2026: '10'}}),
        }
        exec(compile(ast.Module(body=funcoes, type_ignores=[]), 'ponte', 'exec'), contexto)
        resposta = contexto['obter_painel_fiscal_py']()
        self.assertIs(resposta['painel']['fluxo_credito'], projecao)
        resposta = contexto['obter_comprometimento_sadipem_py']()
        self.assertIs(resposta['margemPublica'], margem)
        self.assertIs(resposta['sadipem'], sadipem)
        self.assertEqual(resposta['pagamentosDivida']['pagamentos'], {2026: '10'})
        contexto['obter_pagamentos_dashboard'].assert_called_once_with(2026, sadipem)
        contexto['obter_margem_publica'].assert_called_once_with(projecao, sadipem)
        contexto['obter_comprometimento_goias'].assert_called_once_with(2026, 1000)
        contexto['obter_pagamentos_dashboard'].reset_mock()
        contexto['obter_comprometimento_sadipem_py'](False)
        contexto['obter_pagamentos_dashboard'].assert_not_called()
        contexto['obter_comprometimento_goias'].assert_called_with(2026, 1000, incluir_historico=False)


if __name__ == '__main__':
    unittest.main()


def test_api_lenta_nao_bloqueia_loop_de_eventos_eel():
    import gevent,time
    arvore=ast.parse((Path(__file__).parents[1]/'app.py').read_text(encoding='utf-8-sig'))
    funcao=next(n for n in arvore.body if isinstance(n,ast.FunctionDef) and n.name=='obter_comprometimento_sadipem_py')
    funcao.decorator_list=[]
    def consulta_lenta(detalhado):
        time.sleep(.25)
        return {'status':'sucesso'}
    contexto={'_consultar_comprometimento_sadipem':consulta_lenta}
    exec(compile(ast.Module(body=[funcao],type_ignores=[]),'ponte','exec'),contexto)
    tarefa=gevent.spawn(contexto['obter_comprometimento_sadipem_py'])
    pulsos=0
    while not tarefa.ready():
        gevent.sleep(.01);pulsos+=1
    assert tarefa.get()['status']=='sucesso'
    assert pulsos>=5,'A consulta HTTP bloqueou o loop de eventos do aplicativo'
