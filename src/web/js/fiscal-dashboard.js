/* Apresentação dos dados fiscais já fornecidos pelo backend. */
const LIMITES_PRINCIPAIS = [
    {chave: 'mga', nome: 'Limite anual de operações de crédito — Fluxo', sigla: 'MGA/RCL', descricao: 'Liberações anuais de operações de crédito em relação à RCL projetada.'},
    {chave: 'caed', nome: 'Serviço da dívida', sigla: 'CAED/RCL', descricao: 'Comprometimento da receita com amortizações, juros e encargos da dívida.'},
    {chave: 'dcl', nome: 'Estoque da dívida', sigla: 'DCL/RCL', descricao: 'Dívida Consolidada Líquida em relação à Receita Corrente Líquida.'}
];

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
            fluxo, sadipem: painel.sadipem, valor: fluxo?.dadosCompletos ? fluxo.percentualMgaRcl : null};
    }
    return publicado ? {...publicado, limite: publicado.limite ?? painel.limites_referencia?.[config.sigla]} :
        {valor: null, limite: painel.limites_referencia?.[config.sigla]};
}

function referenciaFiscal(dado) {
    if (!dado?.ano) return 'Sem período publicado';
    const periodo = dado.periodicidade === 'B' ? 'bimestre' : 'quadrimestre';
    return `${dado.periodo ? `${dado.periodo}º ${periodo} de ` : 'Publicação de '}${dado.ano}${dado.origem ? ` · ${dado.origem}` : ''}`;
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
        resumo('Limite legal', `${formatarPercentual(dado.limite)} da RCL projetada`);
        resumo('Teto de referência · RGF', dado.limiteMonetario == null ? 'Dado indisponível' : formatarMoeda(dado.limiteMonetario));
        card.appendChild(elementoFiscal('p', 'limite-resumo-descricao',
            'Verifica as liberações previstas para cada exercício em relação à RCL projetada.'));
        const [status, classe] = badgeQualidade(dado, 'mga');
        card.appendChild(elementoFiscal('span', `qualidade-badge ${classe}`, status));
        card.appendChild(elementoFiscal('p', 'limite-resumo-nota',
            'O teto do RGF usa a RCL publicada; a verificação do pleito usa a RCL projetada e os cronogramas de liberações.'));
        if (dado.referenciaLimite || dado.referenciaRcl) card.appendChild(elementoFiscal('span', 'painel-card-ref',
            dado.referenciaLimite ? `Limite publicado: ${referenciaFiscal(dado.referenciaLimite)}`
                : `RCL: ${referenciaFiscal({...dado.referenciaRcl, periodicidade: 'B'})}`));
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
        if (dado.sadipem?.statusDadosMga === 'Partial') return ['Dados parciais', 'neutro'];
        const status = dado.fluxo?.status;
        return status === 'dentro_do_limite' ? ['Dentro do limite', 'atual'] :
            status === 'proximo_ao_limite' ? ['Próximo ao limite', 'atencao'] :
            status === 'acima_do_limite' ? ['Acima do limite', 'excedido'] :
            ['Comprometimento não disponível', 'neutro'];
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
        conteudo.append(elementoFiscal('p', 'painel-help',
            `Verifica o montante de liberações previsto para cada exercício em relação à RCL projetada. O limite legal é de ${formatarPercentual(dado.limite)} da RCL.`),
            elementoFiscal('p', 'painel-card-ref', 'Art. 7º, inciso I, da RSF 43/2001'));
        const normativo = elementoFiscal('section', 'fluxo-limite-parte');
        normativo.appendChild(elementoFiscal('h4', '', 'Limite normativo'));
        linha('RCL de referência', dado.fluxo?.rclReferencia == null ? 'Dado indisponível' : formatarMoeda(dado.fluxo.rclReferencia));
        linha('Limite legal', formatarPercentual(dado.limite));
        linha('Teto de referência · RGF', dado.limiteMonetario == null ? 'Dado indisponível' : formatarMoeda(dado.limiteMonetario));
        if (dado.fluxo?.tetoAnual != null) {
            linha('RCL projetada', formatarMoeda(dado.fluxo.rclProjetada));
            linha('Teto anual calculado', formatarMoeda(dado.fluxo.tetoAnual));
        }
        normativo.append(valores, elementoFiscal('p', 'painel-help',
            'Teto de referência = RCL ajustada publicada × 16%. No pleito, teto anual = RCL projetada × 16%.'));
        conteudo.appendChild(normativo);
        const comprometimento = elementoFiscal('section', 'fluxo-limite-parte');
        comprometimento.appendChild(elementoFiscal('h4', '', 'Comprometimento do limite'));
        if (dado.fluxo?.dadosCompletos) {
            const itens = elementoFiscal('div', 'limite-valores');
            for (const [rotulo, valor] of [
                ['Liberações computáveis no exercício', formatarMoeda(dado.fluxo.mga)],
                ['Comprometimento da RCL projetada', formatarPercentual(dado.fluxo.percentualMgaRcl)],
                ['Margem estimada para novas liberações', formatarMoeda(dado.fluxo.margemEstimada)]
            ]) {
                const item = elementoFiscal('div');
                item.append(elementoFiscal('span', '', rotulo), elementoFiscal('strong', '', valor));
                itens.appendChild(item);
            }
            comprometimento.appendChild(itens);
        } else {
            const sadipem = dado.sadipem;
            if (sadipem?.liberacoesContratadasSadipem != null) {
                const itens = elementoFiscal('div', 'limite-valores');
                const item = elementoFiscal('div');
                item.append(elementoFiscal('span', '', 'Liberações previstas de operações contratadas'),
                    elementoFiscal('strong', '', formatarMoeda(sadipem.liberacoesContratadasSadipem)));
                itens.appendChild(item);
                comprometimento.append(itens, elementoFiscal('span', 'qualidade-badge neutro', 'Dados parciais'));
                if (sadipem.percentualContratadoRclReferencia != null) comprometimento.appendChild(
                    elementoFiscal('p', 'painel-help', `${formatarPercentual(sadipem.percentualContratadoRclReferencia)} da RCL publicada de referência; não é o MGA/RCL projetado.`));
                comprometimento.appendChild(elementoFiscal('p', 'painel-help',
                    'O valor representa as liberações previstas de operações já contratadas registradas no snapshot do SADIPEM. Operações ainda não contratadas e uma eventual nova operação também integram o MGA e podem reduzir a margem efetiva.'));
            } else {
                comprometimento.appendChild(elementoFiscal('strong', 'fluxo-indisponivel', 'Comprometimento não disponível'));
                const motivo = sadipem?.motivo;
                comprometimento.appendChild(elementoFiscal('p', 'painel-help',
                    motivo === 'API_ERROR' ? 'A consulta ao SADIPEM falhou. Os dados fiscais do SICONFI permanecem disponíveis.' :
                    motivo === 'NO_PVL' ? 'Nenhum PVL elegível do Estado de Goiás foi encontrado na consulta pública.' :
                    motivo === 'NO_RELEASES_REPORTED' ? 'O snapshot não informou liberações para este exercício. Isso não comprova valor zero.' :
                    motivo === 'NO_DATA' ? 'O PVL selecionado não contém cronograma de liberações contratadas para este exercício; isso não comprova valor zero.' :
                    'A margem efetiva depende dos cronogramas anuais de operações contratadas, não contratadas e da operação analisada.'));
            }
            if (sadipem?.liberacoesNaoContratadasSadipem != null) comprometimento.appendChild(
                elementoFiscal('p', 'painel-help', `Liberações anuais de PVLs não contratados listados no snapshot: ${formatarMoeda(sadipem.liberacoesNaoContratadasSadipem)}. A cobertura integral não foi confirmada.`));
            if (sadipem?.snapshot?.valor != null) {
                const pvl = sadipem.snapshot;
                const moeda = pvl.moeda || 'Moeda não informada';
                const valorPvl = /dólar dos eua|dolar dos eua/i.test(moeda)
                    ? new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'USD'}).format(pvl.valor)
                    : /^real$/i.test(moeda) ? formatarMoeda(pvl.valor)
                    : `${new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 2}).format(pvl.valor)} ${moeda}`;
                const dadosPvl = elementoFiscal('div', 'fluxo-dados-pvl');
                dadosPvl.append(elementoFiscal('strong', '', 'Operação registrada no PVL mais recente'),
                    elementoFiscal('p', '', `${valorPvl} · valor total do pleito, não liberação anual${pvl.finalidade ? ` · ${pvl.finalidade}` : ''}`));
                if (pvl.credor || pvl.tipoOperacao) dadosPvl.appendChild(elementoFiscal('p', 'painel-card-ref',
                    [pvl.tipoOperacao, pvl.credor].filter(Boolean).join(' · ')));
                comprometimento.appendChild(dadosPvl);
            }
            if (sadipem?.snapshot) comprometimento.appendChild(elementoFiscal('p', 'painel-card-ref',
                `SADIPEM · PVL ${sadipem.snapshot.numeroPvl || sadipem.snapshot.idPleito} · ID ${sadipem.snapshot.idPleito} · ${sadipem.snapshot.data || 'data não informada'} · ${sadipem.snapshot.status || 'status não informado'}`));
            if (sadipem?.ultimaReferenciaHistorica) {
                const ref = sadipem.ultimaReferenciaHistorica;
                const historico = elementoFiscal('div', 'fluxo-dados-pvl fluxo-historico');
                historico.append(elementoFiscal('strong', '', `Último cronograma localizado · ${ref.ano} · referência histórica`),
                    elementoFiscal('p', '', `${formatarMoeda(ref.valor)} em liberações contratadas previstas no PVL ${ref.numeroPvl || ref.idPleito}. Esse valor não representa o comprometimento de ${sadipem.ano}.`),
                    elementoFiscal('span', 'painel-card-ref', `SADIPEM · ID ${ref.idPleito} · snapshot de ${ref.dataSnapshot || 'data não informada'}`));
                comprometimento.appendChild(historico);
            }
            comprometimento.appendChild(elementoFiscal('p', 'painel-help', 'A API pública não fornece todos os componentes anuais necessários para afirmar uma margem efetiva.'));
        }
        conteudo.appendChild(comprometimento);
        if (dado.fluxo?.exercicios?.length > 1) {
            const projecao = elementoFiscal('details', 'fluxo-projecao');
            projecao.appendChild(elementoFiscal('summary', '', 'Ver projeção por exercício'));
            for (const item of dado.fluxo.exercicios) projecao.appendChild(elementoFiscal('p', '',
                `${item.ano} · RCL projetada: ${item.rclProjetada == null ? 'não disponível' : formatarMoeda(item.rclProjetada)} · Liberações: ${item.mga == null ? 'não disponíveis' : formatarMoeda(item.mga)} · MGA/RCL: ${item.percentualMgaRcl == null ? 'não disponível' : formatarPercentual(item.percentualMgaRcl)} · Margem: ${item.margemEstimada == null ? 'não disponível' : formatarMoeda(item.margemEstimada)}`));
            conteudo.appendChild(projecao);
        }
        conteudo.appendChild(elementoFiscal('p', 'painel-help fluxo-conclusao',
            'O limite de 16% restringe o montante anual de liberações de operações de crédito em relação à RCL projetada. O teto bruto não representa, isoladamente, a capacidade para novas contratações. A margem efetiva depende das liberações de operações já contratadas, em contratação e da operação analisada.'));
        conteudo.appendChild(elementoFiscal('p', 'painel-card-ref',
            `Fonte da RCL: SICONFI / RREO${dado.referenciaRcl ? ` · ${referenciaFiscal({...dado.referenciaRcl, periodicidade: 'B'})}` : ''} · Comprometimento: ${dado.fluxo?.dadosCompletos ? 'cronogramas informados para todos os grupos' : dado.sadipem ? 'SADIPEM / snapshot consultado' : 'SADIPEM / consulta pendente'}`));
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
        elementoFiscal('p', '', 'A CAPAG resume a capacidade de pagamento do ente e é utilizada, entre outros requisitos, na análise de operações com garantia da União.'),
        elementoFiscal('p', 'capag-aviso', 'A classificação CAPAG, isoladamente, não autoriza a contratação nem determina o valor máximo da operação.'),
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
        card.appendChild(elementoFiscal('p', '', descricao));
        if (complemento) card.appendChild(elementoFiscal('p', 'painel-card-extra', complemento));
        card.appendChild(elementoFiscal('span', 'painel-card-ref', publicado
                ? `${capag.ano_base ? `Ano-base ${capag.ano_base} · ` : ''}Publicação de ${capag.ano} · ${capag.origem}`
                : 'Aguardando publicação CAPAG completa na atualização de dados'));
        indicadores.appendChild(card);
    }

    const mga = dadosLimite(painel, LIMITES_PRINCIPAIS[0]);
    const caed = dadosLimite(painel, LIMITES_PRINCIPAIS[1]);

    const interpretacao = document.getElementById('limites-interpretacao-itens');
    interpretacao.replaceChildren();
    for (const [titulo, texto] of [
        [`Fluxo — ${formatarPercentual(mga.limite)} da RCL`, 'Controla o volume de operações de crédito considerado no exercício.'],
        [`Serviço — ${formatarPercentual(caed.limite)} da RCL`, 'Controla o comprometimento da receita com amortizações, juros e encargos.'],
        ['Estoque — DCL/RCL', 'Controla o nível acumulado de endividamento.']
    ]) {
        const item = elementoFiscal('li');
        item.append(elementoFiscal('strong', '', titulo), elementoFiscal('span', '', texto));
        interpretacao.appendChild(item);
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
    const impedimentos = document.getElementById('fator-limitante-impedimentos');
    impedimentos.replaceChildren();
    for (const config of LIMITES_PRINCIPAIS) {
        const dado = dadosLimite(painel, config);
        const situacao = config.chave === 'mga' && dado.valor == null ? 'cronogramas de liberações não consolidados' :
            dado.historico ? `último dado disponível referente a ${dado.ano}` :
            dado.valor == null ? 'dado atual não encontrado' : 'dado atual disponível';
        impedimentos.appendChild(elementoFiscal('li', '', `${config.sigla}: ${situacao}`));
    }
    document.getElementById('fator-limitante-estado').textContent = 'Não determinável com os dados atuais';
    document.getElementById('fator-limitante-texto').textContent =
        'Não é possível identificar com segurança qual limite é atualmente mais restritivo porque nem todos os indicadores possuem informações atuais e completas.';
    document.getElementById('fator-limitante-conclusao').textContent =
        'Por esse motivo, a aplicação não deve apontar um fator limitante atual com base apenas nos dados disponíveis.';
}
