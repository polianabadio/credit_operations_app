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

No fluxo legado de liberação única, SOFR é um cenário de taxa overnight constante. Taxa SOFR, taxa fixa adicional e spread são somados, com juros simples por dias corridos/360. Na carência, os dias são acumulados até o pagamento trimestral, sem composição mensal intermediária. Não há curva futura, reset semestral ou alegação de reprodução de contrato Term SOFR.

Datas, feriados, amortização mensal, juros trimestrais na carência e truncamento em centavos seguem as convenções FCL existentes. Os cenários novos não validam cláusulas de um contrato específico nem alteram as regras fiscais. Novos cálculos usam Decimal com precisão 50 e arredondamento somente nos pagamentos.

## Variação cambial

A escolha habilita moeda estrangeira e cotação contratual: reais por uma unidade da moeda. A cotação é informada pelo usuário e permanece constante em toda a simulação; não se consulta o câmbio de mercado para substituir essa entrada. A moeda do empréstimo identifica sua denominação. A unidade dos valores digitados é a moeda global, com seletores espelhados no topo e no formulário; trocar a unidade converte os campos preservando a base real, sem limpar nem reinterpretar os valores.

O backend converte principal e liberações para BRL com Decimal/precisão 50 e arredonda na fronteira monetária em centavos. `valor_base_brl` e `cotacao_id` da apresentação são ignorados nessa modalidade. Origem, cotação, valor original e valor convertido ficam na memória, sem serem salvos como análise. Permite taxa fixa + spread ou SOFR + taxa fixa + spread na operação cambial.

Os seletores de moeda do cabeçalho e do formulário espelham a mesma escolha global, atualizando apresentação e unidade dos campos; moeda e cotação contratuais não são sobrescritas pelo cabeçalho. Assim, mudar o cabeçalho não muda o principal em BRL usado nas avaliações fiscais.

## Prazos

O usuário informa carência e prazo de amortização em meses. Prazo total nominal = carência + amortização, somente leitura. O backend recalcula e rejeita divergências ou soma acima de 600 meses; contratos legados sem o campo de amortização conservam o contrato anterior. Mantém o início da amortização no mês final da carência, conforme o FCL: não altera silenciosamente a sobreposição já documentada nem transforma o prazo nominal em outro cronograma. O ano final continua sendo conferido contra a última data calculada.

## Cronograma pronto: compatibilidade de backend

O formulário não oferece cronograma pronto nem preenchimento manual dos pagamentos. O usuário informa condições e desembolsos, e o sistema calcula os pagamentos. O contrato `anual_informado` continua no backend para compatibilidade, sem acesso pelo formulário. Isso não altera os cronogramas anuais calculados e apresentados no resumo.

## Cálculo automático com liberações em etapas

Para taxa fixa, CDI, Selic e variação cambial (juros fixos ou SOFR), a forma **Calcular empréstimo automaticamente** oferece periodicidade de juros e amortização, base de dias, spread de captação, spread de capital e comissão sobre saldo não desembolsado. IPCA/TLP continuam usando o modelo FCL anterior com liberação única; os campos desse modelo não são reinterpretados.

No calendário de aniversários de liberação única, a data de início e o prazo total determinam o término, exibido automaticamente. Em etapas, assinatura, vigência e primeiro vencimento são informados separadamente; ver `Calendario e SOFR em etapas.md`. Principal amortizado constantemente entre os vencimentos restantes, limitado ao dinheiro recebido. Se um desembolso ocorrer durante a amortização, valores não amortizados são redistribuídos; isso é premissa de simulação e não interpretação de cláusula contratual. A primeira amortização é no fim da carência; sem carência, no primeiro período. Acrescenta o vencimento final quando houver período curto.

No cronograma anual de liberações, o primeiro recebimento ocorre na data de início e os seguintes no dia 15 do mês de referência escolhido. Julho é padrão editável, conforme definição funcional do usuário. Eventos e datas usados ficam na memória. O botão de preenchimento com zero é uma ação explícita para os campos vazios do cenário, sem confirmar ausência de outras dívidas.

No calendário de aniversários, SOFR usa taxa de referência, taxa fixa adicional e dois spreads somados, nominais simples pela base escolhida. Em etapas, a parcela SOFR é composta diariamente em projeção constante e os spreads são simples separados, com base 360. Taxas fixas/CDI/Selic usam fatores efetivos compostos entre os pagamentos. Bases 360/365 usam dias corridos; 252 usa úteis do calendário FCL de 2009–2060. Vencimentos são aniversários civis, sem ajuste bancário. Taxas são hipóteses constantes, sem curva futura nem reconstrução automática de Term SOFR.

Comissão de crédito = saldo ainda não desembolsado × taxa anual × dias corridos/360, acumulada e paga nas datas de juros. Em etapas, começa somente após os dias informados desde a assinatura (60 inicialmente), validando também o prazo de desembolsos desde a vigência. Outros encargos anuais, na moeda do empréstimo, são pagos em dezembro ou no fim da operação. Juros financeiros, comissão e outros encargos aparecem separados na memória e entram somados no CAED. Não confundir a comissão de até 0,75% do documento de exemplo com juros fixos. Zero inicial desses custos significa hipótese do cenário editável.

O resumo inclui MGA/RCL (16%) e estoque com a nova operação (200%), como demonstrações separadas da avaliação publicada. A RCL do MGA é a mesma projeção do CAED. A DCL utiliza DCL e RCL ajustada do mesmo último RGF elegível, somando o principal integral da operação e outras operações não incorporadas informadas em reais. Duplicidade de estoque não é detectada automaticamente: usuário informa apenas valores ainda não incorporados. As demais liberações também são informadas em reais, com fonte e confirmação separadas do CAED. Campos vazios não são zero. A hipótese sem outras operações precisa ser selecionada explicitamente e não comprova cobertura jurídica. Os cenários não produzem aprovação global nem substituem o motor legado de DCL publicada.

Validação: `tests/test_fluxo_contratual.py` cobre periodicidades, 38 amortizações/49 juros, taxa efetiva/nominal, desembolsos, comissão, principal, igualdade em 16%/200% e ausência/ambiguidade. `tests/ponte_cenario_contratual.py` é somente uma ponte de teste com dados fiscais fictícios para testar a interface com o motor Python real; não integra a aplicação distribuída.
