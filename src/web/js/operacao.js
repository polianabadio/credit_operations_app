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
    const comum = obterOperacaoCompartilhada();
    const entrada = {...comum, tipo_liberacao: document.getElementById('operacao-tipo-liberacao').value,
        data_liberacao: document.getElementById('operacao-data-liberacao').value,
        fator: document.getElementById('fator-rcl').value};
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
        label.textContent = `Liberação de ${exercicio} (R$)`;
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

function atualizarContextoOperacao() {
    let comum;
    try { comum = obterOperacaoCompartilhada(); } catch (_) { return; }
    document.querySelectorAll('.operacao-liberacao-contexto').forEach(no => { no.textContent = `Liberação deste empréstimo: ${formatarMoeda(comum.liberacoes[Number(no.dataset.ano)])} · RCL projetada: ${basesOperacaoCalculada.find(item => item.ano === Number(no.dataset.ano))?.rclProjetada != null ? formatarMoeda(basesOperacaoCalculada.find(item => item.ano === Number(no.dataset.ano)).rclProjetada) : 'indisponível; atualize as avaliações'}`; });
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
    catch (erro) { mostrarErroOperacao(erro.message); return; }
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
    document.getElementById('form-simulacao').addEventListener('input', () => {
        revisaoOperacao++;
        invalidarServicoTlp();
        document.getElementById('operacao-erro').hidden = true;
        document.getElementById('operacao-erro').textContent = '';
        document.getElementById('operacao-aviso').textContent = 'Dados alterados. Simule novamente para atualizar os resultados.';
        document.querySelectorAll('#tbody-resultados tr').forEach(linha => { if (linha.children[1]) linha.children[1].textContent = 'Desatualizada'; });
        for (const valor of Object.values(avaliacoesComplementares)) Object.assign(valor, {status: 'Desatualizada', descricao: 'Simule novamente para atualizar o resultado.'});
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
