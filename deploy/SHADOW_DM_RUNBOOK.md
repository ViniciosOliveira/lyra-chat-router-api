# Shadow da DM do sponsor

O shadow usa uma allowlist exata de espaço. Não aceita prefixo, usuário ou tipo
de conversa como substituto do identificador canônico.

Configuração aprovada em 2026-09-10:

```dotenv
OPENCLAW_SHADOW_SPACE=spaces/mqWtpSAAAAE
OPENCLAW_SHADOW_FORWARD_URL=http://10.0.0.5:18790/googlechat
OPENCLAW_SHADOW_AGENT_HOOK_URL=http://10.0.0.5:18790/hooks/agent
OPENCLAW_SHADOW_AGENT_HOOK_TOKEN=<runtime secret>
```

O forward síncrono e o hook assíncrono escolhem o upstream pela mesma igualdade
exata. Os endpoints principais continuam apontando para a instância antiga.

## Gates antes do restart do Router

1. `pull --rebase` em `main`, árvore limpa e release imutável.
2. Testes provam DM do sponsor → `18790` e outro espaço → `18789` nos caminhos
   síncrono e hook.
3. `backends` alcança `10.0.0.5:18790`; outra origem não autorizada não alcança.
4. Backup de `.env`, unit e revisão atual; rollback resolvido.
5. O token do hook novo entra somente no `.env` root-only do runtime.

## Smoke e rollback

Após um único restart, verificar `/googlechat/health`, enviar evento sintético
sem entrega para cada espaço e conferir o upstream selecionado nos logs. O UAT
real é uma mensagem na DM do sponsor, persistida somente na instância nova.

Rollback: restaurar `.env` e release anteriores e reiniciar o Router uma vez.
Não tocar nenhuma das duas instâncias OpenClaw.
