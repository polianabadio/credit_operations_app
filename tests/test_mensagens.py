from src.simulador.mensagens import mensagem_erro


def test_validacao_orienta_correcao():
    assert mensagem_erro(ValueError('Informe uma taxa entre 0 e 100%.')) == 'Informe uma taxa entre 0 e 100%.'


def test_detalhes_internos_nao_sao_exibidos():
    for erro in (ImportError("cannot import name 'projetar_anos'"),
                 ValueError('invalid literal for int()'),
                 RuntimeError(r'C:\Users\pessoa\dados.db'),
                 ValueError('https://servico.exemplo/?senha=segredo')):
        mensagem = mensagem_erro(erro)
        assert 'Tente novamente' in mensagem
        assert str(erro) not in mensagem
