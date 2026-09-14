# Router — suplemento técnico histórico A3

Registro editorial de 14/09/2026, baseado no dossiê de maio a setembro.
Não é estado atual de produção, autorização de operação nem runbook de deploy.
Não contém o cadastro privado de usuários/espaços ou os seletores ativos.
O código, [README](../../../README.md), [pendências](../../../PENDING.md) e
[runbooks de deploy](../../../deploy/) do sistema prevalecem.

## Arquitetura e fronteiras

O Router é API independente (Python/FastAPI), não um módulo executável do
Mission Control. O MC é consumidor administrativo. O recebimento Google Chat,
autenticação, normalização, policy, roteamento e auditoria pertencem ao Router;
o OpenClaw é um destino permitido pela policy, não a fonte da autorização.
O domínio HTTP compartilhado não implica processo, banco ou secrets compartilhados.

O desenho inicial separava inbound webhook, policy engine, handlers, audit logger
e painel administrativo. PostgreSQL próprio/schema isolado guardaria spaces,
users, space_users, policies, messages, routing_events e handler_runs. O modelo
inclui IDs de provedor, direção, intenção, decisão/motivo, latência, tentativas,
erro redigido e timestamps. Nomes do desenho não substituem migrations vigentes.
Auditoria pode usar log local sem banco no desenvolvimento; em produção,
a configuração real e a política de falhas devem ser verificadas no código.

Health, inbound e admin têm contratos diferentes: health não prova autorização;
admin deve exigir autenticação própria; o endpoint de simulação não deve enviar
mensagem. Nenhum bearer, secret ou payload pessoal deve aparecer em log público.
Análise de dados não autoriza emissão, modificação, envio ou publicação.

## Evolução do protocolo — maio/2026

- O bootstrap começou com health, normalizador, engine deny-by-default,
  handlers mínimos, seed idempotente, migrations e fixture. Encaminhamento,
  UI do MC e troca do endpoint global eram etapas distintas.
- POST sem barra final sofreu redirect 301 seguido de GET/405. O tratamento
  passou a aceitar as duas formas sem redirect que altere o método.
- A validação JWT precisou contemplar audiência com/sem barra e os envelopes
  Google Chat clássico e Workspace Add-ons. Isso não dispensa validação de
  assinatura, issuer/principal e audience conforme código vigente.
- O Add-on fornece chat.messagePayload.space/message e chat.user; a resposta
  usa hostAppDataAction.chatDataAction.createMessageAction.message. HTTP 200
  no envelope errado não é prova de entrega ao usuário.
- Forward permitido transporta contexto namespaced _lyraRouter, com policy e
  escopo. Deny é local. Timeout/erro de transporte deve ser distinguido de
  resposta entregue pelo canal de saída do próprio gateway.
- Pub/Sub decodifica message.data/base64 e Workspace Events, ignora BOT/APP e
  deduplica provider_message_id entre menção e eventos sem menção. A falta
  de autenticação em produção deve falhar fechada.
- IAM, habilitação de API e grant OAuth do Chat são pré-requisitos diferentes.
  Uma consulta bem-sucedida não prova permissão para criar subscription.
  Subscriptions expiram: criação, renovação e reativação precisam de evidência.
- A chave de sessão por espaço preserva continuidade e evita uma sessão por
  thread. Prefixos permitidos de hooks devem aceitar a defaultSessionKey;
  rejeição desse contrato pode impedir inicialização do gateway.
- Cópia de release já apagou .env por exclusão incorreta. Configuração e
  secrets devem ser preservados separadamente, com backup antes da operação.

## Entrega e idempotência — junho/2026

A correção de 08/06 rejeitava resposta vazia; em 10/06 ficou demonstrado que
HTTP 2xx com JSON {} pode significar entrega direta pelo OpenClaw. Reinterpretar
isso como falha criava um segundo hook e respostas tardias sem contexto.
A regra histórica posterior passou a aceitar dict 2xx, inclusive {}, e só
considerar fallback em erro real de forward. Fallback assíncrono foi desativado
até haver idempotência/tracking confiável: este texto não o reativa.

O delivery_ledger usa provider_message_id único e estados received, forwarding,
forwarded, delivered e retry_pending. Duplicata já concluída não reprocessa.
Forwarded não equivale a entrega visível: a entrega deve ser provada no canal.
O watchdog lista stale e marca alertas; não reenvia respostas automaticamente.
O runner histórico consultava até 20 registros com idade acima de 120 segundos,
saía 0 sem pendências e 2 com pendências; isso é histórico, não agenda vigente.

## Políticas, continuidade e isolamento — julho a setembro/2026

- Registries separados por produto evitam colisão de roteamento CRM/MC.
- Divergência entre allowlist global e account.default no gateway causou
  descarte silencioso mesmo com allow no Router e HTTP 200. Read-back deve
  verificar os dois caminhos quando a versão ativa exigir ambos.
- Confirmação curta só pode recuperar uma solicitação no mesmo espaço, thread
  e usuário, dentro da janela limitada (15 minutos na implementação histórica),
  consumir a pendência uma vez e negar em falha de banco. Um “sim” isolado não
  é permissão genérica. Remover thread do forward só quando o contrato de
  entrega daquele fluxo exigir resposta na raiz.
- Continuação de análise aprovada deve retomar a tarefa pendente; cobrança
  genérica não deve virar operação. Classificação de relatório de certificados
  e catálogos deve ser distinta de emissão, alteração ou publicação.
- Escalation é para decisão realmente desconhecida, não para contornar deny
  explícito. Contexto necessário inclui origem, solicitante, thread e mensagem;
  o cadastro e exemplos reais permanecem privados.
- Falha transitória ao buscar certificados Google foi tratada com cache que
  respeita Cache-Control, timeout de três segundos e dois retries de transporte.
  Token inválido continua rejeitado. Readiness deve ser aguardada: um health
  consultado antes de Uvicorn abrir a porta causou rollback prematuro.
- Trabalho durável e autorização sensível não podem ser inferidos de texto
  histórico. O contrato atual de execução é externo a este suplemento.
- Um UAT inicialmente declarado como isolamento de agente foi invalidado por
  inspeção posterior do store: resposta no canal prova comunicação, não binding
  ao agente esperado. Verificar agente, chave de sessão e persistência real.
- Produção atualizada por cópia pode ter HEAD antigo com arquivos novos.
  Comparar hashes de arquivos com release canônica; HEAD isolado não é prova.

## Evidências e limites

O dossiê registra suítes de 7/13 testes no bootstrap até 98 em agosto, testes
focados, smokes HTTP, backups e verificações de hash. São evidências datadas,
não testes executados nesta migração. Há registros de falhas ambientais por
carregar .env de produção em testes dev e de TestClient que trava; a dívida
atual de CI permanece em PENDING.md. Suíte focada ou health não substitui gate
integral, JWT real, evento real e resposta observada no destino correto.

O roadmap histórico sequenciava bootstrap → inbound → policy → forward → painel
MC → migração controlada. A troca do endpoint do app é global, não por grupo;
é necessário mapear o comportamento de todos os espaços antes da mudança.
Nada neste PR altera esse endpoint, upstream, timer, banco, configuração ou código.
