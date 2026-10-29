// ======================================================================
// LÓGICA DO COMPONENTE DE CONFIGURAÇÃO DO BANCO DE DADOS
// ======================================================================

const DB_FIELDS = {
    sqlite: [
        { id: 'path', label: 'Caminho do Arquivo:', type: 'text', placeholder: 'database/simulador.db' }
    ],
    postgresql: [
        { id: 'host', label: 'Host:', type: 'text', placeholder: 'localhost' },
        { id: 'port', label: 'Porta:', type: 'number', placeholder: '5432' },
        { id: 'name', label: 'Nome do Banco:', type: 'text', placeholder: 'simulador_db' },
        { id: 'user', label: 'Usuário:', type: 'text', placeholder: 'postgres' },
        { id: 'password', label: 'Senha:', type: 'password', placeholder: '******' }
    ],
    mysql: [
        { id: 'host', label: 'Host:', type: 'text', placeholder: 'localhost' },
        { id: 'port', label: 'Porta:', type: 'number', placeholder: '3306' },
        { id: 'name', label: 'Nome do Banco:', type: 'text', placeholder: 'simulador_db' },
        { id: 'user', label: 'Usuário:', type: 'text', placeholder: 'root' },
        { id: 'password', label: 'Senha:', type: 'password', placeholder: '******' }
    ]
};

function initializeDbConfigComponent() {
    // Eventos para abrir e fechar o modal
    document.getElementById('openDbConfigModalBtn').addEventListener('click', openDbConfigModal);
    document.getElementById('closeDbConfigModalBtn').addEventListener('click', closeDbConfigModal);

    // Eventos dos botões de ação do modal
    document.getElementById('testDbConnectionBtn').addEventListener('click', testDbConnection);
    document.getElementById('saveDbConfigBtn').addEventListener('click', saveDbConfig);
    
    // Evento para mudar os campos dinamicamente
    document.getElementById('dbType').addEventListener('change', renderDbConfigFields);
}

async function openDbConfigModal() {
    const modal = document.getElementById('dbConfigModal');
    modal.style.display = 'flex'; // Usamos flex para centralizar
    
    try {
        const config = await eel.get_db_config()();
        document.getElementById('dbType').value = config.type || 'sqlite';
        // Renderiza os campos com os valores atuais
        renderDbConfigFields(config); 
    } catch (e) {
        mostrarMensagem('Erro ao carregar configuração do banco de dados.', 'error');
    }
}

function closeDbConfigModal() {
    const modal = document.getElementById('dbConfigModal');
    modal.style.display = 'none';
    document.getElementById('connectionStatus').textContent = ''; // Limpa status
}

function renderDbConfigFields(currentConfig = {}) {
    const dbType = document.getElementById('dbType').value;
    const fieldsContainer = document.getElementById('dbConfigFields');
    fieldsContainer.innerHTML = ''; // Limpa campos antigos

    const fields = DB_FIELDS[dbType];
    if (fields) {
        fields.forEach(field => {
            const value = currentConfig[field.id] || '';
            const formGroup = document.createElement('div');
            formGroup.innerHTML = `
                <label for="db_${field.id}" class="block text-sm font-medium text-gray-700">${field.label}</label>
                <input type="${field.type}" id="db_${field.id}" value="${value}"
                       class="mt-1 block w-full p-2 rounded-md border-gray-300 shadow-sm"
                       placeholder="${field.placeholder}">
            `;
            fieldsContainer.appendChild(formGroup);
        });
    }
}

function getDbConfigFromModal() {
    const dbType = document.getElementById('dbType').value;
    const configData = { type: dbType };
    const fields = DB_FIELDS[dbType];

    if (fields) {
        fields.forEach(field => {
            configData[field.id] = document.getElementById(`db_${field.id}`).value;
        });
    }
    return configData;
}

async function testDbConnection() {
    const configData = getDbConfigFromModal();
    const statusSpan = document.getElementById('connectionStatus');
    statusSpan.textContent = 'Testando...';
    statusSpan.className = 'text-gray-500';

    try {
        const result = await eel.test_db_connection(configData)();
        if (result.status === 'sucesso') {
            statusSpan.textContent = result.mensagem;
            statusSpan.className = 'text-green-600 font-semibold';
        } else {
            statusSpan.textContent = mensagemErroAmigavel(result.mensagem);
            statusSpan.className = 'text-red-600 font-semibold';
        }
    } catch (e) {
        statusSpan.textContent = 'Não foi possível se conectar ao aplicativo. Feche e abra novamente para tentar restabelecer a conexão.';
        statusSpan.className = 'text-red-600 font-semibold';
    }
}

async function saveDbConfig() {
    const configData = getDbConfigFromModal();
    
    try {
        const result = await eel.save_db_config(configData)();
        if (result.status === 'sucesso') {
            mostrarMensagem(result.mensagem, 'success');
            closeDbConfigModal();
        } else {
            mostrarMensagem(mensagemErroAmigavel(result.mensagem), 'error');
        }
    } catch (e) {
        mostrarMensagem('Não foi possível salvar as configurações. Feche e abra o aplicativo e tente novamente.', 'error');
    }
}