"""Leitura da nota CAPAG publicada pelo Tesouro Transparente."""

import csv
from datetime import datetime
from io import StringIO
import re
import unicodedata

import requests
from sqlalchemy.orm import Session

from .database_models import CapagPublicada, db


PACOTE = 'https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show'
NOTAS = {'A+', 'A', 'B+', 'B', 'C', 'D', 'N.D.'}


def _normalizar(valor):
    return ''.join(c for c in unicodedata.normalize('NFKD', valor or '')
                   if not unicodedata.combining(c)).upper().strip()


def extrair_nota_go(conteudo):
    """A UF é a coluna A e a classificação CAPAG é a H, conforme metadados da STN."""
    for codificacao in ('utf-8-sig', 'latin-1'):
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    try:
        separador = csv.Sniffer().sniff(texto[:2048], delimiters=';,\t').delimiter
    except csv.Error:
        separador = ';'
    for linha in csv.reader(StringIO(texto), delimiter=separador):
        if len(linha) < 8:
            continue
        if _normalizar(linha[0]) in ('GO', 'GOIAS'):
            nota = linha[7].upper().strip()
            if nota not in NOTAS:
                raise ValueError(f'Nota CAPAG inválida para GO: {nota}')
            return nota
    raise ValueError('Goiás não foi encontrado na publicação CAPAG.')


def atualizar_capag():
    resposta = requests.get(PACOTE, params={'id': 'capag-estados'}, timeout=(10, 30))
    resposta.raise_for_status()
    pacote = resposta.json()['result']
    recursos = []
    for recurso in pacote['resources']:
        if recurso.get('format', '').upper() != 'CSV':
            continue
        nome = _normalizar(recurso.get('name', ''))
        ano = re.search(r'CAPAG\s+(?:DOS\s+)?ESTADOS\s+(20\d{2})', nome)
        if ano and recurso.get('url'):
            recursos.append((int(ano.group(1)), recurso['url']))
    if not recursos:
        raise ValueError('Publicação CSV de CAPAG dos estados não encontrada.')
    ano, url = max(recursos)
    resposta = requests.get(url, timeout=(10, 30))
    resposta.raise_for_status()
    nota = extrair_nota_go(resposta.content)
    engine = db.session.get_bind()
    CapagPublicada.__table__.create(engine, checkfirst=True)
    with Session(bind=engine) as sessao:
        sessao.merge(CapagPublicada(uf='GO', nota=nota, ano_publicacao=ano,
                                   fonte=url, consultado_em=datetime.now()))
        sessao.commit()
    return nota


def obter_capag():
    CapagPublicada.__table__.create(db.session.get_bind(), checkfirst=True)
    linha = db.session.query(CapagPublicada).filter(CapagPublicada.uf == 'GO').first()
    return None if linha is None else {
        'valor': linha.nota, 'ano': linha.ano_publicacao,
        'origem': 'Tesouro Transparente/CAPAG', 'url': linha.fonte,
    }
