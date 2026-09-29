# Integração SICONFI

O botão Atualizar Dados Siconfi consulta automaticamente o histórico coberto pelo projeto (2021 até o ano corrente), ente 52, anexos 01 e 02 de RREO e RGF. Consulta todos os seis bimestres e três quadrimestres de cada ano. Respostas vazias não geram notificações.

## Busca e armazenamento

A interface inicia a sincronização em segundo plano e consulta seu progresso.
O ano atual (RREO e RGF) é processado antes do histórico. O simulador permanece
disponível com os dados já gravados; o botão mostra etapa e consultas concluídas.
Cliques repetidos não iniciam outra sincronização enquanto houver uma em curso.
Fechar o aplicativo interrompe o trabalho; importações já confirmadas são
preservadas e reutilizadas na próxima execução. A primeira sincronização completa
ainda pode levar minutos; executar em segundo plano não reduz a latência da API.

Consultas concluídas são registradas na tabela `sincronizacao_siconfi`, no mesmo
banco dos dados. Atualizações seguintes reutilizam os dados por 24 horas para o
ano atual e por 7 dias para anos anteriores. Respostas vazias são consultadas
novamente após 1 hora. Falhas não são armazenadas nesse controle; uma nova
atualização tenta novamente. A chave inclui endpoint e todos os filtros,
incluindo ente, ano, período, anexo e poder. O registro de importação é salvo na
mesma transação dos dados, somente depois de todas as páginas serem recebidas.

A primeira atualização após essa mudança ainda consulta todo o histórico para
estabelecer esse controle. Nenhum período é considerado completo apenas porque
já existem algumas linhas no banco. Durante o prazo de reutilização, publicações
novas da API só serão buscadas na atualização seguinte ao vencimento do prazo.

- Até três consultas HTTP em andamento, com início limitado a uma requisição por segundo e gravações sequenciais.
- Paginação por offset e hasMore, preservando os parâmetros.
- Uma consulta de chaves existentes e uma transação por período/anexo.
- Falha em uma página impede a gravação parcial daquele período/anexo.
- Insere registros novos; retificações de valores existentes ainda não são aplicadas automaticamente.
- Mantém o filtro preexistente de colunas RREO iniciadas por % e SALDO.

## Interface e análise

O seletor lista os anos existentes na tabela RREO e é recarregado após a atualização. A análise usa o último período disponível por ano/anexo para não misturar acumulados de diferentes períodos.

Os diagnósticos ficam no terminal Python, sem aba de logs nem funções Eel para consultar ou limpar logs. Falhas técnicas geram mensagens simples na interface; ausência de dados é um resultado normal.

## Consulta de 2026

Em 28/09/2026, a API retornou dados dos anexos 01 e 02 para RREO nos bimestres 1, 2 e 3, e RGF do Executivo no quadrimestre 1. Os demais períodos retornaram HTTP 200 com items vazio. Os dados encontrados foram importados no banco local.

## Testes

O RGF-Anexo 01 consulta os cinco poderes (E, L, J, M, D) para a [regra DTP](Regra%20DTP.md).
O RGF-Anexo 02 mantém a consulta do Executivo.

python -m pytest tests -q -p no:cacheprovider
