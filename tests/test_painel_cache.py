import json
from unittest.mock import Mock
import pytest
from src.simulador import painel_cache as cache
from src.simulador.cache_json import CacheJson,SessaoJson
from src.simulador.database_models import db

@pytest.fixture
def ambiente(tmp_path,monkeypatch):
    armazenamento=CacheJson(tmp_path/'dados-fiscais.json')
    with armazenamento.escrita(): armazenamento.salvar({'versao':1,'tabelas':{}})
    monkeypatch.setattr(db,'session',SessaoJson(armazenamento))
    compor=Mock(return_value=({'exercicio':2026,'rcl':{'valor':123}},[2026,2025]))
    monkeypatch.setattr(cache,'_compor',compor)
    cache._memoria.clear()
    return armazenamento,compor

def test_reutiliza_em_memoria_e_entre_aberturas_sem_recalcular(ambiente):
    armazenamento,compor=ambiente
    painel=cache.obter_painel_fiscal_em_cache();painel['rcl']['valor']=0
    assert cache.obter_painel_fiscal_em_cache()['rcl']['valor']==123
    cache._memoria.clear()
    assert cache.obter_anos_fiscais_em_cache()==[2026,2025]
    assert cache.obter_painel_fiscal_em_cache()['rcl']['valor']==123
    assert compor.call_count==1

def test_mudanca_da_base_ou_versao_invalida_cache(ambiente,monkeypatch):
    armazenamento,compor=ambiente
    cache.obter_painel_fiscal_em_cache()
    with armazenamento.escrita():armazenamento.salvar({'versao':1,'tabelas':{'rreo':[]}})
    compor.return_value=({'exercicio':2026,'rcl':{'valor':456}},[2026])
    assert cache.obter_painel_fiscal_em_cache()['rcl']['valor']==456
    assert compor.call_count==2
    monkeypatch.setattr(cache,'APP_VERSION','nova')
    cache.obter_painel_fiscal_em_cache()
    assert compor.call_count==3

def test_cache_derivado_corrompido_e_reconstruido_sem_apagar_base(ambiente):
    armazenamento,compor=ambiente
    destino=armazenamento.caminho.with_name('painel-fiscal.json')
    destino.write_text('{incompleto',encoding='utf-8')
    assert cache.obter_painel_fiscal_em_cache()['exercicio']==2026
    assert json.loads(destino.read_text(encoding='utf-8'))['anos']==[2026,2025]
    assert armazenamento.ler()['versao']==1

def test_base_alterada_durante_calculo_nao_gera_cache_com_assinatura_incorreta(ambiente):
    armazenamento,compor=ambiente
    def alterar():
        with armazenamento.escrita():armazenamento.salvar({'versao':1,'tabelas':{'rreo':[]}})
        return {'exercicio':2026},[2026]
    compor.side_effect=alterar
    cache.obter_painel_fiscal_em_cache()
    assert not armazenamento.caminho.with_name('painel-fiscal.json').exists()
