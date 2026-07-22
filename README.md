# ask-ME — Analisador de Código com IA - Pojeto de Aprendizado

Aplicação web que recebe um trecho de código (colado ou enviado via arquivo) e retorna,
usando um LLM (Groq / Llama 3.3 70B), uma análise automática com sugestões de melhoria,
testes gerados e riscos de segurança identificados. Cada usuário autenticado tem seu
próprio histórico de análises.

## O que foi feito

- **Análise de código via IA**: endpoint que envia o código para a Groq API e retorna
  sugestões de melhoria, testes sugeridos e riscos de segurança em formato estruturado,
  com retry automático caso o modelo não devolva um JSON válido no primeiro pedido.
- **Autenticação via Google OAuth**: login com conta Google (fluxo authorization-code
  com proteção CSRF via `state`), sessão mantida com JWT próprio (HS256), token guardado
  apenas em memória no frontend (nunca em `localStorage`/`sessionStorage`).
- **Histórico por usuário**: toda análise realizada é persistida no PostgreSQL e associada
  ao usuário autenticado, consultável na página de histórico.
- **Rate limiting por usuário**: limite de requisições por usuário autenticado para
  conter custo/abuso da API de IA.
- **Frontend em React**: tela de login, tela de análise (textarea + upload de arquivo
  único), tela de histórico e navegação entre elas, com logout e redirecionamento
  automático ao expirar a sessão (interceptor de 401).
- **Stack containerizada**: banco, backend e frontend rodam via Docker Compose, com
  migrações do banco (Alembic) aplicadas automaticamente na subida do backend.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, PyJWT, `groq` SDK
- **Frontend**: React 18, Vite, TypeScript, react-router-dom
- **Banco de dados**: PostgreSQL
- **Infra**: Docker Compose (db / backend / frontend)

## Como rodar

1. Copie o arquivo de exemplo de variáveis de ambiente:

   ```bash
   cp .env.example .env
   ```

2. Preencha no `.env`:
   - `GROQ_API_KEY` — chave gerada em [console.groq.com](https://console.groq.com)
   - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — criados no Google Cloud Console,
     usando `http://localhost:8000/auth/google/callback` como redirect URI
   - `JWT_SECRET` — qualquer valor aleatório e secreto (ex.: `openssl rand -hex 32`)

   Os demais valores (`DATABASE_URL`, `FRONTEND_URL`, `POSTGRES_*`, `VITE_API_BASE_URL`)
   já vêm prontos para uso local e não precisam ser alterados.

3. Suba a stack:

   ```bash
   docker compose up --build
   ```

4. Acesse `http://localhost:5173`, clique em "Entrar com Google" e faça login com uma
   conta autorizada no consentimento OAuth (necessário se o app estiver em modo de
   teste no Google Cloud Console).

Serviços expostos: frontend em `:5173`, backend em `:8000`, Postgres apenas interno
à rede do Compose.

Para parar: `Ctrl+C` e depois `docker compose down` (adicione `-v` para também apagar
os dados do Postgres).

## ADR (Architecture Decision Records)

Decisões de arquitetura tomadas durante o desenvolvimento e o motivo de cada uma.

| Decisão                                                                                                                                                   | Motivo                                                                                                                                                                                                                               |
| --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Groq** (`llama-3.3-70b-versatile`) como provedor de IA, em vez de OpenAI/Anthropic                                                                      | Gratuito no tier atual do Groq, evitando custo por requisição de análise.                                                                                                                                                            |
| **Google OAuth** para login, sem cadastro de senha próprio                                                                                                | Elimina a necessidade de armazenar/gerenciar credenciais; login mais simples para o usuário.                                                                                                                                         |
| **Sessão via JWT próprio** (HS256, emitido pelo backend após o OAuth), guardado **apenas em memória** no frontend (nunca `localStorage`/`sessionStorage`) | Reduz a superfície de roubo de token via XSS — um script malicioso não consegue ler o token de um storage persistente porque ele não existe fora da memória do processo React. Custo: a sessão não sobrevive a um refresh de página. |
| Proteção CSRF no fluxo OAuth via parâmetro `state` (cookie HttpOnly/SameSite=Lax, comparação em tempo constante)                                          | O fluxo authorization-code é vulnerável a CSRF sem esse parâmetro — um invasor poderia associar sua própria conta Google à sessão da vítima.                                                                                         |
| **Rate limiting por `user_id`**, não por IP                                                                                                               | Usuários atrás do mesmo IP (rede corporativa, NAT) não devem compartilhar limite; e o limite por usuário autenticado é o que realmente protege o custo da API de IA.                                                                 |
| Rate limiter **próprio, em memória**, em vez de `slowapi`                                                                                                 | `slowapi` extrai a chave de limite por IP por padrão; adaptá-lo para chavear por usuário autenticado exigiria a mesma integração manual que um limiter próprio, então optou-se por uma solução simples e diretamente testável.       |
| Tipos **portáveis** no SQLAlchemy (`String(36)` para UUID em vez de `UUID` do Postgres, `JSON` em vez de `JSONB`)                                         | Permite rodar o mesmo schema e a mesma suíte de testes contra SQLite em memória (CI, sem depender de um Postgres real), enquanto continua funcionando sem alteração contra o Postgres real do Docker Compose.                        |
| **Histórico de análises por usuário**, não compartilhado globalmente                                                                                      | Cada análise pode conter código proprietário; histórico global vazaria código entre usuários.                                                                                                                                        |
| Upload de arquivo é só uma conveniência para preencher a textarea — o backend sempre recebe texto de código, nunca um binário                             | Simplifica a API (um único formato de entrada) e evita lidar com parsing de formatos de arquivo diversos no servidor.                                                                                                                |
| Testes de backend usam **mocks da Groq** — sem chamada real à API no pipeline padrão                                                                      | Evita custo e flakiness (respostas não determinísticas de LLM) nos testes automatizados.                                                                                                                                             |
| `docker-compose` com **healthcheck do Postgres** (`pg_isready`) gating a subida do backend (`condition: service_healthy`)                                 | Sem o healthcheck, o backend tenta rodar `alembic upgrade head` antes do Postgres aceitar conexões e falha com `Connection refused` na primeira subida.                                                                              |
| `.dockerignore` em `backend/` e `frontend/` excluindo `.env`                                                                                              | `COPY . .` no Dockerfile poderia embutir segredos locais (chaves de API, client secret) na imagem gerada.                                                                                                                            |
| Porta do Postgres **não publicada** no host (`5432:5432` removida do compose)                                                                             | O banco só precisa ser acessível pelos outros serviços na rede interna do Compose; publicá-la no host expõe desnecessariamente o banco à máquina local.                                                                              |
