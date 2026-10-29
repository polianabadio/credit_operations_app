# Integração MGA/RCL — atualização de 06/10/2026

Simulação reúne dados gerais e Verificações disponíveis. Liberações e inventário são preenchidos em Ver Detalhes do limite de 16%; pagamentos em Ver Detalhes do CAED, sem bloco de cronograma separado na página. Os recálculos atualizam o conjunto das análises. MGA aparece na lista como “Liberações de crédito — limite de 16% da RCL”, com tabela anual em Ver detalhes. Dashboard e Principais Limites mostram a margem anual disponível antes da nova operação: teto de 16% da RCL projetada menos liberações existentes incluídas. A apresentação reutiliza o saldo calculado pelo backend, exige cobertura do exercício e parâmetro validado, distingue margem zero, negativa e não determinada e preserva fontes. A memória de Limites contém RCL, teto, liberações existentes e margem; a tabela MGA com a nova operação fica na Simulação. A aba Análise foi removida.

Valor requisitado é único. Ano inicial/final de liberação e ano final dos pagamentos são independentes. A interface exibe sempre primeiro ano e ano final; para um único exercício, preencher ambos com o mesmo ano. Cronograma anual exige primeiro um ano inicial válido, habilitando então o ano final igual ou posterior. A grade inclui somente os exercícios entre ambos, sem botão de adicionar ano. Início e fim são editáveis independentemente, a partir do exercício da análise; preserva lançamentos dos anos que continuam no período e não recria campos sem mudança do intervalo. Modos: integral no ano indicado ou cronograma anual, com todos os anos do intervalo e soma exata em centavos. Não existe distribuição uniforme implícita. Campos vazios exibem Aguardando preenchimento e bloqueiam o cálculo.

## Parâmetro auditado

Fonte: MIP 2026.08.21, §§ 4.2.3–4.2.4, páginas 101–102:
https://cdn.tesouro.gov.br/sistemas-internos/apex/producao/sistemas/thot/arquivos/publicacoes/55422_1804616/MIP-2026-08-21.pdf

Desde 22/04/2026: multiplicador 1,02031208231 = taxa percentual 2,031208231% = taxa decimal 0,02031208231. Base: PIB real de 2018–2025. O código legado do serviço da dívida usava 2,031208231 como multiplicador; não foi reutilizado no MGA. O novo mga_parameters.py guarda fonte, vigência, significado e validação próprios. O CAED tem resolução própria de fator documentado, sem usar o parâmetro legado persistido; sua regra atual está em [Serviço da Dívida](Regra%20do%20Serviço%20da%20Dívida%2011,5.md). Na simulação, MGA reutiliza a taxa anual local informada nos dados da operação para CAED; não há segundo campo de taxa. O parâmetro documentado próprio permanece na posição fiscal anterior à simulação.

Entradas distinguem taxa decimal 0,03, percentual 3 e multiplicador 1,03. Parâmetros alternativos são hipóteses pendentes, sem conclusão validada. Referências fora de 2026 exigem fator histórico verificado. Primeiro ano: RCL base × multiplicador^(meses até dezembro / 12); seguintes: RCL anterior × multiplicador. Dezembro anterior implica 12 meses; dezembro do próprio ano já é o fechamento. YAML documenta a mesma unidade/fórmula.

RCL reutiliza data_access.py/SICONFI, RREO Anexo 03, últimos 12 meses, ajustada para endividamento. Sem RCL do ano escolhido, aceita dezembro anterior com referência explícita. Não há novo cliente fiscal nem valores fictícios.

## Memória, cobertura e cálculo

OperacaoCredito, LiberacaoCredito e CoberturaMga usam a Base/SQLAlchemy existentes e create_all sem remover dados. Identificador único permite atualizar; alterações invalidam a cobertura. Registros trazem fonte, situação, valor, período, liberações e data. Informar identificador/PVL da nova operação já cadastrada exclui sua cópia do inventário desta simulação, evitando somá-la duas vezes.

Demais liberações distinguem desconhecido, zero conhecido após confirmação do inventário e zero assumido no cenário parcial. Parcial sempre exibe “Considera apenas a nova operação; demais liberações não incluídas”, inclusive quando excede o limite. Não publica margem disponível ou máximo de contratação. Sem cobertura: “Informe as liberações das demais operações para concluir a verificação.”

MGA = nova operação + demais liberações; teto = RCL projetada × 0,16; razão = MGA/RCL; uso = razão/0,16; saldo = teto − MGA. Saldo negativo é preservado. Razão 15% equivale a uso 93,75%. Exatamente 16% atende. Todos os exercícios relevantes são avaliados. numericOutcome registra o resultado numérico; verificationStatus separa Dentro do limite, Acima do limite, Dados incompletos e Cenário parcial; validatedConclusion exige inventário e parâmetro válidos.

Margem após demais operações e máximo para proporções fixadas do cronograma só aparecem com cobertura e parâmetro validados. O ano restritivo é informado. Sem isso, mostra-se teto bruto anual sem margem disponível. O cálculo aplica o limite geral de 16%; exceções/dispensas jurídicas específicas exigem conferência, sem exclusões legais automáticas. Cadastros em BRL requerem conversões documentadas quando necessário.

Fontes por exercício incluem RCL base, exercício/bimestre, demonstrativo/anexo, data exata de consulta quando registrada, taxa/multiplicador, fonte/vigência, cobertura e contribuições por operação. Datas desconhecidas permanecem nulas.

## Relatório e resultados

O detalhe da regra apresenta a composição econômica: teto anual de 16%, liberações das demais operações, nova operação e saldo após a operação. A conclusão numérica indica dentro/acima do limite ou dados insuficientes; a fonte SADIPEM/PVL é identificada separadamente e conserva a ressalva de cobertura. A tabela mostra os valores anuais em reais, sem duplicar comprometimento e uso do limite. A memória conserva a RCL, sua taxa anual percentual, referências e enquadramento a conferir.

analisar_operacao_py retorna regras existentes e mgaProjection na mesma chamada. Hipóteses não são gravadas no inventário. Relatório HTML inclui entradas, cronogramas, resultados, fontes, parâmetros, pendências e memória das regras, sem recalcular. Pode ser aberto ou impresso no navegador. Mudanças de entradas/cadastros marcam resultados desatualizados e bloqueiam exportação até recálculo. Respostas de cálculos iniciados com entradas anteriores são descartadas.

CAED, DCL, DTP, CAPAG, Regra de Ouro e motor de aprovação mantêm suas fórmulas. MGA é uma verificação própria e não representa aprovação global.

## Dados públicos e pendências

O Dashboard inicia a consulta SADIPEM após apresentar os dados fiscais. A ponte Eel compõe `margemPublica` com `obter_margem_publica`, usando a projeção fiscal e o único snapshot selecionado pelo cliente existente. Principais Limites reutiliza esse resultado. Atualizações da mesma base fiscal preservam a referência; alterações de exercício, RCL ou projeção exigem nova consulta, e respostas de painéis substituídos são descartadas. A margem pública continua sendo referência parcial segundo o PVL, sem confirmar cobertura do inventário.

SADIPEM público mantém cliente, cache e paginação existentes. Snapshots contratados de diferentes PVLs podem repetir operações; não são somados como inventário. Consulta real de 06/10/2026: /pvl retornou 32 registros de Goiás/Estado. Para PVL 74460, /opc-cronograma-liberacoes e /opnc-pvl-tramitacao-deferido responderam HTTP 200 com items vazio. Snapshots históricos não comprovam liberações atuais. Quando a API não cobre o cronograma, é necessário cadastrar os documentos e confirmar cobertura.

Pendências: cobertura atual das demais operações, fatores históricos/alternativos, origem do parâmetro legado do serviço da dívida e enquadramentos jurídicos especiais. O fator MGA de 2026 foi confirmado no MIP vigente.

## Validação

149 testes Python passaram. Casos MGA: integral em ano independente, plurianual, exatamente 16%, excesso/saldo negativo, liberações desconhecidas, parcial favorável/desfavorável, soma divergente por um centavo, precisão monetária, capacidade e ano restritivo, duplicidade, taxa/multiplicador, parâmetro pendente e dezembro anterior.

Playwright/Chrome: tabela em 375/1280 px, MGA na lista/modal, pagamentos únicos na Simulação, resultado desatualizado, operação vazia bloqueada e relatório contendo as mesmas entradas/resultados. Ruff dos módulos/testes MGA e checks/testes JavaScript passam. Testes não usam banco de produção.

## Margem com fonte pública

Ao carregar o Dashboard, a ponte Eel inicia automaticamente a consulta ao SADIPEM, enquanto os dados fiscais já são apresentados, e compõe `margemPublica` no backend, sem importar/persistir inventário. O saldo segundo o PVL do exercício usa liberações contratadas declaradas e liberações anuais não contratadas listadas. Quando liberações estiverem vazias, `indicador_liberacoes=0` em registro correspondente do cronograma de pagamentos comprova ausência declarada das contratadas; flag positivo/ausente, registro estranho ou duplicado não autorizam zero. Metadados: [Tesouro — cronograma de pagamentos](https://www.tesourotransparente.gov.br/ckan/dataset/599608bc-aaeb-42ca-ac48-2f46836f3278/resource/575c2398-9cf9-4476-9e89-e90a4ee0043c/download/metadados-pvl-oc-cp.pdf).

A interface mostra valores, PVL, data, consulta e ressalva de cobertura. Lista vazia de não contratadas significa nenhuma listada nesse PVL; não comprova ausência fora dele. O resultado é referência pública parcial, separada da margem validada do inventário. A simulação reutiliza as liberações do mesmo PVL apenas em exercícios desconhecidos, soma a nova operação e recalcula com sua própria RCL projetada. Preserva a cobertura parcial, não preenche anos ausentes nem disponibiliza máximo de contratação validado. Não soma fotografias, não importa pagamentos como liberações e não reutiliza referência antiga para o exercício atual.
