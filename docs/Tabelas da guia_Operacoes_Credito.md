# Catálogo funcional

Para Serviço da Dívida/CAED, a especificação atual é [Serviço da Dívida](Regra%20do%20Serviço%20da%20Dívida%2011,5.md): cronograma único, operação pleiteada + demais operações, média simples nos anos com pagamentos pleiteados, menor alternativa até o término ou até 2027, igualdade em 11,5% aceita. RCL vem do SICONFI; pagamentos e cobertura documental são informados para análise. Ausências deixam a conclusão INCONCLUSIVA. As tabelas abaixo são catálogo de referência e não comprovam execução de todas as regras ou aprovação global.

# Tabela da guia: Primeira Etapa

| Etapa                                                   | Decisão                                                                                     | Condição     | Próximo Passo                                             | BANCO DE DADOS   | BASE NORMATIVA                                                           | OBJETIVO                                                                                                                                                                                     |
|:--------------------------------------------------------|:--------------------------------------------------------------------------------------------|:-------------|:----------------------------------------------------------|:-----------------|:-------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1. Regra de Ouro (Ano Anterior)                         | Valor previsto dentro dos limites                                                           | Sim          | Prosseguir para a Regra de Ouro (Ano Atual)               | SICONFI          | Regra de ouro 167, Inciso III, da CF 88 + RSF 43/2001, Pag 78 do MIP     | A regra de ouro busca evitar o uso de recursos provenientes de operações de crédito para o pagamento de despesas correntes. Para isto, ela diz que as receitas de operação de crédito não podem ultrapassar as despesas de capital. |
| 1. Regra de Ouro (Ano Anterior)                         | Valor previsto ultrapassa os limites                                                        | Não          | Operação de Crédito Negada                                | SICONFI          | Regra de ouro 167, Inciso III, da CF 88 + RSF 43/2001, Pag 78 do MIP     | A regra de ouro busca evitar o uso de recursos provenientes de operações de crédito para o pagamento de despesas correntes. Para isto, ela diz que as receitas de operação de crédito não podem ultrapassar as despesas de capital. |
| 2. Regra de Ouro (Ano Atual)                            | Dentro dos limites                                                                          | Sim          | Prosseguir para Limite de 16% da Receita Corrente Líquida | SICONFI          | Regra de ouro 167, Inciso III, da CF 88 + RSF 43/2001, Pag 78 do MIP     | A regra de ouro busca evitar o uso de recursos provenientes de operações de crédito para o pagamento de despesas correntes. Para isto, ela diz que as receitas de operação de crédito não podem ultrapassar as despesas de capital. |
| 2. Regra de Ouro (Ano Atual)                            | Ultrapassa os limites                                                                       | Não          | Operação de Crédito Negada                                | SICONFI          | Regra de ouro 167, Inciso III, da CF 88 + RSF 43/2001, Pag 78 do MIP     | A regra de ouro busca evitar o uso de recursos provenientes de operações de crédito para o pagamento de despesas correntes. Para isto, ela diz que as receitas de operação de crédito não podem ultrapassar as despesas de capital. |
| 3. Limite de 16% da RCL                                 | (Receitas das Operações de Crédito + Receitas de Crédito Solicitadas) ≤ 16% da RCL Estimada | Sim          | Prosseguir para a Regra do Dispêndio                      | SICONFI          | Art 7º, Inciso I, da RSF 43/2001, Pag 80 e 81 do MIP                     | O limite do MGA  visa a reduzir a receita total de operações de crédito por meio de endividamento em um ano.                                                                                                                        |
| 3. Limite de 16% da RCL                                 | (Receitas das Operações de Crédito + Receitas de Crédito Solicitadas) > 16% da RCL Estimada | Não          | Operação de Crédito Negada                                | SICONFI          | Art 7º, Inciso I, da RSF 43/2001, Pag 80 e 81 do MIP                     | O limite do MGA  visa a reduzir a receita total de operações de crédito por meio de endividamento em um ano.                                                                                                                                                                                                                                 |
| 4. Regra do Dispêndio (11,5% da RCL Estimada)           | Menor média elegível de CAED/RCL ≤ 11,5%                                   | Sim          | Prosseguir para a Dívida Consolidada                      | SICONFI + cronograma informado | Art. 7º, II e §4º, RSF 43/2001; MIP 2026.08.21                    | Tem o objetivo de restrigir os gastos com a rolagem da dívida, a fim de evitar um desequilíbrio fiscal. O limite de CAED/RCL é de 11,5% para a menor média simples dos anos elegíveis do cronograma único (término ou até 2027)                                        |
| 4. Regra do Dispêndio (11,5% da RCL Estimada)           | Menor média elegível de CAED/RCL > 11,5%                                   | Não          | Operação de Crédito Negada                                | SICONFI + cronograma informado | Art. 7º, II e §4º, RSF 43/2001; MIP 2026.08.21                    | Tem o objetivo de restrigir os gastos com a rolagem da dívida, a fim de evitar um desequilíbrio fiscal. O limite de CAED/RCL é de 11,5% para a menor média simples dos anos elegíveis do cronograma único (término ou até 2027)                                                |
| 5. Dívida Consolidada                                   | Dívida Consolidada ≤ 2x a RCL Estimada                                                      | Sim          | Prosseguir para a confrotação total                       | INTERNA          | Inciso III do Art 7º, combinado com art 3º da RSF 43/2001, Pag 98 do MIP | Tem o Objetivo de evitar o super endividamento                                               |
| 5. Dívida Consolidada                                   | Dívida Consolidada > 2x a RCL Estimada                                                      | Não          | Operação de Crédito Negada                                | INTERNA          | Inciso III do Art 7º, combinado com art 3º da RSF 43/2001, Pag 98 do MIP | Tem o Objetivo de evitar o super endividamento                                               |


# Tabela da guia: Segunda Etapa

|  Etapa                                                   | Decisão                                            | Condição     | Próximo Passo                                                 | BANCO DE DADOS   | BASE NORMATIVA         | OBJETIVO                                       |
|:--------------------------------------------------------|:---------------------------------------------------|:-------------|:--------------------------------------------------------------|:-----------------|:-----------------------|:-----------------------------------------------|
| 1. Limite de Garantias                                  | Garantia ≤ 22% da RCL Estimada                     | Sim          | Prosseguir para a verificação do valor da operação de crédito | B.O              | Art. 9º da RSF 43/2001 | Impedir o comprometimento das garantias na RCL |
| 1. Limite de Garantias                                  | Garantia > 22% da RCL Estimada                     | Não          | Operação de Crédito Negada                                    | B.O              | Art. 9º da RSF 43/2002 | Impedir o comprometimento das garantias na RCL |
| 2. Valor da Garantia                                    | Garantia ≥ Valor da operação de crédito pretendida | Sim          | Prosseguir para a confrotação total                           | B.O              | Art. 9º da RSF 43/2003 | Impedir o comprometimento das garantias na RCL |
| 2. Valor da Garantia                                    | Garantia < Valor da operação de crédito pretendida | Não          | Operação de Crédito Negada                                    | B.O              | Art. 9º da RSF 43/2004 | Impedir o comprometimento das garantias na RCL |


# Tabela da guia: Terceira Etapa

|  Etapa                                                   | Decisão                                            | Condição     | Próximo Passo                                                 | BANCO DE DADOS   | BASE NORMATIVA         | OBJETIVO                                       |
|:--------------------------------------------------------|:------------------------------------------|:--------------------------------------------------------|:-----------------|:---------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------|
| 1. Despesa com Pessoal                                  | Despesa com pessoal ≤ 60% da RCL Estimada | Prosseguir para a próxima decisão de despesas correntes | SICONFI          | Art 19º II, LRF, RSF Nº 43/2001                                                              | O excessivo gasto com despesas com pessoal pode comprometer a capacidade de honrar o serviço da dívida, tendo em vista que o gasto com pessoal é uma despesa de caracter continuado. |
| 1. Despesa com Pessoal                                  | Despesa com pessoal > 60% da RCL Estimada | Operação de Crédito Negada                              | SICONFI          | Art 19º II, LRF, RSF Nº 43/2001                                                              | O excessivo gasto com despesas com pessoal pode comprometer a capacidade de honrar o serviço da dívida, tendo em vista que o gasto com pessoal é uma despesa de caracter continuado.   |
| 3. Nota CAPAG                                           | Nota CAPAG INFERIOR  > A OU B             | Operação de Crédito Vedada                              | SICONFI/INTERNA  | MIP, exigível para a concessão de garantias da União. Necessidade do Ente obter CAPAG A OU B | Caso o Ente não tenha a CAPAG apropriada, não poderá contar com a União no oferecimento de garantias, isto levará a um maior  nível de risco e taxas de juros no mercado             |
| 3. Nota CAPAG                                           | NOTA CAPAG SUPERIOR  < A OU B             | Prosseguir para a confrotação total                     | SICONFI/INTERNA  | MIP, exigível para a concessão de garantias da União. Necessidade do Ente obter CAPAG A OU B | Caso o Ente não tenha a CAPAG apropriada, não poderá contar com a União no oferecimento de garantias, isto levará a um maior  nível de risco e taxas de juros no mercado  |

# Lista Guia Variáveis

- indice_mip: Índice de crescimento da Receita Corrente Líquida, conforme o MIP (Manual para Instruções de Pleitos).
- rcl_anterior: Receita Corrente Líquida realizada de final de período do Ano Anterior. 
- rcl_12meses: Receita Corrente Líquida realizada até o período *(n-1)* do Ano Atual.
- rcl_estimada: Receita Corrente Líquida estimada, utilizando rcl_anterior multiplicando pelo indice_mip.
- amortizacoes:
    * amortizacoes_ano_anterior: Amortizações do ano anterior (Ano Anterior)
    * amortizacoes_ano_atual: Amortizações do ano atual (Ano Atual)
    * amortizacoes_regra_dispendio: Somatório até 2027 dividido pelo período.
    * amortizacoes_operacao_credito: Fluxo total da operação de crédito simulada por fonte externa.
- juros:
    * juros_ano_anterior: Juros do ano anterior (Ano Anterior)
    * juros_ano_atual: Juros do ano atual (Ano Atual)
    * juros_regra_dispendio: Somatório até 2027 dividido pelo período.
    * juros_operacao_credito: Fluxo total da operação de crédito simulada por fonte externa.
- encargos:
    * encargos_ano_anterior: Encargos do ano anterior (Ano Anterior) 
    * encargos_ano_atual: Encargos do ano atual (Ano Atual) 
    * encargos_regra_dispendio: Somatório até 2027 dividido pelo período.
    * encargos_operacao_credito: Fluxo total da operação de crédito simulada por fonte externa.
- divida_consolidada: Dívida consolidada total do ente, conforme o último RREO publicado.
- divida_consolidada_liquida: Dívida consolidada líquida total do ente, conforme o último RREO publicado.
- receita_credito_solicitadas: Receita total de operações de crédito solicitadas e em análise (interna), somente consideradas se receita prevista para o ano atual.
- receita_operacoes_credito: Receita total de operações de crédito contratadas e em andamento (SICONFI).
- despesa_pessoal: Despesa total com pessoal do ente, conforme o último RGF publicado.
- garantia: receitas_impostos + receitas_transferencias_constitucionais_uniao - despesa_transferencias_constitucionais_municipios - servico_divida.
    * servico_divida: Somatório de amortizacoes + juros + encargos, conforme o último RREO publicado.
    * receitas_impostos: Somatório das receitas tributárias, conforme B.O.
    * receitas_transferencias_constitucionais_uniao: Somatório das transferências correntes da União, conforme B.O.
- valor_op_pretendida: Valor total da operação de crédito simulada por fonte externa.
- nota_capag: Última nota CAPAG publicada (interna).

# Lista Guia Variáveis por Fonte de Dados

## Fonte_de_Dados: SICONFI
**Variáveis:**  
- rcl_anterior  
- rcl_12meses  
- amortizacoes_ano_anterior  
- amortizacoes_ano_atual  
- juros_ano_anterior  
- juros_ano_atual  
- encargos 
- divida_consolidada
- divida_consolidada_liquida
- receita_operacoes_credito
- despesa_pessoal
- servico_divida


## Fonte_de_Dados: Boletim Orçamentário (B.O)
**Variáveis:**  
- receitas_impostos
- receitas_transferencias_constitucionais_uniao

## Fonte_de_Dados: INTERNA
**Variáveis:**
- indice_mip
- rcl_estimada
- amortizacoes_regra_dispendio
- amortizacoes_operacao_credito
- juros_regra_dispendio
- juros_operacao_credito
- encargos_regra_dispendio
- encargos_operacao_credito
- valor_op_pretendida
- nota_capag
