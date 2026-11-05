# Indexadores e cotação da operação

A simulação oferece IPCA, sem indexação, TLP, CDI, Selic, SOFR e variação cambial. Não exige nome de projeto/programa nem anexação de normas.

## Taxas e fontes

- IPCA: mantém o motor FCL já implementado, série SGS 433 mensal; meses não publicados usam zero após consulta bem-sucedida. Taxa fixa e spread permanecem entradas do usuário.
- TLP: consulta a parcela fixa Jm na [SGS 27572](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarSeries&series=27572), em percentual anual, além do IPCA. A taxa Jm selecionada permanece fixa. Taxa fixa adicional e spread são fatores adicionais, sem repetir Jm. O cenário não reconstrói redutores históricos ou exceções contratuais da TLP.
- CDI: consulta [SGS 4389](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarSeries&series=4389), taxa anualizada em 252 dias úteis.
- Selic: consulta [SGS 1178](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarSeries&series=1178), Selic efetiva anualizada em 252 dias úteis, sem confundir com a meta do Copom.
- SOFR: consulta a última publicação overnight pela [API do Federal Reserve de Nova York](https://markets.newyorkfed.org/static/docs/markets-api.html), endpoint `/api/rates/secured/sofr/last/1.json`. Não é Term SOFR de seis meses. Fonte, data e valor consultado são preservados.

As referências são consultadas na seleção e no botão Atualizar; permanecem editáveis. Uma edição não é atribuída à API: a memória identifica o valor manual e conserva a referência original quando houver. Falha não vira taxa zero e não apaga um ajuste manual. Respostas de uma seleção anterior ou recebidas após edição são descartadas. Cache das taxas públicas: uma hora em memória da sessão, com data da publicação explícita.

## Hipóteses financeiras

CDI e Selic usam a taxa selecionada constante em todos os períodos; fator do trecho = [(1 + índice/100) × (1 + taxa fixa adicional/100) × (1 + spread/100)]^(dias úteis/252). Sem indexação usa índice zero explicitamente; não aplica IPCA.

SOFR é um cenário de taxa overnight constante. Taxa SOFR, taxa fixa adicional e spread são somados, com juros simples por dias corridos/360. Na carência, os dias são acumulados até o pagamento trimestral, sem composição mensal intermediária. Não há curva futura, reset semestral ou alegação de reprodução de contrato Term SOFR.

Datas, feriados, amortização mensal, juros trimestrais na carência e truncamento em centavos seguem as convenções FCL existentes. Os cenários novos não validam cláusulas de um contrato específico nem alteram as regras fiscais. Novos cálculos usam Decimal com precisão 50 e arredondamento somente nos pagamentos.

## Variação cambial

A escolha habilita moeda estrangeira e cotação contratual: reais por uma unidade da moeda. A cotação é informada pelo usuário e permanece constante em toda a simulação; não se consulta o câmbio de mercado para substituir essa entrada. O valor do empréstimo fica identificado na moeda do contrato. Ao mudar o tipo de unidade, o campo é limpo para impedir reinterpretar silenciosamente um valor em reais como moeda estrangeira.

O backend converte principal e liberações para BRL com Decimal/precisão 50 e arredonda na fronteira monetária em centavos. `valor_base_brl` e `cotacao_id` da apresentação são ignorados nessa modalidade. Origem, cotação, valor original e valor convertido ficam na memória, sem serem salvos como análise. Permite taxa fixa + spread ou SOFR + taxa fixa + spread na operação cambial.

O seletor do cabeçalho continua sendo uma unidade de apresentação global; a moeda e a cotação contratuais não são sobrescritas por ele. Assim, mudar o cabeçalho não muda o principal em BRL usado nas avaliações fiscais.

## Prazos

O usuário informa carência e prazo de amortização em meses. Prazo total nominal = carência + amortização, somente leitura. O backend recalcula e rejeita divergências ou soma acima de 600 meses; contratos legados sem o campo de amortização conservam o contrato anterior. Mantém o início da amortização no mês final da carência, conforme o FCL: não altera silenciosamente a sobreposição já documentada nem transforma o prazo nominal em outro cronograma. O ano final continua sendo conferido contra a última data calculada.
