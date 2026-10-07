# Integração MGA/RCL — atualização de 06/10/2026

Simulação reúne dados gerais, Cronograma financeiro (Recebimentos e Pagamentos) e Verificações disponíveis. MGA aparece na lista como “Liberações de crédito — limite de 16% da RCL”, com tabela anual em Ver detalhes. Dashboard mostra a posição cadastrada, sem acrescentar hipóteses da nova operação. A aba Análise foi removida.

Valor requisitado é único. Ano inicial/final de liberação e ano final dos pagamentos são independentes. Modos: integral no ano indicado ou cronograma anual, com todos os anos do intervalo e soma exata em centavos. Não existe distribuição uniforme implícita. Campos vazios exibem Aguardando preenchimento e bloqueiam o cálculo.

## Parâmetro auditado

Fonte: MIP 2026.08.21, §§ 4.2.3–4.2.4, páginas 101–102:
https://cdn.tesouro.gov.br/sistemas-internos/apex/producao/sistemas/thot/arquivos/publicacoes/55422_1804616/MIP-2026-08-21.pdf

Desde 22/04/2026: multiplicador 1,02031208231 = taxa percentual 2,031208231% = taxa decimal 0,02031208231. Base: PIB real de 2018–2025. O código legado do serviço da dívida usava 2,031208231 como multiplicador; não foi reutilizado no MGA. O novo mga_parameters.py guarda fonte, vigência, significado e validação próprios. Fórmulas e valores persistidos das outras regras foram preservados; a origem do parâmetro legado do serviço da dívida continua pendente e está indicada na interface.

Entradas distinguem taxa decimal 0,03, percentual 3 e multiplicador 1,03. Parâmetros alternativos são hipóteses pendentes, sem conclusão validada. Referências fora de 2026 exigem fator histórico verificado. Primeiro ano: RCL base × multiplicador^(meses até dezembro / 12); seguintes: RCL anterior × multiplicador. Dezembro anterior implica 12 meses; dezembro do próprio ano já é o fechamento. YAML documenta a mesma unidade/fórmula.

RCL reutiliza data_access.py/SICONFI, RREO Anexo 03, últimos 12 meses, ajustada para endividamento. Sem RCL do ano escolhido, aceita dezembro anterior com referência explícita. Não há novo cliente fiscal nem valores fictícios.

## Memória, cobertura e cálculo

OperacaoCredito, LiberacaoCredito e CoberturaMga usam a Base/SQLAlchemy existentes e create_all sem remover dados. Identificador único permite atualizar; alterações invalidam a cobertura. Registros trazem fonte, situação, valor, período, liberações e data. Informar identificador/PVL da nova operação já cadastrada exclui sua cópia do inventário desta simulação, evitando somá-la duas vezes.

Demais liberações distinguem desconhecido, zero conhecido após confirmação do inventário e zero assumido no cenário parcial. Parcial sempre exibe “Considera apenas a nova operação; demais liberações não incluídas”, inclusive quando excede o limite. Não publica margem disponível ou máximo de contratação. Sem cobertura: “Informe as liberações das demais operações para concluir a verificação.”

MGA = nova operação + demais liberações; teto = RCL projetada × 0,16; razão = MGA/RCL; uso = razão/0,16; saldo = teto − MGA. Saldo negativo é preservado. Razão 15% equivale a uso 93,75%. Exatamente 16% atende. Todos os exercícios relevantes são avaliados. numericOutcome registra o resultado numérico; verificationStatus separa Dentro do limite, Acima do limite, Dados incompletos e Cenário parcial; validatedConclusion exige inventário e parâmetro válidos.

Margem após demais operações e máximo para proporções fixadas do cronograma só aparecem com cobertura e parâmetro validados. O ano restritivo é informado. Sem isso, mostra-se teto bruto anual sem margem disponível. O cálculo aplica o limite geral de 16%; exceções/dispensas jurídicas específicas exigem conferência, sem exclusões legais automáticas. Cadastros em BRL requerem conversões documentadas quando necessário.

Fontes por exercício incluem RCL base, exercício/bimestre, demonstrativo/anexo, data exata de consulta quando registrada, taxa/multiplicador, fonte/vigência, cobertura e contribuições por operação. Datas desconhecidas permanecem nulas.

## Relatório e resultados

analisar_operacao_py retorna regras existentes e mgaProjection na mesma chamada. Hipóteses não são gravadas no inventário. Relatório HTML inclui entradas, cronogramas, resultados, fontes, parâmetros, pendências e memória das regras, sem recalcular. Pode ser aberto ou impresso no navegador. Mudanças de entradas/cadastros marcam resultados desatualizados e bloqueiam exportação até recálculo. Respostas de cálculos iniciados com entradas anteriores são descartadas.

CAED, DCL, DTP, CAPAG, Regra de Ouro e motor de aprovação mantêm suas fórmulas. MGA é uma verificação própria e não representa aprovação global.

## Dados públicos e pendências

SADIPEM público mantém cliente, cache e paginação existentes. Snapshots contratados de diferentes PVLs podem repetir operações; não são somados como inventário. Consulta real de 06/10/2026: /pvl retornou 32 registros de Goiás/Estado. Para PVL 74460, /opc-cronograma-liberacoes e /opnc-pvl-tramitacao-deferido responderam HTTP 200 com items vazio. Snapshots históricos não comprovam liberações atuais. Quando a API não cobre o cronograma, é necessário cadastrar os documentos e confirmar cobertura.

Pendências: cobertura atual das demais operações, fatores históricos/alternativos, origem do parâmetro legado do serviço da dívida e enquadramentos jurídicos especiais. O fator MGA de 2026 foi confirmado no MIP vigente.

## Validação

149 testes Python passaram. Casos MGA: integral em ano independente, plurianual, exatamente 16%, excesso/saldo negativo, liberações desconhecidas, parcial favorável/desfavorável, soma divergente por um centavo, precisão monetária, capacidade e ano restritivo, duplicidade, taxa/multiplicador, parâmetro pendente e dezembro anterior.

Playwright/Chrome: tabela em 375/1280 px, MGA na lista/modal, pagamentos únicos na Simulação, resultado desatualizado, operação vazia bloqueada e relatório contendo as mesmas entradas/resultados. Ruff dos módulos/testes MGA e checks/testes JavaScript passam. Testes não usam banco de produção.
