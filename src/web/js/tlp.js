/* Exibe a memória calculada pelo backend para a operação compartilhada. */
function renderizarFluxoTlp(dados, destino) {
    if (!destino) window.cambioUltimoTlp = dados;
    const resultado = destino ?? document.getElementById('tlp-resultado');
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
            if (dados.planilha) {
                renderizarPlanilhaSemestral(resultado, dados.planilha);
                return;
            }
            if (dados.modo === 'contratual') {
                paragrafo(`Principal amortizado: ${formatarMoeda(dados.amortizacao_total)}. Total de pagamentos: ${formatarMoeda(dados.pagamento_total)}. Último pagamento: ${dados.data_final.split('-').reverse().join('/')}.`);
                paragrafo(`Juros sobre o saldo devedor: ${formatarMoeda(dados.juros_financeiros_total)}. Comissão sobre saldo não desembolsado: ${formatarMoeda(dados.comissao_credito_total)}. Outros encargos: ${formatarMoeda(dados.outros_encargos_total)}.`);
                paragrafo(`${dados.quantidade_amortizacoes} amortizações · ${dados.quantidade_pagamentos_juros} pagamentos de juros · Base ${dados.premissas.base_juros} dias. Taxas constantes neste cenário.`);
                if(dados.datas_contratuais) {
                    const d=dados.datas_contratuais,fmt=v=>v.split('-').reverse().join('/');
                    paragrafo(`Assinatura prevista: ${fmt(d.assinatura)}. Vigência prevista: ${fmt(d.vigencia)}. Primeira liberação: ${fmt(d.primeira_liberacao)}. Primeira amortização: ${fmt(d.primeira_amortizacao)}. Início da comissão: ${fmt(d.inicio_comissao)}.`);
                    paragrafo(dados.convencao);
                    if(dados.metodo_sofr==='composta_projetada')paragrafo('Índice SOFR sintético projetado com overnight constante. Não representa série histórica nem curva futura publicada. Spreads acrescidos separadamente.');
                }
                if(dados.taxa_indexador) paragrafo(`${dados.taxa_indexador.indexador}: ${dados.taxa_indexador.valor}% ao ano · ${dados.taxa_indexador.origem}.`);
                const detalhes=document.createElement('details'),titulo=document.createElement('summary');titulo.textContent='Eventos e memória de cálculo';detalhes.append(titulo);
                paragrafo(dados.convencao,detalhes);paragrafo(dados.calendario,detalhes);
                tabela(detalhes,['Data','Saldo anterior','Liberação','Juros','Comissão','Outros encargos','Amortização','Saldo final'],dados.linhas.map(l=>[l.fim.split('-').reverse().join('/'),formatarMoeda(l.saldo_inicial),formatarMoeda(l.liberacao),formatarMoeda(l.juros_financeiros),formatarMoeda(l.comissao_credito),formatarMoeda(l.outros_encargos),formatarMoeda(l.amortizacao),formatarMoeda(l.saldo_final)]));
                resultado.append(detalhes);return;
            }
            if (dados.modo === 'anual_informado') {
                paragrafo('Cronograma anual informado pelo usuário. Valores usados diretamente na análise, sem recalcular juros ou gerar parcelas mensais.');
                paragrafo(`Juros, encargos e comissões: ${formatarMoeda(dados.juros_total)}. Amortização: ${formatarMoeda(dados.amortizacao_total)}. Total de pagamentos: ${formatarMoeda(dados.pagamento_total)}.`);
                paragrafo(`Último ano de pagamento: ${dados.ano_final}. Saldo final: ${formatarMoeda(dados.saldo_final)}.`);
                tabela(resultado, ['Ano', 'Amortização', 'Juros e encargos', 'Pagamentos'], dados.anuais.map(l=>[l.ano,formatarMoeda(l.amortizacao),formatarMoeda(l.juros),formatarMoeda(l.total)]));
                const ajustes=dados.memoria_cronograma?.ajustes_conversao_brl;
                if(ajustes && Object.values(ajustes).some(v=>Number(v)!==0)) paragrafo(`Conciliação de arredondamento cambial na última linha positiva: liberações ${formatarMoeda(ajustes.liberacao)}; amortizações ${formatarMoeda(ajustes.amortizacao)}.`);
                return;
            }

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
