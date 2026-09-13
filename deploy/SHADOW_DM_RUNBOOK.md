# Shadow allowlist da instância limpa

O shadow usa uma allowlist exata de espaço. Não aceita prefixo, usuário ou tipo
de conversa como substituto do identificador canônico.

Configuração aprovada em 2026-09-10:

```dotenv
OPENCLAW_SHADOW_SPACES=spaces/mqWtpSAAAAE,spaces/AAQApxfoZm8,spaces/AAQA8PyOLEI
OPENCLAW_SHADOW_FORWARD_URL=http://10.0.0.5:18790/googlechat
OPENCLAW_SHADOW_AGENT_HOOK_URL=http://10.0.0.5:18790/hooks/agent
OPENCLAW_SHADOW_AGENT_HOOK_TOKEN=<runtime secret>
```

O forward síncrono e o hook assíncrono escolhem o upstream pela mesma
allowlist de identificadores exatos. Os endpoints principais continuam
apontando para a instância antiga. Espaços vazios no CSV são ignorados;
allowlist vazia falha fechada para a instância antiga.

## Gates antes do restart do Router

1. `pull --rebase` em `main`, árvore limpa e release imutável.
2. Testes provam DM do sponsor, Dev FESN e Dev Shared → `18790`, e outro
   espaço → `18789`, nos caminhos síncrono e hook.
3. `backends` alcança `10.0.0.5:18790`; outra origem não autorizada não alcança.
4. Backup de `.env`, unit e revisão atual; rollback resolvido.
5. O token do hook novo entra somente no `.env` root-only do runtime.

## Smoke e rollback

O ensaio obrigatório usa três restarts: candidata, rollback real e restauração
da candidata. Em cada etapa, verificar `/googlechat/health`, autenticação
fail-closed e o upstream selecionado por evento sintético sem entrega.

No UAT final, mensagens reais na DM do sponsor, Dev FESN e Dev Shared devem
ser persistidas somente na instância nova. Um grupo fora da allowlist deve ser
persistido e respondido somente pela instância antiga.

Rollback: restaurar `.env` e release anteriores e reiniciar o Router uma vez.
Não tocar nenhuma das duas instâncias OpenClaw.
