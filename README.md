# ERP Interface — Simulador de Reconhecimento Facial

## Objetivo

Aplicação web independente que fornece interface visual para demonstrar e validar o funcionamento do módulo de reconhecimento facial `face-recognition`, sem que o usuário precise manipular arquivos JSON manualmente.

## Arquitetura

| Item | Detalhe |
|------|---------|
| **Tipo** | Aplicação web rodando em Docker |
| **Framework** | Streamlit (Python) |
| **Instalação** | `c:\erp-simulator` (produção Windows) |
| **Banco local** | SQLite (`erp.db`) para gestão de clientes e logs |
| **Comunicação** | Arquivos JSON compartilhados via volume Docker + iframe para face-recognition |
| **Dependências externas** | Nenhuma (não depende do container facial subir) |

## Funcionalidades

### 1. Gestão de Clientes do ERP (CRUD)
- Cadastro independente: `id`, `nome`, `email`, `telefone`
- Lista todos os clientes cadastrados com indicador de status facial
- Remoção de clientes com confirmação
- **Nota:** Este cadastro é independente do face-recognition

### 2. Solicitar Cadastro Facial
- Seleciona um cliente já cadastrado no ERP (sem facial)
- Gera JSON em `entrada/` automaticamente
- Exibe iframe com `erp-aguardando.html` do face-recognition
- Monitora resposta em `saida/` com barra de progresso
- Atualiza status do cliente automaticamente

### 3. Solicitar Validação Facial
- Seleciona um cliente já cadastrado no ERP (com facial)
- Gera JSON em `entrada/` automaticamente
- Exibe iframe com `erp-aguardando.html` do face-recognition
- Exibe resultado visual (MATCH/NO_MATCH + score)

### 4. Histórico de Respostas
- Lista todas as respostas recebidas do sistema facial
- Expandir para ver detalhes de cada solicitação

### 5. Logs de Auditoria
- Registra todas as operações: cadastro, remoção, solicitação, resultado
- Aba "📊 Logs" com histórico completo

### 6. Diagnóstico
- Verifica acessibilidade dos diretórios `entrada/` e `saida/`
- Contagem de arquivos pendentes e respostas
- Exibe configuração de timeout e polling

## Fluxo de Uso

### Cadastro
```
1. Aba "Clientes" → cadastra novo cliente (id, nome, email, telefone)
         │
2. Aba "Cadastro Facial" → seleciona cliente → clica "Solicitar Cadastro Facial"
         │
3. Sistema gera JSON em entrada/
         │
4. Iframe exibe erp-aguardando.html do face-recognition
         │
5. Face-recognition detecta solicitação e redireciona para erp-cadastro.html
         │
6. Captura facial acontece no iframe
         │
7. Face-recognition grava resposta em saida/
         │
8. ERP Interface detecta resposta, remove iframe, atualiza status do cliente
```

### Validação
```
1. Aba "Validação" → seleciona cliente com facial cadastrada
         │
2. Clica "Solicitar Validação Facial"
         │
3. Sistema gera JSON em entrada/
         │
4. Iframe exibe erp-aguardando.html
         │
5. Face-recognition redireciona para erp-validacao.html
         │
6. Validação facial acontece
         │
7. Resposta em saida/ com MATCH/NO_MATCH + score
         │
8. ERP Interface exibe resultado visual
```

## Configuração

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `ERP_PORT` | `8501` | Porta da interface web |
| `ERP_INTEGRATION_PATH` | `./data/erp-integration` | Caminho absoluto para o diretório de integração do face-recognition |
| `ERP_DB_PATH` | `/app/data/erp.db` | Caminho interno do banco SQLite |
| `FACIAL_URL` | `http://host.docker.internal:8080` | URL do serviço face-recognition |
| `POLL_TIMEOUT_S` | `300` | Timeout (segundos) para aguardar resposta facial |
| `POLL_INTERVAL_S` | `2` | Intervalo (segundos) entre polls em `saida/` |

## Como Rodar

### Desenvolvimento (Linux)
```bash
cd erp-interface
docker compose up --build
```
Acesse: `http://localhost:8501`

### Produção (Windows)
1. Copie o projeto para `c:\erp-simulator`
2. Crie arquivo `.env`:
   ```
   ERP_PORT=8501
   ERP_INTEGRATION_PATH=c:/face-recognition/data/erp-integration
   FACIAL_URL=http://host.docker.internal:8080
   POLL_TIMEOUT_S=300
   POLL_INTERVAL_S=2
   ```
3. Execute:
```cmd
cd c:\erp-simulator
docker compose up -d
```
Acesse: `http://localhost:8501`

## Estrutura do Projeto

```
erp-interface/
├── docker-compose.yml   # Docker compose standalone
├── Dockerfile
├── requirements.txt
├── app.py               # Streamlit app
├── .env.example
├── .gitignore
├── .dockerignore
├── README.md            # Este arquivo
└── PLANO.md             # Plano de implementação
```

## Relação com o Face Recognition

Os dois projetos são **independentes** mas se comunicam:

1. **Via arquivos** — JSONs em `entrada/` e `saida/`
2. **Via iframe** — ERP Interface exibe `http://face-recognition/erp-aguardando.html` para captura

```
c:\face-recognition\                 ← facial (motor)
├── data\erp-integration\            ← arquivos compartilhados
└── backend + frontend               ← servidor em :8080

c:\erp-simulator\                    ← erp-interface (painel)
├── docker compose                   ← web app em :8501
└── iframe → :8080                   ← captura facial via iframe
```

## Dados Persistidos

| Tipo | Onde | Descrição |
|------|------|-----------|
| Clientes ERP | SQLite (`erp.db`) | Banco local independente |
| Logs de Auditoria | SQLite (`erp.db`) | Tabela `log_operacoes` |
| Solicitações | `entrada/*.json` | Arquivos que o facial consome |
| Respostas | `saida/*.json` | Arquivos que o facial gera |

## Volume Docker

O banco SQLite é persistido via Docker volume named `erp-db`. Isso garante que os dados sobrevivam a restarts do container.
