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
    adicionarLinhaFluxoCredito();
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
    for (const id of ['secao-painel', 'secao-limites', 'secao-simulacao', 'secao-analise', 'secao-configuracoes']) {
        document.getElementById(id).classList.add('hidden');
    }
    const secaoParaMostrar = document.getElementById(nomeSecao);
    if (secaoParaMostrar) secaoParaMostrar.classList.remove('hidden');
    const navegacao = {'secao-painel': 'nav-painel', 'secao-limites': 'nav-limites',
        'secao-simulacao': 'nav-simulacao', 'secao-analise': 'nav-analise',
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
    document.getElementById('ano').addEventListener('change', montarLinhasServico);
    document.getElementById('ano-fim-contrato').addEventListener('change', montarLinhasServico);
    document.getElementById('fator-rcl').addEventListener('change', async (e) => {
        const resposta = await eel.salvar_fator_projecao_py(e.target.value)();
        if (resposta.status === 'sucesso') {
            e.target.value = resposta.fator;
            document.getElementById('valor-fator-resumo').textContent = `· ${resposta.fator}`;
        }
        else mostrarMensagem(resposta.mensagem, 'error');
    });
    document.getElementById('btn-recalcular-servico').addEventListener('click', () => executarSimulacao(true));
    document.getElementById('fluxo-adicionar-ano').addEventListener('click', adicionarLinhaFluxoCredito);
    document.getElementById('form-fluxo-credito').addEventListener('submit', executarFluxoCredito);

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
    document.getElementById('nav-analise').addEventListener('click', () => mostrarSecao('secao-analise'));
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
let consultaSadipemEmCurso = null;

function adicionarLinhaFluxoCredito() {
    const container = document.getElementById('fluxo-credito-linhas');
    if (container.children.length >= 30) return;
    const anoBase = Number(document.getElementById('ano').value) || new Date().getFullYear();
    const ano = container.children.length ? Number(container.lastElementChild.dataset.ano) + 1 : anoBase;
    const linha = document.createElement('div');
    linha.className = 'fluxo-sim-linha';
    linha.dataset.ano = String(ano);
    for (const [chave, rotulo] of [
        ['rclProjetada', 'RCL projetada (R$)'],
        ['liberacoesNaoContratadasManual', 'Não contratadas · manual (R$)'],
        ['liberacaoNovaOperacao', 'Nova operação · liberação (R$)']
    ]) {
        const label = document.createElement('label');
        label.textContent = rotulo;
        const input = document.createElement('input');
        input.type = 'number';
        input.min = '0';
        input.step = '0.01';
        input.dataset.campo = chave;
        input.setAttribute('aria-label', `${rotulo} em ${ano}`);
        label.appendChild(input);
        linha.appendChild(label);
    }
    const titulo = document.createElement('strong');
    titulo.textContent = `Exercício ${ano}`;
    linha.prepend(titulo);
    container.appendChild(linha);
}

async function executarFluxoCredito(event) {
    event.preventDefault();
    const destino = document.getElementById('fluxo-credito-resultado');
    const linhas = [...document.querySelectorAll('#fluxo-credito-linhas .fluxo-sim-linha')].map(linha => {
        const entrada = {ano: Number(linha.dataset.ano)};
        for (const input of linha.querySelectorAll('input')) entrada[input.dataset.campo] =
            input.value.trim() === '' ? null : Number(input.value);
        return entrada;
    });
    destino.textContent = 'Consultando o SADIPEM e calculando o cenário...';
    try {
        const resposta = await eel.simular_fluxo_credito_py(linhas)();
        if (resposta.status !== 'sucesso') throw new Error(resposta.mensagem);
        destino.replaceChildren();
        for (const item of resposta.exercicios) {
            const secao = document.createElement('section');
            secao.className = 'fluxo-sim-resultado';
            const titulo = document.createElement('h3');
            titulo.textContent = `${item.ano} · ${item.cenario.dadosCompletos ? 'Cenário calculado com os dados informados' : 'Dados insuficientes para calcular o cenário'}`;
            secao.appendChild(titulo);
            for (const texto of [
                `Liberações contratadas · SADIPEM: ${item.cenario.liberacoesContratadas == null ? 'não informadas no snapshot' : formatarMoeda(item.cenario.liberacoesContratadas)}`,
                `Não contratadas · ${item.fonteNaoContratadas || 'sem fonte'}: ${item.cenario.liberacoesNaoContratadas == null ? 'não informadas' : formatarMoeda(item.cenario.liberacoesNaoContratadas)}`,
                `Nova operação: ${item.cenario.liberacaoOperacaoAnalisada == null ? 'não informada' : formatarMoeda(item.cenario.liberacaoOperacaoAnalisada)}`,
                `MGA/RCL do cenário: ${item.cenario.percentualMgaRcl == null ? 'não calculável' : formatarPercentual(item.cenario.percentualMgaRcl)}`,
                `Margem do cenário: ${item.cenario.margemEstimada == null ? 'não calculável' : formatarMoeda(item.cenario.margemEstimada)}`,
                `PVL de referência: ${item.snapshot?.numeroPvl || item.snapshot?.idPleito || 'não encontrado'}`
            ]) {
                const p = document.createElement('p');
                p.textContent = texto;
                secao.appendChild(p);
            }
            const aviso = document.createElement('p');
            aviso.textContent = 'Cenário indicativo. A cobertura dos cronogramas públicos do SADIPEM não foi confirmada como MGA oficial completo.';
            secao.appendChild(aviso);
            destino.appendChild(secao);
        }
    } catch (error) {
        destino.textContent = `Não foi possível calcular o cenário: ${error.message}`;
    }
}

async function carregarSadipemLimites() {
    if (consultaSadipemEmCurso) return consultaSadipemEmCurso;
    if (!painelFiscalAtual?.exercicio) return;
    consultaSadipemEmCurso = (async () => {
        try {
            const resposta = await eel.obter_comprometimento_sadipem_py()();
            if (resposta.status !== 'sucesso') throw new Error(resposta.mensagem);
            painelFiscalAtual.sadipem = resposta.sadipem;
            renderizarVisaoFiscal(painelFiscalAtual);
        } catch (error) {
            console.error('Erro ao consultar SADIPEM:', error);
            painelFiscalAtual.sadipem = {statusDadosMga: 'Unavailable', motivo: 'API_ERROR'};
            renderizarVisaoFiscal(painelFiscalAtual);
        } finally {
            consultaSadipemEmCurso = null;
        }
    })();
    return consultaSadipemEmCurso;
}

async function carregarPainelFiscal() {
    try {
        const resposta = await eel.obter_painel_fiscal_py()();
        if (resposta.status !== 'sucesso') throw new Error(resposta.mensagem);
        painelFiscalAtual = resposta.painel;
        renderizarPainelFiscal(resposta.painel);
        if (!document.getElementById('secao-limites').classList.contains('hidden')) carregarSadipemLimites();
    } catch (error) {
        console.error('Erro ao carregar painel fiscal:', error);
        document.getElementById('painel-estado-dados').textContent = 'Não foi possível carregar os dados';
        document.getElementById('painel-alertas').textContent = 'Não foi possível consultar o painel fiscal. Tente novamente após verificar a conexão com o banco de dados.';
    }
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
            const fatorCampo = document.getElementById('fator-rcl');
            if (!fatorCampo.dataset.carregado) {
                fatorCampo.value = await eel.obter_fator_projecao_py()();
                fatorCampo.dataset.carregado = '1';
            }
            console.log("Anos disponíveis carregados:", resultado.anos_disponiveis);
        } else {
            throw new Error(resultado.mensagem);
        }
    } catch (error) {
        console.error('Erro ao carregar dados iniciais:', error);
        mostrarMensagem('Falha ao carregar dados iniciais do servidor.', 'error');
    }
}

async function executarSimulacao(usarProjecaoServico = false) {
    const ano = parseInt(document.getElementById('ano').value);
    if (!Number.isInteger(ano)) {
        mostrarMensagem('Selecione um ano de referência disponível para continuar.', 'error');
        document.getElementById('ano').focus();
        return;
    }
    let valorRequisitado;
    try {
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
        modal.dataset.regraTipo === 'servico_divida';
    const botaoCarregamento = modalServico ? 'btn-recalcular-servico' : 'form-simulacao';
    const botao = botaoCarregamento === 'form-simulacao'
        ? document.querySelector('#form-simulacao button[type="submit"]')
        : document.getElementById(botaoCarregamento);
    if (botao.disabled) return;

    console.log(`Iniciando simulação para o ano ${ano} com valor ${valorRequisitado}`);
    mostrarCarregamento(true, botaoCarregamento);

    try {
        const entradaServico = !modalServico ? null : obterEntradaServico();
        if (entradaServico) {
            const salvo = await eel.salvar_fator_projecao_py(entradaServico.fator)();
            if (salvo.status !== 'sucesso') throw new Error(salvo.mensagem);
            entradaServico.fator = salvo.fator;
        }
        const resultado = await eel.analisar_operacao_py(ano, valorRequisitado, entradaServico)();
        console.log("Resultado da análise recebido:", resultado);

        if (resultado.status !== 'Análise completa.') throw new Error('Não foi possível concluir a simulação. Verifique os dados informados ou tente novamente.');
        
        // A nova função central de renderização
        renderizarResultados(resultado);
        if (!modalServico && document.getElementById('tbody-resultados').children.length) {
            document.getElementById('nav-analise').disabled = false;
            mostrarSecao('secao-analise');
        }
        if (modalServico) {
            const alvo = document.getElementById('servico-resultado-hipotese-2') ||
                document.getElementById('servico-resultado-hipotese-1');
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
        mostrarMensagem('Não foi possível concluir a simulação. Verifique os dados informados ou tente novamente.', 'error');
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
        if ((!document.getElementById('secao-simulacao').classList.contains('hidden') ||
             !document.getElementById('secao-analise').classList.contains('hidden')) &&
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
            linha.className = 'grid grid-cols-1 md:grid-cols-3 gap-2 items-center';
            const titulo = document.createElement('span');
            titulo.className = 'text-sm font-medium text-gray-700';
            titulo.textContent = String(anoLinha);
            linha.appendChild(titulo);
            for (const [indice, rotulo] of ['Juros e encargos (R$)', 'Amortização (R$)'].entries()) {
                const campo = document.createElement('input');
                campo.type = 'text';
                campo.inputMode = 'decimal';
                campo.autocomplete = 'off';
                campo.placeholder = 'R$ 0,00';
                campo.setAttribute('aria-label', `${prefixo} ${anoLinha}: ${rotulo}`);
                campo.className = 'w-full rounded-md border border-gray-300 px-3 py-2';
                campo.value = anteriores.get(anoLinha)?.[indice] ?? '';
                campo.addEventListener('focus', () => campo.select());
                campo.addEventListener('blur', () => {
                    try {
                        campo.value = normalizarValorMonetario(campo.value, rotulo)?.formatado ?? '';
                        campo.classList.remove('border-red-500');
                    } catch (error) {
                        campo.classList.add('border-red-500');
                    }
                });
                campo.addEventListener('paste', event => colarPlanilhaServico(event, container, linha, indice));
                linha.appendChild(campo);
            }
            container.appendChild(linha);
        }
    };
    criar(document.getElementById('linhas-hipotese-1'),
        fim >= ano && fim <= ano + 50 ? Array.from({length: fim - ano + 1}, (_, i) => ano + i) : [], 'Hipótese 1');
    criar(document.getElementById('linhas-hipotese-2'),
        ano <= 2027 ? Array.from({length: 2028 - ano}, (_, i) => ano + i) : [], 'Hipótese 2');
}

function prepararColagemMonetaria(texto, linhaInicial, colunaInicial, totalLinhas) {
    const linhas = texto.replace(/\r\n?/g, '\n').replace(/\n+$/, '').split('\n');
    if (linhaInicial + linhas.length > totalLinhas) {
        throw new Error('A colagem excede os anos disponíveis. Ajuste o ano final ou cole menos linhas.');
    }
    const alteracoes = [];
    for (const [deslocamentoLinha, conteudo] of linhas.entries()) {
        const colunas = conteudo.split('\t');
        if (colunaInicial + colunas.length > 2) {
            throw new Error('A colagem excede as duas colunas de valores. Comece pela coluna de juros.');
        }
        for (const [deslocamentoColuna, valor] of colunas.entries()) {
            const dinheiro = normalizarValorMonetario(valor, `Linha ${deslocamentoLinha + 1}, coluna ${deslocamentoColuna + 1}`);
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
    } catch (error) {
        mostrarMensagem(error.message, 'error');
    }
}

function preencherReferenciaServico(referencia) {
    const aviso = document.getElementById('referencia-rreo-servico');
    if (!referencia) {
        aviso.textContent = 'Sem valores de referência publicados no RREO Anexo 01 para este ano.';
        return;
    }
    aviso.textContent = `Referência do RREO: ${referencia.origem}, ${referencia.periodo}º bimestre de ${referencia.ano}. Juros e encargos: ${formatarMoeda(referencia.juros_encargos)}; amortização: ${formatarMoeda(referencia.amortizacao)}.`;
}

function obterEntradaServico() {
    const ler = (id) => [...document.querySelectorAll(`#${id} [data-ano]`)].map(linha => {
        const [juros, amortizacao] = linha.querySelectorAll('input');
        return {ano: Number(linha.dataset.ano),
                juros_encargos: normalizarValorMonetario(juros.value, 'Juros e encargos')?.numero ?? null,
                amortizacao: normalizarValorMonetario(amortizacao.value, 'Amortização')?.numero ?? null};
    });
    return {fator: document.getElementById('fator-rcl').value,
            ano_fim_contrato: Number(document.getElementById('ano-fim-contrato').value),
            hipotese_1: ler('linhas-hipotese-1'),
            hipotese_2: document.getElementById('secao-hipotese-2').classList.contains('hidden')
                ? null : ler('linhas-hipotese-2')};
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
    
    const todasAsRegras = resultado.regras_ordenadas || [
        ...(resultado.regras_violadas || []),
        ...(resultado.regras_cumpridas || []),
        ...(resultado.regras_sem_informacao || [])
    ];
    const servico = todasAsRegras.find(regra => regra.tipo === 'servico_divida');

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
            tr.children[1].querySelector('span').textContent = regra.aprovado ? 'Atendido' : 'Excedido';
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

function renderizarServicoDivida(regra, container) {
    const dados = regra.dados_calculados || {};
    const historico = dados.historico;
    const resultados = document.getElementById('servico-resultados');
    resultados.replaceChildren();
    const criar = (tag, classe, texto) => {
        const no = document.createElement(tag);
        no.className = classe;
        if (texto !== undefined) no.textContent = texto;
        return no;
    };
    const secao = (titulo) => {
        const no = criar('section', 'servico-section');
        no.appendChild(criar('h4', 'servico-section-title', titulo));
        container.appendChild(no);
        return no;
    };
    const linha = (pai, rotulo, valor, destaque = false) => {
        const dl = criar('div', `servico-value-row ${destaque ? 'servico-value-total' : ''}`);
        dl.append(criar('dt', '', rotulo), criar('dd', '', valor));
        pai.appendChild(dl);
    };
    const moedaOuIndisponivel = valor => valor === null || valor === undefined ? 'Não disponível' : formatarMoeda(valor);

    const etapa = secao(`1ª etapa — Exercício anterior (${dados.ano_historico})`);
    etapa.classList.add('servico-stage');
    if (historico) {
        etapa.classList.add(historico.aprovado ? 'servico-stage-ok' : 'servico-stage-failed');
        etapa.appendChild(criar('span', `servico-badge ${historico.aprovado ? 'servico-ok' : 'servico-failed'}`,
            historico.aprovado ? 'Regra atendida' : 'Regra não atendida'));
        etapa.appendChild(criar('p', 'servico-stage-description', historico.aprovado
            ? 'O serviço da dívida ficou abaixo de 11,5% da RCL do exercício anterior.'
            : 'O serviço da dívida ficou igual ou acima de 11,5% da RCL do exercício anterior.'));
        const resultado = criar('div', 'servico-result-grid');
        for (const [rotulo, valor] of [
            ['Serviço da dívida', historico.servico_divida],
            ['Limite', historico.limite],
            ['Margem', historico.margem],
        ]) {
            const celula = criar('div', 'servico-result-item');
            celula.append(criar('span', '', rotulo), criar('strong', '', formatarMoeda(valor)));
            resultado.appendChild(celula);
        }
        etapa.appendChild(resultado);
        etapa.appendChild(criar('p', 'servico-comparison', `${formatarMoeda(historico.servico_divida)} ${historico.aprovado ? '<' : '≥'} ${formatarMoeda(historico.limite)} · A igualdade reprova esta etapa.`));

        const detalhesExercicio = criar('details', 'servico-exercicio-detalhes');
        detalhesExercicio.appendChild(criar('summary', '', 'Dados do exercício anterior · SICONFI'));
        const exercicio = criar('div', 'servico-exercicio-dados');
        linha(exercicio, 'RCL ajustada para endividamento', moedaOuIndisponivel(dados.rcl_historica));
        linha(exercicio, 'Juros e encargos liquidados', formatarMoeda(historico.juros_encargos));
        linha(exercicio, 'Amortização liquidada', formatarMoeda(historico.amortizacao));
        linha(exercicio, 'Restos a pagar não processados', formatarMoeda(historico.restos_juros + historico.restos_amortizacao));
        linha(exercicio, 'Serviço da dívida', formatarMoeda(historico.servico_divida), true);
        linha(exercicio, 'Limite aplicável (calculado: RCL × 11,5%)', formatarMoeda(historico.limite), true);
        const periodo = valor => valor == null ? 'período indisponível' : `${valor}º bimestre`;
        exercicio.appendChild(criar('p', 'servico-source', `Fonte dos dados: SICONFI / RREO · RCL: Anexo 03, ${periodo(dados.periodo_rcl_historica)} de ${dados.ano_historico}; despesas: Anexo 01, ${periodo(dados.periodo_historico)} de ${dados.ano_historico}.`));
        detalhesExercicio.appendChild(exercicio);
        etapa.appendChild(detalhesExercicio);
    } else {
        etapa.appendChild(criar('p', 'servico-stage-description', 'Ainda não foi possível validar o exercício anterior com os dados oficiais disponíveis.'));
    }
    const baseContainer = document.getElementById('servico-dados-base');
    baseContainer.replaceChildren();
    const detalhesBase = criar('details', 'servico-exercicio-detalhes');
    detalhesBase.appendChild(criar('summary', '', 'Dados-base da projeção · SICONFI'));
    const base = criar('div', 'servico-exercicio-dados');
    linha(base, 'RCL de referência', moedaOuIndisponivel(dados.rcl_atual));
    linha(base, 'Período da RCL', dados.periodo_rcl_atual ? `${dados.periodo_rcl_atual}º bimestre de ${dados.ano_atual}` : 'Não disponível');
    linha(base, 'Fonte da RCL', 'SICONFI / RREO, Anexo 03');
    linha(base, 'Fator de projeção', dados.fator ?? 'Não disponível');
    const referencia = dados.referencia_rreo_atual;
    if (referencia) {
        linha(base, 'Juros e encargos de referência', formatarMoeda(referencia.juros_encargos));
        linha(base, 'Amortização de referência', formatarMoeda(referencia.amortizacao));
        linha(base, 'Período das despesas', `${referencia.periodo}º bimestre de ${referencia.ano} · ${referencia.origem}`);
    }
    base.appendChild(criar('p', 'servico-source', 'Os valores do RREO são referência oficial. Os pagamentos futuros são informados pelo usuário nos campos abaixo.'));
    detalhesBase.appendChild(base);
    baseContainer.appendChild(detalhesBase);

    const problemas = [];
    if (dados.rcl_historica == null) problemas.push('RCL do exercício anterior: não disponível.');
    if (dados.periodo_historico == null) problemas.push('Juros e amortização do exercício anterior: não disponíveis.');
    if (dados.rcl_atual == null) problemas.push('RCL de referência para a projeção: não disponível.');
    if (!referencia) problemas.push('Juros e amortização de referência do ano atual: não disponíveis; os campos da operação continuam editáveis.');
    if (dados.periodo_historico && dados.periodo_rcl_historica && dados.periodo_historico !== dados.periodo_rcl_historica) {
        problemas.push('RCL e despesas do exercício anterior pertencem a bimestres diferentes.');
    }
    if (regra.descricao?.startsWith('Dados inválidos ou ambíguos:')) {
        problemas.push(regra.descricao.replace('Dados inválidos ou ambíguos:', 'Verifique o dado:'));
    }
    if (problemas.length) {
        const aviso = secao('ATENÇÃO NOS DADOS DA PROJEÇÃO');
        aviso.classList.add('servico-warning');
        aviso.appendChild(criar('p', '', 'Não foi possível obter automaticamente todos os dados necessários.'));
        const lista = criar('ul', '');
        problemas.forEach(problema => lista.appendChild(criar('li', '', problema)));
        aviso.appendChild(lista);
        aviso.appendChild(criar('p', '', !historico || dados.rcl_atual == null
            ? 'O cálculo não pode continuar até que os dados oficiais necessários estejam disponíveis.'
            : 'A referência do ano atual é opcional; o cálculo continuará com os lançamentos válidos da operação.'));
    }

    for (const numero of [1, 2]) {
        const hipotese = dados[`hipotese_${numero}`];
        if (!hipotese) continue;
        const resultado = criar('section', 'servico-section');
        resultado.appendChild(criar('h4', 'servico-section-title', `RESULTADO DA PROJEÇÃO · HIPÓTESE ${numero}`));
        resultados.appendChild(resultado);
        resultado.id = `servico-resultado-hipotese-${numero}`;
        resultado.appendChild(criar('span', `servico-badge ${hipotese.aprovado ? 'servico-ok' : 'servico-failed'}`,
            hipotese.aprovado ? 'Hipótese atendida' : 'Hipótese não atendida'));
        const fora = hipotese.linhas.filter(item => item.margem <= 0);
        resultado.appendChild(criar('p', 'servico-stage-description',
            `Média dos percentuais anuais: ${formatarPercentual(hipotese.media_percentual)}. A hipótese ${hipotese.aprovado ? 'passa' : 'não passa'} porque a média deve ser inferior a 11,50%. ${fora.length ? `${fora.length} exercício(s) ficaram no limite ou acima dele; primeiro: ${fora[0].ano}.` : 'Todos os exercícios ficaram abaixo do limite anual.'}`));
        if (numero === 1 && !hipotese.aprovado) {
            resultado.appendChild(criar('p', 'servico-next-step', dados.ano_atual <= 2027
                ? 'Hipótese 1 não atendida. A análise seguirá para a Hipótese 2.'
                : 'Hipótese 1 não atendida. A Hipótese 2, limitada a 2027, não se aplica a este ano.'));
        }
        const tabela = criar('div', 'servico-year-table');
        const cabecalho = criar('div', 'servico-year-head');
        for (const titulo of ['Ano', 'Serviço', 'RCL projetada', 'Limite 11,5%', 'Margem', 'Situação anual']) cabecalho.appendChild(criar('span', '', titulo));
        tabela.appendChild(cabecalho);
        for (const item of hipotese.linhas) {
            const linhaAno = criar('div', 'servico-year-row');
            for (const [rotulo, valor] of [
                ['Ano', item.ano], ['Serviço', formatarMoeda(item.servico_divida)],
                ['RCL projetada', formatarMoeda(item.rcl_projetada)],
                ['Limite 11,5%', formatarMoeda(item.limite)],
                ['Margem', formatarMoeda(item.margem)],
                ['Situação anual', item.margem > 0 ? 'Abaixo do limite' : 'No limite ou acima'],
            ]) {
                const celula = criar('span', '', valor);
                celula.dataset.label = rotulo;
                linhaAno.appendChild(celula);
            }
            tabela.appendChild(linhaAno);
        }
        resultado.appendChild(tabela);
        if (hipotese.linhas.length > 1) {
            const grafico = criar('div', 'servico-chart');
            grafico.appendChild(criar('h5', '', 'Serviço × limite por exercício'));
            const maior = Math.max(...hipotese.linhas.flatMap(item => [item.servico_divida, item.limite]), 1);
            for (const item of hipotese.linhas) {
                const grupo = criar('div', 'servico-chart-year');
                grupo.appendChild(criar('strong', '', String(item.ano)));
                for (const [classe, rotulo, valor] of [
                    ['servico-chart-service', 'Serviço', item.servico_divida],
                    ['servico-chart-limit', 'Limite', item.limite],
                ]) {
                    const faixa = criar('div', 'servico-chart-line');
                    faixa.appendChild(criar('span', '', rotulo));
                    const trilho = criar('div', 'servico-chart-track');
                    const preenchimento = criar('div', classe);
                    preenchimento.style.width = `${Math.max(0, Math.min(100, valor / maior * 100))}%`;
                    trilho.appendChild(preenchimento);
                    faixa.append(trilho, criar('span', '', formatarMoeda(valor)));
                    grupo.appendChild(faixa);
                }
                grafico.appendChild(grupo);
            }
            resultado.appendChild(grafico);
        }
    }
    const entender = criar('details', 'servico-explanation');
    entender.appendChild(criar('summary', '', 'Entenda esta validação'));
    entender.append(
        criar('p', '', 'O serviço da dívida soma juros, encargos e amortizações; no exercício anterior, também entram os restos a pagar não processados encontrados no RREO.'),
        criar('p', '', 'No exercício anterior, o limite é a RCL do exercício × 11,5%. Nas hipóteses futuras, o limite é a RCL projetada × 11,5%. A margem é o limite menos o serviço considerado. Igualdade não atende à regra implementada.'),
        criar('p', '', 'Nas hipóteses futuras, cada ano usa RCL de referência × fator elevado ao número do ano projetado. A decisão usa a média dos percentuais anuais, com aprovação quando essa média é inferior a 11,5%.'),
        criar('p', '', 'Referências do projeto: Resolução do Senado Federal nº 43/2001 e Manual para Instrução de Pleitos (MIP).'));
    resultados.appendChild(entender);
}

function mostrarDetalhesRegra(regra) {
    document.getElementById('modal-feedback').dataset.regraTipo = regra.tipo || '';
    const servico = regra.tipo === 'servico_divida';
    document.getElementById('servico-resultados').classList.toggle('hidden', !servico);
    document.getElementById('servico-parametros').classList.toggle('hidden', !servico);
    if (servico) {
        const fator = regra.dados_calculados?.fator ?? document.getElementById('fator-rcl').value;
        document.getElementById('valor-fator-resumo').textContent = `· ${fator}`;
        document.getElementById('servico-fator-fonte').textContent = regra.base_normativa
            ? `Base normativa informada para a regra: ${regra.base_normativa}. O fator é um parâmetro editável salvo no sistema.`
            : 'O fator é um parâmetro editável salvo no sistema; não há fonte normativa específica informada para o seu valor.';
    }
    const podeProjetar = servico && regra.dados_calculados?.historico?.aprovado === true;
    const painelProjecoes = document.getElementById('servico-projecoes');
    painelProjecoes.classList.toggle('hidden', !podeProjetar);
    painelProjecoes.classList.toggle('servico-etapa-aprovada', podeProjetar && regra.aprovado === true);
    painelProjecoes.classList.toggle('servico-etapa-reprovada', podeProjetar && regra.aprovado === false);
    if (podeProjetar) {
        const primeira = regra.dados_calculados.hipotese_1;
        document.getElementById('secao-hipotese-2').classList.toggle('hidden', !primeira ||
            primeira.aprovado || Number(document.getElementById('ano').value) > 2027);
        preencherReferenciaServico(regra.dados_calculados.referencia_rreo_atual);
    }
    document.getElementById('servico-modal-intro').classList.toggle('hidden', !servico);
    if (servico) {
        document.getElementById('servico-anos-contexto').textContent =
            `Ano inicial: ${regra.dados_calculados?.ano_atual}. O ano final define até qual exercício o fluxo será projetado.`;
    }
    const ouroAnterior = regra.tipo === 'regra_ouro_anterior';
    const ouroAtual = regra.tipo === 'regra_ouro_atual';
    const dtp = regra.tipo === 'dtp' || regra.tipo === 'dcl' || regra.tipo === 'servico_divida' || ouroAnterior || ouroAtual;
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
    
    if (ouroAnterior) {
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
