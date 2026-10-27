# Motor de cálculo FCL/TLP

Referência: arquivo `_GOIÁS - Modelo-FCL-777-TLP _revisado 20 anos (2C-18A_Versão 27-07-2026).xlsx`, abas `Modelo FCL 777 - TLP`, `Modelo FCL 777 - TLP 5%`, `Série IPCA` e `FERIADOS`.

O motor em `src/simulador/fluxo_tlp.py` recebe o valor e a data de uma única liberação, o prazo total, a carência, a taxa prefixada e o spread. As condições numéricas do exemplo não são valores predefinidos da aplicação. As outras avaliações fiscais permanecem independentes.

## Sequência reproduzida

1. A referência inicial é o dia 15 do mês da liberação quando a liberação ocorre depois do dia 15. Nos demais casos, é o dia 15 do mês anterior (E13). As referências seguintes avançam um mês.
2. A data de quebra é o primeiro dia útil a partir do dia 15 do mês seguinte (D13 em diante). O calendário contém exatamente os 624 feriados de B3:B626, incorporados em módulo Python para funcionar também no executável. Não acrescenta feriados posteriores ou locais ao calendário original.
3. `dup` e `dut` reproduzem `NETWORKDAYS(início, fim, feriados)-1` (G:H), incluindo o comportamento da planilha quando a liberação ocorre em dia não útil.
4. O rótulo da série TXD00236 no dia 15 corresponde ao IPCA do mês civil anterior (M-1). Por exemplo, a referência 15/01/2011 contém 0,63%, correspondente a dezembro de 2010; 15/02/2011 contém 0,83%, de janeiro de 2011. A série SGS 433 é consultada pela competência civil, sem confundir o mês do rótulo com o mês medido.
5. Fatores: `(1 + IPCA/100)^(dup/dut)`, `(1 + taxa_fixa/100)^(dup/252)` e `(1 + spread/100)^(dup/252)` (I:K). O produto é acumulado enquanto não houver pagamento (L).
6. Na carência há pagamento de juros a cada três linhas mensais. Os juros são arredondados em centavos, metade para cima (M). O saldo não capitaliza juros não pagos entre essas datas.
7. A primeira amortização acontece no mês que encerra a carência, como N36/O36. A amortização mensal é `TRUNC(saldo / parcelas_restantes, 2)`, com redução do saldo a cada pagamento. A última parcela quita o resíduo dos centavos.
8. No exemplo de 24 meses de carência e 216 amortizações, são 239 períodos: a linha 24 pertence simultaneamente ao encerramento da carência e à primeira amortização. A última amortização ocorre na linha 251 do arquivo, em 15/10/2046. O prazo nominal de 240 meses não deve ser reinterpretado como 240 linhas mais 24 meses de carência. Carência zero permite pagamentos mensais desde o primeiro período; é uma generalização do motor, não uma variante presente no arquivo.

## Dados públicos e estimativas

O serviço consulta o IPCA publicado pelo IBGE, disponibilizado pelo Banco Central na série 433. As consultas são divididas em intervalos de até dez anos e mantidas em memória por uma hora. Falha de rede não vira índice zero.

Para qualquer competência sem índice na resposta bem-sucedida, a aplicação usa IPCA de 0%, conforme solicitado pelo usuário. Os períodos são identificados individualmente; a taxa fixa e o spread permanecem no cálculo. Índices publicados, inclusive deflação, são preservados. Uma falha de rede ou resposta inválida interrompe a consulta, em vez de simular indisponibilidade do índice. A antiga opção da interface de repetir o último IPCA foi removida.

## Divergências corrigidas

- L37 aponta para C17/L17 nas duas abas. Como a linha 36 já paga juros, o motor reinicia o fator em vez de reutilizar juros antigos. O teste registra a diferença em L37/M37.
- A linha 252 tem zero parcelas restantes e `IFERROR` esconde a divisão por zero de N252. O motor encerra na linha 251, quando o principal já está quitado.
- O termo `B14 = B13-N13+M13` não altera o exemplo porque M13 é zero. Não foi generalizado para capitalizar juros pagos.

## Integração e limites

A avaliação TLP usa o valor e a data dos dados comuns do empréstimo. Confere o ano da liberação e o ano final antes de consultar a série. Recebimentos distribuídos em vários anos são rejeitados nessa avaliação, pois o arquivo contém uma única liberação. Nenhuma simulação com várias liberações é silenciosamente substituída por uma liberação integral.

O resultado contém memória mensal, total de juros, principal amortizado, total a pagar e agregação anual pela data efetiva de pagamento. Um botão permite aproveitar os pagamentos anuais na hipótese da operação pretendida na avaliação de serviço da dívida. O usuário precisa recalcular essa avaliação para obter o resultado fiscal.

## Verificação

`tests/test_fluxo_tlp.py` reconcilia 478 linhas dos valores salvos nas duas abas, com taxas fixas de 7% e 5% e IPCA zero, ressalvada a correção de L37/M37. A fixture preserva os valores do arquivo sem depender de acesso ao disco de rede durante os testes. Há verificação independente dos fatores com IPCA não nulo, corte do dia 15, feriados, juros trimestrais, truncamento, quitação, deflação e ausência de índices. A conferência usa os valores salvos no arquivo; não significa uma nova execução do Excel.
