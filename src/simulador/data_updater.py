"""
Módulo de Atualização de Dados

Este módulo contém as funções responsáveis por atualizar os dados da aplicação
através de APIs externas (Siconfi), extraídas das rotas Flask originais.
"""

import requests
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Lock
from time import monotonic, sleep
from sqlalchemy.orm import Session

from .config import configurar_banco_dados
from .database_models import RREO, RGF, db, SincronizacaoSiconfi
from .logger import log

_http_lock = Lock()
_ultima_requisicao = 0.0


def _aguardar_limite_api():
    """A API do Tesouro permite uma requisição por segundo."""
    global _ultima_requisicao
    with _http_lock:
        sleep(max(0, 1 - (monotonic() - _ultima_requisicao)))
        _ultima_requisicao = monotonic()


# ----------- Seção de atualização de dados via API do Siconfi -----------

def _criar_chave_identificadora(item, chaves):
    """Cria uma tupla única para um item com base em um conjunto de chaves."""
    return tuple(item.get(chave) for chave in chaves)

def _atualizar_dados_siconfi(modelo_db, endpoint, params_base, periodo_params, progresso=None):
    """Busca todas as páginas e salva cada período em uma única transação."""
    sucessos, falhas, avisos = [], [], []
    engine = db.session.get_bind()
    SincronizacaoSiconfi.__table__.create(engine, checkfirst=True)
    agora = datetime.now()
    def chave_consulta(periodo):
        return json.dumps([endpoint, {**params_base, **periodo}], sort_keys=True)
    pendentes = []
    with Session(bind=engine) as session:
        consultas = {r.chave: r for r in session.query(SincronizacaoSiconfi).all()}
        for periodo in periodo_params:
            anterior = consultas.get(chave_consulta(periodo))
            validade = timedelta(hours=1) if anterior and anterior.quantidade == 0 else (
                timedelta(days=7) if periodo['an_exercicio'] < agora.year else timedelta(hours=24))
            if anterior and timedelta(0) <= agora - anterior.consultado_em < validade:
                sucessos.append(periodo)
            else:
                pendentes.append(periodo)
    log.info('Consultas pendentes Siconfi.', endpoint=endpoint,
             pendentes=len(pendentes), reutilizadas=len(sucessos))
    concluidas = len(sucessos)
    if progresso:
        progresso(concluidas, len(periodo_params))
    def registrar_consulta(session, periodo, quantidade):
        session.merge(SincronizacaoSiconfi(chave=chave_consulta(periodo),
                      consultado_em=datetime.now(), quantidade=quantidade))
    chaves = {
        'rreo': ['exercicio', 'periodo', 'instituicao', 'anexo', 'rotulo', 'coluna', 'conta'],
        'rgf': ['exercicio', 'periodo', 'instituicao', 'co_poder', 'anexo', 'rotulo', 'coluna', 'cod_conta'],
    }[endpoint]
    base_url = f"https://apidatalake.tesouro.gov.br/ords/siconfi/tt/{endpoint}"
    # Somente HTTP em paralelo; gravações permanecem sequenciais.
    def buscar(periodo):
        try:
            with requests.Session() as http:
                items, offset = [], 0
                while True:
                    _aguardar_limite_api()
                    response = http.get(base_url, params={**params_base, **periodo, 'offset': offset}, timeout=(10, 30))
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
                        raise ValueError('Resposta inválida: a API não retornou uma lista items.')
                    pagina = data['items']
                    items.extend(pagina)
                    if not data.get('hasMore', False):
                        return items
                    if not pagina:
                        raise ValueError('Paginação inválida: página vazia com hasMore=true.')
                    offset += len(pagina)
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=3) as pool:
        for periodo, resposta in zip(pendentes, pool.map(buscar, pendentes)):
            log.info('Consultando API Siconfi.', endpoint=endpoint, **periodo)
            try:
                if isinstance(resposta, Exception):
                    raise resposta
                items = resposta
                if not items:
                    with Session(bind=engine) as session:
                        registrar_consulta(session, periodo, 0)
                        session.commit()
                    aviso = {**periodo, 'motivo': 'SICONFI não retornou dados para este período e anexo.'}
                    avisos.append(aviso)
                    log.info(aviso['motivo'], endpoint=endpoint, **periodo)
                    continue

                filtrados = [item for item in items if endpoint != 'rreo'
                             or not (item.get('coluna') or '').startswith(('%', 'SALDO'))]
                # Uma consulta de chaves por período, em vez de consultas OR a cada 50 linhas.
                with Session(bind=db.session.get_bind()) as session:
                    query = session.query(*(getattr(modelo_db, chave) for chave in chaves)).filter(
                        modelo_db.exercicio == periodo['an_exercicio'],
                        modelo_db.periodo == periodo['nr_periodo'],
                        modelo_db.anexo == periodo['no_anexo'])
                    existentes = {tuple(row) for row in query.all()}
                    novos = []
                    for item in filtrados:
                        chave = _criar_chave_identificadora(item, chaves)
                        if chave not in existentes:
                            novos.append(item)
                            existentes.add(chave)
                    if novos:
                        session.bulk_insert_mappings(modelo_db, novos)
                    registrar_consulta(session, periodo, len(items))
                    session.commit()
                sucessos.append(periodo)
                log.info('Período processado.', endpoint=endpoint, **periodo,
                         registros_resgatados=len(filtrados), registros_inseridos=len(novos),
                         registros_ja_existentes=len(filtrados) - len(novos))
            except Exception as exc:
                motivo = ('Tempo limite excedido ao consultar o SICONFI.'
                          if isinstance(exc, requests.Timeout) else str(exc) or type(exc).__name__)
                falhas.append({**periodo, 'motivo': motivo})
                log.error('Falha na atualização Siconfi.', details=motivo, endpoint=endpoint, **periodo)
            finally:
                concluidas += 1
                if progresso:
                    progresso(concluidas, len(periodo_params))
    return sucessos, falhas, avisos


def _resultado_atualizacao(nome, sucessos, falhas, avisos):
    status = 'error' if falhas else 'success'
    return {'message': f'Consulta {nome} concluída: {len(sucessos)} período(s) processado(s), '
                       f'{len(avisos)} sem dados e {len(falhas)} falha(s).',
            'status': status, 'sucessos': sucessos, 'falhas': falhas, 'avisos': avisos}


def _periodos_para_consulta(endpoint, status='all'):
    ano_atual = datetime.now().year
    # Mantém a cobertura histórica do projeto, incluindo todos os períodos.
    anos = [ano_atual] if status == 'now' else range(2021, ano_atual + 1)
    quantidade = 6 if endpoint == 'rreo' else 3
    return [dict(an_exercicio=ano, nr_periodo=periodo,
                 no_anexo=f'{endpoint.upper()}-Anexo {anexo:02}',
                 **({'co_poder': poder} if endpoint == 'rgf' else {}))
            for ano in reversed(list(anos))
            for periodo in range(1, quantidade + 1)
            for anexo in (1, 2)
            for poder in (('E', 'L', 'J', 'M', 'D') if endpoint == 'rgf' and anexo == 1 else ('E',))]


def atualizar_operacoes_rreo(status='all', progresso=None):
    params = dict(co_tipo_demonstrativo='RREO', co_esfera='E', id_ente=52)
    return _resultado_atualizacao('RREO', *_atualizar_dados_siconfi(
        RREO, 'rreo', params, _periodos_para_consulta('rreo', status), progresso))


def atualizar_operacoes_rgf(status='all', progresso=None):
    params = dict(in_periodicidade='Q', co_tipo_demonstrativo='RGF', co_esfera='E', id_ente=52)
    return _resultado_atualizacao('RGF', *_atualizar_dados_siconfi(
        RGF, 'rgf', params, _periodos_para_consulta('rgf', status), progresso))

# ------------------------- Fim da Seção Siconfi -------------------------


# -------- Seção para incluir upload de CSVs --------
# Posteriormente será feito um teste entre uso da biblioteca Pandas e CSV padrão do Python - Será avaliado o peso no empacotamento final


if __name__ == "__main__":
    # Configura banco de dados
    if not configurar_banco_dados():
        print("Falha na configuração do banco de dados.")
        exit(1)

    print("Escolha a operação:")
    print("1 - Atualizar RREO")
    print("2 - Atualizar RGF")
    escolha = input("Digite o número da operação: ")

    if escolha == "1":
        resultado = atualizar_operacoes_rreo(status='past')
        print(resultado)
    elif escolha == "2":
        resultado = atualizar_operacoes_rgf(status='now')
        print(resultado)
    else:
        print("Opção inválida.")
