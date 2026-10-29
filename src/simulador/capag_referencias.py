"""Referências complementares documentadas, independentes das notas da STN."""
import json
from decimal import Decimal, InvalidOperation
from .config import get_config_file_path
from .logger import log


def obter_referencias_indicadores():
    caminho = get_config_file_path('instance/referencias_capag.json')
    if not caminho.exists():
        return []
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8-sig'))
        referencias = []
        anos = set()
        for item in dados['referencias']:
            ano = item['ano_referencia']
            if item.get('ente') != 52 or type(ano) is not int or ano in anos:
                raise ValueError('Ente, exercício ou duplicidade inválida na referência CAPAG.')
            if (not item.get('fonte', '').startswith('https://goias.gov.br/')
                    or not item.get('documento') or not item.get('pagina')
                    or item.get('tipo') != 'referencia_estadual' or not item.get('consultado_em')):
                raise ValueError('Proveniência incompleta na referência CAPAG.')
            valores = {}
            for chave in ('endividamento', 'poupanca_corrente', 'liquidez_relativa'):
                valor = Decimal(str(item['indicadores'][chave]))
                if not valor.is_finite():
                    raise ValueError('Percentual inválido na referência CAPAG.')
                valores[chave] = str(valor)
            referencias.append({**item, 'indicadores': valores})
            anos.add(ano)
        return referencias
    except (OSError, ValueError, TypeError, KeyError, InvalidOperation) as exc:
        log.warning('Referência complementar CAPAG não carregada.', details=str(exc))
        return []


def obter_notas_documentais():
    caminho = get_config_file_path('instance/referencias_capag.json')
    if not caminho.exists():
        return []
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8-sig'))
        referencias = []
        anos = set()
        for item in dados.get('notas_documentais', []):
            if (item.get('ente') != 52 or item.get('tipo') != 'serie_retrospectiva'
                    or not item.get('fonte', '').startswith('https://cdn.tesouro.gov.br/')
                    or not item.get('documento') or not item.get('pagina')
                    or not item.get('consultado_em') or type(item.get('ano_documento')) is not int):
                raise ValueError('Proveniência inválida na série documental CAPAG.')
            for ano_texto, nota in item['notas'].items():
                ano = int(ano_texto)
                if ano in anos or not 1900 <= ano <= item['ano_documento'] or nota not in {'A+', 'A', 'B+', 'B', 'C', 'D', 'N.D.'}:
                    raise ValueError('Ano ou nota inválidos na série documental CAPAG.')
                referencias.append({k: v for k, v in item.items() if k != 'notas'} | {'ano': ano, 'nota': nota})
                anos.add(ano)
        return sorted(referencias, key=lambda item: item['ano'])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        log.warning('Série documental CAPAG não carregada.', details=str(exc))
        return []
