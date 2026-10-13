"""Verificação opcional da tabela real com Playwright e Chrome instalado.

Executar: python tests/browser_mga.py (não depende do banco de produção).
"""
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def validar():
    html = (ROOT / 'src/web/main.html').read_text(encoding='utf-8')
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<link\b[^>]*>', '', html)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page()
        page.route('http://credit.test/**', lambda route: route.fulfill(body=html, content_type='text/html'))
        page.goto('http://credit.test/')
        page.add_style_tag(path=str(ROOT / 'src/web/css/styles.css'))
        page.add_script_tag(content="""
            function formatarMoeda(v) { return new Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'}).format(v); }
            function formatarPercentual(v) { return v.toFixed(2) + '%'; }
        """)
        page.add_script_tag(path=str(ROOT / 'src/web/js/fiscal-dashboard.js'))
        page.evaluate("""() => {
            document.getElementById('secao-simulacao').classList.remove('hidden');
            const p = {globalStatus:'Não Enquadrado', dataAvailability:true, criticalYear:2027,
              maxMgaRcl:.17, maxLimitUsage:1.0625, exceededYears:[2027], message:'Excesso em 2027',
              rows:[{ano:2026,requestedOperation:0,scheduledDisbursements:0,mga:0,rclProjetada:1000,mgaRcl:0,limitUsage:0,situacao:'Enquadrado'},
                    {ano:2027,requestedOperation:170,scheduledDisbursements:0,mga:170,rclProjetada:1000,mgaRcl:.17,limitUsage:1.0625,situacao:'Não Enquadrado'}]};
            document.getElementById('fluxo-credito-resultado').appendChild(criarTabelaMga(p));
        }""")
        for width in (375, 1280):
            page.set_viewport_size({'width': width, 'height': 900})
            page.locator('#fluxo-credito-resultado').scroll_into_view_if_needed()
            assert page.locator('.mga-tabela tbody tr').count() == 2
            assert page.locator('.mga-ano-critico').inner_text().startswith('2027')
            assert page.locator('.mga-ano-critico').evaluate('(e) => getComputedStyle(e).backgroundColor') == 'rgb(254, 242, 242)'
            assert 'Total de liberações (MGA)' in page.locator('.mga-tabela').inner_text()
            assert 'Saldo após a operação' in page.locator('.mga-tabela').inner_text()
            assert 'Uso do limite' not in page.locator('.mga-tabela').inner_text()
            overflow = page.locator('.mga-tabela-rolagem').evaluate('(e) => ({width:e.clientWidth,scroll:e.scrollWidth})')
            if width == 375:
                assert overflow['scroll'] > overflow['width']
                assert overflow['width'] <= width
            print(f'Tabela validada em {width}px.')
        # Limites apresenta margem anterior à nova operação, usando o DTO de posição.
        page.evaluate("""() => {
            window.dadoMargem = {limite:16,fluxo:{ano:2026,positionOnly:true,parameterValidated:true,
                rows:[{ano:2026,dadosCompletos:true,margemEstimada:60,scheduledDisbursements:100,
                    tetoAnual:160,rclProjetada:1000}]}};
            const destino = document.getElementById('painel-limites');
            destino.closest('section').classList.remove('hidden');
            destino.replaceChildren(criarResumoLimite(LIMITES_PRINCIPAIS[0],window.dadoMargem),
                criarDetalheLimitePagina(LIMITES_PRINCIPAIS[0],window.dadoMargem,2026));
        }""")
        margem = page.locator('#painel-limites')
        assert 'Margem disponível no exercício' in margem.inner_text()
        assert 'R$ 60,00' in margem.inner_text().replace('\xa0', ' ')
        assert 'MGA =' not in margem.inner_text()
        assert 'Operação pleiteada' not in margem.inner_text()
        for width in (375,1280):
            page.set_viewport_size({'width':width,'height':900})
            assert margem.locator('tbody tr').count() == 1
            dimensoes = margem.locator('.mga-tabela-rolagem').evaluate('(e)=>({width:e.clientWidth,scroll:e.scrollWidth})')
            if width == 375:
                assert dimensoes['width'] <= width
                assert dimensoes['scroll'] > dimensoes['width']
        for valor in (0,-20):
            page.evaluate("""valor => {
                window.dadoMargem.fluxo.rows[0].margemEstimada = valor;
                document.getElementById('painel-limites').replaceChildren(criarResumoLimite(LIMITES_PRINCIPAIS[0],window.dadoMargem));
            }""",valor)
            assert ('R$ 0,00' if valor == 0 else '-R$ 20,00') in margem.inner_text().replace('\xa0', ' ')
        page.evaluate("""() => {
            window.dadoMargem.fluxo.parameterValidated=false;
            document.getElementById('painel-limites').replaceChildren(criarResumoLimite(LIMITES_PRINCIPAIS[0],window.dadoMargem));
        }""")
        assert 'Não determinada' in margem.inner_text()
        page.evaluate("""() => {
            window.dadoMargem.fluxo.parameterValidated=true;
            window.dadoMargem.fluxo.rows[0].dadosCompletos=false;
            window.dadoMargem.margemPublica={status:'Referência pública',coverageConfirmed:false,
                snapshot:{numeroPvl:'PVL02.001127/2026-73',data:'30/07/2026'},
                motivos:['Cobertura atual não confirmada'],rows:[{ano:2026,margemEstimada:160,
                    scheduledDisbursements:0,rclProjetada:1000,tetoAnual:160,liberacoesContratadas:0,
                    liberacoesNaoContratadasListadas:0,fonteZero:'indicador_liberacoes=0'}]};
            document.getElementById('painel-limites').replaceChildren(
                criarResumoLimite(LIMITES_PRINCIPAIS[0],window.dadoMargem),
                criarDetalheLimitePagina(LIMITES_PRINCIPAIS[0],window.dadoMargem,2026));
        }""")
        assert 'Margem segundo o PVL' in margem.inner_text()
        assert 'R$ 160,00' in margem.inner_text().replace('\xa0',' ')
        assert 'indicador_liberacoes=0' in margem.inner_text()
        assert 'PVL02.001127/2026-73' in margem.inner_text()
        assert 'conferir cobertura' in margem.inner_text()
        print('Saldo público SADIPEM validado: valor, zero declarado, PVL e ressalva.')
        page.locator('#painel-limites').evaluate('(e)=>e.replaceChildren()')
        print('Margem em Limites validada: positiva, zero, negativa, ausente e 375/1280px.')
        page.add_script_tag(path=str(ROOT / 'src/web/js/eel-main.js'))
        page.evaluate("""() => {
            window.chamadasSimulacao = [];
            window.initializeDbConfigComponent = () => {};
            window.mostrarMensagem = (texto) => { window.ultimaMensagem = texto; };
            window.eel = {
                salvar_fator_projecao_py: fator => async () => ({status:'sucesso', fator}),
                analisar_operacao_py: (...args) => async () => {
                    window.chamadasSimulacao.push(args);
                    return {status:'Análise completa.', regras_ordenadas:[],
                        mgaProjection: {globalStatus:'Enquadrado', dataAvailability:true,
                          evaluationScope:'requested_operation_only', requestedTotal:args[1],
                          criticalYear:args[0], maxMgaRcl:.08, maxLimitUsage:.5, exceededYears:[],
                          ano:args[0], rows:[{ano:args[0],requestedOperation:args[1],scheduledDisbursements:0,
                            mga:args[1],rclProjetada:1000,tetoAnual:160,margemEstimada:160-args[1],
                            mgaRcl:.08,limitUsage:.5,situacao:'Enquadrado'}]}};
                }
            };
            document.getElementById('ano').innerHTML = '<option value="2026">2026</option>';
            document.getElementById('ano-fim-contrato').innerHTML = '<option value="2027">2027</option>';
            document.getElementById('fator-rcl').value = '1.10';
            document.getElementById('valor-requisitado').value = 'R$ 80,00';
            configurarEventListeners();
            montarLinhasServico();
            sincronizarCronogramaMga();
            mostrarSecao('secao-simulacao');
        }""")
        assert page.locator('#nav-analise').count() == 0
        assert page.locator('#secao-analise').count() == 0
        assert page.locator('#secao-simulacao #tabela-resultados-container').count() == 1
        assert page.locator('#mga-ano-inicio').input_value() == '2026'
        assert page.locator('#mga-ano-fim').input_value() == '2026'
        assert page.locator('#fluxo-credito-linhas input').input_value() == '80'
        await_result = page.evaluate('async () => { await executarSimulacao(); return window.chamadasSimulacao; }')
        assert len(await_result) == 1
        assert await_result[0][0:2] == [2026, 80]
        assert await_result[0][3]['rows'][0]['liberacaoNovaOperacao'] == 80
        assert await_result[0][3]['projectionParameter']['value'] == '1.10'
        assert await_result[0][3]['projectionParameter']['unit'] == 'percent'
        assert page.locator('#mga-parametro-valor').count() == 0
        page.locator('#fator-rcl').fill('2,5%')
        assert page.evaluate('obterEntradaMga().projectionParameter.value') == '2.5'
        page.locator('#fator-rcl').fill('1.10')
        assert page.locator('#fluxo-credito-resultado table').count() == 0
        assert 'Liberações de crédito — limite de 16%' in page.locator('#tbody-resultados').inner_text()
        page.locator('#tbody-resultados .ver-detalhes-btn').last.click()
        assert 'Valor requisitado: R$' in page.locator('#modal-dados-calculados').inner_text()
        assert page.locator('#modal-dados-calculados .mga-tabela').count() == 1
        assert page.locator('#modal-dados-calculados .mga-tabela tbody tr').evaluate('(e) => getComputedStyle(e).backgroundColor') == 'rgb(240, 253, 244)'
        page.locator('#btn-fechar-modal').click()
        page.locator('#tbody-resultados .ver-detalhes-btn').last.click()
        assert page.locator('#mga-ano-inicio').is_visible()
        assert page.locator('#mga-inicio-rotulo').inner_text() == 'Primeiro ano de liberação'
        assert page.locator('#mga-ano-fim').is_visible()
        page.locator('#mga-ano-inicio').fill('')
        page.locator('#mga-ano-inicio').dispatch_event('change')
        assert page.locator('#mga-ano-fim').is_disabled()
        assert page.locator('#fluxo-credito-linhas input').count() == 0
        page.locator('#mga-ano-inicio').fill('2026')
        page.locator('#mga-ano-inicio').dispatch_event('change')
        assert page.locator('#mga-ano-fim').is_enabled()
        assert page.locator('#mga-ano-fim').get_attribute('min') == '2026'
        page.locator('#mga-ano-fim').fill('2028')
        page.locator('#mga-ano-fim').dispatch_event('change')
        assert page.locator('#mga-ano-inicio').input_value() == '2026'
        assert page.locator('#mga-ano-fim').input_value() == '2028', page.evaluate("({inicio:document.getElementById('mga-ano-inicio').value,fim:document.getElementById('mga-ano-fim').value,modo:document.getElementById('mga-cronograma-modo').value})")
        assert page.locator('#fluxo-credito-linhas input').count() == 3
        page.locator('#fluxo-credito-linhas input').nth(1).fill('25')
        page.locator('#mga-ano-inicio').fill('2027')
        page.locator('#mga-ano-inicio').dispatch_event('change')
        assert page.locator('#mga-ano-fim').input_value() == '2028', page.evaluate("({inicio:document.getElementById('mga-ano-inicio').value,fim:document.getElementById('mga-ano-fim').value,modo:document.getElementById('mga-cronograma-modo').value})")
        assert page.locator('#fluxo-credito-linhas input').nth(0).input_value() == '25'
        page.locator('#mga-ano-fim').fill('2026')
        page.locator('#mga-ano-fim').dispatch_event('change')
        assert page.locator('#fluxo-credito-linhas input').count() == 0
        page.locator('#mga-ano-fim').fill('2028')
        page.locator('#mga-ano-fim').dispatch_event('change')
        page.locator('#mga-ano-inicio').fill('2026')
        page.locator('#mga-ano-inicio').dispatch_event('change')
        page.locator('#mga-ano-fim').fill('2026')
        page.locator('#mga-ano-fim').dispatch_event('change')
        assert page.locator('#fluxo-adicionar-ano').count() == 0
        page.locator('#mga-ano-fim').fill('2027')
        page.locator('#mga-ano-fim').dispatch_event('change')
        assert page.locator('#fluxo-credito-linhas input').count() == 2
        page.locator('#fluxo-credito-linhas input').nth(0).fill('30')
        page.locator('#fluxo-credito-linhas input').nth(1).fill('50')
        assert 'desatualizados' in page.locator('#simulacao-atualidade').inner_text()
        assert page.locator('#btn-relatorio-simulacao').is_disabled()
        entrada = page.evaluate('obterEntradaMga()')
        assert [linha['liberacaoNovaOperacao'] for linha in entrada['rows']] == [30, 50]
        page.locator('#btn-fechar-modal').click()
        page.evaluate('async () => { await executarSimulacao(); }')
        with page.expect_download() as download_info:
            page.locator('#btn-relatorio-simulacao').click()
        import html as html_parser
        import json
        report_html = Path(download_info.value.path()).read_text(encoding='utf-8')
        report = json.loads(html_parser.unescape(re.search(r'<pre id="memoria-relatorio">(.*?)</pre>', report_html, re.DOTALL)[1]))
        assert report['entradas']['mga']['rows'] == entrada['rows']
        assert report['resultados']['mgaProjection']['requestedTotal'] == 80
        page.locator('#valor-requisitado').fill('')
        page.evaluate('async () => { await executarSimulacao(); }')
        assert len(page.evaluate('window.chamadasSimulacao')) == 2
        assert 'Aguardando preenchimento' in page.locator('#valor-erro').inner_text()
        assert page.locator('#secao-simulacao #linhas-hipotese-1').count() == 0
        assert page.locator('#modal-feedback #linhas-hipotese-1').count() == 1
        print('Simulação única validada: mesma entrada, sem aba Análise, cronograma anual disponível.')
        browser.close()


if __name__ == '__main__':
    validar()
