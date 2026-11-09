"""Ponte isolada do teste de interface, com fiscal fictício e motor real."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.simulador.cambio import entrada_em_reais
from src.simulador.operacao import calcular_operacao
from src.simulador.servico_divida import avaliar_caed
from src.simulador.resumo_limites import demonstrar_dcl, demonstrar_mga

entrada=json.load(sys.stdin)
if 'prever_termino_fcl' in entrada:
    from src.simulador.fluxo_tlp import montar_periodos
    try:
        fim = montar_periodos(*entrada['prever_termino_fcl'])[-1]['fim'].isoformat()
        print(json.dumps(dict(status='sucesso', fim=fim)))
    except ValueError as erro:
        print(json.dumps(dict(status='erro', mensagem=str(erro))))
    sys.exit()
convertida,cotacao=entrada_em_reais(entrada)
referencia=dict(valor='46182836779.90',exercicio=2026,periodo=2,origem='Base fiscal fictícia do teste',ente=52)
fator=dict(valor='1.02031208231',fonte='Parâmetro local do usuário',vigencia_inicio='2026-04-22',referencia_validada_ate='2026-12-31',data_referencia='2026-11-06')
dados=calcular_operacao(convertida,serie_ipca={},rcl_base=referencia['valor'],referencia_rcl=referencia,fator_projecao=fator)
dados['cotacao_entrada']=cotacao;dados['fluxo']['cotacao_entrada']=cotacao
servico=dados['servico_input'];servico['data_referencia']='2026-11-06'
for linha in servico['linhas']:linha['demais_operacoes']='1000000'
servico['cobertura_demais']=dict(completa=True,fonte='Fixture do teste',data_referencia='2026-11-06')
caed=avaliar_caed(2026,servico,referencia,fator)
dados['analise']=dict(status='Análise completa.',regras_ordenadas=[caed],regras_violadas=[],circuit_breaker=False)
c=entrada.get('complemento_limites') or {}
registros=[dict(exercicio=2026,periodo=2,coluna='Até o 2º Quadrimestre',conta=conta,valor=v) for conta,v in [('DÍVIDA CONSOLIDADA LÍQUIDA (DCL) (III)','14998011840.21'),('RECEITA CORRENTE LÍQUIDA AJUSTADA PARA CÁLCULO DOS LIMITES DE ENDIVIDAMENTO (VI)','46182836779.90')]]
dados['resumo_limites']=dict(dcl=demonstrar_dcl(2026,registros,dados['fluxo']['amortizacao_total'],c.get('outras_operacoes_dcl_brl'),c.get('cobertura'),c.get('fonte')),mga=demonstrar_mga(dados['bases_fluxo'],c.get('demais_liberacoes_brl'),c.get('cobertura'),c.get('fonte')))
print(json.dumps(dict(status='sucesso',resultado=dados)))
