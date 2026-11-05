"""Cache JSON transacional, sem engine SQL ou arquivo de banco de dados.

Mantém os descritores de modelos legados somente para preservar os contratos de
consulta; expressões não suportadas falham explicitamente, nunca são ignoradas.
"""
import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import DateTime, Numeric
from sqlalchemy.orm import Session as SessaoSqlLegada
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BindParameter, BooleanClauseList, Null, UnaryExpression, Label
from sqlalchemy.sql.functions import Function

from .database_models import Base


def _modelos():
    return {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}


def _serializar(objeto):
    return {col.name: (str(valor) if isinstance(valor, Decimal) else valor.isoformat()
                      if isinstance(valor, datetime) else valor)
            for col in objeto.__table__.columns
            for valor in [getattr(objeto, col.name)]}


def _objeto(modelo, dado):
    valores = dict(dado)
    for coluna in modelo.__table__.columns:
        valor = valores.get(coluna.name)
        if valor is not None and isinstance(coluna.type, Numeric):
            valores[coluna.name] = Decimal(str(valor))
        elif valor is not None and isinstance(coluna.type, DateTime):
            valores[coluna.name] = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
    return modelo(**valores)


def _pk(modelo, objeto):
    return tuple(getattr(objeto, coluna.name) for coluna in modelo.__table__.primary_key)


class CacheJson:
    json_store = True

    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._mutex = threading.RLock()
        self._writer_mutex = threading.RLock()
        self._assinatura = None
        self._dados = {'versao': 1, 'tabelas': {}}
        self._documento_indices = None
        self._indices = {}

    def ler(self):
        with self._mutex:
            try:
                stat = self.caminho.stat()
            except FileNotFoundError:
                return {'versao': 1, 'tabelas': {}}
            assinatura = (stat.st_mtime_ns, stat.st_size)
            if assinatura != self._assinatura:
                # JSON inválido nunca é substituído automaticamente por cache vazio.
                with self.caminho.open(encoding='utf-8') as arquivo:
                    dados = json.load(arquivo)
                if dados.get('versao') != 1 or not isinstance(dados.get('tabelas'), dict):
                    raise ValueError('Cache JSON inválido; restaure uma cópia íntegra.')
                self._dados, self._assinatura = dados, assinatura
            return self._dados

    def selecionar(self, modelo, filtros, dados):
        """Índices em memória; a fonte e os filtros completos continuam os mesmos."""
        with self._mutex:
            if self._documento_indices is not dados:
                self._documento_indices, self._indices = dados, {}
            objetos = dados['tabelas'].get(modelo.__tablename__, [])
            candidatos = objetos
            for filtro in filtros:
                if not hasattr(filtro, 'left') or not isinstance(filtro.right, BindParameter):
                    continue
                coluna = filtro.left
                if not hasattr(coluna, 'table') or coluna.table is None or coluna.table.name != modelo.__tablename__:
                    continue
                if isinstance(coluna.type, (Numeric, DateTime)):
                    continue
                if filtro.operator not in (operators.eq, operators.in_op):
                    continue
                chave = (modelo.__tablename__, coluna.key)
                if chave not in self._indices:
                    indice = {}
                    for item in objetos:
                        indice.setdefault(item.get(coluna.key), []).append(item)
                    self._indices[chave] = indice
                indice = self._indices[chave]
                valor = filtro.right.value
                encontrados = (indice.get(valor, []) if filtro.operator is operators.eq else
                               [item for v in set(valor) for item in indice.get(v, [])])
                if len(encontrados) < len(candidatos): candidatos = encontrados
            return candidatos

    @contextmanager
    def escrita(self):
        with self._writer_mutex:
            lock = self.caminho.with_suffix('.lock')
            with lock.open('a+b') as arquivo:
                arquivo.seek(0, 2)
                if arquivo.tell() == 0:
                    arquivo.write(b'1'); arquivo.flush()
                prazo = time.monotonic() + 45
                while True:
                    try:
                        arquivo.seek(0)
                        if os.name == 'nt':
                            import msvcrt
                            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() >= prazo:
                            raise TimeoutError('Outra máquina está atualizando o cache. Tente novamente.')
                        time.sleep(.1)
                try:
                    self._assinatura = None
                    yield
                finally:
                    arquivo.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)

    def salvar(self, dados):
        fd, nome = tempfile.mkstemp(prefix='cache-', suffix='.tmp', dir=self.caminho.parent)
        temporario = Path(nome)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as arquivo:
                arquivo.write(json.dumps(dados, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
                arquivo.flush(); os.fsync(arquivo.fileno())
            for tentativa in range(30):
                try:
                    os.replace(temporario, self.caminho)
                    break
                except PermissionError:
                    if tentativa == 29:
                        raise
                    time.sleep(.1)
            self._assinatura = None
        finally:
            temporario.unlink(missing_ok=True)


class SessaoJson:
    json_store = True

    def __init__(self, bind):
        self.bind = bind
        self._contexto = None
        self._transacao = None
        self._rastreados = {}
        self._apagados = {}
        self._ids = {}
        self._originais = {}
        self._em_contexto = False

    def __enter__(self):
        self._em_contexto = True
        return self

    def _iniciar_escrita(self):
        if self._contexto is None:
            self._contexto = self.bind.escrita()
            self._contexto.__enter__()
            self._transacao = self.bind.ler()
            self._ids.clear()

    def __exit__(self, *erro):
        self.rollback()
        self._em_contexto = False

    def get_bind(self): return self.bind

    def registros(self, modelo):
        dados = self._transacao if self._transacao is not None else self.bind.ler()
        nome = modelo.__tablename__
        objetos = [_objeto(modelo, item) for item in dados['tabelas'].get(nome, [])]
        if self._transacao is not None:
            rastreados = self._rastreados.setdefault(nome, {})
            objetos = [rastreados.setdefault(_pk(modelo, obj), obj) for obj in objetos]
            objetos = [o for o in objetos if _pk(modelo, o) not in self._apagados.get(nome, set())]
            existentes = {_pk(modelo, obj) for obj in objetos}
            objetos.extend(obj for chave, obj in rastreados.items()
                           if chave not in existentes and chave not in self._apagados.get(nome, set()))
        return objetos

    def query(self, *campos): return ConsultaJson(self, campos)

    def get(self, modelo, chave):
        chave = chave if isinstance(chave, tuple) else (chave,)
        objetos = self.registros(modelo)
        objeto = next((o for o in objetos if _pk(modelo, o) == chave), None)
        if objeto is not None:
            self._rastreados.setdefault(modelo.__tablename__, {})[chave] = objeto
            self._originais.setdefault(modelo.__tablename__, {})[chave] = _serializar(objeto)
        return objeto

    def add(self, objeto):
        self._iniciar_escrita()
        modelo = type(objeto)
        for coluna in modelo.__table__.columns:
            if getattr(objeto, coluna.name) is None and coluna.default is not None and coluna.default.is_scalar:
                setattr(objeto, coluna.name, coluna.default.arg)
        if hasattr(modelo, 'id'):
            nome = modelo.__tablename__
            if nome not in self._ids:
                dados = self._transacao if self._transacao is not None else self.bind.ler()
                self._ids[nome] = max([0, *[r.get('id') or 0 for r in dados['tabelas'].get(nome, [])]])
            if objeto.id is None:
                self._ids[nome] += 1
                objeto.id = self._ids[nome]
            else:
                self._ids[nome] = max(self._ids[nome], objeto.id)
        self._rastreados.setdefault(modelo.__tablename__, {})[_pk(modelo, objeto)] = objeto

    def add_all(self, objetos):
        for objeto in objetos: self.add(objeto)

    def merge(self, objeto): self.add(objeto); return objeto
    def flush(self): pass

    def bulk_insert_mappings(self, modelo, registros):
        campos = {coluna.name for coluna in modelo.__table__.columns}
        for registro in registros:
            self.add(modelo(**{chave: valor for chave, valor in registro.items() if chave in campos}))

    def _gravar(self):
        base = self._transacao if self._transacao is not None else self.bind.ler()
        dados = {**base, 'tabelas': dict(base['tabelas'])}
        modelos = _modelos()
        for nome in self._rastreados.keys() | self._apagados.keys():
            modelo = modelos[nome]
            por_chave = {tuple(item.get(c.name) for c in modelo.__table__.primary_key): item
                         for item in dados['tabelas'].get(nome, [])}
            for chave in self._apagados.get(nome, set()): por_chave.pop(chave, None)
            for chave, objeto in self._rastreados.get(nome, {}).items():
                serializado = _serializar(objeto)
                if (chave not in self._apagados.get(nome, set())
                        and serializado != self._originais.get(nome, {}).get(chave)):
                    por_chave[chave] = serializado
            dados['tabelas'][nome] = list(por_chave.values())
        self.bind.salvar(dados)
        if self._transacao is not None: self._transacao = dados
        self._rastreados.clear(); self._apagados.clear()

    def commit(self):
        self._iniciar_escrita()
        try:
            self._gravar()
        finally:
            self.rollback()

    def rollback(self):
        self._rastreados.clear(); self._apagados.clear(); self._originais.clear()
        self._transacao = None
        self._ids.clear()
        if self._contexto is not None:
            contexto, self._contexto = self._contexto, None
            contexto.__exit__(None, None, None)

    def close(self): self.rollback()
    def expire_all(self): pass


def _valor(expressao, contexto):
    if isinstance(expressao, BindParameter): return expressao.value
    if isinstance(expressao, Null): return None
    if isinstance(expressao, Label): return _valor(expressao.element, contexto)
    if isinstance(expressao, BooleanClauseList):
        valores = [_valor(c, contexto) for c in expressao.clauses]
        return all(valores) if expressao.operator is operators.and_ else any(valores)
    if hasattr(expressao, 'left') and hasattr(expressao, 'right'):
        esquerda, direita = _valor(expressao.left, contexto), _valor(expressao.right, contexto)
        op = expressao.operator
        if op is operators.is_: return esquerda is direita
        if op is operators.is_not: return esquerda is not direita
        if op is operators.in_op: return esquerda in direita
        if op is operators.not_in_op: return esquerda not in direita
        if esquerda is None or direita is None: return False
        if op in (operators.eq, operators.ne, operators.lt, operators.le, operators.gt, operators.ge):
            return op(esquerda, direita)
        raise NotImplementedError(f'Comparação não suportada pelo cache: {op}')
    if hasattr(expressao, 'table') and expressao.table is not None:
        objeto = contexto[expressao.table.name]
        valor = objeto.get(expressao.key) if isinstance(objeto, dict) else getattr(objeto, expressao.key)
        if valor is not None and isinstance(expressao.type, DateTime) and isinstance(valor, str):
            return datetime.fromisoformat(valor)
        return Decimal(str(valor)) if valor is not None and isinstance(expressao.type, Numeric) else valor
    if hasattr(expressao, 'element'): return _valor(expressao.element, contexto)
    raise NotImplementedError(f'Expressão não suportada pelo cache: {expressao}')


class ConsultaJson:
    def __init__(self, sessao, campos):
        self.sessao, self.campos = sessao, campos
        alvo = campos[0]
        self.modelo = alvo if isinstance(alvo, type) else _modelos()[alvo._from_objects[0].name]
        self.filtros, self.ordem, self.juncoes = [], [], []
        self.distinta = False

    def filter(self, *filtros): self.filtros.extend(filtros); return self
    def filter_by(self, **valores): return self.filter(*(getattr(self.modelo, k) == v for k, v in valores.items()))
    def order_by(self, *ordem): self.ordem.extend(ordem); return self
    def distinct(self): self.distinta = True; return self
    def join(self, modelo): self.juncoes.append(modelo); return self

    def _linhas(self):
        dados = self.sessao._transacao if self.sessao._transacao is not None else self.sessao.bind.ler()
        objetos = (dados['tabelas'].get(self.modelo.__tablename__, []) if self.sessao._transacao is not None
                   else self.sessao.bind.selecionar(self.modelo, self.filtros, dados))
        if self.sessao._transacao is not None:
            nome = self.modelo.__tablename__
            por_chave = {tuple(item.get(c.name) for c in self.modelo.__table__.primary_key): item for item in objetos}
            por_chave.update({chave: _serializar(obj) for chave, obj in self.sessao._rastreados.get(nome, {}).items()})
            objetos = [obj for chave, obj in por_chave.items() if chave not in self.sessao._apagados.get(nome, set())]
        linhas = [{self.modelo.__tablename__: obj} for obj in objetos]
        for modelo in self.juncoes:
            pais = {o.id: o for o in self.sessao.registros(modelo)}
            def id_pai(linha):
                obj = linha[self.modelo.__tablename__]
                return obj.get('operacao_id') if isinstance(obj, dict) else obj.operacao_id
            linhas = [{**linha, modelo.__tablename__: pais[id_pai(linha)]}
                      for linha in linhas if id_pai(linha) in pais]
        linhas = [l for l in linhas if all(_valor(f, l) for f in self.filtros)]
        for ordem in reversed(self.ordem):
            desc = isinstance(ordem, UnaryExpression) and ordem.modifier is operators.desc_op
            campo = ordem.element if isinstance(ordem, UnaryExpression) else ordem
            linhas.sort(key=lambda l: (_valor(campo, l) is not None, _valor(campo, l)), reverse=desc)
        return linhas

    def all(self):
        linhas = self._linhas()
        if isinstance(self.campos[0], type):
            return [_objeto(self.modelo, l[self.modelo.__tablename__]) if isinstance(l[self.modelo.__tablename__], dict)
                    else l[self.modelo.__tablename__] for l in linhas]
        if isinstance(self.campos[0], Function):
            funcao = self.campos[0]
            if funcao.name != 'max': raise NotImplementedError(funcao.name)
            campo = list(funcao.clauses)[0]
            valores = [_valor(campo, l) for l in linhas if _valor(campo, l) is not None]
            return [(max(valores) if valores else None,)]
        valores = [tuple(_valor(c, l) for c in self.campos) for l in linhas]
        return list(dict.fromkeys(valores)) if self.distinta else valores

    def first(self): return next(iter(self.all()), None)
    def scalar(self):
        linha = self.first()
        return linha[0] if linha is not None else None
    def one_or_none(self):
        linhas = self.all()
        if len(linhas) > 1: raise ValueError('Registros ambíguos no cache JSON.')
        if linhas and self.modelo.__tablename__ == 'operacao_credito':
            chave = _pk(self.modelo, linhas[0])
            self.sessao._rastreados.setdefault(self.modelo.__tablename__, {})[chave] = linhas[0]
            self.sessao._originais.setdefault(self.modelo.__tablename__, {})[chave] = _serializar(linhas[0])
        return linhas[0] if linhas else None
    def count(self): return len(self.all())
    def delete(self, **kwargs):
        self.sessao._iniciar_escrita()
        linhas = self._linhas()
        for linha in linhas:
            obj = linha[self.modelo.__tablename__]
            if isinstance(obj, dict): obj = _objeto(self.modelo, obj)
            self.sessao._apagados.setdefault(self.modelo.__tablename__, set()).add(_pk(self.modelo, obj))
        return len(linhas)


def Session(bind):
    return SessaoJson(bind) if isinstance(bind, CacheJson) else SessaoSqlLegada(bind=bind)


def garantir_tabela(modelo, engine):
    if not isinstance(engine, CacheJson): modelo.__table__.create(engine, checkfirst=True)


def ultimos_registros(modelo, anos):
    from .database_models import db
    consulta = db.session.query(modelo).filter(modelo.exercicio.in_(anos))
    linhas = consulta._linhas()
    nome = modelo.__tablename__
    periodos = {}
    for contexto in linhas:
        item = contexto[nome]
        chave = item['exercicio'], item['anexo']
        periodos[chave] = max(periodos.get(chave, 0), item['periodo'])
    return [SimpleNamespace(exercicio=item['exercicio'], anexo=item['anexo'],
                            periodo=item['periodo'], coluna=item.get('coluna'), conta=item.get('conta'),
                            valor=Decimal(str(item['valor'])) if item.get('valor') is not None else None)
            for contexto in linhas for item in [contexto[nome]]
            if item['periodo'] == periodos[item['exercicio'], item['anexo']]]
