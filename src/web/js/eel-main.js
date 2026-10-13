/**
 * JavaScript principal para comunicação com Eel e renderização da interface.
 * Simulador de Operações de Crédito v2 - Refatorado
 */

// --- INICIALIZAÇÃO ---

document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM carregado. Inicializando aplicação...');
    recuperarConexaoBackend();
    configurarEventListeners();
    initializeMonitoringComponent();
    mostrarSecao('secao-painel');
    await Promise.allSettled([carregarDadosIniciais(), carregarPainelFiscal()]);
    sincronizarCronogramaMga();
    atualizarDadosSiconfi();
});

function recuperarConexaoBackend() {
    const socket = eel._websocket;
    if (!socket) return;
    socket.addEventListener('close', async () => {
        const aviso = document.createElement('div');
        aviso.setAttribute('role', 'alert');
        aviso.style.cssText = 'position:fixed;left:16px;right:16px;bottom:16px;z-index:9999;padding:14px;background:#fff;border:1px solid #aab4be;border-radius:8px;box-shadow:0 4px 16px #0002;color:#17212f';
        aviso.textContent = 'Conexão com o aplicativo interrompida. Tentando reconectar...';
        document.body.appendChild(aviso);
        for (let tentativa = 0; tentativa < 20; tentativa++) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            try {
                const resposta = await fetch('/eel.js', {cache: 'no-store'});
                if (resposta.ok) {
                    window.location.reload();
                    return;
                }
            } catch (_) { /* O servidor pode estar reiniciando. */ }
        }
        aviso.textContent = 'O backend foi encerrado. Feche e abra o aplicativo novamente. Se persistir, consulte app.log na pasta do programa.';
    });
}

// --- LÓGICA DE NAVEGAÇÃO ENTRE SEÇÕES ---
function mostrarSecao(nomeSecao) {
    for (const id of ['secao-painel', 'secao-limites', 'secao-simulacao', 'secao-configuracoes']) {
        document.getElementById(id).classList.add('hidden');
    }
    const secaoParaMostrar = document.getElementById(nomeSecao);
    if (secaoParaMostrar) secaoParaMostrar.classList.remove('hidden');
    const navegacao = {'secao-painel': 'nav-painel', 'secao-limites': 'nav-limites',
        'secao-simulacao': 'nav-simulacao',
        'secao-configuracoes': 'nav-configuracoes'};
    for (const id of Object.values(navegacao)) {
        const botao = document.getElementById(id);
        botao.classList.toggle('ativo', id === navegacao[nomeSecao]);
        if (id === navegacao[nomeSecao]) botao.setAttribute('aria-current', 'page');
        else botao.removeAttribute('aria-current');
    }
}

// --- CONFIGURAÇÃO DE EVENTOS ---

function configurarEventListeners() {
    const campoValorRequisitado = document.getElementById('valor-requisitado');
    campoValorRequisitado.addEventListener('input', () => {
        campoValorRequisitado.setCustomValidity('');
        campoValorRequisitado.removeAttribute('aria-invalid');
        const erro = document.getElementById('valor-erro');
        erro.hidden = true;
        erro.textContent = '';
        sincronizarCronogramaMga();
    });
    campoValorRequisitado.addEventListener('blur', () => {
        try {
            campoValorRequisitado.value = lerValorRequisitado(campoValorRequisitado.value).formatado;
            campoValorRequisitado.setCustomValidity('');
        } catch (error) {
            campoValorRequisitado.setCustomValidity(error.message);
            campoValorRequisitado.setAttribute('aria-invalid', 'true');
            const erro = document.getElementById('valor-erro');
            erro.textContent = error.message;
            erro.hidden = false;
        }
    });
    // Formulário principal de simulação
    document.getElementById('form-simulacao').addEventListener('submit', (e) => {
        e.preventDefault();
        executarSimulacao();
    });
    document.getElementById('ano').addEventListener('change', () => { montarLinhasServico(); invalidarCoberturaCaed(); carregarFatorCaed(); sincronizarCronogramaMga(true); });
    document.getElementById('ano-fim-contrato').addEventListener('change', () => { montarLinhasServico(); invalidarCoberturaCaed(); marcarSimulacaoDesatualizada(); });
    document.getElementById('caed-data-referencia').addEventListener('change', carregarFatorCaed);
    document.getElementById('fator-rcl').addEventListener('change', () => {
        const campo = document.getElementById('fator-rcl');
        campo.salvamentoCaed = salvarTaxaCaed();
    });
    for (const id of ['caed-fonte-demais', 'caed-data-cobertura']) {
        document.getElementById(id).addEventListener('input', invalidarCoberturaCaed);
    }
    document.getElementById('btn-recalcular-servico').addEventListener('click', () => executarSimulacao(true));
    document.getElementById('btn-recalcular-mga').addEventListener('click', () => executarSimulacao(true));
    document.getElementById('mga-cronograma-modo').addEventListener('change', () => {
        const grade = document.getElementById('fluxo-credito-linhas');
        if (grade.dataset.modo === 'annual_schedule') grade.dataset.fimAnual = document.getElementById('mga-ano-fim').value;
        else if (grade.dataset.fimAnual && document.getElementById('mga-cronograma-modo').value === 'annual_schedule') {
            document.getElementById('mga-ano-fim').value = grade.dataset.fimAnual;
        }
        sincronizarCronogramaMga();
    });
    document.getElementById('mga-escopo').addEventListener('change', () => sincronizarCronogramaMga());

    for (const id of ['mga-ano-inicio', 'mga-ano-fim']) document.getElementById(id).addEventListener('change', () => {
        sincronizarCronogramaMga();
    });
    document.getElementById('secao-simulacao').addEventListener('input', marcarSimulacaoDesatualizada);
    document.getElementById('secao-simulacao').addEventListener('change', marcarSimulacaoDesatualizada);
    document.getElementById('modal-feedback').addEventListener('input', marcarSimulacaoDesatualizada);
    document.getElementById('modal-feedback').addEventListener('change', marcarSimulacaoDesatualizada);
    document.getElementById('btn-relatorio-simulacao').addEventListener('click', baixarRelatorioSimulacao);

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
    document.getElementById('nav-painel').addEventListener('click', () => mostrarSecao('secao-painel'));
    document.getElementById('nav-limites').addEventListener('click', () => { mostrarSecao('secao-limites'); carregarSadipemLimites(); });
    document.getElementById('btn-ver-limites').addEventListener('click', () => { mostrarSecao('secao-limites'); carregarSadipemLimites(); });
    document.getElementById('btn-simular-limites').addEventListener('click', () => mostrarSecao('secao-simulacao'));
    document.getElementById('btn-nova-operacao').addEventListener('click', () => {
        mostrarSecao('secao-simulacao');
        document.getElementById('secao-simulacao').scrollIntoView({behavior: 'smooth', block: 'start'});
        document.getElementById('ano').focus({preventScroll: true});
    });


    document.getElementById('nav-configuracoes').addEventListener('click', (e) => {
        e.preventDefault();
        mostrarSecao('secao-configuracoes');
    });

    // Inicializa a lógica do modal de configuração
    initializeDbConfigComponent();
}


// --- COMUNICAÇÃO COM O BACKEND (PYTHON/EEL) ---

let painelFiscalAtual = null;
let resultadoSimulacaoAtual = null;
let revisaoSimulacao = 0;
let resultadoDesatualizado = false;
let consultaSadipemEmCurso = null;

function sincronizarCronogramaMga(reiniciar = false) {
    const container = document.getElementById('fluxo-credito-linhas');
    const integral = false;
    container.dataset.modo = 'annual_schedule';
    if (reiniciar) delete container.dataset.fimAnual;
    const referencia = document.getElementById('ano').value;
    const inicio = document.getElementById('mga-ano-inicio');
    const fim = document.getElementById('mga-ano-fim');
    if (reiniciar || (!container.dataset.periodo && !inicio.value && !fim.value)) {
        inicio.value = referencia;
        fim.value = referencia;
    }
    inicio.min = referencia;
    const inicioValido = inicio.value !== '' && Number.isInteger(Number(inicio.value))
        && Number(inicio.value) >= Number(referencia) && Number(inicio.value) <= 2100;
    fim.min = inicioValido ? inicio.value : referencia;
    fim.disabled = integral || !inicioValido;
    fim.parentElement.hidden = false;
    document.getElementById('mga-inicio-rotulo').textContent = 'Primeiro ano de liberação';
    document.getElementById('mga-periodo-ajuda').textContent = integral
        ? 'O valor requisitado será recebido integralmente nesse exercício.'
        : 'Preencha primeiro o ano inicial e depois o final, que não pode ser menor que o inicial. A grade inclui todos os exercícios desse intervalo.';
    const inicial = Number(inicio.value), final = Number(fim.value);
    const valido = inicioValido && fim.value !== '' && Number.isInteger(final) && inicial >= Number(referencia)
        && final >= inicial && final <= 2100 && final - inicial < 81;
    const periodo = `${integral}:${inicial}:${final}`;
    if (reiniciar || container.dataset.periodo !== periodo || !container.children.length) {
        const anteriores = reiniciar ? new Map() : new Map([...container.querySelectorAll('[data-ano]')]
            .map(linha => [Number(linha.dataset.ano), linha.querySelector('input').value]));
        container.replaceChildren();
        if (valido) for (let a = inicial; a <= final; a++) {
            adicionarLinhaFluxoCredito(a);
            container.lastElementChild.querySelector('input').value = anteriores.get(a) ?? '';
        }
        container.dataset.periodo = periodo;
    }
    let total = null;
    try { const texto = document.getElementById('valor-requisitado').value.trim(); total = texto ? lerValorRequisitado(texto).numero : null; }
    catch (_) { /* O formulário principal apresenta o erro de valor. */ }
    const unicoExercicio = valido && inicial === final;
    for (const input of container.querySelectorAll('input')) input.readOnly = unicoExercicio;
    if (unicoExercicio) container.querySelector('input').value = total == null ? '' : String(total);
    document.getElementById('mga-valor-resumo').textContent = valido
        ? `Valor requisitado: ${total == null ? 'Aguardando preenchimento' : formatarMoeda(total)}. ${unicoExercicio ? 'Liberação integral no ano selecionado; valor reutilizado dos dados da operação.' : 'A soma das liberações anuais deve corresponder a esse valor.'}`
        : 'Período inválido: use anos a partir do exercício da análise, com ano final igual ou posterior ao inicial.';
    marcarSimulacaoDesatualizada();
}

function obterEntradaMga() {
    const taxa = document.getElementById('fator-rcl').value.trim().replace(/%$/, '').trim().replace(',', '.');
    if (!taxa || !Number.isFinite(Number(taxa)) || Number(taxa) <= -100) {
        throw new Error('Informe uma taxa anual de projeção da RCL válida nos dados da operação.');
    }
    const inicio = Number(document.getElementById('mga-ano-inicio').value);
    const fim = Number(document.getElementById('mga-ano-fim').value);
    if (!Number.isInteger(inicio) || inicio < Number(document.getElementById('ano').value)
        || !Number.isInteger(fim) || fim < inicio || fim > 2100 || fim - inicio >= 81) {
        throw new Error('Confira o período das liberações: o ano final deve ser igual ou posterior ao inicial, a partir do exercício da análise.');
    }
    return {scope: document.getElementById('mga-escopo').value,
        mode: document.getElementById('mga-cronograma-modo').value,
        releaseStart: Number(document.getElementById('mga-ano-inicio').value),
        releaseEnd: Number(document.getElementById('mga-ano-fim').value),
        operationIdentifier: document.getElementById('mga-identificador').value.trim() || null,
        projectionParameter: {value: taxa, unit: 'percent',
            source: 'Taxa local compartilhada da operação — CAED e MGA',
            date: document.getElementById('caed-data-referencia').value},
        rows: [...document.querySelectorAll('#fluxo-credito-linhas .fluxo-sim-linha')].map(linha => ({
            ano: Number(linha.dataset.ano),
            liberacaoNovaOperacao: linha.querySelector('input').value.trim() === '' ? null : Number(linha.querySelector('input').value)
        }))};
}

async function carregarMemoriaMga() {
    const destino = document.getElementById('mga-memoria-lista');
    try {
        const operacoes = await eel.listar_operacoes_mga_py()();
        destino.replaceChildren();
        for (const op of operacoes) {
            const botao = document.createElement('button');
            botao.type = 'button';
            botao.className = 'jornada-link';
            botao.textContent = `${op.identificador} · ${op.situacao} · ${op.anoInicio}–${op.anoFim} · Editar`;
            botao.addEventListener('click', () => {
                const formulario = document.getElementById('form-mga-memoria');
                for (const campo of ['identificador', 'situacao', 'valorTotal', 'anoInicio', 'anoFim', 'fonte']) formulario.elements[campo].value = op[campo];
                formulario.elements.cronogramaCompleto.checked = op.cronogramaCompleto;
                formulario.elements.cronograma.value = op.liberacoes.map(l => `${l.ano};${l.valor}`).join('\n');
            });
            destino.appendChild(botao);
        }
        if (!operacoes.length) destino.textContent = 'Nenhuma operação cadastrada; a cobertura precisa ser conferida.';
    } catch (error) {
        destino.textContent = `Não foi possível carregar a memória: ${error.message}`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    carregarMemoriaMga();
    const mensagem = document.getElementById('mga-memoria-mensagem');
    document.getElementById('form-mga-memoria').addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.target;
        try {
            const entrada = Object.fromEntries(new FormData(form));
            entrada.anoInicio = Number(entrada.anoInicio);
            entrada.anoFim = Number(entrada.anoFim);
            entrada.valorTotal = Number(entrada.valorTotal);
            entrada.cronogramaCompleto = form.elements.cronogramaCompleto.checked;
            entrada.liberacoes = entrada.cronograma.trim() === '' ? [] : entrada.cronograma.trim().split(/\r?\n/).map(linha => {
                const campos = linha.split(';');
                if (campos.length !== 2 || campos.some(c => c.trim() === '')) throw new Error('Use ano;valor, com ponto para decimais.');
                return {ano: Number(campos[0]), valor: Number(campos[1])};
            });
            const resposta = await eel.salvar_operacao_mga_py(entrada)();
            if (resposta.status !== 'sucesso') throw new Error(resposta.mensagem);
            mensagem.textContent = 'Operação salva. Confira e confirme novamente a cobertura do inventário.';
            marcarSimulacaoDesatualizada();
            await carregarMemoriaMga();
            await carregarPainelFiscal();
        } catch (error) { mensagem.textContent = error.message; }
    });
    document.getElementById('form-mga-cobertura').addEventListener('submit', async event => {
        event.preventDefault();
        const form = event.target;
        try {
            const resposta = await eel.confirmar_cobertura_mga_py(Number(form.elements.inicio.value), Number(form.elements.fim.value), form.elements.fonte.value)();
            if (resposta.status !== 'sucesso') throw new Error(resposta.mensagem);
            mensagem.textContent = 'Cobertura confirmada. Recalcule a simulação para usar o inventário atualizado.';
            marcarSimulacaoDesatualizada();
            await carregarPainelFiscal();
        } catch (error) { mensagem.textContent = error.message; }
    });
});

function adicionarLinhaFluxoCredito(anoExplicito) {
    const container = document.getElementById('fluxo-credito-linhas');
    if (container.children.length >= 81) return;
    const anoBase = Number(document.getElementById('mga-ano-inicio').value) || Number(document.getElementById('ano').value);
    const ano = Number.isInteger(anoExplicito) ? anoExplicito
        : container.children.length ? Number(container.lastElementChild.dataset.ano) + 1 : anoBase;
    const linha = document.createElement('div');
    linha.className = 'fluxo-sim-linha';
    linha.dataset.ano = String(ano);
    for (const [chave, rotulo] of [
        ['liberacaoNovaOperacao', 'Nova operação · liberação (R$)']
    ]) {
        const label = document.createElement('label');
        label.textContent = rotulo;
        const input = document.createElement('input');
        input.type = 'number';
        input.min = '0';
        input.step = '0.01';
        input.dataset.campo = chave;
        input.addEventListener('input', () => {
            marcarSimulacaoDesatualizada();
        });
        input.setAttribute('aria-label', `${rotulo} em ${ano}`);
        label.appendChild(input);
        linha.appendChild(label);
    }
    const titulo = document.createElement('strong');
    titulo.textContent = `Exercício ${ano}`;
    linha.prepend(titulo);
    container.appendChild(linha);
    if (!Number.isInteger(anoExplicito)) document.getElementById('mga-ano-fim').value = ano;
    marcarSimulacaoDesatualizada();
}

async function carregarSadipemLimites() {
    if (consultaSadipemEmCurso) return consultaSadipemEmCurso;
    if (!painelFiscalAtual?.exercicio) return;
    if (painelFiscalAtual.sadipem && painelFiscalAtual.sadipem.motivo !== 'API_ERROR' &&
        painelFiscalAtual.margemPublica && painelFiscalAtual.margemPublica.status !== 'Consultando') return;
    const painelConsultado = painelFiscalAtual;
    painelConsultado.margemPublica = {status: 'Consultando'};
    renderizarVisaoFiscal(painelConsultado);
    consultaSadipemEmCurso = (async () => {
        try {
            const resposta = await eel.obter_comprometimento_sadipem_py()();
            if (resposta.status !== 'sucesso') throw new Error(resposta.mensagem);
            if (painelConsultado !== painelFiscalAtual) return;
            painelFiscalAtual.sadipem = resposta.sadipem;
            painelFiscalAtual.margemPublica = resposta.margemPublica;
            renderizarVisaoFiscal(painelFiscalAtual);
        } catch (error) {
            if (painelConsultado !== painelFiscalAtual) return;
            console.error('Erro ao consultar SADIPEM:', error);
            painelFiscalAtual.sadipem = {statusDadosMga: 'Unavailable', motivo: 'API_ERROR'};
            painelFiscalAtual.margemPublica = null;
            renderizarVisaoFiscal(painelFiscalAtual);
        } finally {
            consultaSadipemEmCurso = null;
            if (painelConsultado !== painelFiscalAtual) carregarSadipemLimites();
        }
    })();
    return consultaSadipemEmCurso;
}

async function carregarPainelFiscal() {
    try {
        const resposta = await eel.obter_painel_fiscal_py()();
        if (resposta.status !== 'sucesso') throw new Error(resposta.mensagem);
        const anterior = painelFiscalAtual;
        const atual = resposta.painel;
        if (anterior?.sadipem && anterior.sadipem.motivo !== 'API_ERROR' &&
            anterior.margemPublica && anterior.margemPublica.status !== 'Consultando' &&
            mesmaBaseMargemPublica(anterior, atual)) {
            atual.sadipem = anterior.sadipem;
            atual.margemPublica = anterior.margemPublica;
        }
        painelFiscalAtual = atual;
        renderizarPainelFiscal(resposta.painel);
        carregarSadipemLimites();
    } catch (error) {
        console.error('Erro ao carregar painel fiscal:', error);
        document.getElementById('painel-estado-dados').textContent = 'Não foi possível carregar os dados';
        document.getElementById('painel-alertas').textContent = 'Não foi possível consultar o painel fiscal. Tente novamente após verificar a conexão com o banco de dados.';
    }
}

function mesmaBaseMargemPublica(anterior, atual) {
    const base = painel => ({
        exercicio: painel.exercicio,
        rcl: Object.fromEntries(['valor', 'exercicio', 'ano', 'periodo', 'conta', 'coluna', 'anexo', 'uf', 'esfera']
            .map(chave => [chave, painel.rcl?.[chave] ?? null])),
        projecao: (painel.fluxo_credito?.rows || []).map(linha =>
            [linha.ano, linha.rclProjetada, linha.tetoAnual]),
        parametroValidado: painel.fluxo_credito?.parameterValidated ?? null
    });
    return JSON.stringify(base(anterior)) === JSON.stringify(base(atual));
}

function renderizarPainelFiscal(painel) {
    const criar = (tag, classe, texto) => {
        const no = document.createElement(tag);
        no.className = classe;
        if (texto !== undefined) no.textContent = texto;
        return no;
    };
    const dataConsulta = painel.ultima_consulta
        ? new Date(painel.ultima_consulta).toLocaleString('pt-BR') : null;
    document.getElementById('painel-exercicio').textContent = painel.exercicio
        ? `Exercício dos dados: ${painel.exercicio}` : 'Exercício: não disponível';
    const periodo = painel.dtp ? `${painel.dtp.periodo}º quadrimestre de ${painel.dtp.ano} · DTP`
        : painel.dcl ? `${painel.dcl.periodo}º quadrimestre de ${painel.dcl.ano} · DCL`
        : painel.rcl ? `${painel.rcl.periodo}º bimestre de ${painel.rcl.ano} · RCL` : null;
    document.getElementById('painel-periodo').textContent = periodo
        ? `Período mais recente exibido: ${periodo}` : 'Período: não disponível';
    document.getElementById('painel-fonte').textContent = painel.capag
        ? 'Fontes: SICONFI e Tesouro Transparente' : 'Fonte: SICONFI';
    document.getElementById('painel-consulta').textContent = dataConsulta
        ? `Última consulta registrada: ${dataConsulta}` : 'Última consulta: não registrada';
    document.getElementById('painel-estado-dados').textContent = painel.dados_disponiveis === 0
        ? 'Dados fiscais não encontrados' : 'Dados fiscais publicados';

    renderizarVisaoFiscal(painel);

    document.getElementById('painel-contagem').textContent = dataConsulta
        ? `Última consulta registrada: ${dataConsulta}` : 'Data da última consulta não registrada.';
    const fontes = document.getElementById('painel-fontes');
    fontes.replaceChildren();
    for (const item of (painel.fontes || []).filter(fonte => !fonte.indicador?.startsWith('Regra de Ouro'))) {
        const linha = criar('div', 'painel-source-row');
        linha.append(criar('strong', '', item.indicador),
            criar('span', '', item.anexo
                ? `${item.origem} · ${item.anexo} · ${item.periodo}º ${item.anexo.includes('RGF') ? 'quadrimestre' : 'bimestre'} de ${item.ano}`
                : `${item.origem} · publicação de ${item.ano}`));
        fontes.appendChild(linha);
    }
    if (!fontes.children.length) fontes.appendChild(criar('p', 'painel-help', 'Nenhuma fonte fiscal disponível.'));

    const alertas = document.getElementById('painel-alertas');
    alertas.replaceChildren();
}

async function carregarDadosIniciais() {
    console.log("Buscando dados iniciais do backend...");
    try {
        const resultado = await eel.obter_dados_iniciais()();
        if (resultado.status === 'sucesso') {
            popularSeletorDeAnos(resultado.anos_disponiveis);
            montarLinhasServico();
            await carregarFatorCaed();
            console.log("Anos disponíveis carregados:", resultado.anos_disponiveis);
        } else {
            throw new Error(resultado.mensagem);
        }
    } catch (error) {
        console.error('Erro ao carregar dados iniciais:', error);
        mostrarMensagem('Falha ao carregar dados iniciais do servidor.', 'error');
    }
}

function marcarSimulacaoDesatualizada() {
    if (resultadoSimulacaoAtual && !resultadoDesatualizado && resultadoSimulacaoAtual.assinatura === assinaturaEntradasSimulacao()) return;
    revisaoSimulacao++;
    if (resultadoSimulacaoAtual) {
        resultadoDesatualizado = true;
        document.getElementById('simulacao-atualidade').textContent = 'Resultados desatualizados — recalcule a simulação.';
        document.getElementById('tbody-resultados').classList.add('resultados-desatualizados');
        document.getElementById('fluxo-credito-resultado').textContent = 'Resultados desatualizados';
    } else document.getElementById('fluxo-credito-resultado').textContent = 'Aguardando preenchimento';
    document.getElementById('btn-relatorio-simulacao').disabled = true;
}

function invalidarCoberturaCaed() {
    document.getElementById('caed-cobertura-completa').checked = false;
}

async function carregarFatorCaed() {
    const data = document.getElementById('caed-data-referencia').value;
    const campo = document.getElementById('fator-rcl');
    const origem = document.getElementById('caed-fator-origem');
    campo.value = '';
    origem.textContent = 'Consultando referência documentada do fator CAED...';
    try {
        const fator = await eel.obter_fator_projecao_py(data)();
        if (data !== document.getElementById('caed-data-referencia').value) return;
        campo.value = fator ? `${String(fator.taxa_percentual ?? '').replace('.', ',')}%` : '';
        origem.textContent = fator ? 'Taxa armazenada para as próximas consultas.'
            : 'Fator não validado para esta referência — análise INCONCLUSIVA.';
    } catch (_) {
        if (data === document.getElementById('caed-data-referencia').value) origem.textContent = 'Fator indisponível — análise INCONCLUSIVA.';
    }
}

async function salvarTaxaCaed() {
    const campo = document.getElementById('fator-rcl');
    marcarSimulacaoDesatualizada();
    try {
        const resposta = await eel.salvar_fator_projecao_py(campo.value)();
        if (resposta.status !== 'sucesso') throw new Error(resposta.mensagem);
        campo.value = `${String(resposta.fator).replace('.', ',')}%`;
        document.getElementById('caed-fator-origem').textContent = 'Taxa salva para as próximas consultas.';
    } catch (erro) {
        document.getElementById('caed-fator-origem').textContent = `Taxa não salva: ${erro.message}`;
        campo.setCustomValidity('Salve uma taxa válida antes de simular.');
        return;
    }
    campo.setCustomValidity('');
}

function normalizarPagamentoCaed(valor, campo = 'Pagamento') {
    const texto = String(valor ?? '').trim();
    const decimais = texto.split(',')[1] || '';
    if (decimais.length > 2 && /[1-9]/.test(decimais.slice(2))) throw new Error(`${campo}: informe no máximo duas casas decimais.`);
    return normalizarValorMonetario(valor, campo);
}

function assinaturaEntradasSimulacao() {
    return JSON.stringify([...document.querySelectorAll('#secao-simulacao input, #secao-simulacao select, #secao-simulacao textarea, #modal-feedback input, #modal-feedback select, #modal-feedback textarea')]
        .map(campo => [campo.id || campo.name || campo.getAttribute('aria-label'), campo.value, campo.type === 'checkbox' ? campo.checked : null]));
}

function editarCronogramaFinanceiro() {
    const mga = document.getElementById('modal-feedback').dataset.regraTipo === 'mga';
    const alvo = document.getElementById(mga ? 'mga-entradas' : 'cronograma-pagamentos');
    if (!mga) alvo.open = true;
    alvo.scrollIntoView({behavior:'smooth', block:'nearest'});
}

function criarRegraMga(projecao) {
    const linha = (projecao.rows || []).find(item => item.ano === (projecao.criticalYear ?? projecao.ano));
    return {tipo:'mga', nome:'Liberações de crédito — limite de 16% da RCL',
        status:resultadoVisualMga(projecao),
        descricao:linha?.margemEstimada != null
            ? `Saldo após a nova operação em ${linha.ano}: ${formatarMoeda(linha.margemEstimada)}.${projecao.publicReference ? ' Demais liberações segundo o PVL; conferir cobertura.' : ''}`
            : 'Faltam dados para apurar o saldo anual. Confira a composição em Ver Detalhes.',
        base_normativa:'RSF 43/2001, art. 7º, I, §§ 1º e 6º; MIP 2026.08.21',
        proximo_passo:'Conferir fontes, cobertura e demais verificações.',
        objetivo:'Comparar as liberações anuais incluídas no cálculo com 16% da RCL projetada.',
        dados_calculados:projecao};
}

function baixarRelatorioSimulacao() {
    if (!resultadoSimulacaoAtual || resultadoDesatualizado) return;
    const relatorio = {titulo:'Relatório da simulação de operação de crédito',
        geradoEm:new Date().toISOString(), calculadoEm:resultadoSimulacaoAtual.calculadoEm,
        entradas:resultadoSimulacaoAtual.entradas, resultados:resultadoSimulacaoAtual.resultado};
    const documento = document.implementation.createHTMLDocument(relatorio.titulo);
    documento.documentElement.lang = 'pt-BR';
    const charset = documento.createElement('meta'); charset.setAttribute('charset', 'utf-8'); documento.head.prepend(charset);
    const estilo = documento.createElement('style');
    estilo.textContent = 'body{font:15px Arial,sans-serif;margin:30px;color:#17382f}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #ccc;padding:8px;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{margin:24px 0}a{color:#006b47}progress{display:none}@media print{body{margin:10px}details{display:block}}';
    documento.head.appendChild(estilo);
    documento.body.appendChild(elementoFiscal('h1', '', relatorio.titulo));
    documento.body.appendChild(elementoFiscal('p', '', `Calculado em ${relatorio.calculadoEm}; ano de referência ${relatorio.entradas.ano}; valor requisitado ${formatarMoeda(relatorio.entradas.valorRequisitado)}.`));
    for (const regra of relatorio.resultados.regras_ordenadas || []) {
        const secao = elementoFiscal('section');
        secao.append(elementoFiscal('h2', '', regra.nome), elementoFiscal('p', '', `${regra.status}: ${regra.descricao}`));
        if (regra.tipo === 'servico_divida') {
            secao.appendChild(criarMemoriaCaed(regra));
            const historico = regra.dados_calculados.historico;
            secao.appendChild(elementoFiscal('p', '', historico
                ? `Diagnóstico histórico separado: serviço ${formatarMoeda(historico.servico_divida)} / RCL ${formatarMoeda(historico.rcl)}; ${historico.situacao}. Não bloqueia a análise prospectiva.`
                : 'Diagnóstico histórico indisponível; não bloqueia a análise prospectiva.'));
        } else {
            const memoria = elementoFiscal('details'); memoria.appendChild(elementoFiscal('summary', '', 'Memória desta verificação'));
            memoria.appendChild(elementoFiscal('pre', '', JSON.stringify(regra, null, 2))); secao.appendChild(memoria);
        }
        documento.body.appendChild(secao);
    }
    documento.body.appendChild(elementoFiscal('h2', '', 'Liberações de crédito — limite de 16% da RCL'));
    documento.body.appendChild(criarTabelaMga(relatorio.resultados.mgaProjection));
    const dados = elementoFiscal('details'); dados.appendChild(elementoFiscal('summary', '', 'Entradas e resultados completos do cálculo'));
    // CAED é apresentado em tabela e memória decimal, sem uma regra em JSON.
    const outrasMemorias = { ...relatorio, entradas: {...relatorio.entradas, servico: undefined},
        resultados: {...relatorio.resultados} };
    for (const chave of ['regras_ordenadas', 'regras_cumpridas', 'regras_violadas', 'regras_sem_informacao']) {
        if (outrasMemorias.resultados[chave]) outrasMemorias.resultados[chave] = outrasMemorias.resultados[chave].filter(r => r.tipo !== 'servico_divida');
    }
    const memoria = elementoFiscal('pre', '', JSON.stringify(outrasMemorias, null, 2)); memoria.id = 'memoria-relatorio'; dados.appendChild(memoria);
    documento.body.appendChild(dados);
    const blob = new Blob(['<!DOCTYPE html>' + documento.documentElement.outerHTML], {type:'text/html;charset=utf-8'});
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob);
    link.download = 'relatorio-simulacao.html'; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

async function executarSimulacao(usarProjecaoServico = false) {
    const campoTaxa = document.getElementById('fator-rcl');
    if (campoTaxa?.salvamentoCaed) await campoTaxa.salvamentoCaed;
    if (campoTaxa?.validationMessage) {
        campoTaxa.reportValidity();
        return;
    }
    const ano = parseInt(document.getElementById('ano').value);
    if (!Number.isInteger(ano)) {
        mostrarMensagem('Selecione um ano de referência disponível para continuar.', 'error');
        document.getElementById('ano').focus();
        return;
    }
    let valorRequisitado;
    try {
        if (!document.getElementById('valor-requisitado').value.trim()) throw new Error('Aguardando preenchimento: informe o Valor requisitado.');
        valorRequisitado = lerValorRequisitado(document.getElementById('valor-requisitado').value).numero;
    } catch (error) {
        const campo = document.getElementById('valor-requisitado');
        const erro = document.getElementById('valor-erro');
        campo.setAttribute('aria-invalid', 'true');
        erro.textContent = error.message;
        erro.hidden = false;
        campo.focus();
        return;
    }
    const modal = document.getElementById('modal-feedback');
    const modalServico = usarProjecaoServico && !modal.classList.contains('hidden') &&
        ['servico_divida', 'mga'].includes(modal.dataset.regraTipo);
    const botaoCarregamento = modalServico ? (modal.dataset.regraTipo === 'mga' ? 'btn-recalcular-mga' : 'btn-recalcular-servico') : 'form-simulacao';
    const botao = botaoCarregamento === 'form-simulacao'
        ? document.querySelector('#form-simulacao button[type="submit"]')
        : document.getElementById(botaoCarregamento);
    if (botao.disabled) return;

    console.log(`Iniciando simulação para o ano ${ano} com valor ${valorRequisitado}`);
    mostrarCarregamento(true, botaoCarregamento);

    try {
        const revisao = revisaoSimulacao;
        const assinatura = assinaturaEntradasSimulacao();
        let entradaServico, entradaMga;
        try { entradaServico = obterEntradaServico(); }
        catch (erro) { entradaServico = {erro_entrada: erro.message}; }
        try { entradaMga = obterEntradaMga(); }
        catch (erro) { entradaMga = {erro_entrada: erro.message}; }
        const resultado = await eel.analisar_operacao_py(ano, valorRequisitado, entradaServico, entradaMga)();
        if (revisao !== revisaoSimulacao || assinatura !== assinaturaEntradasSimulacao()) { mostrarMensagem('As entradas mudaram durante o cálculo. Recalcule a simulação.', 'warning'); return; }
        console.log("Resultado da análise recebido:", resultado);

        if (resultado.status !== 'Análise completa.') throw new Error(resultado.mensagem || 'Não foi possível concluir a simulação. Verifique os dados informados ou tente novamente.');
        
        resultadoSimulacaoAtual = {calculadoEm:new Date().toISOString(), assinatura,
            entradas:{ano, valorRequisitado, servico:entradaServico, mga:entradaMga}, resultado};
        resultadoDesatualizado = false;
        document.getElementById('simulacao-atualidade').textContent = 'Resultados atualizados';
        document.getElementById('tbody-resultados').classList.remove('resultados-desatualizados');
        document.getElementById('btn-relatorio-simulacao').disabled = false;
        renderizarResultados(resultado);
        if (modalServico) {
            const regra = modal.dataset.regraTipo === 'mga' ? criarRegraMga(resultado.mgaProjection)
                : resultado.regras_ordenadas.find(item => item.tipo === 'servico_divida');
            if (regra) mostrarDetalhesRegra(regra);
        }
        const destinoMga = document.getElementById('fluxo-credito-resultado');
        destinoMga.textContent = 'Confira Liberações de crédito na lista de verificações abaixo.';
        if (!modalServico) mostrarSecao('secao-simulacao');
        if (modalServico) {
            const alvo = document.getElementById('servico-resultados');
            alvo?.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        }
        if (!modalServico) {
            const regrasReprovadas = [...new Set((resultado.regras_violadas || [])
                .map(regra => regra.nome).filter(Boolean))];
            const detalheFalhas = regrasReprovadas.length
                ? `\n${regrasReprovadas.length === 1 ? 'Regra reprovada' : 'Regras reprovadas'}: ${regrasReprovadas.join('; ')}`
                : '';
            if (resultado.circuit_breaker) {
                mostrarMensagem(`Há regra reprovada nesta simulação.${detalheFalhas}`, 'error');
            } else if (regrasReprovadas.length) {
                mostrarMensagem(`Análise concluída com reprovação.${detalheFalhas}`, 'error');
            } else {
                mostrarMensagem('Verificações concluídas. Confira os resultados disponíveis.', 'info');
            }
        }

    } catch (error) {
        console.error('Erro ao executar simulação:', error);
        mostrarMensagem(error.message || 'Não foi possível concluir a simulação. Verifique os dados informados ou tente novamente.', 'error');
    } finally {
        mostrarCarregamento(false, botaoCarregamento);
    }
}

let atualizacaoEmAndamento = false;

async function atualizarDadosSiconfi() {
    if (atualizacaoEmAndamento) return;
    atualizacaoEmAndamento = true;
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
                await carregarPainelFiscal();
                etapaAnterior = estado.etapa;
            }
            await new Promise(resolve => setTimeout(resolve, 1000));
            estado = await eel.status_atualizacao_siconfi()();
        }
        await carregarDadosIniciais();
        await carregarPainelFiscal();
        if (!document.getElementById('secao-simulacao').classList.contains('hidden') &&
            document.getElementById('tbody-resultados').children.length > 0) {
            await executarSimulacao();
        } else {
            document.getElementById('tbody-resultados').replaceChildren();
            document.getElementById('tabela-resultados-container').style.display = 'none';
        }
        if (estado.falhas) {
            const detalhes = (estado.detalhes_falhas || []).slice(0, 2).map(falha => {
                const referencia = [falha.ano, falha.periodo ? `${falha.periodo}º período` : null,
                    falha.anexo, falha.poder ? `Poder ${falha.poder}` : null].filter(Boolean).join(', ');
                return `${falha.etapa}${referencia ? ` (${referencia})` : ''}: ${falha.motivo}`;
            });
            mostrarMensagem(`Atualização parcial: ${estado.falhas} consulta(s) não concluída(s). Os dados existentes continuam disponíveis.${detalhes.length ? `\n${detalhes.join('\n')}` : ''}`, 'warning');
        } else {
            mostrarMensagem('Dados atualizados.', 'success');
        }

    } catch (error) {
        console.error('Erro ao atualizar dados Siconfi:', error);
        mostrarMensagem('Não foi possível concluir a atualização. Tente novamente mais tarde.', 'error');
    } finally {
        mostrarCarregamento(false, 'btn-atualizar');
        atualizacaoEmAndamento = false;
    }
}


// --- RENDERIZAÇÃO DA INTERFACE (UI) ---

function montarLinhasServico() {
    const ano = Number(document.getElementById('ano').value);
    const campoFim = document.getElementById('ano-fim-contrato');
    if (!Number.isInteger(ano) || ano < 1900) return;
    const dataCampo = document.getElementById('caed-data-referencia');
    if (!dataCampo.value.startsWith(`${ano}-`)) {
        const agora = new Date();
        dataCampo.value = ano === agora.getFullYear()
            ? `${ano}-${String(agora.getMonth() + 1).padStart(2, '0')}-${String(agora.getDate()).padStart(2, '0')}` : `${ano}-12-31`;
    }
    const escolhaAnterior = Number(campoFim.value);
    const fim = Number.isInteger(escolhaAnterior) && escolhaAnterior >= ano && escolhaAnterior <= ano + 50
        ? escolhaAnterior : ano;
    campoFim.replaceChildren();
    for (let anoOpcao = ano; anoOpcao <= ano + 50; anoOpcao++) {
        const option = document.createElement('option');
        option.value = String(anoOpcao);
        option.textContent = String(anoOpcao);
        campoFim.appendChild(option);
    }
    campoFim.value = String(fim);
    const criar = (container, anos, prefixo) => {
        const mesmoAno = container.dataset.anoBase === String(ano);
        const anteriores = mesmoAno ? new Map([...container.querySelectorAll('[data-ano]')]
            .map(linha => [Number(linha.dataset.ano), [...linha.querySelectorAll('input')].map(campo => campo.value)])) : new Map();
        container.dataset.anoBase = String(ano);
        container.replaceChildren();
        for (const anoLinha of anos) {
            const linha = document.createElement('div');
            linha.dataset.ano = String(anoLinha);
            linha.className = 'caed-input-row';
            const titulo = document.createElement('span');
            titulo.className = 'text-sm font-medium text-gray-700';
            titulo.textContent = String(anoLinha);
            linha.appendChild(titulo);
            for (const [indice, rotulo] of ['Juros e encargos da nova operação (R$)', 'Amortização da nova operação (R$)', 'Pagamentos das demais operações (R$)'].entries()) {
                const rotuloCampo = document.createElement('label');
                rotuloCampo.className = 'caed-input-label';
                const textoCampo = document.createElement('span');
                textoCampo.textContent = rotulo;
                rotuloCampo.appendChild(textoCampo);
                const campo = document.createElement('input');
                campo.type = 'text';
                campo.inputMode = 'decimal';
                campo.autocomplete = 'off';
                campo.placeholder = 'Informe o valor em R$';
                campo.setAttribute('aria-label', `${prefixo} ${anoLinha}: ${rotulo}`);
                campo.className = 'w-full rounded-md border border-gray-300 px-3 py-2';
                campo.value = anteriores.get(anoLinha)?.[indice] ?? '';
                campo.addEventListener('focus', () => campo.select());
                campo.addEventListener('input', invalidarCoberturaCaed);
                campo.addEventListener('blur', () => {
                    try {
                        campo.value = normalizarPagamentoCaed(campo.value, rotulo)?.formatado ?? '';
                        campo.classList.remove('border-red-500');
                    } catch (error) {
                        campo.classList.add('border-red-500');
                    }
                });
                campo.addEventListener('paste', event => colarPlanilhaServico(event, container, linha, indice));
                rotuloCampo.appendChild(campo);
                linha.appendChild(rotuloCampo);
            }
            container.appendChild(linha);
        }
    };
    criar(document.getElementById('linhas-hipotese-1'),
        fim >= ano && fim <= ano + 50 ? Array.from({length: fim - ano + 1}, (_, i) => ano + i) : [], 'CAED');
}

function prepararColagemMonetaria(texto, linhaInicial, colunaInicial, totalLinhas) {
    const linhas = texto.replace(/\r\n?/g, '\n').replace(/\n+$/, '').split('\n');
    if (linhaInicial + linhas.length > totalLinhas) {
        throw new Error('A colagem excede os anos disponíveis. Ajuste o ano final ou cole menos linhas.');
    }
    const alteracoes = [];
    for (const [deslocamentoLinha, conteudo] of linhas.entries()) {
        const colunas = conteudo.split('\t');
        if (colunaInicial + colunas.length > 3) {
            throw new Error('A colagem excede as três colunas de pagamentos. Comece pela coluna de juros.');
        }
        for (const [deslocamentoColuna, valor] of colunas.entries()) {
            const dinheiro = normalizarPagamentoCaed(valor, `Linha ${deslocamentoLinha + 1}, coluna ${deslocamentoColuna + 1}`);
            alteracoes.push({linha: linhaInicial + deslocamentoLinha,
                             coluna: colunaInicial + deslocamentoColuna,
                             formatado: dinheiro?.formatado ?? ''});
        }
    }
    return alteracoes;
}

function colarPlanilhaServico(event, container, linhaInicial, colunaInicial) {
    const texto = event.clipboardData?.getData('text/plain');
    if (!texto || !/[\t\r\n]/.test(texto)) return;
    event.preventDefault();
    const linhas = [...container.querySelectorAll('[data-ano]')];
    try {
        const alteracoes = prepararColagemMonetaria(
            texto, linhas.indexOf(linhaInicial), colunaInicial, linhas.length);
        for (const alteracao of alteracoes) {
            const campo = linhas[alteracao.linha].querySelectorAll('input')[alteracao.coluna];
            campo.value = alteracao.formatado;
            campo.classList.remove('border-red-500');
        }
        invalidarCoberturaCaed();
        marcarSimulacaoDesatualizada();
    } catch (error) {
        mostrarMensagem(error.message, 'error');
    }
}

function obterEntradaServico() {
    const ler = (id) => [...document.querySelectorAll(`#${id} [data-ano]`)].map(linha => {
        const [juros, amortizacao, demais] = linha.querySelectorAll('input');
        return {ano: Number(linha.dataset.ano),
                juros_encargos: normalizarPagamentoCaed(juros.value, 'Juros e encargos')?.numero ?? null,
                amortizacao: normalizarPagamentoCaed(amortizacao.value, 'Amortização')?.numero ?? null,
                demais_operacoes: normalizarPagamentoCaed(demais.value, 'Demais operações')?.numero ?? null};
    });
    return {data_referencia: document.getElementById('caed-data-referencia').value,
            ano_fim_contrato: Number(document.getElementById('ano-fim-contrato').value),
            linhas: ler('linhas-hipotese-1'),
            cobertura_demais: {completa: document.getElementById('caed-cobertura-completa').checked,
                fonte: document.getElementById('caed-fonte-demais').value.trim(),
                data_referencia: document.getElementById('caed-data-cobertura').value}};
}

function popularSeletorDeAnos(anos) {
    const selectAno = document.getElementById('ano');
    const anoAnterior = Number(selectAno.value);
    selectAno.innerHTML = ''; // Limpa opções antigas
    const anoCorrente = new Date().getFullYear();

    anos.forEach(ano => {
        const option = document.createElement('option');
        option.value = ano;
        option.textContent = ano;
        if (ano === (anos.includes(anoAnterior) ? anoAnterior : anoCorrente)) {
            option.selected = true;
        }
        selectAno.appendChild(option);
    });
}

function renderizarResultados(resultado) {
    const container = document.getElementById('tabela-resultados-container'); // Você precisará criar este container no HTML
    const tbody = document.getElementById('tbody-resultados'); // E este tbody
    
    tbody.innerHTML = ''; // Limpa resultados anteriores
    
    const todasAsRegras = resultado.regras_ordenadas ? [...resultado.regras_ordenadas] : [
        ...(resultado.regras_violadas || []),
        ...(resultado.regras_cumpridas || []),
        ...(resultado.regras_sem_informacao || [])
    ];
    if (resultado.mgaProjection) todasAsRegras.push(criarRegraMga(resultado.mgaProjection));
    const servico = todasAsRegras.find(regra => regra.tipo === 'servico_divida');

    if (todasAsRegras.length === 0) {
        container.style.display = 'none';
        return;
    }

    todasAsRegras.forEach(regra => {
        const tr = document.createElement('tr');
        
        const statusClasse = regra.status === 'Cumprida' || regra.status === 'ATENDE'
            ? 'bg-green-100 text-green-800' 
            : regra.status === 'Sem informação' || regra.status === 'INCONCLUSIVO' ? 'bg-gray-100 text-gray-800' : 'bg-red-100 text-red-800';

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

        if (regra.tipo === 'mga') {
            const p = regra.dados_calculados;
            tr.children[1].querySelector('span').className = 'mga-status ' +
                (!p.dataAvailability ? 'mga-pendente' : (p.exceededYears || []).length ? 'mga-excedido' : 'mga-atendido');
            tr.children[2].textContent = regra.descricao;
        }
        if (regra.tipo === 'dtp') {
            tr.children[1].querySelector('span').textContent = regra.aprovado ? 'Atendido' : 'Excedido';
            tr.children[2].textContent = `${formatarPercentual(regra.dados_calculados.percentual)} — ${regra.descricao}`;
        }
        if (regra.tipo === 'dcl') {
            tr.children[1].querySelector('span').textContent = regra.aprovado === null
                ? 'Sem informação' : regra.aprovado ? 'Aprovado' : 'Recusado';
        }

        if (regra.tipo === 'servico_divida') {
            tr.children[1].querySelector('span').textContent = regra.estado === 'NAO_ATENDE' ? 'NÃO ATENDE' : regra.estado;
            tr.children[2].textContent = regra.descricao;
        }
        // Adiciona o listener no botão para mostrar o modal com os dados da regra específica
        tr.querySelector('.ver-detalhes-btn').addEventListener('click', () => mostrarDetalhesRegra(regra));
        
        tbody.appendChild(tr);
    });

    container.style.display = 'block'; // Mostra a tabela de resultados
    const modal = document.getElementById('modal-feedback');
    if (!modal.classList.contains('hidden') && modal.dataset.regraTipo === 'servico_divida' && servico) {
        mostrarDetalhesRegra(servico);
    }
}

function criarUtilitariosOuro(container) {
    const elemento = (tag, classe, texto) => {
        const el = document.createElement(tag);
        if (classe) el.className = classe;
        if (texto !== undefined) el.textContent = texto;
        return el;
    };
    const secao = (titulo) => {
        const el = elemento('section', 'ouro-section');
        el.appendChild(elemento('h4', 'ouro-section-title', titulo));
        container.appendChild(el);
        return el;
    };
    const linha = (rotulo, valor, destaque = false) => {
        const el = elemento('div', `ouro-value-row${destaque ? ' ouro-value-row-total' : ''}`);
        el.append(elemento('span', '', rotulo), elemento('strong', '', formatarMoeda(valor)));
        return el;
    };
    return {elemento, secao, linha};
}

function renderizarRegraOuroAnterior(regra, container) {
    const dados = regra.dados_calculados || {};
    const {elemento, secao, linha} = criarUtilitariosOuro(container);
    if (dados.mensagem) {
        container.appendChild(elemento('p', 'ouro-empty', dados.mensagem));
        return;
    }

    const cumprida = regra.status === 'Cumprida';
    const despesas = dados.despesas_capital?.total;
    const receitas = dados.operacoes_credito?.total;
    const resultado = dados.limite_disponivel;
    const status = elemento('section', 'ouro-status');
    status.appendChild(elemento('span', `ouro-status-badge ${cumprida ? 'ouro-approved' : 'ouro-failed'}`,
        cumprida ? 'Regra cumprida' : 'Regra não cumprida'));
    status.appendChild(elemento('p', '', cumprida
        ? 'As receitas de operações de crédito não ultrapassaram as despesas de capital ajustadas no exercício analisado.'
        : 'As receitas de operações de crédito ultrapassaram as despesas de capital ajustadas no exercício analisado.'));
    container.appendChild(status);

    const apuracao = secao('Resultado da apuração');
    apuracao.appendChild(elemento('p', 'ouro-main-value', formatarMoeda(resultado)));
    apuracao.appendChild(elemento('p', 'ouro-secondary',
        'Margem apurada entre as despesas de capital ajustadas e as receitas de operações de crédito.'));
    apuracao.appendChild(elemento('p', 'ouro-note',
        'Este valor representa a diferença apurada no exercício anterior e não corresponde ao limite disponível para uma nova operação de crédito.'));

    const calculo = secao('Cálculo');
    calculo.append(linha('Despesas de capital ajustadas', despesas),
        linha('(-) Receitas de operações de crédito', receitas),
        linha('Resultado', resultado, true));
    calculo.appendChild(elemento('p', 'ouro-comparison',
        `${formatarMoeda(despesas)} ${cumprida ? '≥' : '<'} ${formatarMoeda(receitas)} · ${cumprida ? 'Regra cumprida' : 'Regra não cumprida'}`));

    const detalhamento = secao('Detalhamento');
    const componentes = dados.despesas_capital?.detalhe || {};
    const ordem = ['INVESTIMENTOS', 'INVERSÕES FINANCEIRAS', 'AMORTIZAÇÃO DA DÍVIDA'];
    detalhamento.appendChild(elemento('h5', 'ouro-group-title', 'Despesas de capital ajustadas'));
    for (const conta of ordem) {
        if (Object.prototype.hasOwnProperty.call(componentes, conta)) {
            const rotulo = conta.charAt(0) + conta.slice(1).toLocaleLowerCase('pt-BR');
            detalhamento.appendChild(linha(rotulo, componentes[conta]));
        }
    }
    for (const [conta, valor] of Object.entries(componentes)) {
        if (!ordem.includes(conta)) detalhamento.appendChild(linha(conta, valor));
    }
    detalhamento.appendChild(elemento('h5', 'ouro-group-title', 'Receitas de operações de crédito'));
    for (const [conta, valor] of Object.entries(dados.operacoes_credito?.detalhe || {})) {
        detalhamento.appendChild(linha(conta, valor));
    }

    if (Array.isArray(dados.fontes) && dados.fontes.length) {
        const fontes = secao('Fonte dos dados');
        for (const fonte of dados.fontes) {
            fontes.appendChild(elemento('p', 'ouro-secondary',
                `SICONFI — RREO, ${fonte.anexo.replace('RREO-', '')}, ${fonte.periodo}º bimestre de ${dados.ano_analisado}`));
        }
    }

    const normas = elemento('details', 'ouro-normas');
    normas.appendChild(elemento('summary', '', 'Entenda esta validação'));
    const conteudo = elemento('div', 'ouro-normas-content');
    conteudo.append(elemento('h5', '', 'Objetivo'),
        elemento('p', '', 'Verificar se, no exercício anterior, as receitas provenientes de operações de crédito não ultrapassaram as despesas de capital ajustadas.'),
        elemento('h5', '', 'Base normativa'),
        elemento('p', '', 'Constituição Federal, art. 167, III; Resolução do Senado Federal nº 43/2001; MIP — Regra de Ouro.'),
        elemento('h5', '', 'Próxima verificação'),
        elemento('p', '', 'Regra de Ouro — Exercício Atual'));
    normas.appendChild(conteudo);
    container.appendChild(normas);
}

function renderizarRegraOuroAtual(regra, container) {
    const dados = regra.dados_calculados || {};
    const {elemento, secao, linha} = criarUtilitariosOuro(container);
    if (dados.mensagem) {
        container.appendChild(elemento('p', 'ouro-empty', dados.mensagem));
        return;
    }

    const cumprida = regra.status === 'Cumprida';
    const despesas = dados.despesas_capital?.total;
    const receitas = dados.operacoes_credito?.total;
    const operacao = dados.valor_requisitado_na_analise;
    const receitasTotais = dados.receitas_totais_consideradas;
    const margem = dados.margem_apos_operacao;
    const status = elemento('section', 'ouro-status');
    status.appendChild(elemento('span', `ouro-status-badge ${cumprida ? 'ouro-approved' : 'ouro-failed'}`,
        cumprida ? 'Regra cumprida' : 'Regra não cumprida'));
    status.appendChild(elemento('p', '', cumprida
        ? 'Considerando a previsão de receitas de operações de crédito do exercício e o valor informado para a operação em análise, a Regra de Ouro permanece respeitada.'
        : 'Considerando a previsão de receitas de operações de crédito do exercício e o valor informado para a operação em análise, o total ultrapassa as despesas de capital ajustadas.'));
    container.appendChild(status);

    const operacaoSecao = secao('Operação em análise');
    operacaoSecao.appendChild(elemento('p', 'ouro-secondary', 'Valor informado para esta simulação, considerado integralmente no exercício selecionado'));
    operacaoSecao.appendChild(elemento('p', 'ouro-feature-value', formatarMoeda(operacao)));
    operacaoSecao.appendChild(elemento('p', 'ouro-secondary',
        'O formulário não separa o valor por ano de desembolso.'));

    const apuracao = secao('Resultado da apuração');
    apuracao.appendChild(elemento('h5', 'ouro-group-title', 'Margem após a operação analisada'));
    apuracao.appendChild(elemento('p', 'ouro-main-value', formatarMoeda(margem)));
    apuracao.appendChild(elemento('p', 'ouro-secondary',
        'Diferença entre as despesas de capital ajustadas e as receitas de operações de crédito consideradas nesta análise.'));
    apuracao.appendChild(elemento('p', 'ouro-note',
        'Este valor representa a margem apurada exclusivamente para a Regra de Ouro e não corresponde ao limite total disponível para novas operações de crédito.'));

    const calculo = secao('Cálculo');
    calculo.appendChild(elemento('h5', 'ouro-group-title', 'Dados do exercício · SICONFI/RREO'));
    calculo.append(linha('Despesas de capital ajustadas', despesas),
        linha('(-) Receitas de operações de crédito · previsão atualizada', receitas));
    calculo.appendChild(elemento('h5', 'ouro-group-title', 'Operação em análise · valor informado'));
    calculo.appendChild(linha('(-) Operação considerada neste exercício', operacao));
    calculo.appendChild(elemento('h5', 'ouro-group-title', 'Resultado da simulação'));
    calculo.append(linha('Receitas totais consideradas', receitasTotais),
        linha('Margem da Regra de Ouro', margem, true));
    calculo.appendChild(elemento('p', 'ouro-comparison',
        `${formatarMoeda(despesas)} ${cumprida ? '≥' : '<'} ${formatarMoeda(receitasTotais)} · ${cumprida ? 'Regra cumprida' : 'Regra não cumprida'}`));

    const detalhamento = secao('Detalhamento dos dados fiscais');
    detalhamento.appendChild(elemento('h5', 'ouro-group-title', 'Despesas de capital ajustadas'));
    const componentes = dados.despesas_capital?.detalhe || {};
    for (const conta of ['INVESTIMENTOS', 'INVERSÕES FINANCEIRAS', 'AMORTIZAÇÃO DA DÍVIDA']) {
        if (Object.prototype.hasOwnProperty.call(componentes, conta)) {
            detalhamento.appendChild(linha(conta.charAt(0) + conta.slice(1).toLocaleLowerCase('pt-BR'), componentes[conta]));
        }
    }
    for (const [conta, valor] of Object.entries(componentes)) {
        if (!['INVESTIMENTOS', 'INVERSÕES FINANCEIRAS', 'AMORTIZAÇÃO DA DÍVIDA'].includes(conta)) {
            detalhamento.appendChild(linha(conta, valor));
        }
    }
    detalhamento.appendChild(elemento('h5', 'ouro-group-title', 'Receitas de operações de crédito · previsão atualizada'));
    detalhamento.appendChild(linha('Total no RREO', receitas, true));
    for (const [conta, valor] of Object.entries(dados.operacoes_credito?.detalhe || {})) {
        detalhamento.appendChild(linha(conta, valor));
    }

    if (Array.isArray(dados.fontes) && dados.fontes.length) {
        const fontes = secao('Fonte dos dados');
        for (const fonte of dados.fontes) {
            fontes.appendChild(elemento('p', 'ouro-secondary',
                `SICONFI — RREO, ${fonte.anexo.replace('RREO-', '')}, ${fonte.periodo}º bimestre de ${dados.ano_analisado}`));
        }
        fontes.appendChild(elemento('p', 'ouro-secondary',
            'A receita de operações de crédito é a previsão atualizada; as despesas incluem valores liquidados e restos a pagar não processados.'));
        fontes.appendChild(elemento('p', 'ouro-secondary',
            'Os dados do exercício refletem o período disponível na análise; não representam necessariamente o ano encerrado.'));
    }

    const normas = elemento('details', 'ouro-normas');
    normas.appendChild(elemento('summary', '', 'Entenda esta validação'));
    const conteudo = elemento('div', 'ouro-normas-content');
    conteudo.append(elemento('h5', '', 'Objetivo'),
        elemento('p', '', 'Verificar se as receitas de operações de crédito consideradas no exercício, incluindo o valor informado para a operação em análise, não ultrapassam as despesas de capital ajustadas.'),
        elemento('h5', '', 'Base normativa'),
        elemento('p', '', 'Constituição Federal, art. 167, III; Resolução do Senado Federal nº 43/2001; MIP — Regra de Ouro.'),
        elemento('h5', '', 'Próxima verificação prevista'),
        elemento('p', '', 'Limite de 16% da Receita Corrente Líquida. Esta regra ainda não é avaliada pelo simulador.'));
    normas.appendChild(conteudo);
    container.appendChild(normas);
}

function formatarNumeroDtp(valor) {
    return new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(valor);
}

function renderizarDtp(regra, container) {
    const dados = regra.dados_calculados;
    const criar = (tag, classe, texto) => {
        const no = document.createElement(tag);
        no.className = classe;
        if (texto !== undefined) no.textContent = texto;
        return no;
    };
    const barra = (item) => {
        const limite = item.limite_maximo;
        const figura = criar('div', 'dtp-gauge');
        figura.setAttribute('role', 'img');
        figura.setAttribute('aria-label', `${item.poder || 'Estado'}: ${formatarPercentual(item.percentual)}; alerta acima de ${formatarPercentual(item.limite_alerta)}; prudencial acima de ${formatarPercentual(item.limite_prudencial)}; máximo ${formatarPercentual(limite)}.`);
        const trilho = criar('div', 'dtp-gauge-track');
        trilho.appendChild(criar('span', `dtp-gauge-fill dtp-tone-${item.faixa}`));
        trilho.firstChild.style.width = `${Math.max(0, Math.min(100, item.percentual_limite_consumido))}%`;
        for (const posicao of [90, 95]) {
            const marco = criar('span', 'dtp-gauge-marker');
            marco.style.left = `${posicao}%`;
            trilho.appendChild(marco);
        }
        const legenda = criar('div', 'dtp-gauge-labels');
        legenda.append(
            criar('span', '', `Alerta > ${formatarPercentual(item.limite_alerta)}`),
            criar('span', '', `Prudencial > ${formatarPercentual(item.limite_prudencial)}`),
            criar('span', '', `Máximo ${formatarPercentual(limite)}`));
        figura.append(trilho, legenda);
        return figura;
    };

    container.appendChild(criar('p', 'dtp-intro', `${dados.quadrimestre}º quadrimestre de ${dados.ano}. Percentual de despesa com pessoal sobre a RCL ajustada. O resultado considera a soma do mesmo quadrimestre e o limite global de 60%.`));
    const resumo = criar('section', `dtp-overview dtp-border-${dados.faixa}`);
    resumo.append(
        criar('p', 'dtp-eyebrow', 'Estado de Goiás · DTP consolidada'),
        criar('strong', 'dtp-total', formatarPercentual(dados.percentual)),
        criar('span', `dtp-status dtp-tone-${dados.faixa}`, regra.descricao),
        criar('p', 'dtp-overview-note', `${dados.situacao} · Margem para o máximo: ${formatarNumeroDtp(dados.margem_pontos_percentuais)} p.p.`),
        barra({...dados, poder: 'Estado consolidado'}));
    container.appendChild(resumo);

    const faixas = ['maximo', 'prudencial', 'alerta'];
    const destaques = dados.poderes.filter(item => faixas.includes(item.faixa))
        .sort((a, b) => faixas.indexOf(a.faixa) - faixas.indexOf(b.faixa));
    const aviso = destaques.length
        ? `Atenção aos limites individuais: ${destaques.map(item => `${item.poder} — ${item.situacao.toLowerCase()}`).join('; ')}.`
        : 'Nenhum Poder ou órgão com limite individual ultrapassou a faixa de alerta.';
    container.appendChild(criar('p', `dtp-alert-summary ${destaques.length ? 'dtp-alert-active' : ''}`, aviso));

    container.appendChild(criar('h4', 'dtp-section-title', 'Valores por Poder e órgão'));
    container.appendChild(criar('p', 'dtp-section-help', 'Cada barra mostra quanto do limite próprio foi usado; os percentuais são parcelas da RCL ajustada.'));
    const lista = criar('div', 'dtp-power-list');
    for (const item of dados.poderes) {
        const secao = criar('article', 'dtp-power');
        const cabecalho = criar('div', 'dtp-power-head');
        cabecalho.append(
            criar('h5', '', item.poder),
            criar('strong', 'dtp-power-value', formatarPercentual(item.percentual)),
            criar('span', `dtp-status dtp-tone-${item.faixa}`, item.situacao));
        secao.appendChild(cabecalho);
        if (item.limite_maximo !== null) {
            secao.appendChild(barra(item));
            secao.appendChild(criar('p', 'dtp-power-margin', `Margem para o máximo: ${formatarNumeroDtp(item.margem_pontos_percentuais)} p.p. · ${formatarPercentual(item.percentual_limite_consumido)} do limite usado`));
        } else {
            secao.appendChild(criar('p', 'dtp-power-margin', 'Sem teto individual nesta visualização; valor incluído no total consolidado.'));
        }
        lista.appendChild(secao);
    }
    container.appendChild(lista);
    container.appendChild(criar('p', 'dtp-source', `Fonte: SICONFI · RGF, Anexo 01 · Goiás · ${dados.quadrimestre}º quadrimestre de ${dados.ano}.`));
    const explicacao = criar('details', 'dtp-explanation');
    explicacao.appendChild(criar('summary', '', 'Entenda esta validação'));
    explicacao.append(
        criar('p', '', 'A DTP consolidada soma os percentuais publicados para os Poderes e órgãos do último quadrimestre com pelo menos seis instituições. O limite global é 60% da RCL ajustada; até 60%, a regra é atendida.'),
        criar('p', '', 'As faixas individuais são informativas: alerta acima de 90%, prudencial acima de 95% e máximo acima de 100% do limite próprio. Estar exatamente no marco ainda não o ultrapassa.'),
        criar('p', '', 'Limites de Goiás: Executivo 48,60%; Legislativo 3,40%; Judiciário 6%; Ministério Público 2%. A classificação individual não altera a aprovação global desta regra. Base: Lei Complementar nº 101/2000, arts. 19, 20, 22 e 59.'));
    container.appendChild(explicacao);
}

function criarMemoriaCaed(regra) {
    const dados = regra.dados_calculados || {};
    const criar = (tag, texto) => { const no = document.createElement(tag); if (texto !== undefined) no.textContent = texto; return no; };
    const secao = criar('section');
    secao.className = 'servico-section';
    const estado = regra.estado || 'INCONCLUSIVO';
    secao.append(criar('h4', 'Memória anual do CAED'), criar('p', `Resultado: ${estado === 'NAO_ATENDE' ? 'NÃO ATENDE' : estado}`));
    const entrada = dados.memoria_exata?.entrada;
    if (entrada) secao.appendChild(criar('p', `Data da análise: ${entrada.data_referencia || 'Não informada'} · Término da operação: ${entrada.ano_fim_contrato ?? 'Não informado'}.`));
    const rolagem = criar('div'); rolagem.className = 'caed-table-scroll';
    const tabela = criar('table'); tabela.className = 'caed-table';
    const cabecalho = criar('thead'); const titulos = criar('tr');
    for (const texto of ['Ano', 'Operação pretendida', 'Demais operações', 'CAED total', 'RCL projetada', 'CAED/RCL']) titulos.appendChild(criar('th', texto));
    cabecalho.appendChild(titulos); tabela.appendChild(cabecalho);
    const corpo = criar('tbody');
    const moeda = valor => valor == null ? 'Não disponível' : formatarMoeda(valor);
    for (const item of dados.linhas || []) {
        const linha = criar('tr');
        for (const texto of [String(item.ano), moeda(item.operacao_pleiteada), moeda(item.demais_operacoes), moeda(item.caed_total), moeda(item.rcl_projetada), item.percentual == null ? 'Não disponível' : formatarPercentual(item.percentual * 100)]) linha.appendChild(criar('td', texto));
        corpo.appendChild(linha);
    }
    tabela.appendChild(corpo); rolagem.appendChild(tabela); secao.appendChild(rolagem);
    const media = valor => valor == null ? 'Não disponível' : formatarPercentual(valor);
    const alternativa = dados.alternativa_utilizada === 'ATE_2027' ? 'Até 31/12/2027' : dados.alternativa_utilizada === 'TERMINO_OPERACAO' ? 'Término da operação' : 'Não determinada';
    secao.append(criar('p', `Média até o término da operação: ${media(dados.media_termino)}`),
        criar('p', `Média até 2027: ${dados.anos_2027?.length === 0 ? 'Não aplicável — sem pagamentos elegíveis até 2027' : media(dados.media_2027)}`),
        criar('p', `Alternativa mais benéfica: ${alternativa}`),
        criar('p', `Percentual determinante: ${media(dados.percentual_determinante)} · Limite: 11,5% (igualdade atende)`),
        criar('p', 'As médias usam apenas os anos com pagamentos positivos da operação pretendida. Um ano acima de 11,5% não reprova isoladamente a média.'));
    const rcl = dados.rcl_fonte;
    secao.appendChild(criar('p', rcl ? `Fonte da RCL: ${rcl.origem} · ${rcl.anexo} · Goiás/Estadual · ${rcl.periodo}º bimestre de ${rcl.exercicio} · Data-base ${rcl.data_base} · RCL ${moeda(rcl.valor)}.` : 'RCL ajustada para endividamento não disponível.'));
    if (rcl) secao.appendChild(criar('p', `Conta: ${rcl.conta || 'Não disponível'} · Coluna: ${rcl.coluna || 'Não disponível'} · Valor decimal da RCL base: ${rcl.valor}.`));
    const fator = dados.fator_atualizacao;
    secao.appendChild(criar('p', fator ? `Fator: ${fator.valor} (multiplicador) · Referência ${fator.data_referencia} · Janela documentada desde ${fator.vigencia_inicio}; referências validadas até ${fator.referencia_validada_ate} · Origem: ${fator.fonte}. Projeção da data-base fiscal até dezembro, proporcional aos meses; anos seguintes com atualização anual.` : 'Fator sem fonte/vigência validada para esta referência.'));
    if (fator?.fonte) { const link = criar('a', 'Fonte do fator: MIP'); link.href = fator.fonte; link.target = '_blank'; link.rel = 'noopener noreferrer'; secao.appendChild(link); }
    const cobertura = dados.cobertura;
    secao.appendChild(criar('p', cobertura?.completa ? `Cobertura declarada das demais operações: ${cobertura.fonte || 'Fonte ausente'} · Conferência ${cobertura.data_referencia || 'Data ausente'}.` : 'Demais operações: cobertura não confirmada; ausência não é zero.'));
    for (const motivo of dados.motivos || []) secao.appendChild(criar('p', `${motivo.codigo}: ${motivo.mensagem}`));
    const exata = criar('details'); exata.appendChild(criar('summary', 'Memória decimal exata do CAED'));
    const tabelaExata = criar('table'); tabelaExata.className = 'caed-table';
    const headExato = criar('tr');
    for (const titulo of ['Ano', 'Juros/encargos', 'Amortização', 'Demais operações', 'CAED', 'RCL projetada', 'Relação decimal', 'Meses de projeção']) headExato.appendChild(criar('th', titulo));
    tabelaExata.appendChild(headExato);
    for (const item of dados.memoria_exata?.linhas || []) {
        const linha = criar('tr');
        for (const chave of ['ano', 'juros_encargos', 'amortizacao', 'demais_operacoes', 'caed_total', 'rcl_projetada', 'percentual', 'meses_projecao']) linha.appendChild(criar('td', String(item[chave] ?? 'Não disponível')));
        tabelaExata.appendChild(linha);
    }
    const scrollExato = criar('div'); scrollExato.className = 'caed-table-scroll'; scrollExato.appendChild(tabelaExata); exata.appendChild(scrollExato);
    const medias = dados.memoria_exata?.alternativas;
    if (medias) exata.appendChild(criar('p', `Relações decimais exatas: término ${medias.media_termino}; até 2027 ${medias.media_2027 ?? 'não aplicável'}; determinante ${medias.percentual_determinante}; comparador ≤ ${medias.limite_percentual}.`));
    secao.appendChild(exata);
    return secao;
}

function renderizarServicoDivida(regra, container) {
    const dados = regra.dados_calculados || {};
    const historico = document.createElement('section'); historico.className = 'servico-section';
    const titulo = document.createElement('h4'); titulo.textContent = `Diagnóstico histórico (${dados.ano_historico ?? 'referência indisponível'}) — não bloqueia a análise prospectiva`;
    const texto = document.createElement('p');
    texto.textContent = dados.historico ? `${dados.historico.situacao}. Serviço observado: ${formatarMoeda(dados.historico.servico_divida)}; RCL: ${formatarMoeda(dados.historico.rcl)}; relação: ${formatarPercentual(dados.historico.percentual * 100)}. SICONFI/RREO, Anexos 01/03, 6º bimestre. Restos ausentes seguem a convenção histórica de zero, pendente de validação.` : (dados.historico_motivos || ['Diagnóstico histórico indisponível.']).join(' ');
    historico.append(titulo, texto); container.appendChild(historico);
    document.getElementById('servico-dados-base').replaceChildren();
    document.getElementById('servico-resultados').replaceChildren(criarMemoriaCaed(regra));
}

function mostrarDetalhesRegra(regra) {
    document.getElementById('modal-feedback').dataset.regraTipo = regra.tipo || '';
    const servico = regra.tipo === 'servico_divida';
    document.getElementById('mga-entradas').classList.toggle('hidden', regra.tipo !== 'mga');
    document.getElementById('servico-resultados').classList.toggle('hidden', !servico);
    document.getElementById('servico-parametros').classList.toggle('hidden', !servico);
    if (servico) {
        const fator = regra.dados_calculados?.fator_atualizacao;
        document.getElementById('valor-fator-resumo').textContent = fator?.valor || 'Não validado';
        document.getElementById('servico-fator-fonte').textContent = fator?.fonte || 'Fator indisponível; sem fallback legado.';
    }
    const painelProjecoes = document.getElementById('servico-projecoes');
    painelProjecoes.classList.toggle('hidden', !servico);
    painelProjecoes.classList.toggle('servico-etapa-aprovada', servico && regra.aprovado === true);
    painelProjecoes.classList.toggle('servico-etapa-reprovada', servico && regra.aprovado === false);
    document.getElementById('servico-modal-intro').classList.toggle('hidden', !servico);
    if (servico) document.getElementById('servico-anos-contexto').textContent = 'Um cronograma anual; médias até o término e até 2027, quando aplicável. Histórico separado da conclusão.';
    const ouroAnterior = regra.tipo === 'regra_ouro_anterior';
    const ouroAtual = regra.tipo === 'regra_ouro_atual';
    const dtp = regra.tipo === 'mga' || regra.tipo === 'dtp' || regra.tipo === 'dcl' || regra.tipo === 'servico_divida' || ouroAnterior || ouroAtual;
    for (const id of ['modal-descricao', 'modal-proximo-passo', 'modal-base-normativa', 'modal-objetivo']) {
        document.getElementById(id).parentElement.hidden = dtp;
    }
    document.querySelector('#modal-dados-calculados-container > dt').hidden = dtp;
    // Popula o modal com os dados detalhados da regra
    document.getElementById('modal-title').textContent = servico
        ? 'Projeção do Serviço da Dívida — Limite de 11,5% da RCL' : regra.nome;
    const anoAnalise = document.getElementById('modal-ano-analise');
    anoAnalise.hidden = !(ouroAnterior || ouroAtual) || !regra.dados_calculados?.ano_analisado;
    anoAnalise.textContent = anoAnalise.hidden ? '' : `Exercício analisado: ${regra.dados_calculados.ano_analisado}`;
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
    calculadosContainer.classList.toggle('ouro-layout', ouroAnterior || ouroAtual);
    calculadosContainer.classList.toggle('dtp-layout', regra.tipo === 'dtp');
    calculadosContainer.classList.toggle('servico-layout', servico);
    
    if (regra.tipo === 'mga') {
        if (resultadoDesatualizado) calculadosContainer.appendChild(elementoFiscal('p', 'simulacao-erro', 'Resultados desatualizados — recalcule a simulação.'));
        calculadosContainer.appendChild(criarTabelaMga(regra.dados_calculados));
        const editar = elementoFiscal('button', 'jornada-link', 'Editar cronograma financeiro');
        editar.type = 'button'; editar.addEventListener('click', editarCronogramaFinanceiro);
        calculadosContainer.appendChild(editar);
    } else if (ouroAnterior) {
        renderizarRegraOuroAnterior(regra, calculadosContainer);
    } else if (ouroAtual) {
        renderizarRegraOuroAtual(regra, calculadosContainer);
    } else if (regra.tipo === 'servico_divida') {
        renderizarServicoDivida(regra, calculadosContainer);
    } else if (regra.tipo === 'dtp') {
        renderizarDtp(regra, calculadosContainer);
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
    document.getElementById('modal-feedback').style.display = 'flex';
}


function esconderModal() {
    document.getElementById('modal-feedback').classList.add('hidden');
    document.getElementById('modal-feedback').style.display = 'none';
    document.getElementById('servico-projecoes').classList.add('hidden');
    document.getElementById('servico-parametros').classList.add('hidden');
    document.getElementById('servico-parametros').open = false;
}


// --- FUNÇÕES UTILITÁRIAS ---

function formatarMoeda(valor) {
    if (valor === null || valor === undefined || isNaN(valor)) return 'R$ 0,00';
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor);
}

function normalizarValorMonetario(valor, nomeCampo = 'Valor') {
    const texto = String(valor ?? '').trim().replace(/^R\$\s*/, '').replace(/\s/g, '');
    if (!texto) return null;
    if (/^[-−]/.test(texto) || /^\(.*\)$/.test(texto)) {
        throw new Error(`${nomeCampo}: valor negativo não é aceito nesta projeção (${valor}).`);
    }
    // Durante a edição, os pontos podem ficar fora da posição de milhar;
    // validamos os dígitos e reagrupamos ao formatar.
    if (!/^\d+(?:\.\d+)*(?:,\d*)?$/.test(texto)) {
        throw new Error(`${nomeCampo}: use o formato 1.234,56.`);
    }
    const [parteInteira, parteDecimal = ''] = texto.split(',');
    const inteiro = parteInteira.replace(/\./g, '').replace(/^0+(?=\d)/, '');
    const centavos = parteDecimal.slice(0, 2).padEnd(2, '0');
    const milhar = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return {numero: `${inteiro}.${centavos}`, formatado: `R$ ${milhar},${centavos}`};
}

function lerValorRequisitado(valor) {
    const texto = String(valor ?? '').trim();
    if (!texto) return {numero: 0, formatado: ''};
    const decimais = texto.split(',')[1] || '';
    if (decimais.length > 2 && /[1-9]/.test(decimais.slice(2))) {
        throw new Error('Valor requisitado: informe no máximo duas casas decimais.');
    }
    const dinheiro = normalizarValorMonetario(texto, 'Valor requisitado');
    const centavos = BigInt(dinheiro.numero.replace('.', ''));
    if (centavos > BigInt(Number.MAX_SAFE_INTEGER)) {
        throw new Error('Valor requisitado muito alto para uma simulação precisa.');
    }
    return {numero: Number(dinheiro.numero), formatado: dinheiro.formatado};
}

function formatarPercentual(valor) {
    return new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(valor) + '%';
}

function mostrarMensagem(mensagem, tipo = 'info') {
     // Criar elemento de notificação
    const notificacao = document.createElement('div');
    notificacao.className = `fixed top-4 right-4 max-w-md whitespace-pre-line p-4 rounded-lg shadow-lg z-50 ${obterClasseTipo(tipo)}`;
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
        botao.innerHTML = `<span class="loading-orbit" aria-hidden="true"></span><span class="loading-label" role="status">${elementoId === 'btn-atualizar' ? 'Sincronizando dados' : elementoId === 'form-simulacao' ? 'Calculando impacto...' : 'Analisando operação'}</span>`;
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
