# Compartilhar o simulador pela pasta da rede

Este método usa uma pasta compartilhada para distribuir o **código**. Cada pessoa instala Python uma vez e abre o simulador por um atalho. Ao iniciar, o atalho copia a versão mais recente para o próprio computador. Não é necessário gerar `.exe` nem usar Inno Setup ou Docker.

## 1. Preparar a pasta compartilhada

1. No Explorador de Arquivos, abra a pasta da rede à qual toda a equipe tem acesso.
2. Crie nela uma pasta chamada `SimuladorCredito`. Você precisa ter permissão de escrita; a equipe precisa apenas de leitura.
3. Clique na barra de endereço do Explorador e copie o caminho. Prefira o endereço completo iniciado por `\\`, por exemplo `\\servidor\equipe\SimuladorCredito`. Cada computador deve conseguir abrir **esse mesmo endereço**.

Não copie `settings.ini`, `instance`, `database.db`, `dist` ou a pasta inteira do projeto para a rede. O script de publicação seleciona somente os arquivos necessários.

## 2. Preparar cada computador (uma vez)

1. Abra o PowerShell pelo menu Iniciar e digite `py -3.13 --version`.
2. Se aparecer `Python 3.13.x`, continue. Caso contrário, instale o Python 3.13 em cada computador. Na instalação, marque a opção para adicionar Python ao PATH. Se o computador da equipe bloquear instalações, solicite essa instalação ao suporte de TI.
3. Confirme que o computador acessa o caminho `\\servidor\equipe\SimuladorCredito` pelo Explorador. Na primeira execução também será preciso acessar a internet (ou o repositório de pacotes Python da organização) para instalar as bibliotecas.

## 3. Publicar a primeira versão (somente no seu computador)

Abra o PowerShell na pasta do projeto, onde está `app.py`, e execute, trocando o endereço pelo caminho real da sua pasta:

```powershell
.\compartilhamento\Publicar-Versao.ps1 -PastaCompartilhada '\\servidor\equipe\SimuladorCredito' -Versao '2.1.0'
```

Se o PowerShell bloquear a execução de scripts, use nesta janela:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\compartilhamento\Publicar-Versao.ps1' -PastaCompartilhada '\\servidor\equipe\SimuladorCredito' -Versao '2.1.0'
```

O comando cria `versoes\2.1.0`, `Iniciar-Simulador.ps1` e `versao-atual.txt` na rede. Confira se aparecer a mensagem de versão publicada.

## 4. Criar o atalho da equipe (uma vez por pessoa)

1. Na Área de Trabalho, clique com o botão direito e escolha **Novo → Atalho**.
2. No campo do local, cole a linha abaixo, substituindo o caminho de exemplo pelo endereço real da pasta compartilhada:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\servidor\equipe\SimuladorCredito\Iniciar-Simulador.ps1"
```

3. Clique em **Avançar**, dê o nome `Simulador de Operações de Crédito` e clique em **Concluir**.
4. Abra o atalho. Na primeira vez, espere a instalação das bibliotecas e mantenha a janela do PowerShell aberta enquanto usar o simulador. O simulador abrirá sua interface. Nas vezes seguintes, a abertura será mais rápida.
5. Se o seletor de anos vier vazio, clique em **Atualizar Dados Siconfi** para carregar os dados no banco local desse computador.

## 5. Publicar mudanças depois

Depois de modificar e testar o código no seu computador, execute de novo o comando de publicação com **um número novo**, por exemplo `2.1.1`:

```powershell
.\compartilhamento\Publicar-Versao.ps1 -PastaCompartilhada '\\servidor\equipe\SimuladorCredito' -Versao '2.1.1'
```

Peça à equipe para fechar e abrir o atalho. Isso basta para receber a versão nova; ninguém precisa reinstalar o programa. Uma sessão já aberta continua na versão anterior até ser fechada.

As configurações, o banco SQLite e os dados pessoais ficam em `%LOCALAPPDATA%\SimuladorCredito\dados` em cada computador. A atualização de código não apaga esse banco. A pasta compartilhada guarda somente versões do programa e o atalho de inicialização.

Para voltar a uma versão anterior, altere o conteúdo de `versao-atual.txt` na pasta compartilhada para o número da versão anterior, salve e reabra o atalho. Não altere o conteúdo de uma versão já publicada.

Se a rede estiver indisponível, o atalho não conseguirá verificar qual versão está publicada. Se a instalação de bibliotecas falhar por falta de acesso ao repositório Python, o suporte de TI precisará liberar o acesso ou fornecer essas bibliotecas internamente.
