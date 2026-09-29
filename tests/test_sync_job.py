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
    assert chamadas == ['now', 'now', 'all', 'all']
    assert not job.status_atualizacao()['running']


def test_falha_encerra_estado_de_carregamento(monkeypatch):
    def falhar(*args, **kwargs):
        raise RuntimeError('API indisponível')
    monkeypatch.setattr(job, 'atualizar_operacoes_rreo', falhar)
    job._estado.update(running=True, falhas=0)
    job._executar()
    assert job.status_atualizacao()['running'] is False
    assert job.status_atualizacao()['falhas'] == 1
