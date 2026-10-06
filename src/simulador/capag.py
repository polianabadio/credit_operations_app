"""Leitura da nota CAPAG publicada pelo Tesouro Transparente."""

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
import re
import unicodedata

import requests
from sqlalchemy.orm import Session

from .database_models import CapagPublicada, CapagIndicadores, db


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


def extrair_indicadores_go(conteudo):
    """Lê as colunas B–G do mesmo registro usado para a nota geral (H)."""
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
        if len(linha) < 8 or _normalizar(linha[0]) not in ('GO', 'GOIAS'):
            continue
        nota_geral = linha[7].upper().strip()
        if nota_geral not in NOTAS:
            raise ValueError(f'Nota CAPAG inválida para GO: {nota_geral}')
        indicadores = {}
        for chave, coluna_valor, coluna_nota in (
            ('endividamento', 1, 2),
            ('poupanca_corrente', 3, 4),
            ('liquidez_relativa', 5, 6),
        ):
            valor_bruto = linha[coluna_valor].strip().replace('%', '').replace(' ', '')
            if ',' in valor_bruto:
                valor_bruto = valor_bruto.replace('.', '').replace(',', '.')
            try:
                valor = Decimal(valor_bruto)
            except InvalidOperation as exc:
                raise ValueError(f'Valor CAPAG inválido para {chave}: {linha[coluna_valor]}') from exc
            nota = linha[coluna_nota].upper().strip()
            if not valor.is_finite() or nota not in NOTAS:
                raise ValueError(f'Indicador CAPAG inválido para {chave}')
            indicadores[chave] = {'valor': valor, 'nota': nota}
        return {'nota': nota_geral, 'indicadores': indicadores}
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
            recursos.append((int(ano.group(1)), 'REVISAO' in nome,
                             recurso['url'], recurso.get('description', '')))
    if not recursos:
        raise ValueError('Publicação CSV de CAPAG dos estados não encontrada.')
    # Usa a publicação íntegra mais recente; uma consulta falha não apaga o cache.
    ultimo_erro = None
    for ano, _, url, descricao in sorted(recursos, reverse=True):
        try:
            resposta = requests.get(url, timeout=(10, 30))
            resposta.raise_for_status()
            dados = extrair_indicadores_go(resposta.content)
            break
        except requests.HTTPError as exc:
            codigo = getattr(exc.response, 'status_code', None)
            if codigo not in (404, 410):
                raise
            ultimo_erro = exc
        except ValueError as exc:
            ultimo_erro = exc
    else:
        raise ValueError('Nenhuma publicação CAPAG completa foi encontrada.') from ultimo_erro
    nota = dados['nota']
    base = re.search(r'ANO\s*BASE\s*(20\d{2})', _normalizar(descricao))
    ano_base = int(base.group(1)) if base else None
    engine = db.session.get_bind()
    CapagPublicada.__table__.create(engine, checkfirst=True)
    CapagIndicadores.__table__.create(engine, checkfirst=True)
    with Session(bind=engine) as sessao:
        anterior = sessao.get(CapagIndicadores, 'GO')
        if anterior is not None and anterior.ano_publicacao > ano:
            nota_anterior = sessao.get(CapagPublicada, 'GO')
            return nota_anterior.nota if nota_anterior else nota
        sessao.merge(CapagPublicada(uf='GO', nota=nota, ano_publicacao=ano,
                                   fonte=url, consultado_em=datetime.now()))
        sessao.merge(CapagIndicadores(
            uf='GO', ano_publicacao=ano, ano_base=ano_base, fonte=url,
            consultado_em=datetime.now(),
            endividamento=dados['indicadores']['endividamento']['valor'],
            nota_endividamento=dados['indicadores']['endividamento']['nota'],
            poupanca_corrente=dados['indicadores']['poupanca_corrente']['valor'],
            nota_poupanca_corrente=dados['indicadores']['poupanca_corrente']['nota'],
            liquidez_relativa=dados['indicadores']['liquidez_relativa']['valor'],
            nota_liquidez_relativa=dados['indicadores']['liquidez_relativa']['nota'],
        ))
        sessao.commit()
    return nota


def obter_capag():
    engine = db.session.get_bind()
    CapagPublicada.__table__.create(engine, checkfirst=True)
    CapagIndicadores.__table__.create(engine, checkfirst=True)
    linha = db.session.query(CapagPublicada).filter(CapagPublicada.uf == 'GO').first()
    if linha is None:
        return None
    indicadores = db.session.query(CapagIndicadores).filter(CapagIndicadores.uf == 'GO').first()
    # A nota e os três componentes precisam pertencer à mesma publicação.
    componentes = None
    if indicadores and indicadores.ano_publicacao == linha.ano_publicacao and indicadores.fonte == linha.fonte:
        componentes = {
            chave: {'valor': float(getattr(indicadores, chave)),
                    'nota': getattr(indicadores, f'nota_{chave}')}
            for chave in ('endividamento', 'poupanca_corrente', 'liquidez_relativa')
        }
    return {
        'valor': linha.nota, 'ano': linha.ano_publicacao,
        'origem': 'Tesouro Transparente/CAPAG', 'url': linha.fonte,
        'ano_base': indicadores.ano_base if componentes else None,
        'indicadores': componentes,
    }
