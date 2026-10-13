# Serviço da Dívida — CAED, 11,5% da RCL

A análise prospectiva implementa o art. 7º, II e §4º da [RSF 43/2001](https://legis.senado.leg.br/norma/582604/publicacao/16433616), com referência ao [MIP 2026.08.21](https://cdn.tesouro.gov.br/sistemas-internos/apex/producao/sistemas/thot/arquivos/publicacoes/55422_1804616/MIP-2026-08-21.pdf), itens 3.12.8.1, 3.12.9, 4.1.3 e 4.2.3–4.2.4. É simulação, não autorização de contratação.

## Dados e cronograma único

O preenchimento dos pagamentos ocorre em Ver Detalhes do CAED, com campos únicos. Recalcular atualiza o conjunto de verificações da simulação; não constitui aprovação global nem bloqueia outras regras por reprovação ou ausência de dados do CAED.

Para cada exercício, CAED = juros/encargos da operação pleiteada + amortização da operação pleiteada + pagamentos das demais operações elegíveis. Os três componentes vêm do cronograma informado pelo usuário. As demais operações exigem fonte, data de referência e declaração de cobertura completa; valores ausentes não são zero. O cadastro interno de operações armazena liberações para MGA e não representa pagamentos de dívida. Dados públicos SADIPEM não comprovam inventário completo e não preenchem essa grade automaticamente.

A data da análise deve pertencer ao exercício escolhido. A grade inclui todos os anos desse exercício até o término, sem duplicatas, até 50 anos de horizonte. Valores não negativos, com precisão em centavos: casas extras não nulas são rejeitadas, não truncadas. É possível colar até três colunas do Excel; uma colagem inválida é rejeitada integralmente. Edição, mudança de período e colagem invalidam resultados, relatório e confirmação de cobertura. Uma resposta assíncrona só pode ser usada se suas entradas ainda forem atuais.

## RCL e fator documentado

A RCL é ajustada para cálculo dos limites de endividamento: SICONFI/RREO-Anexo 03, GO, esfera estadual E, conta ajustada `(V) = (III - IV)`, coluna `TOTAL (ÚLTIMOS 12 MESES)`. `obter_rcl_caed` considera bimestres encerrados até a data de análise ou dezembro anterior. Seleciona a referência mais recente, preservando fonte, conta, coluna, exercício, bimestre, ente e data-base. Nulo não autoriza recuo silencioso; duplicidade deixa a análise inconclusiva. RCL deve ser positiva.

A taxa do CAED é um parâmetro local editável, exibido em percentual, inicialmente 2,031208231%. Cada alteração válida é persistida em `ParametroSimulacao` (`taxa_percentual_rcl_caed`) e reutilizada nas consultas seguintes. Multiplicador interno = 1 + taxa/100. Não há consulta externa para obtê-la; alterações do usuário não recebem validação normativa automática. O parâmetro legado permanece preservado sem reinterpretar sua unidade. A janela de datas da análise permanece 22/04 a 31/12/2026; outras referências continuam pendentes. A mesma taxa anual é utilizada na simulação do MGA, por definição funcional do especialista. Alterações invalidam os resultados da simulação até recálculo.

Para cada dezembro projetado:

`meses = 12 × (ano projetado − exercício base) + 12 − 2 × bimestre base`

`RCL projetada = RCL base × multiplicador^(meses / 12)`

Dezembro do próprio exercício implica zero meses; dezembro anterior implica doze. Cálculos prospectivos usam Decimal com precisão 50, sem arredondamentos intermediários; apresentações monetárias não determinam a aprovação.

## Alternativas e conclusão

O universo elegível contém os anos com pagamentos positivos da operação pleiteada. Ambas as alternativas usam exatamente a mesma memória anual consolidada:

- A: média simples de CAED/RCL nos exercícios elegíveis até o término.
- B: média simples do mesmo universo restrito até 31/12/2027, quando não vazio.

São calculadas todas as alternativas aplicáveis. Usa-se a menor; empate mantém A. Média determinante ≤ 11,5% resulta ATENDE; > 11,5% resulta NAO_ATENDE. Um ano individual acima de 11,5% não é, sozinho, impeditivo. Sem anos elegíveis, dados válidos, cobertura ou fator aplicável, resulta INCONCLUSIVO com motivos estruturados. Não existe segunda grade nem aprovação presumida por ausência/erro.

O DTO conserva `estado`, `status`, `aprovado` (true/false/null), linhas, fontes, cobertura, médias, anos elegíveis, alternativa utilizada, percentual determinante e limite. `memoria_exata` preserva entradas e valores decimais inclusive nos retornos antecipados. Modal e relatório apresentam tabelas, fontes e limitações legíveis, sem exibir JSON do CAED. O relatório usa o resultado já calculado.

## Histórico e dependências

O exercício anterior é diagnóstico separado: exige sexto bimestre coincidente da RCL ajustada e despesas do RREO-Anexo 01. Soma juros/encargos e amortização liquidados, mais restos não processados quando disponíveis. Compara com 11,5% da RCL histórica, sem fator. Restos ausentes continuam tratados como zero apenas nesse diagnóstico, com ressalva explícita. Ausência, duplicidade, erro ou resultado histórico acima do limite não bloqueiam a análise prospectiva. Despesas atuais não necessárias ao cálculo não são consultadas como condição de análise.

A DCL é avaliada independentemente do resultado prospectivo do Serviço da Dívida; cada análise mantém sua conclusão individual. Não há aprovação global consolidada nem verificação automática de dispensas jurídicas.

## Restrições e validações pendentes

O comparador estrito, o multiplicador anual `2.031208231`, hipóteses independentes e bloqueio pelo histórico eram comportamentos legados e não são a regra atual. Valores persistidos antigos são preservados e ignorados.

Continuam pendentes: comprovação documental da cobertura/elegibilidade das demais operações; fatores para referências fora da janela documentada; política definitiva e restos ausentes do diagnóstico histórico; exceções/dispensas e aprovação global. A confirmação fornecida pelo usuário não comprova materialmente essas questões.

Testes de domínio cobrem igualdade, precisão decimal, fontes/períodos, composição, alternativas e ausências. Testes Node verificam contrato, colagem e descarte assíncrono; `tests/browser_caed.py` verifica HTML real com ponte Eel simulada, relatório, estados e telas 375/1280 px. Não representam consulta real às APIs nem validação jurídica de documentos.
