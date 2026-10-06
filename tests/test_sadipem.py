from src.simulador.sadipem import (SadipemClient, SadipemSnapshotSelector,
                                   obter_comprometimento_goias, simular_fluxo_goias)


PVL_ATUAL = {
    'id_pleito': 74460, 'tipo_interessado': 'Estado', 'interessado': 'Goiás',
    'cod_ibge': 52, 'uf': 'GO', 'num_pvl': 'PVL02.001127/2026-73',
    'status': 'Encaminhado à PGFN com manifestação técnica favorável',
    'data_status': '30/07/2026', 'data_protocolo': '2026-07-22T17:48:51Z',
}


class FakeClient:
    def __init__(self, liberacoes=None, nao_contratadas=None, pvls=None, liberacoes_por_pvl=None):
        self.liberacoes = liberacoes or []
        self.nao_contratadas = nao_contratadas or []
        self.pvls = pvls or [PVL_ATUAL]
        self.liberacoes_por_pvl = liberacoes_por_pvl
        self.chamadas = []

    def listar(self, endpoint, params=None, cancel_event=None):
        self.chamadas.append((endpoint, params))
        if endpoint == 'pvl':
            return self.pvls
        if endpoint == 'opc-cronograma-liberacoes':
            return (self.liberacoes_por_pvl.get(params['id_pleito'], [])
                    if self.liberacoes_por_pvl is not None else self.liberacoes)
        return self.nao_contratadas


def test_snapshot_2026_sem_linha_nao_vira_zero_ou_margem():
    cliente = FakeClient()
    dado = obter_comprometimento_goias(2026, 1000, client=cliente)
    assert dado['snapshot']['idPleito'] == 74460
    assert dado['motivo'] == 'NO_DATA'
    assert dado['liberacoesContratadasSadipem'] is None
    assert dado['mgaCompleto'] is None and dado['margemCompleta'] is None
    assert len(cliente.chamadas) == 3


def test_cronograma_historico_aparece_sem_preencher_comprometimento_atual():
    antigo = {**PVL_ATUAL, 'id_pleito': 27067, 'num_pvl': 'PVL02.002574/2017-59',
              'data_status': '12/03/2018', 'data_protocolo': '2018-03-12T10:45:53Z'}
    cliente = FakeClient(pvls=[PVL_ATUAL, antigo], liberacoes_por_pvl={
        74460: [], 27067: [{'id_pleito': 27067, 'ano': 2018,
                            'indicador_liberacoes': '1', 'liberacoes_total': 295461624.89}]})
    dado = obter_comprometimento_goias(2026, client=cliente)
    assert dado['snapshot']['idPleito'] == 74460
    assert dado['ultimaReferenciaHistorica']['ano'] == 2018
    assert dado['ultimaReferenciaHistorica']['valor'] == 295461624.89
    assert dado['liberacoesContratadasSadipem'] is None
    assert dado['margemCompleta'] is None


def test_liberacao_real_e_parcial_sem_somar_pvls_ou_valor_total():
    cliente = FakeClient(
        liberacoes=[{'id_pleito': 74460, 'ano': 2026, 'indicador_liberacoes': '1  ',
                     'liberacoes_total': 250, 'liberacoes_operacoes_sfn': 200,
                     'liberacoes_aro': 0, 'liberacoes_demais': 50}],
        nao_contratadas=[{'id_pleito': 74460, 'pleito_nao_contratado': 11,
                          'ano_pvl_nao_contratado': 2026,
                          'liberacao_pvl_nao_contratado': 25,
                          'valor_pvl_nao_contratado': 900}])
    dado = obter_comprometimento_goias(2026, 1000, client=cliente)
    assert dado['statusDadosMga'] == 'Partial'
    assert dado['liberacoesContratadasSadipem'] == 250
    assert dado['liberacoesNaoContratadasSadipem'] == 25
    assert dado['percentualContratadoRclReferencia'] == 25
    assert dado['mgaCompleto'] is None and dado['margemCompleta'] is None


def test_selector_prioriza_data_e_descarta_arquivado():
    base = {'idPleito': 1, 'status': 'Deferido', 'dataProtocolo': '2025-01-01T00:00:00Z'}
    ordem = SadipemSnapshotSelector().ordenar([
        {**base, 'idPleito': 8, 'dataStatus': '01/01/2025'},
        {**base, 'idPleito': 9, 'dataStatus': '01/01/2026'},
        {**base, 'idPleito': 10, 'dataStatus': '01/02/2026', 'status': 'Arquivado'},
    ])
    assert [item['idPleito'] for item in ordem] == [9, 8]


def test_simulacao_complementar_so_calcula_quando_todos_os_componentes_existem():
    cliente = FakeClient(liberacoes=[{'id_pleito': 74460, 'ano': 2026,
                                     'indicador_liberacoes': '1', 'liberacoes_total': 100}])
    incompleto = simular_fluxo_goias([{'ano': 2026, 'rclProjetada': 1000,
                                       'liberacaoNovaOperacao': 20}], client=cliente)[0]
    assert incompleto['cenario']['mga'] is None
    completo = simular_fluxo_goias([{'ano': 2026, 'rclProjetada': 1000,
                                     'liberacoesNaoContratadasManual': 0,
                                     'liberacaoNovaOperacao': 20}], client=cliente)[0]
    assert completo['cenario']['mga'] == 120
    assert completo['cenario']['margemEstimada'] == 40
    assert completo['statusDadosMga'] == 'Partial'  # cenário, não margem oficial


def test_duplicidade_de_linhas_do_mesmo_ano_nao_e_somada():
    linha = {'id_pleito': 74460, 'ano': 2026, 'indicador_liberacoes': '1',
             'liberacoes_total': 100}
    dado = obter_comprometimento_goias(2026, client=FakeClient(liberacoes=[linha, linha]))
    assert dado['motivo'] == 'AMBIGUOUS_DATA'
    assert dado['liberacoesContratadasSadipem'] is None


def test_cliente_respeita_intervalo_e_reutiliza_cache():
    instantes = [0.0]
    chamadas = []

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {'items': [], 'hasMore': False}

    class Sessao:
        def get(self, url, params, timeout):
            chamadas.append(instantes[0])
            return Resposta()

    def dormir(segundos):
        instantes[0] += segundos

    cliente = SadipemClient(session=Sessao(), clock=lambda: instantes[0],
                            sleeper=dormir, min_interval=1.05)
    cliente.listar('pvl')
    cliente.listar('pvl')  # mesma chave: cache
    cliente.listar('res-cdp', {'id_pleito': 1})
    assert chamadas == [0.0, 1.05]
