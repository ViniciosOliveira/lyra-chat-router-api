# Google Chat sem menção — Workspace Events API + Pub/Sub

Data: 2026-05-19

## Objetivo

Receber mensagens do `Comitê de Mkt Performance` (`spaces/AAQAiP4nKa4`) mesmo quando Lyra não é mencionada.

## Estado do código

Implementado no router:

- `POST /googlechat/events/pubsub`
- Decodificação de push Pub/Sub (`message.data` base64)
- Normalização de evento Workspace Events API `google.workspace.chat.message.v1.created`
- Filtro anti-loop para mensagens BOT/app
- Filtro de duplicidade por `provider_message_id`
- Policy engine existente reutilizada
- Encaminhamento para OpenClaw via `/hooks/agent` com delivery para Google Chat
- Proteção MVP por header `X-Lyra-Router-Secret`

## Endpoint público

```text
https://api.grupooliveirarocha.com/googlechat/events/pubsub?secret=<GOOGLE_CHAT_PUBSUB_SHARED_SECRET>
```

Header também aceito para smoke manual:

```text
X-Lyra-Router-Secret: <GOOGLE_CHAT_PUBSUB_SHARED_SECRET>
```

Observação: Pub/Sub push não suporta headers customizados arbitrários; por isso o endpoint real usa query param no MVP. Hardening futuro: validação OIDC do Pub/Sub push.

## Configuração Google Cloud necessária

Projeto Google Cloud:

```text
lyra-490912
```

APIs necessárias:

```bash
gcloud services enable pubsub.googleapis.com workspaceevents.googleapis.com chat.googleapis.com
```

Criar tópico:

```bash
gcloud pubsub topics create lyra-chat-router-events
```

Criar push subscription para o router:

```bash
gcloud pubsub subscriptions create lyra-chat-router-events-push \
  --topic=lyra-chat-router-events \
  --push-endpoint='https://api.grupooliveirarocha.com/googlechat/events/pubsub?secret=<GOOGLE_CHAT_PUBSUB_SHARED_SECRET>'
```

Observação: o código atual valida shared secret. Para produção hardening, trocar para validação OIDC Pub/Sub push e remover dependência de header secreto.

Criar Workspace Events subscription para o espaço:

Target resource:

```text
//chat.googleapis.com/spaces/AAQAiP4nKa4
```

Event type:

```text
google.workspace.chat.message.v1.created
```

Notification endpoint:

```text
projects/lyra-490912/topics/lyra-chat-router-events
```

Payload/resource data: incluir resource data da mensagem.

## Permissões/scopes

Para ler mensagens como app, a documentação indica escopo:

```text
https://www.googleapis.com/auth/chat.app.messages.readonly
```

Esse escopo é restrito e exige aprovação/admin approval para app authentication.

## Validação

1. Mandar mensagem no Comitê sem mencionar Lyra.
2. Verificar router:

```bash
journalctl -u lyra-chat-router-api.service -f
```

3. Verificar banco:

```sql
select m.created_at, s.space_name, m.text, r.handler, r.decision, r.reason
from messages m
join spaces s on s.id=m.space_id
join routing_events r on r.message_id=m.id
where s.space_name = 'spaces/AAQAiP4nKa4'
order by m.created_at desc
limit 20;
```

## Rollback

Desativar a Workspace Events subscription ou a Pub/Sub push subscription. O webhook normal com menção continua funcionando em `/googlechat`.

## Bloqueio atual

No host atual não há `gcloud` autenticado e o service account local `cloudclaw@lyra-490912.iam.gserviceaccount.com` não tem permissão para consultar/habilitar APIs de Service Usage (`403`). Configuração Cloud precisa ser feita por conta com permissão de admin/projeto.
