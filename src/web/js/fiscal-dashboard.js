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
    const card = elementoFiscal('article', 'limite-grafico');
    card.dataset.limite = config.chave;
    card.appendChild(elementoFiscal('h3', '', config.chave === 'mga' ? 'Operações de crédito' : config.nome));
    const principal = elementoFiscal('div','limite-grafico-principal');
    if (config.chave === 'mga') {
        const atual = linhaMargemCredito(dado) || linhaMargemPublica(dado);
        card.classList.add(!atual ? 'limite-grafico-indisponivel' : atual.margemEstimada < 0 ? 'limite-grafico-excedido' : 'limite-grafico-atual');
        card.appendChild(elementoFiscal('p','limite-grafico-referencia',atual
            ? `${atual.referenciaPublica ? 'Referência do PVL' : 'Inventário confirmado'} · ${atual.ano}`
            : badgeQualidade(dado,'mga')[0]));
        principal.append(elementoFiscal('span','',atual?.referenciaPublica?'Margem segundo o PVL':'Margem no exercício'),
            elementoFiscal('strong','',atual?formatarMoeda(atual.margemEstimada):'Não determinada'));
        card.append(principal,elementoFiscal('p','limite-grafico-contexto', atual?.referenciaPublica
            ? 'Referência parcial das operações informadas nesse PVL.' : atual
            ? 'Saldo anual antes da nova operação.' : 'Aguardando referência suficiente para calcular a margem.'));
        card.appendChild(elementoFiscal('p','limite-grafico-teto',`Limite anual: ${formatarPercentual(dado.limite)} da RCL projetada`));
        if (atual && atual.margemEstimada < 0) card.appendChild(elementoFiscal('span','limite-grafico-aviso','Saldo negativo'));
        return card;
    }
    const limite = Number(dado.limite);
    const valor = dado.valor == null || !Number.isFinite(Number(dado.valor)) ? null : Number(dado.valor);
    const disponivel = valor !== null && Number.isFinite(limite) && limite > 0;
    const excedido = disponivel && valor > limite;
    card.classList.add(!disponivel ? 'limite-grafico-indisponivel' : excedido ? 'limite-grafico-excedido' : dado.historico ? 'limite-grafico-historico' : 'limite-grafico-atual');
    card.appendChild(elementoFiscal('p','limite-grafico-referencia', dado.historico
        ? `Referência histórica · ${dado.ano}` : referenciaFiscal(dado)));
    principal.append(elementoFiscal('span','',config.sigla),elementoFiscal('strong','',valor===null?'Não disponível':formatarPercentual(valor)));
    card.appendChild(principal);
    const comparacao = elementoFiscal('div','limite-comparacao');
    const trilho = elementoFiscal('div','limite-comparacao-trilho');
    trilho.setAttribute('role','img');
    trilho.setAttribute('aria-label',`${config.sigla}: ${valor===null?'não disponível':formatarPercentual(valor)} da RCL; limite ${formatarPercentual(dado.limite)} da RCL${dado.historico?`, referência histórica de ${dado.ano}`:''}`);
    if (disponivel) {
        const barra = elementoFiscal('span','limite-comparacao-barra');
        barra.style.width = `${Math.max(0,Math.min(100,valor/limite*100))}%`;
        trilho.appendChild(barra);
    }
    const escala = elementoFiscal('div','limite-comparacao-escala');
    escala.append(elementoFiscal('span','','0%'),elementoFiscal('span','',`Limite: ${formatarPercentual(dado.limite)}`));
    comparacao.append(trilho,escala);
    card.append(comparacao,elementoFiscal('p','limite-grafico-contexto','Percentuais sobre a RCL.'));
    if (excedido) card.appendChild(elementoFiscal('span','limite-grafico-aviso','Acima do limite'));
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

function classificacaoVisualCapag(nota) {
    if (['A+', 'A', 'B+', 'B'].includes(nota)) return {classe: 'capag-favoravel', icone: '✓'};
    if (['C', 'D'].includes(nota)) return {classe: 'capag-desfavoravel', icone: '!'};
    return {classe: 'capag-sem-nota', icone: '—'};
}

function seloNotaCapag(nota) {
    const visual = classificacaoVisualCapag(nota);
    return elementoFiscal('span', `fiscal-badge capag-selo ${visual.classe}`,
        `${visual.icone} ${nota && nota !== 'N.D.' ? `Nota ${nota}` : 'Nota indisponível'}`);
}

function criarHistoricoDividaRcl(historico) {
    const card = elementoFiscal('section', 'divida-historico');
    card.append(elementoFiscal('h2', '', 'Evolução da dívida e da receita'),
        elementoFiscal('p', 'painel-help', 'Goiás · Dívida consolidada e Receita Corrente Líquida (RCL) por ano'));
    const serie = [...(historico ?? [])].sort((a,b) => a.ano-b.ano);
    if (!serie.length) {
        card.appendChild(elementoFiscal('p', 'painel-help', 'Histórico ainda não disponível. Atualize os dados do SICONFI.'));
        return card;
    }
    const campos = [
        {chave: 'divida_consolidada', nome: 'Dívida bruta (DC)', classe: 'divida-historico-dc'},
        {chave: 'rcl', nome: 'RCL · últimos 12 meses', classe: 'divida-historico-rcl'}
    ];
    const numero = valor => valor == null || valor === '' || !Number.isFinite(Number(valor)) ? null : Number(valor);
    const legenda = elementoFiscal('div', 'divida-historico-legenda');
    for (const campo of campos) legenda.appendChild(elementoFiscal('span', campo.classe, campo.nome));
    legenda.appendChild(elementoFiscal('span', 'divida-historico-dcl-legenda', 'DCL/RCL · linha · escala à direita'));
    card.appendChild(legenda);
    const valores = serie.flatMap(item => campos.map(c => numero(item[c.chave]))).filter(v=>v!==null);
    const magnitude = Math.max(1, ...valores.map(Math.abs));
    const passo = Math.pow(10, Math.floor(Math.log10(magnitude))) / 2;
    const baixo = Math.floor(Math.min(0,...valores)/passo)*passo;
    const alto = Math.max(passo,Math.ceil(Math.max(0,...valores)/passo)*passo);
    const largura = Math.max(840,serie.length*88+160), inicio = 75, fim = largura-85;
    const y = valor => 305-(valor-baixo)/(alto-baixo)*230;
    const percentuais = serie.map(item=>numero(item.percentual_dcl_rcl)).filter(v=>v!==null);
    const minimoPercentual = Math.floor(Math.min(0,...percentuais)/50)*50;
    const maximoPercentual = Math.max(200,Math.ceil(Math.max(0,...percentuais)/50)*50);
    const yPercentual = valor=>305-(valor-minimoPercentual)/(maximoPercentual-minimoPercentual)*230;
    const unidade = magnitude >= 1e9 ? 1e9 : magnitude >= 1e6 ? 1e6 : 1;
    const numeroCurto = new Intl.NumberFormat('pt-BR',{maximumFractionDigits:1});
    const criar = (tag,atributos,texto) => {
        const el = document.createElementNS('http://www.w3.org/2000/svg',tag);
        for (const [chave,valor] of Object.entries(atributos)) el.setAttribute(chave,String(valor));
        if (texto !== undefined) el.textContent=texto;
        return el;
    };
    const svg = criar('svg',{viewBox:`0 0 ${largura} 365`,class:'divida-historico-svg',role:'group','aria-label':'Colunas de dívida bruta e RCL em reais, eixo esquerdo. Linha DCL/RCL em percentual, eixo direito. Selecione um ano para ver os valores exatos.'});
    svg.appendChild(criar('text',{x:inicio,y:23,class:'divida-historico-eixo'},unidade===1e9?'R$ bilhões':unidade===1e6?'R$ milhões':'R$'));
    for (let i=0;i<=5;i++) {
        const valor=baixo+(alto-baixo)*i/5, py=y(valor);
        svg.append(criar('line',{x1:inicio,x2:fim,y1:py,y2:py,class:'divida-historico-grade'}),
            criar('text',{x:inicio-12,y:py+4,'text-anchor':'end',class:'divida-historico-eixo'},numeroCurto.format(valor/unidade)));
    }
    svg.appendChild(criar('text',{x:largura-10,y:23,'text-anchor':'end',class:'divida-historico-eixo'},'DCL/RCL (%)'));
    for (let i=0;i<=5;i++) {
        const valor=minimoPercentual+(maximoPercentual-minimoPercentual)*i/5;
        svg.appendChild(criar('text',{x:fim+12,y:yPercentual(valor)+4,class:'divida-historico-eixo'},`${numeroCurto.format(valor)}%`));
    }
    const detalhe = elementoFiscal('div','divida-historico-detalhe');
    detalhe.setAttribute('aria-live','polite');
    const mostrar = item => {
        detalhe.replaceChildren();
        detalhe.appendChild(elementoFiscal('strong','divida-historico-referencia',`${item.ano} · ${item.periodo}º quadrimestre${item.parcial?' · parcial':''}`));
        for (const campo of campos) {
            const bloco=elementoFiscal('div');
            const valor=numero(item[campo.chave]);
            bloco.append(elementoFiscal('span','',campo.nome),elementoFiscal('strong','',valor===null?'Não disponível':formatarMoeda(valor)));
            detalhe.appendChild(bloco);
        }
        const proporcao=elementoFiscal('div');
        proporcao.append(elementoFiscal('span','',`DCL / ${item.base_dcl_rcl || 'RCL'}`),elementoFiscal('strong','',numero(item.percentual_dcl_rcl)===null?'Não disponível':formatarPercentual(item.percentual_dcl_rcl)));
        detalhe.appendChild(proporcao);
        svg.querySelectorAll('.divida-historico-ano').forEach(g=>g.setAttribute('aria-pressed',String(Number(g.dataset.ano)===Number(item.ano))));
    };
    serie.forEach((item,i) => {
        const centro=inicio+(i+.5)*(fim-inicio)/serie.length;
        const grupo=criar('g',{class:'divida-historico-ano',role:'button',tabindex:0,'data-ano':item.ano,'aria-pressed':'false',
            'aria-label':`${item.ano}, ${item.periodo}º quadrimestre${item.parcial?', parcial':''}. ${campos.map(c=>`${c.nome}: ${numero(item[c.chave])===null?'não disponível':formatarMoeda(item[c.chave])}`).join('. ')}. DCL/${item.base_dcl_rcl || 'RCL'}: ${numero(item.percentual_dcl_rcl)===null?'não disponível':formatarPercentual(item.percentual_dcl_rcl)}`});
        grupo.appendChild(criar('rect',{x:centro-39,y:34,width:78,height:325,rx:6,class:'divida-historico-selecao'}));
        campos.forEach((campo,j) => {
            const valor=numero(item[campo.chave]),px=centro+(j===0?-25:3);
            if (valor===null) {
                grupo.appendChild(criar('text',{x:px+11,y:y(0)-8,'text-anchor':'middle',class:'divida-historico-eixo'},'N.D.'));
                return;
            }
            const barra=criar('rect',{x:px,y:Math.min(y(valor),y(0)),width:22,height:Math.abs(y(valor)-y(0)),rx:3,class:`divida-historico-barra ${campo.classe}`});
            barra.appendChild(criar('title',{},`${item.ano} · ${campo.nome}: ${formatarMoeda(valor)} · ${item.periodo}º quadrimestre`));
            grupo.append(barra,criar('text',{x:px+11,y:valor>=0?y(valor)-8:y(valor)+14,'text-anchor':'middle',class:`divida-historico-valor ${campo.classe}`},numeroCurto.format(valor/unidade)));
        });
        grupo.appendChild(criar('text',{x:centro,y:341,'text-anchor':'middle',class:'divida-historico-eixo'},`${item.ano}${item.parcial?'*':''}`));
        grupo.addEventListener('click',()=>mostrar(item));
        grupo.addEventListener('focus',()=>mostrar(item));
        grupo.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();mostrar(item);}});
        svg.appendChild(grupo);
    });
    svg.append(criar('line',{x1:inicio,x2:fim,y1:yPercentual(200),y2:yPercentual(200),class:'divida-historico-limite'}),
        criar('text',{x:fim,y:yPercentual(200)-10,'text-anchor':'end',class:'divida-historico-eixo'},'Limite DCL/RCL: 200%'));
    let anterior = null;
    const camadaLinha = criar('g',{class:'divida-historico-camada-dcl'});
    serie.forEach((item,i)=>{
        const valor=numero(item.percentual_dcl_rcl);
        if (valor===null) { anterior=null; return; }
        const px=inicio+(i+.5)*(fim-inicio)/serie.length, py=yPercentual(valor);
        if (anterior && item.ano===anterior.ano+1) camadaLinha.appendChild(criar('path',{
            d:`M ${anterior.x} ${anterior.y} L ${px} ${py}`,class:'divida-historico-linha-dcl'}));
        const ponto=criar('circle',{cx:px,cy:py,r:4.5,tabindex:0,role:'button',class:'divida-historico-ponto-dcl',
            'aria-label':`${item.ano} · DCL/${item.base_dcl_rcl || 'RCL'}: ${formatarPercentual(valor)}`});
        ponto.appendChild(criar('title',{},`${item.ano} · DCL/${item.base_dcl_rcl || 'RCL'}: ${formatarPercentual(valor)} · ${item.periodo}º quadrimestre`));
        ponto.addEventListener('click',()=>mostrar(item));
        ponto.addEventListener('focus',()=>mostrar(item));
        ponto.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();mostrar(item);}});
        const rotulosColunas=campos.map(c=>numero(item[c.chave])).filter(v=>v!==null).map(v=>v>=0?y(v)-8:y(v)+14);
        const deslocamento=[-12,18,-28,34].find(d=>rotulosColunas.every(rotulo=>Math.abs(py+d-rotulo)>14)) ?? 18;
        camadaLinha.append(ponto,criar('text',{x:px,y:py+deslocamento,'text-anchor':'middle',class:'divida-historico-rotulo-dcl'},formatarPercentual(valor)));
        anterior={x:px,y:py,ano:item.ano};
    });
    svg.appendChild(camadaLinha);
    const rolagem=elementoFiscal('div','divida-historico-rolagem');
    rolagem.appendChild(svg);
    card.append(rolagem,detalhe,elementoFiscal('p','divida-historico-nota',
        'SICONFI/RGF · Anexo 02 · Executivo de Goiás. Último quadrimestre disponível de cada ano; * ano sem o 3º quadrimestre. Selecione um ano para ver os valores exatos. Colunas em reais (eixo esquerdo); linha DCL/RCL publicada (eixo direito). Dados ausentes interrompem a linha. Não é a nota CAPAG.'));
    mostrar(serie.at(-1));
    return card;
}

function renderizarResumoOuro(destino, regras, exercicio) {
    destino.replaceChildren();
    const anterior = regras?.[0], atual = regras?.[1];
    const memoria = atual?.dados_calculados;
    const numero = v => v == null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
    const margem = numero(memoria?.limite_disponivel);
    const resumo = elementoFiscal('div','ouro-resumo');
    const principal = elementoFiscal('div',`ouro-margem${margem!==null && margem<0?' ouro-margem-negativa':''}`);
    principal.append(elementoFiscal('span','painel-categoria','Margem estimada no exercício'),
        elementoFiscal('strong','',margem===null?'Dado indisponível':formatarMoeda(margem)));
    if (margem!==null) principal.appendChild(elementoFiscal('p','ouro-formula','Despesas de capital − receitas de crédito previstas'));
    else principal.appendChild(elementoFiscal('p','ouro-formula','Faltam dados para calcular a margem.'));
    resumo.appendChild(principal);
    const componentes = [
        {nome:'Despesas de capital consideradas',valor:numero(memoria?.despesas_capital?.total),classe:'ouro-barra-capital'},
        {nome:'Receitas de crédito previstas',valor:numero(memoria?.operacoes_credito?.total),classe:'ouro-barra-credito'}
    ];
    const grafico = elementoFiscal('div','ouro-comparacao');
    const escala = Math.max(1,...componentes.map(c=>Math.abs(c.valor??0)));
    for (const item of componentes) {
        const linha = elementoFiscal('div','ouro-componente');
        const cabecalho = elementoFiscal('div','ouro-componente-cabecalho');
        const valor = item.valor===null?'Não disponível':formatarMoeda(item.valor);
        cabecalho.append(elementoFiscal('span','',item.nome),elementoFiscal('strong','',valor));
        const trilho = elementoFiscal('div','ouro-componente-trilho');
        trilho.setAttribute('role','img');
        trilho.setAttribute('aria-label',`${item.nome}: ${valor}`);
        if (item.valor!==null) {
            const barra = elementoFiscal('span',item.classe);
            barra.style.width=`${Math.abs(item.valor)/escala*100}%`;
            trilho.appendChild(barra);
        }
        linha.append(cabecalho,trilho); grafico.appendChild(linha);
    }
    resumo.appendChild(grafico); destino.appendChild(resumo);
    const fontes = memoria?.fontes ?? [];
    const periodo = Math.max(...fontes.map(f=>Number(f.periodo)).filter(Number.isFinite));
    destino.appendChild(elementoFiscal('p','ouro-referencia',`${Number.isFinite(periodo)?`${periodo}º bimestre de `:'Exercício '}${atual?.ano??exercicio??'não informado'} · SICONFI/RREO${fontes.length?` · ${[...new Set(fontes.map(f=>f.anexo))].join(', ')}`:''}`));
    const detalhes = elementoFiscal('details','ouro-detalhes-fonte');
    detalhes.append(elementoFiscal('summary','','Ver critérios e fonte'),
        elementoFiscal('p','','Esta margem não representa o valor máximo de uma nova contratação.'),
        elementoFiscal('p','','A Regra de Ouro compara as receitas de operações de crédito com as despesas de capital consideradas no exercício. Neste painel, as receitas usam a previsão atualizada; as despesas incluem investimentos, inversões financeiras e amortização, nas colunas de despesas liquidadas e restos a pagar não processados.'),
        elementoFiscal('p','','A capacidade para uma nova operação também depende dos limites de fluxo, serviço da dívida, estoque da dívida e das características da operação.'));
    if (anterior?.situacao==='Dados insuficientes') detalhes.appendChild(elementoFiscal('p','',`Dados completos do exercício anterior (${anterior.ano}) não foram encontrados para esta verificação.`));
    destino.appendChild(detalhes);
}

function renderizarVisaoFiscal(painel) {
    const capag = painel.capag;
    const indicadores = document.getElementById('painel-indicadores');
    indicadores.replaceChildren();
    const conjunto = elementoFiscal('section', 'capag-conjunto capag-tesouro');
    conjunto.setAttribute('aria-label', 'Capacidade de pagamento e indicadores publicados');
    const visual = classificacaoVisualCapag(capag?.valor);
    const nota = elementoFiscal('article', `painel-indicador capag-destaque ${visual.classe}`);
    const cabecalhoCapag = elementoFiscal('header', 'capag-cabecalho');
    const tituloCapag = elementoFiscal('h2', '', 'Nota CAPAG');
    tituloCapag.id = 'capag-titulo';
    conjunto.setAttribute('aria-labelledby', tituloCapag.id);
    cabecalhoCapag.append(tituloCapag, elementoFiscal('p', 'capag-subtitulo', 'Os entes federativos que obtiverem nota de Capag “A”, “A+”, “B” ou “B+” são elegíveis a obter garantia da União a operações de crédito. Para maiores informações sobre metodologia de análise de Capag, consultar a Portaria MF nº 1.583, de 13 de dezembro de 2023.'));
    nota.setAttribute('aria-label', 'Classificação CAPAG');
    nota.append(seloNotaCapag(capag?.valor), elementoFiscal('strong', '', capag?.valor ?? '—'));
    const faixas = elementoFiscal('div', 'capag-faixas');
    const campos = [
        ['endividamento', 'Indicador I · Endividamento', 'Dívida Consolidada / Receita Corrente Líquida'],
        ['poupanca_corrente', 'Indicador II · Poupança Corrente', 'Despesa Corrente / Receita Corrente Ajustada'],
        ['liquidez_relativa', 'Indicador III · Liquidez Relativa', 'Disponibilidade de caixa e obrigações financeiras / Receita Corrente Líquida']
    ];
    for (const [chave, nome, descricao] of campos) {
        const publicado = capag?.indicadores?.[chave];
        const estado = classificacaoVisualCapag(publicado?.nota);
        const faixa = elementoFiscal('article', `capag-indicador capag-faixa ${estado.classe}`);
        const simbolo = elementoFiscal('span', 'capag-simbolo', estado.icone);
        simbolo.setAttribute('aria-hidden', 'true');
        faixa.append(simbolo, elementoFiscal('p', 'capag-formula', descricao),
            elementoFiscal('h3', '', nome), seloNotaCapag(publicado?.nota),
            elementoFiscal('strong', '', publicado?.valor == null ? 'Dado indisponível' : formatarPercentual(publicado.valor)));
        faixas.appendChild(faixa);
    }
    const ranking = capag?.ranking;
    const rankingVisual = classificacaoVisualCapag(ranking?.replace(/icf$/i, '').toUpperCase());
    const faixaRanking = elementoFiscal('article', `capag-indicador capag-faixa capag-ranking ${rankingVisual.classe}`);
    faixaRanking.append(elementoFiscal('span', 'capag-simbolo', rankingVisual.icone),
        elementoFiscal('p', 'capag-formula', 'Qualidade da informação contábil e fiscal'),
        elementoFiscal('h3', '', 'Ranking da qualidade fiscal'),
        elementoFiscal('strong', '', ranking || 'Não informado nesta publicação'));
    faixas.appendChild(faixaRanking);
    const rodape = elementoFiscal('div', 'capag-rodape');
    rodape.append(elementoFiscal('span', 'painel-card-ref', capag
            ? `${capag.ano_base ? `Ano-base ${capag.ano_base} · ` : ''}${referenciaFiscal(capag)}`
            : 'Sem publicação integrada'));
    conjunto.append(cabecalhoCapag, nota, faixas, rodape);
    if (capag?.observacao) conjunto.appendChild(elementoFiscal('p', 'capag-observacao', capag.observacao));
    indicadores.appendChild(conjunto);
    indicadores.appendChild(criarHistoricoDividaRcl(painel.historico_divida_rcl));

    renderizarResumoOuro(document.getElementById('ouro-teto-dashboard'), painel.regra_ouro, painel.exercicio);
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
