# Lyra Chat Router API — Deploy Checklist

Status: Gates 1 e 2 executados em 2026-05-19; API copiada para o servidor `backends`, mas ainda sem systemd/nginx público.  
Objetivo: subir a API em paralelo, validar com smoke test e só depois decidir troca controlada do endpoint do Google Chat.

## Deployment log

### 2026-05-19 14:22 BRT — Gates 1 e 2 concluídos

- Banco `lyra_chat_router` criado/validado no servidor `database` (`10.0.0.2`).
- Usuário PostgreSQL `chat_router` criado/rotacionado.
- Migration `001_initial.sql` aplicada.
- Seed `mkt_performance_analysis_only:active` validado.
- API copiada para `/opt/lyra-chat-router-api/` no servidor `backends` (`10.0.0.3`).
- `.env` real criado no servidor com permissão `600`.
- Venv criado e dependências instaladas.
- Testes no servidor: `13 passed`.
- Smoke local em prod:
  - `GET /googlechat/health` OK.
  - `POST /googlechat/` sem JWT retornou `401`.
  - Admin com secret retornou modo `database`.
- Smoke local em dev controlado validou persistência de auditoria no banco.

Ainda não executado:

- Gate 3 systemd.
- Gate 4 nginx.
- Gate 5 smoke público.
- Gate 6 Google Chat real.

## Premissas

- Repo final: `ViniciosOliveira/lyra-chat-router-api`.
- Servidor app: `backends` (`10.0.0.3`).
- Servidor DB: `database` (`10.0.0.2`).
- Path app: `/opt/lyra-chat-router-api/`.
- Serviço: `lyra-chat-router-api.service`.
- Porta interna: `127.0.0.1:3201`.
- URL pública alvo: `https://api.grupooliveirarocha.com/googlechat/`.
- Não trocar o endpoint real do Google Chat antes do smoke test externo passar.

## Gate 0 — Pré-deploy obrigatório

- [ ] Repo criado no GitHub.
- [ ] Código pushado com `.env` fora do Git.
- [ ] `pytest -q` passando localmente.
- [ ] Confirmar branch que será deployada: `main`.
- [ ] Gerar senha forte para usuário PostgreSQL `chat_router`.
- [ ] Confirmar se `/googlechat/` no `api.grupooliveirarocha.com` não conflita com rota existente.
- [ ] Confirmar janela de teste para Google Chat.

## Gate 1 — Banco PostgreSQL

Executar no servidor `database` como usuário admin PostgreSQL.

> Atenção: substituir `CHANGE_ME` por senha forte gerada. Não commitar senha.

```bash
psql -U postgres -f deploy/postgres.bootstrap.example.sql
```

Depois aplicar schema inicial:

```bash
psql "postgresql://chat_router:CHANGE_ME@10.0.0.2:5432/lyra_chat_router" \
  -f app/db/migrations/001_initial.sql
```

Validação:

```bash
psql "postgresql://chat_router:CHANGE_ME@10.0.0.2:5432/lyra_chat_router" -c "select key,status from policies;"
```

Resultado esperado:

```text
mkt_performance_analysis_only | active
```

## Gate 2 — App no servidor backends

Executar no servidor `backends`.

```bash
mkdir -p /opt/lyra-chat-router-api
cd /opt/lyra-chat-router-api
git clone git@github.com:ViniciosOliveira/lyra-chat-router-api.git .
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

Criar `/opt/lyra-chat-router-api/.env`:

```env
APP_ENV=prod
APP_NAME=lyra-chat-router-api
PUBLIC_BASE_URL=https://api.grupooliveirarocha.com/googlechat
DATABASE_URL=postgresql+psycopg://chat_router:CHANGE_ME@10.0.0.2:5432/lyra_chat_router
GOOGLE_CHAT_AUDIENCE=https://api.grupooliveirarocha.com/googlechat/
GOOGLE_CHAT_AUTH_MODE=app_url
GOOGLE_CHAT_DEV_BYPASS_AUTH=false
OPENCLAW_FORWARD_ENABLED=false
OPENCLAW_FORWARD_URL=
MC_ADMIN_SHARED_SECRET=GENERATE_STRONG_SECRET
```

Permissões mínimas:

```bash
chmod 600 /opt/lyra-chat-router-api/.env
```

Validação local sem systemd:

```bash
cd /opt/lyra-chat-router-api
. .venv/bin/activate
python3 -m compileall app tests
pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 3201
```

Em outro terminal:

```bash
curl -fsS http://127.0.0.1:3201/googlechat/health
```

Resultado esperado:

```json
{"status":"ok","service":"lyra-chat-router-api"}
```

Observação: `POST /googlechat/` em `APP_ENV=prod` deve retornar `401` sem bearer JWT real do Google. Isso é correto.

## Gate 3 — systemd

Copiar serviço:

```bash
cp /opt/lyra-chat-router-api/deploy/systemd.service.example \
  /etc/systemd/system/lyra-chat-router-api.service
systemctl daemon-reload
systemctl enable lyra-chat-router-api.service
systemctl start lyra-chat-router-api.service
```

Validação:

```bash
systemctl status lyra-chat-router-api.service --no-pager
journalctl -u lyra-chat-router-api.service -n 80 --no-pager
curl -fsS http://127.0.0.1:3201/googlechat/health
```

Critério de sucesso:

- Serviço `active (running)`.
- Healthcheck local OK.
- Sem stacktrace no journal.

## Gate 4 — nginx

Adicionar location no server block de `api.grupooliveirarocha.com`:

```nginx
location /googlechat/ {
    proxy_pass http://127.0.0.1:3201/googlechat/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Authorization $http_authorization;
}
```

Validação antes de reload:

```bash
nginx -t
```

Aplicar:

```bash
systemctl reload nginx
```

Smoke externo:

```bash
curl -fsS https://api.grupooliveirarocha.com/googlechat/health
```

Resultado esperado:

```json
{"status":"ok","service":"lyra-chat-router-api"}
```

## Gate 5 — Smoke de segurança

Sem JWT Google real, o inbound de produção precisa negar:

```bash
curl -i -X POST https://api.grupooliveirarocha.com/googlechat/ \
  -H 'Content-Type: application/json' \
  -d @tests/fixtures/googlechat_message.json
```

Resultado esperado:

```text
HTTP/2 401
```

Se retornar `200`, parar: `GOOGLE_CHAT_DEV_BYPASS_AUTH` está errado ou auth falhou aberto.

## Gate 6 — Teste com Google Chat real

Antes de trocar para todos:

- [ ] Confirmar audience exata no Google Chat App: `https://api.grupooliveirarocha.com/googlechat/`.
- [ ] Confirmar que Google Chat envia `Authorization: Bearer ...` até o backend.
- [ ] Testar em janela controlada.
- [ ] Monitorar logs:

```bash
journalctl -u lyra-chat-router-api.service -f
```

Validações:

- [ ] Health público OK.
- [ ] Evento real chega sem 401.
- [ ] Mensagem é normalizada.
- [ ] Policy aplicada.
- [ ] Resposta síncrona aparece no Google Chat.
- [ ] Auditoria gravada no PostgreSQL.

## Gate 7 — Fallback

Antes de alterar endpoint do app Google Chat:

- [ ] Registrar endpoint antigo do OpenClaw.
- [ ] Ter acesso pronto ao console/config do Google Chat App.
- [ ] Se novo endpoint falhar, voltar imediatamente para endpoint antigo.
- [ ] Não remover configuração atual do OpenClaw até estabilidade comprovada.

## Rollback rápido

1. Voltar endpoint do Google Chat App para OpenClaw.
2. Manter router rodando para investigação.
3. Se necessário:

```bash
systemctl stop lyra-chat-router-api.service
```

4. Não apagar banco/logs antes de análise.

## Critério para considerar deploy concluído

- [ ] `GET /googlechat/health` OK via URL pública.
- [ ] `POST /googlechat/` nega sem JWT em produção.
- [ ] Evento real do Google Chat passa com JWT válido.
- [ ] Resposta aparece no Google Chat.
- [ ] `messages`, `routing_events` e `handler_runs` recebem registros.
- [ ] OpenClaw permanece como fallback durante transição.

## Próxima fase depois do deploy paralelo

- Implementar endpoints admin para Mission Control.
- Criar tela MC para spaces/policies/logs.
- Definir policy de DMs.
- Definir primeira onda de grupos migrados.
- Decidir fila interna para processamentos longos.
