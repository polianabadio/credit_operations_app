"""Consulta pública do SADIPEM. Cada PVL é um snapshot, não um somatório de PVLs."""

import json
import os
import threading
import time
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests

from .logger import log


BASE_URL = os.getenv('SADIPEM_BASE_URL', 'https://apidatalake.tesouro.gov.br/ords/cdwhprd/sadipem/tt/')
CACHE_SECONDS = int(os.getenv('SADIPEM_CACHE_MINUTES', '60')) * 60


class SadipemMGADataStatus:
    COMPLETE = 'Complete'
    PARTIAL = 'Partial'
    UNAVAILABLE = 'Unavailable'


class SadipemApiError(Exception):
    pass


class SadipemCancelled(Exception):
    pass


def _decimal(valor):
    if valor is None:
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Valor numérico inválido no SADIPEM.') from exc
    if not numero.is_finite() or numero < 0:
        raise ValueError('Valor numérico inválido no SADIPEM.')
    return numero


def _data(valor):
    if not valor:
        return datetime.min
    for formato in ('%d/%m/%Y', '%d/%m/%Y %H:%M:%S'):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(valor.replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        return datetime.min


def _normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto or '').lower())
                   if not unicodedata.combining(c))


class SadipemClient:
    """Cliente serial: no máximo uma chamada por segundo, inclusive em retries."""

    def __init__(self, session=None, base_url=BASE_URL, cache_seconds=CACHE_SECONDS,
                 min_interval=1.05, clock=time.monotonic, sleeper=time.sleep):
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip('/') + '/'
        self.cache_seconds = cache_seconds
        self.min_interval = min_interval
        self.clock = clock
        self.sleeper = sleeper
        self._lock = threading.RLock()
        self._ultima = float('-inf')
        self._cache = {}

    def listar(self, endpoint, params=None, cancel_event=None):
        if endpoint not in ('pvl', 'opc-cronograma-liberacoes',
                            'opnc-pvl-tramitacao-deferido', 'opc-cronograma-pagamentos',
                            'res-cronograma-pagamentos', 'res-cdp'):
            raise ValueError('Endpoint SADIPEM não permitido.')
        params = dict(params or {})
        chave = (endpoint, json.dumps(params, sort_keys=True))
        with self._lock:
            salvo = self._cache.get(chave)
            if salvo and self.clock() - salvo[0] < self.cache_seconds:
                return [dict(item) for item in salvo[1]]
            itens, offset = [], 0
            while True:
                dados = self._pagina(endpoint, {**params, 'offset': offset, 'limit': 5000}, cancel_event)
                pagina = dados.get('items')
                if not isinstance(pagina, list):
                    raise SadipemApiError('Resposta sem lista items.')
                itens.extend(pagina)
                if not dados.get('hasMore'):
                    break
                if not pagina:
                    raise SadipemApiError('Paginação vazia com hasMore=true.')
                offset += len(pagina)
            self._cache[chave] = (self.clock(), itens)
            return [dict(item) for item in itens]

    def _pagina(self, endpoint, params, cancel_event):
        for tentativa in range(3):
            if cancel_event is not None and cancel_event.is_set():
                raise SadipemCancelled()
            espera = max(0, self.min_interval - (self.clock() - self._ultima))
            if espera:
                self.sleeper(espera)
            self._ultima = self.clock()
            try:
                resposta = self.session.get(self.base_url + endpoint, params=params, timeout=(8, 20))
                resposta.raise_for_status()
                return resposta.json()
            except (requests.RequestException, ValueError) as exc:
                codigo = getattr(getattr(exc, 'response', None), 'status_code', None)
                if tentativa == 2 or codigo not in (None, 429, 500, 502, 503, 504):
                    raise SadipemApiError(str(exc)) from exc
                self.sleeper(2 ** tentativa)
        raise SadipemApiError('Falha ao consultar o SADIPEM.')


class SadipemPvlService:
    def __init__(self, client):
        self.client = client

    def goias(self, cancel_event=None):
        dados = self.client.listar('pvl', {'q': json.dumps({'uf': 'GO', 'tipo_interessado': 'Estado'})}, cancel_event)
        return [self.dto(item) for item in dados if item.get('uf') == 'GO'
                and _normalizar(item.get('tipo_interessado')) == 'estado'
                and (item.get('cod_ibge') == 52 or
                     _normalizar(item.get('interessado')) in ('goias', 'estado de goias'))]

    @staticmethod
    def dto(item):
        return {'idPleito': item.get('id_pleito'), 'numeroPvl': item.get('num_pvl'),
                'numeroProcesso': item.get('num_processo'), 'interessado': item.get('interessado'),
                'uf': item.get('uf'), 'status': item.get('status'),
                'dataProtocolo': item.get('data_protocolo'), 'dataStatus': item.get('data_status'),
                'tipoOperacao': item.get('tipo_operacao'), 'finalidade': item.get('finalidade'),
                'credor': item.get('credor'), 'moeda': item.get('moeda'), 'valor': item.get('valor'),
                # Grafia confirmada na resposta pública em 06/10/2026.
                'contratadoCredor': item.get('pvl_contradado_credor')}


class SadipemSnapshotSelector:
    def ordenar(self, pvls):
        elegiveis = [p for p in pvls if p.get('idPleito') and p.get('dataProtocolo')
                     and not any(t in _normalizar(p.get('status')) for t in
                                 ('arquivado', 'cancelado', 'rascunho'))]
        return sorted(elegiveis, key=lambda p: (_data(p.get('dataStatus')),
                                                  _data(p.get('dataProtocolo')),
                                                  int(p['idPleito'])), reverse=True)


class SadipemLiberacoesService:
    def __init__(self, client):
        self.client = client

    def por_pvl(self, id_pleito, cancel_event=None):
        dados = self.client.listar('opc-cronograma-liberacoes', {'id_pleito': id_pleito}, cancel_event)
        return [{'idPleito': item.get('id_pleito'), 'numeroPvl': item.get('num_pvl'),
                 'numeroProcesso': item.get('num_processo'),
                 'indicadorLiberacoes': str(item.get('indicador_liberacoes') or '').strip(),
                 'ano': int(item['ano']), 'liberacoesOperacoesSfn': item.get('liberacoes_operacoes_sfn'),
                 'liberacoesAro': item.get('liberacoes_aro'),
                 'liberacoesDemais': item.get('liberacoes_demais'),
                 'liberacoesTotal': item.get('liberacoes_total')}
                for item in dados if item.get('ano') is not None]


class SadipemNonContractedService:
    def __init__(self, client):
        self.client = client

    def por_pvl(self, id_pleito, cancel_event=None):
        dados = self.client.listar('opnc-pvl-tramitacao-deferido', {'id_pleito': id_pleito}, cancel_event)
        # A API inclui liberação anual; preservar ano, status e identificador do PVL relacionado.
        return [{'idPleito': item.get('id_pleito'),
                 'idPleitoNaoContratado': item.get('pleito_nao_contratado'),
                 'numeroPvlNaoContratado': item.get('num_pvl_nao_contratado'),
                 'statusPvlNaoContratado': item.get('status_pvl_nao_contratado'),
                 'ano': int(item['ano_pvl_nao_contratado']) if item.get('ano_pvl_nao_contratado') is not None else None,
                 'liberacaoAnual': item.get('liberacao_pvl_nao_contratado'),
                 'valorTotalPvl': item.get('valor_pvl_nao_contratado')}
                for item in dados]


class SadipemPagamentosService:
    def __init__(self, client):
        self.client = client

    def por_pvl(self, id_pleito, resumo=False, cancel_event=None):
        return self.client.listar('res-cronograma-pagamentos' if resumo else
                                  'opc-cronograma-pagamentos', {'id_pleito': id_pleito}, cancel_event)


class SadipemCdpService:
    def __init__(self, client):
        self.client = client

    def por_pvl(self, id_pleito, cancel_event=None):
        return self.client.listar('res-cdp', {'id_pleito': id_pleito}, cancel_event)


_client = SadipemClient()


def obter_comprometimento_goias(ano, rcl_referencia=None, cancel_event=None, client=None):
    """Retorna a parcela conhecida do snapshot; não conclui MGA/margem integral."""
    cliente = client or _client
    resultado = {'ano': int(ano), 'statusDadosMga': SadipemMGADataStatus.UNAVAILABLE,
                 'motivo': 'NO_PVL', 'snapshot': None, 'liberacoesContratadasSadipem': None,
                 'liberacoesNaoContratadasSadipem': None, 'operacoesNaoContratadas': [],
                 'percentualContratadoRcl': None, 'mgaCompleto': None, 'margemCompleta': None,
                 'ultimaReferenciaHistorica': None,
                 'origem': 'SADIPEM'}
    try:
        pvls = SadipemSnapshotSelector().ordenar(SadipemPvlService(cliente).goias(cancel_event))
        if not pvls:
            return resultado
        # O mais recente elegível representa o snapshot atual. Não agregar fotografias.
        pvl = pvls[0]
        resultado['snapshot'] = {'idPleito': pvl['idPleito'], 'numeroPvl': pvl['numeroPvl'],
                                 'data': pvl['dataStatus'] or pvl['dataProtocolo'],
                                 'status': pvl['status'], 'dataProtocolo': pvl['dataProtocolo'],
                                 'tipoOperacao': pvl['tipoOperacao'], 'finalidade': pvl['finalidade'],
                                 'credor': pvl['credor'], 'moeda': pvl['moeda'],
                                 'valor': pvl['valor']}
        linhas = SadipemLiberacoesService(cliente).por_pvl(pvl['idPleito'], cancel_event)
        nao_contratadas = SadipemNonContractedService(cliente).por_pvl(pvl['idPleito'], cancel_event)
        resultado['operacoesNaoContratadas'] = nao_contratadas
        anuais = [x for x in nao_contratadas if x['ano'] == int(ano)]
        ids = [x['idPleitoNaoContratado'] for x in anuais]
        if (anuais and all(x['liberacaoAnual'] is not None for x in anuais)
                and None not in ids and len(ids) == len(set(ids))):
            resultado['liberacoesNaoContratadasSadipem'] = float(sum(
                (_decimal(x['liberacaoAnual']) for x in anuais), Decimal('0')))
        no_ano = [linha for linha in linhas if linha['ano'] == int(ano)
                  and linha['indicadorLiberacoes'] != '0']
        if not no_ano:
            resultado['motivo'] = 'NO_RELEASES_REPORTED' if any(
                linha['ano'] == int(ano) and linha['indicadorLiberacoes'] == '0'
                for linha in linhas) else 'NO_DATA'
            # Mostrar a última fotografia com cronograma somente como referência
            # histórica. Nunca aproveitá-la como comprometimento do ano atual.
            for candidato in pvls[1:6]:
                try:
                    antigas = SadipemLiberacoesService(cliente).por_pvl(candidato['idPleito'], cancel_event)
                except SadipemApiError as exc:
                    log.warning('Consulta histórica SADIPEM indisponível.', details=str(exc))
                    break
                validas = [linha for linha in antigas if linha['ano'] <= int(ano)
                           and linha['indicadorLiberacoes'] != '0'
                           and linha['liberacoesTotal'] is not None]
                if not validas:
                    continue
                ultima = max(validas, key=lambda linha: linha['ano'])
                resultado['ultimaReferenciaHistorica'] = {
                    'ano': ultima['ano'], 'valor': float(_decimal(ultima['liberacoesTotal'])),
                    'idPleito': candidato['idPleito'], 'numeroPvl': candidato['numeroPvl'],
                    'dataSnapshot': candidato['dataStatus'] or candidato['dataProtocolo']}
                break
            return resultado
        # A aba é um agregado do PVL, não uma linha por operação. Mais de uma linha
        # para o mesmo ano seria ambígua: não somar nem escolher silenciosamente.
        if len(no_ano) != 1 or no_ano[0]['liberacoesTotal'] is None:
            resultado['motivo'] = 'AMBIGUOUS_DATA'
            return resultado
        valor = _decimal(no_ano[0]['liberacoesTotal'])
        resultado['liberacoesContratadasSadipem'] = float(valor)
        resultado['statusDadosMga'] = SadipemMGADataStatus.PARTIAL
        resultado['motivo'] = 'CONTRACTED_ONLY'
        # As linhas de não contratadas têm liberações anuais reais, mas a cobertura
        # de todos os PVLs relevantes não pode ser presumida do snapshot público.
        rcl = _decimal(rcl_referencia)
        if rcl is not None and rcl > 0:
            # Apenas razão indicativa com a RCL publicada; não é MGA/RCL projetada.
            resultado['percentualContratadoRclReferencia'] = float(valor / rcl * 100)
        return resultado
    except SadipemCancelled:
        resultado['motivo'] = 'CANCELLED'
        return resultado
    except (SadipemApiError, ValueError) as exc:
        log.error('Falha na consulta ao SADIPEM.', details=str(exc))
        resultado['motivo'] = 'API_ERROR'
        return resultado


def simular_fluxo_goias(linhas, client=None):
    """Cenário informado: nunca equivale a uma verificação oficial do MGA."""
    from .fluxo_credito import CreditFlowLimitService

    if not isinstance(linhas, list) or not 1 <= len(linhas) <= 30:
        raise ValueError('Informe entre um e 30 exercícios.')
    vistos, resultados = set(), []
    for entrada in linhas:
        ano = int(entrada['ano'])
        if ano in vistos or not 2020 <= ano <= 2100:
            raise ValueError('Exercícios duplicados ou inválidos.')
        vistos.add(ano)
        rcl = _decimal(entrada.get('rclProjetada'))
        nova = _decimal(entrada.get('liberacaoNovaOperacao'))
        manual = _decimal(entrada.get('liberacoesNaoContratadasManual'))
        sadipem = obter_comprometimento_goias(ano, client=client)
        contratadas = sadipem['liberacoesContratadasSadipem']
        nao_contratadas = sadipem['liberacoesNaoContratadasSadipem']
        fonte_nao_contratadas = 'SADIPEM' if nao_contratadas is not None else None
        if nao_contratadas is None and manual is not None:
            nao_contratadas = float(manual)
            fonte_nao_contratadas = 'Informado pelo usuário'
        avaliado = CreditFlowLimitService().avaliar(
            ano, rcl_projetada={ano: rcl} if rcl is not None else None,
            liberacoes_contratadas={ano: contratadas} if contratadas is not None else None,
            liberacoes_nao_contratadas={ano: nao_contratadas} if nao_contratadas is not None else None,
            liberacoes_analisadas={ano: nova})
        resultados.append({'ano': ano, 'snapshot': sadipem['snapshot'],
                           'motivoSadipem': sadipem['motivo'],
                           'fonteNaoContratadas': fonte_nao_contratadas,
                           'statusDadosMga': SadipemMGADataStatus.PARTIAL if avaliado['dadosCompletos']
                           else SadipemMGADataStatus.UNAVAILABLE,
                           'cenario': avaliado})
    return resultados
