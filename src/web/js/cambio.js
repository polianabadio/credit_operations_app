/* Moeda global. As taxas e conversões de entrada são validadas no backend. */
const CambioUI = (() => {
    let atual = {moeda:'BRL', taxa_brl:'1', id:'BRL', fonte:'Moeda base', data:null};
    let versao = 0;
    function referenciaVisual() {
        if (atual.moeda !== 'BRL' && document.getElementById('operacao-indexador')?.value === 'CAMBIAL'
            && document.getElementById('operacao-moeda-contrato')?.value === atual.moeda) {
            try { return {...atual, taxa_brl:decimalCotacaoContratual(document.getElementById('operacao-cotacao-contrato').value),contratual:true}; }
            catch (_) { return {...atual,taxa_brl:null,contratual:true}; }
        }
        return atual;
    }
    const formatadores=new Map();
    function formatador(moeda) {
        if(!formatadores.has(moeda)) formatadores.set(moeda,new Intl.NumberFormat('pt-BR',{style:'currency',currency:moeda,minimumFractionDigits:2,maximumFractionDigits:2}));
        return formatadores.get(moeda);
    }
    const reais = valor => formatador('BRL').format(Number(valor));
    const estrangeiro = (valor,ref=referenciaVisual()) => formatador(ref.moeda).format(Number(valor)/Number(ref.taxa_brl));
    const simbolo = () => formatador(atual.moeda).formatToParts(0).find(p=>p.type==='currency').value;
    const exibir = valor => { const ref=referenciaVisual(); return ref.moeda!=='BRL' && Number(ref.taxa_brl)>0 ? `${reais(valor)} · ${estrangeiro(valor,ref)}` : reais(valor); };
    const entradaFormatada = valor => new Intl.NumberFormat('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(valor));
    const campos = () => [...document.querySelectorAll('#valor-requisitado, #operacao-liberacoes input, #fluxo-credito-linhas input, #linhas-hipotese-2 input')].filter(campo => !(document.getElementById('operacao-indexador')?.value === 'CAMBIAL' && (campo.id === 'valor-requisitado' || campo.closest('#operacao-liberacoes'))));
    const valoresOriginais = new WeakMap();
    function rotulos() {
        document.querySelectorAll('label').forEach(label => {
            if (document.getElementById('operacao-indexador')?.value === 'CAMBIAL' && (label.htmlFor === 'valor-requisitado' || label.closest('#operacao-liberacoes'))) return;
            for (const no of label.childNodes) if (no.nodeType===3 && /\((?:R\$|BRL|USD|EUR|GBP|JPY|CHF|CAD|AUD|CNY)\)/.test(no.textContent))
                { const novo=no.textContent.replace(/\((?:R\$|BRL|USD|EUR|GBP|JPY|CHF|CAD|AUD|CNY)\)/g, `(${atual.moeda==='BRL'?'R$':atual.moeda})`); if(novo!==no.textContent)no.textContent=novo; }
        });
        for (const campo of campos()) if (campo.placeholder) campo.placeholder=`${simbolo()} 0,00`;
    }
    function preencherPar(no,valor) {
        const texto=exibir(valor);
        if(no.dataset.cambioTexto===texto) return;
        no.dataset.cambioTexto=texto; no.dataset.cambioBrlOficial=String(valor);
        no.setAttribute('aria-label',texto);
        no.classList.add('valor-duas-moedas');
        const partes=texto.split(' · ');
        const oficial=document.createElement('span');oficial.textContent=partes[0];
        const secundario=document.createElement('small');secundario.textContent=partes[1]||'';secundario.hidden=!partes[1];
        no.replaceChildren(oficial,secundario);
    }
    function textosPublicados(raiz=document.body) {
        raiz.querySelectorAll('[data-cambio-brl-oficial]').forEach(no=>preencherPar(no,Number(no.dataset.cambioBrlOficial)));
        const walker=document.createTreeWalker(raiz,NodeFilter.SHOW_TEXT);
        const nos=[]; while(walker.nextNode()) nos.push(walker.currentNode);
        for(const no of nos) {
            if (no.parentElement?.closest('script,style,input,textarea,select,option,#cambio-estado,[data-moeda-contratual],[data-cambio-brl-oficial]')) continue;
            const salvo=valoresOriginais.get(no);
            let texto=salvo && no.textContent===salvo.exibido ? salvo.original : no.textContent;
            texto=texto.replace(/(-?R\$\s*-?[\d.]+,\d{2})\s*·\s*-?(?:US\$|USD|EUR|GBP|JPY|CHF|CAD|AUD|CNY|€|£|JP¥|¥|CA\$|AU\$|CN¥)\s*-?[\d.]+,\d{2}/g,'$1');
            if (!/R\$\s*-?[\d.]+,\d{2}/.test(texto)) continue;
            const exibido=texto.replace(/(-?)R\$\s*(-?)([\d.]+,\d{2})/g,(_,sinal,neg,numero)=>exibir(Number(numero.replace(/\./g,'').replace(',','.'))*(sinal||neg?-1:1)));
            valoresOriginais.set(no,{original:texto,exibido});
            if(no.textContent!==exibido) no.textContent=exibido;
            const inteiro=texto.match(/^(-?)R\$\s*(-?)([\d.]+,\d{2})$/);
            if(inteiro && no.parentElement?.childNodes.length===1 && ['STRONG','TD'].includes(no.parentElement.tagName)) {
                preencherPar(no.parentElement,Number(inteiro[3].replace(/\./g,'').replace(',','.'))*(inteiro[1]||inteiro[2]?-1:1));
            }
        }
    }
    function reapresentar() {
        if(typeof painelFiscalAtual!=='undefined' && painelFiscalAtual) renderizarVisaoFiscal(painelFiscalAtual);
        const desatualizada=[...document.querySelectorAll('#tbody-resultados tr')].some(l=>l.children[1]?.textContent==='Desatualizada');
        if(window.cambioUltimoResultado && !desatualizada) renderizarResultados(window.cambioUltimoResultado);
        if(window.cambioUltimoTlp && typeof fluxoTlpServico!=='undefined' && fluxoTlpServico) renderizarFluxoTlp(window.cambioUltimoTlp);
        const modal=document.getElementById('modal-feedback');
        if(!desatualizada && window.cambioUltimaRegra && modal && !modal.classList.contains('hidden')) mostrarDetalhesRegra(window.cambioUltimaRegra);
        if(typeof atualizarContextoOperacao==='function') atualizarContextoOperacao();
        rotulos(); textosPublicados();
    }
    function estado(texto,erro=false) {
        const no=document.getElementById('cambio-estado');no.textContent=texto;no.classList.toggle('cambio-erro',erro);
    }
    function atualizarEstado() {
        const ref=referenciaVisual();
        if(atual.moeda==='BRL') {estado('Valores oficiais em reais');return;}
        const modo=`Real oficial + ${ref.moeda}`;
        if(!(Number(ref.taxa_brl)>0)) {estado(`Real oficial · informe a cotação contratual para exibir ${ref.moeda}`);return;}
        estado(ref.contratual ? `${modo} · 1 ${ref.moeda} = R$ ${Number(ref.taxa_brl).toLocaleString('pt-BR',{maximumFractionDigits:12})} · cotação contratual fixa`
            : `${modo} · 1 ${ref.moeda} = R$ ${Number(ref.taxa_brl).toLocaleString('pt-BR',{maximumFractionDigits:6})} · ${new Date(ref.data).toLocaleString('pt-BR')} · ${ref.fonte||'API de câmbio'}${ref.referencia_anterior?' · referência anterior':''}`);
    }
    async function selecionar(moeda) {
        const minhaVersao=++versao;
        const seletor=document.getElementById('moeda-global');
        const botao=document.getElementById('cambio-atualizar');
        seletor.disabled=botao.disabled=true;
        const bloqueados=[...campos(),...document.querySelectorAll('#form-simulacao button[type="submit"]')].map(campo=>({campo,disabled:campo.disabled}));
        bloqueados.forEach(({campo})=>campo.disabled=true);
        estado('Consultando cotação…');
        try {
            const resposta=await eel.obter_cotacao_py(moeda)();
            if(resposta.status!=='sucesso'||!resposta.cotacao) throw new Error(resposta.mensagem||'Cotação indisponível.');
            const proxima=resposta.cotacao;
            if(!(Number(proxima.taxa_brl)>0)||proxima.moeda!==moeda) throw new Error('Cotação inválida.');
            const preenchidos=campos().filter(campo=>campo.value.trim()!=='');
            const valores=preenchidos.map(campo=>{
                const original=campo.dataset.cambioExibido===campo.value ? campo.dataset.cambioBrl : null;
                const texto=campo.type==='number' ? campo.value : normalizarValorMonetario(campo.value).numero;
                return {campo,original,texto};
            });
            // Conversão ocorre com Decimal no backend; entradas preservam centavos da base.
            const convertidos=[];
            for(const grupo of [valores.filter(v=>v.original!=null),valores.filter(v=>v.original==null)]) {
                if(!grupo.length) continue;
                const r=await eel.converter_moedas_py(grupo.map(v=>v.original??v.texto),grupo[0].original!=null?'BRL':atual.id,proxima.id)();
                if(r.status!=='sucesso'||r.valores?.length!==grupo.length) throw new Error(r.mensagem||'Falha na conversão dos campos.');
                grupo.forEach((v,i)=>convertidos.push({...v,resultado:r.valores[i]}));
            }
            if(minhaVersao!==versao) return;
            atual=proxima;
            for(const {campo,resultado} of convertidos) {
                campo.value=campo.type==='number'?resultado.valor: `${simbolo()} ${entradaFormatada(resultado.valor)}`;
                campo.dataset.cambioBrl=resultado.brl;campo.dataset.cambioExibido=campo.value;
            }
            localStorage.setItem('simulador.moeda',moeda);
            seletor.value=moeda;
            reapresentar();
            atualizarEstado();
        } catch(erro) {
            seletor.value=atual.moeda;
            estado(`${erro.message} Moeda mantida: ${atual.moeda}.`,true);
        } finally {seletor.disabled=botao.disabled=false;bloqueados.forEach(({campo,disabled})=>campo.disabled=disabled);}
    }
    document.addEventListener('DOMContentLoaded',()=>{
        document.getElementById('moeda-global').addEventListener('change',e=>selecionar(e.target.value));
        document.getElementById('cambio-atualizar').addEventListener('click',()=>selecionar(atual.moeda));
        document.getElementById('form-simulacao').addEventListener('input',e=>{
            if(['operacao-cotacao-contrato','operacao-moeda-contrato','operacao-indexador'].includes(e.target.id)) {
                queueMicrotask(()=>{reapresentar();atualizarEstado();});
            }
        });
        atualizarEstado();
        let marcada=false;
        new MutationObserver(()=>{if(marcada)return;marcada=true;queueMicrotask(()=>{marcada=false;rotulos();textosPublicados();});}).observe(document.body,{childList:true,subtree:true,characterData:true});
        const salva=localStorage.getItem('simulador.moeda');
        if(salva && salva!=='BRL') selecionar(salva);
    });
    return {formatar:exibir,simbolo,selecionar,referencia:()=>({...atual}),converterVisual:valor=>Number(valor),simboloVisual:()=>'R$',referenciaVisual:()=>({...referenciaVisual()})};
})();
