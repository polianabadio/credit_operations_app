from datetime import date, timedelta
from decimal import Decimal, localcontext, ROUND_HALF_UP
import pytest
from src.simulador import indexadores
from src.simulador.cambio import entrada_em_reais
from src.simulador.operacao import calcular_operacao, normalizar_prazos
from src.simulador.fluxo_indexado import calcular_fluxo_indexado


def entrada(**alteracoes):
    return dict(ano=2026, fim=2027, valor='1000', tipo_liberacao='unica',
                data_liberacao='2026-10-16', prazo_meses='12', carencia_meses='0',
                amortizacao_meses='12', prefixada='0', spread='0', fator='2', **alteracoes)


def test_total_e_calculado_e_nao_aceita_prazo_adulterado():
    assert normalizar_prazos({'carencia_meses':72,'amortizacao_meses':222})['prazo_meses']==294
    with pytest.raises(ValueError,match='diferente'):
        normalizar_prazos({'carencia_meses':72,'amortizacao_meses':222,'prazo_meses':293})
    with pytest.raises(ValueError,match='600'):
        normalizar_prazos({'carencia_meses':300,'amortizacao_meses':400})


def test_cambio_contratual_ignora_cotacao_atual_e_base_de_apresentacao(monkeypatch):
    import src.simulador.cambio as cambio
    monkeypatch.setattr(cambio,'referencia',lambda *a: pytest.fail('Consultou câmbio atual'))
    dados, ref=entrada_em_reais(dict(valor='1000.12',indexador='CAMBIAL',moeda_contrato='USD',
        cotacao_contrato='5.432123',cotacao_id='mercado-atual',valor_base_brl='999999',liberacoes={2026:'1000.12'}))
    assert dados['valor']==str((Decimal('1000.12')*Decimal('5.432123')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    assert dados['liberacoes'][2026]==dados['valor']
    assert ref['constante'] and ref['taxa_brl']=='5.432123'
    assert ref['valor_original']=='1000.12'


@pytest.mark.parametrize('valor',['0','-1','NaN','Infinity',''])
def test_rejeita_cambio_manual_invalido(valor):
    with pytest.raises(ValueError):
        entrada_em_reais(dict(valor='100',indexador='CAMBIAL',moeda_contrato='USD',cotacao_contrato=valor))


def test_sem_indexador_nao_aplica_ipca_e_quita_principal():
    r=calcular_operacao(entrada(indexador='FIXA'),serie_ipca={'2026-09':'50'})
    assert r['fluxo']['juros_total']=='0.00'
    assert Decimal(r['fluxo']['amortizacao_total'])==1000
    assert r['fluxo']['saldo_final']=='0.00'


def test_tlp_jm_nao_e_contada_duas_vezes():
    tlp=calcular_operacao(entrada(indexador='TLP',taxa_indexador='6'),serie_ipca={'2026-09':'0.4'})
    ipca=calcular_operacao({**entrada(),'prefixada':'6'},serie_ipca={'2026-09':'0.4'})
    assert tlp['fluxo']['juros_total']==ipca['fluxo']['juros_total']


@pytest.mark.parametrize('indice',['CDI','SELIC'])
def test_taxa_anual_252_sem_ipca_adicional(indice):
    r=calcular_fluxo_indexado('1000','2026-10-16',12,0,'0','0',indice,'10')
    primeira=r['linhas'][0]
    with localcontext() as c:
        c.prec=50
        esperado=(1000*((Decimal('1.10')**(Decimal(primeira['dup'])/252))-1)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    assert Decimal(primeira['juros'])==esperado
    assert Decimal(r['amortizacao_total'])==1000


def test_sofr_simples_act360_sem_composto_mensal_na_carencia():
    r=calcular_fluxo_indexado('1000','2026-10-16',12,3,'0','2','SOFR','6')
    linhas=r['linhas'][:3]
    dias=sum(l['dias_corridos'] for l in linhas)
    esperado=(Decimal('1000')*Decimal('.08')*dias/360).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    assert Decimal(linhas[-1]['juros'])==esperado
    assert all(Decimal(l['juros'])==0 for l in linhas[:2])


@pytest.mark.parametrize('indice,serie',[('CDI',4389),('SELIC',1178),('TLP',27572)])
def test_api_bcb_preserva_data_taxa_e_ajuste_manual(indice,serie,requests_mock):
    indexadores._cache.clear()
    dia=date.today()-timedelta(days=1)
    url=f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/3'
    requests_mock.get(url,json=[{'data':dia.strftime('%d/%m/%Y'),'valor':'7.1234'}])
    ref=indexadores.consultar_taxa(indice)
    assert ref['valor']=='7.1234' and ref['data']==dia.isoformat()
    assert indexadores.memoria_taxa(indice,'7.1234',ref['id'])['origem']=='API'
    ajuste=indexadores.memoria_taxa(indice,'8',ref['id'])
    assert ajuste['origem']=='Informada pelo usuário'
    assert ajuste['referencia_api']['valor']=='7.1234'


def test_api_sofr_over_preserva_base360_e_falha_nao_vira_zero(requests_mock):
    indexadores._cache.clear()
    url='https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json'
    requests_mock.get(url,json={'refRates':[{'type':'SOFR','effectiveDate':date.today().isoformat(),'percentRate':4.5}]})
    assert indexadores.consultar_taxa('SOFR')['base']=='ACT/360'
    indexadores._cache.clear();requests_mock.get(url,status_code=503)
    with pytest.raises(ValueError,match='consultar'):indexadores.consultar_taxa('SOFR')
