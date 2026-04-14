# Plano de Implementação — ERP Interface

## Objetivo

Criar um simulador de ERP web-based que permita cadastrar e validar clientes via reconhecimento facial, utilizando o sistema `face-recognition` já existente.

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│                        Docker Desktop (Windows)                   │
│                                                                   │
│  ┌────────────────────┐         ┌────────────────────────────┐   │
│  │ face-recognition   │         │ erp-interface              │   │
│  │ porta: 8080        │         │ porta: 8501                │   │
│  │                    │         │                            │   │
│  │ - watcher detecta  │◄───────►│ - gera JSON em entrada/    │   │
│  │   JSON em entrada/ │         │ - lê resposta em saida/    │   │
│  │ - redireciona para │         │ - SQLite local (clientes)  │   │
│  │   erp-cadastro.html│  iframe  │ - exibe iframe :8080       │   │
│  │ - grava resposta   │         │                            │   │
│  │   em saida/        │         │                            │   │
│  └────────────────────┘         └────────────────────────────┘   │
│                                                                   │
│  Volume compartilhado: c:/face-recognition/data/erp-integration  │
│  Comunicação: arquivos JSON (entrada/ e saida/)                   │
└──────────────────────────────────────────────────────────────────┘
```

## Fases de Implementação

### Fase 1 — Estrutura do Projeto ✅ (feito)

| Item | Status | Arquivo |
|------|--------|---------|
| `docker-compose.yml` | ✅ | `docker-compose.yml` |
| `Dockerfile` | ✅ | `Dockerfile` |
| `requirements.txt` | ✅ | `requirements.txt` |
| `.env.example` | ✅ | `.env.example` |
| `.gitignore` | ✅ | `.gitignore` |
| `.dockerignore` | ✅ | `.dockerignore` |

### Fase 2 — Refinamento do app.py ✅ (feito)

| Item | Descrição | Status |
|------|-----------|--------|
| 2.1 | Session state para controle de fluxo (evitar re-execução) | ✅ |
| 2.2 | Tratamento de erros robusto (diretórios inexistentes, JSON malformado) | ✅ |
| 2.3 | Feedback visual com barras de progresso e spinners | ✅ |
| 2.4 | Remoção automática do iframe após conclusão | ✅ |
| 2.5 | Timeout configurável com feedback ao usuário | ✅ |
| 2.6 | Confirmação antes de remover cliente | ✅ |

### Fase 3 — Persistência e Infraestrutura ✅ (feito)

| Item | Descrição | Status |
|------|-----------|--------|
| 3.1 | `.gitignore` do projeto | ✅ |
| 3.2 | `.dockerignore` do projeto | ✅ |
| 3.3 | Volume Docker para SQLite persistir entre restarts | ✅ |
| 3.4 | Configuração correta de `FACIAL_URL` para Docker Desktop Windows | ✅ |

### Fase 4 — Logs e Auditoria ✅ (feito)

| Item | Descrição | Status |
|------|-----------|--------|
| 4.1 | Tabela `log_operacoes` no SQLite | ✅ |
| 4.2 | Registrar: quem solicitou, quando, resultado, tempo | ✅ |
| 4.3 | Aba "📊 Logs" na interface | ✅ |

### Fase 5 — Validação e Testes ✅ (feito)

| Item | Descrição | Status |
|------|-----------|--------|
| 5.1 | Build Docker local (`docker compose up --build`) | ✅ |

### Fase 6 — Documentação Final

| Item | Descrição | Status |
|------|-----------|--------|
| 6.1 | README.md com instruções completas de instalação | ⬜ |
| 6.2 | Documentar variáveis de ambiente | ⬜ |

## Fluxo de Uso Final

### Cadastro
1. Usuário acessa `http://localhost:8501`
2. Aba **Clientes** → cadastra novo cliente (id, nome, email, telefone)
3. Aba **Cadastro Facial** → seleciona cliente → clica "Solicitar Cadastro Facial"
4. Sistema gera JSON em `entrada/`
5. Iframe exibe `erp-aguardando.html` do face-recognition
6. Face-recognition detecta solicitação e redireciona para `erp-cadastro.html`
7. Captura facial acontece no iframe
8. Face-recognition grava resposta em `saida/`
9. ERP Interface detecta resposta, remove iframe, atualiza status do cliente

### Validação
1. Aba **Validação** → seleciona cliente com facial cadastrada
2. Clica "Solicitar Validação Facial"
3. Sistema gera JSON em `entrada/`
4. Iframe exibe `erp-aguardando.html`
5. Face-recognition redireciona para `erp-validacao.html`
6. Validação facial acontece
7. Resposta em `saida/` com MATCH/NO_MATCH + score
8. ERP Interface exibe resultado visual

## Critérios de Aceite

- [ ] CRUD de clientes funcional
- [ ] Cadastro facial via iframe funciona de ponta a ponta
- [ ] Validação facial via iframe funciona de ponta a ponta
- [ ] Histórico de respostas acessível
- [ ] Logs de auditoria registrados
- [ ] Banco SQLite persiste entre restarts do container
- [ ] Build Docker sem erros
- [ ] Documentação completa no README.md
