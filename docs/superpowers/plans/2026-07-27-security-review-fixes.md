# Correção dos Apontamentos da Revisão de Segurança Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir os 8 apontamentos acionáveis de `docs/agent-reports/2026-07-27-security-engineer-app-security-review.md` (itens 1–8; o item 9 é informativo e vira apenas documentação de risco aceito).

**Architecture:** Cada tarefa é independente e ataca um achado específico do relatório, sem tocar na lógica de negócio já coberta por teste (hashing, rotação de refresh token, IDOR, etc. permanecem intocados). Mudanças concentradas em: seleção de `EmailSender` por ambiente, validação de `Settings` via Pydantic, chave composta no rate limiter + suporte a proxy confiável, paridade de flags de cookie, meta tag de referrer, middleware de headers HTTP + timeouts explícitos, correção de pin de dependência, e gates de CI (SCA + build do frontend).

**Tech Stack:** FastAPI 0.115, Pydantic 2 / pydantic-settings, SQLAlchemy 2.0, pytest; React 18 + TypeScript + Vite; GitHub Actions.

## Global Constraints

- **Não alterar comportamento coberto por teste existente sem atualizar o teste correspondente.** Rodar `cd backend && python -m pytest` (e `cd frontend && npm run build`, quando aplicável) ao final de cada tarefa.
- **Copy de erro em pt-BR** para qualquer mensagem nova voltada ao usuário; mensagens de configuração/infra (logs, exceptions internas) podem ser em inglês, seguindo o padrão já usado no repo (ex. `EmailAlreadyRegistered`).
- **Sem novas dependências de infraestrutura** (decisão explícita do usuário: sem Redis para o rate limiter neste plano).
- **Variáveis de ambiente novas** precisam de entrada correspondente em `.env.example` com valor de exemplo seguro (nunca um segredo real).
- Rodar backend tests a partir de `backend/`: `cd backend && python -m pytest`.
- Rodar frontend build a partir de `frontend/`: `cd frontend && npm run build`.

---

## Task 1: Seleção de `EmailSender` por ambiente + redação do token nos logs (Achado #1, ALTO)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/auth/email_sender.py`
- Modify: `.env.example`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_email_sender.py`

**Interfaces:**
- Consumes: `settings` de `app.core.config` (nova propriedade `environment: str`).
- Produces: `email_sender.SmtpEmailSender` (classe nova), `email_sender.get_email_sender()` passa a escolher a implementação por `settings.environment`; `ConsoleEmailSender.send` passa a mascarar tokens no corpo logado.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_email_sender.py`:

```python
import logging

from app.auth.email_sender import ConsoleEmailSender, SmtpEmailSender, get_email_sender


def test_console_sender_masks_token_in_body(caplog):
    body = "Clique aqui: http://localhost:5173/reset-password?token=abcdef1234567890"

    with caplog.at_level(logging.WARNING):
        ConsoleEmailSender().send("user@example.com", "Assunto", body)

    logged = caplog.text
    assert "abcdef1234567890" not in logged
    assert "token=***redacted***" in logged


def test_get_email_sender_returns_console_in_development(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "development")
    assert isinstance(get_email_sender(), ConsoleEmailSender)


def test_get_email_sender_returns_smtp_in_production(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    assert isinstance(get_email_sender(), SmtpEmailSender)


def test_smtp_sender_requires_smtp_host(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", "")

    try:
        get_email_sender()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "smtp_host" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_email_sender.py -v`
Expected: FAIL with `ImportError: cannot import name 'SmtpEmailSender'`

- [ ] **Step 3: Add `environment` and SMTP settings**

In `backend/app/core/config.py`, add fields to `Settings` (after `email_from`):

```python
    environment: str = "development"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
```

- [ ] **Step 4: Implement masking and the SMTP sender**

Replace `backend/app/auth/email_sender.py` entirely:

```python
import logging
import re
import smtplib
from email.mime.text import MIMEText
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_QUERY_PARAM = re.compile(r"(token=)[^&\s]+")


def _mask_tokens(text: str) -> str:
    return _TOKEN_QUERY_PARAM.sub(r"\1***redacted***", text)


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Writes a token-redacted version of the message to the application log.

    Dev and docker-compose default only. `get_email_sender` never returns
    this outside `settings.environment == "development"`.
    """

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning(
            "\n--- EMAIL (dev, token redacted) ---\nFrom: %s\nTo: %s\nSubject: %s\n\n%s\n-------------",
            settings.email_from,
            to,
            subject,
            _mask_tokens(body),
        )


class SmtpEmailSender:
    """Sends mail via SMTP. Used whenever settings.environment != 'development'."""

    def send(self, to: str, subject: str, body: str) -> None:
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = settings.email_from
        message["To"] = to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)


def get_email_sender() -> EmailSender:
    if settings.environment == "development":
        return ConsoleEmailSender()

    if not settings.smtp_host:
        raise RuntimeError(
            "settings.smtp_host is required when settings.environment != 'development'"
        )
    return SmtpEmailSender()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_email_sender.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Update `.env.example`**

Append to `.env.example`:

```
ENVIRONMENT=development
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
```

- [ ] **Step 7: Keep the test suite's dependency override working**

`backend/tests/conftest.py` already overrides `get_email_sender` via `app.dependency_overrides` (line 82), so no change is needed there — verify by running the full suite.

- [ ] **Step 8: Run the full suite**

Run: `cd backend && python -m pytest`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/config.py backend/app/auth/email_sender.py .env.example backend/tests/test_email_sender.py
git commit -m "fix(auth): send real email outside dev and redact reset tokens in logs"
```

---

## Task 2: Validação de força do `JWT_SECRET` (Achado #2, ALTO)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/conftest.py`
- Modify: `.env.example`
- Test: `backend/tests/test_config_jwt_secret.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Settings` rejeita, na inicialização, um `jwt_secret` com menos de 32 caracteres ou presente em uma lista de valores óbvios.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_config_jwt_secret.py`:

```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE_ENV = {
    "groq_api_key": "k",
    "google_client_id": "id",
    "google_client_secret": "secret",
    "google_redirect_uri": "http://localhost/callback",
    "database_url": "sqlite:///:memory:",
    "frontend_url": "http://localhost:5173",
}


def test_rejects_short_secret():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(jwt_secret="too-short", **BASE_ENV)


def test_rejects_known_placeholder():
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(jwt_secret="change-me" + "x" * 30, **BASE_ENV)


def test_accepts_strong_secret():
    strong = "a" * 32
    settings = Settings(jwt_secret=strong, **BASE_ENV)
    assert settings.jwt_secret == strong
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config_jwt_secret.py -v`
Expected: FAIL — no validation is raised yet (`test_rejects_short_secret` and `test_rejects_known_placeholder` fail because no `ValidationError` is raised).

- [ ] **Step 3: Add the validator**

In `backend/app/core/config.py`, add the import and validator:

```python
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {"change-me", "secret", "changeme", "password", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    jwt_secret: str
    jwt_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    reset_token_expire_minutes: int = 60
    cookie_secure: bool = False
    email_from: str = "no-reply@ask-me.local"
    environment: str = "development"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    database_url: str
    frontend_url: str

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_strong(cls, value: str) -> str:
        stripped = value.strip()
        if any(stripped.lower().startswith(bad) for bad in _PLACEHOLDER_SECRETS if bad):
            raise ValueError("jwt_secret looks like a placeholder value, not a real secret")
        if len(stripped) < 32:
            raise ValueError("jwt_secret must be at least 32 characters long")
        return value


settings = Settings()
```

Note: `_PLACEHOLDER_SECRETS` includes `""`, but the `if bad` guard in the generator skips the empty string for the `startswith` check (an empty prefix always matches and would false-positive on every secret) — the empty-string case is instead caught by the length check below it.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_config_jwt_secret.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Fix the now-too-short test secret**

In `backend/tests/conftest.py` line 4, replace:

```python
os.environ.setdefault("JWT_SECRET", "test-secret")
```

with:

```python
os.environ.setdefault("JWT_SECRET", "test-secret-used-only-in-pytest-32chars")
```

- [ ] **Step 6: Update `.env.example` with guidance**

In `.env.example`, replace line 3 (`JWT_SECRET=change-me`) with:

```
# Generate with: openssl rand -hex 32
JWT_SECRET=
```

- [ ] **Step 7: Run the full suite**

Run: `cd backend && python -m pytest`
Expected: all PASS — this also confirms nothing else hardcodes a short `JWT_SECRET`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/config.py backend/tests/conftest.py backend/tests/test_config_jwt_secret.py .env.example
git commit -m "fix(config): reject weak or placeholder JWT_SECRET at startup"
```

---

## Task 3: Rate limit — chave composta IP+e-mail e suporte a proxy confiável (Achado #3, MÉDIO)

**Files:**
- Modify: `backend/app/core/rate_limit.py`
- Modify: `backend/app/auth/router_credentials.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_rate_limit.py`

**Scope decision (confirmed with user):** sem Redis. O deployment atual é mono-instância sem proxy configurado no `docker-compose.yml`; a correção aqui é (a) evitar que um único IP compartilhado (NAT, proxy corporativo) derrube o login de todos ao chavear por IP+e-mail em vez de só IP, e (b) tornar opcional confiar em `X-Forwarded-For` via uma flag explícita, para quando um reverse proxy for introduzido. Migração para storage compartilhado (Redis) fica registrada como follow-up caso o deploy real passe a rodar múltiplos workers/réplicas.

**Interfaces:**
- Consumes: nada novo de outras tasks.
- Produces: `rate_limit.login_key(request, email) -> str`; `enforce_login_rate_limit` passa a receber o corpo da requisição para compor a chave; `settings.trust_proxy_headers: bool`.

- [ ] **Step 1: Write the failing test**

Create/replace `backend/tests/test_rate_limit.py` (extends the existing one from the JWT auth plan — keep its 3 existing tests and add these):

```python
import pytest
from fastapi import HTTPException

from app.core.rate_limit import InMemoryRateLimiter, client_ip


def test_limiter_uses_its_own_detail_message():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, detail="Custom message")
    limiter.check("key")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("key")

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "Custom message"


def test_limits_are_tracked_per_key():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, detail="nope")
    limiter.check("key-a")
    limiter.check("key-b")

    with pytest.raises(HTTPException):
        limiter.check("key-a")


def test_analysis_limiter_keeps_its_original_message():
    from app.core.rate_limit import analyze_rate_limiter

    assert analyze_rate_limiter.detail == "Too many analysis requests, try again later"


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, client_host, headers=None):
        self.client = _FakeClient(client_host) if client_host else None
        self.headers = headers or {}


def test_client_ip_uses_socket_by_default(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    request = _FakeRequest("10.0.0.1", headers={"x-forwarded-for": "1.2.3.4"})

    assert client_ip(request) == "10.0.0.1"


def test_client_ip_trusts_forwarded_for_when_enabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    request = _FakeRequest("10.0.0.1", headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1"})

    assert client_ip(request) == "1.2.3.4"


def test_client_ip_falls_back_to_socket_when_header_absent(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    request = _FakeRequest("10.0.0.1")

    assert client_ip(request) == "10.0.0.1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL with `ImportError: cannot import name 'client_ip'`

- [ ] **Step 3: Add `trust_proxy_headers` setting**

In `backend/app/core/config.py`, add after `environment`:

```python
    trust_proxy_headers: bool = False
```

- [ ] **Step 4: Rename `_client_ip` to `client_ip`, honor the proxy setting, and add a composite login key**

Replace the bottom of `backend/app/core/rate_limit.py` (from `def _client_ip` onward):

```python
from app.core.config import settings


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # First entry is the original client per the de-facto X-Forwarded-For
            # convention; only trust this when a proxy we control sets the header.
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def login_key(request: Request, email: str) -> str:
    # Composite key: an attacker flooding one account no longer exhausts the
    # shared quota for every other user behind the same IP (NAT, corporate
    # proxy), while still rate-limiting a single IP hammering many emails.
    return f"{client_ip(request)}:{email.strip().lower()}"


def enforce_login_rate_limit(request: Request, email: str) -> None:
    login_rate_limiter.check(login_key(request, email))


def enforce_register_rate_limit(request: Request) -> None:
    register_rate_limiter.check(client_ip(request))


def enforce_forgot_password_rate_limit(request: Request) -> None:
    forgot_password_rate_limiter.check(client_ip(request))
```

Also delete the old `_client_ip` function definition (now replaced by `client_ip` above) and add `from app.core.config import settings` near the top imports if not already re-added by the block above.

- [ ] **Step 5: Update the login route to pass the email into the dependency**

`enforce_login_rate_limit` now needs the request body's email, which FastAPI dependencies can't read before the route parses it. In `backend/app/auth/router_credentials.py`, drop `enforce_login_rate_limit` from the `Depends(...)` parameter list and call it explicitly inside the handler instead, with `request: Request` added as a route parameter:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    enforce_login_rate_limit(request, str(payload.email))

    user = service.authenticate(db, str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        )

    refresh_tokens.set_cookie(response, refresh_tokens.issue(db, user.id))
    return TokenResponse(access_token=create_access_token(user.id))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_rate_limit.py tests/test_login_endpoint.py -v`
Expected: PASS — `test_login_is_rate_limited` in `test_login_endpoint.py` (existing test, same email/IP every attempt) keeps passing since the composite key still collapses to one key for repeated same-email attempts from the test client.

- [ ] **Step 7: Update `.env.example`**

Append:

```
TRUST_PROXY_HEADERS=false
```

- [ ] **Step 8: Run the full suite**

Run: `cd backend && python -m pytest`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/rate_limit.py backend/app/core/config.py backend/app/auth/router_credentials.py backend/tests/test_rate_limit.py .env.example
git commit -m "fix(auth): key login rate limit by IP+email and gate X-Forwarded-For trust"
```

---

## Task 4: Paridade de `secure` no cookie `oauth_state` (Achado #4, MÉDIO)

**Files:**
- Modify: `backend/app/auth/router_google.py`
- Test: `backend/tests/test_auth_endpoint.py` (extend existing file)

**Interfaces:**
- Consumes: `settings.cookie_secure` (já existe).
- Produces: nada novo — apenas alinha o `set_cookie` existente.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_auth_endpoint.py` (create the file with this single test if it doesn't already cover this case — check first with `grep -n "oauth_state" backend/tests/test_auth_endpoint.py`; if the file doesn't exist yet, create it with just this test):

```python
def test_oauth_state_cookie_respects_cookie_secure_setting(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "cookie_secure", True)

    response = client.get("/auth/google/login", follow_redirects=False)

    set_cookie_header = response.headers.get("set-cookie", "")
    assert "oauth_state=" in set_cookie_header
    assert "secure" in set_cookie_header.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_auth_endpoint.py -k oauth_state_cookie -v`
Expected: FAIL — `secure` is absent from the `Set-Cookie` header.

- [ ] **Step 3: Fix the cookie call**

In `backend/app/auth/router_google.py`, update the import and the `set_cookie` call:

```python
from app.core.config import settings
```

```python
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
```

(`from app.core.config import settings` is already imported in this file for `settings.frontend_url` — just add `secure=settings.cookie_secure` to the existing call.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_auth_endpoint.py -k oauth_state_cookie -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `cd backend && python -m pytest`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/router_google.py backend/tests/test_auth_endpoint.py
git commit -m "fix(auth): set secure flag on oauth_state cookie to match refresh_token"
```

---

## Task 5: Meta tag de referrer restritivo (Achado #5, MÉDIO)

**Files:**
- Modify: `frontend/index.html`

**Interfaces:** nenhuma — mudança puramente declarativa em HTML.

**Decisão de escopo:** aplicar a política globalmente via `frontend/index.html` (em vez de injetar a meta tag só na rota `/reset-password`) — é uma SPA de página única; o `<meta>` de referrer não pode ser condicional por rota sem manipulação de DOM em tempo de execução, e `strict-origin-when-cross-origin` é um default seguro e amplamente recomendado para a aplicação inteira, não só a página de reset.

- [ ] **Step 1: Read the current file**

Run: `cat frontend/index.html` (or open it) to find the `<head>` block before editing.

- [ ] **Step 2: Add the meta tag**

In `frontend/index.html`, inside `<head>`, add immediately after the `<meta charset>` tag:

```html
    <meta name="referrer" content="strict-origin-when-cross-origin" />
```

- [ ] **Step 3: Verify the frontend still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "fix(frontend): restrict Referer header via meta policy"
```

---

## Task 6: Middleware de headers de segurança + timeouts explícitos (Achado #6, BAIXO)

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/auth/google_oauth.py`
- Modify: `backend/app/analysis/groq_client.py`
- Test: `backend/tests/test_security_headers.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: middleware `add_security_headers` registrado em `app`; `exchange_code_for_userinfo` e `call_groq` passam a usar timeout explícito.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_security_headers.py`:

```python
def test_response_includes_security_headers(client):
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-frame-options"] == "DENY"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_security_headers.py -v`
Expected: FAIL — headers absent.

- [ ] **Step 3: Add the middleware**

In `backend/app/main.py`, add after the `CORSMiddleware` block:

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    return response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_security_headers.py -v`
Expected: PASS

- [ ] **Step 5: Add explicit timeout to the Google token exchange**

In `backend/app/auth/google_oauth.py`, change:

```python
    with httpx.Client() as client:
```

to:

```python
    with httpx.Client(timeout=10.0) as client:
```

- [ ] **Step 6: Add explicit timeout to the Groq client**

In `backend/app/analysis/groq_client.py`, change:

```python
        _client = Groq(api_key=settings.groq_api_key)
```

to:

```python
        _client = Groq(api_key=settings.groq_api_key, timeout=30.0)
```

- [ ] **Step 7: Run the full suite**

Run: `cd backend && python -m pytest`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/main.py backend/app/auth/google_oauth.py backend/app/analysis/groq_client.py backend/tests/test_security_headers.py
git commit -m "fix(backend): add security response headers and explicit outbound timeouts"
```

---

## Task 7: Corrigir pin de `requests` (Achado #7, BAIXO)

**Files:**
- Modify: `backend/requirements.txt`

**Interfaces:** nenhuma.

- [ ] **Step 1: Confirm the intended version**

Run: `pip index versions requests` (or check https://pypi.org/project/requests/#history) to find the latest real `2.32.x` release at the time of the fix.

- [ ] **Step 2: Fix the pin**

In `backend/requirements.txt`, replace:

```
requests==2.34.2
```

with the confirmed real version, e.g.:

```
requests==2.32.3
```

- [ ] **Step 3: Reinstall and verify**

Run: `cd backend && pip install -r requirements.txt && python -m pytest`
Expected: install succeeds, all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "fix(deps): correct requests pin to an existing published version"
```

---

## Task 8: CI — auditoria de dependências e gate de build do frontend (Achado #8, BAIXO)

**Files:**
- Modify: `.github/workflows/tests.yml`

**Interfaces:** nenhuma — mudança de pipeline apenas.

- [ ] **Step 1: Add a backend dependency-audit step**

In `.github/workflows/tests.yml`, add a step to the existing `backend-tests` job, after "Install dependencies":

```yaml
      - name: Audit Python dependencies
        run: |
          pip install pip-audit
          pip-audit -r requirements.txt
```

- [ ] **Step 2: Add a frontend build/typecheck/audit job**

Append a new job at the end of the file:

```yaml
  frontend-build:
    name: Frontend build, typecheck, and audit
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Build (includes tsc typecheck)
        run: npm run build

      - name: Audit npm dependencies
        run: npm audit --audit-level=high
```

- [ ] **Step 3: Verify locally what CI will run**

Run: `cd backend && pip install pip-audit && pip-audit -r requirements.txt` — resolve any reported vulnerability before merging (upgrade the pin or document why it's an accepted risk).
Run: `cd frontend && npm ci && npm run build && npm audit --audit-level=high` — same.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/tests.yml
git commit -m "ci: add dependency audits and frontend build gate to PR checks"
```

---

## Task 9: Documentar risco residual — sem rotação suave de `JWT_SECRET` (Achado #9, informativo)

**Files:**
- Create: `docs/SECURITY.md`

**Interfaces:** nenhuma — documentação apenas.

- [ ] **Step 1: Write the document**

Create `docs/SECURITY.md`:

```markdown
# Riscos de Segurança Aceitos

Este documento registra decisões de risco residual tomadas conscientemente, para que não sejam reabertas como bugs no futuro sem contexto.

## Rotação de `JWT_SECRET` sem múltiplas chaves

`backend/app/auth/jwt.py` assina e verifica tokens com um único segredo (`settings.jwt_secret`, HS256). Não há suporte a `kid`/lista de chaves válidas para rotação gradual.

**Impacto de rotacionar o segredo hoje:** todo `access_token` em circulação (validade de 15 min) passa a falhar a verificação imediatamente. O cliente trata isso como uma chamada 401 seguida de um `POST /auth/refresh` automático (o refresh token não depende do JWT secret), então o efeito prático para o usuário é uma chamada extra, não logout nem perda de dados.

**Quando revisitar:** se o volume de usuários simultâneos crescer a ponto de um pico de `/auth/refresh` após rotação de segredo virar um problema de carga, ou se houver requisito de rotação sem nenhum downtime perceptível — nesse caso, introduzir uma lista de segredos válidos para verificação (assinando sempre com o mais recente).

Referência: achado #9 de `docs/agent-reports/2026-07-27-security-engineer-app-security-review.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/SECURITY.md
git commit -m "docs: record JWT_SECRET rotation as an accepted residual risk"
```

---

## Final Verification

- [ ] Run `cd backend && python -m pytest -v` — all tests pass, including the new ones added in Tasks 1–6.
- [ ] Run `cd frontend && npm run build` — succeeds.
- [ ] Re-read `docs/agent-reports/2026-07-27-security-engineer-app-security-review.md` achados #1–#8 and confirm each has a corresponding completed task above.
- [ ] Confirm `.env.example` has entries for every new setting introduced: `ENVIRONMENT`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `TRUST_PROXY_HEADERS`.
