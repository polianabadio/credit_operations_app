/* Apresentação dos dados fiscais já fornecidos pelo backend. */
const LIMITES_PRINCIPAIS = [
    {chave: 'mga', nome: 'Margem disponível para operações de crédito', sigla: 'Limite de 16%', descricao: 'Saldo anual antes de incluir a nova operação da simulação.'},
    {chave: 'caed', nome: 'Serviço da dívida', sigla: 'CAED/RCL', descricao: 'Comprometimento da receita com amortizações, juros e encargos da dívida.'},
    {chave: 'dcl', nome: 'Estoque da dívida', sigla: 'DCL/RCL', descricao: 'Dívida Consolidada Líquida em relação à Receita Corrente Líquida.'}
];

function resultadoVisualMga(projecao) {
    if (!projecao.dataAvailability) return 'Inconclusivo — faltam dados anuais';
    const excede = (projecao.exceededYears || []).length > 0;
    const resultado = excede ? 'Acima do limite de 16%' : 'Dentro do limite de 16%';
    if (projecao.publicReference) return `${resultado} — segundo os dados do PVL${projecao.parameterValidated === false ? ' e a taxa informada' : ''}`;
    if (!projecao.validatedConclusion) return `${resultado} — cenário parcial ou parâmetro a conferir`;
    return resultado;
}

function criarTabelaMga(projecao) {
    const estado = !projecao.dataAvailability ? 'mga-pendente'
        : (projecao.exceededYears || []).length ? 'mga-excedido' : 'mga-atendido';
    const secao = elementoFiscal('section', `mga-projecao dtp-card ${estado}`);
    secao.appendChild(elementoFiscal('h3', '', resultadoVisualMga(projecao)));
    secao.appendChild(elementoFiscal('p', '', 'Quanto do limite anual de operações de crédito esta contratação utiliza? O teto é 16% da RCL projetada. Dele são descontadas as liberações das demais operações e o valor da nova operação previsto para cada ano.'));
    if (projecao.positionOnly) secao.appendChild(elementoFiscal('p', '', 'Posição atual do inventário cadastrado, sem nova operação.'));
    if (projecao.requestedTotal != null) secao.appendChild(elementoFiscal('p', '',
        `Valor requisitado: ${formatarMoeda(projecao.requestedTotal)}`));
    if (projecao.maxRequestedAmountForSchedule != null) secao.appendChild(elementoFiscal('p', '',
        `Valor máximo pelo MGA/RCL mantendo a distribuição proporcional deste cronograma: ${formatarMoeda(projecao.maxRequestedAmountForSchedule)}. Ano restritivo: ${projecao.capacityRestrictingYear}. Não representa capacidade final de contratação.`));
    const principal = (projecao.rows || []).find(linha => linha.ano === (projecao.criticalYear ?? projecao.ano));
    if (principal) {
        secao.appendChild(elementoFiscal('h4', '', `Composição do limite em ${principal.ano}`));
        const resumo = elementoFiscal('div', 'mga-resumo');
        for (const [rotulo, valor] of [['Teto anual (16% da RCL)', principal.tetoAnual],
            ['Liberações das demais operações', principal.scheduledDisbursements],
            ['Liberação da nova operação', principal.requestedOperation],
            ['Saldo após a nova operação', principal.margemEstimada]]) {
            const item = elementoFiscal('div');
            item.append(elementoFiscal('span', '', rotulo),
                elementoFiscal('strong', '', valor == null ? 'Dado não informado' : formatarMoeda(valor)));
            resumo.appendChild(item);
        }
        secao.appendChild(resumo);
    }
    secao.appendChild(elementoFiscal('p', 'painel-help', 'Saldo = teto anual − demais liberações − nova operação. Saldo negativo indica excesso. Esse saldo pertence ao exercício e não representa, sozinho, o valor máximo de um contrato.'));
    if (projecao.publicReference) secao.appendChild(elementoFiscal('p', 'mga-ressalva',
        'Demais liberações obtidas no SADIPEM/PVL. O resultado usa os valores declarados nesse documento; é necessário conferir se existem operações posteriores ou não incluídas.'));
    else if (!projecao.validatedConclusion && projecao.message) secao.appendChild(elementoFiscal('p', 'mga-ressalva', projecao.message));
    if (projecao.exceededYears.length) secao.appendChild(elementoFiscal('p', 'fluxo-indisponivel',
        `Exercícios não enquadrados: ${projecao.exceededYears.join(', ')}`));
    const rolagem = elementoFiscal('div', 'mga-tabela-rolagem');
    rolagem.tabIndex = 0;
    rolagem.setAttribute('aria-label', 'Projeção anual de MGA/RCL; role para visualizar todas as colunas');
    const tabela = elementoFiscal('table', 'mga-tabela');
    const cabecalho = elementoFiscal('thead');
    const titulos = elementoFiscal('tr');
    for (const titulo of ['Ano', 'RCL projetada', 'Teto anual (16%)', 'Demais liberações', 'Nova operação', 'Total de liberações (MGA)', 'Saldo após a operação']) {
        const th = elementoFiscal('th', '', titulo);
        th.scope = 'col';
        titulos.appendChild(th);
    }
    cabecalho.appendChild(titulos);
    const corpo = elementoFiscal('tbody');
    const moeda = valor => valor == null ? 'Não disponível' : formatarMoeda(valor);
    const percentual = valor => valor == null ? 'Não disponível' : formatarPercentual(valor * 100);
    for (const linha of projecao.rows) {
        const estadoLinha = linha.mga == null ? 'mga-pendente'
            : (projecao.exceededYears || []).includes(linha.ano) ? 'mga-excedido' : 'mga-atendido';
        const tr = elementoFiscal('tr', `${estadoLinha}${linha.ano === projecao.criticalYear ? ' mga-ano-critico' : ''}`);
        for (const texto of [String(linha.ano), moeda(linha.rclProjetada), moeda(linha.tetoAnual),
            moeda(linha.scheduledDisbursements), moeda(linha.requestedOperation),
            moeda(linha.mga), moeda(linha.margemEstimada)]) {
            tr.appendChild(elementoFiscal('td', '', texto));
        }
        const fontes = linha.sources || {};
        tr.title = `${fontes.rclSource || 'RCL sem fonte'} · ${fontes.rclExercise || ''} · período ${fontes.rclReferencePeriod || ''} · ${fontes.scheduledOperationsSource || 'Cobertura não confirmada'}`;
        corpo.appendChild(tr);
    }
    tabela.append(cabecalho, corpo);
    rolagem.appendChild(tabela);
    secao.appendChild(rolagem);
    const memoria = elementoFiscal('details', 'painel-details');
    memoria.appendChild(elementoFiscal('summary', '', 'Fontes e memória de cálculo'));
    const origem = projecao.sources || {};
    memoria.appendChild(elementoFiscal('p', '', 'Base: RSF 43/2001, art. 7º, I, §§ 1º e 6º. A regra considera os ingressos de crédito por exercício. Exceções e dispensas exigem conferência jurídica; a aplicação não as exclui automaticamente.'));
    if (projecao.publicReference) {
        const publica = projecao.publicReference;
        const snapshot = publica.snapshot || {};
        memoria.appendChild(elementoFiscal('p', '', `Liberações segundo o PVL ${snapshot.numeroPvl || snapshot.idPleito || '?'} · referência ${snapshot.data || snapshot.dataProtocolo || 'não informada'} · consulta ${publica.consultadoEm || 'não informada'}. Cobertura integral não confirmada.`));
        for (const motivo of publica.motivos || []) memoria.appendChild(elementoFiscal('p', 'painel-help', motivo));
    }
    const taxa = origem.projectionFactor == null ? 'não informada' :
        `${new Intl.NumberFormat('pt-BR', {maximumFractionDigits:9}).format(origem.projectionFactor * 100)}%`;
    memoria.appendChild(elementoFiscal('p', '', `Taxa anual utilizada na projeção da RCL: ${taxa}. Vigência: ${origem.projectionFactorEffectiveFrom || 'a conferir'}. ${origem.projectionFactorMeaning || ''}. Parâmetro ${origem.projectionFactorValidated ? 'validado' : 'pendente de validação'}.`));
    if (origem.projectionFactorSource?.startsWith('https://')) {
        const link = elementoFiscal('a', 'jornada-link', 'Consultar fonte do parâmetro');
        link.href = origem.projectionFactorSource; link.target = '_blank'; link.rel = 'noopener'; memoria.appendChild(link);
    }
    memoria.appendChild(elementoFiscal('p', '', `Demais liberações: ${projecao.otherDisbursementsState === 'public_snapshot' ? 'valores declarados/listados no PVL, com cobertura parcial' : projecao.otherDisbursementsState === 'assumed_zero' ? 'zero assumido somente para esta hipótese' : projecao.otherDisbursementsState === 'confirmed' ? 'inventário e zeros conhecidos confirmados' : 'dados desconhecidos'}. Operação excluída do inventário para evitar duplicidade: ${projecao.excludedOperationIdentifier || 'nenhuma'}.`));
    for (const linha of projecao.rows) {
        const fonte = linha.sources || {};
        if (fonte.publicReference?.memoria_exata?.fonteZero) memoria.appendChild(elementoFiscal('p', 'painel-help',
            `${linha.ano}: o PVL declara ausência de liberações previstas de operações já contratadas.`));
        memoria.appendChild(elementoFiscal('p', '', `${linha.ano}: RCL base ${moeda(fonte.rclBaseValue)} · ${fonte.rclSource || 'fonte indisponível'} · ${fonte.rclStatement || ''} ${fonte.rclAnnex || ''} · exercício ${fonte.rclExercise || ''} · bimestre ${fonte.rclReferencePeriod || ''} · consulta ${fonte.rclQueriedAt || 'não disponível'} · fator anual ${percentual(fonte.projectionFactor)} · ${fonte.projectionFactorSource || 'fonte do fator indisponível'} · atualização proporcional ${fonte.proportionalMonths ?? '?'} meses. Cobertura: ${fonte.scheduledOperationsSource || 'não confirmada'} · atualização ${fonte.scheduledOperationsUpdatedAt || 'não disponível'}.`));
        for (const op of fonte.operations || []) memoria.appendChild(elementoFiscal('p', 'painel-card-ref',
            `${op.identificador}: ${moeda(op.amount)} · ${op.source} · ${op.updatedAt}`));
    }
    secao.appendChild(memoria);
    return secao;
}

function elementoFiscal(tag, classe, texto) {
    const no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined) no.textContent = texto;
    return no;
}

function situacaoLimite(dado) {
    if (dado?.valor == null || dado?.limite == null || dado.limite <= 0) return {texto: 'Dado indisponível', classe: 'indisponivel'};
    if (dado.historico) return {texto: dado.valor > dado.limite ? 'Histórico · acima do limite' : 'Referência histórica',
        classe: dado.valor > dado.limite ? 'excedido' : 'indisponivel'};
    const uso = dado.valor / dado.limite;
    if (uso > 1) return {texto: 'Limite excedido', classe: 'excedido'};
    if (uso >= 0.9) return {texto: 'Próximo ao limite', classe: 'proximo'};
    if (uso >= 0.7) return {texto: 'Atenção', classe: 'atencao'};
    return {texto: 'Confortável', classe: 'confortavel'};
}

function dadosLimite(painel, config) {
    const publicado = painel[config.chave];
    if (config.chave === 'mga') {
        const fluxo = painel.fluxo_credito;
        return {limite: fluxo?.percentualLimite ?? painel.limites_referencia?.[config.sigla],
            limiteMonetario: fluxo?.tetoReferencia ?? painel.limite_mga_publicado?.valor ?? null,
            referenciaLimite: painel.limite_mga_publicado, referenciaRcl: painel.rcl,
            fluxo, margemPublica: painel.margemPublica, sadipem: painel.sadipem, valor: fluxo?.dataAvailability && fluxo?.parameterValidated !== false ? fluxo.maxMgaRcl * 100 : null};
    }
    return publicado ? {...publicado, limite: publicado.limite ?? painel.limites_referencia?.[config.sigla]} :
        {valor: null, limite: painel.limites_referencia?.[config.sigla]};
}

function referenciaFiscal(dado) {
    if (!dado?.ano) return 'Sem período publicado';
    const periodo = dado.periodicidade === 'B' ? 'bimestre' : 'quadrimestre';
    return `${dado.periodo ? `${dado.periodo}º ${periodo} de ` : 'Publicação de '}${dado.ano}${dado.origem ? ` · ${dado.origem}` : ''}`;
}

function linhaMargemCredito(dado, ano = dado.fluxo?.ano) {
    const fluxo = dado.fluxo;
    if (fluxo?.positionOnly !== true || fluxo.parameterValidated !== true) return null;
    const linha = fluxo.rows?.find(item => item.ano === ano);
    return linha?.dadosCompletos && Number.isFinite(linha.margemEstimada) ? linha : null;
}

function linhaMargemPublica(dado, ano = dado.fluxo?.ano) {
    if (dado.margemPublica?.status !== 'Referência pública') return null;
    const linha = dado.margemPublica.rows?.find(item => item.ano === ano);
    return Number.isFinite(linha?.margemEstimada) ? {...linha, referenciaPublica: true} : null;
}

function criarDetalheMargemCredito(dado) {
    const secao = elementoFiscal('section', 'fluxo-limite-parte margem-credito');
    const atual = linhaMargemCredito(dado) || linhaMargemPublica(dado);
    secao.append(elementoFiscal('h4', '', 'Margem antes da nova operação'),
        elementoFiscal('strong', '', atual ? formatarMoeda(atual.margemEstimada) : 'Margem disponível não determinada'),
        elementoFiscal('p', 'painel-help', 'Margem disponível = teto anual de 16% da RCL projetada − liberações das operações existentes incluídas. O possível empréstimo será acrescentado na Simulação.'),
        elementoFiscal('p', 'painel-card-ref', 'Art. 7º, inciso I, da RSF 43/2001'));
    const rolagem = elementoFiscal('div', 'mga-tabela-rolagem');
    rolagem.tabIndex = 0;
    rolagem.setAttribute('aria-label', 'Margem anual disponível antes da nova operação');
    const tabela = elementoFiscal('table', 'mga-tabela');
    const head = elementoFiscal('tr');
    for (const titulo of ['Ano', 'RCL projetada', 'Teto anual (16%)', 'Liberações existentes incluídas', 'Margem disponível']) head.appendChild(elementoFiscal('th', '', titulo));
    const thead = elementoFiscal('thead'); thead.appendChild(head); tabela.appendChild(thead);
    const corpo = elementoFiscal('tbody');
    const moeda = valor => valor == null ? 'Não disponível' : formatarMoeda(valor);
    if (dado.fluxo?.positionOnly === true) for (const item of dado.fluxo.rows || []) {
        const linha = elementoFiscal('tr');
        const validada = linhaMargemCredito(dado, item.ano) || linhaMargemPublica(dado, item.ano);
        for (const texto of [String(item.ano), moeda(validada?.rclProjetada ?? item.rclProjetada), moeda(validada?.tetoAnual ?? item.tetoAnual), moeda(validada?.scheduledDisbursements ?? item.scheduledDisbursements), validada ? moeda(validada.margemEstimada) : 'Não determinada']) linha.appendChild(elementoFiscal('td', '', texto));
        corpo.appendChild(linha);
    }
    tabela.appendChild(corpo); rolagem.appendChild(tabela); secao.appendChild(rolagem);
    if (!atual) {
        secao.appendChild(elementoFiscal('p', 'painel-help', 'Faltam dados confirmados das liberações existentes ou parâmetro validado. Ausência não significa zero.'));
        for (const motivo of dado.fluxo?.unavailabilityReasons || []) secao.appendChild(elementoFiscal('p', 'painel-help', motivo));
        for (const motivo of dado.margemPublica?.motivos || []) secao.appendChild(elementoFiscal('p', 'painel-help', motivo));
    }
    if (atual?.referenciaPublica) {
        const publica = dado.margemPublica;
        secao.appendChild(elementoFiscal('p', 'painel-card-ref', `Saldo segundo o PVL ${publica.snapshot?.numeroPvl || publica.snapshot?.idPleito} · referência ${publica.snapshot?.data || 'não informada'} · consulta ${publica.consultadoEm || 'não informada'}.`));
        for (const motivo of publica.motivos || []) secao.appendChild(elementoFiscal('p', 'painel-help', motivo));
        if (atual.fonteZero) secao.appendChild(elementoFiscal('p', 'painel-help', `Zero declarado pela fonte: ${atual.fonteZero}.`));
        secao.appendChild(elementoFiscal('p', 'painel-help', `Liberações contratadas declaradas: ${moeda(atual.liberacoesContratadas)} · Não contratadas listadas no PVL: ${moeda(atual.liberacoesNaoContratadasListadas)}.`));
    }
    const fontes = dado.fluxo?.sources || {};
    secao.appendChild(elementoFiscal('p', 'painel-card-ref', `RCL: ${fontes.rclSource || 'fonte não disponível'} · exercício ${fontes.rclExercise || 'não informado'} · bimestre ${fontes.rclReferencePeriod || 'não informado'} · Liberações: ${atual?.referenciaPublica ? 'SADIPEM / declaração do PVL' : fontes.scheduledOperationsSource || 'cobertura não confirmada'}.`));
    const sadipem = dado.sadipem;
    if (sadipem?.liberacoesContratadasSadipem != null) secao.appendChild(elementoFiscal('p', 'painel-help', `Referência pública parcial: ${formatarMoeda(sadipem.liberacoesContratadasSadipem)} em liberações contratadas no PVL ${sadipem.snapshot?.numeroPvl || 'não informado'}. Esse valor não confirma a cobertura integral da margem.`));
    secao.appendChild(elementoFiscal('p', 'painel-help', 'A margem é anual e pode ser negativa. Não representa, isoladamente, o valor total máximo de um contrato.'));
    return secao;
}

function criarResumoLimite(config, dado) {
    const card = elementoFiscal('article', 'limite-resumo');
    const estado = situacaoLimite(dado);
    const resumo = (rotulo, valor) => {
        const linha = elementoFiscal('div', 'limite-resumo-linha');
        linha.append(elementoFiscal('span', '', rotulo), elementoFiscal('strong', '', valor));
        card.appendChild(linha);
    };
    const sigla = elementoFiscal('span', 'limite-resumo-sigla', config.sigla);
    sigla.title = config.descricao;
    if (config.chave === 'mga') {
        card.append(elementoFiscal('h3', '', config.nome), sigla);
        const atual = linhaMargemCredito(dado) || linhaMargemPublica(dado);
        resumo(atual?.referenciaPublica ? 'Margem segundo o PVL' : 'Margem disponível no exercício', atual ? formatarMoeda(atual.margemEstimada) : 'Não determinada');
        resumo('Limite legal', `${formatarPercentual(dado.limite)} da RCL projetada`);
        if (atual) resumo('Exercício', String(atual.ano));
        card.appendChild(elementoFiscal('p', 'limite-resumo-descricao',
            'Saldo do teto anual após as liberações das operações existentes incluídas.'));
        const [status, classe] = badgeQualidade(dado, 'mga');
        card.appendChild(elementoFiscal('span', `qualidade-badge ${classe}`, status));
        if (!atual) card.appendChild(elementoFiscal('p', 'limite-resumo-nota',
            'A margem depende da RCL projetada e da cobertura das demais liberações; o teto bruto não é margem disponível.'));
        return card;
    }
    card.append(elementoFiscal('h3', '', config.nome), sigla);
    if (config.chave === 'caed') {
        if (dado.historico) card.appendChild(elementoFiscal('span', 'limite-badge-historico',
            `Dado histórico — ${dado.ano ?? 'ano não informado'}`));
        resumo(dado.historico ? 'Última referência disponível' : 'Serviço da dívida',
            dado.valor == null ? 'Dado indisponível' : formatarPercentual(dado.valor));
        resumo('Limite', formatarPercentual(dado.limite));
        if (dado.valor != null) resumo(dado.historico ? 'Margem na referência' : 'Margem até o limite',
            `${formatarPercentual(dado.limite - dado.valor)} p.p.`);
        card.appendChild(elementoFiscal('p', 'limite-resumo-descricao',
            'Indica o comprometimento da Receita Corrente Líquida com amortizações, juros e encargos da dívida.'));
        card.appendChild(elementoFiscal('p', 'limite-resumo-descricao',
            'Uma nova operação altera este indicador conforme seu prazo, juros, carência, amortização e cronograma de pagamentos.'));
    } else {
        resumo('DCL em relação à RCL', dado.valor == null ? 'Dado indisponível' : formatarPercentual(dado.valor));
        resumo('Limite legal', `${formatarPercentual(dado.limite)} da RCL`);
        if (dado.valor != null) {
            resumo('Parcela do limite utilizada', formatarPercentual(dado.valor / dado.limite * 100));
            resumo('Margem até o limite', `${formatarPercentual(dado.limite - dado.valor)} p.p.`);
        }
        card.appendChild(elementoFiscal('p', 'limite-resumo-descricao',
            'Mostra o estoque da Dívida Consolidada Líquida em relação à Receita Corrente Líquida.'));
        card.appendChild(elementoFiscal('p', 'limite-resumo-descricao',
            'Esse indicador mede o estoque acumulado de endividamento, diferentemente do limite anual de fluxo de operações de crédito.'));
    }
    const visual = elementoFiscal('div', 'limite-resumo-visual');
    if (dado.valor != null && dado.limite > 0) {
        const uso = dado.valor / dado.limite * 100;
        const usoTexto = dado.historico
            ? `${formatarPercentual(uso)} do limite utilizado na referência histórica de ${dado.ano ?? 'ano não informado'}`
            : `${formatarPercentual(uso)} do limite legal utilizado`;
        visual.appendChild(elementoFiscal('span', 'limite-resumo-dado', usoTexto));
        const trilho = elementoFiscal('div', 'painel-progress-track');
        trilho.setAttribute('role', 'progressbar');
        trilho.setAttribute('aria-label', `${config.nome}: ${usoTexto}`);
        trilho.setAttribute('aria-valuenow', String(Math.max(0, Math.min(100, uso))));
        trilho.setAttribute('aria-valuemin', '0');
        trilho.setAttribute('aria-valuemax', '100');
        const preenchimento = elementoFiscal('span', dado.historico ? 'painel-progress-historico' : estado.classe === 'excedido' ? 'painel-progress-excedido' : '');
        preenchimento.style.width = `${Math.max(0, Math.min(100, uso))}%`;
        trilho.appendChild(preenchimento);
        visual.appendChild(trilho);
    } else {
        visual.appendChild(elementoFiscal('span', 'limite-resumo-dado', 'Utilização não disponível'));
    }
    card.appendChild(visual);
    if (dado.valor != null) card.appendChild(elementoFiscal('span', 'painel-card-ref', referenciaFiscal(dado)));
    return card;
}

function badgeQualidade(dado, chave) {
    if (chave === 'mga') {
        const atual = linhaMargemCredito(dado);
        if (!atual && dado.margemPublica?.status === 'Consultando') return ['Consultando SADIPEM…', 'neutro'];
        if (!atual && linhaMargemPublica(dado)) return ['Referência SADIPEM · conferir cobertura', 'neutro'];
        return atual ? [atual.margemEstimada < 0 ? 'Sem margem · limite excedido' : 'Margem calculada', atual.margemEstimada < 0 ? 'excedido' : 'atual'] : ['Margem não determinada', 'neutro'];
    }
    if (dado.historico) return ['Histórico', 'historico'];
    return dado.valor == null ? ['Incompleto', 'incompleto'] : ['Atual', 'atual'];
}

function criarDetalheLimitePagina(config, dado, exercicioAtual) {
    const bloco = elementoFiscal('article', 'painel-box limite-detalhe limite-detalhe-fixo');
    const [qualidade, classe] = badgeQualidade(dado, config.chave);
    const cabecalho = elementoFiscal('div', 'limite-detalhe-cabecalho');
    cabecalho.append(elementoFiscal('h3', '', config.chave === 'mga' ? config.nome : `${config.sigla} · ${config.nome}`),
        elementoFiscal('span', `qualidade-badge ${classe}`, qualidade));
    if (config.chave === 'dcl' && dado.valor != null) {
        const situacao = situacaoLimite(dado);
        cabecalho.appendChild(elementoFiscal('span', `fiscal-badge ${situacao.classe}`, situacao.texto));
    }
    bloco.appendChild(cabecalho);
    const conteudo = elementoFiscal('div', 'limite-detalhe-conteudo');
    const valores = elementoFiscal('div', 'limite-valores');
    const linha = (rotulo, valor) => {
        const item = elementoFiscal('div');
        item.append(elementoFiscal('span', '', rotulo), elementoFiscal('strong', '', valor));
        valores.appendChild(item);
    };
    if (config.chave === 'mga') {
        conteudo.appendChild(criarDetalheMargemCredito(dado));
    } else {
        linha(dado.historico ? 'Última referência disponível' : config.chave === 'dcl' ? 'DCL/RCL atual' : 'Atual',
            dado.valor == null ? 'Dado indisponível' : formatarPercentual(dado.valor));
        linha(config.chave === 'dcl' ? 'Limite legal' : 'Limite',
            config.chave === 'dcl' ? `${formatarPercentual(dado.limite)} da RCL` : formatarPercentual(dado.limite));
        if (dado.valor != null && dado.limite > 0) {
            const uso = dado.valor / dado.limite * 100;
            linha(dado.historico ? 'Utilização do limite na referência' : 'Parcela do limite utilizada', formatarPercentual(uso));
            linha(dado.historico ? 'Margem na referência' : 'Margem até o limite', `${formatarPercentual(dado.limite - dado.valor)} p.p.`);
            conteudo.appendChild(valores);
            const legenda = `${formatarPercentual(uso)} do limite ${dado.historico ? `utilizado na referência de ${dado.ano}` : 'legal utilizado'}`;
            const barra = elementoFiscal('div', 'painel-progress-track');
            barra.setAttribute('role', 'progressbar');
            barra.setAttribute('aria-label', legenda);
            barra.setAttribute('aria-valuenow', String(Math.max(0, Math.min(100, uso))));
            barra.setAttribute('aria-valuemin', '0');
            barra.setAttribute('aria-valuemax', '100');
            const preenchimento = elementoFiscal('span', dado.historico ? 'painel-progress-historico' : '');
            preenchimento.style.width = `${Math.max(0, Math.min(100, uso))}%`;
            barra.appendChild(preenchimento);
            conteudo.append(elementoFiscal('p', 'painel-progress-label', legenda), barra);
        } else conteudo.appendChild(valores);
        if (dado.historico) conteudo.appendChild(elementoFiscal('p', 'limite-aviso-historico',
            `Este valor é histórico e não deve ser interpretado como a posição atual do exercício de ${exercicioAtual ?? 'referência corrente'}.`));
        conteudo.appendChild(elementoFiscal('p', 'painel-help', config.chave === 'caed'
            ? 'O CAED mede o comprometimento da RCL com amortizações, juros e encargos. O impacto de uma nova operação depende do cronograma de pagamentos, prazo, juros, carência e amortizações.'
            : 'O indicador mostra o estoque da Dívida Consolidada Líquida em relação à Receita Corrente Líquida.'));
        if (dado.valor != null) conteudo.appendChild(elementoFiscal('p', 'painel-card-ref', referenciaFiscal(dado)));
    }
    bloco.appendChild(conteudo);
    return bloco;
}

function renderizarVisaoFiscal(painel) {
    const capag = painel.capag;
    const capagCompativel = capag && ['A+', 'A', 'B+', 'B'].includes(capag.valor);
    const indicadores = document.getElementById('painel-indicadores');
    indicadores.replaceChildren();
    const nota = elementoFiscal('article', 'painel-indicador capag-destaque');
    nota.append(elementoFiscal('span', 'painel-categoria', 'Capacidade de pagamento'),
        elementoFiscal('h2', '', 'CAPAG'),
        elementoFiscal('strong', '', capag ? `Nota ${capag.valor}` : 'Dado indisponível'),
        elementoFiscal('span', `fiscal-badge ${capagCompativel ? 'confortavel' : 'indisponivel'}`,
            capagCompativel ? 'Classificação elegível para análise de garantia da União' : 'Classificação não confirmada para análise de garantia da União'),
        elementoFiscal('p', 'capag-aviso', 'Indicador publicado. Não representa autorização de contratação.'),
        elementoFiscal('span', 'painel-card-ref', capag ? referenciaFiscal(capag) : 'Sem publicação integrada'));
    indicadores.appendChild(nota);
    for (const [chave, nome, descricao, complemento] of [
        ['endividamento', 'Endividamento', 'Indica quanto a dívida consolidada bruta representa em relação à Receita Corrente Líquida.',
            'Quanto menor o comprometimento, maior tende a ser a capacidade fiscal associada a este indicador.'],
        ['poupanca_corrente', 'Poupança Corrente', 'Compara as despesas correntes com as receitas correntes ajustadas e indica a capacidade do ente de gerar poupança.',
            'Quanto menor o comprometimento das receitas correntes com despesas correntes, maior tende a ser a capacidade de geração de poupança.'],
        ['liquidez_relativa', 'Liquidez Relativa', 'Avalia a disponibilidade de caixa em relação às obrigações financeiras exigíveis.',
            'Quanto menor o comprometimento da disponibilidade de caixa, melhor tende a ser a posição de liquidez.']
    ]) {
        const publicado = capag?.indicadores?.[chave];
        const card = elementoFiscal('article', 'painel-indicador');
        card.append(elementoFiscal('span', 'painel-categoria', 'Indicador CAPAG'),
            elementoFiscal('h2', '', nome),
            elementoFiscal('strong', '', publicado?.valor == null ? 'Dado indisponível' : formatarPercentual(publicado.valor)));
        if (publicado?.nota) card.appendChild(elementoFiscal('span', 'fiscal-badge', `Nota ${publicado.nota}`));
        const explicacao = elementoFiscal('details', 'indicador-explicacao');
        explicacao.append(elementoFiscal('summary', '', 'Sobre o indicador'), elementoFiscal('p', '', descricao));
        if (complemento) explicacao.appendChild(elementoFiscal('p', '', complemento));
        card.appendChild(explicacao);
        card.appendChild(elementoFiscal('span', 'painel-card-ref', publicado
                ? `${capag.ano_base ? `Ano-base ${capag.ano_base} · ` : ''}Publicação de ${capag.ano} · ${capag.origem}`
                : 'Aguardando publicação CAPAG completa na atualização de dados'));
        indicadores.appendChild(card);
    }

    const tetoOuro = document.getElementById('ouro-teto-dashboard');
    tetoOuro.replaceChildren();
    const ouroAnterior = painel.regra_ouro?.[0];
    const ouroAtual = painel.regra_ouro?.[1];
    const memoriaOuro = ouroAtual?.dados_calculados;
    const margemOuro = memoriaOuro?.limite_disponivel;
    tetoOuro.appendChild(elementoFiscal('span', 'painel-categoria', 'Margem estimada no exercício'));
    if (margemOuro != null && Number.isFinite(Number(margemOuro))) {
        tetoOuro.appendChild(elementoFiscal('strong', '', formatarMoeda(Number(margemOuro))));
        tetoOuro.appendChild(elementoFiscal('p', 'ouro-aviso',
            'Esta margem não representa o valor máximo de uma nova contratação.'));
        tetoOuro.appendChild(elementoFiscal('p', 'painel-help ouro-explicacao',
            'A Regra de Ouro verifica a relação entre as receitas de operações de crédito e as despesas de capital consideradas no exercício.'));
        tetoOuro.appendChild(elementoFiscal('p', 'painel-help ouro-explicacao',
            'A capacidade efetiva para uma nova operação também depende dos limites de fluxo, serviço da dívida, estoque da dívida e das características financeiras da operação.'));
        const fontesOuro = memoriaOuro.fontes ?? [];
        const periodoOuro = Math.max(...fontesOuro.map(fonte => Number(fonte.periodo)).filter(Number.isFinite));
        tetoOuro.appendChild(elementoFiscal('span', 'painel-card-ref',
            `${Number.isFinite(periodoOuro) ? `${periodoOuro}º bimestre de ` : 'Exercício '}${ouroAtual.ano} · SICONFI/RREO${fontesOuro.length ? ` · ${[...new Set(fontesOuro.map(fonte => fonte.anexo))].join(', ')}` : ''}`));
        if (ouroAnterior?.situacao === 'Dados insuficientes') {
            const fonteAnterior = elementoFiscal('details', 'ouro-detalhes-fonte');
            fonteAnterior.append(elementoFiscal('summary', '', 'Detalhes da fonte'),
                elementoFiscal('p', '', `Dados completos do exercício anterior (${ouroAnterior.ano}) não foram encontrados para esta verificação.`));
            tetoOuro.appendChild(fonteAnterior);
        }
    } else {
        tetoOuro.appendChild(elementoFiscal('strong', '', 'Dado indisponível'));
        tetoOuro.appendChild(elementoFiscal('p', 'painel-help', 'A Regra de Ouro atual não tem dados suficientes para calcular uma margem.'));
    }
    const homeLimites = document.getElementById('home-limites');
    const limitesMeta = document.getElementById('limites-meta');
    const detalhes = document.getElementById('painel-limites');
    for (const no of [homeLimites, limitesMeta, detalhes]) no.replaceChildren();
    const periodoRecente = painel.dtp ?? painel.dcl ?? painel.rcl;
    const meta = [
        painel.exercicio ? `Exercício: ${painel.exercicio}` : null,
        periodoRecente ? `Período mais recente: ${referenciaFiscal(periodoRecente)}` : null,
        painel.ultima_consulta ? `Última consulta: ${new Date(painel.ultima_consulta).toLocaleString('pt-BR')}` : null,
        painel.sadipem ? 'Fontes: SICONFI, SADIPEM e Tesouro Transparente' :
            painel.capag ? 'Fontes: SICONFI e Tesouro Transparente' : 'Fonte: SICONFI'
    ];
    for (const texto of meta.filter(Boolean)) limitesMeta.appendChild(elementoFiscal('span', '', texto));
    for (const config of LIMITES_PRINCIPAIS) {
        const dado = dadosLimite(painel, config);
        homeLimites.appendChild(criarResumoLimite(config, dado));
        detalhes.appendChild(criarDetalheLimitePagina(config, dado, painel.exercicio));
    }

}
