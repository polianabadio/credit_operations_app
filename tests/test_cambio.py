from decimal import Decimal
from datetime import datetime, timezone
import pytest
import requests
from src.simulador import cambio


class Resposta:
    def __init__(self, taxa='5', moeda='USD', timestamp=None):
        self.registro = {'code':moeda,'codein':'BRL','bid':taxa,
                         'timestamp':timestamp or str(int(datetime.now(timezone.utc).timestamp()))}
    def raise_for_status(self): pass
    def json(self):
        return {'success':True,'base':'USD','timestamp':self.registro['timestamp'],
                'rates':{**{moeda:'1' for moeda in cambio.MOEDAS},'BRL':self.registro['bid']}}


class Cliente:
    def __init__(self, resposta=None): self.resposta=resposta or Resposta(); self.chamadas=0
    def get(self,*args,**kwargs): self.chamadas+=1; return self.resposta


@pytest.fixture(autouse=True)
def isolado():
    cambio._cache.clear(); cambio._snapshots.clear()
    yield
    cambio._cache.clear(); cambio._snapshots.clear()


def test_cotacao_cache_e_conversao_decimal():
    cliente=Cliente()
    ref=cambio.cotacao('USD',cliente)
    assert cambio.cotacao('USD',cliente)==ref
    assert cliente.chamadas==1
    assert cambio.converter_valores(['100.01'],ref['id'],'BRL')==[{'brl':'500.05','valor':'500.05'}]
    entrada, memoria=cambio.entrada_em_reais({'valor':'100.01','cotacao_id':ref['id'],'fator':'2'})
    assert entrada['valor']=='500.05'
    assert entrada['fator']=='2'
    assert memoria==ref


def test_preserva_base_monetaria_apos_troca_de_moeda():
    ref=cambio.cotacao('USD',Cliente(Resposta('5.12345')))
    valor=cambio.converter_valores(['1000'],'BRL',ref['id'])[0]
    entrada,_=cambio.entrada_em_reais({'valor':valor['valor'],'valor_base_brl':valor['brl'],'cotacao_id':ref['id']})
    assert Decimal(entrada['valor'])==1000


@pytest.mark.parametrize('taxa',['0','-1','NaN','Infinity'])
def test_rejeita_cotacao_invalida(taxa):
    with pytest.raises(ValueError): cambio.cotacao('USD',Cliente(Resposta(taxa)))
    assert not cambio._snapshots


def test_falha_api_nao_cria_taxa():
    class Falha:
        def get(self,*args,**kwargs): raise requests.ConnectionError()
    with pytest.raises(ValueError): cambio.cotacao('EUR',Falha())
    assert not cambio._snapshots
    with pytest.raises(ValueError): cambio.referencia('inexistente')
    assert cambio.cotacao('BRL')['taxa_brl']=='1'


def test_todas_as_moedas_usam_mesmo_snapshot_e_consulta():
    cliente = Cliente()
    cotacoes = [cambio.cotacao(moeda, cliente) for moeda in cambio.MOEDAS if moeda != 'BRL']
    assert cliente.chamadas == 1
    assert len({item['data'] for item in cotacoes}) == 1
    assert all('FXRatesAPI' in item['fonte'] for item in cotacoes)


def test_calcula_taxa_cruzada_sem_arredondamento_intermediario():
    class Taxas(Resposta):
        def json(self):
            dados=super().json()
            dados['rates']['EUR']='0.8'
            return dados
    ref=cambio.cotacao('EUR',Cliente(Taxas('5')))
    assert Decimal(ref['taxa_brl']) == Decimal('6.25')
    assert ref['memoria_cambio']['moeda_por_USD'] == '0.8'
