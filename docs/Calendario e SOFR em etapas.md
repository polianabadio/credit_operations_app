# Calendário contratual e SOFR em etapas

O cálculo por etapas utiliza datas explícitas de assinatura, vigência e primeira liberação. A minuta fornecida pelo usuário descreve os vencimentos e o início dos encargos, mas não fixa a data definitiva de assinatura nem a trajetória de taxas que gerou o CSV. Reproduzir as regras não comprova igualdade com aquele cronograma.

## Entradas e datas

Nas liberações anuais, a data da primeira liberação e a soma da carência com a amortização permitem calcular o término durante o preenchimento. Se assinatura ou vigência ficarem em branco, o cenário usa a data da primeira liberação. Se o primeiro vencimento ficar em branco, o cenário usa a vigência acrescida da periodicidade de juros, limitada pelo prazo e pela carência quando houver. Datas informadas prevalecem sobre essas hipóteses. O dia e os meses dos próximos vencimentos seguem o primeiro vencimento e a periodicidade escolhida. Para reproduzir o calendário da minuta BID, informe o primeiro vencimento após a vigência, em março ou setembro.

- Prazo nominal final: assinatura + carência/amortização nominais somadas, em meses.
- Fim da carência: vigência + meses de carência.
- Primeira amortização: vencimento de juros coincidente ou imediatamente anterior ao fim da carência; sem carência, primeiro vencimento.
- Última amortização: vencimento de juros coincidente ou imediatamente anterior ao fim nominal.
- Amortizações coincidem com datas de juros; periodicidades precisam ser compatíveis.
- Ajustes de fim de mês mantêm a âncora original do calendário. Não há ajuste adicional de vencimento bancário por feriados.
- Comissão começa na assinatura + dias informados. O padrão editável de 60 dias vem do art.3.08 da minuta, não de regra geral para todos os empréstimos.
- Prazo de desembolsos contado da vigência: padrão editável de 60 meses, conforme cláusula 2.04 da minuta.
- Primeira liberação tem sua própria data; demais liberações anuais permanecem no dia 15 do mês escolhido. Essa distribuição é hipótese editável, não um calendário histórico recuperado.

`calendario_contratual.py` valida datas e gera vencimentos; `fluxo_contratual.py` calcula o fluxo. A prévia JS serve apenas para exibir o ano efetivo e o prazo nominal: o backend recalcula e rejeita divergências.

## Projeção SOFR

O formulário usa por padrão **Juros simples sobre a taxa total**, com base inicial de 365 dias. Em cada intervalo, aplica ao saldo desembolsado a soma da SOFR, taxa fixa adicional e spreads de captação e capital, proporcionalmente aos dias e à base escolhida. O pagamento de juros é arredondado em centavos. A base de 365 dias reproduz a fórmula corrigida da planilha PROFISCO III. A reprodução integral do exemplo também requer os desembolsos semestrais, a comissão e o agrupamento anual usados naquela planilha.

A opção **SOFR composta + spreads simples** mantém a projeção descrita a seguir e fixa a base em 360 dias.

A definição 106 da Parte II descreve a taxa a partir da razão dos Índices SOFR inicial/final: `(I_final/I_inicial - 1) × 360/dias`. O artigo 3.07 também prevê estimativas e ajustes pelo Agente de Cálculo. A aplicação não dispõe dessas estimativas originais nem de taxas futuras publicadas para todo o horizonte.

No cenário de etapas, `metodo_sofr=composta_projetada` gera um índice sintético mantendo a taxa overnight escolhida constante. Para n dias, o fator é `(1 + SOFR/100/360)^n`. A parcela SOFR compõe diariamente até o pagamento; taxa fixa adicional e spreads são acrescidos como juros simples separados por dias/360. Eventos de desembolso e amortização segmentam os intervalos; nada é arredondado antes dos pagamentos. A memória identifica a projeção, a taxa escolhida e os fatores dos trechos. Não apresentar o índice sintético como série histórica, previsão publicada ou Term SOFR de seis meses.

Comissão não compõe a SOFR: incide somente sobre principal não desembolsado após seu início, paga nos vencimentos de juros. Outros encargos anuais continuam separados. Todos são somados uma vez ao fluxo que alimenta CAED, preservando os critérios fiscais e a cobertura das demais dívidas.

## Conferência do exemplo

Hipótese de teste (não uma data comprovada do contrato): assinatura/vigência/primeira liberação em 15/07/2026, primeiro juros em 15/09/2026, carência 72 meses, amortização nominal 222, total 294. O calendário gera primeira amortização em 15/03/2032, última em 15/09/2050, fim nominal em 15/01/2051, 38 amortizações e 49 pagamentos de juros.

Com principal USD 90.366.254,00, liberações anuais do CSV, SOFR projetada constante 3,69%, spread total 1,21%, comissão 0,75% após 60 dias e sem outros encargos, a conferência diária independente em USD resulta em:

| Componente | USD |
|---|---:|
| Juros financeiros | 55.748.822,76 |
| Comissão | 1.672.392,48 |
| Juros + comissão | 57.421.215,24 |
| Principal | 90.366.254,00 |

Isso **não** coincide com USD 44.183.403,78 de encargos do CSV. As regras documentadas foram testadas; não se infere que os parâmetros originais do CSV foram descobertos. Não ajustar spread/taxa apenas para coincidir. Conversão anterior para BRL e arredondamento dos pagamentos em BRL pode gerar diferença de centavos em relação a converter os totais já arredondados em USD.

## Compatibilidade e testes

Em **Liberação fracionada → Por semestre**, a data da primeira liberação ancora os semestres de seis meses. A carência e o prazo total devem ser múltiplos de seis meses. Informe o principal e as liberações na moeda da operação. O cálculo arredonda juros, comissão e amortização em centavos nessa moeda. Aplica a taxa total em dias corridos/365, cobra metade da comissão anual a cada semestre sobre o saldo a liberar após o desembolso e amortiza o saldo de abertura dividido pelas parcelas restantes a partir do final da carência. A comparação agrupa os semestres pelo ano de início. A avaliação fiscal recebe as liberações pelo ano do desembolso e os pagamentos em reais pelo ano de vencimento. A planilha PROFISCO III corrigida fecha em USD 148.671.858,03, com 49 semestres e 38 amortizações.

IPCA/TLP e os demais modos de liberação única preservam o fluxo anterior. A memória do FCL está disponível também no resumo da simulação. Payloads legados sem `calendario_pagamentos=fixo` mantêm aniversários e SOFR simples. A interface usa o calendário explícito nas liberações anuais em etapas. Não existe entrada de cronograma pronto.

`tests/test_calendario_minuta.py` confere calendário, atrasos da comissão, inconsistências, âncora de fim de mês, fórmulas fechadas e o benchmark diário independente. `tests/test_fluxo_tlp.py` preserva a conferência com o fixture Excel. Os testes de moedas verificam equivalência BRL/USD; o navegador executa a simulação com o motor Python real e verifica invalidação e telas móveis. Nenhum teste importa `app.py` sem dados isolados.
