/* Verificação visual isolada: fixtures locais, sem API ou banco reais. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../src/web');
const output = path.resolve(__dirname, '../.ui-preview');
const painel = {
    pagamentosDivida: {composicao_pagamentos:{2026:{amortizacao:'1600000000',juros_encargos:'400000000'},'Restante a pagar':{amortizacao:'2800000000',juros_encargos:'200000000'}},status:'Disponível',ano_inicial:2026,pagamentos:{2026:'2000000000',2027:'2500000000',2029:'0'},snapshot:{idPleito:1,numeroPvl:'PVL teste',data:'2026-07-30'},consultado_em:'2026-10-29T10:00:00',saldos_sem_ano:[{rotulo:'Restante a pagar',demais_operacoes:'3000000000'}],motivos:[]},
    exercicio: 2026, ultima_consulta: '2026-10-28T16:00:00', dados_disponiveis: 10,
    historico_divida_rcl: Array.from({length:12},(_,i)=>({ano:2015+i,periodo:i===11?2:3,parcial:i===11,
        divida_consolidada:String(20000000000+i*800000000),rcl:String(25000000000+i*2000000000),
        percentual_dc_rcl:String((20000000000+i*800000000)/(25000000000+i*2000000000)*100),
        percentual_dcl_rcl:String([90,88,80,73,65,56,49,46,45,44,43.5,43.3][i]),base_dcl_rcl:i<5?'RCL':'RCL ajustada',
        anexo:'RGF-Anexo 02',origem:'SICONFI/RGF',escopo:'Executivo'})),
    rcl: {valor: 47000000000, ano: 2026, periodo: 4, anexo: 'RREO-Anexo 03', origem: 'SICONFI/RREO'},
    capag: {historico_documental: ['B','B','B','B','C','C'].map((nota,i)=>({ano:2012+i,nota,documento:'Relatório Fiscal 2017',pagina:74,tipo:'serie_retrospectiva'})),referencias_indicadores:[{ente:52,ano_referencia:2024,tipo:'referencia_estadual',documento:'Relatório estadual de 2024',pagina:29,indicadores:{endividamento:'68.99',poupanca_corrente:'87.10',liquidez_relativa:'15.44'}}],valor: 'B+', ranking:'Aicf', ano: 2025, ano_base: 2024, origem: 'Tesouro Transparente/CAPAG',
    historico: ['C','C','C','C','B','C','C','B+'].map((nota, i) => ({ano:2018+i, ano_base:2017+i, nota,
        indicadores: [5,6].includes(i) ? {} : Object.fromEntries(['endividamento','poupanca_corrente','liquidez_relativa'].map((chave,j)=>[chave, [
            [93.35,95.10,1820.59], [92.3696551,96.2577285,-1021.893677], [84.0513371,98.063539,298.3387595],
            [86.11,95.96,248.73], [73,91.34,11.3], [], [], [65.53,86.28,12.95]
        ][i][j]])),
        url:'https://www.tesourotransparente.gov.br/ckan/dataset/capag-estados'})), indicadores: {
        endividamento: {valor: 65.53, nota: 'B'}, poupança: {},
        poupanca_corrente: {valor: 86.28, nota: 'B'}, liquidez_relativa: {valor: 12.95, nota: 'A'}
    }},
    dcl: {valor: 43.3, limite: 200, ano: 2026, periodo: 2, origem: 'SICONFI/RGF'},
    caed: {valor: 3.69, limite: 11.5, ano: 2025, periodo: 6, origem: 'SICONFI/RREO', periodicidade: 'B', historico: true, natureza: 'servico_realizado'},
    dtp: {valor: 43, limite: 60, ano: 2026, periodo: 2},
    limites_referencia: {'DCL/RCL': 200, 'CAED/RCL': 11.5, 'Limite de 16%': 16}, fontes: [],
    regra_ouro: [{ano: 2025, situacao: 'Atendida'}, {ano: 2026, dados_calculados: {limite_disponivel: 6500000000, despesas_capital:{total:10000000000}, operacoes_credito:{total:3500000000}, fontes:[{anexo:'RREO-Anexo 01',periodo:4}]}}]
};
const stub = `const painelFixture=${JSON.stringify(painel)};
window.eel=new Proxy({}, {get(_,nome){ if(nome==='_websocket') return null; return (...args)=>async()=>{
if(nome==='obter_cotacao_contratual_py')return {status:'sucesso',cotacao:{moeda:args[0],taxa_brl:args[1],id:'manual:'+args[0]+':'+args[1],constante:true,fonte:'Cotação contratual informada pelo usuário'}};if(nome==='obter_cotacao_py'){if(args[0]==='JPY')return {status:'erro',mensagem:'Cotação indisponível'};return {status:'sucesso',cotacao:{moeda:args[0],taxa_brl:args[0]==='BRL'?'1':'5',id:args[0],data:'2026-11-05T12:00:00Z'}};}
if(nome==='converter_entradas_simulacao_py')return {status:'sucesso',valores:args[0].map(v=>{const brl=v.base_brl!=null?Number(v.base_brl):Number(v.valor)*(args[1]==='BRL'?1:5);return {brl:brl.toFixed(2),valor:(brl/(args[2]==='BRL'?1:5)).toFixed(2)};})};
if(nome==='converter_moedas_py')return {status:'sucesso',valores:args[0].map(v=>{const brl=Number(v)*(args[1]==='BRL'?1:args[1].startsWith('manual:')?Number(args[1].split(':')[2]):5);return {brl:brl.toFixed(2),valor:(brl/(args[2]==='BRL'?1:args[2].startsWith('manual:')?Number(args[2].split(':')[2]):5)).toFixed(2)};})};
if(nome==='obter_dados_iniciais') return {status:'sucesso',anos_disponiveis:[2026,2025]};
if(nome==='obter_fator_projecao_py') return '2.031208231';
if(nome==='obter_painel_fiscal_py') return {status:'sucesso',painel:painelFixture};
if(nome==='iniciar_atualizacao_siconfi') return {running:false,falhas:0};
if(nome==='obter_comprometimento_sadipem_py') return {status:'erro'};
if(nome==='get_system_status_py') return {database:{status:'Online',mensagem:'Conexão disponível'},resources:{cpu_percent:'1',memory_mb:'100'}};
if(nome==='get_db_config') return {type:'json',path:'cache/dados-fiscais.json'};
return {status:'sucesso'};
};}});`;
const server = http.createServer((req,res) => {
    if(req.url === '/eel.js') { res.setHeader('Content-Type','text/javascript'); return res.end(stub); }
    const file = path.join(root, req.url === '/' ? 'main.html' : decodeURIComponent(req.url.split('?')[0]));
    if(!file.startsWith(root) || !fs.existsSync(file)) { res.statusCode=404; return res.end(); }
    res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'image/png');
    res.end(fs.readFileSync(file));
});
(async () => {
    fs.mkdirSync(output,{recursive:true});
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    let browser;
    try {
        browser = await chromium.launch({headless:true, channel:'msedge'});
        const page = await browser.newPage({viewport:{width:1440,height:1000}});
        const errors=[]; page.on('pageerror',e=>errors.push(e.message));
        await page.goto(`http://127.0.0.1:${server.address().port}`);
        await page.waitForFunction(()=>document.querySelector('#painel-indicadores strong')?.textContent.includes('B+'));
        assert.equal(await page.locator('.painel-ponte').count(),1);
        assert(await page.locator('.painel-ponte').evaluate(el=>Boolean(el.parentElement.classList.contains('painel-hero') && el.parentElement.nextElementSibling?.id==='painel-indicadores')));
        assert.equal(await page.locator('.painel-ponte').evaluate(el=>getComputedStyle(el).backgroundColor),'rgba(0, 0, 0, 0)');
        assert.match(await page.locator('.painel-ponte').textContent(),/Os indicadores deste painel/);
        assert.equal(await page.locator('.painel-hero').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
        assert.equal(await page.locator('.painel-ponte').getAttribute('open'),null);
        assert(!await page.locator('.painel-ponte-conteudo').isVisible());
        await page.locator('.painel-ponte summary').click();
        assert(await page.locator('.painel-ponte-conteudo').isVisible());
        await page.locator('.painel-ponte summary').focus();
        await page.keyboard.press('Enter');
        assert(!await page.locator('.painel-ponte-conteudo').isVisible());
        await page.locator('.painel-hero').screenshot({path:path.join(output,'dashboard-titulo-branco.png')});
        await page.evaluate(p=>renderizarVisaoFiscal(p),painel);
        assert.equal(await page.locator('.pagamentos-divida').count(),0);
        assert.equal(await page.getByRole('heading', {name:'Pagamentos anuais da dívida', exact:true}).count(),0);
        assert.equal(await page.locator('.ouro-componente-trilho span').count(),2);
        assert.match(await page.locator('.ouro-margem > strong').textContent(),/6\.500\.000\.000,00/);
        assert.match(await page.locator('.ouro-referencia').textContent(),/4º bimestre de 2026/);
        assert.equal(await page.locator('.ouro-barra-credito').evaluate(e=>e.style.width),'35%');
        assert.equal(await page.locator('.ouro-detalhes-fonte').getAttribute('open'),null);
        assert(!await page.getByText('Esta margem não representa o valor máximo de uma nova contratação.',{exact:true}).isVisible());
        await page.locator('.regra-ouro-home').evaluate(el=>el.scrollIntoView({block:'center'}));
        await page.locator('.regra-ouro-home').screenshot({path:path.join(output,'dashboard-regra-ouro.png')});
        await page.locator('.ouro-detalhes-fonte summary').click();
        assert(await page.getByText('Esta margem não representa o valor máximo de uma nova contratação.',{exact:true}).isVisible());
        await page.locator('.ouro-detalhes-fonte summary').click();
        await page.evaluate(p=>{
            const teste=structuredClone(p);
            teste.regra_ouro[1].dados_calculados.limite_disponivel=-100;
            teste.regra_ouro[1].dados_calculados.operacoes_credito.total=10000000100;
            renderizarVisaoFiscal(teste);
        },painel);
        assert.equal(await page.locator('.ouro-margem-negativa').count(),1);
        assert.match(await page.locator('.ouro-margem > strong').textContent(),/-R\$|R\$\s*-/);
        await page.evaluate(p=>{
            const teste=structuredClone(p);
            teste.regra_ouro[1].dados_calculados={limite_disponivel:0,despesas_capital:{total:0},operacoes_credito:{total:0}};
            renderizarVisaoFiscal(teste);
        },painel);
        assert.match(await page.locator('.ouro-margem > strong').textContent(),/0,00/);
        assert.equal(await page.locator('.ouro-barra-credito').evaluate(e=>e.style.width),'0%');
        await page.evaluate(p=>{
            const teste=structuredClone(p); teste.regra_ouro[1].dados_calculados=null; renderizarVisaoFiscal(teste);
        },painel);
        assert.equal(await page.locator('.ouro-margem > strong').textContent(),'Dado indisponível');
        assert.equal(await page.locator('.ouro-componente-trilho span').count(),0);
        await page.evaluate(p=>renderizarVisaoFiscal(p),painel);
        assert.equal(await page.locator('#home-limites .limite-grafico-svg').count(),0);
        assert.equal(await page.locator('#home-limites .limite-comparacao-trilho').count(),2);
        assert.equal(await page.locator('#home-limites .limite-resumo-descricao, #home-limites .limite-resumo-linha').count(),0);
        assert.equal(await page.locator('.limites-interpretacao').count(),0);
        assert.match(await page.locator('[data-limite="caed"]').textContent(),/Último exercício fechado · 2025/);
        assert.equal(await page.locator('[data-limite="dcl"] .limite-grafico-principal strong').textContent(),'43,30%');
        assert.match(await page.locator('[data-limite="dcl"] .limite-comparacao-escala').textContent(),/Limite: 200,00%/);
        assert.doesNotMatch(await page.locator('[data-limite="dcl"]').textContent(),/21,65%|do limite utilizado/);
        assert.equal(await page.locator('[data-limite="mga"] .limite-comparacao, [data-limite="mga"] svg').count(),0);
        await page.evaluate(p=>{
            const teste=structuredClone(p);
            teste.fluxo_credito={ano:2026,percentualLimite:16,positionOnly:true,parameterValidated:true,rows:[{ano:2026,dadosCompletos:false,rclProjetada:50000000000,tetoAnual:8000000000,scheduledDisbursements:null,margemEstimada:null}]};
            teste.margemPublica={status:'Indisponível',rows:[]};
            renderizarVisaoFiscal(teste);
        },painel);
        assert.match(await page.locator('[data-limite="mga"]').textContent(),/RCL projetada:.*50\.000\.000\.000,00/);
        assert.match(await page.locator('[data-limite="mga"]').textContent(),/Teto anual.*8\.000\.000\.000,00/);
        assert.equal(await page.locator('[data-limite="mga"] .limite-grafico-principal strong').textContent(),'Não determinada');
        const componentesParciais=page.locator('#painel-limites .margem-componentes');
        assert.match(await componentesParciais.textContent(),/RCL projetada.*50\.000\.000\.000,00/);
        assert.match(await componentesParciais.textContent(),/Teto anual.*8\.000\.000\.000,00/);
        assert.match(await componentesParciais.textContent(),/Liberações existentes incluídasNão disponível/);
        await page.click('#nav-limites');
        await page.evaluate(()=>window.scrollTo(0,0));
        await page.locator('#painel-limites .margem-credito').screenshot({path:path.join(output,'limites-rcl-sem-liberacoes.png')});
        await page.click('#nav-painel');
        await page.evaluate(p=>{
            const teste=structuredClone(p);
            teste.fluxo_credito={ano:2026,percentualLimite:16,positionOnly:true,parameterValidated:true,rows:[{ano:2026,dadosCompletos:false,rclProjetada:50000000000,tetoAnual:8000000000}],sources:{rclSource:'SICONFI/RREO',rclExercise:2026,rclReferencePeriod:4}};
            teste.margemPublica={status:'Referência pública',snapshot:{numeroPvl:'PVL teste',data:'30/07/2026'},motivos:['Cobertura atual não confirmada'],rows:[{ano:2026,tetoAnual:8000000000,scheduledDisbursements:1000000000,margemEstimada:7000000000}]};
            renderizarVisaoFiscal(teste);
        },painel);
        assert.match(await page.locator('[data-limite="mga"]').textContent(),/Referência do PVL · 2026/);
        assert.doesNotMatch(await page.locator('[data-limite="mga"]').textContent(),/12,50%|0,00%|do limite utilizado/);
        assert.match(await page.locator('[data-limite="mga"] .limite-grafico-principal').textContent(),/7\.000\.000\.000,00/);
        await page.locator('#home-limites').evaluate(el=>el.scrollIntoView({block:'center'}));
        await page.locator('#home-limites').screenshot({path:path.join(output,'dashboard-limites-graficos.png')});
        await page.click('#nav-limites');
        assert.equal(await page.locator('.limites-fator').count(),0);
        const margemDetalhe = page.locator('#painel-limites .margem-credito');
        assert.match(await margemDetalhe.locator('.margem-valor-principal').textContent(), /7\.000\.000\.000,00/);
        assert.match(await margemDetalhe.locator('.limite-ressalva').textContent(), /cobertura.*não está confirmada/);
        assert(!await margemDetalhe.locator('table').isVisible());
        await margemDetalhe.locator('summary').focus();
        await page.keyboard.press('Enter');
        assert(await margemDetalhe.locator('table').isVisible());
        assert.match(await margemDetalhe.locator('details').textContent(), /PVL teste/);
        await margemDetalhe.locator('summary').click();
        assert.equal(await page.locator('#painel-limites [data-regra="dcl"] h3').textContent(),'DCL/RCL · Estoque da dívida');
        assert.equal(await page.locator('#painel-limites [data-regra="caed"] h3').textContent(),'CAED/RCL · Serviço da dívida');
        assert.equal(await page.locator('#painel-limites .limite-valores > div').count(),4);
        assert.equal(await page.locator('#painel-limites .painel-progress-track').count(),0);
        assert.match(await page.locator('#painel-limites .limite-ressalva').allTextContents().then(t=>t.join(' ')), /último exercício fechado disponível \(2025\)/);
        await margemDetalhe.locator('summary').blur();
        await page.locator('#painel-limites').screenshot({path:path.join(output,'limites-simplificados.png')});
        await page.setViewportSize({width:390,height:844});
        assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2));
        await margemDetalhe.locator('summary').click();
        assert(await margemDetalhe.locator('table').isVisible());
        assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2));
        await margemDetalhe.locator('summary').click();
        await margemDetalhe.locator('summary').blur();
        await page.locator('#painel-limites').screenshot({path:path.join(output,'limites-simplificados-mobile.png')});
        await page.setViewportSize({width:1440,height:1000});
        await page.click('#nav-painel');
        await page.evaluate(p=>{
            const teste=structuredClone(p);
            teste.fluxo_credito={ano:2026,percentualLimite:16};
            teste.margemPublica={status:'Referência pública',rows:[{ano:2026,tetoAnual:8000000000,scheduledDisbursements:9000000000,margemEstimada:-1000000000}]};
            teste.dcl.valor=0;
            renderizarVisaoFiscal(teste);
        },painel);
        assert.equal(await page.locator('[data-limite="mga"] .limite-grafico-aviso').textContent(),'Saldo negativo');
        assert.equal(await page.locator('[data-limite="mga"].limite-grafico-excedido').count(),1);
        assert.match(await page.locator('[data-limite="mga"] .limite-grafico-principal').textContent(),/-R\$|R\$\s*-/);
        assert.equal(await page.locator('[data-limite="dcl"] .limite-grafico-principal strong').textContent(),'0,00%');
        await page.evaluate(p=>{
            const teste=structuredClone(p); teste.dcl.valor=210; teste.caed.valor=null;
            renderizarVisaoFiscal(teste);
        },painel);
        assert.equal(await page.locator('[data-limite="dcl"] .limite-grafico-principal strong').textContent(),'210,00%');
        assert.equal(await page.locator('[data-limite="dcl"] .limite-comparacao-barra').evaluate(e=>e.style.width),'100%');
        assert.equal(await page.locator('[data-limite="dcl"] .limite-grafico-aviso').textContent(),'Acima do limite');
        assert.equal(await page.locator('[data-limite="caed"] .limite-grafico-principal strong').textContent(),'Não disponível');
        assert.equal(await page.locator('[data-limite="caed"] .limite-comparacao-barra').count(),0);
        await page.evaluate(p=>renderizarVisaoFiscal(p),painel);
        assert.equal(await page.locator('.capag-faixa').count(), 4);
        assert.equal(await page.locator('.capag-arco, .capag-tabela').count(), 0);
        assert.equal(await page.locator('.capag-indicador.capag-favoravel').count(), 4);
        assert.equal(await page.locator('.capag-evolucao, .capag-evolucao-ponto').count(), 0);
        assert.equal(await page.locator('.posicao-monetaria').count(), 0);
        assert.equal(await page.locator('.divida-historico-ano').count(), 12);
        assert.equal(await page.locator('.divida-historico-barra').count(), 24);
        assert.equal(await page.locator('.divida-historico-ponto-dcl').count(),12);
        assert.equal(await page.locator('.divida-historico-linha-dcl').count(),11);
        assert.match(await page.locator('.divida-historico-legenda').textContent(),/DCL\/RCL · linha/);
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /2026 · 2º quadrimestre · parcial/);
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /R\$\s*28\.800\.000\.000,00/);
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /43,30%/);
        await page.locator('.divida-historico-ano[data-ano="2015"] text').last().click();
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /2015 · 3º quadrimestre/);
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /90,00%/);
        await page.locator('.divida-historico-ano[data-ano="2016"]').focus();
        await page.keyboard.press('Enter');
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /2016/);
        await page.locator('.divida-historico-ano[data-ano="2026"] text').last().click();
        await page.locator('.divida-historico').screenshot({path:path.join(output,'historico-divida-rcl.png')});
        await page.evaluate(p => {
            const teste = structuredClone(p);
            teste.historico_divida_rcl[0].divida_consolidada='0';
            teste.historico_divida_rcl[0].rcl=null;
            teste.historico_divida_rcl[0].percentual_dc_rcl=null;
            teste.historico_divida_rcl[0].percentual_dcl_rcl=null;
            renderizarVisaoFiscal(teste);
        },painel);
        assert.equal(await page.locator('.divida-historico-ano[data-ano="2015"] .divida-historico-barra').count(),1);
        assert.equal(await page.locator('.divida-historico-ponto-dcl').count(),11);
        assert.equal(await page.locator('.divida-historico-linha-dcl').count(),10);
        await page.locator('.divida-historico-ano[data-ano="2015"] text').last().click();
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /0,00/);
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /Não disponível/);
        await page.evaluate(p => renderizarVisaoFiscal(p),painel);
        await page.evaluate(p => {
            p.capag.valor = 'C';
            p.capag.indicadores.endividamento.nota = 'D';
            p.capag.indicadores.poupanca_corrente.nota = 'N.D.';
            renderizarVisaoFiscal(p);
        }, JSON.parse(JSON.stringify(painel)));
        assert.match(await page.locator('.capag-destaque .capag-selo').textContent(), /! Nota C/);
        assert.match(await page.locator('.capag-indicador.capag-desfavoravel .capag-selo').textContent(), /! Nota D/);
        assert.equal(await page.locator('.capag-indicador.capag-sem-nota').count(), 1);
        await page.evaluate(p => renderizarVisaoFiscal(p), painel);
        assert.equal(await page.locator('.capag-cabecalho h2').textContent(),'Nota CAPAG');
        assert.equal(await page.locator('.capag-destaque h2, .capag-info, .capag-tooltip').count(),0);
        assert(await page.locator('.capag-subtitulo').isVisible());
        assert.match(await page.locator('.capag-subtitulo').textContent(), /Os entes federativos.*1\.583, de 13 de dezembro de 2023/);
        assert.equal(await page.locator('.capag-conjunto > .capag-cabecalho').count(),1);
        assert.equal(await page.locator('.capag-conjunto .capag-faixa').count(),4);
        assert.equal(await page.locator('.capag-conjunto').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(255, 255, 255)');
        await page.locator('.capag-conjunto').evaluate(el=>el.scrollIntoView({block:'center'}));
        await page.locator('.capag-conjunto').screenshot({path:path.join(output,'capag-bloco-unico.png')});
        for(const [id,label] of [['nav-painel','dashboard'],['nav-limites','limites'],['nav-simulacao','simulacao']]) {
            await page.click('#'+id);
            await page.screenshot({path:path.join(output,label+'.png'),fullPage:true});
            assert.equal(await page.locator('#'+id).getAttribute('aria-current'),'page');
            assert.notEqual(await page.locator('#'+id).evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
            const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
            assert(!overflow, 'Rolagem horizontal em '+label);
        }
        await page.click('#nav-simulacao');
        assert.equal(await page.locator('#form-simulacao legend').count(),0);
        assert(await page.locator('#fator-rcl').isVisible());
        assert(await page.locator('#fator-rcl').evaluate(el => Boolean(el.compareDocumentPosition(document.querySelector('#form-simulacao > details')) & Node.DOCUMENT_POSITION_FOLLOWING)));
        await page.locator('#form-simulacao > details:has(#operacao-premissas-indexador) summary').click();
        assert(await page.locator('#form-simulacao > details:has(#operacao-premissas-indexador) p').first().isVisible());
        await page.locator('#form-simulacao > details:has(#operacao-premissas-indexador) summary').click();
        await page.locator('#secao-simulacao .simulacao-formulario').screenshot({path:path.join(output,'simulacao-campos-organizados.png')});
        assert.equal(await page.locator('#nav-configuracoes').count(),0);
        await page.evaluate(()=>mostrarSecao('secao-configuracoes'));
        await page.click('#openDbConfigModalBtn');
        await page.locator('#dbConfigFields').waitFor({state:'visible'});
        assert.match(await page.locator('#dbConfigFields').innerText(), /cache JSON/);
        assert.equal(await page.locator('#dbType').count(), 0);
        await page.screenshot({path:path.join(output,'modal-configuracao.png')});
        await page.click('#closeDbConfigModalBtn');
        await page.click('#openMonitoringModalBtn');
        await page.locator('#monitoringModal').waitFor({state:'visible'});
        await page.screenshot({path:path.join(output,'modal-monitoramento.png')});
        await page.click('#closeMonitoringModalBtn');
        await page.click('#nav-painel');
        await page.locator('#nav-painel').blur();
        await page.screenshot({path:path.join(output,'dashboard-viewport.png')});
        await page.setViewportSize({width:390,height:844});
        for(const id of ['nav-painel','nav-limites','nav-simulacao']) {
            await page.click('#'+id);
            assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2), 'Rolagem horizontal em tela pequena: '+id);
        }
        await page.click('#nav-painel');
        await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
        await page.click('#nav-simulacao');
        await page.fill('#valor-requisitado','1.000,00');
        assert.equal(await page.inputValue('#moeda-entrada'),'BRL');
        await page.selectOption('#moeda-global','USD');
        await page.waitForFunction(()=>!document.getElementById('moeda-global').disabled);
        assert.equal(await page.inputValue('#moeda-entrada'),'USD');
        assert.match(await page.inputValue('#valor-requisitado'),/200,00/);
        assert.match(await page.locator('label[for="valor-requisitado"]').textContent(),/USD/);
        assert.match(await page.locator('#valor-requisitado + small').textContent(),/1\.000,00/);
        for(const aba of ['nav-painel','nav-limites','nav-simulacao']) {
            await page.click('#'+aba);
            assert(await page.locator('#moeda-global').isVisible());
            assert(await page.locator('#moeda-global').evaluate(el=>{const r=el.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth && r.top>=0;}));
            assert.equal(await page.inputValue('#moeda-global'),'USD');
        }
        await page.selectOption('#moeda-global','BRL');
        await page.waitForFunction(()=>!document.getElementById('moeda-global').disabled);
        assert.match(await page.inputValue('#valor-requisitado'),/1\.000,00/);
        await page.selectOption('#moeda-entrada','BRL');
        await page.waitForFunction(()=>!document.getElementById('moeda-entrada').disabled);
        await page.selectOption('#moeda-global','USD');
        await page.waitForFunction(()=>!document.getElementById('moeda-global').disabled);
        assert.equal(await page.locator('#moeda-global').inputValue(),'USD');
        assert.match(await page.locator('#valor-requisitado').inputValue(), /200,00/);
        assert.match(await page.locator('label[for="valor-requisitado"]').textContent(), /USD/);
        await page.selectOption('#moeda-entrada','USD');
        await page.waitForFunction(()=>!document.getElementById('moeda-entrada').disabled);
        assert.match(await page.locator('#valor-requisitado').inputValue(),/200,00/);
        await page.selectOption('#moeda-entrada','BRL');
        await page.waitForFunction(()=>!document.getElementById('moeda-entrada').disabled);
        assert.equal(await page.inputValue('#moeda-global'),'BRL');
        await page.selectOption('#moeda-entrada','USD');
        await page.waitForFunction(()=>!document.getElementById('moeda-entrada').disabled);
        assert.equal(await page.inputValue('#moeda-global'),'USD');
        assert.match(await page.locator('#cambio-estado').textContent(), /1 USD = R\$/);
        assert.equal(await page.evaluate(()=>CambioUI.referencia().id),'USD');
        await page.click('#nav-painel');
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /US\$/);
        assert.match(await page.locator('.divida-historico-detalhe').textContent(), /R\$/);
        assert.equal(await page.locator('#cambio-duplo').count(),0);
        assert.match(await page.evaluate(()=>CambioUI.formatar(1000)), /R\$.*1\.000,00.*US\$.*200,00/);
        assert.match(await page.evaluate(()=>CambioUI.formatar(-1000)), /-R\$.*1\.000,00.*-US\$.*200,00/);
        // Monetary conversion must retain the native table grid.
        await page.evaluate(()=>{
            const table=document.createElement('table');table.id='teste-grade-moedas';table.style.width='100%';
            table.innerHTML='<thead><tr><th>Ano</th><th>Total</th><th>RCL</th><th>Percentual</th></tr></thead><tbody><tr><td>2026</td><td>R$ 1.000,00</td><td>R$ 5.000,00</td><td>20%</td></tr><tr><td>2027</td><td>R$ 2.000,00</td><td>R$ 6.000,00</td><td>33%</td></tr></tbody>';
            document.body.append(table);
        });
        await page.waitForFunction(()=>document.querySelectorAll('#teste-grade-moedas td.valor-duas-moedas').length===4);
        const grade=await page.locator('#teste-grade-moedas').evaluate(table=>({
            displays:[...table.querySelectorAll('td.valor-duas-moedas')].map(td=>getComputedStyle(td).display),
            linhas:[...table.rows].map(row=>[...row.cells].map(cell=>({x:cell.getBoundingClientRect().x,width:cell.getBoundingClientRect().width})))
        }));
        assert.ok(grade.displays.every(display=>display==='table-cell'));
        for(const row of grade.linhas.slice(1)) row.forEach((cell,i)=>{
            assert.ok(Math.abs(cell.x-grade.linhas[0][i].x)<1);
            assert.ok(Math.abs(cell.width-grade.linhas[0][i].width)<1);
        });
        await page.locator('#teste-grade-moedas').evaluate(table=>table.remove());

        assert.match(await page.locator('.divida-historico-svg').getAttribute('aria-label'), /BRL/);
        assert.match(await page.locator('.divida-historico-svg').getAttribute('aria-label'), /USD/);
        assert.equal(await page.locator('.divida-historico-ponto-dcl').count(),12);
        await page.evaluate(p=>{
            const teste=structuredClone(p);
            teste.fluxo_credito={ano:2026,percentualLimite:16,positionOnly:true,parameterValidated:true,rows:[{ano:2026,dadosCompletos:false,rclProjetada:50000000000,tetoAnual:8000000000}]};
            teste.margemPublica={status:'Referência pública',snapshot:{numeroPvl:'PVL teste'},rows:[{ano:2026,tetoAnual:8000000000,scheduledDisbursements:1000000000,margemEstimada:7000000000}]};
            painelFiscalAtual=teste;renderizarVisaoFiscal(teste);
        },painel);
        await page.click('#nav-limites');
        await page.waitForFunction(()=>document.querySelector('#painel-limites .margem-valor-principal strong small')?.textContent.includes('US$'));
        assert.match(await page.locator('#painel-limites .margem-valor-principal strong > span').textContent(),/R\$.*7\.000\.000\.000,00/);
        assert.match(await page.locator('#painel-limites .margem-valor-principal strong > small').textContent(),/US\$.*1\.400\.000\.000,00/);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true);
        await page.setViewportSize({width:1440,height:1000});
        await page.evaluate(()=>window.scrollTo(0,0));
        await page.locator('#painel-limites .margem-credito').screenshot({path:path.join(output,'limites-real-e-dolar.png')});

        await page.click('#nav-simulacao');
        assert.equal(await page.evaluate(()=>localStorage.getItem('simulador.moeda')),'USD');
        await page.selectOption('#moeda-global','JPY');
        await page.waitForFunction(()=>!document.getElementById('moeda-global').disabled);
        assert.equal(await page.locator('#moeda-global').inputValue(),'USD');
        assert.match(await page.locator('#cambio-estado').textContent(), /indisponível/);
        await page.selectOption('#moeda-global','BRL');
        await page.waitForFunction(()=>!document.getElementById('moeda-global').disabled);
        assert.match(await page.locator('#valor-requisitado').inputValue(), /1\.000,00/);
        assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2));
        await page.selectOption('#moeda-entrada','BRL');
        await page.waitForFunction(()=>!document.getElementById('moeda-entrada').disabled);
        await page.selectOption('#moeda-global','USD');
        await page.waitForFunction(()=>!document.getElementById('moeda-global').disabled);
        assert.match(await page.inputValue('#valor-requisitado'),/200,00/);
        await page.selectOption('#moeda-global','JPY');
        await page.waitForFunction(()=>!document.getElementById('moeda-global').disabled);
        assert.equal(await page.inputValue('#moeda-global'),'USD');
        assert.equal(await page.inputValue('#moeda-entrada'),'USD');
        assert.match(await page.inputValue('#valor-requisitado'),/200,00/);
        await page.selectOption('#moeda-entrada','USD');
        await page.waitForFunction(()=>!document.getElementById('moeda-global').disabled);
        assert.deepEqual(await page.locator('#moeda-entrada option').allTextContents(),await page.locator('#moeda-global option').allTextContents());
        assert.equal(await page.locator('#moeda-entrada-estado').isVisible(),false);
        assert.equal(await page.locator('#moeda-entrada option[value="GLOBAL"]').count(),0);
        await page.evaluate(()=>window.scrollTo(0,0));
        await page.evaluate(()=>mostrarMensagem('Verificação do seletor de moeda','success'));
        assert(await page.getByText('Verificação do seletor de moeda',{exact:true}).evaluate(el=>el.getBoundingClientRect().top>=document.querySelector('.app-topbar').getBoundingClientRect().bottom));
        await page.screenshot({path:path.join(output,'moeda-topo-integrada.png')});
        assert.deepEqual(errors,[]);
        console.log('Interface: três abas públicas em 1440px e 390px; recursos técnicos preservados sem acesso pelo menu.');
    } finally { if(browser) await browser.close(); server.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
