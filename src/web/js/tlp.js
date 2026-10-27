/* Exibe a memória calculada pelo backend para a operação compartilhada. */
function renderizarFluxoTlp(dados) {
    const resultado = document.getElementById('tlp-resultado');
    function paragrafo(texto, destino = resultado) {
        const p = document.createElement('p'); p.textContent = texto; destino.appendChild(p);
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
            if (dados.estimado) paragrafo(`Projeção com IPCA zero nos meses ainda não publicados. As parcelas podem mudar conforme a inflação.`);
            paragrafo(`Inflação: ${dados.fonte_ipca}. Consulta em ${dados.consultado_em.replace('T', ' ')}.`);
            const detalhes = document.createElement('details'), titulo = document.createElement('summary');
            detalhes.className = 'servico-exercicio-detalhes servico-parcelas-detalhes';
            detalhes.open = false;
            titulo.textContent = 'Parcelas e memória de cálculo'; detalhes.appendChild(titulo);
            paragrafo(dados.convencao, detalhes); paragrafo(dados.calendario, detalhes);
            paragrafo('O saldo diminui pelas amortizações. Os juros acumulam entre os pagamentos; a amortização é truncada em centavos e os juros são arredondados em centavos, como no modelo.', detalhes);
            tabela(detalhes, ['Fim do período', 'Saldo inicial', 'IPCA do mês', 'Índice usado', 'Dias úteis / base', 'Juros pagos', 'Amortização', 'Saldo final'], dados.linhas.map(l => [l.fim.split('-').reverse().join('/'), formatarMoeda(l.saldo_inicial), l.competencia_ipca, `${l.ipca}%${l.ipca_ausente_zero ? ' (sem índice publicado)' : ''}`, `${l.dup} / ${l.dut}`, formatarMoeda(l.juros), formatarMoeda(l.amortizacao), formatarMoeda(l.saldo_final)]));
            resultado.appendChild(detalhes);
}
