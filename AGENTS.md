# Mapa do projeto e regras para agentes

## Objetivo e arquitetura

Simulador desktop de operações de crédito para o Estado de Goiás. Apresenta a posição fiscal publicada e simula o impacto de uma nova operação; seus resultados não constituem autorização de contratação.

Fluxo ativo: `src/web/main.html` → JavaScript/Eel → funções `@eel.expose` em `app.py` → serviços/regras em `src/simulador/` → SQLAlchemy e integrações HTTP. `app.py` inicializa diretórios e banco já ao ser importado; não o importe em testes sem isolamento.

Stack: Python, Eel, SQLAlchemy, Requests, PyYAML e psutil; frontend HTML/CSS/JavaScript sem framework de aplicação ou build npm. Tailwind, Flowbite e Font Awesome são carregados como assets locais. SQLite é o padrão; configuração também suporta PostgreSQL (`psycopg2`) e MySQL (`pymysql`), com drivers adicionais. Não há aplicação Flask/FastAPI ativa, Docker, migrações Alembic ou pipeline CI versionado. Dependência listada ou asset legado não comprova uso: Pandas/importação CSV não fazem parte do fluxo implementado.

## Estrutura e responsabilidades

| Local | Responsabilidade |
| --- | --- |
| `app.py` | Inicialização Eel, ponte frontend/backend e composição das respostas. |
| `src/simulador/config.py`, `database_models.py` | Caminhos/configuração INI, engine/sessão e modelos declarativos. |
| `src/simulador/data_access.py` | Consultas fiscais e seleção de conta, coluna, exercício e período. |
| `src/simulador/rule_engine.py`, `modelo.yaml` | Orquestração, Regra de Ouro, registro/ordem das regras e textos normativos. |
| `src/simulador/dtp.py`, `dcl.py`, `servico_divida.py` | Cálculos de pessoal, estoque e serviço da dívida. |
| `src/simulador/mga_projection.py`, `fluxo_credito.py`, `mga_parameters.py` | Memória/cobertura das operações, fluxo anual de 16% e parâmetro próprio da RCL. |
| `src/simulador/parametros_simulacao.py` | Persistência da taxa percentual compartilhada por CAED e MGA na simulação e conversão em multiplicador. |
| `src/simulador/painel_fiscal.py`, `indicadores_rgf.py` | Posição fiscal anterior à nova operação e indicadores publicados. |
| `src/simulador/data_updater.py`, `sync_job.py`, `capag.py`, `sadipem.py` | Importações, sincronização em segundo plano e clientes externos. |
| `src/web/js/eel-main.js`, `fiscal-dashboard.js`, `config.js` | Eventos/simulação/modais/relatório HTML, apresentação fiscal e configuração de banco. |
| `src/web/css/styles.css`, `src/web/images/`, `assets/` | Identidade visual, logo e ícone do executável. |
| `tests/`, `docs/` | Testes Python/Node/Playwright e documentação de regras/distribuição. |
| `installer/`, `compartilhamento/` | PyInstaller/Inno Setup e distribuição de código por versões na rede. |
| `instance/`, `settings.ini`, `app.log`, `uploads/` | Dados/configurações locais e diagnóstico; preservar. |

`build/`, `dist/`, `.venv/` e caches são artefatos locais. O spec `Operations_Credit_v2.0.spec` é antigo; o build atual gera `Operations_Credit_v2.1.0.exe`. Existem scripts legados em `src/web/javascript/` e `src/web/js/logs.js`; não restaurar rotas Flask ou um terminal de logs a partir deles. `main.html` referencia `js/sys-status.js`, ausente; o monitoramento ativo está em `eel-main.js`.

## Fontes e persistência

- **SICONFI:** `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/{rreo,rgf}`; ente 52, esfera estadual. Importa RREO anexos 01–03 e RGF 01, 02, 03, 04, 06; anexo 01 do RGF consulta poderes E/L/J/M/D. Histórico desde 2021. HTTP paginado, até três tentativas, início espaçado em um segundo; gravações sequenciais e transação por período/anexo/poder. Retificações substituem o período apenas após receber todas as páginas. Cache persistido em `SincronizacaoSiconfi`: uma hora para ano atual, sete dias para anteriores.
- **RCL de endividamento:** `data_access.obter_rcl_ajustada_endividamento`, RREO Anexo 03 de GO, conta ajustada e coluna `TOTAL (ÚLTIMOS 12 MESES)`, último bimestre disponível. Não confundir RCL publicada, ajustada para pessoal e projetada.
- **CAPAG:** `capag.py` consulta CKAN `https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show`, pacote `capag-estados`, e tenta o CSV completo mais recente, recorrendo a publicações anteriores quando o recurso retorna 404/410 ou seus dados são inválidos. Nota e componentes vêm da mesma publicação; não são calculados localmente. Preservar a referência da publicação efetivamente utilizada.
- **SADIPEM:** `sadipem.py`, base `https://apidatalake.tesouro.gov.br/ords/cdwhprd/sadipem/tt/`; fluxo ativo usa `pvl`, `opc-cronograma-liberacoes` e `opnc-pvl-tramitacao-deferido`. Seleciona um snapshot elegível, com paginação, retries e cache em memória. Variáveis `SADIPEM_BASE_URL`/`SADIPEM_CACHE_MINUTES` configuram o cliente. Nunca somar snapshots de PVLs diferentes nem tratar dados históricos como atuais.
- **Margem pública:** `margem_publica.py` integra a consulta automática iniciada no carregamento do Dashboard com a posição fiscal. Os dados fiscais são apresentados imediatamente; o SADIPEM atualiza Dashboard e Limites ao responder. Atualizações fiscais com o mesmo exercício, referência/valor de RCL e projeção preservam o resultado SADIPEM antes de renderizar, evitando alternância para margem desconhecida. Mudança dessa base invalida o resultado. A abertura de Limites reutiliza o resultado do painel, sem consulta duplicada; respostas de um painel substituído são descartadas e a consulta é retomada para o painel atual. Reutiliza clientes/cache SADIPEM; não grava operações, liberações ou cobertura no banco. `indicador_liberacoes=0`, em registro do exercício e do PVL selecionado, confirma ausência de liberações contratadas declaradas (metadados oficiais do cronograma de pagamentos), mesmo quando o endpoint de liberações vem vazio. Vazio sem esse indicador não é zero. Não contratadas listadas são somadas por ano e identificador, sem duplicidade; lista vazia informa nenhuma listada naquele PVL, não inexistência global. Preservar fonte, data, motivos e memória decimal. Referência antiga, conflito, erro, RCL/fator inválido não produzem saldo público.
- **MGA:** a simulação usa a memória interna `OperacaoCredito`/`LiberacaoCredito` e confirmação `CoberturaMga`; o snapshot público SADIPEM não é importado automaticamente como inventário completo. A simulação pode reutilizar seus valores anuais como referência parcial quando faltam liberações no inventário. Identificador único permite edição; alterações invalidam a cobertura. Cronograma da nova operação é hipótese e não é salvo nesse inventário.
- `Base.metadata.create_all` cria tabelas ausentes, sem migrar colunas existentes. `settings.ini` define o banco. `SIMULADOR_DATA_DIR` separa configurações/banco/uploads do código; assets usam `get_asset_path` e `sys._MEIPASS` no executável. O logger ativo grava na raiz em desenvolvimento ou junto ao executável.

## Regras de negócio consolidadas

Este arquivo é a fonte central de contexto técnico e funcional, mas não substitui a validação normativa. As classificações abaixo distinguem conhecimento funcional de comprovação jurídica:

- **Regra validada:** comportamento cuja regra funcional está suficientemente conhecida. Não implica, por si só, validação normativa de todos os critérios, fontes ou exceções.
- **Comportamento legado:** comportamento existente no código cuja validade normativa ou funcional ainda não foi comprovada. Deve ser descrito e preservado até revisão explícita no escopo da tarefa.
- **Pendência de validação:** questão aberta que não deve ser modificada automaticamente pelo agente. Código, testes ou comentários isolados não encerram essa pendência.

O código existente não é, isoladamente, fonte de verdade da regra de negócio. Quando houver divergência entre AGENTS.md, código, testes, documentação ou norma, o agente deve identificar a divergência, explicitar o comportamento atual e não alterar silenciosamente a regra. Não inventar fundamento normativo nem corrigir critérios apenas por parecerem estranhos.

### Regra de Ouro

- **Finalidade e dados:** comparar receitas de operações de crédito com despesas de capital; considerar o valor requisitado no exercício atual. Usa investimentos, inversões financeiras e amortização, nas colunas de despesas liquidadas até o bimestre e restos a pagar não processados.
- **Fonte e período:** SICONFI/RREO persistido; `data_access.py` seleciona o último período por exercício/anexo dos anos atual e anterior. Receitas usam `Até o Bimestre (c)` no anterior e `PREVISÃO ATUALIZADA (a)` no atual. As consultas genéricas não filtram explicitamente UF/esfera; os somatórios filtram conta/coluna, sem filtro adicional de anexo.
- **Lógica, aprovação e igualdade:** margem = despesas de capital − receitas de crédito. No anterior, margem ≥ 0; no atual, margem ≥ valor requisitado. Igualdade atende nos dois casos.
- **Dependências:** as duas avaliações são executadas pelo motor, sem bloqueio automático da atual pela reprovação da anterior. Os próximos passos do YAML não constituem dependências executadas.
- **Ausência de dados — comportamento legado:** sem registros do ano, o motor retorna aprovação. Consultas genéricas convertem nulos em zero; componentes não encontrados permanecem zero no somatório. O painel fiscal verifica a presença de componentes antes de apresentar a regra, portanto seu tratamento de ausência difere do motor.
- **Pendências:** validar aprovação sem dados, completude dos componentes, critérios contábeis/períodos usados e eventuais exceções jurídicas. A fórmula implementada é conhecida; esses comportamentos legados não comprovam enquadramento normativo.

### DTP — Despesa Total com Pessoal

- **Finalidade, dados e fonte:** apresentar o comprometimento com pessoal a partir dos percentuais publicados no SICONFI/RGF-Anexo 01 de GO, esfera estadual, periodicidade Q, coluna `% sobre a RCL Ajustada`, contas contendo `DESPESA TOTAL COM PESSOAL`, poderes E/L/J/M/D e valores não nulos.
- **Lógica, aprovação e igualdade:** selecionar o último quadrimestre com pelo menos seis instituições distintas elegíveis, deduplicar e somar contribuições dos poderes daquele período; total ≤ 60% atende, inclusive igualdade. Não completar poderes com períodos anteriores.
- **Faixas informativas:** alerta em 90% e prudencial em 95% do máximo, com comparação estrita para exceder cada faixa. Máximos registrados: consolidado 60%, Executivo 48,60%, Legislativo 3,40%, Judiciário 6% e Ministério Público 2%. Defensoria sem teto individual separado. Essas faixas não alteram a aprovação global.
- **Dependências e ausência:** não depende da aprovação de outra regra. Sem quadrimestre elegível, a regra não é exibida nem aprovada; zero publicado é válido, nulo não conta.
- **Comportamento legado e pendências:** o mínimo de seis instituições é critério existente sem justificativa normativa comprovada. Validar suficiência da cobertura dos poderes/instituições, tratamento de duplicatas conflitantes e aplicabilidade das faixas individuais antes de ampliar seu efeito decisório.

### Serviço da Dívida — CAED, limite de 11,5%

- **Regra consolidada e fundamento:** art. 7º, II e §4º da [RSF 43/2001](https://legis.senado.leg.br/norma/582604/publicacao/16433616), com metodologia do [MIP 2026.08.21](https://cdn.tesouro.gov.br/sistemas-internos/apex/producao/sistemas/thot/arquivos/publicacoes/55422_1804616/MIP-2026-08-21.pdf), itens 3.12.8.1, 3.12.9 e 4.1.3–4.2.4. Avalia a média simples do comprometimento anual com amortizações, juros e encargos da dívida, incluindo a operação pleiteada e as demais operações elegíveis.
- **Cronograma único e fontes:** juros/encargos e amortização da operação pleiteada são informados pelo usuário; demais operações são pagamentos anuais agregados informados para análise, acompanhados de fonte, data e declaração explícita de cobertura completa. CAED anual = juros/encargos pleiteados + amortização pleiteada + demais operações. O banco só possui cronogramas de liberações do MGA, que não representam pagamentos do CAED; SADIPEM público não comprova cobertura completa e não preenche esses valores automaticamente. Zero exige lançamento explícito; campo vazio é desconhecido. A cobertura declarada não é auditoria automática do documento nem confirmação jurídica de elegibilidade.
- **RCL e período:** `obter_rcl_caed` seleciona SICONFI/RREO-Anexo 03, GO, esfera E, conta ajustada para endividamento, coluna `TOTAL (ÚLTIMOS 12 MESES)`. Considera bimestres encerrados até a data da análise no exercício selecionado ou dezembro anterior. Conserva fonte, conta, coluna, exercício, bimestre, ente e data-base fiscal. Nulo no período mais recente não autoriza recuo para um valor antigo; duplicatas são ambiguidade. RCL deve ser positiva.
- **Taxa e projeção:** o CAED lê a taxa percentual local em `ParametroSimulacao`, chave `taxa_percentual_rcl_caed`. Padrão inicial 2,031208231%; alterações válidas são salvas e reutilizadas. A interface exibe porcentagem editável; internamente multiplicador = 1 + taxa/100. Não consulta API ou norma para preencher o campo. O valor antigo `fator_projecao_rcl` é preservado sem reinterpretar sua unidade. A origem do fator utilizado é parâmetro local do usuário, sem alegar validação normativa de alterações. A janela de referência da análise permanece 22/04–31/12/2026; outras datas seguem pendentes. RCL de dezembro de y = RCL base × multiplicador^(meses entre fim do bimestre base e dezembro de y / 12). Não aplicar ano completo sobre dezembro do próprio ano usar a mesma taxa anual informada também na simulação do MGA, conforme definição funcional do especialista.
- **Alternativas e igualdade:** universo elegível = exercícios com pagamentos positivos da operação pleiteada no cronograma único. A: média simples de CAED/RCL até o término da operação. B: média do mesmo universo restrito a exercícios até 31/12/2027, quando existir. Calcular ambas e usar a menor; empate conserva A. Percentual determinante ≤ 11,5% atende, inclusive igualdade; > 11,5% não atende. Ano isolado acima do limite não reprova por si só. Resultado registra médias, anos elegíveis, alternativa utilizada e limite. Não existe segunda grade independente nem dispensa de B por aprovação de A.
- **Contrato e memória:** todos os anos entre o exercício escolhido e o fim do contrato devem estar presentes, sem duplicidade; horizonte máximo de 50 anos, valores não negativos com precisão em centavos. Cálculos prospectivos usam `Decimal`, precisão 50, sem arredondamento monetário intermediário. DTO usa `estado`/`status` `ATENDE`, `NAO_ATENDE` ou `INCONCLUSIVO`, e `aprovado` true/false/null. `memoria_exata` conserva entrada, fontes, fator, linhas e médias como textos decimais, inclusive nos retornos antecipados; valores de apresentação são separados. Modal e relatório exibem tabelas legíveis, sem JSON do CAED.
- **Ausência e erros:** cobertura não confirmada, componentes ausentes, RCL/fator inválido ou ausente, cronograma inválido, ausência de pagamentos elegíveis, ambiguidade e erro técnico produzem INCONCLUSIVO com motivos estruturados. Nunca converter esses casos em zero ou ATENDE. Alterar dados ou colar valores invalida conclusão e confirmação de cobertura; respostas assíncronas de entradas antigas são descartadas.
- **Histórico separado e dependências:** diagnóstico do exercício anterior exige fechamento no sexto bimestre tanto da RCL quanto das despesas RREO-Anexo 01. Soma juros/encargos e amortização liquidados, mais restos não processados quando disponíveis; usa limite observado de 11,5% sem fator. Falha, ausência ou resultado histórico acima do limite não bloqueiam a análise prospectiva. DCL é avaliada independentemente do resultado do CAED; cada regra mantém sua conclusão própria.
- **Legado substituído:** o comparador estrito `< 11,5%`, o multiplicador anual `2.031208231`, as grades independentes, a execução condicional da segunda hipótese e o bloqueio pelo histórico não integram a regra atual. Não restaurá-los a partir de testes ou textos antigos.
- **Pendências preservadas:** comprovação material da cobertura/elegibilidade das demais operações; fatores para referências fora da janela documentada; exceções/dispensas jurídicas; política definitiva do diagnóstico histórico e tratamento legado dos restos ausentes como zero nesse diagnóstico. A declaração de cobertura não comprova essas questões nem autoriza contratação.

### DCL — Dívida Consolidada Líquida

- **Finalidade, dados e fonte:** verificar percentuais publicados da DCL sobre a RCL ajustada, SICONFI/RGF-Anexo 02 de GO, esfera estadual, periodicidade Q, Executivo; conta `% da DCL sobre a RCL AJUSTADA (III/VI)`.
- **Lógica, aprovação e igualdade:** no maior quadrimestre contendo a conta, extrair `Saldo do exercício anterior` e `Até o Nº Quadrimestre`; comparar individualmente, sem soma. Ambos ≤ 200% atendem; igualdade atende. Não recalcula estoque acrescido da nova operação.
- **Dependências:** é avaliada na simulação e no painel independentemente da aprovação do serviço da dívida.
- **Ausência:** sem a conta no ano, não exibe a regra. Coluna ausente ou valores conflitantes deixam `aprovado = None`/`Sem informação`; não substituir por zero nem por quadrimestre anterior.
- **Pendências:** validar suficiência dessa comparação de posição publicada para o impacto da nova operação, a dependência entre regras e eventuais exceções jurídicas. A lógica funcional é conhecida; o texto do YAML sobre dívida/RCL estimada não comprova cálculo de estoque projetado.

### MGA / limite anual de 16%

- **Finalidade, dados e fontes:** comparar liberações anuais sujeitas ao limite geral com a RCL projetada. Usa RCL ajustada do SICONFI/RREO-Anexo 03, inventário interno `OperacaoCredito`/`LiberacaoCredito`, confirmação `CoberturaMga` e cronograma hipotético da nova operação. SADIPEM público não comprova nem alimenta automaticamente a cobertura integral.
- **Lógica:** MGA anual = liberações contratadas + não contratadas incluídas + nova operação; teto = RCL projetada × 0,16; saldo = teto − MGA, preservando negativo. Para 2026, `mga_parameters.py` registra multiplicador `1.02031208231`, fonte/edição MIP 2026.08.21 e vigência 22/04/2026. Primeiro ano projeta proporcionalmente os meses até dezembro; seguintes aplicam o multiplicador anual. Na simulação, sem RCL do ano, aceita dezembro anterior com referência explícita.
- **Aprovação e igualdade:** cada exercício relevante deve ter MGA ≤ teto; exatamente 16% atende. Conclusão validada exige inventário coberto, cronogramas completos e parâmetro validado. Resultado numérico e conclusão validada são conceitos separados.
- **Apresentação:** Dashboard/Principais Limites mostram a margem anual antes da nova operação: teto de 16% da RCL projetada menos liberações existentes incluídas, reutilizando a posição do backend. Margem de inventário confirmado exige posição sem nova operação, período completo e parâmetro validado. O carregamento do Dashboard também consulta automaticamente o SADIPEM e pode apresentar “Margem segundo o PVL”, em campo separado `margemPublica`, calculada a partir das liberações declaradas/listadas no único PVL do exercício. Esse saldo público é referência parcial, com cobertura não confirmada. Na simulação, liberações anuais declaradas/listadas no mesmo PVL podem preencher exercícios desconhecidos do inventário e ser somadas à nova operação; não substituem valores de inventário confirmado, não preenchem anos sem informação e não geram conclusão validada ou máximo de contratação. A projeção usa a RCL e o parâmetro da própria simulação, preservando fonte, snapshot e memória decimal. Preservar zero e saldo negativo. Teto bruto não é margem disponível; saldo público deve ser identificado como referência segundo o PVL. A tabela MGA com a nova operação pertence à Simulação; Limites apresenta uma memória de margem, fontes e cobertura.
- **Dependências:** composta em `app.py` e acrescentada à lista pelo frontend; não depende da aprovação das outras regras nem integra automaticamente o `circuit_breaker`. Identificador permite excluir a cópia já cadastrada da nova operação para evitar duplicidade; edição do inventário invalida cobertura.
- **Ausência:** distingue desconhecido, zero confirmado e zero assumido em cenário parcial. Cenário apenas da nova operação assume demais liberações zero e permanece parcial. Sem cobertura/parâmetro válido, não publica máximo disponível validado; ausência de RCL ou cronograma impede conclusão. Anos sem evento no cronograma hipotético são preenchidos com zero; isso não confirma ausência de outras operações.
- **Pendências:** cobertura real do inventário, fatores históricos/alternativos, conversões documentadas de moeda e exceções/dispensas jurídicas. O registro do fator de 2026 não é verificação automática de vigência externa nem autorização de contratação.

### CAPAG — indicador publicado

- **Finalidade, dados e fonte:** apresentar nota e componentes de Goiás da publicação CAPAG dos estados no Tesouro Transparente/CKAN; nota, endividamento, poupança corrente e liquidez relativa vêm do CSV selecionado.
- **Lógica:** selecionar publicação completa válida, persistir e apresentar os valores publicados. Não há fórmula local de classificação CAPAG.
- **Aprovação, igualdade e dependências:** não há critério local de aprovação nem comparador de igualdade. `Nota_CAPAG` no YAML não é regra executada pelo motor; a apresentação do indicador não depende da aprovação de outras regras.
- **Ausência:** consulta falha não apaga dados persistidos; sem nota persistida, indicador indisponível. Componentes só são apresentados se corresponderem à mesma publicação/fonte da nota. Publicação anterior usada como alternativa conserva sua referência.
- **Pendências:** atualidade/aplicabilidade da publicação ao pleito e critérios jurídicos de garantia da União. Textos do YAML não comprovam uma verificação executada ou aprovação global.

### Política de conclusão global

As análises são apresentadas individualmente; falha no MGA não descarta os resultados das demais regras, e reprovação ou inconclusão do CAED não omite a DCL. O motor retorna listas de regras cumpridas, violadas e sem informação; o `circuit_breaker` sinaliza violações de DTP, DCL ou serviço da dívida. Reprovação da Regra de Ouro é apresentada, mas não compõe esse sinalizador. MGA é separado; CAPAG e regras de garantias do YAML não são executadas como decisão do motor. DTP/DCL podem ser omitidas quando faltam dados, conforme descrito acima.

**Comportamento legado e pendência de validação:** não existe política comprovada de aprovação global combinando todas as regras, ausências, indicadores e exceções. Ausência de violações ou `circuit_breaker = False` não comprova aprovação integral. Não inferir autorização de contratação, criar aprovação global ou alterar dependências automaticamente.

## Débitos técnicos conhecidos

Registrar estes pontos não autoriza sua correção fora do escopo da tarefa:

- Consultas genéricas usadas pela Regra de Ouro não possuem filtro explícito de UF/esfera; a importação de GO não garante isolamento de bancos com outros entes.
- DTO formatado das regras de Ouro não inclui `aprovado`, embora outras regras retornem esse campo. Preservar consumidores existentes e revisar o contrato explicitamente antes de uniformizá-lo.
- A tabela de resultados e detalhes genéricos usam `innerHTML` com determinados textos, sem escape explícito; revisar os caminhos de conteúdo externo/usuário. A orientação para novas alterações continua sendo `textContent` ou escape.
- README e documentação secundária contêm descrições desatualizadas, como importação CSV/Pandas, caminhos antigos, terminal de logs e localização das entradas do serviço da dívida. Não usar esses trechos para restaurar funcionalidades legadas.
- Teste de conexão SQLite em `app.py` resolve caminho com `get_asset_path`; conexão principal usa `get_config_file_path`. Podem apontar para bancos diferentes com `SIMULADOR_DATA_DIR` ou executável empacotado.
- URLs de conexão podem ser registradas em logs com credenciais nos caminhos de teste/inicialização; revisar proteção desses registros sem expor seu conteúdo.
- `main.html` referencia `js/sys-status.js`, inexistente. O monitoramento ativo permanece em `eel-main.js`.

## Regras para alterações no backend

- Antes de alterar uma regra, ler seu módulo, `data_access.py`, `rule_engine.py`, `modelo.yaml`, testes correspondentes e documentos em `docs/`. Código/testes descrevem o comportamento; documentação pode estar desatualizada e não comprova validade normativa.
- Manter cálculos e acesso a dados no backend; `app.py` deve continuar como ponte. Preservar contratos Eel e DTOs (`tipo`, `status`, `aprovado`, `dados_calculados`, listas ordenadas e `mgaProjection`). Há regras no YAML sem implementação; não apresentá-las como verificações executadas.
- Preservar filtros de ente, anexo, conta, coluna e período, deduplicação e tratamento de ambiguidade. Não somar acumulados de períodos diferentes. Não converter ausência/conflito em zero ou aprovação. Há exceções legadas na Regra de Ouro e conversão de nulos em consultas genéricas: não propagá-las nem corrigi-las silenciosamente fora do escopo solicitado.
- Usar `Decimal` nos novos cálculos financeiros, sem arredondamentos intermediários; manter conversão explícita para DTOs serializáveis e precisão em centavos. Não modificar comparadores de igualdade sem revisar regra e testes: MGA aceita 16%; DCL aceita 200%; CAED aceita média igual a 11,5%.
- MGA deve distinguir desconhecido, zero confirmado e zero assumido em cenário parcial. Preservar saldo negativo, fontes/vigência, ausência de máximo disponível em cenário incompleto e prevenção de duplicidade por identificador.
- Na simulação, CAED e MGA compartilham a taxa percentual local dos dados da operação, por definição explícita do especialista. MGA mantém seu parâmetro documentado para a posição fiscal anterior à simulação; o CAED rejeita o multiplicador legado `2.031208231`. Fonte, vigência e data de referência são obrigatórias; unidade percentual não é multiplicador.
- Não alterar a ordem ou dependências implicitamente: DCL é avaliada independentemente do serviço da dívida; DTP usa o último quadrimestre com ao menos seis instituições. MGA é composto separadamente em `app.py` e acrescentado à lista visual pelo frontend, sem entrar automaticamente no `circuit_breaker` do motor.
- Reutilizar clientes reais, cache, timeouts e transações. Não criar mocks, hardcodes de dados fiscais ou valores de contingência no produto; fixtures/mocks isolados são usados e permitidos nos testes. Não compartilhar `db.session` entre threads; seguir as sessões próprias do importador e CAPAG.

## Regras para alterações no frontend e convenções

- Preservar Dashboard → Principais Limites → Simulação, modais de detalhe e configuração. Manter o padrão institucional verde/amarelo, superfícies claras, classes existentes e layout responsivo; evitar redesign ou introdução de React/Vue/build npm sem pedido.
- `eel-main.js` coordena chamadas `await eel.funcao(...)()`; `fiscal-dashboard.js` apresenta DTOs. Não duplicar regras fiscais no JavaScript nem trocar Eel por endpoints REST inventados. Preservar IDs e ordem dos scripts usados pelos eventos/testes.
- Valor requisitado é único; recebimentos e pagamentos têm períodos separados. Manter formato monetário pt-BR, validação, colagem de Excel e campos vazios distintos de zero. Resumos devem ser compactos; tabelas anuais/fontes ficam em detalhes, com rolagem em telas pequenas.
- A interface de liberações mostra sempre dois campos: primeiro ano e ano final, independentes, a partir do exercício da análise. Preencher primeiro o início; o fim fica desabilitado até um início válido e deve ser igual ou posterior. A grade contém exclusivamente os exercícios entre esses campos, inclusive as extremidades; não há inclusão avulsa de exercício. Alterações de período preservam os valores dos anos que permanecem e não recriam a grade se o intervalo não mudou. O ano final dos pagamentos do CAED é independente. Um único exercício é informado preenchendo os dois anos com o mesmo valor; não há seletor de liberação integral na interface. O backend conserva o modo integral por compatibilidade.
- No primeiro cálculo, as liberações usam inicialmente o exercício de referência já selecionado nos dois campos de período. Um único exercício reutiliza integralmente o valor requisitado, sem segunda entrada monetária editável. O usuário pode alterar início e fim separadamente para informar um cronograma plurianual; nesse caso a distribuição é explícita, sem rateio automático. Trocar o exercício de análise reinicializa esse período; limpar um ano manualmente mantém a validação de ausência.
- Cores da regra de 16% representam a conclusão numérica: verde dentro do limite, vermelho para excesso e cinza quando insuficiente. Ano crítico recebe destaque de texto, sem amarelo automático; ressalva de cobertura não é reprovação nem aprovação global.
- No detalhe do limite de 16%, apresentar teto anual, demais liberações, nova operação e saldo após a operação. Resultado numérico e fonte são separados: dados do PVL não são um status de aprovação. A tabela anual mostra a composição em reais; fontes, taxa percentual efetivamente usada e ressalvas ficam na memória. Preservar zero, saldo negativo e anos desconhecidos; não criar aprovação global.
- A Simulação apresenta dados gerais e a lista de verificações. Ano final dos pagamentos e pagamentos anuais são preenchidos exclusivamente em Ver Detalhes do CAED; liberações e inventário ficam em Ver Detalhes do limite de 16%. Cada campo possui uma única instância. Recalcular em qualquer detalhe atualiza o conjunto das regras e a lista, preservando as conclusões individuais.
- Alterações de entradas invalidam resultados e bloqueiam relatório até recálculo. O relatório usa exatamente o resultado calculado. Texto oriundo de fontes/usuário deve ser inserido com `textContent` ou escapado.
- Seguir nomes/docstrings em português, `snake_case` Python, imports relativos no pacote e funções JavaScript no estilo existente. Não há configuração central de formatter/linter; evitar reformatação ampla de arquivos legados.

## Executar, testar e validar

Comandos PowerShell na raiz. Usar o Python do ambiente virtual; o alias `python` do Windows pode não apontar para uma instalação válida. Não há requisito mínimo de Python declarado; o launcher de rede pede 3.13 e o ambiente local existente usa 3.12.

```powershell
# Preparação, somente se necessário
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-runtime.txt
.\.venv\Scripts\python.exe -m pip install pytest pytest-mock requests-mock
# Aplicação (abre janela e inicia sincronização real)
.\.venv\Scripts\python.exe app.py
# Testes Python isolados
.\.venv\Scripts\python.exe -m pytest tests -q
# JavaScript: Node instalado, sem npm install
node --check src/web/js/eel-main.js
node --check src/web/js/fiscal-dashboard.js
node --check src/web/js/config.js
node tests/test_valor_requisitado.js
node tests/test_paste_grid.js
node tests/test_servico_frontend.js
node tests/test_margem_limites.js
# Opcional para UI: pip install playwright e Chrome instalado
.\.venv\Scripts\python.exe tests/browser_mga.py
.\.venv\Scripts\python.exe -m tests.browser_caed
```

`requirements-runtime.txt` contém o runtime mínimo; `requirements.txt` inclui testes, empacotamento e drivers opcionais. Playwright e Ruff são ferramentas adicionais, não declaradas nesses arquivos. Se Ruff estiver disponível, aplicar `python -m ruff check` aos módulos alterados; não prometer lint global limpo de código legado.

Para empacotar, com PyInstaller instalado:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name Operations_Credit_v2.1.0 --icon assets/icon.ico --add-data 'src/web;src/web' --add-data 'modelo.yaml;.' app.py
# Instalador: Python/PyInstaller no PATH e Inno Setup (ISCC.exe)
powershell -NoProfile -ExecutionPolicy Bypass -File installer/build.ps1
```

Validar testes do domínio alterado e regressões pertinentes; mudanças de interface exigem navegação/modais, estados vazio/parcial/desatualizado e telas estreitas. `browser_mga.py` e `browser_caed.py` usam HTML real com ponte Eel simulada, não é teste completo do servidor ou das APIs reais. Para smoke test real, usar banco/configuração isolados via `SIMULADOR_DATA_DIR`. Não inicializar/sincronizar o banco do usuário para testar. Testes podem acrescentar erros intencionais ao `app.log`; preservar entradas preexistentes. Conferir `git diff --check` e o diff final, relatando limitações de validação.

## Restrições permanentes e pendências

Não apagar/substituir `instance/database.db`, `settings.ini`, logs, dados pessoais ou alterações do usuário. Não incluir credenciais/configuração de desenvolvimento ou banco em artefatos de distribuição. `installer/settings.ini` é o modelo sem credenciais; versões publicadas por `compartilhamento/Publicar-Versao.ps1` são imutáveis. Não publicar, instalar para terceiros ou alterar licenciamento como consequência automática de um ajuste; consultar `LICENSE.md` para distribuição.

O código não comprova cobertura real de todas as operações, dispensas/exceções jurídicas, fatores históricos/alternativos da RCL ou fatores do CAED fora da janela de referência documentada e política impeditiva do histórico. Também não explica normativamente o mínimo de seis instituições da DTP, aprovação legada da Regra de Ouro sem dados ou política final de aprovação combinando todas as regras. Registrar essas dúvidas quando pertinentes; não inventar respostas nem mudar critérios por inferência.

## Manutenção obrigatória do AGENTS.md

Este arquivo deve ser mantido sincronizado com a implementação real.

Sempre que uma alteração modificar de forma relevante:

- arquitetura;
- fórmula, critério de aprovação, limite ou comparador;
- período de referência ou tratamento de ausência de dados;
- fluxo de análise ou dependência entre regras;
- estrutura de diretórios;
- stack ou dependências principais;
- integrações externas;
- fontes de dados;
- fluxo de execução;
- comandos de build/teste;
- regras permanentes para agentes;
- módulos responsáveis por regras de negócio;
- contratos entre frontend e backend;

o agente deve avaliar e, se necessário, atualizar este AGENTS.md na mesma tarefa,
além de avaliar a documentação afetada em `docs/`. Atualizar apenas documentos
secundários não substitui manter esta fonte central coerente.

Mudanças cosméticas ou refatorações internas sem impacto funcional ou estrutural
não exigem atualização. Correções pontuais que alterem algum dos itens acima
exigem a mesma avaliação.

Descrever estado, regras e restrições atuais, sem transformar o arquivo em
histórico cronológico de alterações. Quando AGENTS.md, código, testes,
documentação ou norma divergirem, identificar a divergência antes de alterar
regras de negócio; não assumir silenciosamente qual fonte está correta.
