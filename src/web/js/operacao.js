let referenciaTaxaIndexador = null;
let versaoConsultaIndexador = 0;
let tipoTaxaAnterior = null;
function atualizarPrazoTotal() {
    const carencia = document.getElementById('tlp-carencia');
    const amortizacao = document.getElementById('operacao-amortizacao');
    const total = document.getElementById('tlp-prazo');
    const soma = Number(carencia.value) + Number(amortizacao.value);
    total.value = carencia.value !== '' && amortizacao.value !== '' && Number.isInteger(soma) ? String(soma) : '';
    total.setCustomValidity(soma > 600 ? 'A soma dos prazos deve ser de no máximo 600 meses.' : '');
    const termino = atualizarFimContratual();
    if (usaPlanilhaSemestral()) montarLiberacoesCompartilhadas();
    return termino;
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
    if(typeof CambioUI!=='undefined') CambioUI.atualizarEntradas();
}
function atualizarIndexadorOperacao(consultar) {
    const tipo = document.getElementById('operacao-indexador').value;
    const cambial = tipo === 'CAMBIAL';
    for (const id of ['operacao-moeda-campo','operacao-cotacao-campo','operacao-juros-campo']) document.getElementById(id).hidden = !cambial;
    const taxa = indexadorDeJuros();
    document.getElementById('operacao-taxa-campo').hidden = !taxa;
    if (taxa !== tipoTaxaAnterior) {
        document.getElementById('base-juros').value=taxa === 'SOFR' ? '365' : ['CDI','SELIC'].includes(taxa) ? '252' : '360';
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
    atualizarModeloContratual();
    montarLiberacoesCompartilhadas();
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
    window.resumoOperacaoAtual=null;
    document.getElementById('resumo-operacao').hidden=true;
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
    if (!Number.isInteger(fim) || fim < ano) {
        const campoFim = document.getElementById('ano-fim-contrato');
        throw new Error(campoFim.disabled && document.getElementById('operacao-termino-calculado').textContent
            || 'Informe o ano final do empréstimo nos dados do empréstimo.');
    }
    const liberacoes = {};
    if (usaPlanilhaSemestral()) {
        const primeiraLiberacao = document.getElementById('operacao-data-liberacao').value;
        if (!primeiraLiberacao || Number(primeiraLiberacao.slice(0, 4)) !== ano) {
            throw new Error('Informe a data da primeira liberação dentro do ano de referência para definir as datas dos semestres.');
        }
        const liberacoes_semestrais = {};
        for (let exercicio = ano; exercicio <= fim; exercicio++) liberacoes[exercicio] = 0;
        for (const campo of document.querySelectorAll('#operacao-liberacoes input[data-ativo="true"]')) {
            const data = campo.dataset.ano;
            const valor = lerValorEntradaMonetaria(campo.value, `Liberação de ${data.split('-').reverse().join('/')}`);
            liberacoes_semestrais[data] = valor?.numero ?? '0.00';
            liberacoes[Number(data.slice(0, 4))] += Number(liberacoes_semestrais[data]);
        }
        return {ano, fim, valor, liberacoes, liberacoes_semestrais};
    }
    if (tipoLiberacaoOperacao() === 'unica') {
        for (let exercicio = ano; exercicio <= fim; exercicio++) liberacoes[exercicio] = exercicio === ano ? valor : 0;
    } else {
        for (const campo of document.querySelectorAll('#operacao-liberacoes input[data-ativo="true"]')) {
            const liberacao = lerValorEntradaMonetaria(campo.value, `Liberação de ${campo.dataset.ano}`);
            if (!liberacao) throw new Error('Complete as liberações por ano no calendário de recebimentos, inclusive os valores iguais a zero.');
            liberacoes[Number(campo.dataset.ano)] = usaModeloContratual() ? liberacao.numero : Number(liberacao.numero);
        }
        const soma = Object.values(liberacoes).reduce((total, v) => total + Number(v), 0);
        if (Object.keys(liberacoes).length !== fim - ano + 1 || (!usaModeloContratual() && Math.abs(soma - valor) > .005)) throw new Error('A soma das parcelas a receber deve corresponder ao valor total do empréstimo.');
    }
    return {ano, fim, valor, liberacoes};
}

function obterCondicoesOperacao() {
    if (usaPlanilhaSemestral() && indexadorDeJuros() !== 'SOFR') {
        throw new Error('O cálculo semestral usa SOFR. Selecione SOFR no indexador ou nos juros da operação cambial.');
    }
    if (!usaModeloContratual() && tipoLiberacaoOperacao() !== 'unica') {
        throw new Error('O modelo de IPCA/TLP usa liberação única. Para liberação fracionada, escolha um indexador compatível.');
    }
    const comum = obterOperacaoCompartilhada();
    const entrada = {...comum, tipo_liberacao: tipoLiberacaoOperacao(),
        data_liberacao: document.getElementById('operacao-data-liberacao').value,
        fator: document.getElementById('fator-rcl').value,
        indexador: document.getElementById('operacao-indexador').value,
        amortizacao_meses: document.getElementById('operacao-amortizacao').value};
    if (entrada.indexador === 'CAMBIAL') {
        entrada.moeda_contrato = document.getElementById('operacao-moeda-contrato').value;
        entrada.cotacao_contrato = decimalCotacaoContratual(document.getElementById('operacao-cotacao-contrato').value);
        entrada.referencia_juros_cambial = document.getElementById('operacao-juros-cambial').value;
    }
    if (typeof CambioUI !== 'undefined') {
        const referencia=CambioUI.referenciaEntrada();
        entrada.moeda_entrada=referencia.moeda;
        entrada.memoria_mudancas_unidade=CambioUI.memoriaEntrada();
        entrada.cotacao_id=referencia.id;
        const base=CambioUI.baseCampo(document.getElementById('valor-requisitado'));
        if(base!=null) entrada.valor_base_brl=base;
        entrada.liberacoes_base_brl={};entrada.encargos_base_brl={};
        for(const campo of document.querySelectorAll('#operacao-liberacoes input[data-ativo="true"]')) {
            const brl=CambioUI.baseCampo(campo);if(brl!=null)entrada.liberacoes_base_brl[campo.dataset.ano]=brl;
        }
        for(const campo of document.querySelectorAll('#operacao-outros-encargos input[data-ativo="true"]')) {
            const brl=CambioUI.baseCampo(campo);if(brl!=null)entrada.encargos_base_brl[campo.dataset.ano]=brl;
        }
    }
    if(usaModeloContratual()) entrada.valor=normalizarValorMonetario(document.getElementById('valor-requisitado').value).numero;
    entrada.complemento_limites = obterComplementoLimites();
    const tipoTaxa = indexadorDeJuros();
    if (tipoTaxa) {
        const campoTaxa = document.getElementById('operacao-taxa-indexador');
        if (campoTaxa.value === '' || !campoTaxa.validity.valid) throw new Error('Consulte ou informe a taxa do indexador.');
        entrada.taxa_indexador = campoTaxa.value;
        entrada.referencia_indexador_id = referenciaTaxaIndexador?.id ?? null;
    }
    if (!entrada.data_liberacao) throw new Error('Informe a data prevista de recebimento.');
    for (const [nome, id] of Object.entries({prazo_meses:'tlp-prazo', carencia_meses:'tlp-carencia', amortizacao_meses:'operacao-amortizacao', prefixada:'tlp-prefixada', spread:'tlp-spread', fator:'fator-rcl'})) {
        const campo = document.getElementById(id);
        if (!campo.value.trim() || !campo.validity.valid) throw new Error(`Confira o campo ${campo.labels[0].textContent}.`);
        entrada[nome] = campo.value;
    }
    if (usaModeloContratual()) {
        entrada.modelo_fluxo='contratual';
        if (usaPlanilhaSemestral()) {
            for (const [chave, id] of Object.entries({spread_capital:'spread-capital', comissao_credito:'comissao-credito'})) {
                const campo = document.getElementById(id);
                if (!campo.validity.valid) throw new Error(`Confira o campo ${campo.labels[0].textContent}.`);
                entrada[chave] = campo.value || '0';
            }
            return entrada;
        }
        if(usaCalendarioFixo()) {
            entrada.calendario_pagamentos='fixo';
            Object.assign(entrada, datasCalendarioAnual(entrada.data_liberacao));
            for(const [chave,id] of Object.entries({dias_inicio_comissao:'dias-inicio-comissao',prazo_desembolso_meses:'prazo-desembolso'})) {
                const campo=document.getElementById(id);
                if(campo.value==='' || !campo.validity.valid) throw new Error(`Confira o campo ${campo.labels[0].textContent}.`);
                entrada[chave]=campo.value;
            }
        }
        if (tipoTaxa === 'SOFR') entrada.metodo_sofr = document.getElementById('metodo-sofr').value;

        for(const [chave,id] of Object.entries({periodicidade_amortizacao:'periodicidade-amortizacao',periodicidade_juros:'periodicidade-juros',base_juros:'base-juros',spread_capital:'spread-capital',comissao_credito:'comissao-credito',mes_liberacoes:'mes-liberacoes'})) {
            const campo=document.getElementById(id);
            if(campo.value==='' || !campo.validity.valid) throw new Error('Complete as periodicidades, spreads e comissão do cenário.');
            entrada[chave]=campo.value;
        }
        entrada.encargos_anuais={};
        for(const campo of document.querySelectorAll('#operacao-outros-encargos input[data-ativo="true"]')) {
            if(campo.value==='' || !campo.validity.valid) throw new Error('Informe os outros encargos por ano, inclusive zeros.');
            entrada.encargos_anuais[campo.dataset.ano]=campo.value;
        }
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
    for (const campo of destino.querySelectorAll('input')) liberacoesOperacao.set(campo.dataset.periodo, guardarValorEntrada(campo));
    destino.replaceChildren();
    const ano = Number(document.getElementById('ano').value);
    const fim = Math.max(ano, Number(document.getElementById('ano-fim-contrato').value));
    const unica = tipoLiberacaoOperacao() === 'unica';
    const semestral = usaPlanilhaSemestral();
    document.getElementById('operacao-cronograma-detalhes').hidden = unica;
    document.querySelector('#operacao-cronograma-detalhes summary').textContent = semestral ? 'Liberações por semestre' : 'Liberações por ano';
    const abertura = document.getElementById('operacao-data-liberacao').value;
    const carencia = document.getElementById('tlp-carencia').value;
    const periodos = [];
    if (semestral) {
        const aviso = indexadorDeJuros() === 'SOFR' ? '' : ' Para calcular por semestre, selecione SOFR nos juros.';
        const orientacao = abertura ? '' : ' A data da primeira liberação define as datas dos semestres.';
        document.getElementById('liberacoes-ajuda').textContent = `Distribua o valor do empréstimo entre os semestres.${orientacao}${aviso}`;
        const quantidade = carencia === '' ? 2 : Math.min(100, Math.max(1, Math.ceil(Number(carencia) / 6)));
        for (let i = 0; i < quantidade; i++) periodos.push(`semestre-${i}`);
    } else {
        document.getElementById('liberacoes-ajuda').textContent = 'Distribua o valor total do empréstimo entre os anos.';
        const anos = new Set([...liberacoesOperacao.keys()].filter(chave => /^\d{4}$/.test(chave)));
        if (ano && fim >= ano) {
            for (let a = ano; a <= fim; a++) anos.add(String(a));
        }
        periodos.push(...[...anos].sort());
    }
    const ativos = new Set(periodos);
    for (const periodo of new Set([...periodos, ...liberacoesOperacao.keys()])) {
        const ordem = periodo.startsWith('semestre-') ? Number(periodo.slice('semestre-'.length)) : null;
        const data = ordem !== null && abertura ? deslocarDataContrato(abertura, ordem * 6) : null;
        const rotulo = ordem === null ? periodo : `${ordem + 1}º semestre${data ? ` · ${data.split('-').reverse().join('/')}` : ''}`;
        const ativo = ativos.has(periodo) && (ordem !== null || (Number(periodo) >= ano && Number(periodo) <= fim));
        const label = document.createElement('label');
        label.hidden = !ativo;
        const moeda = typeof CambioUI !== 'undefined' ? CambioUI.referenciaEntrada().moeda : 'BRL';
        const simbolo = typeof CambioUI !== 'undefined' ? CambioUI.simbolo() : 'R$';
        label.textContent = `Liberação ${ordem === null ? 'de' : 'do'} ${rotulo} (${moeda === 'BRL' ? 'R$' : moeda})`;
        const campo = document.createElement('input');
        campo.type = 'text';
        campo.inputMode = 'decimal';
        campo.autocomplete = 'off';
        campo.placeholder = `${simbolo} 0,00`;
        campo.dataset.periodo = periodo;
        campo.dataset.ano = data ?? periodo;
        campo.dataset.ativo = String(ativo);
        restaurarValorEntrada(campo,liberacoesOperacao.get(periodo),'');
        const erro = document.createElement('span');
        erro.id = `liberacao-erro-${periodo}`;
        erro.className = 'simulacao-erro';
        erro.setAttribute('role', 'alert');
        erro.hidden = true;
        campo.setAttribute('aria-describedby', erro.id);
        configurarCampoMonetario(campo, erro, valor => lerValorEntradaMonetaria(valor, `Liberação de ${rotulo}`));
        label.append(campo, erro);
        destino.appendChild(label);
    }
    document.getElementById('operacao-cronograma-detalhes').open = !unica;
}

function renderizarPlanilhaSemestral(destino, planilha) {
    const formatador = new Intl.NumberFormat('pt-BR', {style: 'currency', currency: planilha.moeda,
        minimumFractionDigits: 2, maximumFractionDigits: 2});
    const moeda = valor => formatador.format(valor);
    const data = valor => valor.split('-').reverse().join('/');
    const colunas = ['Liberações', 'Amortização', 'Juros', 'Comissão', 'Juros + comissão', 'Serviço'];
    const valores = linha => ['liberacao', 'amortizacao', 'juros_financeiros', 'comissao_credito', 'juros', 'total'].map(chave => moeda(linha[chave]));

    function adicionarTabela(titulo, cabecalhos, linhas, aberta) {
        const detalhes = document.createElement('details');
        detalhes.className = destino.closest('#resumo-operacao') ? 'limite-memoria' : 'servico-exercicio-detalhes';
        detalhes.open = aberta;
        const summary = document.createElement('summary');
        summary.textContent = titulo;
        const rolagem = document.createElement('div');
        rolagem.className = 'tlp-tabela-rolagem';
        const tabela = document.createElement('table');
        tabela.className = 'tlp-tabela';
        const cabecalho = tabela.createTHead().insertRow();
        for (const nome of cabecalhos) {
            const th = document.createElement('th');
            th.scope = 'col';
            th.textContent = nome;
            cabecalho.append(th);
        }
        const corpo = tabela.createTBody();
        for (const linha of linhas) {
            const tr = corpo.insertRow();
            if (linha[0] === 'Totais') tr.className = 'resumo-operacao-totais';
            for (const celula of linha) tr.insertCell().textContent = celula;
        }
        rolagem.append(tabela);
        detalhes.append(summary, rolagem);
        destino.append(detalhes);
    }

    adicionarTabela(`Resumo da planilha · ano de início do semestre (${planilha.moeda})`, ['Ano', ...colunas],
        [...planilha.anuais.map(linha => [linha.ano, ...valores(linha)]), ['Totais', ...valores(planilha.totais)]], true);
    adicionarTabela('Memória da planilha por semestre', ['Início', 'Vencimento', 'Dias', 'Saldo inicial', ...colunas, 'Saldo final'],
        planilha.semestres.map(linha => [data(linha.inicio), data(linha.fim), linha.dias, moeda(linha.saldo_inicial),
            ...valores(linha), moeda(linha.saldo_final)]), false);
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
    const taxa=typeof CambioUI!=='undefined'?Number(CambioUI.referenciaEntrada().taxa_brl):1;
    if(!(taxa>0))return null;
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
        document.getElementById('operacao-cotacao-contrato').value = '';
        atualizarRotuloMoedaContrato(); montarLiberacoesCompartilhadas();
    });
    document.getElementById('operacao-atualizar-taxa').addEventListener('click', consultarTaxaOperacao);
    document.getElementById('operacao-taxa-indexador').addEventListener('input', () => {
        const valor = document.getElementById('operacao-taxa-indexador').value;
        if (!referenciaTaxaIndexador || Number(valor) !== Number(referenciaTaxaIndexador.valor)) document.getElementById('operacao-taxa-fonte').textContent = 'Taxa informada manualmente · constante nesta simulação';
    });
    atualizarIndexadorOperacao(false);
    document.getElementById('form-simulacao').addEventListener('input', (evento) => {
        if(evento.target.id==='moeda-entrada')return;
        if(evento.target.id!=='limites-cobertura') document.getElementById('limites-cobertura').checked=false;
        window.resumoOperacaoAtual = null;
        document.getElementById('resumo-operacao').hidden = true;
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
    for (const id of ['operacao-tipo-liberacao', 'operacao-periodicidade-liberacao']) {
        document.getElementById(id).addEventListener('change', () => {
            document.getElementById('periodicidade-liberacao-campo').hidden = tipoLiberacaoOperacao() === 'unica';
            atualizarModeloContratual();
            montarLiberacoesCompartilhadas();
            atualizarContextoOperacao();
        });
    }
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
/* Resumo somente de valores devolvidos pelo backend: não calcula novos limites. */
function renderizarResumoOperacao(calculo) {
    window.resumoOperacaoAtual = calculo;
    const destino = document.getElementById('resumo-operacao');
    destino.replaceChildren(); destino.hidden = false;
    const criar = (tag, texto, classe) => {
        const no = document.createElement(tag); no.textContent = texto ?? '';
        if (classe) no.className = classe;
        return no;
    };
    const moeda = valor => valor == null ? 'Não disponível' : formatarMoeda(valor);
    const fluxo = calculo.fluxo || {};
    const bloco = criar('section', '', 'painel-box limite-detalhe-fixo');
    bloco.setAttribute('aria-labelledby', 'resumo-operacao-titulo');
    const cabecalhoResumo = criar('header', '', 'limite-detalhe-cabecalho');
    const tituloResumo = criar('h3', 'Resumo da operação');
    tituloResumo.id = 'resumo-operacao-titulo';
    cabecalhoResumo.append(tituloResumo);
    const conteudo = criar('div', '', 'limite-detalhe-conteudo');
    bloco.append(cabecalhoResumo, conteudo);
    destino.append(bloco);

    const resumo = criar('div', '', 'margem-resumo-visual');
    const destaque = criar('div', '', 'margem-valor-principal');
    destaque.append(criar('span', 'Total de pagamentos'), criar('strong', moeda(fluxo.pagamento_total)));
    if (fluxo.data_final) destaque.append(criar('span', `Último pagamento em ${fluxo.data_final.split('-').reverse().join('/')}`, 'limite-referencia-curta'));
    const componentes = criar('div', '', 'margem-componentes');
    for (const [titulo, valor] of [['Principal amortizado', fluxo.amortizacao_total], ['Juros e encargos', fluxo.juros_total]]) {
        const linha = criar('div');
        linha.append(criar('span', titulo), criar('strong', moeda(valor)));
        componentes.append(linha);
    }
    resumo.append(destaque, componentes);
    conteudo.append(resumo);

    const premissas = criar('details', '', 'limite-memoria');
    premissas.append(criar('summary', 'Ver premissas e composição dos pagamentos'));
    if (fluxo.modo === 'anual_informado') premissas.append(criar('p', `Cronograma anual informado · último ano de pagamento: ${fluxo.ano_final}. Os juros e encargos já estão incluídos nos valores declarados.`, 'painel-help'));
    if (fluxo.saldo_final != null) premissas.append(criar('p', `Saldo final: ${moeda(fluxo.saldo_final)}`, 'painel-help'));
    if (fluxo.modo === 'contratual') {
        premissas.append(criar('p', `${fluxo.quantidade_amortizacoes} amortizações · ${fluxo.quantidade_pagamentos_juros} pagamentos de juros`, 'painel-help'),
            criar('p', `Comissão sobre saldo não desembolsado: ${moeda(fluxo.comissao_credito_total)} · Outros encargos: ${moeda(fluxo.outros_encargos_total)}`, 'painel-help'));
    }
    if(fluxo.datas_contratuais) {
        const d=fluxo.datas_contratuais,fmt=v=>v.split('-').reverse().join('/');
        premissas.append(criar('p',`Assinatura prevista: ${fmt(d.assinatura)} · Vigência prevista: ${fmt(d.vigencia)} · Primeira amortização: ${fmt(d.primeira_amortizacao)} · Início da comissão: ${fmt(d.inicio_comissao)}`, 'painel-help'));
    }
    if (fluxo.convencao) premissas.append(criar('p', fluxo.convencao, 'painel-help'));
    const cambio = calculo.cotacao_entrada || fluxo.cotacao_entrada;
    if (cambio?.constante) {
        const nota = criar('p', `Cotação contratual fixa: 1 ${cambio.moeda} = R$ ${String(cambio.taxa_brl).replace('.', ',')}`, 'painel-help');
        nota.dataset.moedaContratual = 'true'; premissas.append(nota);
    }
    const regras = calculo.analise?.regras_ordenadas || [...(calculo.analise?.regras_cumpridas || []), ...(calculo.analise?.regras_violadas || []), ...(calculo.analise?.regras_sem_informacao || [])];
    const caed = regras.find(regra => regra.tipo === 'servico_divida')?.dados_calculados;
    const recorte = caed?.recorte_sadipem;
    const medias = [];
    if (caed?.media_termino != null) medias.push(`Média até o término: ${formatarPercentual(caed.media_termino)}`);
    if (caed?.media_2027 != null) medias.push(`Média até 2027: ${formatarPercentual(caed.media_2027)}`);
    if (caed?.percentual_determinante != null) medias.push(`Média utilizada: ${formatarPercentual(caed.percentual_determinante)} · Limite: 11,5%`);
    if (medias.length) premissas.append(criar('p', medias.join(' · '), 'painel-help'));
    premissas.append(criar('p', caed?.cobertura?.completa ? 'Cobertura dos pagamentos confirmada conforme a fonte indicada na avaliação.' : 'A avaliação dos limites depende da cobertura dos dados das demais dívidas.', 'limite-ressalva'));
    if (fluxo.planilha) premissas.append(criar('p', `Taxa total da operação: ${fluxo.premissas.taxa_total.replace('.', ',')}% a.a. No Excel, a coluna de juros inclui a comissão.`, 'painel-help'));
    const referencia = calculo.referencia_rcl;
    if (referencia) premissas.append(criar('p', `Base da RCL: ${referencia.exercicio} · ${referencia.periodo}º bimestre · ${referencia.origem || 'SICONFI/RREO'} · Projeção: parâmetro informado na simulação.`, 'painel-help'));
    conteudo.append(premissas);
    if (fluxo.planilha) {
        renderizarPlanilhaSemestral(conteudo, fluxo.planilha);
    } else if (['IPCA', 'TLP'].includes(fluxo.indexador) && fluxo.linhas?.length) {
        const fcl = criar('details', '', 'limite-memoria');
        const conteudo = criar('div');
        fcl.append(criar('summary', 'Planilha FCL · liberação única'), conteudo);
        renderizarFluxoTlp(fluxo, conteudo);
        conteudo.append(fcl);
    }
    const memoria = criar('details', '', 'limite-memoria');
    memoria.open = !fluxo.planilha;
    memoria.append(criar('summary', fluxo.planilha ? 'Fluxo fiscal anual · pagamentos pelo ano de vencimento' : 'Fluxo anual: recebimentos e pagamentos'));
    if (recorte) memoria.append(criar('p', `CAED/RCL até ${recorte.ano_final}: ${formatarPercentual(recorte.media)} · ${recorte.dentro_do_limite ? 'Dentro do limite' : 'Acima do limite'} no período informado.`, 'painel-help'));
    const rolagem = criar('div', '', 'tlp-tabela-rolagem');
    const tabela = criar('table', '', 'tlp-tabela');
    const cabecalho = tabela.createTHead().insertRow();
    for (const titulo of ['Ano', 'Recebimentos da operação', 'Pagamentos da operação', 'Demais dívidas', 'Pagamentos totais', 'RCL projetada', 'CAED/RCL']) {
        const th = criar('th', titulo); th.scope = 'col'; cabecalho.append(th);
    }
    const corpo = tabela.createTBody();
    const anuais = new Map((fluxo.anuais || []).map(linha => [Number(linha.ano), linha]));
    const composicao = new Map((caed?.linhas || []).map(linha => [Number(linha.ano), linha]));
    for (const base of calculo.bases_fluxo || []) {
        if (recorte && base.ano > recorte.ano_final) continue;
        const anual = anuais.get(Number(base.ano));
        const linha = composicao.get(Number(base.ano));
        const tr = corpo.insertRow();
        for (const valor of [base.ano, moeda(base.liberacaoNovaOperacao), moeda(anual?.total), moeda(linha?.demais_operacoes), moeda(linha?.caed_total), moeda(linha?.rcl_projetada ?? base.rclProjetada), linha?.percentual == null ? 'Não disponível' : formatarPercentual(linha.percentual * 100)]) tr.insertCell().textContent = valor;
    }
    if (recorte) {
        const tr = corpo.insertRow();
        tr.className = 'servico-restante';
        for (const valor of ['Restante a pagar', '—', moeda(recorte.nova_operacao_restante), moeda(recorte.demais_operacoes_restantes), '—', '—', '—']) tr.insertCell().textContent = valor;
    }
    rolagem.append(tabela); memoria.append(rolagem); conteudo.append(memoria);
    if (calculo.resumo_limites) renderizarLimitesCenario(conteudo, calculo.resumo_limites);
    conteudo.append(criar('p', 'Simulação indicativa, sujeita à análise da operação.', 'limite-ressalva'));
}

function usaModeloContratual() {
    return !['IPCA','TLP'].includes(document.getElementById('operacao-indexador').value);
}
function usaCalendarioFixo() {
    return usaModeloContratual() && tipoLiberacaoOperacao() === 'cronograma';
}
function tipoLiberacaoOperacao() {
    return document.getElementById('operacao-tipo-liberacao').value === 'fracionada'
        ? document.getElementById('operacao-periodicidade-liberacao').value : 'unica';
}
function usaPlanilhaSemestral() {
    return tipoLiberacaoOperacao() === 'semestral';
}
function deslocarDataContrato(texto,meses) {
    const [ano,mes,dia]=texto.split('-').map(Number),indice=ano*12+mes-1+meses;
    const a=Math.floor(indice/12),m=indice%12+1;
    return `${a}-${String(m).padStart(2,'0')}-${String(Math.min(dia,new Date(Date.UTC(a,m,0)).getUTCDate())).padStart(2,'0')}`;
}
function datasCalendarioAnual(liberacao) {
    const vigencia = document.getElementById('data-vigencia').value || liberacao;
    const periodicidade = Number(document.getElementById('periodicidade-juros').value);
    const prazo = Number(document.getElementById('tlp-prazo').value);
    const carencia = Number(document.getElementById('tlp-carencia').value);
    return {
        data_assinatura: document.getElementById('data-assinatura').value || liberacao,
        data_vigencia: vigencia,
        primeiro_vencimento_juros: document.getElementById('primeiro-vencimento-juros').value
            || deslocarDataContrato(vigencia, Math.min(periodicidade, prazo, carencia || prazo))
    };
}

let versaoPrevisaoTermino = 0;
let previsaoFcl;
async function atualizarFimContratual() {
    const versao = ++versaoPrevisaoTermino;
    const fixo=usaCalendarioFixo();
    const inicio=document.getElementById('operacao-data-liberacao').value;
    const prazo=Number(document.getElementById('tlp-prazo').value);
    const mensagem=document.getElementById('operacao-termino-calculado');
    const seletor=document.getElementById('ano-fim-contrato');
    function marcarPendente(motivo) {
        mensagem.textContent = motivo;
        seletor.removeAttribute('title');
        if (![...seletor.options].some(o => o.value === '')) seletor.prepend(new Option('A calcular', ''));
        if (seletor.value === '') return;
        seletor.value = '';
        seletor.dispatchEvent(new Event('change', {bubbles: true}));
    }
    if (!inicio) return marcarPendente('Informe a data da primeira liberação para calcular o término.');
    if (Number(inicio.slice(0, 4)) !== Number(document.getElementById('ano').value)) {
        return marcarPendente('A data da primeira liberação deve estar no ano de referência.');
    }
    if (!Number.isInteger(prazo) || prazo <= 0 || prazo > 600) {
        return marcarPendente('Informe os prazos de carência e amortização para calcular o término.');
    }
    const datas = fixo ? datasCalendarioAnual(inicio) : null;
    const nominal=deslocarDataContrato(datas?.data_assinatura ?? inicio,prazo);
    let fim=nominal;
    if(fixo) {
        const primeiro = datas.primeiro_vencimento_juros;
        const periodicidade=Number(document.getElementById('periodicidade-juros').value);
        if (datas.data_assinatura.slice(0, 4) !== inicio.slice(0, 4)) {
            return marcarPendente('A data de assinatura deve estar no ano de referência.');
        }
        if (datas.data_assinatura > datas.data_vigencia || datas.data_vigencia > inicio) {
            return marcarPendente('Confira a ordem das datas de assinatura, vigência e primeira liberação.');
        }
        if (primeiro <= datas.data_vigencia || primeiro > nominal || primeiro > deslocarDataContrato(datas.data_vigencia, periodicidade)) {
            return marcarPendente('Confira o primeiro vencimento de juros e a periodicidade nas condições abaixo.');
        }
        for(let n=0;n<=600;n++) {
            const data=deslocarDataContrato(primeiro,n*periodicidade);
            if(data>nominal)break;
            fim=data;
        }
    } else if (!usaModeloContratual()) {
        const carencia = document.getElementById('tlp-carencia').value;
        const chave = `${inicio}:${prazo}:${carencia}`;
        if (previsaoFcl?.chave !== chave) {
            marcarPendente('Calculando a data do último pagamento.');
            previsaoFcl = {chave, resposta: Promise.resolve().then(() => eel.prever_termino_fcl_py(inicio, prazo, carencia)())};
        }
        try {
            const resposta = await previsaoFcl.resposta;
            if (versao !== versaoPrevisaoTermino) return;
            if (resposta.status !== 'sucesso') return marcarPendente(resposta.mensagem);
            fim = resposta.fim;
        } catch (_) {
            if (versao === versaoPrevisaoTermino) {
                previsaoFcl = null;
                marcarPendente('Não foi possível calcular o término. Tente simular novamente.');
            }
            return;
        }
    }
    const fimAno=Number(fim.slice(0,4));
    if(![...seletor.options].some(o=>o.value===String(fimAno))) seletor.add(new Option(String(fimAno),String(fimAno)));
    if(seletor.value!==String(fimAno)) {seletor.value=String(fimAno);seletor.dispatchEvent(new Event('change',{bubbles:true}));}
    seletor.title=`Último pagamento: ${fim.split('-').reverse().join('/')}`;
    mensagem.textContent=seletor.title+(fixo?` · Prazo nominal: ${nominal.split('-').reverse().join('/')}`:'');
}
const encargosOperacao = new Map();
function montarOutrosEncargos() {
    const destino=document.getElementById('operacao-outros-encargos');
    for(const campo of destino.querySelectorAll('input')) encargosOperacao.set(Number(campo.dataset.ano),guardarValorEntrada(campo));
    destino.replaceChildren();
    const inicio=Number(document.getElementById('ano').value),fim=Number(document.getElementById('ano-fim-contrato').value);
    if(!inicio || fim<inicio || fim-inicio>50) return;
    const anos=new Set(encargosOperacao.keys());for(let a=inicio;a<=fim;a++)anos.add(a);
    for(const a of [...anos].sort((a,b)=>a-b)) {
        const label=document.createElement('label');label.hidden=a<inicio||a>fim;label.textContent=`Outros encargos de ${a} (${typeof CambioUI!=='undefined'?CambioUI.referenciaEntrada().moeda:'BRL'})`;
        const campo=document.createElement('input');campo.type='number';campo.min='0';campo.step='.01';campo.dataset.ano=a;campo.dataset.ativo=String(a>=inicio&&a<=fim);restaurarValorEntrada(campo,encargosOperacao.get(a),'0');label.append(campo);destino.append(label);
    }
}
function atualizarMetodoSofr() {
    const sofr = usaModeloContratual() && indexadorDeJuros() === 'SOFR';
    document.getElementById('metodo-sofr-campo').hidden = !sofr;
    const composta = sofr && document.getElementById('metodo-sofr').value === 'composta_projetada';
    const base = document.getElementById('base-juros');
    if (composta) base.value = '360';
    if (sofr && !composta && base.disabled) base.value = '365';
    base.disabled = composta;
    if (sofr) {
        document.getElementById('operacao-premissas-indexador').textContent = composta
            ? 'SOFR overnight constante com composição diária em base 360. A taxa fixa adicional e os spreads são calculados como juros simples.'
            : 'Taxa total = SOFR + taxa fixa adicional + spreads de captação e de capital. Os juros simples aplicam essa taxa ao saldo desembolsado, proporcionalmente aos dias e à base escolhida.';
    }
}
function atualizarModeloContratual() {
    const contratual=usaModeloContratual(),fixo=usaCalendarioFixo();
    const semestral = usaPlanilhaSemestral();
    document.getElementById('calendario-etapas').hidden=!fixo;
    document.querySelector('label[for="operacao-data-liberacao"]').textContent=fixo?'Data da primeira liberação':'Data de início / primeira liberação';
    document.querySelector('label[for="tlp-prazo"]').textContent=fixo?'Prazo total nominal (meses)':'Prazo total (meses)';
    document.getElementById('convencao-contratual-ajuda').textContent=fixo?'Prazo final contado da assinatura; carência contada da vigência. Primeira e última amortizações ajustadas ao vencimento de juros anterior quando necessário. Comissão após os dias informados. Liberações anuais seguintes no dia 15 do mês escolhido. Taxas são premissas constantes de projeção.':'Amortização e juros nas datas de aniversário da primeira liberação. Comissão desde o início. Taxas constantes no cenário.';
    document.getElementById('operacao-condicoes-contratuais').hidden=!contratual;
    document.getElementById('mes-liberacoes').parentElement.hidden = !fixo;
    for (const id of ['periodicidade-amortizacao', 'periodicidade-juros', 'base-juros']) document.getElementById(id).parentElement.hidden = semestral;
    document.getElementById('operacao-encargos-detalhes').hidden = semestral;
    document.getElementById('tlp-carencia').step=semestral?'6':contratual?'1':'3';
    document.getElementById('carencia-ajuda').textContent=contratual?'Meses até a primeira amortização.':'Múltiplos de 3 meses no modelo FCL.';
    if(contratual) {
        document.getElementById('operacao-premissas-indexador').textContent='Taxas fixas, CDI e Selic em fatores efetivos compostos. Taxas constantes no cenário.';
        document.getElementById('premissas-periodicidade').textContent='Juros e amortizações seguem suas próprias periodicidades. A primeira amortização ocorre ao final da carência; sem carência, ao final do primeiro período. O término é calculado pela data de início e pelo prazo total.';
    } else document.getElementById('premissas-periodicidade').textContent='Modelo FCL: juros trimestrais na carência e amortizações mensais a partir do mês final da carência.';
    atualizarMetodoSofr();
    if (semestral) {
        document.getElementById('metodo-sofr-campo').hidden = true;
        document.getElementById('convencao-contratual-ajuda').textContent = 'Juros simples em base 365 e comissão semestral sobre o saldo a liberar.';
        document.getElementById('operacao-premissas-indexador').textContent = 'Juros sobre o saldo desembolsado, incluindo a liberação na abertura do semestre. A taxa total soma SOFR, taxa fixa adicional e spreads.';
    }
    atualizarFimContratual();montarOutrosEncargos();
}
document.addEventListener('DOMContentLoaded',()=>{
    document.getElementById('operacao-data-liberacao').addEventListener('input', () => {
        if (usaPlanilhaSemestral()) montarLiberacoesCompartilhadas();
    });
    document.getElementById('metodo-sofr').addEventListener('change', atualizarMetodoSofr);
    for(const id of ['operacao-data-liberacao','data-assinatura','data-vigencia','primeiro-vencimento-juros','periodicidade-juros']) document.getElementById(id).addEventListener('input',atualizarFimContratual);
    document.getElementById('ano').addEventListener('change', atualizarFimContratual);
    document.getElementById('liberacoes-preencher-zero').addEventListener('click',()=>{
        const campos=[...document.querySelectorAll('#operacao-liberacoes input[data-ativo="true"]')];
        const vazios = campos.filter(campo => campo.value.trim() === '');
        const zero = normalizarValorMonetario('0').formatado;
        for (const campo of vazios) campo.value = zero;
        vazios[0]?.dispatchEvent(new Event('input', {bubbles: true}));
    });
    for(const id of ['ano','ano-fim-contrato']) document.getElementById(id).addEventListener('change',montarOutrosEncargos);
    atualizarModeloContratual();
});

const valoresDemaisLimites = new Map();
function montarComplementoLimites() {
    const destino=document.getElementById('limites-demais-liberacoes');
    for(const c of destino.querySelectorAll('input')) valoresDemaisLimites.set(Number(c.dataset.ano),c.value);
    destino.replaceChildren();
    const inicio=Number(document.getElementById('ano').value),fim=Number(document.getElementById('ano-fim-contrato').value);
    if(!inicio || fim<inicio || fim-inicio>50)return;
    for(let ano=inicio;ano<=fim;ano++) {
        const label=document.createElement('label');label.textContent=`Demais liberações de ${ano} (R$)`;
        const campo=document.createElement('input');campo.type='number';campo.min='0';campo.step='.01';campo.dataset.ano=ano;campo.value=valoresDemaisLimites.get(ano)??'';label.append(campo);destino.append(label);
    }
    aplicarHipoteseLimites();
}
function aplicarHipoteseLimites() {
    const usar=document.getElementById('limites-cenario-isolado').checked;
    for(const c of document.querySelectorAll('#limites-outras-dcl, #limites-demais-liberacoes input')) {
        if(usar && c.value==='') {c.value='0';c.dataset.zeroCenario='true';}
        else if(!usar && c.dataset.zeroCenario && c.value==='0') {c.value='';delete c.dataset.zeroCenario;}
    }
}
function obterComplementoLimites() {
    const dcl=document.getElementById('limites-outras-dcl');
    if(!dcl.validity.valid) throw new Error('Informe um valor não negativo para outras operações da DCL.');
    const entrada={outras_operacoes_dcl_brl:dcl.value===''?null:dcl.value,demais_liberacoes_brl:{},fonte:document.getElementById('limites-fonte').value.trim(),cobertura:document.getElementById('limites-cobertura').checked};
    for(const campo of document.querySelectorAll('#limites-demais-liberacoes input')) {
        if(!campo.validity.valid) throw new Error('Informe valores não negativos para as demais liberações.');
        entrada.demais_liberacoes_brl[campo.dataset.ano]=campo.value===''?null:campo.value;
    }
    if(entrada.cobertura && !entrada.fonte) throw new Error('Informe a fonte antes de confirmar a cobertura das demais operações.');
    return entrada;
}
document.addEventListener('DOMContentLoaded',()=>{
    for(const id of ['ano','ano-fim-contrato']) document.getElementById(id).addEventListener('change',montarComplementoLimites);
    document.getElementById('limites-cenario-isolado').addEventListener('change',aplicarHipoteseLimites);
    montarComplementoLimites();
});

function renderizarLimitesCenario(destino, limites) {
    const criar=(tag,texto)=>{const n=document.createElement(tag);n.textContent=texto??'';return n;};
    const moeda=v=>v==null?'Não disponível':formatarMoeda(v);
    const percentual=v=>v==null?'Não disponível':formatarPercentual(v);
    const mga=limites.mga,dcl=limites.dcl;
    const detalhes=criar('details');detalhes.className='limite-memoria';
    detalhes.append(criar('summary','Liberações anuais · MGA/RCL · limite de 16%'));
    detalhes.append(criar('p',mga.observacao));
    const rolagem=criar('div');rolagem.className='tlp-tabela-rolagem';
    const t=criar('table');t.className='tlp-tabela';const h=t.createTHead().insertRow();
    for(const titulo of ['Ano','Nova operação','Demais liberações','Total','Teto de 16%','MGA/RCL','Nova operação/RCL']) {const th=criar('th',titulo);th.scope='col';h.append(th);}
    const b=t.createTBody();
    for(const l of mga.linhas) {const tr=b.insertRow();for(const v of [l.ano,moeda(l.nova_operacao),moeda(l.demais_liberacoes),moeda(l.total),moeda(l.teto),percentual(l.percentual),percentual(l.percentual_nova_operacao)]) tr.insertCell().textContent=v;}
    rolagem.append(t);detalhes.append(rolagem);
    detalhes.append(criar('p',mga.anos_acima.length?`Total conhecido acima de 16% nos anos: ${mga.anos_acima.join(', ')}.`:mga.cobertura_confirmada?'Totais do cenário dentro do limite de 16%. Cobertura declarada conforme a fonte informada.':'Conjunto das demais liberações não confirmado. O percentual isolado da nova operação não comprova atendimento ao limite total.'));
    destino.append(detalhes);
    const estoque=criar('details');estoque.className='limite-memoria';
    estoque.append(criar('summary','Estoque com a nova operação · cenário DCL/RCL · limite de 200%'));
    const dl=criar('dl');dl.className='resumo-dcl-cenario';
    for(const [label,valor] of [['DCL publicada',moeda(dcl.dcl_publicada)],['RCL do mesmo RGF',moeda(dcl.rcl)],['Nova operação integral',moeda(dcl.principal)],['Outras operações informadas',moeda(dcl.outras_operacoes)],['Saldo do cenário',moeda(dcl.total)],['DCL/RCL do cenário',percentual(dcl.percentual)]]) {dl.append(criar('dt',label),criar('dd',valor));}
    estoque.append(dl,criar('p',`${dcl.memoria_exata.ano} · ${dcl.memoria_exata.periodo??'?'}º quadrimestre · ${dcl.memoria_exata.fonte}`),criar('p',dcl.observacao));
    estoque.append(criar('p',dcl.resultado_numerico?`${dcl.resultado_numerico} no cenário. ${dcl.cobertura_confirmada?'Cobertura declarada pelo usuário.':'Cobertura das outras operações não confirmada.'}`:'Complete os dados das demais operações ou escolha explicitamente a hipótese sem outras operações para calcular o cenário.'));
    destino.append(estoque);
}

function guardarValorEntrada(campo) {
    return {valor:campo.value,cambioBrl:campo.dataset.cambioBrl,cambioExibido:campo.dataset.cambioExibido,cambioAssinatura:campo.dataset.cambioAssinatura};
}
function restaurarValorEntrada(campo,salvo,padrao) {
    campo.value=typeof salvo==='object'?salvo.valor:salvo??padrao;
    if(typeof salvo==='object') for(const chave of ['cambioBrl','cambioExibido','cambioAssinatura']) if(salvo[chave]!=null)campo.dataset[chave]=salvo[chave];
}
