# AI Code Analyzer — Design Spec

Data: 2026-07-21
Status: Aprovado para planejamento de implementação

## 1. Visão geral

MVP de uma ferramenta que analisa código colado (ou enviado via arquivo) usando um LLM
(Groq / Llama 3.3 70B Versatile) e retorna sugestões de melhoria, testes gerados e
riscos de segurança identificados. Serve como projeto de portfólio demonstrando
fundamentos de front-end, back-end, persistência, segurança e testes.

**Fora de escopo para este MVP:** múltiplos provedores de IA simultâneos, edição
colaborativa, análise de múltiplos arquivos/repositórios, CI/CD, deploy em produção.

## 2. Arquitetura

```
[React (Vite) SPA] --JWT (Authorization: Bearer)--> [FastAPI backend] --HTTPS--> [Groq API]
                                                            |
                                                      [PostgreSQL]
```

- O front-end nunca fala diretamente com a Groq nem guarda API keys.
- O back-end é o único responsável por: autenticação (Google OAuth), montagem de
  prompt, chamada à Groq, persistência do histórico, rate limiting e validação de
  input.
- Três serviços no `docker-compose.yml`: `frontend`, `backend`, `db` (Postgres).

## 3. Front-end (React + Vite)

### Telas
- **`/login`** — botão "Entrar com Google"; inicia o fluxo OAuth redirecionando para
  `GET /auth/google/login` no back-end.
- **`/` (rota protegida)** — tela principal:
  - Seletor de linguagem (dropdown com lista fixa: JavaScript, Python, Java, Go, etc.)
  - `Textarea` para colar código **e** input de upload de arquivo único (o upload lê o
    conteúdo do arquivo e popula a textarea — não há envio de arquivo binário ao back).
  - Botão "Analisar" (desabilitado durante loading).
  - Painel de resultado com três seções: **Sugestões**, **Testes Gerados** (com
    highlight de sintaxe), **Riscos de Segurança**.
- **`/historico` (rota protegida)** — lista paginada das análises do usuário logado
  (data, linguagem, trecho do código, link para reabrir o resultado completo).

### Componentes principais
`CodeInput`, `AnalysisResult`, `HistoryList`, `AuthGuard` (wrapper de rota protegida),
`AuthProvider` (contexto React com o JWT e o usuário logado).

### Comunicação com a API
Cliente HTTP (fetch/axios) injeta `Authorization: Bearer <jwt>` em toda chamada
autenticada. Interceptor de resposta: em `401`, limpa sessão local e redireciona para
`/login`.

## 4. Back-end (Python/FastAPI)

### Estrutura de módulos
```
app/
  main.py                 # cria app, inclui routers, configura CORS
  auth/
    google_oauth.py        # troca authorization code por id_token/dados do usuário
    jwt.py                  # emite/valida JWT de sessão próprio
    dependencies.py         # get_current_user (FastAPI Depends)
  analysis/
    router.py               # POST /analyze, GET /history, GET /history/{id}
    prompt_builder.py        # monta o prompt estruturado enviado à Groq
    groq_client.py            # chama a API Groq; trata timeout/erro/parsing
    schemas.py                # Pydantic: AnalyzeRequest, AnalyzeResponse, etc.
  db/
    models.py                # SQLAlchemy: User, Analysis
    session.py                # engine/session factory
    migrations/                # Alembic
  core/
    rate_limit.py              # limite por user_id (slowapi)
    config.py                   # leitura de env vars (pydantic-settings)
tests/
  ...                            # espelha a estrutura acima
```

### Endpoints

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/auth/google/login` | não | Redireciona para o consentimento do Google |
| GET | `/auth/google/callback` | não | Troca `code` pelo `id_token`, cria/atualiza `User`, retorna JWT próprio |
| POST | `/analyze` | sim | Recebe `{ codigo, linguagem }`, valida, monta prompt, chama Groq, persiste, retorna resultado |
| GET | `/history` | sim | Lista paginada das análises do usuário autenticado |
| GET | `/history/{id}` | sim | Detalhe de uma análise (só se pertencer ao usuário) |

### Contrato de `POST /analyze`

Request:
```json
{ "codigo": "string (max 20000 chars)", "linguagem": "javascript|python|java|go|..." }
```

Response (200):
```json
{
  "sugestoes": ["string", "..."],
  "testes_gerados": "string (código dos testes)",
  "riscos_seguranca": ["string", "..."]
}
```

Erros tratados: `422` (código vazio, acima do limite de tamanho, ou linguagem fora da
lista permitida), `401` (sem JWT ou JWT inválido/expirado), `429` (rate limit
excedido), `502` (Groq indisponível, timeout, ou resposta que não pôde ser parseada
como o schema esperado mesmo após uma tentativa de re-prompt).

### Prompt e parsing

Template fixo injeta `linguagem` e `codigo`, instruindo o modelo a responder
**exclusivamente em JSON** com as chaves `sugestoes`, `testes_gerados`,
`riscos_seguranca`. A resposta é validada contra o schema Pydantic; se falhar o
parse, uma única retentativa é feita reforçando o formato esperado — se falhar de
novo, retorna `502`.

## 5. Autenticação (Google OAuth + JWT próprio)

1. Front redireciona para `GET /auth/google/login`.
2. Back redireciona ao consentimento do Google; no callback, o Google chama
   `GET /auth/google/callback?code=...`.
3. Back troca o `code` pelo `id_token`, extrai `sub`, `email`, `name`, `picture`.
4. Back faz upsert do `User` (chave: `google_sub`), emite um JWT próprio (assinado com
   `JWT_SECRET`, expiração curta, ex. 1h, sem refresh token no MVP) e devolve ao front
   (via redirect com token na URL de callback do front, ou POST — decidir na
   implementação seguindo boas práticas de não vazar token em logs/histórico do
   navegador).
5. Front guarda o JWT (memória/contexto React, não localStorage, para reduzir
   exposição a XSS) e o envia em `Authorization: Bearer` nas chamadas subsequentes.
6. `get_current_user` (dependency) decodifica e valida o JWT em cada rota protegida.

## 6. Banco de dados (PostgreSQL)

### Tabela `users`
| coluna | tipo | notas |
|---|---|---|
| id | UUID | PK |
| google_sub | string | unique, not null |
| email | string | not null |
| name | string | not null |
| avatar_url | string | nullable |
| created_at | timestamp | default now() |

### Tabela `analyses`
| coluna | tipo | notas |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id, not null |
| language | string | not null |
| code_snippet | text | código enviado (truncado se exceder limite de storage) |
| suggestions | jsonb | not null |
| generated_tests | text | not null |
| security_risks | jsonb | not null |
| created_at | timestamp | default now() |

Índice composto em `(user_id, created_at desc)` para paginação do histórico.
Migrações gerenciadas via Alembic.

## 7. Segurança

- `GROQ_API_KEY`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`,
  `DATABASE_URL` e `FRONTEND_URL` só existem como env vars do container do back-end
  (nunca no front, nunca logadas).
- Rate limiting por `user_id` (ex.: 10 análises/minuto) via `slowapi`, storage
  in-memory (suficiente para uma única instância do back no MVP).
- Validação de input: tamanho máximo do código (20.000 caracteres), linguagem
  restrita a uma lista permitida (enum); payloads inválidos retornam `422`.
- CORS restrito à origem definida em `FRONTEND_URL`.
- `id_token` do Google é validado (assinatura, `aud`, `exp`) antes de criar/atualizar
  o usuário e emitir o JWT de sessão.

## 8. Testes (Pytest)

Todos os testes de integração com IA usam **mock** da Groq (sem custo, sem rede):

- `prompt_builder`: gera o prompt correto a partir de `codigo` + `linguagem`.
- `groq_client`: trata timeout, erro 4xx/5xx da API externa, resposta com JSON
  malformado (aciona a retentativa e depois o erro tratado).
- `POST /analyze`: caso de sucesso (mock retorna JSON válido) grava no banco e
  retorna o schema esperado; rejeita código vazio ou acima do limite (`422`); rejeita
  requisição sem JWT (`401`); respeita o rate limit (`429`).
- `auth`: JWT válido resolve para o usuário correto; JWT ausente/expirado/inválido
  retorna `401`.
- Banco de testes isolado do banco de desenvolvimento (fixture com banco de teste
  dedicado ou transação por teste — detalhe de implementação).

## 9. Docker Compose

Três serviços:

```yaml
services:
  db:
    image: postgres:16
    environment: [POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]
    volumes: [pgdata:/var/lib/postgresql/data]
  backend:
    build: ./backend
    env_file: .env
    depends_on: [db]
    ports: ["8000:8000"]
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    depends_on: [backend]
volumes:
  pgdata:
```

`docker-compose up` sobe o ambiente completo com um comando. Um `.env.example`
documenta todas as variáveis necessárias: `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `JWT_SECRET`, `DATABASE_URL`, `FRONTEND_URL`.

## 10. Decisões registradas

- IA: Groq, modelo `llama-3.3-70b-versatile` (gratuito no tier atual do Groq).
- Front: React + Vite.
- Back: Python + FastAPI.
- Banco: PostgreSQL (via Docker Compose, Alembic para migrações).
- Auth: Google OAuth no login, sessão via JWT próprio emitido pelo back.
- Histórico de análises é por usuário (não compartilhado globalmente).
- Rate limiting por `user_id` (não por IP).
- Upload de arquivo é aceito como conveniência para popular a textarea, mas o input
  enviado à API é sempre texto de código, não um arquivo binário.
- Testes de back-end usam mocks da Groq; não há testes de integração real com custo
  de API no pipeline padrão.
