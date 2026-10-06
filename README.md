# Simulador de Operações de Crédito - Aplicativo Desktop com Eel

Este é um aplicativo desktop desenvolvido com Python e [Eel](https://github.com/python-eel/Eel) para simular e gerenciar operações de crédito. Ele oferece uma interface de usuário moderna e amigável, permitindo a interação com um banco de dados local e a execução de análises financeiras.

## Funcionalidades

- **Interface Desktop Híbrida:** Utiliza Eel para integrar uma interface web (HTML/CSS/JavaScript) com a lógica de backend Python, proporcionando uma experiência de aplicativo desktop nativa.
- **Análise de Operações de Crédito:** Realiza análises detalhadas de operações de crédito com base em parâmetros como ano e valor requisitado.
- **Gestão de Dados Financeiros:** Permite a obtenção e atualização de dados RREO (Relatório Resumido da Execução Orçamentária) e RGF (Relatório de Gestão Fiscal).
- **Feedback Dinâmico:** Apresenta feedback detalhado sobre as regras de negócio cumpridas e violadas durante a simulação de operações de crédito.
- **Importação de Dados:** Suporta a importação de dados de operações a partir de arquivos CSV.
- **Banco de Dados Local:** Interage com um banco de dados SQLite local para armazenamento persistente de dados.
- **Configuração Flexível:** Configurações como caminho do banco de dados, diretórios de upload e logging são gerenciadas através do arquivo `config.py`.

## Tecnologias Utilizadas

- **Python:** Linguagem de programação principal.
- **Eel:** Biblioteca para criar aplicativos desktop com tecnologias web.
- **SQLAlchemy:** ORM (Object-Relational Mapper) para interação com o banco de dados.
- **SQLite:** Banco de dados leve e embutido para armazenamento de dados.
- **Pandas:** Para manipulação e análise de dados (identificado em `requirements.txt`).
- **HTML, CSS, JavaScript:** Para a construção da interface de usuário.

## Instalação

Para configurar e rodar o projeto localmente, siga os passos abaixo:

1. **Clone o repositório:**

   ```bash
   git clone https://github.com/polianabadio/credit_operations_app.git
   cd credit_operations_app
   ```

2. **Mude para a branch `feat/app-eel`:**

   ```bash
   git checkout feat/app-eel
   ```

3. **Instale as dependências:**

   As dependências do projeto estão listadas no arquivo `requirements.txt`. Instale-as usando pip:

   ```bash
   pip install -r requirements.txt
   ```

## Uso

Para iniciar o aplicativo, execute o arquivo `app.py`:

```bash
python app.py
```

Isso iniciará a aplicação Eel e abrirá a interface do aplicativo em uma janela desktop.

## Estrutura do Projeto

```
credit_operations_app/
├── app.py                  # Ponto de entrada principal da aplicação Eel
├── config.py               # Configurações do aplicativo (caminhos, logging, etc.)
├── database_models.py      # Definições dos modelos de banco de dados SQLAlchemy
├── data_updater.py         # Lógica para atualização e importação de dados (RREO, RGF, CSV)
├── rule_engine.py          # Lógica de análise de operações de crédito
├── utils.py                # Funções utilitárias
├── requirements.txt        # Dependências do projeto Python
├── instance/               # Contém o banco de dados SQLite (database.db) e outros arquivos de instância
├── web/                    # Arquivos da interface web (HTML, CSS, JavaScript) para o Eel
│   ├── css/
│   ├── images/
│   ├── javascript/
│   ├── js/
│   └── main.html           # Página principal da interface
└── app.log                 # Arquivo de log da aplicação
```

## Empacotamento Pyinstaller
Para empacotar o aplicativo em um executável standalone, utilize o PyInstaller com o seguinte comando:

```bash
   pyinstaller --noconsole --onefile --icon="assets/icon.ico" --add-data="src/web;src/web" --add-data="modelo.yaml;." --name="Operations_Credit_v2.1.0" app.py
```
## Instalador Windows

Para gerar o executável atualizado e o instalador, execute no PowerShell, na raiz do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer/build.ps1
```

O script usa o PyInstaller e precisa do compilador `ISCC.exe` do [Inno Setup](https://jrsoftware.org/isdl.php). Se o Inno Setup não estiver instalado, o executável ficará em `dist/Operations_Credit_v2.1.0.exe`; instale o Inno Setup e execute o script novamente. Você também pode passar o caminho do compilador com `-InnoCompiler`. O instalador final será `installer/output/SimuladorOperacoesCredito-Setup-2.1.0.exe`.

O instalador usa `%LOCALAPPDATA%\Programs\SimuladorOperacoesCredito` e não exige permissão de administrador. Ele inclui o executável e um `settings.ini` inicial sem credenciais; o banco SQLite é criado na primeira execução. Atualizações no mesmo diretório preservam o banco e as configurações. O banco e o `settings.ini` desta máquina de desenvolvimento não são incluídos.

## Contribuição

No momento não estamos aceitando contribuições externas. No entanto, sinta-se à vontade para abrir issues.

## Licença

Este projeto está licenciado sob licença personalizada. Veja o arquivo `LICENSE` para mais detalhes.

---

## Desenvolvido por Pedro Galvão [GitHub](https://github.com/PedroFGN1) e Por Poliana Abadio [GitHub](https://github.com/polianabadio)
## 

---
### Integração SADIPEM para o limite anual de crédito

A página **Principais Limites** consulta a [API pública do SADIPEM](https://apidatalake.tesouro.gov.br/docs/sadipem/) sob demanda. O cliente em `src/simulador/sadipem.py` consulta `/pvl`, seleciona um único snapshot elegível do Estado de Goiás pela data/status e consulta `/opc-cronograma-liberacoes` e `/opnc-pvl-tramitacao-deferido` pelo `id_pleito`. Os valores de PVLs diferentes nunca são somados. O cliente faz no máximo uma requisição por segundo, pagina respostas, tenta novamente falhas transitórias e mantém cache por 60 minutos. `SADIPEM_BASE_URL` e `SADIPEM_CACHE_MINUTES` podem alterar a URL e o tempo de cache.

O SICONFI continua sendo a fonte fiscal da RCL e do teto de referência. A RCL publicada **não é rotulada como RCL projetada**. A API pública oferece liberações de contratadas por PVL e, em alguns snapshots, liberações anuais de PVLs ainda não contratados; não oferece um MGA consolidado oficial para toda nova operação. Portanto, a aplicação não apresenta margem efetiva quando faltam cronogramas ou não é possível atestar a cobertura. A simulação anual permite informar RCL projetada, liberações da nova operação e complemento manual de não contratadas; seu resultado é identificado como cenário indicativo.

Na consulta real de 06/10/2026, o PVL mais recente de Goiás era `74460` (`PVL02.001127/2026-73`, status de 30/07/2026). O endpoint público de liberações contratadas não retornou linha para esse PVL; a aplicação registra `NO_DATA`, sem converter ausência em zero. O card exibe os dados básicos reais desse PVL e, separadamente, a última referência histórica localizada: R$ 295.461.624,89 para 2018, no PVL `27067`. Esse valor histórico não entra no cálculo de 2026. Os campos e o comportamento podem mudar em novas publicações.
