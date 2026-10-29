const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
async function testar() {
    let consulta = 0;
    const pendentes = [];
    let painel = {exercicio:2026};
    const ctx = vm.createContext({console, document:{addEventListener(){},getElementById(){
        return {classList:{contains:()=>true}};
    }},eel:{obter_painel_fiscal_py:()=>async()=>({status:'sucesso',painel}),
        obter_comprometimento_sadipem_py:()=>()=>{consulta++;return new Promise(resolve=>pendentes.push(resolve));}}});
    vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/web/js/eel-main.js'),'utf8'),ctx);
    const exibidos=[];
    ctx.renderizarPainelFiscal = p=>exibidos.push(p);
    ctx.renderizarVisaoFiscal = ()=>{};
    assert(ctx.mesmaBaseMargemPublica({exercicio:2026,ultima_consulta:'antiga'},
        {exercicio:2026,ultima_consulta:'nova'}),'Data de consulta isolada não invalida a margem');
    assert(!ctx.mesmaBaseMargemPublica({exercicio:2026,rcl:{valor:100,periodo:3}},
        {exercicio:2026,rcl:{valor:100,periodo:4}}),'Novo período fiscal invalida a margem');
    assert(!ctx.mesmaBaseMargemPublica({exercicio:2026,fluxo_credito:{rows:[{ano:2026,rclProjetada:100}]}},
        {exercicio:2026,fluxo_credito:{rows:[{ano:2026,rclProjetada:110}]}}),
        'Nova projeção invalida a margem mesmo com o mesmo exercício');
    await ctx.carregarPainelFiscal();
    assert.equal(consulta,1,'Dashboard deve iniciar SADIPEM mesmo com Limites oculto');
    assert.equal(exibidos.length,1,'Dados fiscais aparecem antes da resposta SADIPEM');
    const andamento = ctx.carregarSadipemLimites();
    assert.equal(consulta,1,'Navegação não duplica consulta em andamento');
    pendentes.shift()({status:'sucesso',sadipem:{snapshot:{idPleito:1}},margemPublica:{status:'Referência pública'},pagamentosDivida:{status:'Disponível',pagamentos:{2026:'20'}}});
    await andamento;
    assert.equal(painel.pagamentosDivida.pagamentos[2026],'20');
    await ctx.carregarSadipemLimites();
    assert.equal(consulta,1,'Navegação reutiliza os dados já carregados');
    painel={exercicio:2026};
    await ctx.carregarPainelFiscal();
    assert.equal(consulta,1,'Atualização da mesma base não apaga nem reconsulta a margem');
    assert.equal(exibidos.at(-1).pagamentosDivida.pagamentos[2026],'20');
    assert.equal(exibidos.at(-1).margemPublica.status,'Referência pública',
        'Margem permanece disponível desde a primeira renderização da atualização');
    painel={exercicio:2026,rcl:{valor:200,periodo:4}};
    await ctx.carregarPainelFiscal();
    assert.equal(consulta,2,'Mudança da RCL exige atualizar a margem SADIPEM');
    const antigo=painel;
    painel={exercicio:2027};
    await ctx.carregarPainelFiscal();
    pendentes.shift()({status:'sucesso',sadipem:{snapshot:{idPleito:2}},margemPublica:{status:'Referência pública'}});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(consulta,3,'Painel substituído recebe sua própria consulta');
    assert.equal(painel.sadipem,undefined,'Resposta antiga não é aplicada no painel novo');
    assert.equal(antigo.sadipem,undefined);
    const ultima=ctx.carregarSadipemLimites();
    pendentes.shift()({status:'sucesso',sadipem:{snapshot:{idPleito:3}},margemPublica:{status:'Referência pública'}});
    await ultima;
    assert.equal(painel.sadipem.snapshot.idPleito,3);
    console.log('SADIPEM no Dashboard: início automático, dados fiscais imediatos, reuso e descarte de resposta antiga validados.');
}
testar().catch(e=>{console.error(e);process.exitCode=1;});
