let referenciaTaxaIndexador = null;
let versaoConsultaIndexador = 0;
let tipoTaxaAnterior = null;
let operacaoEraCambial = false;
function atualizarPrazoTotal() {
    const carencia = document.getElementById('tlp-carencia');
    const amortizacao = document.getElementById('operacao-amortizacao');
    const total = document.getElementById('tlp-prazo');
    const soma = Number(carencia.value) + Number(amortizacao.value);
    total.value = carencia.value !== '' && amortizacao.value !== '' && Number.isInteger(soma) ? String(soma) : '';
    total.setCustomValidity(soma > 600 ? 'A soma dos prazos deve ser de no máximo 600 meses.' : '');
}
function decimalCotacaoContratual(texto) {
    texto = texto.trim().replace(/\s/g, '');
    if (texto.includes(',')) texto = texto.replace(/\./g, '').replace(',', '.');
    if (!/^\d+(?:\.\d{1,12})?$/.test(texto) || !(Number(texto) > 0)) throw new Error('Informe a cotação contratual em reais por unidade da moeda.');
    return texto;
}
function indexadorDeJuros() {
    const indexador = document.getElementById('operacao-indexador').value;
    if (['CDI','SELIC','TLP','SOFR'].includes(indexador)) return indexador;
    return indexador === 'CAMBIAL' && document.getElementById('operacao-juros-cambial').value === 'SOFR' ? 'SOFR' : null;
}
function atualizarRotuloMoedaContrato() {
    const cambial = document.getElementById('operacao-indexador').value === 'CAMBIAL';
    const moeda = cambial ? document.getElementById('operacao-moeda-contrato').value : (typeof CambioUI !== 'undefined' ? CambioUI.referencia().moeda : 'BRL');
    document.querySelector('label[for="valor-requisitado"]').textContent = `Valor do empréstimo (${moeda === 'BRL' ? 'R$' : moeda})`;
    if (cambial) document.getElementById('valor-requisitado').placeholder = `${moeda} 0,00`;
}
function atualizarIndexadorOperacao(consultar) {
    const tipo = document.getElementById('operacao-indexador').value;
    const cambial = tipo === 'CAMBIAL';
    if (cambial !== operacaoEraCambial) {
        const valor = document.getElementById('valor-requisitado');
        valor.value = ''; delete valor.dataset.cambioBrl; delete valor.dataset.cambioExibido;
        operacaoEraCambial = cambial;
    }
    for (const id of ['operacao-moeda-campo','operacao-cotacao-campo','operacao-juros-campo']) document.getElementById(id).hidden = !cambial;
    const taxa = indexadorDeJuros();
    document.getElementById('operacao-taxa-campo').hidden = !taxa;
    if (taxa !== tipoTaxaAnterior) {
        versaoConsultaIndexador++;
        referenciaTaxaIndexador = null;
        document.getElementById('operacao-taxa-indexador').value = '';
        document.getElementById('operacao-taxa-fonte').textContent = '';
        if (taxa) document.getElementById('tlp-prefixada').value = '0';
        tipoTaxaAnterior = taxa;
    }
    document.querySelector('label[for="operacao-taxa-indexador"]').textContent = taxa === 'TLP' ? 'Parcela fixa TLP · Jm (% ao ano)' : `${taxa === 'SOFR' ? 'SOFR overnight' : taxa === 'SELIC' ? 'Selic' : taxa || 'Indexador'} (% ao ano)`;
    document.querySelector('label[for="tlp-prefixada"]').textContent = taxa ? 'Taxa fixa adicional (% ao ano)' : 'Taxa fixa da proposta (% ao ano)';
    document.getElementById('operacao-premissas-indexador').textContent = tipo === 'IPCA' || tipo === 'TLP'
        ? 'IPCA mensal publicado; competências sem publicação usam zero. Taxas fixas e spread em 252 dias úteis. Na TLP, a parcela Jm selecionada fica fixa.'
        : taxa === 'SOFR' ? 'Cenário com SOFR overnight constante, taxa fixa e spread somados; juros simples em dias corridos, base 360. Não é Term SOFR de seis meses.'
        : 'Cenário com taxas anuais constantes, composição dos fatores em 252 dias úteis e calendário FCL.';
    atualizarRotuloMoedaContrato();
    if (consultar && taxa) consultarTaxaOperacao();
}
async function consultarTaxaOperacao() {
    const tipo = indexadorDeJuros(); if (!tipo) return;
    const versao = ++versaoConsultaIndexador;
    const entrada = document.getElementById('operacao-taxa-indexador');
    const valorAnterior = entrada.value;
    const mensagem = document.getElementById('operacao-taxa-fonte');
    mensagem.textContent = 'Consultando taxa…';
    try {
        const r = await eel.obter_taxa_indexador_py(tipo)();
        if (versao !== versaoConsultaIndexador || tipo !== indexadorDeJuros()) return;
        if (r.status !== 'sucesso' || !r.taxa) throw new Error(r.mensagem || 'Taxa indisponível. Informe manualmente.');
        // Não substituir uma edição feita enquanto a consulta estava em andamento.
        if (entrada.value !== valorAnterior) { mensagem.textContent = 'Taxa informada manualmente.'; return; }
        referenciaTaxaIndexador = r.taxa;
        entrada.value = r.taxa.valor;
        mensagem.textContent = `${r.taxa.fonte} · ${r.taxa.data.split('-').reverse().join('/')} · editável`;
        entrada.dispatchEvent(new Event('input', {bubbles:true}));
    } catch (erro) {
        if (versao === versaoConsultaIndexador) mensagem.textContent = erro.message;
    }
}

/* Contexto único da operação. As avaliações mantêm apenas seus dados específicos. */
let revisaoOperacao = 0;
let servicoInformado = false;
let fluxoTlpServico = null;
let basesOperacaoCalculada = [];
let revisaoServico = 0;

function invalidarServicoTlp() {
    revisaoServico++;
    if (!fluxoTlpServico) return;
    fluxoTlpServico = null;
    basesOperacaoCalculada = [];
    servicoInformado = false;
    document.getElementById('servico-resultados').replaceChildren();
    document.querySelectorAll('#tbody-resultados tr').forEach(item => {
        if (item.textContent.includes('Serviço da Dívida') || item.textContent.includes('Serviço da dívida')) {
            item.children[1].textContent = 'Desatualizada';
            item.children[2].textContent = 'Recalcule o serviço da dívida com as condições atualizadas.';
        }
    });
}

let revisaoFluxo = 0;
const liberacoesOperacao = new Map();
const basesFluxoOperacao = new Map();
const avaliacoesComplementares = {
    fluxo: {nome: 'Fluxo anual de operações de crédito · MGA/RCL', status: 'Não avaliada', descricao: 'Consulte as liberações anuais e a margem sobre a RCL projetada.'},
};
let focoAntesModal = null;

function obterOperacaoCompartilhada() {
    const ano = Number(document.getElementById('ano').value);
    const fim = Number(document.getElementById('ano-fim-contrato').value);
    const texto = document.getElementById('valor-requisitado').value.trim();
    if (!Number.isInteger(ano) || ano < 1900) throw new Error('Informe o exercício nos dados do empréstimo.');
    if (!texto) throw new Error('Informe o valor total do possível empréstimo nos dados do empréstimo.');
    const valor = Number(lerValorRequisitado(texto).numero);
    if (!(valor > 0)) throw new Error('O valor total do possível empréstimo deve ser positivo.');
    if (!Number.isInteger(fim) || fim < ano) throw new Error('Informe o ano final do empréstimo nos dados do empréstimo.');
    const liberacoes = {};
    if (document.getElementById('operacao-tipo-liberacao').value === 'unica') {
        for (let exercicio = ano; exercicio <= fim; exercicio++) liberacoes[exercicio] = exercicio === ano ? valor : 0;
    } else {
        for (const campo of document.querySelectorAll('#operacao-liberacoes input')) {
            if (campo.value.trim() === '' || !campo.validity.valid) throw new Error('Complete as liberações por ano no calendário de recebimentos, inclusive os valores iguais a zero.');
            liberacoes[Number(campo.dataset.ano)] = Number(campo.value);
        }
        const soma = Object.values(liberacoes).reduce((total, v) => total + v, 0);
        if (Object.keys(liberacoes).length !== fim - ano + 1 || Math.abs(soma - valor) > .005) throw new Error('A soma das parcelas a receber deve corresponder ao valor total do empréstimo.');
    }
    return {ano, fim, valor, liberacoes};
}

function obterCondicoesOperacao() {
    atualizarPrazoTotal();
    const comum = obterOperacaoCompartilhada();
    const entrada = {...comum, tipo_liberacao: document.getElementById('operacao-tipo-liberacao').value,
        data_liberacao: document.getElementById('operacao-data-liberacao').value,
        fator: document.getElementById('fator-rcl').value,
        indexador: document.getElementById('operacao-indexador').value,
        amortizacao_meses: document.getElementById('operacao-amortizacao').value};
    if (entrada.indexador === 'CAMBIAL') {
        entrada.moeda_contrato = document.getElementById('operacao-moeda-contrato').value;
        entrada.cotacao_contrato = decimalCotacaoContratual(document.getElementById('operacao-cotacao-contrato').value);
        entrada.referencia_juros_cambial = document.getElementById('operacao-juros-cambial').value;
    } else if (typeof CambioUI !== 'undefined') {
        entrada.cotacao_id = CambioUI.referencia().id;
        const campo = document.getElementById('valor-requisitado');
        if (campo.dataset.cambioExibido === campo.value && campo.dataset.cambioBrl) entrada.valor_base_brl = campo.dataset.cambioBrl;
    }
    const tipoTaxa = indexadorDeJuros();
    if (tipoTaxa) {
        const campoTaxa = document.getElementById('operacao-taxa-indexador');
        if (campoTaxa.value === '' || !campoTaxa.validity.valid) throw new Error('Consulte ou informe a taxa do indexador.');
        entrada.taxa_indexador = campoTaxa.value;
        entrada.referencia_indexador_id = referenciaTaxaIndexador?.id ?? null;
    }
    if (!entrada.data_liberacao) throw new Error('Informe a data prevista de recebimento.');
    for (const [nome, id] of Object.entries({prazo_meses:'tlp-prazo', carencia_meses:'tlp-carencia', prefixada:'tlp-prefixada', spread:'tlp-spread'})) {
        const campo = document.getElementById(id);
        if (!campo.value.trim() || !campo.validity.valid) throw new Error('Complete o prazo, a carência e as taxas da proposta na página principal.');
        entrada[nome] = campo.value;
    }
    return entrada;
}

function mostrarErroOperacao(mensagem) {
    const erro = document.getElementById('operacao-erro');
    erro.textContent = mensagem;
    erro.hidden = false;
    erro.scrollIntoView({behavior: 'smooth', block: 'center'});
}

function montarLiberacoesCompartilhadas() {
    const destino = document.getElementById('operacao-liberacoes');
    for (const campo of destino.querySelectorAll('input')) liberacoesOperacao.set(Number(campo.dataset.ano), campo.value);
    destino.replaceChildren();
    const ano = Number(document.getElementById('ano').value);
    const fim = Number(document.getElementById('ano-fim-contrato').value);
    if (!ano || fim < ano) return;
    const unica = document.getElementById('operacao-tipo-liberacao').value === 'unica';
    document.getElementById('operacao-cronograma-detalhes').hidden = unica;
    if (unica) return;
    for (let exercicio = ano; exercicio <= fim; exercicio++) {
        const label = document.createElement('label');
        label.textContent = `Liberação de ${exercicio} (${document.getElementById('operacao-indexador').value === 'CAMBIAL' ? document.getElementById('operacao-moeda-contrato').value : 'R$'})`;
        const campo = document.createElement('input');
        campo.type = 'number'; campo.min = '0'; campo.step = '0.01';
        campo.dataset.ano = exercicio;
        campo.value = liberacoesOperacao.get(exercicio) ?? '';
        label.appendChild(campo);
        destino.appendChild(label);
    }
    document.getElementById('operacao-cronograma-detalhes').open = true;
}

function montarFluxoDaOperacao() {
    const destino = document.getElementById('fluxo-credito-linhas');
    for (const linha of destino.querySelectorAll('[data-ano]')) {
        basesFluxoOperacao.set(Number(linha.dataset.ano), Object.fromEntries([...linha.querySelectorAll('input')].map(campo => [campo.dataset.campo, campo.value])));
    }
    destino.replaceChildren();
    const ano = Number(document.getElementById('ano').value);
    const fim = Number(document.getElementById('ano-fim-contrato').value);
    if (!ano || fim < ano) return;
    for (let exercicio = ano; exercicio <= fim; exercicio++) {
        const linha = document.createElement('div');
        linha.className = 'fluxo-sim-linha'; linha.dataset.ano = exercicio;
        const titulo = document.createElement('strong'); titulo.textContent = `Exercício ${exercicio}`; linha.appendChild(titulo);
        for (const [chave, rotulo] of [['liberacoesNaoContratadasManual', 'Outros empréstimos em negociação (R$)']]) {
            const label = document.createElement('label'); label.textContent = rotulo;
            const campo = document.createElement('input'); campo.type = 'number'; campo.min = '0'; campo.step = '0.01';
            campo.dataset.campo = chave; campo.value = basesFluxoOperacao.get(exercicio)?.[chave] ?? '';
            campo.setAttribute('aria-label', `${rotulo} em ${exercicio}`);
            label.appendChild(campo); linha.appendChild(label);
        }
        const nota = document.createElement('p'); nota.className = 'operacao-liberacao-contexto'; nota.dataset.ano = exercicio;
        linha.appendChild(nota); destino.appendChild(linha);
    }
    atualizarContextoOperacao();
}

function liberacaoEmReaisParaExibicao(comum, ano) {
    const calculado=basesOperacaoCalculada.find(item=>item.ano===ano)?.liberacaoNovaOperacao;
    if(calculado!=null) return calculado;
    let taxa=typeof CambioUI!=='undefined'?Number(CambioUI.referencia().taxa_brl):1;
    if(document.getElementById('operacao-indexador').value==='CAMBIAL') {
        try {taxa=Number(decimalCotacaoContratual(document.getElementById('operacao-cotacao-contrato').value));}
        catch(_){return null;}
    }
    return comum.liberacoes[ano]*taxa;
}

function atualizarContextoOperacao() {
    let comum;
    try { comum = obterOperacaoCompartilhada(); } catch (_) { return; }
    document.querySelectorAll('.operacao-liberacao-contexto').forEach(no => {
        const ano=Number(no.dataset.ano);
        const valor=liberacaoEmReaisParaExibicao(comum,ano);
        const rcl=basesOperacaoCalculada.find(item=>item.ano===ano)?.rclProjetada;
        no.textContent=`Liberação deste empréstimo: ${valor==null?'informe a cotação contratual':formatarMoeda(valor)} · RCL projetada: ${rcl!=null?formatarMoeda(rcl):'indisponível; atualize as avaliações'}`;
    });
}

function obterEntradaFluxoCompartilhada() {
    const comum = obterOperacaoCompartilhada();
    if (comum.fim - comum.ano + 1 > 30) throw new Error('A avaliação de fluxo suporta até 30 exercícios. O prazo comum foi preservado; esta avaliação precisa de um horizonte compatível.');
    const complementos = [...document.querySelectorAll('#fluxo-credito-linhas .fluxo-sim-linha')].map(linha => {
        const ano = Number(linha.dataset.ano);
        const entrada = {ano, liberacaoNovaOperacao: comum.liberacoes[ano]};
        for (const campo of linha.querySelectorAll('input')) {
            if (!campo.validity.valid) throw new Error('Informe valores não negativos na avaliação de fluxo.');
            entrada[campo.dataset.campo] = campo.value.trim() === '' ? null : Number(campo.value);
        }
        return entrada;
    });
    return {operacao: obterCondicoesOperacao(), complementos};
}

function registrarAvaliacaoComplementar(tipo, status, descricao) {
    Object.assign(avaliacoesComplementares[tipo], {status, descricao});
    renderizarAvaliacoesComplementares();
}

function renderizarAvaliacoesComplementares() {
    const tbody = document.getElementById('tbody-resultados');
    tbody.querySelectorAll('[data-complementar]').forEach(linha => linha.remove());
    for (const [tipo, avaliacao] of Object.entries(avaliacoesComplementares)) {
        if (tipo === 'fluxo') continue;
        const linha = document.createElement('tr'); linha.dataset.complementar = tipo;
        for (const texto of [avaliacao.nome, avaliacao.status, avaliacao.descricao]) {
            const celula = document.createElement('td'); celula.className = 'px-6 py-4 text-sm'; celula.textContent = texto; linha.appendChild(celula);
        }
        const celula = document.createElement('td'); celula.className = 'px-6 py-4';
        const botao = document.createElement('button'); botao.type = 'button'; botao.className = 'text-blue-600 hover:text-blue-900 ver-detalhes-btn';
        botao.setAttribute('aria-haspopup', 'dialog');
        botao.textContent = 'Abrir avaliação'; botao.addEventListener('click', () => abrirModalAvaliacao(tipo));
        celula.appendChild(botao); linha.appendChild(celula); tbody.appendChild(linha);
    }
}

function abrirModalAvaliacao(tipo) {
    try { obterOperacaoCompartilhada(); }
    catch (erro) { mostrarErroOperacao(mensagemErroAmigavel(erro)); return; }
    atualizarContextoOperacao();
    focoAntesModal = document.activeElement;
    const modal = document.getElementById(`modal-${tipo}`);
    modal.classList.remove('hidden');
    modal.querySelector('button').focus();
}

function fecharModalAvaliacao(tipo) {
    document.getElementById(`modal-${tipo}`).classList.add('hidden');
    if (focoAntesModal?.isConnected) focoAntesModal.focus();
    else document.querySelector(`[data-complementar="${tipo}"] button`)?.focus();
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('tlp-carencia').addEventListener('input', atualizarPrazoTotal);
    document.getElementById('operacao-amortizacao').addEventListener('input', atualizarPrazoTotal);
    document.getElementById('operacao-indexador').addEventListener('change', () => atualizarIndexadorOperacao(true));
    document.getElementById('operacao-juros-cambial').addEventListener('change', () => atualizarIndexadorOperacao(true));
    document.getElementById('operacao-moeda-contrato').addEventListener('change', () => {
        document.getElementById('valor-requisitado').value = '';
        document.getElementById('operacao-cotacao-contrato').value = '';
        atualizarRotuloMoedaContrato(); montarLiberacoesCompartilhadas();
    });
    document.getElementById('operacao-atualizar-taxa').addEventListener('click', consultarTaxaOperacao);
    document.getElementById('operacao-taxa-indexador').addEventListener('input', () => {
        const valor = document.getElementById('operacao-taxa-indexador').value;
        if (!referenciaTaxaIndexador || Number(valor) !== Number(referenciaTaxaIndexador.valor)) document.getElementById('operacao-taxa-fonte').textContent = 'Taxa informada manualmente · constante nesta simulação';
    });
    atualizarIndexadorOperacao(false);
    document.getElementById('form-simulacao').addEventListener('input', () => {
        revisaoOperacao++;
        invalidarServicoTlp();
        document.getElementById('operacao-erro').hidden = true;
        document.getElementById('operacao-erro').textContent = '';
        document.getElementById('operacao-aviso').textContent = 'Dados alterados. Simule novamente para atualizar os resultados.';
        document.querySelectorAll('#tbody-resultados tr').forEach(linha => { if (linha.children[1]) linha.children[1].textContent = 'Desatualizada'; });
        for (const valor of Object.values(avaliacoesComplementares)) Object.assign(valor, {status: 'Desatualizada', descricao: 'Dados alterados. Simule novamente para atualizar o resultado.'});
        document.getElementById('fluxo-credito-resultado').textContent = 'Dados alterados. Simule novamente.';
        document.getElementById('tlp-resultado').textContent = 'Dados alterados. Simule novamente.';
        atualizarContextoOperacao();
    });
    document.getElementById('form-fluxo-credito').addEventListener('input', () => {
        revisaoFluxo++;
        document.getElementById('fluxo-credito-resultado').textContent = 'Dados alterados. Recalcule o fluxo.';
        registrarAvaliacaoComplementar('fluxo', 'Desatualizada', 'A receita ou os dados complementares mudaram.');
    });
    document.getElementById('operacao-tipo-liberacao').addEventListener('change', () => { montarLiberacoesCompartilhadas(); atualizarContextoOperacao(); });
    document.querySelectorAll('[data-fechar-avaliacao]').forEach(botao => botao.addEventListener('click', () => fecharModalAvaliacao(botao.dataset.fecharAvaliacao)));
    for (const tipo of ['fluxo']) {
        const modal = document.getElementById(`modal-${tipo}`);
        modal.addEventListener('click', evento => { if (evento.target === modal) fecharModalAvaliacao(tipo); });
        modal.addEventListener('keydown', evento => {
            if (evento.key === 'Escape') fecharModalAvaliacao(tipo);
            if (evento.key !== 'Tab') return;
            const focaveis = [...modal.querySelectorAll('button,input,select,summary')].filter(no => !no.disabled && no.getClientRects().length);
            const primeiro = focaveis[0], ultimo = focaveis[focaveis.length - 1];
            if (evento.shiftKey && document.activeElement === primeiro) { evento.preventDefault(); ultimo.focus(); }
            else if (!evento.shiftKey && document.activeElement === ultimo) { evento.preventDefault(); primeiro.focus(); }
        });
    }
});
