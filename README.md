# Lyra Chat Router API

API independente para receber eventos do Google Chat, aplicar policies por grupo/usuário/escopo e rotear para handlers seguros.

## Status

Skeleton local inicial. Ainda não está em produção e não recebe o endpoint real do Google Chat.

Entregue até aqui:

- FastAPI com `/googlechat/health` e `POST /googlechat/`.
- Validação Google Chat preparada com bypass apenas para dev.
- Normalizador de payload Google Chat.
- Policy engine MVP com policy `mkt_performance_analysis_only`.
- Bloqueio explícito de execução operacional.
- Auditoria estruturada com fallback em log e persistência em PostgreSQL quando `DATABASE_URL` estiver configurado.
- Admin interno mínimo: `/admin/spaces`, `/admin/routing-events`, `/admin/test/route`.
- Auth admin via `X-MC-Admin-Secret`.
- Migration SQL inicial e bootstrap SQL exemplo.
- Smoke test local.

## Rodar local

```bash
cd projects/lyra-chat-router/api
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 3201
```

## Healthcheck

```bash
curl http://127.0.0.1:3201/googlechat/health
```

## Testes

```bash
pytest
```

## Smoke test local

Em um terminal:

```bash
uvicorn app.main:app --reload --port 3201
```

Em outro:

```bash
./deploy/smoke_test.sh http://127.0.0.1:3201
```

## Admin interno

Endpoints:

- `GET /admin/spaces`
- `GET /admin/routing-events`
- `POST /admin/test/route`

Autenticação:

```bash
-H 'X-MC-Admin-Secret: dev-admin-secret'
```

Em dev, se `MC_ADMIN_SHARED_SECRET` não estiver definido, o fallback é `dev-admin-secret`. Em produção, `MC_ADMIN_SHARED_SECRET` é obrigatório.

Exemplo:

```bash
curl -fsS \
  -H 'X-MC-Admin-Secret: dev-admin-secret' \
  -H 'Content-Type: application/json' \
  -d @tests/fixtures/googlechat_message.json \
  http://127.0.0.1:3201/admin/test/route
```

## Banco

Database recomendado: `lyra_chat_router` no PostgreSQL existente.

Arquivos relevantes:

- `deploy/postgres.bootstrap.example.sql` — exemplo para criar database/usuário.
- `app/db/migrations/001_initial.sql` — schema inicial e seed idempotente da policy.

Sem `DATABASE_URL`, a API roda localmente e registra auditoria apenas em log. Com `DATABASE_URL`, cada mensagem roteada tenta persistir `messages`, `routing_events` e `handler_runs`.

## Segurança de produção

Antes de produção:

- `APP_ENV=prod`
- `GOOGLE_CHAT_DEV_BYPASS_AUTH=false`
- `GOOGLE_CHAT_AUDIENCE=https://api.grupooliveirarocha.com/googlechat/`
- `MC_ADMIN_SHARED_SECRET` forte e fora do Git.
- Não trocar o endpoint real do Google Chat antes do smoke test em staging.
