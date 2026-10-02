"""Parâmetros editáveis compartilhados pelas simulações."""

from .database_models import db, ParametroSimulacao
from .servico_divida import FATOR_MEDIA_GEOMETRICA_10_ANOS, decimal_nao_negativo

CHAVE_FATOR = 'fator_projecao_rcl'


def obter_fator_projecao():
    registro = db.session.get(ParametroSimulacao, CHAVE_FATOR)
    return registro.valor if registro else str(FATOR_MEDIA_GEOMETRICA_10_ANOS)


def salvar_fator_projecao(valor):
    fator = decimal_nao_negativo(valor, 'fator de projeção')
    if fator == 0:
        raise ValueError('O fator de projeção deve ser positivo')
    texto = str(fator)
    registro = db.session.get(ParametroSimulacao, CHAVE_FATOR)
    if registro:
        registro.valor = texto
    else:
        db.session.add(ParametroSimulacao(chave=CHAVE_FATOR, valor=texto))
    db.session.commit()
    return texto
