"""Consulta somente leitura da versão publicada na pasta da equipe."""
import os
import re
from pathlib import Path


def consultar_versao_rede():
    raiz = os.environ.get('SIMULADOR_RELEASE_ROOT')
    atual = os.environ.get('SIMULADOR_RELEASE_VERSION')
    if not raiz or not atual:
        return {'disponivel': False}
    try:
        publicada = (Path(raiz) / 'versao-atual.txt').read_text(encoding='utf-8-sig').strip()
        pronta = Path(raiz) / 'versoes' / publicada / 'pronta.txt'
        disponivel = bool(re.fullmatch(r'\d+\.\d+\.\d+', publicada)
                          and publicada != atual and pronta.is_file())
        return {'disponivel': disponivel, 'atual': atual, 'publicada': publicada}
    except OSError:
        return {'disponivel': False}
