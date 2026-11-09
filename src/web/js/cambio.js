/* Moeda global. As taxas e conversões de entrada são validadas no backend. */
const CambioUI = (() => {
    let atual = {moeda:'BRL', taxa_brl:'1', id:'BRL', fonte:'Moeda base', data:null};
    let versao = 0;
    let versaoEntrada=0;
    let erroEntrada=false;
    const mudancasEntrada=[];
    let entradaAtual={moeda:'BRL',taxa_brl:'1',id:'BRL',fonte:'Moeda base',data:null};
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
    const simbolo = () => formatador(entradaAtual.moeda).formatToParts(0).find(p=>p.type==='currency').value;
    const exibir = valor => { const ref=referenciaVisual(); return ref.moeda!=='BRL' && Number(ref.taxa_brl)>0 ? `${reais(valor)} · ${estrangeiro(valor,ref)}` : reais(valor); };
    const entradaFormatada = valor => new Intl.NumberFormat('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(valor));
    const campos = () => [...document.querySelectorAll('#valor-requisitado, #operacao-liberacoes input, #operacao-outros-encargos input, #fluxo-credito-linhas input, #linhas-hipotese-2 input')];
    function lerEntrada(campo) {
        if (campo.type === 'number') return campo.value;
        if (campo.id === 'valor-requisitado') return lerValorEntradaMonetaria(campo.value, 'Valor requisitado')?.numero;
        if (campo.closest('#operacao-liberacoes')) return lerValorEntradaMonetaria(campo.value, `Liberação de ${campo.dataset.ano}`)?.numero;
        return normalizarValorMonetario(campo.value)?.numero;
    }
    const valoresOriginais = new WeakMap();
    function rotulos() {
        document.querySelectorAll('label').forEach(label => {
            if(label.closest('#complemento-limites-campo')) return;
            for (const no of label.childNodes) if (no.nodeType===3 && /\((?:R\$|BRL|USD|EUR|GBP|JPY|CHF|CAD|AUD|CNY)\)/.test(no.textContent))
                { const novo=no.textContent.replace(/\((?:R\$|BRL|USD|EUR|GBP|JPY|CHF|CAD|AUD|CNY)\)/g, `(${entradaAtual.moeda==='BRL'?'R$':entradaAtual.moeda})`); if(novo!==no.textContent)no.textContent=novo; }
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
            if (no.parentElement?.closest('script,style,input,textarea,select,option,#cambio-estado,#moeda-entrada-estado,[data-cambio-equivalencia],[data-moeda-contratual],[data-cambio-brl-oficial]')) continue;
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
        if(window.resumoOperacaoAtual && typeof renderizarResumoOperacao==='function') renderizarResumoOperacao(window.resumoOperacaoAtual);
        if(typeof painelFiscalAtual!=='undefined' && painelFiscalAtual) renderizarVisaoFiscal(painelFiscalAtual);
        const desatualizada=[...document.querySelectorAll('#tbody-resultados tr')].some(l=>l.children[1]?.textContent==='Desatualizada');
        if(window.cambioUltimoResultado && !desatualizada) renderizarResultados(window.cambioUltimoResultado);
        if(window.cambioUltimoTlp && typeof fluxoTlpServico!=='undefined' && fluxoTlpServico) renderizarFluxoTlp(window.cambioUltimoTlp);
        const modal=document.getElementById('modal-feedback');
        if(!desatualizada && window.cambioUltimaRegra && modal && !modal.classList.contains('hidden')) mostrarDetalhesRegra(window.cambioUltimaRegra);
        if(typeof atualizarContextoOperacao==='function') atualizarContextoOperacao();
        rotulos(); textosPublicados(); equivalenciasEntradas();
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
        const seletorEntrada=document.getElementById('moeda-entrada');
        seletor.disabled=botao.disabled=seletorEntrada.disabled=true;
        estado('Consultando cotação…');
        try {
            const resposta=await eel.obter_cotacao_py(moeda)();
            if(resposta.status!=='sucesso'||!resposta.cotacao) throw new Error(resposta.mensagem||'Cotação indisponível.');
            const proxima=resposta.cotacao;
            if(!(Number(proxima.taxa_brl)>0)||proxima.moeda!==moeda) throw new Error('Cotação inválida.');
            if(minhaVersao!==versao) return;
            if(!await converterEntrada(moeda,proxima)) throw new Error('Não foi possível converter o preenchimento. Confira a mensagem no formulário.');
            atual=proxima;
            localStorage.setItem('simulador.moeda',moeda);
            seletor.value=seletorEntrada.value=moeda;
            reapresentar();
            atualizarEstado();
        } catch(erro) {
            seletor.value=seletorEntrada.value=atual.moeda;
            estado(`${erro.message} Moeda mantida: ${atual.moeda}.`,true);
        } finally {seletor.disabled=botao.disabled=seletorEntrada.disabled=false;}
    }
    const assinatura=ref=>`${ref.moeda}:${String(ref.taxa_brl).includes('.')?String(ref.taxa_brl).replace(/0+$/,'').replace(/\.$/,''):ref.taxa_brl}`;
    function referenciaEntrada() {
        if(document.getElementById('operacao-indexador')?.value==='CAMBIAL' && entradaAtual.moeda===document.getElementById('operacao-moeda-contrato').value) {
            try { const taxa=decimalCotacaoContratual(document.getElementById('operacao-cotacao-contrato').value);return {...entradaAtual,taxa_brl:taxa,id:`manual:${entradaAtual.moeda}:${taxa}`,constante:true,fonte:'Cotação de preenchimento informada pelo usuário'}; }
            catch(_){return {...entradaAtual,taxa_brl:null,constante:true};}
        }
        return {...entradaAtual};
    }
    function baseCampo(campo) {
        const ref=referenciaEntrada();
        return campo.dataset.cambioExibido===campo.value && campo.dataset.cambioAssinatura===assinatura(ref) ? campo.dataset.cambioBrl : undefined;
    }
    function equivalenciasEntradas() {
        const ref=referenciaEntrada(),visual=referenciaVisual();
        const estadoEntrada=document.getElementById('moeda-entrada-estado');
        if(estadoEntrada && !erroEntrada) {estadoEntrada.textContent='';estadoEntrada.hidden=true;}

        for(const campo of [...campos(),...document.querySelectorAll('#limites-outras-dcl,#limites-demais-liberacoes input')]) {
            let nota=campo.nextElementSibling;
            if(!nota?.hasAttribute('data-cambio-equivalencia')) {nota=document.createElement('small');nota.dataset.cambioEquivalencia='true';nota.className='cambio-equivalencia';campo.after(nota);}
            let texto='';
            const fixo=!!campo.closest('#complemento-limites-campo');
            const unidade=fixo?{moeda:'BRL',taxa_brl:'1'}:ref;
            if(campo.value.trim()!=='') {
                try {
                    const valor = Number(lerEntrada(campo));
                    if(Number.isFinite(valor)) {
                        if(!(Number(unidade.taxa_brl)>0)) texto='Informe a cotação contratual para calcular o equivalente em reais.';
                        else {
                            const preservado=fixo?null:baseCampo(campo);
                            const brl=preservado!=null?Number(preservado):valor*Number(unidade.taxa_brl);
                            if(unidade.moeda!=='BRL') texto=`Real oficial: ${reais(brl)}`;
                            if(visual.moeda!=='BRL' && visual.moeda!==unidade.moeda && Number(visual.taxa_brl)>0) texto+=`${texto?' · ':''}Equivalente: ${estrangeiro(brl,visual)}`;
                        }
                    }
                } catch(_){ }
            }
            if(nota.textContent!==texto) nota.textContent=texto;
            nota.hidden=!texto;
        }
    }
    async function resolverEntrada(moeda) {
        if(document.getElementById('operacao-indexador')?.value==='CAMBIAL' && moeda===document.getElementById('operacao-moeda-contrato').value) {
            const taxa=decimalCotacaoContratual(document.getElementById('operacao-cotacao-contrato').value);
            const r=await eel.obter_cotacao_contratual_py(moeda,taxa)();
            if(r.status!=='sucesso'||!r.cotacao) throw new Error(r.mensagem||'Cotação contratual inválida.');
            return r.cotacao;
        }
        if(moeda===entradaAtual.moeda) return {...entradaAtual};
        const r=await eel.obter_cotacao_py(moeda)();
        if(r.status!=='sucesso'||!r.cotacao) throw new Error(r.mensagem||'Cotação de preenchimento indisponível.');
        return r.cotacao;
    }
    async function converterEntrada(moeda,referenciaGlobal) {
        const minhaVersao=++versaoEntrada;
        erroEntrada=false;
        const seletor=document.getElementById('moeda-entrada'),mensagem=document.getElementById('moeda-entrada-estado');
        const bloqueados=[...document.querySelectorAll('#moeda-global,#cambio-atualizar,#form-simulacao input,#form-simulacao select,#form-simulacao button[type="submit"]')].filter(campo=>campo!==seletor).map(campo=>({campo,disabled:campo.disabled}));
        seletor.disabled=true;bloqueados.forEach(({campo})=>campo.disabled=true);
        mensagem.hidden=false;mensagem.textContent='Convertendo os valores informados…';
        try {
            const preenchidos=campos().filter(c=>c.value.trim()!=='');
            const origem=preenchidos.length?await resolverEntrada(entradaAtual.moeda):referenciaEntrada();
            const contratual=document.getElementById('operacao-indexador')?.value==='CAMBIAL' && moeda===document.getElementById('operacao-moeda-contrato').value;
            const destino=referenciaGlobal && !contratual?referenciaGlobal:await resolverEntrada(moeda);
            if(!(Number(destino.taxa_brl)>0)||destino.moeda!==moeda) throw new Error('Cotação de preenchimento inválida.');
            const valores=preenchidos.map(campo=>({campo,base:baseCampo(campo),valor:lerEntrada(campo)??'0'}));
            const liberacoesAtivas=[...document.querySelectorAll('#operacao-liberacoes input[data-ativo="true"]')];
            const conciliar=tipoLiberacaoOperacao()==='cronograma' && liberacoesAtivas.length>0 && liberacoesAtivas.every(c=>c.value.trim()!=='');
            const entradas=valores.map(v=>({valor:v.valor,base_brl:v.base,tipo:v.campo.id==='valor-requisitado'?'principal':conciliar&&liberacoesAtivas.includes(v.campo)?'liberacao':'outro'}));
            const conversao=await eel.converter_entradas_simulacao_py(entradas,origem.id,destino.id,conciliar)();
            if(conversao.status!=='sucesso'||conversao.valores?.length!==valores.length) throw new Error(conversao.mensagem||'Falha na conversão das entradas.');
            const convertidos=valores.map((v,i)=>({...v,resultado:conversao.valores[i]}));
            if(minhaVersao!==versaoEntrada)return;
            entradaAtual=destino;
            mudancasEntrada.push({origem:{...origem},destino:{...destino},ajuste_liberacoes_brl:conversao.ajuste_liberacoes_brl||'0'});
            if(mudancasEntrada.length>20)mudancasEntrada.shift();
            for(const {campo,resultado} of convertidos) {
                campo.value=campo.type==='number'?resultado.valor:`${simbolo()} ${entradaFormatada(resultado.valor)}`;
                campo.dataset.cambioBrl=resultado.brl;campo.dataset.cambioExibido=campo.value;campo.dataset.cambioAssinatura=assinatura(destino);
            }
            seletor.value=moeda;
            mensagem.textContent=moeda==='BRL'?'Preenchimento em reais. A moeda de exibição fica no cabeçalho.':`Preenchimento em ${moeda} · 1 ${moeda} = R$ ${Number(destino.taxa_brl).toLocaleString('pt-BR',{maximumFractionDigits:12})} · ${destino.fonte||'cotação selecionada'}`;
            reapresentar();atualizarEstado();
            return true;
        } catch(erro) {erroEntrada=true;seletor.value=entradaAtual.moeda;mensagem.textContent=erro.message;return false;}
        finally {seletor.disabled=false;bloqueados.forEach(({campo,disabled})=>campo.disabled=disabled);equivalenciasEntradas();}
    }
    document.addEventListener('DOMContentLoaded',()=>{
        document.getElementById('moeda-global').addEventListener('change',e=>selecionar(e.target.value));
        document.getElementById('cambio-atualizar').addEventListener('click',()=>selecionar(atual.moeda));
        document.getElementById('form-simulacao').addEventListener('input',e=>{
            if(e.target.id==='operacao-cotacao-contrato') {const ref=referenciaEntrada();if(ref.constante && Number(ref.taxa_brl)>0)entradaAtual=ref;}
            if(['operacao-cotacao-contrato','operacao-moeda-contrato','operacao-indexador'].includes(e.target.id)) {
                erroEntrada=false;
                queueMicrotask(()=>{reapresentar();atualizarEstado();});
            }
        });
        document.getElementById('moeda-entrada').addEventListener('change',e=>selecionar(e.target.value));
        document.getElementById('form-simulacao').addEventListener('input',()=>queueMicrotask(equivalenciasEntradas));
        atualizarEstado();
        equivalenciasEntradas();
        let marcada=false;
        new MutationObserver(()=>{if(marcada)return;marcada=true;queueMicrotask(()=>{marcada=false;rotulos();textosPublicados();equivalenciasEntradas();});}).observe(document.body,{childList:true,subtree:true,characterData:true});
        const salva=localStorage.getItem('simulador.moeda');
        if(salva && salva!=='BRL') selecionar(salva);
    });
    return {formatar:exibir,simbolo,selecionar,selecionarEntrada:selecionar,referenciaEntrada,baseCampo,memoriaEntrada:()=>mudancasEntrada.map(m=>({...m})),atualizarEntradas:()=>{rotulos();equivalenciasEntradas();},referencia:()=>({...atual}),converterVisual:valor=>Number(valor),simboloVisual:()=>'R$',referenciaVisual:()=>({...referenciaVisual()})};
})();
