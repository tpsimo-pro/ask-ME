# Riscos de Segurança Aceitos

Este documento registra decisões de risco residual tomadas conscientemente, para que não sejam reabertas como bugs no futuro sem contexto.

## Vulnerabilidades conhecidas em `starlette` (transitivo via FastAPI)

`backend/requirements.txt` pina `fastapi==0.115.6`, que por sua vez fixa uma versão de `starlette` (0.41.3) com vulnerabilidades conhecidas reportadas por `pip-audit`:
- PYSEC-2026-161 (duplicado em relatório)
- PYSEC-2026-248 (duplicado em relatório)
- PYSEC-2026-249
- PYSEC-2026-1942
- PYSEC-2026-1941
- PYSEC-2026-2281
- PYSEC-2026-2280

### Por que não foi corrigido agora

Não há correção disponível na linha 0.41.x do starlette — a correção exige subir para 0.47.2+ ou 1.x, o que por sua vez provavelmente exige uma atualização do FastAPI em si (a versão do starlette é fixada por compatibilidade). Isso é uma mudança de escopo e risco muito maior do que os apontamentos deste plano de correções de segurança — toca toda a camada de API (routers, middlewares, serialização) e merece sua própria avaliação e plano de testes.

### Mitigação atual

O CI (`pip-audit` em `.github/workflows/tests.yml`) ignora explicitamente essas advisories via `--ignore-vuln`, para que o gate continue detectando novas vulnerabilidades sem falhar permanentemente nesta já conhecida.

### Quando revisitar

Na próxima vez que o FastAPI for atualizado por qualquer outro motivo, revisar se o starlette resultante resolve essas CVEs e remover as flags `--ignore-vuln` correspondentes. 

Também revisitar se alguma dessas CVEs for reclassificada como explorável no contexto específico desta aplicação (hoje nenhuma delas foi avaliada como diretamente explorável nas rotas expostas por este app — essa avaliação caso a caso não foi feita, é uma aceitação de risco por proporcionalidade de esforço, não uma análise de exploitabilidade).

## Rotação de `JWT_SECRET` sem múltiplas chaves

`backend/app/auth/jwt.py` assina e verifica tokens com um único segredo (`settings.jwt_secret`, HS256). Não há suporte a `kid`/lista de chaves válidas para rotação gradual.

### Impacto de rotacionar o segredo hoje

Todo `access_token` em circulação (validade de 15 min) passa a falhar a verificação imediatamente. O cliente trata isso como uma chamada 401 seguida de um `POST /auth/refresh` automático (o refresh token não depende do JWT secret), então o efeito prático para o usuário é uma chamada extra, não logout nem perda de dados.

### Quando revisitar

Se o volume de usuários simultâneos crescer a ponto de um pico de `/auth/refresh` após rotação de segredo virar um problema de carga, ou se houver requisito de rotação sem nenhum downtime perceptível — nesse caso, introduzir uma lista de segredos válidos para verificação (assinando sempre com o mais recente).

Referência: achado #9 de `docs/agent-reports/2026-07-27-security-engineer-app-security-review.md`.
