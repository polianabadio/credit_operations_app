from threading import Event
from src.simulador import sync_job as job


def test_background_prioriza_ano_atual_e_impede_duplicacao(monkeypatch):
    entrou, liberar, terminou = Event(), Event(), Event()
    chamadas = []
    def atualizar(escopo, progresso):
        chamadas.append(escopo)
        entrou.set()
        assert liberar.wait(3)
        progresso(1, 1)
        return {'falhas': []}
    monkeypatch.setattr(job, 'atualizar_operacoes_rreo', atualizar)
    monkeypatch.setattr(job, 'atualizar_operacoes_rgf', atualizar)
    monkeypatch.setattr(job, 'atualizar_capag', lambda: None)
    original = job._executar
    def executar():
        try:
            original()
        finally:
            terminou.set()
    monkeypatch.setattr(job, '_executar', executar)
    try:
        assert job.iniciar_atualizacao()['running']
        assert entrou.wait(3)
        assert job.iniciar_atualizacao()['running']
        assert chamadas == ['now']
    finally:
        liberar.set()
        assert terminou.wait(3)
    assert chamadas == ['now', 'now', 'past', 'past']
    assert not job.status_atualizacao()['running']


def test_falha_encerra_estado_de_carregamento(monkeypatch):
    def falhar(*args, **kwargs):
        raise RuntimeError('API indisponível')
    monkeypatch.setattr(job, 'atualizar_operacoes_rreo', falhar)
    monkeypatch.setattr(job, 'atualizar_capag', lambda: None)
    job._estado.update(running=True, falhas=0, detalhes_falhas=[])
    job._executar()
    assert job.status_atualizacao()['running'] is False
    assert job.status_atualizacao()['falhas'] == 1
    assert job.status_atualizacao()['detalhes_falhas'][0]['motivo'] == 'API indisponível'


def test_falhas_por_periodo_aparecem_no_status(monkeypatch):
    def atualizar(escopo, progresso):
        progresso(1, 1)
        return {'falhas': [{'an_exercicio': 2026, 'nr_periodo': 2,
                            'no_anexo': 'RGF-Anexo 01', 'co_poder': 'E',
                            'motivo': 'Tempo limite excedido ao consultar o SICONFI.'}]}
    monkeypatch.setattr(job, 'atualizar_operacoes_rreo', atualizar)
    monkeypatch.setattr(job, 'atualizar_operacoes_rgf', atualizar)
    monkeypatch.setattr(job, 'atualizar_capag', lambda: None)
    job._estado.update(running=True, falhas=0, detalhes_falhas=[])
    job._executar()
    estado = job.status_atualizacao()
    assert estado['running'] is False
    assert estado['falhas'] == 4
    assert estado['detalhes_falhas'][0]['ano'] == 2026
    assert estado['detalhes_falhas'][0]['anexo'] == 'RGF-Anexo 01'
    assert len(estado['detalhes_falhas']) == 3


def test_capag_lenta_nao_atrasa_inicio_do_siconfi(monkeypatch):
    capag_iniciou, liberar_capag, siconfi_iniciou = Event(), Event(), Event()

    def capag_lenta():
        capag_iniciou.set()
        assert liberar_capag.wait(2)

    def atualizar(escopo, progresso):
        siconfi_iniciou.set()
        return {'falhas': []}

    monkeypatch.setattr(job, 'atualizar_capag', capag_lenta)
    monkeypatch.setattr(job, 'atualizar_operacoes_rreo', atualizar)
    monkeypatch.setattr(job, 'atualizar_operacoes_rgf', atualizar)
    trabalho = job.Thread(target=job._executar)
    try:
        trabalho.start()
        assert capag_iniciou.wait(2)
        assert siconfi_iniciou.wait(2)
    finally:
        liberar_capag.set()
        trabalho.join(2)
    assert not trabalho.is_alive()
