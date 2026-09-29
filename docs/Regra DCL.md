# % da DCL sobre a RCL AJUSTADA (III/VI)

Fonte: RGF-Anexo 02, periodicidade Q, Goiás (UF GO, esfera estadual), Executivo.
A importação existente já consulta esses dados para o ente 52.

No ano selecionado, usa o relatório de maior quadrimestre contendo a conta
`% da DCL sobre a RCL AJUSTADA (III/VI)` e extrai as colunas:

- Saldo do exercício anterior.
- Até o maior quadrimestre disponível no relatório: 1º, 2º ou 3º.

Os campos são comparados individualmente, sem soma. Ambos menores ou iguais a
200%: aprovado. Qualquer um maior que 200%: recusado. Exatamente 200% aprova.

O modal apresenta uma caixa com situação, ano e quadrimestre do relatório e os
dois percentuais. O nome e o valor da coluna acompanham o quadrimestre do
relatório mais recente: por exemplo, Até o 3º Quadrimestre para o terceiro
relatório do ano. Colunas de quadrimestres anteriores não substituem essa coluna.

Valor ausente ou valores conflitantes para a mesma coluna impedem a avaliação;
não são substituídos por zero ou por valores de relatórios anteriores. Sem a
conta no ano selecionado, a regra não é exibida. Não se aplica o requisito de
seis instituições da DTP.
