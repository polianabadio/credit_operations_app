/* Verificação visual isolada: fixtures locais, sem API ou banco reais. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../src/web');
const output = path.resolve(__dirname, '../.ui-preview');
const painel = {
    exercicio: 2026, ultima_consulta: '2026-10-28T16:00:00', dados_disponiveis: 10,
    rcl: {valor: 47000000000, ano: 2026, periodo: 4, anexo: 'RREO-Anexo 03', origem: 'SICONFI/RREO'},
    capag: {valor: 'B+', ano: 2025, ano_base: 2024, origem: 'Tesouro Transparente/CAPAG', indicadores: {
        endividamento: {valor: 65.53, nota: 'B'}, poupança: {},
        poupanca_corrente: {valor: 86.28, nota: 'B'}, liquidez_relativa: {valor: 12.95, nota: 'A'}
    }},
    dcl: {valor: 43.3, limite: 200, ano: 2026, periodo: 2, origem: 'SICONFI/RGF'},
    caed: {valor: 3.69, limite: 11.5, ano: 2025, periodo: 6, origem: 'SICONFI/RREO', periodicidade: 'B', historico: true, natureza: 'servico_realizado'},
    dtp: {valor: 43, limite: 60, ano: 2026, periodo: 2},
    limites_referencia: {'DCL/RCL': 200, 'CAED/RCL': 11.5, 'Limite de 16%': 16}, fontes: [],
    regra_ouro: [{ano: 2025, situacao: 'Atendida'}, {ano: 2026, dados_calculados: {limite_disponivel: 6500000000, fontes: []}}]
};
const stub = `const painelFixture=${JSON.stringify(painel)};
window.eel=new Proxy({}, {get(_,nome){ if(nome==='_websocket') return null; return (...args)=>async()=>{
if(nome==='obter_dados_iniciais') return {status:'sucesso',anos_disponiveis:[2026,2025]};
if(nome==='obter_fator_projecao_py') return '2.031208231';
if(nome==='obter_painel_fiscal_py') return {status:'sucesso',painel:painelFixture};
if(nome==='iniciar_atualizacao_siconfi') return {running:false,falhas:0};
if(nome==='obter_comprometimento_sadipem_py') return {status:'erro'};
if(nome==='get_system_status_py') return {database:{status:'Online',mensagem:'Conexão disponível'},resources:{cpu_percent:'1',memory_mb:'100'}};
if(nome==='get_db_config') return {type:'sqlite',path:'instance/database.db'};
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
        for(const [id,label] of [['nav-painel','dashboard'],['nav-limites','limites'],['nav-simulacao','simulacao']]) {
            await page.click('#'+id);
            await page.screenshot({path:path.join(output,label+'.png'),fullPage:true});
            assert.equal(await page.locator('#'+id).getAttribute('aria-current'),'page');
            assert.notEqual(await page.locator('#'+id).evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
            const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
            assert(!overflow, 'Rolagem horizontal em '+label);
        }
        assert.equal(await page.locator('#nav-configuracoes').count(),0);
        await page.evaluate(()=>mostrarSecao('secao-configuracoes'));
        await page.click('#openDbConfigModalBtn');
        await page.locator('#db_path').waitFor({state:'visible'});
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
        assert.deepEqual(errors,[]);
        console.log('Interface: três abas públicas em 1440px e 390px; recursos técnicos preservados sem acesso pelo menu.');
    } finally { if(browser) await browser.close(); server.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
