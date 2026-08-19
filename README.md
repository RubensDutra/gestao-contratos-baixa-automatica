# 📋 Gestão de Contratos — Baixa Automática

Aplicativo web local (Streamlit) que automatiza a **baixa de itens de contratos** a partir de Ordens de Fornecimento (OFs) em PDF.

O app lê a planilha de controle do contrato (`CONTROLE_DE_CONTRATO.xlsx`), extrai os itens dos PDFs das OFs, **identifica automaticamente cada item na planilha** (mesmo com nomes errados ou erros de digitação vindos do fornecedor) e aplica a baixa das quantidades, **preservando 100% do layout, estilos e fórmulas** do arquivo original.

## ✨ Funcionalidades

- 📄 **Leitura automática de PDFs de OFs** — extrai código, descrição, quantidade, unidade, valor unitário e valor total (com tolerância a variações no cabeçalho, ex.: `QUANT`, `QTD`, `QUANTIDADE`).
- 🔍 **Correspondência inteligente** — casamento por similaridade de texto (fuzzy) + valor unitário idêntico, tolerante a erros de digitação do fornecedor.
- 📖 **Dicionário de sinônimos** (`sinonimos.txt`) — corrige nomes errados recorrentes (ex.: `FRAJA DO CONVERSOR = FLANGE DO CONVERSOR`).
- ✋ **Correção manual** — itens não encontrados podem ser casados manualmente com a linha certa da planilha; o app **sugere salvar o sinônimo** automaticamente.
- ⚠️ **Detecção de duplicidade** — quando um item do PDF corresponde a mais de uma linha da planilha, você escolhe quais linhas descontar (multisseleção).
- ✅ **Baixa em lote** — gera os lançamentos na aba *Baixas (Lançamentos)* respeitando fórmulas pré-existentes (`SUMIFS`, `IFERROR(INDEX...)`, etc.).
- 💾 **Backup automático** — antes de atualizar o arquivo original, uma cópia é salva em `data/backup/` com data e hora.
- 📜 **Histórico de baixas** — registro de cada baixa (OF, data, itens e valores) em `data/historico_baixas.json`, com resumo no menu lateral.
- 🌙 Tema claro/escuro e interface em português.

## 🧩 Como funciona

1. **Entrada** — você informa a planilha base e os PDFs das OFs (via upload ou pasta `data/inputs`).
2. **Extração** — o app extrai os itens de cada PDF e encontra o cabeçalho da tabela automaticamente.
3. **Correspondência** — cada item do PDF é comparado com as linhas da planilha:
   - similaridade da descrição ≥ 90% **ou**
   - similaridade ≥ 70% **com o valor unitário idêntico**.
   - Cada item recebe um status: ✅ Aprovado · ⚠️ Duplicidade · ❌ Não encontrado · 🚫 Saldo insuficiente.
4. **Revisão** — você resolve duplicidades (escolhe as linhas) e itens não encontrados (correção manual/sinônimo).
5. **Baixa** — os lançamentos são gravados na aba *Baixas (Lançamentos)*: código, descrição (via fórmula automática), data, quantidade, nº da OF e observação.
6. **Saída** — baixe a planilha atualizada, salve uma cópia em `data/export/` ou **atualize o próprio arquivo original** (com backup automático).

> O arquivo original **nunca é alterado sem você pedir** — o fluxo normal gera uma cópia (download ou `data/export`). O botão *"Atualizar CONTROLE_DE_CONTRATO.xlsx (com backup)"* é a única forma de modificar o original, e ele cria backup antes.

## 📁 Estrutura do projeto

```
gestao-contratos-baixa-automatica/
├── app.py                     # Interface Streamlit
├── config.py                  # Configurações (caminhos, colunas, limiares)
├── requirements.txt           # Dependências
├── assets/
│   └── style.css              # Estilos da interface
├── utils/
│   ├── pdf_extractor.py       # Extração de itens dos PDFs
│   ├── excel_loader.py        # Leitura e mapeamento das colunas da planilha
│   ├── matcher.py             # Correspondência fuzzy + sinônimos
│   ├── baixa_writer.py        # Gravação dos lançamentos (preserva fórmulas)
│   └── historico.py           # Histórico de baixas (JSON)
├── scripts/
│   ├── testar_correspondencia.py  # Teste de correspondência sem abrir o app
│   ├── inspecionar_of.py          # Inspeção de um PDF
│   └── inspecionar_planilha.py    # Inspeção da planilha
├── data/
│   ├── inputs/                # Planilha base e PDFs (entrada)
│   ├── export/                # Cópias geradas (saída)
│   ├── backup/                # Backups do original
│   └── historico_baixas.json  # Registro das baixas (gerado automaticamente)
└── sinonimos.txt              # Dicionário de sinônimos (gerado na 1ª execução)
```

> ⚠️ `data/*.xlsx`, `data/*.json`, `data/inputs/`, `data/export/`, `data/backup/` e `sinonimos.txt` estão no `.gitignore` — **dados reais do contrato nunca vão para o repositório**. Os únicos arquivos versionados em `data/inputs/` são os **dados de exemplo fictícios** descritos abaixo.

## 🧪 Dados de exemplo (100% fictícios)

Para você testar o sistema sem usar dados reais, o repositório inclui em `data/inputs/`:

| Arquivo | O que demonstra |
|---|---|
| `CONTROLE_DE_CONTRATO.xlsx` | Planilha fictícia com 3 abas (`Resumo`, `Itens do Contrato`, `Baixas (Lançamentos)`), 15 itens, fórmulas `SUMIFS`/`IFERROR` e 2 lançamentos da OF-0001 |
| `ORDEM DE FORNECIMENTO - OF-0001_EXEMPLO.pdf` | OF que **já consta na aba Baixas** → demonstra o bloqueio de OF repetida |
| `ORDEM DE FORNECIMENTO - OF-0002_EXEMPLO.pdf` | OF com itens casando normalmente → demonstra a baixa **Aprovado** |
| `ORDEM DE FORNECIMENTO - OF-0003_EXEMPLO.pdf` | Item com nome errado (`SEXTABADO`) e valor divergente → demonstra a **sugestão de sinônimo** |

Todos os nomes, valores, CNPJ e números de contrato são **inventados** — não há qualquer vínculo com dados reais.

Para usar com os seus dados reais, basta substituir esses arquivos pelos seus (ou usar o upload direto na sidebar). Ao atualizar o original, o app gera **backup automático** em `data/backup/`.

## 🚀 Instalação

Requer **Python 3.10+**.

```powershell
cd "C:\caminho\do\seu\projeto\gestao-contratos-baixa-automatica"

# 1. Criar o ambiente virtual (uma vez)
python -m venv .venv

# 2. Instalar as dependências (uma vez)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## ▶️ Como usar

### 1. Iniciar o app

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abra o navegador em `http://localhost:8501`.

### 2. Colocar os arquivos

Copie para `data/inputs/`:

| Arquivo | Descrição |
|---|---|
| `CONTROLE_DE_CONTRATO.xlsx` | A planilha base do contrato (no repositório: versão fictícia de exemplo) |
| `ORDEM DE FORNECIMENTO - OF-XXXX.pdf` | Os PDFs das Ordens de Fornecimento (no repositório: exemplos `OF-0001/0002/0003_EXEMPLO`) |

Ou use o upload direto na sidebar do app.

### 3. Fluxo de uso

1. **📊 Planilha base** → escolha *"Pasta data/inputs"* (ou envie o arquivo).
2. **📄 Ordens de Fornecimento** → marque os PDFs desejados.
3. Confira os **cards** (valores) e os **badges** (situações dos itens) e a **tabela** de correspondência.
4. Itens **⚠️ Duplicidade**: marque no multiselect quais linhas devem receber a quantidade.
5. Itens **❌ Não encontrado**: escolha a linha correta no seletor *"Corrigir manualmente"* e, se quiser, **💡 Salvar sinônimo** para as próximas OFs.
6. Clique em **✅ Confirmar e Dar Baixa**.
7. Clique em **⬇️ Preparar planilha atualizada** e então:
   - **📥** baixar o arquivo, ou
   - **💾 Salvar cópia em data/export**, ou
   - **💾 Atualizar CONTROLE_DE_CONTRATO.xlsx (com backup)** — substitui o original (backup em `data/backup/`).
8. Abra a planilha no Excel — os saldos (coluna *Saldo Disponível*) recalculam automaticamente pelas fórmulas.

### 4. Reaproveitamento

- **Sinônimos**: quando um item do PDF é corrigido manualmente, o par *nome do PDF = nome da planilha* pode ser salvo em `sinonimos.txt` — nas próximas OFs ele casa sozinho.
- **Histórico**: o menu lateral mostra as 10 últimas baixas (OF, quantidade de itens, valor total e data).

## 🔧 Solução de problemas

| Problema | Solução |
|---|---|
| `PermissionError` ao atualizar o original | O arquivo está **aberto no Excel** ou sincronizando no OneDrive. Feche-o, aguarde e clique novamente (o backup já terá sido salvo). |
| Erro de módulo "antigo" após atualização de código | **Reinicie o Streamlit** (Ctrl+C no terminal e rode `streamlit run app.py` de novo). |
| Item do PDF não encontrado | Corrija manualmente e salve o sinônimo; confira se o valor unitário na planilha está preenchido. |
| Quantidade do PDF igual a 0 | O cabeçalho da tabela do PDF não foi reconhecido — confira se usa `QUANT`, `QTD`, `QTDE` ou `QUANTIDADE`. |
| Saldo vazio (`?` na tabela) | A célula de saldo depende de fórmula com cache do Excel — abra e salve o arquivo no Excel uma vez para o app ler os valores. |

## 🧪 Testes

Testes de regressão rápidos (sem abrir o navegador):

```powershell
# Correspondência de um PDF contra a planilha
.\.venv\Scripts\python.exe scripts\testar_correspondencia.py data\inputs\CONTROLE_DE_CONTRATO.xlsx "data\inputs\ORDEM DE FORNECIMENTO - OF-0001_EXEMPLO.pdf"

# Inspecionar PDF / planilha
.\.venv\Scripts\python.exe scripts\inspecionar_of.py "data\inputs\ORDEM DE FORNECIMENTO - OF-0001_EXEMPLO.pdf"
.\.venv\Scripts\python.exe scripts\inspecionar_planilha.py data\inputs\CONTROLE_DE_CONTRATO.xlsx
```

## 🛠️ Tecnologias

| Camada | Ferramenta |
|---|---|
| Interface | Streamlit |
| Planilha | openpyxl + pandas (preserva fórmulas e estilos) |
| PDF | pdfplumber + pypdf |
| Correspondência fuzzy | thefuzz + python-Levenshtein |

---

> Projeto pessoal para controle de contratos de fornecimento. Os dados do contrato (planilha, PDFs e histórico) são armazenados localmente e não são enviados ao repositório.