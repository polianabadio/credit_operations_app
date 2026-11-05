// A versão em uso permanece estável enquanto uma simulação estiver aberta.
document.addEventListener('DOMContentLoaded', () => {
    async function conferirVersao() {
        try {
            if (typeof eel.consultar_versao_rede_py !== 'function') return;
            const versao = await eel.consultar_versao_rede_py()();
            if (!versao.disponivel || document.getElementById('aviso-versao-rede')) return;
            const aviso = document.createElement('div');
            aviso.id = 'aviso-versao-rede';
            aviso.setAttribute('role', 'status');
            aviso.style.cssText = 'position:fixed;bottom:20px;right:20px;max-width:420px;padding:16px;background:#065f46;color:white;border-radius:10px;z-index:9999;box-shadow:0 4px 20px #0003';
            aviso.textContent = 'Há uma nova versão disponível. Feche e abra o simulador pelo atalho da equipe para atualizar.';
            document.body.append(aviso);
        } catch (_) { /* Sem rede, não interrompe uma análise em andamento. */ }
    }
    conferirVersao();
    setInterval(conferirVersao, 60000);
});
