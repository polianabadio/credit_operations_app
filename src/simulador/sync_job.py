"""Atualização em segundo plano; a interface permanece disponível."""
from threading import Lock, Thread
from .data_updater import atualizar_operacoes_rreo, atualizar_operacoes_rgf
from .capag import atualizar_capag
from .logger import log

_lock = Lock()
_estado = {'running': False, 'etapa': '', 'concluidas': 0, 'total': 0,
           'falhas': 0, 'detalhes_falhas': []}


def status_atualizacao():
    with _lock:
        return {**_estado, 'detalhes_falhas': [dict(falha) for falha in _estado['detalhes_falhas']]}


def _progresso(concluidas, total):
    with _lock:
        _estado.update(concluidas=concluidas, total=total)


def _atualizar_capag_em_paralelo():
    try:
        atualizar_capag()
    except Exception as exc:
        log.warning('CAPAG não pôde ser atualizada.', details=str(exc))


def _executar(automatico=False):
    try:
        tarefa_capag = Thread(target=_atualizar_capag_em_paralelo, daemon=True)
        tarefa_capag.start()
        escopos = [('now', 'Ano atual')]
        if not automatico: escopos.append(('past', 'Histórico'))
        for escopo, label in escopos:
            for nome, atualizar in [('RREO', atualizar_operacoes_rreo), ('RGF', atualizar_operacoes_rgf)]:
                with _lock:
                    _estado.update(etapa=f'{label} — {nome}', concluidas=0, total=0)
                resultado = atualizar(escopo, progresso=_progresso)
                with _lock:
                    _estado['falhas'] += len(resultado.get('falhas', []))
                    for falha in resultado.get('falhas', [])[:3]:
                        _estado['detalhes_falhas'].append({
                            'etapa': f'{label} — {nome}',
                            'ano': falha.get('an_exercicio'),
                            'periodo': falha.get('nr_periodo'),
                            'anexo': falha.get('no_anexo'),
                            'poder': falha.get('co_poder'),
                            'motivo': 'Não foi possível concluir a atualização desses dados. Tente novamente mais tarde.',
                        })
                    _estado['detalhes_falhas'] = _estado['detalhes_falhas'][:3]
        if not automatico:
            with _lock: _estado.update(etapa='CAPAG', concluidas=0, total=0)
            tarefa_capag.join()
    except Exception as exc:
        log.error('Falha na sincronização.', details=str(exc))
        with _lock:
            _estado['falhas'] += 1
            _estado['detalhes_falhas'].append({'etapa': _estado['etapa'],
                                               'motivo': 'A atualização foi interrompida. Tente novamente mais tarde.'})
            _estado['detalhes_falhas'] = _estado['detalhes_falhas'][:3]
    finally:
        with _lock:
            _estado['running'] = False


def iniciar_atualizacao(automatico=False):
    with _lock:
        if _estado['running']:
            return {**_estado, 'detalhes_falhas': [dict(falha) for falha in _estado['detalhes_falhas']]}
        _estado.update(running=True, etapa='Iniciando', concluidas=0, total=0,
                       falhas=0, detalhes_falhas=[])
        tarefa = (lambda: _executar(automatico=True)) if automatico else _executar
        Thread(target=tarefa, daemon=True).start()
        return {**_estado, 'detalhes_falhas': []}
