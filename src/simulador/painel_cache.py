"""Cache derivado exclusivamente da posição pública, invalidado pela base fiscal.

Não armazena simulações. Uma alteração no JSON, data ou versão invalida o painel.
"""
import copy
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from threading import RLock

from .database_models import db, RREO
from .config import APP_VERSION

_mutex = RLock()
_memoria = {}


def _assinatura(bind):
    try:
        info = bind.caminho.stat()
        arquivo = [info.st_mtime_ns, info.st_size]
    except FileNotFoundError:
        arquivo = None
    return [APP_VERSION, date.today().isoformat(), str(bind.caminho), arquivo]


def _compor():
    from .painel_fiscal import obter_painel_fiscal
    from .mga_projection import obter_projecao
    painel = obter_painel_fiscal()
    if painel.get('exercicio') is not None:
        painel['fluxo_credito'] = obter_projecao(painel)
    anos = [r[0] for r in db.session.query(RREO.exercicio).distinct().order_by(RREO.exercicio.desc()).all()]
    return painel, anos


def _registro():
    bind = db.session.get_bind()
    if not getattr(bind, 'json_store', False):
        painel, anos = _compor()
        return {'painel': painel, 'anos': anos}
    chave = str(bind.caminho)
    caminho = bind.caminho.with_name('painel-fiscal.json')
    with _mutex:
        assinatura = _assinatura(bind)
        registro = _memoria.get(chave)
        if registro and registro.get('assinatura') == assinatura:
            return registro
        try:
            registro = json.loads(caminho.read_text(encoding='utf-8'))
            if (registro.get('assinatura') == assinatura and isinstance(registro.get('painel'), dict)
                    and isinstance(registro.get('anos'), list)):
                _memoria[chave] = registro
                return registro
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        painel, anos = _compor()
        registro = {'assinatura': assinatura, 'painel': painel, 'anos': anos}
        if _assinatura(bind) == assinatura:
            _memoria[chave] = registro
            temporario = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=caminho.parent,
                                                 suffix='.tmp', delete=False) as arquivo:
                    temporario = Path(arquivo.name)
                    arquivo.write(json.dumps(registro, ensure_ascii=False, allow_nan=False))
                os.replace(temporario, caminho)
            except OSError:
                pass  # Falha em cache derivado não elimina os dados válidos já calculados.
            finally:
                if temporario is not None:
                    temporario.unlink(missing_ok=True)
        return registro


def obter_painel_fiscal_em_cache():
    return copy.deepcopy(_registro()['painel'])


def obter_anos_fiscais_em_cache():
    return list(_registro()['anos'])
