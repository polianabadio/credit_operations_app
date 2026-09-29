"""Atualização em segundo plano; a interface permanece disponível."""
from threading import Lock, Thread
from .data_updater import atualizar_operacoes_rreo, atualizar_operacoes_rgf
from .logger import log

_lock = Lock()
_estado = {'running': False, 'etapa': '', 'concluidas': 0, 'total': 0, 'falhas': 0}


def status_atualizacao():
    with _lock:
        return dict(_estado)


def _progresso(concluidas, total):
    with _lock:
        _estado.update(concluidas=concluidas, total=total)


def _executar():
    try:
        for escopo, label in [('now', 'Ano atual'), ('all', 'Histórico')]:
            for nome, atualizar in [('RREO', atualizar_operacoes_rreo), ('RGF', atualizar_operacoes_rgf)]:
                with _lock:
                    _estado.update(etapa=f'{label} — {nome}', concluidas=0, total=0)
                resultado = atualizar(escopo, progresso=_progresso)
                with _lock:
                    _estado['falhas'] += len(resultado.get('falhas', []))
    except Exception as exc:
        log.error('Falha na sincronização.', details=str(exc))
        with _lock:
            _estado['falhas'] += 1
    finally:
        with _lock:
            _estado['running'] = False


def iniciar_atualizacao():
    with _lock:
        if _estado['running']:
            return dict(_estado)
        _estado.update(running=True, etapa='Iniciando', concluidas=0, total=0, falhas=0)
        Thread(target=_executar, daemon=True).start()
        return dict(_estado)
