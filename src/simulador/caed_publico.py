"""Pagamentos declarados em um único PVL, sem atestar cobertura integral."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from .logger import log
from .sadipem import (SadipemPvlService, SadipemSnapshotSelector,
                      SadipemPagamentosService, _client, _data)
from .servico_divida import valor_monetario


def assinatura_pagamentos(referencia):
    """Vincula a declaração aos valores anuais e ao PVL, sem incluir hora da consulta."""
    dados = {'snapshot': referencia.get('snapshot'),
             'pagamentos': {str(ano): format(valor_monetario(valor, 'pagamento'), '.2f')
                            for ano, valor in referencia.get('pagamentos', {}).items()},
             'saldos_sem_ano': referencia.get('saldos_sem_ano', [])}
    return sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def caminho_confirmacao():
    from .config import get_config_file_path
    return get_config_file_path('instance/confirmacao_caed.json')


def registrar_confirmacao(referencia, ano, fim, data_referencia, caminho=None):
    """Somente para declaração explícita do usuário; não chamar ao consultar a API."""
    if not referencia.get('snapshot') or referencia.get('motivos') or any(
            a not in referencia.get('pagamentos', {}) for a in range(ano, fim + 1)):
        raise ValueError('A confirmação exige pagamentos válidos em todos os anos da análise.')
    registro = {'assinatura': assinatura_pagamentos(referencia), 'ano': ano, 'fim': fim,
                'completa': True, 'fonte': referencia['fonte'], 'data_referencia': data_referencia,
                'origem_confirmacao': 'Declaração explícita do usuário',
                'registrada_em': datetime.now().isoformat(timespec='seconds')}
    destino = Path(caminho) if caminho else caminho_confirmacao()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding='utf-8')
    return registro


def obter_confirmacao(referencia, ano, fim, caminho=None):
    """Mudança de PVL, valores ou intervalo exige nova declaração."""
    destino = Path(caminho) if caminho else caminho_confirmacao()
    try:
        registro = json.loads(destino.read_text(encoding='utf-8'))
        if not isinstance(registro, dict):
            return None
        if (registro.get('completa') is True and registro.get('ano') == ano and registro.get('fim') == fim
                and registro.get('assinatura') == assinatura_pagamentos(referencia)):
            return registro
    except (OSError, ValueError, TypeError):
        pass
    return None


def obter_pagamentos_caed(ano, fim, data_referencia, client=None):
    """Não usa a operação do PVL como se fosse a nova operação simulada."""
    cliente = client or _client
    referencia = datetime.fromisoformat(data_referencia)
    resultado = {'fonte': 'SADIPEM / res-cronograma-pagamentos', 'snapshot': None,
                 'consultado_em': datetime.now().isoformat(timespec='seconds'),
                 'pagamentos': {}, 'saldos_sem_ano': [], 'cobertura_confirmada': False, 'motivos': []}
    try:
        pvls = SadipemSnapshotSelector().ordenar(SadipemPvlService(cliente).goias())
        if not pvls:
            resultado['motivos'].append('Não há PVL disponível para consultar os pagamentos.')
            return resultado
        pvl = pvls[0]
        resultado['snapshot'] = {'idPleito': pvl['idPleito'], 'numeroPvl': pvl['numeroPvl'],
                                 'data': pvl['dataStatus'] or pvl['dataProtocolo']}
        protocolo = _data(pvl['dataProtocolo'])
        atualizacao = _data(pvl['dataStatus'] or pvl['dataProtocolo'])
        if protocolo.year != ano or max(protocolo, atualizacao) > referencia.replace(hour=23, minute=59, second=59):
            resultado['motivos'].append('O PVL disponível não corresponde à data da análise.')
            return resultado
        registros = SadipemPagamentosService(cliente).por_pvl(pvl['idPleito'], resumo=True)
        por_ano = {}
        for registro in registros:
            if str(registro.get('id_pleito')) != str(pvl['idPleito']):
                raise ValueError('A consulta retornou pagamentos de outro PVL.')
            if str(registro.get('ano') or '').strip().casefold() == 'restante a pagar':
                resultado['saldos_sem_ano'].append({
                    'rotulo': registro['ano'],
                    'demais_operacoes': str(valor_monetario(registro.get('demais_operacoes'), 'saldo restante'))})
                continue
            exercicio = int(registro['ano'])
            if ano <= exercicio <= fim:
                por_ano.setdefault(exercicio, []).append(registro)
        for exercicio, linhas in por_ano.items():
            if len(linhas) != 1:
                resultado['motivos'].append(f'Pagamentos conflitantes em {exercicio}.')
                continue
            try:
                valor = valor_monetario(linhas[0].get('demais_operacoes'), 'pagamentos das demais operações')
                resultado['pagamentos'][exercicio] = str(valor)
            except ValueError:
                resultado['motivos'].append(f'Pagamentos não informados ou inválidos em {exercicio}.')
    except Exception as exc:
        log.error('Falha na consulta de pagamentos CAED.', details=str(exc))
        resultado['pagamentos'] = {}
        resultado['motivos'].append('Não foi possível consultar os pagamentos no SADIPEM agora.')
    return resultado


def integrar_pagamentos_caed(entrada, referencia):
    """Preenche apenas anos desconhecidos; conserva fonte e ausência de confirmação."""
    linhas = []
    for linha in entrada['linhas']:
        nova = dict(linha)
        if nova.get('demais_operacoes') is None:
            nova['demais_operacoes'] = referencia.get('pagamentos', {}).get(linha['ano'])
        linhas.append(nova)
    return {**entrada, 'linhas': linhas, 'referencia_publica_demais': referencia}
