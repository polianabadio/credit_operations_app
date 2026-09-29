/**
 * JavaScript principal para comunicação com Eel e renderização da interface.
 * Simulador de Operações de Crédito v2 - Refatorado
 */

// --- INICIALIZAÇÃO ---

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM carregado. Inicializando aplicação...');
    configurarEventListeners();
    carregarDadosIniciais();
    initializeMonitoringComponent();
    // Garante que a seção de simulação seja exibida por padrão ao carregar
    mostrarSecao('secao-simulacao');
});

// --- LÓGICA DE NAVEGAÇÃO ENTRE SEÇÕES ---
function mostrarSecao(nomeSecao) {
    // Esconde todas as seções principais
    document.getElementById('secao-simulacao').classList.add('hidden');
    document.getElementById('secao-configuracoes').classList.add('hidden');
    // Adicione outras seções aqui

    // Remove a classe de 'ativo' de todos os links de navegação
    document.getElementById('nav-simulacao').classList.remove();
    document.getElementById('nav-configuracoes').classList.remove();
    // Mostra a seção desejada
    const secaoParaMostrar = document.getElementById(nomeSecao);
    if (secaoParaMostrar) {
        secaoParaMostrar.classList.remove('hidden');
    }
    
    // Adiciona a classe de 'ativo' ao link de navegação clicado
    const navLinkAtivo = document.getElementById(`nav-${nomeSecao.split('-')[1]}`);
    if (navLinkAtivo) {
        navLinkAtivo.classList.add();
    }
}

// --- CONFIGURAÇÃO DE EVENTOS ---

function configurarEventListeners() {
    // Formulário principal de simulação
    document.getElementById('form-simulacao').addEventListener('submit', (e) => {
        e.preventDefault();
        executarSimulacao();
    });

    // Botão para atualizar dados da API Siconfi
    document.getElementById('btn-atualizar').addEventListener('click', atualizarDadosSiconfi);
    
    // Botões e eventos do modal de detalhes
    document.getElementById('btn-fechar-modal').addEventListener('click', esconderModal);
    document.getElementById('btn-fechar-modal-2').addEventListener('click', esconderModal);
    document.getElementById('modal-feedback').addEventListener('click', (e) => {
        if (e.target.id === 'modal-feedback') esconderModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') esconderModal();
    });

    // Adiciona os listeners para o novo modal de monitoramento
    document.getElementById('openMonitoringModalBtn').addEventListener('click', openMonitoringModal);
    document.getElementById('closeMonitoringModalBtn').addEventListener('click', closeMonitoringModal);
    document.getElementById('closeMonitoringModalBtn2').addEventListener('click', closeMonitoringModal);

    // Adiciona os novos listeners para a navegação
    document.getElementById('nav-simulacao').addEventListener('click', (e) => {
        e.preventDefault();
        mostrarSecao('secao-simulacao');
    });


    document.getElementById('nav-configuracoes').addEventListener('click', (e) => {
        e.preventDefault();
        mostrarSecao('secao-configuracoes');
    });

    // Inicializa a lógica do modal de configuração
    initializeDbConfigComponent();
}


// --- COMUNICAÇÃO COM O BACKEND (PYTHON/EEL) ---

async function carregarDadosIniciais() {
    console.log("Buscando dados iniciais do backend...");
    try {
        const resultado = await eel.obter_dados_iniciais()();
        if (resultado.status === 'sucesso') {
            popularSeletorDeAnos(resultado.anos_disponiveis);
            console.log("Anos disponíveis carregados:", resultado.anos_disponiveis);
        } else {
            throw new Error(resultado.mensagem);
        }
    } catch (error) {
        console.error('Erro ao carregar dados iniciais:', error);
        mostrarMensagem('Falha ao carregar dados iniciais do servidor.', 'error');
    }
}

async function executarSimulacao() {
    const ano = parseInt(document.getElementById('ano').value);
    const valorRequisitado = parseFloat(document.getElementById('valor-requisitado').value) || 0;

    console.log(`Iniciando simulação para o ano ${ano} com valor ${valorRequisitado}`);
    mostrarCarregamento(true, 'form-simulacao');

    try {
        const resultado = await eel.analisar_operacao_py(ano, valorRequisitado)();
        console.log("Resultado da análise recebido:", resultado);

        if (resultado.status !== 'Análise completa.') {
            throw new Error(resultado.mensagem || 'Ocorreu um erro desconhecido na análise.');
        }
        
        // A nova função central de renderização
        renderizarResultados(resultado);
        mostrarMensagem(resultado.circuit_breaker
            ? 'FALHA: Operação de Crédito Negada (Circuit Breaker)'
            : 'Análise concluída.', resultado.circuit_breaker ? 'error' : 'info');

    } catch (error) {
        console.error('Erro ao executar simulação:', error);
        mostrarMensagem(`Erro na simulação: ${error.message}`, 'error');
    } finally {
        mostrarCarregamento(false, 'form-simulacao');
    }
}

async function atualizarDadosSiconfi() {
    console.log("Iniciando atualização de dados Siconfi...");
    mostrarCarregamento(true, 'btn-atualizar');
    
    try {
        let estado = await eel.iniciar_atualizacao_siconfi()();
        const botao = document.getElementById('btn-atualizar');
        let etapaAnterior = '';
        while (estado.running) {
            botao.querySelector('.loading-label').textContent = estado.total
                ? `${estado.etapa} · ${estado.concluidas}/${estado.total}` : estado.etapa;
            if (estado.etapa !== etapaAnterior) {
                await carregarDadosIniciais();
                etapaAnterior = estado.etapa;
            }
            await new Promise(resolve => setTimeout(resolve, 1000));
            estado = await eel.status_atualizacao_siconfi()();
        }
        await carregarDadosIniciais();
        mostrarMensagem(estado.falhas
            ? 'Atualização parcial. Os dados disponíveis podem ser consultados; tente novamente mais tarde.'
            : 'Dados atualizados.', estado.falhas ? 'warning' : 'success');

    } catch (error) {
        console.error('Erro ao atualizar dados Siconfi:', error);
        mostrarMensagem('Não foi possível concluir a atualização. Tente novamente mais tarde.', 'error');
    } finally {
        mostrarCarregamento(false, 'btn-atualizar');
    }
}


// --- RENDERIZAÇÃO DA INTERFACE (UI) ---

function popularSeletorDeAnos(anos) {
    const selectAno = document.getElementById('ano');
    selectAno.innerHTML = ''; // Limpa opções antigas
    const anoCorrente = new Date().getFullYear();

    anos.forEach(ano => {
        const option = document.createElement('option');
        option.value = ano;
        option.textContent = ano;
        if (ano === anoCorrente) {
            option.selected = true;
        }
        selectAno.appendChild(option);
    });
}

function renderizarResultados(resultado) {
    const container = document.getElementById('tabela-resultados-container'); // Você precisará criar este container no HTML
    const tbody = document.getElementById('tbody-resultados'); // E este tbody
    
    tbody.innerHTML = ''; // Limpa resultados anteriores
    
    const todasAsRegras = [
        ...(resultado.regras_violadas || []),
        ...(resultado.regras_cumpridas || []),
        ...(resultado.regras_sem_informacao || [])
    ];

    if (todasAsRegras.length === 0) {
        container.style.display = 'none';
        return;
    }

    todasAsRegras.forEach(regra => {
        const tr = document.createElement('tr');
        
        const statusClasse = regra.status === 'Cumprida' 
            ? 'bg-green-100 text-green-800' 
            : regra.status === 'Sem informação' ? 'bg-gray-100 text-gray-800' : 'bg-red-100 text-red-800';

        tr.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${regra.nome}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${statusClasse}">
                    ${regra.status}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-normal text-sm text-gray-500">${regra.descricao}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button class="text-blue-600 hover:text-blue-900 ver-detalhes-btn">Ver Detalhes</button>
            </td>
        `;

        if (regra.tipo === 'dtp') {
            tr.children[1].querySelector('span').textContent = regra.aprovado ? 'Aprovado' : 'Falha';
            tr.children[2].textContent = `${formatarPercentual(regra.dados_calculados.percentual)} — ${regra.descricao}`;
        }
        if (regra.tipo === 'dcl') {
            tr.children[1].querySelector('span').textContent = regra.aprovado === null
                ? 'Sem informação' : regra.aprovado ? 'Aprovado' : 'Recusado';
        }

        // Adiciona o listener no botão para mostrar o modal com os dados da regra específica
        tr.querySelector('.ver-detalhes-btn').addEventListener('click', () => mostrarDetalhesRegra(regra));
        
        tbody.appendChild(tr);
    });

    container.style.display = 'block'; // Mostra a tabela de resultados
}


function mostrarDetalhesRegra(regra) {
    const dtp = regra.tipo === 'dtp' || regra.tipo === 'dcl';
    for (const id of ['modal-descricao', 'modal-proximo-passo', 'modal-base-normativa', 'modal-objetivo']) {
        document.getElementById(id).parentElement.hidden = dtp;
    }
    document.querySelector('#modal-dados-calculados-container > dt').hidden = dtp;
    // Popula o modal com os dados detalhados da regra
    document.getElementById('modal-title').textContent = regra.nome;
    document.getElementById('modal-status').hidden = dtp;
    document.getElementById('modal-status').textContent = dtp ? '' : regra.status;
    document.getElementById('modal-status').className = `font-semibold ${regra.status === 'Cumprida' ? 'text-green-600' : regra.status === 'Sem informação' ? 'text-gray-600' : 'text-red-600'}`;
    
    document.getElementById('modal-descricao').textContent = regra.descricao;
    document.getElementById('modal-proximo-passo').textContent = regra.proximo_passo;
    document.getElementById('modal-base-normativa').textContent = regra.base_normativa;
    document.getElementById('modal-objetivo').textContent = regra.objetivo;
    
    // Constrói a visualização dos dados calculados
    const calculadosContainer = document.getElementById('modal-dados-calculados');
    calculadosContainer.innerHTML = ''; // Limpa
    calculadosContainer.classList.toggle('dtp-cards', dtp);
    
    if (regra.tipo === 'dtp') {
        const dados = regra.dados_calculados;
        const resumo = document.createElement('article');
        resumo.className = `dtp-card ${regra.aprovado ? 'dtp-card-approved' : 'dtp-card-failed'}`;
        const titulo = document.createElement('h4');
        titulo.className = 'dtp-summary-title';
        titulo.textContent = `Total DTP: ${formatarPercentual(dados.percentual)}`;
        const decisao = document.createElement('p');
        decisao.className = 'dtp-message';
        decisao.textContent = `${regra.descricao} — Limite: 60%`;
        const referencia = document.createElement('p');
        referencia.className = 'dtp-reference';
        referencia.textContent = `${dados.quadrimestre}º quadrimestre · Ano de referência ${dados.ano}`;
        resumo.append(titulo, decisao, referencia);
        calculadosContainer.appendChild(resumo);
        const contribuicoes = document.createElement('dl');
        contribuicoes.className = 'dtp-contributions';
        resumo.appendChild(contribuicoes);
        for (const item of dados.poderes) {
            const linha = document.createElement('div');
            linha.className = 'dtp-contribution-row';
            const heading = document.createElement('dt');
            heading.textContent = item.poder;
            const value = document.createElement('dd');
            value.textContent = formatarPercentual(item.percentual);
            linha.append(heading, value);
            contribuicoes.appendChild(linha);
        }
    } else if (regra.tipo === 'dcl') {
        const dados = regra.dados_calculados;
        const card = document.createElement('article');
        card.className = `dtp-card ${regra.aprovado === null ? 'dtp-contribution' : regra.aprovado ? 'dtp-card-approved' : 'dtp-card-failed'}`;
        const titulo = document.createElement('h4');
        titulo.className = 'dtp-summary-title';
        titulo.textContent = regra.aprovado === null ? 'Sem informação' : regra.aprovado ? 'Aprovado' : 'Recusado';
        const descricao = document.createElement('p');
        descricao.className = 'dtp-message';
        descricao.textContent = regra.descricao;
        const referencia = document.createElement('p');
        referencia.className = 'dtp-reference';
        referencia.textContent = `Relatório do ${dados.quadrimestre}º quadrimestre · Ano de referência ${dados.ano}`;
        const lista = document.createElement('dl');
        lista.className = 'dtp-contributions';
        for (const item of dados.valores) {
            const linha = document.createElement('div');
            linha.className = 'dtp-contribution-row';
            const nome = document.createElement('dt');
            nome.textContent = item.rotulo;
            const valor = document.createElement('dd');
            valor.textContent = item.percentual === null ? 'Sem informação' : formatarPercentual(item.percentual);
            linha.append(nome, valor);
            lista.appendChild(linha);
        }
        card.append(titulo, descricao, referencia, lista);
        calculadosContainer.appendChild(card);
    } else if (regra.dados_calculados) {
        for (const [key, value] of Object.entries(regra.dados_calculados)) {
            const div = document.createElement('div');
            div.className = 'py-2';
            
            let content = `<dt class="font-medium text-gray-900">${key.replace(/_/g, ' ')}</dt>`;
            
            if (typeof value === 'object' && value !== null && value.total !== undefined) {
                content += `<dd class="text-gray-700"><strong>Total: ${formatarMoeda(value.total)}</strong></dd>`;
                if(value.detalhe){
                    const detalhesList = Object.entries(value.detalhe)
                        .map(([detalheKey, detalheValue]) => `<li class="ml-4 text-sm">${detalheKey}: ${formatarMoeda(detalheValue)}</li>`)
                        .join('');
                    content += `<ul class="list-disc list-inside">${detalhesList}</ul>`;
                }
            } else {
                content += `<dd class="text-gray-700">${formatarMoeda(value)}</dd>`;
            }
            div.innerHTML = content;
            calculadosContainer.appendChild(div);
        }
    }

    // Mostra o modal
    document.getElementById('modal-feedback').classList.remove('hidden');
}


function esconderModal() {
    document.getElementById('modal-feedback').classList.add('hidden');
}


// --- FUNÇÕES UTILITÁRIAS ---

function formatarMoeda(valor) {
    if (valor === null || valor === undefined || isNaN(valor)) return 'R$ 0,00';
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor);
}

function formatarPercentual(valor) {
    return new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(valor) + '%';
}

function mostrarMensagem(mensagem, tipo = 'info') {
     // Criar elemento de notificação
    const notificacao = document.createElement('div');
    notificacao.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 ${obterClasseTipo(tipo)}`;
    notificacao.textContent = mensagem;
    
    document.body.appendChild(notificacao);
    
    // Remover após 5 segundos
    setTimeout(() => {
        if (notificacao.parentNode) {
            notificacao.parentNode.removeChild(notificacao);
        }
    }, 5000);
}

function obterClasseTipo(tipo) {
    const classes = {
        'success': 'bg-green-500 text-white',
        'error': 'bg-red-500 text-white',
        'warning': 'bg-yellow-500 text-white',
        'info': 'bg-blue-500 text-white'
    };
    
    return classes[tipo] || classes['info'];
}

function mostrarCarregamento(mostrar, elementoId) {
    const elemento = document.getElementById(elementoId);
    let botao;

    if (elemento.tagName === 'BUTTON') {
        botao = elemento;
    } else {
        botao = elemento.querySelector('button[type="submit"]');
    }

    if (!botao) return;

    if (mostrar) {
        if (botao.disabled) return;
        botao.disabled = true;
        botao.setAttribute('aria-busy', 'true');
        botao.dataset.originalText = botao.innerHTML; // Salva o texto original
        botao.innerHTML = `<span class="loading-orbit" aria-hidden="true"></span><span class="loading-label" role="status">${elementoId === 'btn-atualizar' ? 'Sincronizando dados' : 'Analisando operação'}</span>`;
    } else {
        botao.disabled = false;
        botao.removeAttribute('aria-busy');
        botao.innerHTML = botao.dataset.originalText; // Restaura o texto original
    }
}


// ======================================================================
// LÓGICA DO COMPONENTE DE MONITORAMENTO (Atualizada)
// ======================================================================
let monitoringInterval = null;

function initializeMonitoringComponent() {
    // O intervalo agora verifica se o modal está aberto
    monitoringInterval = setInterval(() => {
        const modal = document.getElementById('monitoringModal');
        // Atualiza apenas se o modal estiver visível (não contiver 'hidden')
        if (modal && !modal.classList.contains('hidden')) {
            updateMonitoringData();
        }
    }, 5000); // 5 segundos
}

async function updateMonitoringData() {
    // Esta é a função que busca e renderiza os dados
    try {
        const status = await eel.get_system_status_py()();
        if (status) {
            updateMonitoringUI(status);
        }
    } catch (e) {
        console.error("Erro ao buscar status do sistema:", e);
        // Opcional: mostrar um erro dentro do modal
    }
}

function updateMonitoringUI(status) {
    if (!status) return;

    // Atualiza o Card do Banco de Dados
    const dbIcon = document.getElementById('status-db-icon');
    const dbText = document.getElementById('status-db-text');
    const dbMessage = document.getElementById('status-db-message');
    
    if (status.database.status === 'Online') {
        dbIcon.className = 'w-4 h-4 rounded-full bg-green-500 mr-3';
        dbText.textContent = 'Online';
        dbText.className = 'text-green-600 font-semibold';
    } else {
        dbIcon.className = 'w-4 h-4 rounded-full bg-red-500 mr-3';
        dbText.textContent = status.database.status; // 'Offline' ou 'Erro'
        dbText.className = 'text-red-600 font-semibold';
    }
    dbMessage.textContent = status.database.mensagem;

    // Atualiza o Card de CPU
    document.getElementById('status-cpu-percent').textContent = status.resources.cpu_percent;
    
    // Atualiza o Card de Memória
    document.getElementById('status-memory-mb').textContent = status.resources.memory_mb;
}

// Funções para controlar o modal de monitoramento
function openMonitoringModal() {
    const modal = document.getElementById('monitoringModal');
    modal.style.display = 'flex'; // Usamos flex para centralizar
    modal.classList.remove('hidden');
    
    // Busca os dados imediatamente ao abrir o modal
    updateMonitoringData();
}

function closeMonitoringModal() {
    const modal = document.getElementById('monitoringModal');
    modal.style.display = 'none';
    modal.classList.add('hidden');
}
