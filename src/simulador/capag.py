"""Leitura da nota CAPAG publicada pelo Tesouro Transparente."""

import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import StringIO
import re
import unicodedata

import requests
from sqlalchemy.orm import Session

from .database_models import CapagPublicada, CapagIndicadores, CapagComplemento, CapagHistorico, CapagHistoricoIndicadores, db
from .logger import log


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


def extrair_nota_historica(conteudo):
    """Lê o cabeçalho da publicação, inclusive o layout de cinco colunas de 2018."""
    try:
        texto = conteudo.decode('utf-8-sig')
    except UnicodeDecodeError:
        texto = conteudo.decode('latin-1')
    try:
        separador = csv.Sniffer().sniff(texto[:2048], delimiters=';,\t').delimiter
    except csv.Error:
        separador = ';'
    cabecalho = None
    encontrados = []
    for linha in csv.reader(StringIO(texto), delimiter=separador):
        if linha and _normalizar(linha[0]) == 'UF':
            cabecalho = [_normalizar(c) for c in linha]
        if not linha or _normalizar(linha[0]) not in ('GO', 'GOIAS'):
            continue
        if not cabecalho or 'CLASSIFICACAO DA CAPAG' not in cabecalho:
            raise ValueError('Cabeçalho CAPAG histórico não reconhecido.')
        indice = cabecalho.index('CLASSIFICACAO DA CAPAG')
        nota = linha[indice].strip().upper() if len(linha) > indice else None
        if nota not in NOTAS:
            raise ValueError('Nota histórica inválida.')
        obs = cabecalho.index('OBSERVACAO') if 'OBSERVACAO' in cabecalho else None
        indicadores = {}
        for numero, chave in enumerate(('endividamento', 'poupanca_corrente', 'liquidez_relativa'), 1):
            coluna = f'INDICADOR {numero}'
            if coluna not in cabecalho:
                continue
            pos = cabecalho.index(coluna)
            bruto = linha[pos].strip() if len(linha) > pos else ''
            if bruto in ('', '-', 'N.D.'):
                continue
            try:
                numero_decimal = bruto.replace('%', '').replace(' ', '')
                if ',' in numero_decimal:
                    numero_decimal = numero_decimal.replace('.', '').replace(',', '.')
                valor = Decimal(numero_decimal)
                # Os CSVs históricos sem sinal % publicam razões (ex.: 0,92).
                # Valores com sinal % já estão em pontos percentuais.
                if '%' not in bruto:
                    valor *= 100
                if not valor.is_finite():
                    continue
                indicadores[chave] = str(valor)
            except InvalidOperation:
                continue
        encontrados.append({'nota': nota, 'indicadores': indicadores,
                            'observacao': linha[obs].strip() if obs is not None and len(linha) > obs else None})
    if len(encontrados) != 1:
        raise ValueError('Registro histórico de Goiás ausente ou ambíguo.')
    return encontrados[0]


def atualizar_historico_capag(engine, pacote):
    """Cache por publicação; falhas não apagam notas nem rebaixam uma revisão salva."""
    CapagHistorico.__table__.create(engine, checkfirst=True)
    CapagHistoricoIndicadores.__table__.create(engine, checkfirst=True)
    recursos = {}
    for recurso in pacote.get('resources', []):
        nome = _normalizar(recurso.get('name', ''))
        ano = re.search(r'CAPAG\s+(?:DOS\s+)?ESTADOS\s+(20\d{2})', nome)
        if ano and recurso.get('format', '').upper() == 'CSV' and recurso.get('url'):
            recursos.setdefault(int(ano.group(1)), []).append(recurso)
    with Session(bind=engine) as sessao:
        for ano, candidatos in sorted(recursos.items()):
            anterior = sessao.get(CapagHistorico, (ano, 'GO'))
            componentes = sessao.get(CapagHistoricoIndicadores, (ano, 'GO'))
            candidatos.sort(key=lambda r: ('REVISAO' in _normalizar(r.get('name', '')), r['url']), reverse=True)
            if (anterior and componentes and componentes.fonte == anterior.fonte and anterior.fonte == candidatos[0]['url']
                    and anterior.consultado_em > datetime.now() - timedelta(days=7)):
                continue
            for recurso in candidatos:
                revisao = 'REVISAO' in _normalizar(recurso.get('name', ''))
                if anterior and anterior.revisao and not revisao:
                    continue
                try:
                    resposta = requests.get(recurso['url'], timeout=(10, 30))
                    resposta.raise_for_status()
                    dados = extrair_nota_historica(resposta.content)
                except (requests.RequestException, ValueError) as exc:
                    log.warning(f'Publicação histórica CAPAG {ano} não atualizada.', details=str(exc))
                    continue
                base = re.search(r'ANOS?\s*BASE\s*(20\d{2})', _normalizar(recurso.get('description', '')))
                sessao.merge(CapagHistorico(uf='GO', ano_publicacao=ano,
                    ano_base=int(base.group(1)) if base else None, nota=dados['nota'],
                    observacao=dados['observacao'], fonte=recurso['url'], revisao=revisao,
                    consultado_em=datetime.now()))
                sessao.merge(CapagHistoricoIndicadores(uf='GO', ano_publicacao=ano,
                    fonte=recurso['url'], valores=json.dumps(dados['indicadores'])))
                sessao.commit()
                break


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
        # Layout oficial desde 2024: I = ranking ICF; J = observação.
        ranking = linha[8].strip() if len(linha) >= 10 else None
        if ranking and ranking.upper() not in {'AICF', 'BICF', 'CICF', 'DICF', 'EICF', 'N.D.'}:
            ranking = None
        observacao = linha[9].strip() if len(linha) >= 10 else linha[8].strip() if len(linha) == 9 else None
        return {'nota': nota_geral, 'indicadores': indicadores,
                'ranking': ranking or None, 'observacao': observacao or None}
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
    CapagComplemento.__table__.create(engine, checkfirst=True)
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
        sessao.merge(CapagComplemento(uf='GO', ano_publicacao=ano, fonte=url,
                                     ranking=dados['ranking'], observacao=dados['observacao']))
        sessao.commit()
    try:
        atualizar_historico_capag(engine, pacote)
    except Exception as exc:
        log.warning('Histórico CAPAG não atualizado; publicação atual preservada.', details=str(exc))
    return nota


def obter_capag():
    engine = db.session.get_bind()
    CapagPublicada.__table__.create(engine, checkfirst=True)
    CapagIndicadores.__table__.create(engine, checkfirst=True)
    CapagComplemento.__table__.create(engine, checkfirst=True)
    CapagHistorico.__table__.create(engine, checkfirst=True)
    CapagHistoricoIndicadores.__table__.create(engine, checkfirst=True)
    linha = db.session.query(CapagPublicada).filter(CapagPublicada.uf == 'GO').first()
    if linha is None:
        return None
    indicadores = db.session.query(CapagIndicadores).filter(CapagIndicadores.uf == 'GO').first()
    complemento = db.session.query(CapagComplemento).filter(CapagComplemento.uf == 'GO').first()
    complemento_compativel = (complemento is not None and complemento.ano_publicacao == linha.ano_publicacao
                              and complemento.fonte == linha.fonte)
    componentes_historicos = {item.ano_publicacao: item for item in
        db.session.query(CapagHistoricoIndicadores).filter_by(uf='GO').all()}
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
        'ranking': complemento.ranking if complemento_compativel else None,
        'observacao': complemento.observacao if complemento_compativel else None,
        'historico': [{'ano': item.ano_publicacao, 'ano_base': item.ano_base,
                      'nota': item.nota, 'url': item.fonte, 'revisao': item.revisao,
                      'observacao': item.observacao, 'consultado_em': item.consultado_em.isoformat()}
                     | {'indicadores': json.loads(componentes_historicos[item.ano_publicacao].valores)
                        if item.ano_publicacao in componentes_historicos and componentes_historicos[item.ano_publicacao].fonte == item.fonte else {}}
                     for item in db.session.query(CapagHistorico).filter_by(uf='GO')
                     .order_by(CapagHistorico.ano_publicacao).all()],
    }
