"""Paridade fiscal e transaÃ§Ãµes do cache JSON, sem banco da aplicaÃ§Ã£o."""
from datetime import datetime
from decimal import Decimal
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SqlSession
from src.simulador.cache_json import CacheJson, SessaoJson, Session
from src.simulador.database_models import Base, db, RREO, RGF, SincronizacaoSiconfi, ParametroSimulacao
from src.simulador.data_access import obter_dados_rreo_para_analise, obter_dados_rgf_para_analise


@pytest.fixture
def cache(tmp_path):
    return CacheJson(tmp_path / 'dados-fiscais.json')


def rreo(ano=2026,periodo=1,valor='12.34'):
    return RREO(exercicio=ano,periodo=periodo,demonstrativo='RREO',instituicao='GO',
                uf='GO',esfera='E',anexo='RREO-Anexo 01',conta='Conta',coluna='Coluna',valor=Decimal(valor))


def test_grava_decimal_data_zero_e_consulta_sem_criar_banco(cache):
    with Session(cache) as s:
        s.add(rreo(valor='0'))
        s.merge(SincronizacaoSiconfi(chave='ref',consultado_em=datetime(2026,11,5),quantidade=1))
        s.commit()
    outra=SessaoJson(CacheJson(cache.caminho))
    assert outra.query(RREO).filter(RREO.valor.isnot(None),RREO.exercicio==2026).first().valor==Decimal('0')
    assert outra.get(SincronizacaoSiconfi,'ref').consultado_em==datetime(2026,11,5)
    assert outra.query(SincronizacaoSiconfi.consultado_em).first()[0]==datetime(2026,11,5)
    assert list(cache.caminho.parent.glob('*.db'))==[]
    assert json.loads(cache.caminho.read_text(encoding='utf-8'))['tabelas']['rreo'][0]['valor']=='0'


def test_transacao_substitui_periodo_sem_duplicar_ou_perder_outro(cache):
    with Session(cache) as s:
        s.add_all([rreo(periodo=1),rreo(periodo=2)])
        s.commit()
    with Session(cache) as s:
        s.query(RREO).filter(RREO.periodo==2).delete()
        s.bulk_insert_mappings(RREO,[dict(exercicio=2026,periodo=2,demonstrativo='RREO',
            instituicao='GO',uf='GO',esfera='E',anexo='RREO-Anexo 01',conta='Conta',coluna='Coluna',valor='99.99')])
        s.commit()
    rows=SessaoJson(cache).query(RREO).order_by(RREO.periodo).all()
    assert [r.valor for r in rows]==[Decimal('12.34'),Decimal('99.99')]
    with pytest.raises(RuntimeError):
        with Session(cache) as s:
            s.query(RREO).delete()
            raise RuntimeError('API incompleta')
    assert SessaoJson(cache).query(RREO).count()==2


def test_sessoes_distintas_preservam_parametros_e_recarga(cache):
    a,b=SessaoJson(cache),SessaoJson(CacheJson(cache.caminho))
    a.add(ParametroSimulacao(chave='a',valor='1')); a.commit()
    b.add(ParametroSimulacao(chave='b',valor='2')); b.commit()
    assert a.get(ParametroSimulacao,'b').valor=='2'
    registro=a.get(ParametroSimulacao,'a');registro.valor='3';a.commit()
    assert b.get(ParametroSimulacao,'a').valor=='3'


def test_cache_invalido_nao_e_apagado(cache):
    cache.caminho.write_text('{incompleto',encoding='utf-8')
    with pytest.raises(ValueError): cache.ler()
    assert cache.caminho.read_text(encoding='utf-8')=='{incompleto'


def test_paridade_selecao_ultimos_periodos_json_sql(cache,monkeypatch):
    objetos=[rreo(2025,6,'9.99'),rreo(2026,1,'1'),rreo(2026,2,'2'),
             RGF(exercicio=2026,periodo=1,periodicidade='Q',instituicao='GO',uf='GO',
                 co_poder='E',esfera='E',anexo='RGF-Anexo 02',conta='Conta',coluna='Coluna',valor=Decimal('10'))]
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with SqlSession(engine) as sql:
        sql.add_all(objetos);sql.commit()
        monkeypatch.setattr(db,'session',sql)
        esperado=(obter_dados_rreo_para_analise(2026),obter_dados_rgf_para_analise(2026))
        with Session(cache) as destino:
            for objeto in objetos:
                modelo=type(objeto)
                destino.add(modelo(**{c.name:getattr(objeto,c.name) for c in modelo.__table__.columns}))
            destino.commit()
    monkeypatch.setattr(db,'session',SessaoJson(cache))
    assert (obter_dados_rreo_para_analise(2026),obter_dados_rgf_para_analise(2026))==esperado


def _escritor_json(caminho, prefixo):
    from src.simulador.cache_json import CacheJson, Session
    for n in range(4):
        with Session(CacheJson(caminho)) as sessao:
            sessao.add(ParametroSimulacao(chave=f'{prefixo}-{n}', valor=str(n)))
            sessao.commit()


def test_processos_simultaneos_nao_perdem_gravacoes(cache):
    from multiprocessing import get_context
    ctx = get_context('spawn')
    processos = [ctx.Process(target=_escritor_json, args=(cache.caminho, str(n))) for n in range(3)]
    for processo in processos: processo.start()
    for processo in processos:
        processo.join(timeout=20)
        assert processo.exitcode == 0
    assert SessaoJson(cache).query(ParametroSimulacao).count() == 12


def test_importacao_siconfi_json_paginacao_e_falha(cache, monkeypatch, requests_mock):
    from src.simulador import data_updater as updater
    from unittest.mock import Mock
    monkeypatch.setattr(db, 'session', SessaoJson(cache))
    monkeypatch.setattr(updater, 'log', Mock())
    monkeypatch.setattr(updater, '_aguardar_limite_api', lambda: None)
    monkeypatch.setattr(updater, 'sleep', lambda _: None)
    url = 'https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo'
    params = {'co_tipo_demonstrativo':'RREO','co_esfera':'E','id_ente':52}
    periodo = {'an_exercicio':2026,'nr_periodo':4,'no_anexo':'RREO-Anexo 01'}
    def item(conta):
        return dict(exercicio=2026,periodo=4,demonstrativo='RREO',instituicao='GO',
                    uf='GO',esfera='E',anexo='RREO-Anexo 01',conta=conta,coluna='Valor',valor=123.45,cod_ibge=52,campo_novo_api='metadado')
    requests_mock.get(url, [{'json':{'items':[item('A')],'hasMore':True}},
                            {'json':{'items':[item('A'),item('B')],'hasMore':False}}])
    ok, erros, _ = updater._atualizar_dados_siconfi(RREO,'rreo',params,[periodo])
    assert len(ok)==1 and not erros
    assert db.session.query(RREO).count()==2
    assert db.session.query(RREO).first().valor==Decimal('123.45')
    # Retificação com segunda página inválida não substitui a publicação íntegra.
    with Session(cache) as sessao:
        sessao.query(SincronizacaoSiconfi).delete(); sessao.commit()
    requests_mock.get(url, [{'json':{'items':[item('C')],'hasMore':True}}, {'json':{'erro':'indisponível'}}])
    _, erros, _ = updater._atualizar_dados_siconfi(RREO,'rreo',params,[periodo])
    assert erros and {r.conta for r in db.session.query(RREO).all()}=={'A','B'}


def test_capag_importa_no_json_com_fonte_e_historico(cache,monkeypatch,requests_mock):
    from src.simulador import capag
    monkeypatch.setattr(db,'session',SessaoJson(cache))
    url='https://fonte/capag-2025.csv'
    requests_mock.get(capag.PACOTE,json={'result':{'resources':[
        {'name':'CAPAG Estados 2025','format':'CSV','url':url,'description':'Ano base 2024'}]}})
    requests_mock.get(url,content=('UF;Indicador 1;Nota 1;Indicador 2;Nota 2;Indicador 3;Nota 3;Classificação da CAPAG\n'
                                   'GO;68,54;B;87,10;B;15,44;A;B+\n').encode())
    assert capag.atualizar_capag()=='B+'
    dados=capag.obter_capag()
    assert dados['valor']=='B+' and dados['url']==url
    assert dados['historico'][0]['ano']==2025


def test_aviso_de_versao_so_aparece_com_publicacao_pronta(tmp_path,monkeypatch):
    from src.simulador.versao_rede import consultar_versao_rede
    monkeypatch.setenv('SIMULADOR_RELEASE_ROOT',str(tmp_path))
    monkeypatch.setenv('SIMULADOR_RELEASE_VERSION','2.1.2')
    (tmp_path/'versao-atual.txt').write_text('2.1.3')
    assert not consultar_versao_rede()['disponivel']
    pasta=tmp_path/'versoes'/'2.1.3';pasta.mkdir(parents=True)
    (pasta/'pronta.txt').write_text('2.1.3')
    assert consultar_versao_rede()['disponivel']


def test_leitura_nao_bloqueia_outro_escritor_e_commit_libera(cache):
    from threading import Thread,Event
    concluiu=Event()
    def gravar():
        with Session(CacheJson(cache.caminho)) as outra:
            outra.add(ParametroSimulacao(chave='outra',valor='1'));outra.commit()
        concluiu.set()
    with Session(cache) as leitura:
        leitura.query(ParametroSimulacao).all()
        tarefa=Thread(target=gravar);tarefa.start()
        assert concluiu.wait(2), 'Consulta de leitura reteve o bloqueio de escrita'
        tarefa.join()
        leitura.add(ParametroSimulacao(chave='primeira',valor='2'));leitura.commit()
        concluiu.clear();tarefa=Thread(target=gravar);tarefa.start()
        assert concluiu.wait(2), 'Commit reteve o bloqueio durante operações posteriores'
        tarefa.join()
    assert SessaoJson(cache).query(ParametroSimulacao).count()==2
