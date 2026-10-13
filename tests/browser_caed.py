"""UI real do CAED com dados de teste isolados; sem Eel, banco ou HTTP reais."""
import os
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.simulador.parametros_simulacao import obter_fator_projecao
from src.simulador.servico_divida import avaliar_caed

ROOT = Path(__file__).resolve().parents[1]


def validar():
    html = (ROOT / 'src/web/main.html').read_text(encoding='utf-8')
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<link\b[^>]*>', '', html)
    fator = obter_fator_projecao('2026-12-31')
    referencia = {'valor': '100', 'exercicio': 2026, 'periodo': 6, 'data_base': '2026-12-31',
                  'uf': 'GO', 'esfera': 'E', 'ente': 52, 'origem': 'SICONFI/RREO', 'anexo': 'RREO-Anexo 03'}
    entrada = {'data_referencia': '2026-12-31', 'ano_fim_contrato': 2028,
               'linhas': [{'ano': ano, 'juros_encargos': valor, 'amortizacao': '0', 'demais_operacoes': '0'}
                          for ano, valor in [(2026, '10'), (2027, '10'), (2028, '30')]],
               'cobertura_demais': {'completa': True, 'fonte': 'Documento de teste', 'data_referencia': '2026-12-31'}}
    regra = avaliar_caed(2026, entrada, referencia, fator)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(accept_downloads=True)
        page.on('pageerror', lambda erro: print('Erro JS:', erro, flush=True))
        page.route('http://credit.test/**', lambda route: route.fulfill(body=html, content_type='text/html'))
        page.goto('http://credit.test/')
        page.add_style_tag(path=str(ROOT / 'src/web/css/styles.css'))
        page.add_script_tag(path=str(ROOT / 'src/web/js/fiscal-dashboard.js'))
        page.add_script_tag(path=str(ROOT / 'src/web/js/eel-main.js'))
        page.evaluate('([regra, fator]) => { window.regraTeste = regra; window.fatorTeste = fator; }', [regra, fator])
        page.evaluate("""() => {
            window.initializeDbConfigComponent = () => {};
            window.mostrarMensagem = mensagem => { window.ultimaMensagem = mensagem; };
            window.eel = {
                obter_fator_projecao_py: data => async () => window.fatorTeste,
                analisar_operacao_py: () => async () => ({status:'Análise completa.',
                    regras_ordenadas:[window.regraTeste], regras_cumpridas:[window.regraTeste],
                    regras_violadas:[], regras_sem_informacao:[], circuit_breaker:false,
                    mgaProjection:{verificationStatus:'Inconclusivo',globalStatus:'Indisponível',
                        dataAvailability:false,rows:[],exceededYears:[],message:'Sem inventário nesta fixture.'}})
            };
            document.getElementById('ano').innerHTML = '<option value="2026">2026</option>';
            document.getElementById('ano-fim-contrato').innerHTML = '<option value="2028">2028</option>';
            document.getElementById('caed-data-referencia').value = '2026-12-31';
            document.getElementById('valor-requisitado').value = '100,00';
            configurarEventListeners(); montarLinhasServico(); sincronizarCronogramaMga();
            mostrarSecao('secao-simulacao');
        }""")
        assert page.locator('#linhas-hipotese-2').count() == 0
        assert page.locator('#linhas-hipotese-1 input').count() == 9
        assert page.locator('#secao-simulacao #linhas-hipotese-1').count() == 0
        page.evaluate('mostrarDetalhesRegra(window.regraTeste)')
        assert page.locator('#cronograma-pagamentos').evaluate('(e) => e.open')
        for i, valor in enumerate(['10', '10', '30']):
            linha = page.locator('#linhas-hipotese-1 [data-ano]').nth(i)
            for j, pagamento in enumerate([valor, '0', '0']):
                linha.locator('input').nth(j).fill(pagamento)
        page.locator('#caed-fonte-demais').fill('Documento de teste')
        page.locator('#caed-data-cobertura').fill('2026-12-31')
        page.locator('#caed-cobertura-completa').check()
        page.evaluate('async () => { await carregarFatorCaed(); await executarSimulacao(true); }')
        assert page.locator('#btn-relatorio-simulacao').is_enabled()
        assert page.locator('#servico-resultados > section > .caed-table-scroll tbody tr').count() == 3
        conteudo = page.locator('#servico-resultados').inner_text()
        for texto in ['Operação pretendida', 'Demais operações', 'CAED total', 'Média até o término',
                      'Até 31/12/2027', 'Resultado: ATENDE', 'Fonte da RCL', 'Fator: 1.02031208231']:
            assert texto in conteudo
        assert page.locator('#servico-resultados pre').count() == 0
        for largura in (375, 1280):
            page.set_viewport_size({'width': largura, 'height': 900})
            dimensoes = page.locator('#servico-resultados > section > .caed-table-scroll').evaluate(
                '(e) => ({width:e.clientWidth, scroll:e.scrollWidth})')
            if largura == 375:
                assert dimensoes['scroll'] > dimensoes['width']
                assert dimensoes['width'] < largura
            screenshot_dir = os.getenv('CAED_SCREENSHOT_DIR')
            if screenshot_dir:
                page.screenshot(path=str(Path(screenshot_dir) / f'caed-{largura}.png'), full_page=True)
        page.locator('#btn-fechar-modal').click()
        with page.expect_download() as download_info:
            page.locator('#btn-relatorio-simulacao').click()
        relatorio = Path(download_info.value.path()).read_text(encoding='utf-8')
        assert 'Memória anual do CAED' in relatorio and 'Demais operações' in relatorio
        assert '"tipo": "servico_divida"' not in relatorio
        # Colagem programática deve invalidar relatório e confirmação de cobertura.
        page.evaluate("""() => {
            const grade = document.getElementById('linhas-hipotese-1');
            const linha = grade.querySelector('[data-ano]');
            colarPlanilhaServico({clipboardData:{getData:()=> '1,00\\t2,00\\t3,00\\n'},preventDefault(){}}, grade, linha, 0);
        }""")
        assert page.locator('#btn-relatorio-simulacao').is_disabled()
        assert not page.locator('#caed-cobertura-completa').is_checked()
        # Ausência/limitações também são visíveis no modal, com a mesma tabela.
        incompleta = avaliar_caed(2026, entrada, None, None)
        page.evaluate('(r) => mostrarDetalhesRegra(r)', incompleta)
        assert 'Resultado: INCONCLUSIVO' in page.locator('#servico-resultados').inner_text()
        assert 'RCL_AUSENTE' in page.locator('#servico-resultados').inner_text()
        print('CAED UI validada em 375/1280 px: grade única, alternativas, fontes, relatório e colagem.')
        browser.close()


if __name__ == '__main__':
    validar()
