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
            assert '106.25%' in page.locator('.mga-tabela').inner_text()
            overflow = page.locator('.mga-tabela-rolagem').evaluate('(e) => ({width:e.clientWidth,scroll:e.scrollWidth})')
            if width == 375:
                assert overflow['scroll'] > overflow['width']
                assert overflow['width'] <= width
            print(f'Tabela validada em {width}px.')
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
                          rows:[{ano:args[0],requestedOperation:args[1],scheduledDisbursements:0,
                            mga:args[1],rclProjetada:1000,mgaRcl:.08,limitUsage:.5,situacao:'Enquadrado'}]}};
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
        await_result = page.evaluate('async () => { await executarSimulacao(); return window.chamadasSimulacao; }')
        assert len(await_result) == 1
        assert await_result[0][0:2] == [2026, 80]
        assert await_result[0][3]['rows'][0]['liberacaoNovaOperacao'] == 80
        assert page.locator('#fluxo-credito-resultado table').count() == 0
        assert 'Liberações de crédito — limite de 16%' in page.locator('#tbody-resultados').inner_text()
        page.locator('#tbody-resultados .ver-detalhes-btn').last.click()
        assert 'Valor requisitado: R$' in page.locator('#modal-dados-calculados').inner_text()
        assert page.locator('#modal-dados-calculados .mga-tabela').count() == 1
        page.locator('#btn-fechar-modal').click()
        page.select_option('#mga-cronograma-modo', 'annual_schedule')
        page.locator('#fluxo-adicionar-ano').click()
        assert page.locator('#fluxo-credito-linhas input').count() == 2
        page.locator('#fluxo-credito-linhas input').nth(0).fill('30')
        page.locator('#fluxo-credito-linhas input').nth(1).fill('50')
        assert 'desatualizados' in page.locator('#simulacao-atualidade').inner_text()
        assert page.locator('#btn-relatorio-simulacao').is_disabled()
        entrada = page.evaluate('obterEntradaMga()')
        assert [linha['liberacaoNovaOperacao'] for linha in entrada['rows']] == [30, 50]
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
        assert page.locator('#secao-simulacao #linhas-hipotese-1').count() == 1
        assert page.locator('#modal-feedback #linhas-hipotese-1').count() == 0
        print('Simulação única validada: mesma entrada, sem aba Análise, cronograma anual disponível.')
        browser.close()


if __name__ == '__main__':
    validar()
