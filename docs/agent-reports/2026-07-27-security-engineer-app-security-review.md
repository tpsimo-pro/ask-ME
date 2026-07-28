# Revisão de Segurança — ask-ME (pós PR #8, auth JWT + OAuth)

**Data:** 2026-07-27
**Escopo:** Backend FastAPI (`backend/app/`), frontend React/Vite (`frontend/src/`), Docker Compose, CI, manifests de dependências, com foco no fluxo de autenticação (Google OAuth + credenciais, JWT + refresh token rotativo, reset de senha) e varredura geral (OWASP Top 10) sobre `analysis`, CORS, secrets e supply chain.

## Como foi revisado

Leitura completa e manual do código-fonte (não uso de scanners automatizados):

- Autenticação: `backend/app/auth/*.py` (jwt, refresh_tokens, reset_tokens, passwords, service, router_credentials, router_google, router_session, dependencies, google_oauth, email_sender), `backend/app/db/models.py`, `backend/app/core/config.py`, `backend/app/core/rate_limit.py`, `backend/app/main.py`.
- Feature `analysis`: `backend/app/analysis/{router,service,groq_client,prompt_builder,schemas}.py`.
- Frontend: `frontend/src/api/{client,auth}.ts`, `frontend/src/context/AuthContext.tsx`, `frontend/src/components/{AuthGuard,AnalysisResult,AuthLayout}.tsx`, `frontend/src/pages/ResetPasswordPage.tsx`.
- Infra/config: `docker-compose.yml`, `.env.example`, `.github/workflows/tests.yml`, `backend/requirements.txt`, `frontend/package.json`, `.gitignore` (confirmado que `.env` não está versionado).

Modelo de ameaça considerado: atacante externo não autenticado (via rede/HTTP), atacante autenticado tentando escalar para outros usuários (IDOR/broken access control), atacante com posição "man-in-the-middle" parcial ou acesso a logs de infraestrutura, e um site malicioso tentando abusar do navegador de uma vítima autenticada (CSRF/XSS).

---

## Achados (do mais crítico ao mais sutil)

### 1. [ALTO] Fluxo de reset de senha não envia e-mail em nenhum ambiente — token fica em texto claro nos logs da aplicação

**Local:** `backend/app/auth/email_sender.py:31-32` (`get_email_sender()`), usado por `backend/app/auth/router_credentials.py:70` e `backend/app/auth/service.py:66-93`.

```python
def get_email_sender() -> EmailSender:
    return ConsoleEmailSender()
```

Não há nenhuma ramificação por ambiente (dev/staging/prod) nem variável de configuração que troque `ConsoleEmailSender` por um provedor real (SMTP/SendGrid/SES/etc.). O comentário na classe deixa claro que essa é uma escolha deliberada para dev, mas **o código como está hoje é o único caminho existente** — se este PR for implantado em produção sem alteração, o link de reset de senha (`{FRONTEND_URL}/reset-password?token=<raw>`) é escrito em texto claro no log da aplicação (`logger.warning`) para qualquer solicitação de "esqueci minha senha".

**Cenário de exploração:** Qualquer pessoa com acesso de leitura aos logs — operador de infraestrutura, ferramenta de agregação de logs (CloudWatch/Datadog/ELK) mal configurada como pública, ou um atacante que explore uma falha não relacionada dando acesso a logs — pode ler o token bruto de reset de qualquer usuário que peça redefinição de senha e sequestrar a conta antes do dono, sem precisar de acesso à caixa de e-mail. Como o token é de uso único mas válido por 60 min (`reset_token_expire_minutes`), a janela de exploração é real.

**Correção recomendada:** Implementar um `EmailSender` real (SMTP/provedor transacional) e selecionar a implementação por variável de ambiente (`ENVIRONMENT`/`EMAIL_PROVIDER`), com `ConsoleEmailSender` habilitado *apenas* quando `ENVIRONMENT=development`. Adicionalmente, evitar logar o corpo completo do e-mail (que contém a URL com o token) mesmo no ambiente de dev — mascarar o token no log e, se necessário para debug, imprimir só os primeiros caracteres.

---

### 2. [ALTO] `JWT_SECRET` sem validação de força e valor placeholder óbvio no template de configuração

**Local:** `backend/app/core/config.py:9` (`jwt_secret: str`), `.env.example:3` (`JWT_SECRET=change-me`).

Não há nenhuma validação de comprimento/entropia mínima para `jwt_secret` no `Settings` (Pydantic). Um deploy que esqueça de sobrescrever `.env.example` — cenário comum em projetos pequenos/pessoais indo para produção rapidamente — sobe com `JWT_SECRET=change-me`, um segredo trivialmente adivinhável.

**Cenário de exploração:** Com o segredo HS256 conhecido, qualquer atacante forja um `access_token` JWT válido (`{"sub": "<qualquer-user-id>", "exp": ...}`) para **qualquer** `user_id` existente (UUIDs previsíveis o suficiente de se obter via outros vazamentos, ou até por força bruta caso IDs sejam sequenciais — aqui são UUIDv4, o que mitiga adivinhação, mas não o risco do segredo fraco) e passa a acessar `/history`, `/analyze` etc. como esse usuário — bypass total de autenticação.

**Correção recomendada:** Adicionar um `field_validator` em `Settings` que rejeite segredos com menos de, por exemplo, 32 bytes de entropia ou que estejam em uma lista de valores óbvios (`change-me`, `secret`, vazio). Documentar claramente no README/`.env.example` como gerar um segredo forte (`openssl rand -hex 32`). Considerar também suporte a rotação de `JWT_SECRET` (ex.: aceitar uma lista de segredos válidos para decodificar, assinando sempre com o mais novo) para permitir rotação sem invalidar todas as sessões instantaneamente.

---

### 3. [MÉDIO] Rate limiting em memória, keyed por IP do socket — quebra atrás de proxy/load balancer e não é compartilhado entre processos/réplicas

**Local:** `backend/app/core/rate_limit.py:13-72`, especificamente `_client_ip()` (linha 58-59) usando `request.client.host`.

Dois problemas compostos:

1. **Estado local por processo:** `InMemoryRateLimiter` guarda os hits em um `dict` no processo Python. Se o backend rodar com múltiplos workers Uvicorn/Gunicorn ou múltiplas réplicas (comum atrás de qualquer load balancer em produção), cada processo tem seu próprio contador — um atacante distribui as tentativas entre workers/réplicas e multiplica o limite efetivo por N.
2. **IP não confiável atrás de proxy reverso:** se o backend for implantado atrás de um reverse proxy/load balancer que faz TLS termination (Nginx, ALB, Cloudflare — cenário típico de produção), `request.client.host` será o IP do proxy, **não o IP real do cliente**. Isso tem dois efeitos: (a) o rate limit de login/registro/forgot-password vira um limite *global* compartilhado por todos os usuários — um único atacante insistente pode causar negação de serviço para logins legítimos de todos os outros usuários ao esgotar a cota do "IP" do proxy; (b) um atacante que queira forçar senha por brute-force pode, na prática, contornar o limite completamente se o app não estiver atrás de proxy (usando múltiplos IPs de origem/botnet), já que não há segundo fator de limitação (ex. por conta/e-mail).

**Correção recomendada:** Para produção, mover os limitadores para um backend compartilhado (Redis, ex. `slowapi` com storage Redis) e, se houver reverse proxy, configurar Uvicorn com `--proxy-headers --forwarded-allow-ips` (ou middleware equivalente) para que `request.client.host` reflita o `X-Forwarded-For` de forma confiável — só habilitar isso se o proxy for confiável (senão o header é falsificável pelo próprio cliente). Considerar também limitar por combinação IP+e-mail para login, para que um IP compartilhado (NAT corporativo) não bloqueie todos os usuários por trás dele quando apenas uma conta está sob ataque.

---

### 4. [MÉDIO] Cookie de estado do OAuth (`oauth_state`) não usa `secure` mesmo quando `COOKIE_SECURE=true`

**Local:** `backend/app/auth/router_google.py:26-32`.

```python
response.set_cookie(
    OAUTH_STATE_COOKIE,
    state,
    max_age=600,
    httponly=True,
    samesite="lax",
)
```

Diferente do cookie `refresh_token` (`backend/app/auth/refresh_tokens.py:88-97`), que usa `secure=settings.cookie_secure`, este cookie **nunca** define `secure`, independentemente da configuração de produção. É uma inconsistência que indica que a flag foi esquecida aqui, não uma decisão deliberada.

**Cenário de exploração:** Em produção servida via HTTPS mas com um subdomínio ou rede comprometida servindo HTTP (downgrade, portal cativo malicioso, MITM em rede aberta), esse cookie de 10 minutos poderia ser capturado ou fixado por um atacante ativo na rede, abrindo caminho para um ataque de CSRF no fluxo OAuth (login CSRF): o atacante inicia o fluxo, captura/injeta seu próprio `state`, e induz a vítima a completar o callback, potencialmente vinculando a conta Google do atacante à sessão da vítima (dependendo de como o restante do fluxo trata isso — aqui o impacto real é limitado porque `state` é validado via `hmac.compare_digest` contra o cookie, mas a integridade do canal de entrega do cookie fica mais fraca sem `secure`).

**Correção recomendada:** Alterar para `secure=settings.cookie_secure`, igual ao cookie de refresh token, mantendo consistência.

---

### 5. [MÉDIO] Token de reset de senha trafega na query string (`?token=`) — exposição via histórico do navegador e cabeçalho `Referer`

**Local:** `backend/app/auth/service.py:74` (`reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"`), consumido em `frontend/src/pages/ResetPasswordPage.tsx:14` (`searchParams.get("token")`).

O token de reset (32 bytes aleatórios, uso único, mas válido por 60 min) viaja na URL. Isso é um padrão comum na indústria, mas tem duas consequências que vale registrar:

- Fica gravado no **histórico do navegador** e em qualquer log de acesso de proxies/CDNs no caminho até o frontend.
- Se a página `/reset-password` (ou o layout compartilhado `AuthLayout`) carregar qualquer recurso de terceiro (fonte externa, analytics, pixel de tracking) **antes** da submissão do formulário, o navegador pode vazar a URL completa — incluindo o token — via cabeçalho `Referer` para esse terceiro. Hoje `AuthLayout.tsx` não carrega nada externo, então o risco atual é baixo, mas é uma armadilha fácil de reintroduzir (ex. ao adicionar Google Fonts via `<link>`, um script de analytics, etc.).

**Correção recomendada:** Não é necessário mudar o mecanismo agora, mas recomenda-se: (a) adicionar `<meta name="referrer" content="strict-origin-when-cross-origin">` ou mais restritivo (`no-referrer`) pelo menos na rota `/reset-password`, e (b) garantir uma política (lint/checklist) de não adicionar recursos de terceiros a essa página sem revisão. Alternativa mais robusta usada por alguns produtos: token curto de confirmação exibido só depois de POST inicial, mas isso é uma mudança maior de UX — não obrigatória.

---

### 6. [BAIXO] Falta de headers de segurança HTTP e de connection pooling/timeout explícito nas chamadas ao Google/Groq

**Local:** `backend/app/main.py` (nenhum middleware de headers de segurança), `backend/app/auth/google_oauth.py:32-43` (`httpx.Client()` sem timeout explícito), `backend/app/analysis/groq_client.py` (SDK Groq, timeout padrão do cliente).

Não há middleware adicionando `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Strict-Transport-Security` (quando atrás de HTTPS), etc. Para uma API JSON pura o risco é menor que em uma aplicação que serve HTML, mas ainda vale como defesa em profundidade, especialmente para respostas de erro que ecoam texto do usuário.

Separadamente, `httpx.Client()` em `google_oauth.py:32` não define `timeout=`; se o endpoint de token do Google ficar lento/travado, a requisição do worker FastAPI pode ficar presa por muito tempo (o timeout padrão do httpx é 5s, então o risco aqui é baixo, mas vale confirmar que está alinhado ao SLA desejado e não depender do padrão implícito).

**Correção recomendada:** Adicionar `SecurityHeadersMiddleware` simples (ou usar `secure` header defaults de biblioteca) e definir `timeout=` explícito nas chamadas HTTP de saída para todos os serviços externos (Google, Groq).

---

### 7. [BAIXO] Dependência `requests==2.34.2` — versão não encontrada nos releases conhecidos do PyPI

**Local:** `backend/requirements.txt:11`.

A biblioteca `requests` não teve, até onde é de conhecimento deste revisor (corte de conhecimento janeiro/2026), nenhuma versão `2.34.x` publicada — as séries conhecidas vão até `2.32.x`. Isso pode ser (a) um erro de digitação no pin (ex. deveria ser `2.32.x`), ou (b) — cenário mais preocupante de checar antes do deploy — o ambiente de build/CI resolvendo esse pin para um pacote com nome/versão inesperados (risco de dependency confusion caso exista, em algum índice acessível, um pacote com esse nome/versão que não seja o `requests` oficial do PyPI).

**Correção recomendada:** Confirmar manualmente com `pip index versions requests` (ou consultando pypi.org/project/requests) qual é a versão pretendida, corrigir o pin, e rodar o pipeline de CI com `pip install --require-hashes` (ou ao menos `pip download` + verificação de hash) para builds reprodutíveis. Vale também rodar `pip-audit` / `safety` no CI (`.github/workflows/tests.yml` hoje só roda `pytest`, sem nenhuma etapa de auditoria de dependências).

---

### 8. [BAIXO / OBSERVAÇÃO] CI sem etapa de auditoria de dependências (SCA) nem lint/type-check obrigatório no pipeline de PR

**Local:** `.github/workflows/tests.yml` (roda apenas `pytest`), `frontend/package.json` (nenhum workflow de CI cobre o frontend — `tsc -b`, lint ou `npm audit`).

O workflow de PR só executa os testes do backend. Não há: `pip-audit`/`safety` para o backend, `npm audit`/`osv-scanner` para o frontend, nem `tsc --noEmit`/build do frontend como gate de PR. Isso significa que uma dependência com CVE conhecida (backend ou frontend) pode ser introduzida e mesclada sem qualquer alerta automatizado — relevante dado o achado #7 acima.

**Correção recomendada:** Adicionar ao workflow: `pip-audit -r backend/requirements.txt`, `npm audit --audit-level=high` (ou Dependabot/Renovate configurado no repo), e um job de build/typecheck do frontend (`npm ci && npm run build`) como gate de PR.

---

### 9. [INFORMATIVO / risco residual aceito, vale documentar] Rotação de `JWT_SECRET` sem plano de invalidação suave

**Local:** `backend/app/auth/jwt.py`.

Não há mecanismo de múltiplas chaves (`kid`) para rotação gradual do `JWT_SECRET`. Trocar o segredo hoje invalida instantaneamente todos os access tokens em circulação (usuários são deslogados na próxima chamada, mas o refresh token os recupera transparentemente via `/auth/refresh`, então o impacto prático é pequeno — apenas uma chamada 401→refresh extra). Não é uma vulnerabilidade, mas registro para o time saber que rotacionar o segredo (ex. em resposta a um vazamento) é seguro e o pior efeito colateral é um refresh silencioso no cliente, não perda de dados.

---

## Pontos que foram verificados e estão corretos (sem achado)

Para não haver dúvida sobre o que foi de fato revisado e considerado seguro:

- **Hashing de senha:** argon2id via `argon2-cffi`, parâmetros padrão da biblioteca são adequados; `_burn_verification_time()` equaliza corretamente o tempo de resposta para e-mail inexistente.
- **Enumeração de usuários:** login (401 uniforme), forgot-password (sempre 202) e erro de e-mail duplicado no registro (mensagem que não confirma dados de senha) foram conferidos e não vazam informação diferencial de forma clara. Pequena ressalva: o 409 de "e-mail já cadastrado" no `/register` *é* um sinal de enumeração (revela que aquele e-mail existe) — isso é uma escolha de produto comum (necessária para o fluxo de "criar conta") e não um bug, mas registre-se como enumeração aceita nesse único endpoint.
- **Refresh token:** hash SHA-256 armazenado (não o token bruto), rotação com detecção de reuso (`revoke_all` em token já revogado) implementada com `UPDATE ... WHERE revoked_at IS NULL` atômico, corretamente evitando race conditions de dupla revogação. Cookie `httponly`, `samesite=lax`, `path=/auth` corretamente restrito.
- **CSRF em `/auth/refresh` e `/auth/logout`:** ambos são POST e o cookie é `SameSite=Lax`; requisições cross-site (fetch/XHR ou submissão de formulário) de outra origem não enviam o cookie sob essa política, portanto CSRF clássico não é explorável aqui. CORS também restringe `allow_origins` a uma única origem configurada (`settings.frontend_url`), então mesmo o "simple request" cross-site do refresh não consegue ler a resposta.
- **Reset de senha:** token single-use com `UPDATE ... WHERE used_at IS NULL` atômico (mesma proteção de corrida do refresh); ao concluir o reset, `revoke_all` derruba todas as sessões — correto.
- **IDOR em `/history` e `/history/{id}`:** todas as queries filtram por `Analysis.user_id == current_user.id`; tentativa de acessar/deletar registro de outro usuário retorna 404 (não vaza existência do recurso).
- **Injeção SQL:** toda a camada de dados usa SQLAlchemy ORM com parâmetros ligados; nenhuma concatenação de string em query encontrada.
- **XSS armazenado via IA:** a resposta do modelo Groq (`sugestoes`, `testes_gerados`, `riscos_seguranca`) é renderizada como texto React puro (`{item}`) ou via `react-syntax-highlighter`, sem `dangerouslySetInnerHTML` em nenhum ponto — mesmo que um usuário tente prompt-injection para fazer o modelo "devolver" HTML/script, o React escapa a saída antes de ir ao DOM.
- **SSRF na feature `analysis`:** não há nenhuma funcionalidade que busque URLs fornecidas pelo usuário; o código enviado é tratado como texto e embutido no prompt enviado à API da Groq (chamada de saída fixa, não parametrizável pelo usuário). Sem risco de SSRF identificado.
- **Armazenamento do access token no frontend:** mantido apenas em estado React (`useState` em `AuthContext`), nunca em `localStorage`/`sessionStorage`, o que reduz a superfície de roubo via XSS (um XSS ainda poderia ler o token da memória JS em tempo de execução, mas não haveria persistência entre reloads/abas a exfiltrar de um storage passivo).
- **`.env` não versionado:** confirmado via `.gitignore` e `git ls-files` que nenhum arquivo `.env` real está no repositório; apenas `.env.example` com placeholders.
- **Verificação do e-mail Google:** `email_verified` do ID token é checado antes de vincular/criar conta (`google_oauth.py:50-55`), prevenindo takeover de conta local via Google de domínio não verificado.
- **Redação de dados sensíveis em erros de validação:** `main.py:25-42` redige campos `password`/`token` no corpo de erros 422, evitando eco de segredos na resposta.

---

## Resumo executivo (para priorização)

| # | Severidade | Achado | Ação |
|---|---|---|---|
| 1 | Alto | Reset de senha sempre loga token em vez de enviar e-mail, em qualquer ambiente | Implementar `EmailSender` real selecionado por ambiente antes de qualquer deploy em produção |
| 2 | Alto | `JWT_SECRET` sem validação de força; template usa `change-me` | Adicionar validação de entropia mínima + checklist de deploy |
| 3 | Médio | Rate limit em memória, keyed por IP de socket | Mover para storage compartilhado (Redis) e configurar `--proxy-headers` com cuidado se houver proxy |
| 4 | Médio | Cookie `oauth_state` sem `secure` condicional | Alinhar com `settings.cookie_secure` |
| 5 | Médio | Token de reset na query string | Meta `referrer` restritivo na página de reset; evitar recursos de terceiros nela |
| 6 | Baixo | Faltam headers de segurança HTTP; timeouts implícitos em chamadas externas | Middleware de headers + `timeout=` explícito |
| 7 | Baixo | `requests==2.34.2` — versão a confirmar | Corrigir pin, adicionar SCA ao CI |
| 8 | Baixo | CI sem auditoria de dependências/typecheck de frontend | Adicionar `pip-audit`/`npm audit`/build gate |
| 9 | Informativo | Sem suporte a múltiplas chaves JWT para rotação suave | Documentar como risco residual aceito |

**Risco residual aceito pelo time (a confirmar explicitamente):** rate limiting em memória por instância única (aceitável apenas se o deployment atual for de fato mono-instância, mono-processo, sem proxy que mascare o IP — verificar isso no ambiente real antes de aceitar); ausência de segundo fator de autenticação (fora do escopo desta PR); tokens de acesso não revogáveis individualmente antes da expiração de 15 min (mitigado pela janela curta).

Nenhuma alteração de código foi aplicada — este é um relatório de revisão apenas, conforme escopo solicitado.
