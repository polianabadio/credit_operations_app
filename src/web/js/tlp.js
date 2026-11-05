/* Exibe a memória calculada pelo backend para a operação compartilhada. */
function renderizarFluxoTlp(dados) {
    window.cambioUltimoTlp = dados;
    const resultado = document.getElementById('tlp-resultado');
    function paragrafo(texto, destino = resultado) {
        const p = document.createElement('p'); p.textContent = texto; destino.appendChild(p); return p;
    }
    function tabela(destino, colunas, linhas) {
        const rolagem = document.createElement('div'); rolagem.className = 'tlp-tabela-rolagem';
        const table = document.createElement('table'); table.className = 'tlp-tabela';
        const thead = table.createTHead(), tr = thead.insertRow();
        for (const titulo of colunas) { const th = document.createElement('th'); th.scope = 'col'; th.textContent = titulo; tr.appendChild(th); }
        const tbody = table.createTBody();
        for (const valores of linhas) { const linha = tbody.insertRow(); for (const valor of valores) linha.insertCell().textContent = valor; }
        rolagem.appendChild(table); destino.appendChild(rolagem);
    }
            resultado.replaceChildren();
            paragrafo(`Total de juros: ${formatarMoeda(dados.juros_total)}. Amortização: ${formatarMoeda(dados.amortizacao_total)}. Total a pagar: ${formatarMoeda(dados.pagamento_total)}.`);
            paragrafo(`Último pagamento: ${dados.data_final.split('-').reverse().join('/')}. Saldo ao final: ${formatarMoeda(dados.saldo_final)}.`);
            if (dados.prazos) paragrafo(`Carência: ${dados.prazos.carencia_meses} meses · Amortização: ${dados.prazos.amortizacao_meses} meses · Prazo total: ${dados.prazos.prazo_total_meses} meses.`);
            const inflacao = !dados.indexador || ['IPCA','TLP'].includes(dados.indexador);
            if (dados.estimado) paragrafo(inflacao ? 'Projeção com IPCA zero nos meses ainda não publicados. As parcelas podem mudar conforme a inflação.' : 'A taxa selecionada foi mantida constante neste cenário; não representa uma previsão de taxas futuras.');
            if (inflacao) paragrafo(`Inflação: ${dados.fonte_ipca}. Consulta em ${dados.consultado_em.replace('T', ' ')}.`);
            if (dados.taxa_indexador) {
                const taxa = dados.taxa_indexador;
                paragrafo(`${taxa.indexador}: ${taxa.valor}% ao ano · ${taxa.origem}${taxa.referencia_api ? ` · referência ${taxa.referencia_api.data} · ${taxa.referencia_api.fonte}` : ''}.`);
            }
            const cambio = dados.cotacao_entrada;
            if (cambio?.constante) {
                const memoria = paragrafo(`Cotação contratual fixa: 1 ${cambio.moeda} = R$ ${Number(cambio.taxa_brl).toLocaleString('pt-BR',{maximumFractionDigits:12})}. Valor original: ${cambio.valor_original} ${cambio.moeda}.`);
                memoria.dataset.moedaContratual = 'true';
            }
            const detalhes = document.createElement('details'), titulo = document.createElement('summary');
            detalhes.className = 'servico-exercicio-detalhes servico-parcelas-detalhes';
            detalhes.open = false;
            titulo.textContent = 'Parcelas e memória de cálculo'; detalhes.appendChild(titulo);
            paragrafo(dados.convencao, detalhes); paragrafo(dados.calendario, detalhes);
            paragrafo('O saldo diminui pelas amortizações. Os juros acumulam entre os pagamentos; a amortização é truncada em centavos e os juros são arredondados em centavos, como no modelo.', detalhes);
            tabela(detalhes, ['Fim do período', 'Saldo inicial', inflacao ? 'Competência IPCA' : 'Referência de juros', inflacao ? 'Índice usado' : 'Taxa do cenário', dados.referencia_juros === 'SOFR' ? 'Dias corridos / base' : 'Dias úteis / base', 'Juros pagos', 'Amortização', 'Saldo final'], dados.linhas.map(l => [l.fim.split('-').reverse().join('/'), formatarMoeda(l.saldo_inicial), inflacao ? l.competencia_ipca : dados.referencia_juros || dados.indexador, inflacao ? `${l.ipca}%${l.ipca_ausente_zero ? ' (sem índice publicado)' : ''}` : l.indice_utilizado || '0% a.a.', dados.referencia_juros === 'SOFR' ? `${l.dias_corridos} / 360` : `${l.dup} / 252`, formatarMoeda(l.juros), formatarMoeda(l.amortizacao), formatarMoeda(l.saldo_final)]));
            resultado.appendChild(detalhes);
}
