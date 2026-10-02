import pytest

from src.simulador.capag import extrair_nota_go


def test_capag_usa_classificacao_da_coluna_h_para_go():
    csv = ('UF;Indicador 1;Nota 1;Indicador 2;Nota 2;Indicador 3;Nota 3;'
           'Classificação da CAPAG\n'
           'DF;1;A;2;B;3;C;B\n'
           'GO;1;A;2;B;3;C;A+\n')
    assert extrair_nota_go(csv.encode('utf-8')) == 'A+'


def test_capag_nao_inventa_nota_ausente():
    with pytest.raises(ValueError, match='não foi encontrado'):
        extrair_nota_go(b'UF;1;2;3;4;5;6;7\nDF;1;2;3;4;5;6;A\n')
