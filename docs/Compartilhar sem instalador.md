# Simulador na pasta compartilhada

A aplicação usa **cache JSON compartilhado**, sem banco SQL e sem salvar os resultados das simulações. O código é distribuído por versões; cada computador recebe a versão publicada ao abrir o atalho da equipe. Não é necessário manter um serviço Python no servidor.

## Preparação

- Windows 64 bits. Python e bibliotecas estão incluídos no aplicativo portátil; a equipe não instala Python nem usa pip.
- Acesso à internet para consultar as APIs. A primeira abertura copia o aplicativo e suas bibliotecas pela rede.
- Equipe com leitura nas versões do programa e **leitura, criação, renomeação e exclusão de arquivos na subpasta `cache`**. Essas permissões são necessárias para a substituição atômica do JSON.
- Publicador com escrita na pasta das versões e nos arquivos de inicialização.

## Publicar

Na pasta do projeto, execute no PowerShell, com um número de versão novo:

```powershell
.\compartilhamento\Publicar-Versao.ps1 -PastaCompartilhada '\\sefazarquivos\STE\GDPRET\GEDP Flávio\SimuladorCredito' -Versao '2.1.3'
```

No computador de manutenção, a `.venv` deve conter `requirements-runtime.txt` e PyInstaller. O publicador gera um aplicativo portátil atualizado antes de copiar a versão. Também aceita `-ExecutavelPortatil` com uma pasta previamente gerada e validada por `Empacotar-Portatil.ps1`. A pasta de destino deve existir. O publicador copia o aplicativo e seus recursos; não publica `settings.ini`, banco antigo, logs ou arquivos pessoais. Não altere uma versão já publicada. O marcador `versao-atual.txt` só aponta para uma versão após a cópia terminar.

## Abrir

Abra **Simulador de Crédito** (atalho com ícone) na pasta compartilhada ou copie esse atalho para a Área de Trabalho. O terminal fica oculto; falhas de inicialização aparecem em uma janela de aviso. Na primeira execução, a cópia do aplicativo pode demorar. `Abrir-Simulador.cmd` continua disponível para diagnóstico com terminal visível.

O inicializador copia o código para `%LOCALAPPDATA%\SimuladorCredito\versoes` com Python e bibliotecas incluídos. **Não cria banco local.** Todos consultam `cache\dados-fiscais.json` na rede. Se o cache estiver vazio, use **Atualizar Dados Siconfi**. As consultas mantêm os prazos de atualização e as referências das fontes.

As simulações ficam na memória de cada sessão. Logs, preferências de execução e eventual declaração explícita de cobertura CAED ficam no diretório local; não são análises compartilhadas nem comprovação automática de cobertura.

## Atualizações

Publique um novo número de versão. Cada pessoa recebe a atualização ao fechar e abrir o atalho. Sessões já abertas recebem um aviso em até um minuto, enquanto a rede estiver acessível; não são encerradas automaticamente.

As gravações do cache são serializadas por bloqueio de arquivo e publicadas por substituição atômica. Outra máquina relê o JSON quando consulta os dados novamente. Uma tela já renderizada não é uma atualização em tempo real: reabra a aba ou atualize a consulta para visualizar dados novos. Esses mecanismos devem ser verificados também com os acessos reais da equipe no compartilhamento.

Sem acesso à pasta da rede, a aplicação não pode abrir seu cache compartilhado. Não há troca silenciosa para um cache local divergente. O servidor deve incluir a pasta `cache` na rotina de backup. JSON inválido gera erro e não é sobrescrito como se estivesse vazio.

Para voltar a uma versão, altere `versao-atual.txt` para uma versão compatível já publicada e reabra o atalho. Versões anteriores à adoção do JSON não são compatíveis com este cache.

A pasta de entrada da equipe exibe somente o atalho. Arquivos e pastas de suporte usam o atributo Oculto do Windows, mantendo os caminhos existentes. Isso organiza a apresentação; não restringe permissões. A manutenção pode habilitar a exibição de itens ocultos no Explorador.

## Abertura e atualização fiscal

A abertura apresenta primeiro o cache fiscal compartilhado e verifica o ano atual em segundo plano. O botão **Atualizar Dados Siconfi** executa também a revisão do histórico, respeitando os prazos de cache por período. CAPAG automática não mantém o indicador fiscal de atualização aguardando sua consulta. SADIPEM mantém respostas completas por até uma hora no cache compartilhado, com chave por URL, endpoint e parâmetros; falhas ou paginação incompleta não substituem respostas íntegras. A abertura consulta o PVL atual para a margem, sem buscar cronogramas históricos e pagamentos de gráficos que não são exibidos. Chamadas HTTP do painel público executam fora do loop de eventos do Eel para preservar a comunicação da interface. Essas otimizações não alteram valores, períodos ou critérios de cobertura.

O painel fiscal e a lista de anos são reutilizados em `cache/painel-fiscal.json`, um cache derivado apenas da posição pública, sem entradas ou resultados de simulações. A assinatura combina versão do aplicativo, data e data/tamanho do arquivo fiscal. Qualquer mudança invalida o painel; um cache derivado inválido é reconstruído a partir da fonte. RCL projetada e teto de 16% aparecem mesmo quando faltam liberações, preservando a margem como desconhecida quando não puder ser calculada.

A verificação de distribuição deve incluir `--verificar-distribuicao --verificar-apis`: consulta HTTPS SICONFI/SADIPEM e importa períodos reais de RREO/RGF em um JSON de diagnóstico isolado. Não aprovar uma publicação apenas com leitura do cache. O empacotamento inclui recursos adicionais exigidos pelo módulo SSL do Python utilizado no build; preservar verificação de certificados, sem usar `verify=False`.
