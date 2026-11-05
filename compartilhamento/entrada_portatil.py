"""Entrada do executável com verificação técnica sem abrir a janela."""
import json
import sys
import traceback
from pathlib import Path

if '--verificar-distribuicao' in sys.argv:
    import os
    destino = Path(os.environ['SIMULADOR_DATA_DIR']) / 'verificacao-distribuicao.json'
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        import app
        from src.simulador.config import EEL_WEB_FOLDER
        painel = app.obter_painel_fiscal()
        resultado = {'sucesso': True, 'empacotado': bool(getattr(sys, 'frozen', False)),
                     'armazenamento': app.get_db_config()['type'],
                     'exercicio': painel['exercicio'],
                     'interface': (EEL_WEB_FOLDER / 'main.html').is_file(),
                     'anos': app.obter_dados_iniciais()['anos_disponiveis']}
        import time
        inicio_cache = time.perf_counter()
        retorno_cache = app.obter_painel_fiscal_py()
        resultado['tempo_painel_cache_ms'] = round((time.perf_counter() - inicio_cache) * 1000, 2)
        projecao = retorno_cache['painel']['fluxo_credito']
        linha = next((r for r in projecao.get('rows', []) if r['ano'] == projecao['ano']), {})
        resultado['rcl_projetada'] = linha.get('rclProjetada')
        resultado['teto_anual'] = linha.get('tetoAnual')
        from gevent import get_hub
        resultado['threadpool'] = get_hub().threadpool.apply(lambda: True)
        if '--verificar-apis' in sys.argv:
            import requests, certifi
            resultado['certificado_existe'] = Path(certifi.where()).is_file()
            resultado['apis'] = {}
            consultas = {
                'siconfi': ('https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo',
                            {'an_exercicio':2026,'nr_periodo':4,'no_anexo':'RREO-Anexo 01','id_ente':52,'co_esfera':'E','co_tipo_demonstrativo':'RREO','limit':1}),
                'sadipem': ('https://apidatalake.tesouro.gov.br/ords/cdwhprd/sadipem/tt/pvl',{'limit':1})}
            for nome, (url, parametros) in consultas.items():
                try:
                    resposta = requests.get(url, params=parametros, timeout=(8,12))
                    resposta.raise_for_status()
                    dados = resposta.json()
                    resultado['apis'][nome] = {'sucesso':isinstance(dados.get('items'),list),'status':resposta.status_code,'quantidade':len(dados.get('items',[]))}
                except Exception:
                    resultado['apis'][nome] = {'sucesso':False,'erro':traceback.format_exc()}
            from src.simulador.cache_json import CacheJson, SessaoJson
            from src.simulador.database_models import db, RREO, RGF
            from src.simulador.data_updater import _atualizar_dados_siconfi
            sessao_anterior = db.session
            resultado['importacao_real'] = {}
            try:
                db.session = SessaoJson(CacheJson(destino.parent / 'verificacao-importacao.json'))
                for modelo, endpoint, periodo, anexo in [(RREO,'rreo',4,'RREO-Anexo 01'), (RGF,'rgf',2,'RGF-Anexo 01')]:
                    parametros = {'co_esfera':'E','id_ente':52,'co_tipo_demonstrativo':endpoint.upper()}
                    consulta = {'an_exercicio':2026,'nr_periodo':periodo,'no_anexo':anexo}
                    if endpoint == 'rgf':
                        parametros['in_periodicidade'] = 'Q'
                        consulta['co_poder'] = 'E'
                    ok, falhas, _ = _atualizar_dados_siconfi(modelo,endpoint,parametros,[consulta])
                    quantidade = db.session.query(modelo).count()
                    resultado['importacao_real'][endpoint] = {'sucesso':bool(ok) and not falhas and quantidade > 0,
                                                             'registros':quantidade,'falhas':falhas}
            finally:
                db.session = sessao_anterior
            referencia = app.obter_comprometimento_sadipem_py(False)
            resultado['margem_status'] = referencia.get('margemPublica',{}).get('status')
        if '--verificar-indexadores' in sys.argv:
            from src.simulador.indexadores import consultar_taxa
            from src.simulador.operacao import calcular_operacao
            from src.simulador.cambio import entrada_em_reais
            taxas = {tipo: consultar_taxa(tipo) for tipo in ['CDI','SELIC','TLP','SOFR']}
            resultado['indexadores_api'] = {k: {'valor':v['valor'],'data':v['data'],'fonte':v['fonte']} for k,v in taxas.items()}
            resultado['cenarios_indexadores'] = {}
            for tipo in ['IPCA','FIXA','TLP','CDI','SELIC','SOFR','CAMBIAL']:
                entrada = dict(ano=2026,fim=2027,valor='1000',tipo_liberacao='unica',data_liberacao='2026-10-16',
                               carencia_meses=0,amortizacao_meses=12,prazo_meses=12,prefixada='0',spread='1',fator='2',indexador=tipo)
                if tipo in taxas:
                    entrada.update(taxa_indexador=taxas[tipo]['valor'],referencia_indexador_id=taxas[tipo]['id'])
                if tipo == 'CAMBIAL':
                    entrada.update(moeda_contrato='USD',cotacao_contrato='5.4321',referencia_juros_cambial='SOFR',
                                   taxa_indexador=taxas['SOFR']['valor'],referencia_indexador_id=taxas['SOFR']['id'])
                    entrada, _ = entrada_em_reais(entrada)
                fluxo = calcular_operacao(entrada,serie_ipca={})['fluxo']
                resultado['cenarios_indexadores'][tipo] = {'saldo_final':fluxo['saldo_final'],'principal':fluxo['amortizacao_total'],
                                                          'juros':fluxo['juros_total'],'prazo':fluxo['prazos']['prazo_total_meses']}
        destino.write_text(json.dumps(resultado), encoding='utf-8')
    except Exception:
        destino.write_text(json.dumps({'sucesso': False, 'erro': traceback.format_exc()}), encoding='utf-8')
        sys.exit(1)
else:
    import app
    app.main()
