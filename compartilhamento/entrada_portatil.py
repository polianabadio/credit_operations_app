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
        from src.simulador.cambio import entrada_em_reais
        from src.simulador.operacao import calcular_operacao
        from decimal import Decimal
        entrada_anual = dict(ano=2026,fim=2027,valor='1000',indexador='CAMBIAL',moeda_contrato='USD',
            cotacao_contrato='4.9886',fator='2',modo_calculo='anual_informado',
            cronograma_anual=[dict(ano=2026,liberacao='400',amortizacao='0',juros_encargos='10'),
                              dict(ano=2027,liberacao='600',amortizacao='1000',juros_encargos='20')])
        entrada_anual, _ = entrada_em_reais(entrada_anual)
        anual = calcular_operacao(entrada_anual,serie_ipca={})
        resultado['cronograma_anual'] = anual['fluxo']['modo'] == 'anual_informado' and Decimal(anual['fluxo']['amortizacao_total']) == Decimal('4988.60')
        if not resultado['cronograma_anual']: raise ValueError('Cronograma anual inválido no executável.')
        entrada_contratual = dict(ano=2026,fim=2050,valor='90366254',indexador='CAMBIAL',moeda_contrato='USD',
            cotacao_contrato='4.9886',fator='2.031208231',modelo_fluxo='contratual',tipo_liberacao='cronograma',
            data_liberacao='2026-01-01',prazo_meses='294',carencia_meses='72',amortizacao_meses='222',
            periodicidade_amortizacao='6',periodicidade_juros='6',base_juros='360',prefixada='0',spread='1.21',spread_capital='0',
            comissao_credito='.75',referencia_juros_cambial='SOFR',taxa_indexador='3.69',mes_liberacoes='7',
            liberacoes={a:dict(zip(range(2026,2032),['692828.30','16108360.85','27066874.79','24932850.99','18397003.74','3168335.33'])).get(a,'0') for a in range(2026,2051)},
            encargos_anuais={a:'0' for a in range(2026,2051)},complemento_limites={})
        convertida,_=entrada_em_reais(entrada_contratual)
        contratual=calcular_operacao(convertida,serie_ipca={})
        resultado['fluxo_contratual'] = dict(amortizacoes=contratual['fluxo']['quantidade_amortizacoes'],pagamentos_juros=contratual['fluxo']['quantidade_pagamentos_juros'],saldo=contratual['fluxo']['saldo_final'],principal=contratual['fluxo']['amortizacao_total'])
        if resultado['fluxo_contratual']['amortizacoes']!=38 or resultado['fluxo_contratual']['pagamentos_juros']!=49 or Decimal(resultado['fluxo_contratual']['saldo'])!=0: raise ValueError('Fluxo por etapas inválido no executável.')
        from copy import deepcopy
        reais=deepcopy(entrada_contratual)
        reais.update(moeda_entrada='BRL',cotacao_id='BRL',valor=convertida['valor'],liberacoes=convertida['liberacoes'],encargos_anuais=convertida['encargos_anuais'])
        reais_convertidos,_=entrada_em_reais(reais)
        fluxo_reais=calcular_operacao(reais_convertidos,serie_ipca={})['fluxo']
        resultado['preenchimento_brl_equivalente'] = all(fluxo_reais[k]==contratual['fluxo'][k] for k in ('amortizacao_total','juros_total','pagamento_total','saldo_final'))
        if not resultado['preenchimento_brl_equivalente']: raise ValueError('Preenchimento em reais alterou o cálculo do empréstimo.')
        fixa=deepcopy(entrada_contratual)
        fixa.update(calendario_pagamentos='fixo',data_assinatura='2026-07-15',data_vigencia='2026-07-15',
                    data_liberacao='2026-07-15',primeiro_vencimento_juros='2026-09-15',
                    dias_inicio_comissao=60,prazo_desembolso_meses=60,metodo_sofr='composta_projetada')
        fixa_brl,_=entrada_em_reais(fixa)
        novo=calcular_operacao(fixa_brl,serie_ipca={})['fluxo']
        resultado['calendario_minuta'] = (novo['data_final']=='2050-09-15' and novo['quantidade_amortizacoes']==38
            and novo['datas_contratuais']['primeira_amortizacao']=='2032-03-15'
            and novo['datas_contratuais']['inicio_comissao']=='2026-09-13'
            and novo['metodo_sofr']=='composta_projetada' and Decimal(novo['saldo_final'])==0)
        if not resultado['calendario_minuta']: raise ValueError('Calendário contratual inválido no executável.')
        from src.simulador.cambio import converter_entradas,registrar_cotacao_contratual
        ref_manual=registrar_cotacao_contratual('USD','4.9886')
        campos=[dict(tipo='principal',valor=entrada_contratual['valor'])]+[dict(tipo='liberacao',valor=v) for v in entrada_contratual['liberacoes'].values()]
        conversao=converter_entradas(campos,ref_manual['id'],'BRL',True)
        resultado['conversor_preenchimento']=sum(Decimal(v['brl']) for v in conversao['valores'][1:])==Decimal(conversao['valores'][0]['brl'])
        if not resultado['conversor_preenchimento']: raise ValueError('Conversão de unidade não conciliou o principal.')



        from gevent import get_hub
        resultado['threadpool'] = get_hub().threadpool.apply(lambda: True)
        if '--verificar-apis' in sys.argv:
            import requests, certifi
            resultado['certificado_existe'] = Path(certifi.where()).is_file()
            integrado=app.avaliar_operacao_completa_py(entrada_contratual)
            resultado['simulacao_integrada'] = integrado.get('status')=='sucesso' and len(integrado.get('resultado',{}).get('bases_fluxo',[]))==25 and 'resumo_limites' in integrado.get('resultado',{})
            if not resultado['simulacao_integrada']: raise ValueError('Falha na simulação integrada: '+str(integrado.get('mensagem')))
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
