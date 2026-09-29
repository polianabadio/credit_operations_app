# Despesa Total com Pessoal — DTP

No ano selecionado, filtra RGF-Anexo 01, UF GO, esfera estadual,
periodicidade quadrimestral e coluna `% sobre a RCL Ajustada`, com valor não nulo.
Seleciona contas cujo nome contenha **DESPESA TOTAL COM PESSOAL**, independentemente
do código e dos sufixos do nome. Ignora diferenças de maiúsculas e espaços repetidos.

Utiliza o último quadrimestre com valores elegíveis de **pelo menos seis
instituições distintas** e soma os poderes desse mesmo
período. Não completa poderes ausentes com valores de quadrimestres anteriores.
Os valores são agrupados por poder, preservando as instituições distintas e
eliminando registros duplicados pela chave de instituição/conta/código/rótulo/coluna.

- Total até 60%: **SUCESSO: Operação Aprovada / Concatenação Concluída**.
- Total acima de 60%: **FALHA: Operação de Crédito Negada (Circuit Breaker)**.
- Sem valores: não exibe a regra. Zero é um valor válido.

Uma única linha DTP apresenta o resultado. Nos detalhes: total, ano, quadrimestre,
decisão e contribuição de cada poder com dados nesse período. Não há decisões
individuais por poder. O último período disponível pode não conter publicações
de todos os poderes/instituições; a conclusão exige no mínimo seis instituições
com valores. Conta nomes distintos, ignorando diferenças de caixa e espaços;
linhas repetidas da mesma instituição não aumentam a contagem. Zero é válido,
valor nulo não conta. Se nenhum quadrimestre do ano atingir seis instituições,
a regra não é exibida nem aprovada. Períodos recentes incompletos são ignorados.

Testes: `python -m pytest tests -q -p no:cacheprovider`.
