// Consulta técnica do cache compartilhado, sem configuração de banco SQL.
function initializeDbConfigComponent() {
    document.getElementById('openDbConfigModalBtn').addEventListener('click', openDbConfigModal);
    document.getElementById('closeDbConfigModalBtn').addEventListener('click', closeDbConfigModal);
    document.getElementById('testDbConnectionBtn').addEventListener('click', testDbConnection);
}
async function openDbConfigModal() {
    document.getElementById('dbConfigModal').style.display = 'flex';
    try {
        const config = await eel.get_db_config()();
        const container = document.getElementById('dbConfigFields');
        container.replaceChildren();
        const label = document.createElement('p');
        label.textContent = 'Dados fiscais em cache JSON. As simulações não são armazenadas.';
        const path = document.createElement('p');
        path.textContent = config.path || '';
        path.style.overflowWrap = 'anywhere';
        container.append(label, path);
    } catch (e) { mostrarMensagem('Não foi possível consultar o cache.', 'error'); }
}
function closeDbConfigModal() {
    document.getElementById('dbConfigModal').style.display = 'none';
    document.getElementById('connectionStatus').textContent = '';
}
async function testDbConnection() {
    const status = document.getElementById('connectionStatus');
    status.textContent = 'Verificando…';
    try {
        const result = await eel.test_db_connection({type: 'json'})();
        status.textContent = result.mensagem;
    } catch (e) { status.textContent = 'Não foi possível consultar o cache.'; }
}
