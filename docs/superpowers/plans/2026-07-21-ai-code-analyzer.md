# AI Code Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP described in `docs/superpowers/specs/2026-07-21-ai-code-analyzer-design.md`: a React front-end where a user logs in with Google, pastes or uploads code, and gets AI-generated suggestions, tests, and security risks from Groq, with history persisted per-user in PostgreSQL.

**Architecture:** React (Vite) SPA talks only to a FastAPI back-end using a bearer JWT issued after Google OAuth login. The back-end owns all secrets (Groq API key, JWT secret, Google OAuth secret), builds the analysis prompt, calls Groq, validates/parses the response, persists it, and enforces per-user rate limiting. Three Docker Compose services: `frontend`, `backend`, `db` (Postgres).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, PyJWT, `google-auth` + `httpx` for OAuth, `groq` SDK, Pytest; React 18 + Vite + TypeScript, `react-router-dom`; PostgreSQL 16; Docker Compose.

## Global Constraints

- Max code size accepted by `/analyze`: 20,000 characters (`docs/superpowers/specs/2026-07-21-ai-code-analyzer-design.md` §4, §7).
- Allowed languages (enum): `javascript`, `typescript`, `python`, `java`, `go`, `csharp`, `cpp`, `ruby`, `php` (§7).
- Groq model default: `llama-3.3-70b-versatile`, configurable via `GROQ_MODEL` env var (§10).
- JWT session expiry: 60 minutes, no refresh token in MVP (§5).
- Rate limit: 10 analyses per user per minute (§5, §7).
- History and analyses are scoped per authenticated user, never shared globally (§10).
- Secrets (`GROQ_API_KEY`, `JWT_SECRET`, `GOOGLE_CLIENT_SECRET`, `DATABASE_URL`) only ever live in the backend container's environment (§5, §7).
- Automated tests are backend-only (Pytest with mocked Groq calls); the spec does not call for a frontend test framework (§8). Frontend tasks are verified by running the Vite dev server and exercising the flow manually.
- **Deviation from spec §5 noted here:** the spec suggested `slowapi` for rate limiting. This plan implements a small custom in-memory limiter keyed by `user_id` instead (Task 10), because `slowapi`'s default key extraction is IP-based and would need the same custom wiring anyway to key by the authenticated user — a hand-rolled limiter is simpler and directly testable.
- **Deviation from spec §6 noted here:** Postgres-specific `UUID`/`JSONB` column types are replaced with portable `String(36)` (storing `str(uuid4())`) and `JSON` types, so the same schema/tests run against SQLite in-memory in CI without requiring a live Postgres instance, while still working unmodified against Postgres in Docker Compose.

---

## File Structure

```
backend/
  app/
    __init__.py
    main.py
    core/
      __init__.py
      config.py
      rate_limit.py
    auth/
      __init__.py
      jwt.py
      google_oauth.py
      dependencies.py
      router.py
    analysis/
      __init__.py
      schemas.py
      prompt_builder.py
      groq_client.py
      service.py
      router.py
    db/
      __init__.py
      base.py
      session.py
      models.py
  alembic.ini
  alembic/
    env.py
    script.py.mako
    versions/
      0001_initial.py
  tests/
    __init__.py
    conftest.py
    test_prompt_builder.py
    test_groq_client.py
    test_service.py
    test_jwt.py
    test_analyze_endpoint.py
    test_history_endpoint.py
    test_auth_endpoint.py
  requirements.txt
  Dockerfile
  docker-entrypoint.sh
frontend/
  package.json
  tsconfig.json
  vite.config.ts
  index.html
  Dockerfile
  src/
    main.tsx
    App.tsx
    api/
      client.ts
    context/
      AuthContext.tsx
    components/
      AuthGuard.tsx
      LanguageSelect.tsx
      CodeInput.tsx
      AnalysisResult.tsx
      HistoryList.tsx
    pages/
      LoginPage.tsx
      AuthCallbackPage.tsx
      AnalyzePage.tsx
      HistoryPage.tsx
docker-compose.yml
.env.example
```

---

### Task 1: Backend scaffolding — config and DB base

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/conftest.py` (fixtures used by all later backend tests)

**Interfaces:**
- Produces: `app.core.config.settings` (a `Settings` instance with attributes `groq_api_key: str`, `groq_model: str`, `jwt_secret: str`, `jwt_expire_minutes: int`, `google_client_id: str`, `google_client_secret: str`, `google_redirect_uri: str`, `database_url: str`, `frontend_url: str`).
- Produces: `app.db.base.Base` (SQLAlchemy `DeclarativeBase` subclass).
- Produces: `app.db.session.get_db()` (FastAPI dependency generator yielding a `Session`).
- Produces test fixtures: `client`, `db_session`, `test_user`, `auth_headers` (defined in Task 1, consumed by Tasks 6, 9, 11, 12, 13).

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.3
pydantic-settings==2.6.1
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
alembic==1.14.0
pyjwt==2.10.1
httpx==0.28.1
google-auth==2.36.0
groq==0.13.0
pytest==8.3.4
```

- [ ] **Step 2: Create `backend/app/__init__.py`, `backend/app/core/__init__.py`, `backend/app/db/__init__.py`, `backend/tests/__init__.py` (all empty)**

- [ ] **Step 3: Create `backend/app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    jwt_secret: str
    jwt_expire_minutes: int = 60
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    database_url: str
    frontend_url: str


settings = Settings()
```

- [ ] **Step 4: Create `backend/app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 5: Create `backend/app/db/session.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Create `backend/tests/conftest.py`**

```python
import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.auth.jwt import create_access_token
from app.db.models import User
from app.core.rate_limit import analyze_rate_limiter

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session):
    user = User(google_sub="google-123", email="dev@example.com", name="Dev User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user):
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    analyze_rate_limiter._hits.clear()
    yield
```

This fixture file references `app.main`, `app.auth.jwt`, `app.db.models`, and `app.core.rate_limit`, which don't exist yet — that's expected. It becomes runnable once Tasks 2, 7, 10, and 13 land. Leave it in place now; later tasks will each add their own test file that imports from it and can be run individually as they're written.

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/__init__.py backend/app/core/__init__.py backend/app/core/config.py backend/app/db/__init__.py backend/app/db/base.py backend/app/db/session.py backend/tests/__init__.py backend/tests/conftest.py
git commit -m "feat: scaffold backend config, db base session, and test fixtures"
```

---

### Task 2: Database models and Alembic migration

**Files:**
- Create: `backend/app/db/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial.py`

**Interfaces:**
- Consumes: `app.db.base.Base` (Task 1).
- Produces: `app.db.models.User` (fields: `id: str`, `google_sub: str`, `email: str`, `name: str`, `avatar_url: str | None`, `created_at: datetime`) and `app.db.models.Analysis` (fields: `id: str`, `user_id: str`, `language: str`, `code_snippet: str`, `suggestions: list`, `generated_tests: str`, `security_risks: list`, `created_at: datetime`) — consumed by Tasks 6, 8, 9, 11, 12.
- Produces: `app.db.models.new_uuid() -> str` helper.

- [ ] **Step 1: Create `backend/app/db/models.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    google_sub: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    code_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    suggestions: Mapped[list] = mapped_column(JSON, nullable=False)
    generated_tests: Mapped[str] = mapped_column(Text, nullable=False)
    security_risks: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Create `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Create `backend/alembic/env.py`**

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401  (registers models on Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create `backend/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Create `backend/alembic/versions/0001_initial.py`**

```python
"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("google_sub", sa.String(), nullable=False, unique=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("code_snippet", sa.Text(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("generated_tests", sa.Text(), nullable=False),
        sa.Column("security_risks", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_analyses_user_created", "analyses", ["user_id", "created_at"])


def downgrade():
    op.drop_index("ix_analyses_user_created", table_name="analyses")
    op.drop_table("analyses")
    op.drop_table("users")
```

- [ ] **Step 6: Verify the models import cleanly**

Run: `cd backend && python -c "from app.db.models import User, Analysis; print(User.__tablename__, Analysis.__tablename__)"`
Expected: prints `users analyses` with no errors (env vars from Task 1's `conftest.py` are not needed here since this is a plain import, but `GROQ_API_KEY` etc. must be set in the shell, or run it as `GROQ_API_KEY=x JWT_SECRET=x GOOGLE_CLIENT_ID=x GOOGLE_CLIENT_SECRET=x GOOGLE_REDIRECT_URI=http://x DATABASE_URL=sqlite:///:memory: FRONTEND_URL=http://x python -c "..."` since `app.core.config.settings` is instantiated eagerly).

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/models.py backend/alembic.ini backend/alembic/env.py backend/alembic/script.py.mako backend/alembic/versions/0001_initial.py
git commit -m "feat: add User/Analysis models and initial Alembic migration"
```

---

### Task 3: Prompt builder

**Files:**
- Create: `backend/app/analysis/__init__.py`
- Create: `backend/app/analysis/prompt_builder.py`
- Test: `backend/tests/test_prompt_builder.py`

**Interfaces:**
- Produces: `app.analysis.prompt_builder.build_prompt(code: str, language: str) -> str` — consumed by Task 6.

- [ ] **Step 1: Write the failing test in `backend/tests/test_prompt_builder.py`**

```python
from app.analysis.prompt_builder import build_prompt


def test_build_prompt_includes_code_language_and_json_keys():
    prompt = build_prompt("print('hi')", "python")

    assert "python" in prompt
    assert "print('hi')" in prompt
    assert "sugestoes" in prompt
    assert "testes_gerados" in prompt
    assert "riscos_seguranca" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_prompt_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.analysis'`

- [ ] **Step 3: Create `backend/app/analysis/__init__.py` (empty) and `backend/app/analysis/prompt_builder.py`**

```python
def build_prompt(code: str, language: str) -> str:
    return (
        "Voce e um analisador de codigo senior. Analise o codigo abaixo, escrito em "
        f"{language}, e responda EXCLUSIVAMENTE com um JSON valido, sem nenhum texto "
        "fora do JSON, no seguinte formato exato:\n"
        '{"sugestoes": ["..."], "testes_gerados": "...", "riscos_seguranca": ["..."]}\n\n'
        "- sugestoes: lista de strings com melhorias de qualidade, legibilidade ou performance.\n"
        "- testes_gerados: uma string contendo codigo de testes unitarios para o codigo, "
        "na mesma linguagem.\n"
        "- riscos_seguranca: lista de strings descrevendo vulnerabilidades ou riscos de "
        "seguranca encontrados (lista vazia se nao houver nenhum).\n\n"
        f"Codigo ({language}):\n```{language}\n{code}\n```"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_prompt_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/__init__.py backend/app/analysis/prompt_builder.py backend/tests/test_prompt_builder.py
git commit -m "feat: add prompt builder for code analysis requests"
```

---

### Task 4: Groq client wrapper

**Files:**
- Create: `backend/app/analysis/groq_client.py`
- Test: `backend/tests/test_groq_client.py`

**Interfaces:**
- Consumes: `app.core.config.settings.groq_api_key`, `settings.groq_model` (Task 1).
- Produces: `app.analysis.groq_client.GroqAnalysisError(Exception)`, `app.analysis.groq_client.call_groq(prompt: str, client: Groq | None = None) -> dict` — consumed by Task 6.

- [ ] **Step 1: Write the failing tests in `backend/tests/test_groq_client.py`**

```python
import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import MagicMock

import pytest

from app.analysis.groq_client import call_groq, GroqAnalysisError


def _make_mock_client(content: str) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client


def test_call_groq_parses_valid_json():
    client = _make_mock_client(
        '{"sugestoes": ["a"], "testes_gerados": "t", "riscos_seguranca": []}'
    )

    result = call_groq("prompt", client=client)

    assert result == {"sugestoes": ["a"], "testes_gerados": "t", "riscos_seguranca": []}


def test_call_groq_raises_on_invalid_json():
    client = _make_mock_client("not json")

    with pytest.raises(GroqAnalysisError):
        call_groq("prompt", client=client)


def test_call_groq_raises_on_api_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("timeout")

    with pytest.raises(GroqAnalysisError):
        call_groq("prompt", client=client)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_groq_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.analysis.groq_client'`

- [ ] **Step 3: Create `backend/app/analysis/groq_client.py`**

```python
import json

from groq import Groq

from app.core.config import settings


class GroqAnalysisError(Exception):
    pass


_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def call_groq(prompt: str, client: Groq | None = None) -> dict:
    active_client = client or _get_client()

    try:
        completion = active_client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as exc:
        raise GroqAnalysisError(f"Groq API request failed: {exc}") from exc

    content = completion.choices[0].message.content

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise GroqAnalysisError(f"Groq returned invalid JSON: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_groq_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/groq_client.py backend/tests/test_groq_client.py
git commit -m "feat: add Groq client wrapper with JSON parsing and error handling"
```

---

### Task 5: Analysis schemas

**Files:**
- Create: `backend/app/analysis/schemas.py`
- Test: `backend/tests/test_schemas.py`

**Interfaces:**
- Produces: `app.analysis.schemas.ALLOWED_LANGUAGES: set[str]`, `app.analysis.schemas.AnalyzeRequest` (fields `codigo: str`, `linguagem: str`, validates length 1-20000 and language membership), `app.analysis.schemas.AnalyzeResponse` (fields `sugestoes: list[str]`, `testes_gerados: str`, `riscos_seguranca: list[str]`), `app.analysis.schemas.HistoryItem` (fields `id: str`, `language: str`, `code_snippet: str`, `created_at: datetime`, `model_config` with `from_attributes=True`) — consumed by Tasks 6, 11, 12.

- [ ] **Step 1: Write the failing tests in `backend/tests/test_schemas.py`**

```python
import pytest
from pydantic import ValidationError

from app.analysis.schemas import AnalyzeRequest


def test_analyze_request_accepts_allowed_language():
    request = AnalyzeRequest(codigo="print(1)", linguagem="python")
    assert request.linguagem == "python"


def test_analyze_request_rejects_unknown_language():
    with pytest.raises(ValidationError):
        AnalyzeRequest(codigo="print(1)", linguagem="cobol")


def test_analyze_request_rejects_empty_code():
    with pytest.raises(ValidationError):
        AnalyzeRequest(codigo="", linguagem="python")


def test_analyze_request_rejects_code_over_20000_chars():
    with pytest.raises(ValidationError):
        AnalyzeRequest(codigo="x" * 20001, linguagem="python")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.analysis.schemas'`

- [ ] **Step 3: Create `backend/app/analysis/schemas.py`**

```python
from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_LANGUAGES = {
    "javascript",
    "typescript",
    "python",
    "java",
    "go",
    "csharp",
    "cpp",
    "ruby",
    "php",
}


class AnalyzeRequest(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=20000)
    linguagem: str

    @field_validator("linguagem")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if value not in ALLOWED_LANGUAGES:
            raise ValueError(f"linguagem deve ser uma de: {sorted(ALLOWED_LANGUAGES)}")
        return value


class AnalyzeResponse(BaseModel):
    sugestoes: List[str]
    testes_gerados: str
    riscos_seguranca: List[str]


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language: str
    code_snippet: str
    created_at: datetime
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_schemas.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/schemas.py backend/tests/test_schemas.py
git commit -m "feat: add Pydantic schemas for analyze request/response and history"
```

---

### Task 6: Analysis service (prompt → Groq → validated response, with one retry)

**Files:**
- Create: `backend/app/analysis/service.py`
- Test: `backend/tests/test_service.py`

**Interfaces:**
- Consumes: `build_prompt` (Task 3), `call_groq`, `GroqAnalysisError` (Task 4), `AnalyzeResponse` (Task 5).
- Produces: `app.analysis.service.AnalysisFailedError(Exception)`, `app.analysis.service.run_analysis(code: str, language: str) -> AnalyzeResponse` — consumed by Task 11.

- [ ] **Step 1: Write the failing tests in `backend/tests/test_service.py`**

```python
import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import patch

import pytest

from app.analysis.service import run_analysis, AnalysisFailedError


def test_run_analysis_succeeds_on_first_try():
    with patch("app.analysis.service.call_groq") as mock_call:
        mock_call.return_value = {
            "sugestoes": ["ok"],
            "testes_gerados": "t",
            "riscos_seguranca": [],
        }

        result = run_analysis("code", "python")

        assert result.sugestoes == ["ok"]
        assert mock_call.call_count == 1


def test_run_analysis_retries_once_on_bad_shape_then_succeeds():
    with patch("app.analysis.service.call_groq") as mock_call:
        mock_call.side_effect = [
            {"unexpected": "shape"},
            {"sugestoes": ["ok"], "testes_gerados": "t", "riscos_seguranca": []},
        ]

        result = run_analysis("code", "python")

        assert result.sugestoes == ["ok"]
        assert mock_call.call_count == 2


def test_run_analysis_fails_after_retry_exhausted():
    with patch("app.analysis.service.call_groq") as mock_call:
        mock_call.side_effect = [{"bad": "shape"}, {"bad": "again"}]

        with pytest.raises(AnalysisFailedError):
            run_analysis("code", "python")

        assert mock_call.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.analysis.service'`

- [ ] **Step 3: Create `backend/app/analysis/service.py`**

```python
from app.analysis.groq_client import call_groq, GroqAnalysisError
from app.analysis.prompt_builder import build_prompt
from app.analysis.schemas import AnalyzeResponse

_RETRY_SUFFIX = (
    "\n\nATENCAO: sua resposta anterior nao estava em JSON valido no formato pedido. "
    "Responda novamente APENAS com o JSON exato no formato especificado, sem texto adicional."
)


class AnalysisFailedError(Exception):
    pass


def run_analysis(code: str, language: str) -> AnalyzeResponse:
    prompt = build_prompt(code, language)

    result = _try_analyze(prompt)
    if result is None:
        result = _try_analyze(prompt + _RETRY_SUFFIX)

    if result is None:
        raise AnalysisFailedError("Groq did not return a valid analysis after retry")

    return result


def _try_analyze(prompt: str) -> AnalyzeResponse | None:
    try:
        raw = call_groq(prompt)
        return AnalyzeResponse(**raw)
    except (GroqAnalysisError, TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_service.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/service.py backend/tests/test_service.py
git commit -m "feat: add analysis service with one retry on malformed Groq response"
```

---

### Task 7: JWT utilities

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/jwt.py`
- Test: `backend/tests/test_jwt.py`

**Interfaces:**
- Consumes: `app.core.config.settings.jwt_secret`, `settings.jwt_expire_minutes` (Task 1).
- Produces: `app.auth.jwt.create_access_token(user_id: str) -> str`, `app.auth.jwt.decode_access_token(token: str) -> str` (raises `jwt.PyJWTError` subclasses on invalid/expired tokens) — consumed by Tasks 8, 9, and `conftest.py` (Task 1).

- [ ] **Step 1: Write the failing tests in `backend/tests/test_jwt.py`**

```python
import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

import time

import jwt as pyjwt
import pytest

from app.auth.jwt import create_access_token, decode_access_token
from app.core.config import settings


def test_create_and_decode_access_token_roundtrip():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_expired_token_raises():
    expired_payload = {"sub": "user-123", "exp": int(time.time()) - 10}
    token = pyjwt.encode(expired_payload, settings.jwt_secret, algorithm="HS256")

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(token)


def test_decode_token_with_wrong_secret_raises():
    token = pyjwt.encode({"sub": "user-123", "exp": int(time.time()) + 60}, "wrong-secret", algorithm="HS256")

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(token)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_jwt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`

- [ ] **Step 3: Create `backend/app/auth/__init__.py` (empty) and `backend/app/auth/jwt.py`**

```python
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    return payload["sub"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_jwt.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/__init__.py backend/app/auth/jwt.py backend/tests/test_jwt.py
git commit -m "feat: add JWT session token creation and validation"
```

---

### Task 8: Auth dependency (get_current_user)

**Files:**
- Create: `backend/app/auth/dependencies.py`

**Interfaces:**
- Consumes: `decode_access_token` (Task 7), `get_db` (Task 1), `User` model (Task 2).
- Produces: `app.auth.dependencies.get_current_user(...) -> User` (FastAPI dependency; raises `HTTPException(401)` on missing/invalid/expired token or unknown user) — consumed by Tasks 10, 11, 12. Verified indirectly through Task 11's and Task 12's endpoint tests (this dependency has no isolated unit test file because its only observable behavior is via the endpoints that use it).

- [ ] **Step 1: Create `backend/app/auth/dependencies.py`**

```python
import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.db.models import User
from app.db.session import get_db

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd backend && GROQ_API_KEY=x JWT_SECRET=x GOOGLE_CLIENT_ID=x GOOGLE_CLIENT_SECRET=x GOOGLE_REDIRECT_URI=http://x DATABASE_URL=sqlite:///:memory: FRONTEND_URL=http://x python -c "from app.auth.dependencies import get_current_user; print('ok')"`
Expected: prints `ok`

This dependency's actual behavior (401 on bad token, 401 on unknown user, success on valid token) is covered by the `/analyze` and `/history` endpoint tests in Tasks 11 and 12, which exercise it end-to-end through `TestClient`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/auth/dependencies.py
git commit -m "feat: add get_current_user dependency for JWT-authenticated routes"
```

---

### Task 9: Google OAuth flow and auth router

**Files:**
- Create: `backend/app/auth/google_oauth.py`
- Create: `backend/app/auth/router.py`
- Test: `backend/tests/test_auth_endpoint.py`

**Interfaces:**
- Consumes: `settings` (Task 1), `create_access_token` (Task 7), `User` model + `get_db` (Tasks 1, 2).
- Produces: `app.auth.google_oauth.build_google_login_url() -> str`, `app.auth.google_oauth.exchange_code_for_userinfo(code: str) -> dict` (keys `google_sub`, `email`, `name`, `avatar_url`), `app.auth.router.router` (FastAPI `APIRouter` with `GET /auth/google/login` and `GET /auth/google/callback`) — consumed by Task 13 (`main.py`).

- [ ] **Step 1: Write the failing test in `backend/tests/test_auth_endpoint.py`**

```python
import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import patch


def test_login_redirects_to_google(client):
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]


def test_callback_creates_user_and_redirects_with_token(client, db_session):
    fake_userinfo = {
        "google_sub": "new-google-sub",
        "email": "new@example.com",
        "name": "New User",
        "avatar_url": None,
    }

    with patch("app.auth.router.exchange_code_for_userinfo", return_value=fake_userinfo):
        response = client.get("/auth/google/callback?code=fake-code", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("http://localhost:5173/auth/callback#token=")

    from app.db.models import User

    user = db_session.query(User).filter(User.google_sub == "new-google-sub").first()
    assert user is not None
    assert user.email == "new@example.com"
```

Note: `exchange_code_for_userinfo` is defined as an `async def` in Step 3 below, but `unittest.mock.patch` with `return_value=fake_userinfo` (a plain dict, not a coroutine) works here because Step 3's router calls `await exchange_code_for_userinfo(code)` — for this to work with a synchronous mock, the router imports and calls the function as `await exchange_code_for_userinfo(code)`; `patch(..., return_value=fake_userinfo)` replaces it with a `MagicMock` whose call returns `fake_userinfo` directly, not a coroutine, which would break `await`. To keep the mock simple and correct, Step 3 implements `exchange_code_for_userinfo` as a **synchronous** function using `httpx.Client` (not `AsyncClient`), so the router calls it without `await` and the test's `patch(..., return_value=...)` works as written. This keeps the OAuth call blocking but it's a single request during a rare login flow, which is an acceptable trade-off for MVP simplicity and testability.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auth_endpoint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.google_oauth'` (or `app.main` missing — expected until Task 13; for now confirm the failure is import-related, not a logic failure)

- [ ] **Step 3: Create `backend/app/auth/google_oauth.py`**

```python
import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def build_google_login_url() -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


def exchange_code_for_userinfo(code: str) -> dict:
    with httpx.Client() as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        tokens = response.json()

    id_info = google_id_token.verify_oauth2_token(
        tokens["id_token"], google_requests.Request(), settings.google_client_id
    )

    return {
        "google_sub": id_info["sub"],
        "email": id_info["email"],
        "name": id_info.get("name", id_info["email"]),
        "avatar_url": id_info.get("picture"),
    }
```

- [ ] **Step 4: Create `backend/app/auth/router.py`**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.google_oauth import build_google_login_url, exchange_code_for_userinfo
from app.auth.jwt import create_access_token
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/auth/google", tags=["auth"])


@router.get("/login")
def login():
    return RedirectResponse(build_google_login_url())


@router.get("/callback")
def callback(code: str, db: Session = Depends(get_db)):
    userinfo = exchange_code_for_userinfo(code)

    user = db.query(User).filter(User.google_sub == userinfo["google_sub"]).first()
    if user is None:
        user = User(
            google_sub=userinfo["google_sub"],
            email=userinfo["email"],
            name=userinfo["name"],
            avatar_url=userinfo["avatar_url"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.email = userinfo["email"]
        user.name = userinfo["name"]
        user.avatar_url = userinfo["avatar_url"]
        db.commit()

    token = create_access_token(user.id)
    return RedirectResponse(f"{settings.frontend_url}/auth/callback#token={token}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_auth_endpoint.py -v`
Expected: PASS (2 passed) — requires `app.main` to exist per Task 13; if run before Task 13, skip execution and revisit after Task 13's Step 4, then confirm PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/google_oauth.py backend/app/auth/router.py backend/tests/test_auth_endpoint.py
git commit -m "feat: add Google OAuth login/callback flow issuing session JWTs"
```

---

### Task 10: Per-user rate limiter

**Files:**
- Create: `backend/app/core/rate_limit.py`

**Interfaces:**
- Produces: `app.core.rate_limit.InMemoryRateLimiter` (class with `check(key: str) -> None`, raises `HTTPException(429)` when exceeded), `app.core.rate_limit.analyze_rate_limiter` (module-level instance configured for 10 requests / 60 seconds), `app.core.rate_limit.enforce_analyze_rate_limit(current_user: User = Depends(get_current_user)) -> User` — consumed by Task 11 and `conftest.py`'s `reset_rate_limiter` fixture (Task 1).

- [ ] **Step 1: Create `backend/app/core/rate_limit.py`**

```python
import threading
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.db.models import User


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window_seconds
            hits[:] = [timestamp for timestamp in hits if timestamp > cutoff]
            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many analysis requests, try again later",
                )
            hits.append(now)


analyze_rate_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)


def enforce_analyze_rate_limit(current_user: User = Depends(get_current_user)) -> User:
    analyze_rate_limiter.check(current_user.id)
    return current_user
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd backend && GROQ_API_KEY=x JWT_SECRET=x GOOGLE_CLIENT_ID=x GOOGLE_CLIENT_SECRET=x GOOGLE_REDIRECT_URI=http://x DATABASE_URL=sqlite:///:memory: FRONTEND_URL=http://x python -c "from app.core.rate_limit import analyze_rate_limiter; print('ok')"`
Expected: prints `ok`

The limiter's 429 behavior is covered by `test_analyze_rate_limit_enforced` in Task 11's endpoint tests.

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/rate_limit.py
git commit -m "feat: add per-user in-memory rate limiter for the analyze endpoint"
```

---

### Task 11: POST /analyze endpoint

**Files:**
- Create: `backend/app/analysis/router.py`
- Test: `backend/tests/test_analyze_endpoint.py`

**Interfaces:**
- Consumes: `AnalyzeRequest`, `AnalyzeResponse` (Task 5), `run_analysis`, `AnalysisFailedError` (Task 6), `enforce_analyze_rate_limit` (Task 10), `get_db` (Task 1), `Analysis` model (Task 2).
- Produces: `app.analysis.router.router` including `POST /analyze` — consumed by Task 13 (`main.py`) and Task 12 (shares the same router file, `GET /history*` added there).

- [ ] **Step 1: Write the failing tests in `backend/tests/test_analyze_endpoint.py`**

```python
import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from unittest.mock import patch

from app.analysis.schemas import AnalyzeResponse
from app.analysis.service import AnalysisFailedError


def test_analyze_success_persists_and_returns_result(client, auth_headers, db_session):
    fake_response = AnalyzeResponse(
        sugestoes=["melhore nomes de variaveis"],
        testes_gerados="def test_x(): pass",
        riscos_seguranca=[],
    )

    with patch("app.analysis.router.run_analysis", return_value=fake_response):
        response = client.post(
            "/analyze",
            json={"codigo": "print(1)", "linguagem": "python"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["sugestoes"] == ["melhore nomes de variaveis"]

    from app.db.models import Analysis

    saved = db_session.query(Analysis).first()
    assert saved is not None
    assert saved.language == "python"
    assert saved.suggestions == ["melhore nomes de variaveis"]


def test_analyze_rejects_empty_code(client, auth_headers):
    response = client.post(
        "/analyze", json={"codigo": "", "linguagem": "python"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_analyze_rejects_invalid_language(client, auth_headers):
    response = client.post(
        "/analyze", json={"codigo": "x = 1", "linguagem": "cobol"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_analyze_requires_auth(client):
    response = client.post("/analyze", json={"codigo": "x = 1", "linguagem": "python"})
    assert response.status_code == 401


def test_analyze_rejects_invalid_token(client):
    response = client.post(
        "/analyze",
        json={"codigo": "x = 1", "linguagem": "python"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_analyze_returns_502_when_groq_fails(client, auth_headers):
    with patch("app.analysis.router.run_analysis", side_effect=AnalysisFailedError("boom")):
        response = client.post(
            "/analyze", json={"codigo": "x = 1", "linguagem": "python"}, headers=auth_headers
        )
    assert response.status_code == 502


def test_analyze_rate_limit_enforced(client, auth_headers):
    fake_response = AnalyzeResponse(sugestoes=[], testes_gerados="", riscos_seguranca=[])

    with patch("app.analysis.router.run_analysis", return_value=fake_response):
        for _ in range(10):
            response = client.post(
                "/analyze", json={"codigo": "x = 1", "linguagem": "python"}, headers=auth_headers
            )
            assert response.status_code == 200

        response = client.post(
            "/analyze", json={"codigo": "x = 1", "linguagem": "python"}, headers=auth_headers
        )

    assert response.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_analyze_endpoint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.analysis.router'` (or `app.main` missing until Task 13 — same caveat as Task 9, revisit after Task 13)

- [ ] **Step 3: Create `backend/app/analysis/router.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.analysis.schemas import AnalyzeRequest, AnalyzeResponse
from app.analysis.service import run_analysis, AnalysisFailedError
from app.core.rate_limit import enforce_analyze_rate_limit
from app.db.models import Analysis, User
from app.db.session import get_db

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    request: AnalyzeRequest,
    current_user: User = Depends(enforce_analyze_rate_limit),
    db: Session = Depends(get_db),
):
    try:
        result = run_analysis(request.codigo, request.linguagem)
    except AnalysisFailedError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    analysis = Analysis(
        user_id=current_user.id,
        language=request.linguagem,
        code_snippet=request.codigo,
        suggestions=result.sugestoes,
        generated_tests=result.testes_gerados,
        security_risks=result.riscos_seguranca,
    )
    db.add(analysis)
    db.commit()

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_analyze_endpoint.py -v`
Expected: PASS (7 passed) — after Task 13 wires `app.main`

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/router.py backend/tests/test_analyze_endpoint.py
git commit -m "feat: add POST /analyze endpoint wiring rate limit, service, and persistence"
```

---

### Task 12: GET /history and GET /history/{id} endpoints

**Files:**
- Modify: `backend/app/analysis/router.py`
- Test: `backend/tests/test_history_endpoint.py`

**Interfaces:**
- Consumes: `HistoryItem`, `AnalyzeResponse` (Task 5), `get_current_user` (Task 8), `Analysis` model (Task 2).
- Produces: `GET /history` (returns `list[HistoryItem]`, only the current user's analyses, newest first) and `GET /history/{analysis_id}` (returns `AnalyzeResponse` or 404 if missing/not owned) added to `app.analysis.router.router`.

- [ ] **Step 1: Write the failing tests in `backend/tests/test_history_endpoint.py`**

```python
import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from app.db.models import Analysis, User


def test_history_returns_only_current_user_analyses(client, auth_headers, test_user, db_session):
    own = Analysis(
        user_id=test_user.id,
        language="python",
        code_snippet="print(1)",
        suggestions=["a"],
        generated_tests="t",
        security_risks=[],
    )
    other_user = User(google_sub="other-sub", email="other@example.com", name="Other")
    db_session.add_all([own, other_user])
    db_session.commit()

    other_analysis = Analysis(
        user_id=other_user.id,
        language="java",
        code_snippet="class X {}",
        suggestions=["b"],
        generated_tests="t2",
        security_risks=[],
    )
    db_session.add(other_analysis)
    db_session.commit()

    response = client.get("/history", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["language"] == "python"


def test_history_requires_auth(client):
    response = client.get("/history")
    assert response.status_code == 401


def test_history_detail_returns_full_analysis(client, auth_headers, test_user, db_session):
    analysis = Analysis(
        user_id=test_user.id,
        language="python",
        code_snippet="print(1)",
        suggestions=["a"],
        generated_tests="t",
        security_risks=["risco x"],
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)

    response = client.get(f"/history/{analysis.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sugestoes"] == ["a"]
    assert body["riscos_seguranca"] == ["risco x"]


def test_history_detail_not_found_for_other_users_analysis(client, auth_headers, db_session):
    other_user = User(google_sub="other-sub-2", email="other2@example.com", name="Other2")
    db_session.add(other_user)
    db_session.commit()

    other_analysis = Analysis(
        user_id=other_user.id,
        language="java",
        code_snippet="class X {}",
        suggestions=["b"],
        generated_tests="t2",
        security_risks=[],
    )
    db_session.add(other_analysis)
    db_session.commit()
    db_session.refresh(other_analysis)

    response = client.get(f"/history/{other_analysis.id}", headers=auth_headers)

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_history_endpoint.py -v`
Expected: FAIL with 404s (routes don't exist yet)

- [ ] **Step 3: Modify `backend/app/analysis/router.py` — add imports and the two new routes**

Add to the imports at the top:

```python
from app.analysis.schemas import AnalyzeRequest, AnalyzeResponse, HistoryItem
from app.auth.dependencies import get_current_user
```

Append at the end of the file:

```python
@router.get("/history", response_model=list[HistoryItem])
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )


@router.get("/history/{analysis_id}", response_model=AnalyzeResponse)
def get_history_item(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analysis = db.get(Analysis, analysis_id)
    if analysis is None or analysis.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    return AnalyzeResponse(
        sugestoes=analysis.suggestions,
        testes_gerados=analysis.generated_tests,
        riscos_seguranca=analysis.security_risks,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_history_endpoint.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/router.py backend/tests/test_history_endpoint.py
git commit -m "feat: add GET /history and GET /history/{id} endpoints scoped per user"
```

---

### Task 13: Wire main.py, CORS, and Docker

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/Dockerfile`
- Create: `backend/docker-entrypoint.sh`

**Interfaces:**
- Consumes: `auth.router.router` (Task 9), `analysis.router.router` (Tasks 11, 12), `settings.frontend_url` (Task 1).
- Produces: `app.main.app` (the FastAPI instance) — consumed by every test file's `client` fixture (Task 1) and by Docker at runtime.

- [ ] **Step 1: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analysis.router import router as analysis_router
from app.auth.router import router as auth_router
from app.core.config import settings

app = FastAPI(title="AI Code Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(analysis_router)
```

- [ ] **Step 2: Run the full backend test suite to verify everything wired together passes**

Run: `cd backend && pytest -v`
Expected: all tests from Tasks 3–12 PASS (this is the point where Tasks 9 and 11's tests, deferred earlier, are confirmed green)

- [ ] **Step 3: Create `backend/docker-entrypoint.sh`**

```bash
#!/bin/sh
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 4: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/Dockerfile backend/docker-entrypoint.sh
git commit -m "feat: wire FastAPI app with CORS and routers; add backend Dockerfile"
```

---

### Task 14: Frontend scaffolding (Vite + React + TypeScript + routing skeleton)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `App` component (default route tree, initially with placeholder pages) — consumed by Task 15 (`AuthContext`/`AuthGuard`) and Task 16 (real pages replace placeholders).

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "ai-code-analyzer-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.2",
    "vite": "^6.0.3"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
```

- [ ] **Step 4: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Code Analyzer</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";

function LoginPlaceholder() {
  return <p>Login page (Task 16)</p>;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPlaceholder />} />
        <Route path="*" element={<LoginPlaceholder />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Create `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 7: Install dependencies and verify the dev server boots**

Run: `cd frontend && npm install`
Expected: installs without errors

Run: `cd frontend && npm run dev`
Expected: Vite prints `Local: http://localhost:5173/`; open it in a browser and confirm the page renders "Login page (Task 16)" with no console errors. Stop the server (Ctrl+C) after verifying.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html frontend/src/main.tsx frontend/src/App.tsx
git commit -m "feat: scaffold Vite React TypeScript frontend with routing skeleton"
```

---

### Task 15: Auth context, guard, and API client

**Files:**
- Create: `frontend/src/context/AuthContext.tsx`
- Create: `frontend/src/components/AuthGuard.tsx`
- Create: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `AuthProvider` (React context provider), `useAuth() -> { token: string | null; setToken: (token: string | null) => void }`, `AuthGuard` (component that redirects to `/login` when `token` is null), `apiFetch<T>(path: string, token: string | null, options?: RequestInit) -> Promise<T>`, `ApiError extends Error` (has `status: number`) — consumed by Tasks 16, 17, 18, 19.

- [ ] **Step 1: Create `frontend/src/context/AuthContext.tsx`**

```tsx
import { createContext, ReactNode, useContext, useState } from "react";

interface AuthContextValue {
  token: string | null;
  setToken: (token: string | null) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);

  return <AuthContext.Provider value={{ token, setToken }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
```

Note: the token is kept in memory only (no `localStorage`/`sessionStorage`), per the spec's XSS-hardening decision — a page refresh logs the user out and they must sign in again.

- [ ] **Step 2: Create `frontend/src/components/AuthGuard.tsx`**

```tsx
import { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function AuthGuard({ children }: { children: ReactNode }) {
  const { token } = useAuth();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
```

- [ ] **Step 3: Create `frontend/src/api/client.ts`**

```typescript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  token: string | null,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }

  return response.json() as Promise<T>;
}
```

- [ ] **Step 4: Modify `frontend/src/App.tsx` to wrap routes in `AuthProvider` and protect the home route with `AuthGuard`**

```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthGuard } from "./components/AuthGuard";
import { AuthProvider } from "./context/AuthContext";

function LoginPlaceholder() {
  return <p>Login page (Task 16)</p>;
}

function HomePlaceholder() {
  return <p>Analyze page (Task 18)</p>;
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPlaceholder />} />
          <Route
            path="/"
            element={
              <AuthGuard>
                <HomePlaceholder />
              </AuthGuard>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

- [ ] **Step 5: Verify in the browser**

Run: `cd frontend && npm run dev`
Expected: visiting `http://localhost:5173/` redirects to `/login` and shows "Login page (Task 16)" (since there's no token yet); visiting `/login` directly also shows that text. Stop the server after verifying.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/context/AuthContext.tsx frontend/src/components/AuthGuard.tsx frontend/src/api/client.ts frontend/src/App.tsx
git commit -m "feat: add in-memory auth context, route guard, and API client"
```

---

### Task 16: Login page and OAuth callback page

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/AuthCallbackPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useAuth` (Task 15).
- Produces: `LoginPage`, `AuthCallbackPage` components — wired into `App.tsx`'s routes, consumed by manual verification in Step 4.

- [ ] **Step 1: Create `frontend/src/pages/LoginPage.tsx`**

```tsx
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function LoginPage() {
  return (
    <div>
      <h1>AI Code Analyzer</h1>
      <a href={`${API_BASE_URL}/auth/google/login`}>
        <button type="button">Entrar com Google</button>
      </a>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/pages/AuthCallbackPage.tsx`**

```tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export function AuthCallbackPage() {
  const { setToken } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const match = window.location.hash.match(/token=([^&]+)/);
    if (match) {
      setToken(decodeURIComponent(match[1]));
      navigate("/", { replace: true });
    } else {
      navigate("/login", { replace: true });
    }
  }, [setToken, navigate]);

  return <p>Entrando...</p>;
}
```

- [ ] **Step 3: Modify `frontend/src/App.tsx` to use the real pages and add the callback route**

```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthGuard } from "./components/AuthGuard";
import { AuthProvider } from "./context/AuthContext";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { LoginPage } from "./pages/LoginPage";

function HomePlaceholder() {
  return <p>Analyze page (Task 18)</p>;
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            path="/"
            element={
              <AuthGuard>
                <HomePlaceholder />
              </AuthGuard>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

- [ ] **Step 4: Verify in the browser**

Run: `cd frontend && npm run dev`
Expected: `/login` shows the "Entrar com Google" button; manually navigating to `/auth/callback#token=fake123` sets the in-memory token and redirects to `/`, which now shows "Analyze page (Task 18)" instead of bouncing to `/login`; navigating to `/auth/callback` with no `#token=` redirects to `/login`. Stop the server after verifying.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/pages/AuthCallbackPage.tsx frontend/src/App.tsx
git commit -m "feat: add login page and OAuth callback token capture"
```

---

### Task 17: Code input, language select, and analysis result components

**Files:**
- Create: `frontend/src/components/LanguageSelect.tsx`
- Create: `frontend/src/components/CodeInput.tsx`
- Create: `frontend/src/components/AnalysisResult.tsx`

**Interfaces:**
- Produces: `LanguageSelect({ value, onChange })`, `CodeInput({ code, language, onCodeChange, onLanguageChange })` (includes the file-upload input that reads a file's text into `onCodeChange`), `AnalysisResult({ result })` where `result: { sugestoes: string[]; testes_gerados: string; riscos_seguranca: string[] } | null` — consumed by Task 18 (`AnalyzePage`) and Task 19 (`HistoryPage`).

- [ ] **Step 1: Create `frontend/src/components/LanguageSelect.tsx`**

```tsx
const LANGUAGES = [
  "javascript",
  "typescript",
  "python",
  "java",
  "go",
  "csharp",
  "cpp",
  "ruby",
  "php",
];

interface LanguageSelectProps {
  value: string;
  onChange: (value: string) => void;
}

export function LanguageSelect({ value, onChange }: LanguageSelectProps) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)} aria-label="Linguagem">
      {LANGUAGES.map((language) => (
        <option key={language} value={language}>
          {language}
        </option>
      ))}
    </select>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/CodeInput.tsx`**

```tsx
import { ChangeEvent } from "react";

import { LanguageSelect } from "./LanguageSelect";

interface CodeInputProps {
  code: string;
  language: string;
  onCodeChange: (code: string) => void;
  onLanguageChange: (language: string) => void;
}

export function CodeInput({ code, language, onCodeChange, onLanguageChange }: CodeInputProps) {
  async function handleFileUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    onCodeChange(text);
  }

  return (
    <div>
      <LanguageSelect value={language} onChange={onLanguageChange} />
      <input type="file" onChange={handleFileUpload} aria-label="Carregar arquivo de codigo" />
      <textarea
        value={code}
        onChange={(event) => onCodeChange(event.target.value)}
        placeholder="Cole seu codigo aqui"
        rows={20}
        aria-label="Codigo"
      />
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/AnalysisResult.tsx`**

```tsx
interface AnalysisResultData {
  sugestoes: string[];
  testes_gerados: string;
  riscos_seguranca: string[];
}

interface AnalysisResultProps {
  result: AnalysisResultData | null;
}

export function AnalysisResult({ result }: AnalysisResultProps) {
  if (!result) return null;

  return (
    <div>
      <section>
        <h3>Sugestoes</h3>
        <ul>
          {result.sugestoes.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </section>
      <section>
        <h3>Testes Gerados</h3>
        <pre>{result.testes_gerados}</pre>
      </section>
      <section>
        <h3>Riscos de Seguranca</h3>
        <ul>
          {result.riscos_seguranca.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Verify components compile**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: no type errors (these components aren't wired into a page yet, but they must type-check cleanly)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/LanguageSelect.tsx frontend/src/components/CodeInput.tsx frontend/src/components/AnalysisResult.tsx
git commit -m "feat: add language select, code input, and analysis result components"
```

---

### Task 18: Analyze page

**Files:**
- Create: `frontend/src/pages/AnalyzePage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `CodeInput`, `AnalysisResult` (Task 17), `useAuth`, `apiFetch`, `ApiError` (Task 15).
- Produces: `AnalyzePage` component, replacing `HomePlaceholder` in `App.tsx`'s `/` route.

- [ ] **Step 1: Create `frontend/src/pages/AnalyzePage.tsx`**

```tsx
import { useState } from "react";

import { ApiError, apiFetch } from "../api/client";
import { AnalysisResult } from "../components/AnalysisResult";
import { CodeInput } from "../components/CodeInput";
import { useAuth } from "../context/AuthContext";

interface AnalyzeResponse {
  sugestoes: string[];
  testes_gerados: string;
  riscos_seguranca: string[];
}

export function AnalyzePage() {
  const { token } = useAuth();
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState("python");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch<AnalyzeResponse>("/analyze", token, {
        method: "POST",
        body: JSON.stringify({ codigo: code, linguagem: language }),
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro inesperado");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <CodeInput
        code={code}
        language={language}
        onCodeChange={setCode}
        onLanguageChange={setLanguage}
      />
      <button type="button" onClick={handleAnalyze} disabled={isLoading || code.trim().length === 0}>
        {isLoading ? "Analisando..." : "Analisar"}
      </button>
      {error && <p role="alert">{error}</p>}
      <AnalysisResult result={result} />
    </div>
  );
}
```

- [ ] **Step 2: Modify `frontend/src/App.tsx` to use `AnalyzePage`**

Replace the `HomePlaceholder` function and its usage with:

```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthGuard } from "./components/AuthGuard";
import { AuthProvider } from "./context/AuthContext";
import { AnalyzePage } from "./pages/AnalyzePage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { LoginPage } from "./pages/LoginPage";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            path="/"
            element={
              <AuthGuard>
                <AnalyzePage />
              </AuthGuard>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

- [ ] **Step 3: Verify in the browser (requires the backend running per Task 13, or a temporary manual token)**

Run: `cd frontend && npm run dev`, and separately `cd backend && uvicorn app.main:app --reload` with a valid `.env`
Expected: navigate to `/auth/callback#token=<a-real-JWT-from-a-manual-login>`, land on `/`, paste a small code snippet, select a language, click "Analisar", and see the loading state followed by the three result sections populated from the real Groq response. If a full OAuth round-trip isn't available yet in this environment, at minimum verify the page renders, the button disables while `code` is empty, and an intentionally-wrong `VITE_API_BASE_URL` produces the `role="alert"` error message.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AnalyzePage.tsx frontend/src/App.tsx
git commit -m "feat: add analyze page wiring code input, API call, and result display"
```

---

### Task 19: History list and history page

**Files:**
- Create: `frontend/src/components/HistoryList.tsx`
- Create: `frontend/src/pages/HistoryPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `AnalysisResult` (Task 17), `useAuth`, `apiFetch` (Task 15).
- Produces: `HistoryList({ items, onSelect })`, `HistoryPage` component, wired at `/historico` in `App.tsx`.

- [ ] **Step 1: Create `frontend/src/components/HistoryList.tsx`**

```tsx
interface HistoryItem {
  id: string;
  language: string;
  code_snippet: string;
  created_at: string;
}

interface HistoryListProps {
  items: HistoryItem[];
  onSelect: (id: string) => void;
}

export function HistoryList({ items, onSelect }: HistoryListProps) {
  if (items.length === 0) {
    return <p>Nenhuma analise ainda.</p>;
  }

  return (
    <ul>
      {items.map((item) => (
        <li key={item.id}>
          <button type="button" onClick={() => onSelect(item.id)}>
            [{item.language}] {new Date(item.created_at).toLocaleString()} —{" "}
            {item.code_snippet.slice(0, 60)}
          </button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 2: Create `frontend/src/pages/HistoryPage.tsx`**

```tsx
import { useEffect, useState } from "react";

import { apiFetch } from "../api/client";
import { AnalysisResult } from "../components/AnalysisResult";
import { HistoryList } from "../components/HistoryList";
import { useAuth } from "../context/AuthContext";

interface HistoryItem {
  id: string;
  language: string;
  code_snippet: string;
  created_at: string;
}

interface AnalyzeResponse {
  sugestoes: string[];
  testes_gerados: string;
  riscos_seguranca: string[];
}

export function HistoryPage() {
  const { token } = useAuth();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [selected, setSelected] = useState<AnalyzeResponse | null>(null);

  useEffect(() => {
    apiFetch<HistoryItem[]>("/history", token).then(setItems);
  }, [token]);

  async function handleSelect(id: string) {
    const detail = await apiFetch<AnalyzeResponse>(`/history/${id}`, token);
    setSelected(detail);
  }

  return (
    <div>
      <HistoryList items={items} onSelect={handleSelect} />
      <AnalysisResult result={selected} />
    </div>
  );
}
```

- [ ] **Step 3: Modify `frontend/src/App.tsx` to add the `/historico` route**

Add the import `import { HistoryPage } from "./pages/HistoryPage";` and add this route inside `<Routes>`, alongside the `/` route:

```tsx
<Route
  path="/historico"
  element={
    <AuthGuard>
      <HistoryPage />
    </AuthGuard>
  }
/>
```

- [ ] **Step 4: Verify in the browser**

Run: `cd frontend && npm run dev` with the backend running and a valid token set via `/auth/callback#token=...`
Expected: navigating to `/historico` lists past analyses for the logged-in user (newest first); clicking one shows its full result via `AnalysisResult`; an unauthenticated visit to `/historico` redirects to `/login`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/HistoryList.tsx frontend/src/pages/HistoryPage.tsx frontend/src/App.tsx
git commit -m "feat: add history list and history page"
```

---

### Task 20: Frontend Dockerfile and full Docker Compose

**Files:**
- Create: `frontend/Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

**Interfaces:**
- Consumes: `backend/Dockerfile` (Task 13), `frontend/package.json` (Task 14).
- Produces: a working `docker-compose up` bringing up `frontend`, `backend`, `db`.

- [ ] **Step 1: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 2: Create `.env.example` at the repo root**

```
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
JWT_SECRET=change-me
JWT_EXPIRE_MINUTES=60
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
DATABASE_URL=postgresql://postgres:postgres@db:5432/ai_code_analyzer
FRONTEND_URL=http://localhost:5173
POSTGRES_DB=ai_code_analyzer
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: Create `docker-compose.yml` at the repo root**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      - db
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    environment:
      VITE_API_BASE_URL: ${VITE_API_BASE_URL}
    depends_on:
      - backend
    ports:
      - "5173:5173"

volumes:
  pgdata:
```

- [ ] **Step 4: Verify the whole stack boots**

Run: `cp .env.example .env` (then fill in real `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` before this step for a real login test), then `docker-compose up --build`
Expected: `db` becomes healthy, `backend` runs `alembic upgrade head` then starts Uvicorn on port 8000 with no errors, `frontend` starts Vite on port 5173; visiting `http://localhost:5173` shows the login page.

- [ ] **Step 5: Commit**

```bash
git add frontend/Dockerfile docker-compose.yml .env.example
git commit -m "feat: add frontend Dockerfile and docker-compose for full stack"
```

---

### Task 21: End-to-end manual verification

**Files:** none (verification only)

**Interfaces:** none — this task exercises the whole system built in Tasks 1–20.

- [ ] **Step 1: Fill in real credentials**

Edit `.env` (created from `.env.example` in Task 20) with a real `GROQ_API_KEY` (from console.groq.com) and a real Google OAuth Web Client's `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, with the authorized redirect URI in Google Cloud Console set to `http://localhost:8000/auth/google/callback`.

- [ ] **Step 2: Boot the stack**

Run: `docker-compose up --build`
Expected: all three services start with no errors, as in Task 20 Step 4.

- [ ] **Step 3: Walk the golden path**

1. Open `http://localhost:5173` → redirected to `/login`.
2. Click "Entrar com Google" → completes Google's consent screen → redirected back to `/auth/callback#token=...` → lands on `/` with the analyzer visible.
3. Select "python", paste a small snippet (e.g. a function with an obvious bug), click "Analisar" → loading state shows, then Sugestões/Testes Gerados/Riscos de Segurança populate from the real Groq response.
4. Navigate to `/historico` → the just-created analysis appears; click it → the same result renders via `AnalysisResult`.
5. Log out is not in scope for the MVP; to test the unauthenticated path, open a private/incognito window and confirm `/` and `/historico` redirect to `/login`.

- [ ] **Step 4: Walk the edge cases**

1. Submit an empty code field → the "Analisar" button stays disabled (client-side); if bypassed via direct API call, confirm a `422` (already covered by Task 11's automated test, this is a smoke check).
2. Upload a small `.txt`/`.py` file via the file input → confirm its contents populate the textarea.
3. Send 11 analyze requests within a minute (e.g. by clicking rapidly) → confirm the 11th shows the error message surfaced from a `429` response.

- [ ] **Step 5: Record results**

No commit for this task — if any step fails, open a follow-up task against the specific file/component involved rather than patching ad hoc during verification.

---

## Self-Review Notes

- **Spec coverage:** Front-end textarea + language selector + upload (§3 → Tasks 17–18), analyze/result panel (§3 → Task 18), POST /analyze building a structured prompt and calling Groq (§4 → Tasks 3, 4, 6, 11), JSON contract (§4 → Task 5), history persistence (§6 → Tasks 2, 12, 19), API key only in backend env (§5, §7 → Task 1, 13), rate limiting (§5, §7 → Task 10), input validation (§7 → Task 5), Pytest coverage of prompt building, error handling, and endpoint behavior (§8 → Tasks 3, 4, 6, 11, 12), Docker Compose with three services (§9 → Tasks 13, 20), Google OAuth + JWT session (§5, §10 → Tasks 7, 8, 9, 15, 16). No spec section is without a task.
- **Placeholder scan:** no `TBD`/`TODO`/"add error handling" phrasing remains; every step has complete, runnable code.
- **Type consistency:** `AnalyzeResponse` fields (`sugestoes`, `testes_gerados`, `riscos_seguranca`) match across `schemas.py`, `service.py`, `router.py`, and the frontend `AnalyzeResponse`/`AnalysisResult` types. `HistoryItem` fields (`id`, `language`, `code_snippet`, `created_at`) match between the backend Pydantic schema and the frontend `HistoryItem` interface. `run_analysis(code: str, language: str) -> AnalyzeResponse` signature is consistent between Task 6's definition and Task 11's call site.
