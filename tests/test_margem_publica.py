from decimal import Decimal

import pytest

from src.simulador.margem_publica import (
    integrar_referencia_publica,
    obter_margem_publica,
)


@pytest.mark.parametrize('outras,esperado', [('0', 100), ('50', 150)])
def test_simulacao_reutiliza_pvl_sem_confirmar_cobertura(outras, esperado):
    simulacao = {'ano': 2026, 'evaluationScope': 'registered_inventory',
                 'rows': [{'ano': 2026, 'requestedOperation': 100, 'rclProjetada': 1000,
                           'scheduledDisbursements': None, 'dadosCompletos': False}]}
    publica = {'status': 'Referência pública', 'snapshot': {'idPleito': 74460},
               'memoria_exata': [{'ano': 2026, 'scheduledDisbursements': outras}]}
    r = integrar_referencia_publica(simulacao, publica)
    assert r['rows'][0]['mga'] == esperado
    assert r['rows'][0]['margemEstimada'] == 160 - esperado
    assert r['rows'][0]['mgaRcl'] == esperado / 1000
    assert r['validatedConclusion'] is False
    assert r['maxRequestedAmountForSchedule'] is None
    assert r['verificationStatus'] == 'Referência pública'


def test_pvl_nao_completa_anos_ausentes_ou_substitui_inventario():
    simulacao = {'ano': 2026, 'evaluationScope': 'registered_inventory', 'rows': [
        {'ano': 2026, 'requestedOperation': 100, 'rclProjetada': 1000,
         'scheduledDisbursements': 20, 'dadosCompletos': True},
        {'ano': 2027, 'requestedOperation': 100, 'rclProjetada': 1100,
         'scheduledDisbursements': None, 'dadosCompletos': False}]}
    publica = {'status': 'Referência pública',
               'memoria_exata': [{'ano': 2026, 'scheduledDisbursements': '0'}]}
    r = integrar_referencia_publica(simulacao, publica)
    assert r['rows'][0]['scheduledDisbursements'] == 20
    assert r['rows'][1]['scheduledDisbursements'] is None
    assert 'publicReference' not in r


def projecao():
    return {'ano':2026,'positionOnly':True,'parameterValidated':True,
            'rows':[{'ano':2026,'rclProjetada':'1000'}]}


def referencia(contratadas=None, nao_contratadas=None):
    return {'snapshot':{'idPleito':74460,'numeroPvl':'PVL02.001127/2026-73',
                        'dataProtocolo':'2026-07-22T17:48:51Z','data':'30/07/2026'},
            'liberacoesContratadasSadipem':contratadas,
            'operacoesNaoContratadas':nao_contratadas or []}


class Cliente:
    def __init__(self, indicador='0', linhas=None):
        self.linhas = linhas if linhas is not None else [{'id_pleito':74460,'ano':'2026','indicador_liberacoes':indicador}]
    def listar(self, endpoint, params, cancel_event=None):
        assert endpoint == 'opc-cronograma-pagamentos'
        assert params['id_pleito'] == 74460
        return self.linhas


def test_zero_declarado_publica_saldo_sem_confirmar_inventario():
    r=obter_margem_publica(projecao(),referencia(),Cliente())
    assert r['rows'][0]['scheduledDisbursements']==0
    assert r['rows'][0]['margemEstimada']==160
    assert r['coverageConfirmed'] is False
    assert r['memoria_exata'][0]['fonteZero']
    assert r['memoria_exata'][0]['naoContratadasListadas']==0


@pytest.mark.parametrize('linhas',[[],[{'id_pleito':74460,'ano':'2026','indicador_liberacoes':'1'}],
    [{'id_pleito':999,'ano':'2026','indicador_liberacoes':'0'}],
    [{'id_pleito':74460,'ano':'2026','indicador_liberacoes':'0'}]*2])
def test_ausencia_flag_positivo_ente_errado_duplicatas_nao_sao_zero(linhas):
    assert not obter_margem_publica(projecao(),referencia(),Cliente(linhas=linhas))['rows']


def test_soma_so_nao_contratadas_deste_ano_e_preserva_saldo_negativo():
    nao=[{'ano':2026,'idPleitoNaoContratado':1,'liberacaoAnual':'20.01'},
         {'ano':2027,'idPleitoNaoContratado':2,'liberacaoAnual':'999'}]
    r=obter_margem_publica(projecao(),referencia('200.00',nao),Cliente())
    assert Decimal(r['memoria_exata'][0]['margemEstimada'])==Decimal('-60.01')
    assert r['rows'][0]['liberacoesNaoContratadasListadas']==20.01


@pytest.mark.parametrize('alteracao',[{'parameterValidated':False},{'positionOnly':False},{'rows':[]}])
def test_fator_rcl_ou_posicao_invalidos_nao_produzem_margem(alteracao):
    p=projecao();p.update(alteracao)
    assert not obter_margem_publica(p,referencia(10),Cliente())['rows']


def test_snapshot_antigo_nao_preenche_ano_atual():
    s=referencia(10);s['snapshot']['dataProtocolo']='2018-01-01'
    assert not obter_margem_publica(projecao(),s,Cliente())['rows']


@pytest.mark.parametrize('valores',[[None],['10','10']])
def test_componentes_ausentes_ou_identificador_repetido_nao_produzem_margem(valores):
    s=referencia(10,[{'ano':2026,'idPleitoNaoContratado':1,'liberacaoAnual':v} for v in valores])
    assert not obter_margem_publica(projecao(),s,Cliente())['rows']

@pytest.mark.parametrize('motivo',['API_ERROR','CANCELLED','AMBIGUOUS_DATA'])
def test_falha_da_consulta_base_nao_vira_saldo_zero(motivo):
    s=referencia();s['motivo']=motivo
    assert not obter_margem_publica(projecao(),s,Cliente())['rows']
