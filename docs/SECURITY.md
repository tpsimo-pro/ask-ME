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

Não há correção disponível na linha 0.41.x do starlette — a correção exige subir para 0.47.2+ ou 1.x. Confirmado: `fastapi==0.140.7` está disponível, audita limpo com `pip-audit` (zero achados) e resolveria as 7 CVEs listadas acima. A opção existe e foi avaliada, não é hipotética.

A decisão foi adiar esse upgrade mesmo assim: é um salto de ~25 versões menores do FastAPI, não testado contra as rotas, middlewares e serialização desta aplicação — o risco de quebra silenciosa é maior do que o risco das CVEs em aberto (nenhuma delas foi avaliada como diretamente explorável nas rotas expostas por este app; ver "Quando revisitar" abaixo). Isso é uma escolha de proporcionalidade de esforço/risco feita conscientemente em 2026-07-27, não uma limitação técnica.

### Mitigação atual

O CI (`pip-audit` em `.github/workflows/tests.yml`) ignora explicitamente essas advisories via `--ignore-vuln`, para que o gate continue detectando novas vulnerabilidades sem falhar permanentemente nesta já conhecida.

### Quando revisitar

No prazo de até um trimestre a partir de 2026-07-27 (ou antes, se qualquer uma destas CVEs for reclassificada como explorável nas rotas deste app), planejar e testar o upgrade para `fastapi==0.140.x` (ou a versão estável mais recente na época) em um branch dedicado, com a suíte completa de testes e uma passada manual pelas rotas mais sensíveis (auth, análise). Se o upgrade passar limpo, remover as flags `--ignore-vuln` correspondentes. Também revisitar antes desse prazo caso o FastAPI seja atualizado por qualquer outro motivo — nesse caso, checar se o starlette resultante já resolve essas CVEs de graça.

## Rotação de `JWT_SECRET` sem múltiplas chaves

`backend/app/auth/jwt.py` assina e verifica tokens com um único segredo (`settings.jwt_secret`, HS256). Não há suporte a `kid`/lista de chaves válidas para rotação gradual.

### Impacto de rotacionar o segredo hoje

Todo `access_token` em circulação (validade de 15 min) passa a falhar a verificação imediatamente. O cliente trata isso como uma chamada 401 seguida de um `POST /auth/refresh` automático (o refresh token não depende do JWT secret), então o efeito prático para o usuário é uma chamada extra, não logout nem perda de dados.

### Quando revisitar

Se o volume de usuários simultâneos crescer a ponto de um pico de `/auth/refresh` após rotação de segredo virar um problema de carga, ou se houver requisito de rotação sem nenhum downtime perceptível — nesse caso, introduzir uma lista de segredos válidos para verificação (assinando sempre com o mais recente).

Referência: achado #9 de `docs/agent-reports/2026-07-27-security-engineer-app-security-review.md`.
