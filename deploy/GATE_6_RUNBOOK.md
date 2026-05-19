# Gate 6 — Google Chat Real Webhook Runbook

Date: 2026-05-19

## Objective

Validate a real Google Chat event against Lyra Chat Router API before considering endpoint migration complete.

## Current state

- Current Google Chat app endpoint: `https://lyra.grupooliveirarocha.com/googlechat`
- Target router endpoint: `https://api.grupooliveirarocha.com/googlechat/`
- Router public health: `https://api.grupooliveirarocha.com/googlechat/health`
- Router audience expected in prod: `https://api.grupooliveirarocha.com/googlechat/`
- Google Chat service account issuer/email expected: `chat@system.gserviceaccount.com`
- OpenClaw config currently expects audience: `https://lyra.grupooliveirarocha.com/googlechat`

## Hard safety constraint

Google Chat App endpoint is global for the app, not per-space. Switching it affects DMs and all enabled spaces.

The current router MVP only has an active policy for `spaces/AAQAiP4nKa4` (`mkt_performance_analysis_only`). Any other space falls into `default_safe` and receives a denial response.

Therefore, do **not** leave the Chat app endpoint pointed at the router until one of these is true:

1. The router implements all required DM/group behavior; or
2. The migration is intentionally limited to a short test window and rolled back immediately; or
3. A dedicated/staging Google Chat app is used for real JWT validation.

## Preflight checks already passed

```bash
curl -fsS https://api.grupooliveirarocha.com/googlechat/health
# {"status":"ok","service":"lyra-chat-router-api"}

curl -i -X POST https://api.grupooliveirarocha.com/googlechat/ \
  -H 'Content-Type: application/json' \
  -d @tests/fixtures/googlechat_message.json
# HTTP 401 expected without Google bearer token
```

Server env validated on `backends`:

```text
APP_ENV=prod
GOOGLE_CHAT_AUDIENCE=https://api.grupooliveirarocha.com/googlechat/
GOOGLE_CHAT_AUTH_MODE=app_url
GOOGLE_CHAT_DEV_BYPASS_AUTH=false
.env mode=600
service active
```

## Controlled test window procedure

1. Open Google Cloud Console:

   `https://console.developers.google.com/apis/api/chat.googleapis.com/hangouts-chat?project=lyra-490912`

2. Record current values before changing:
   - HTTP endpoint URL: `https://lyra.grupooliveirarocha.com/googlechat`
   - Authentication Audience: HTTP endpoint URL / app URL mode

3. Change HTTP endpoint URL to:

   `https://api.grupooliveirarocha.com/googlechat/`

4. Confirm Authentication Audience remains endpoint/app URL mode, so Google sends an OIDC ID token with audience:

   `https://api.grupooliveirarocha.com/googlechat/`

5. Save.

6. Monitor router logs on `backends`:

   ```bash
   journalctl -u lyra-chat-router-api.service -f
   ```

7. Send one controlled message in the selected test space.

8. Validate:
   - Request reaches router.
   - No 401 from auth.
   - Event is normalized.
   - Policy decision is recorded.
   - Response appears in Google Chat.
   - PostgreSQL audit tables receive rows.

9. Immediately roll back unless full migration behavior is already implemented.

## Rollback

1. In Google Chat API Configuration, restore HTTP endpoint URL:

   `https://lyra.grupooliveirarocha.com/googlechat`

2. Save.

3. Send a DM test to Lyra through Google Chat.

4. Confirm OpenClaw receives and responds normally.

5. Keep router service running for log analysis unless it creates active errors.

## Acceptance criteria for Gate 6

Gate 6 is complete only when a real Google Chat request with Google bearer token reaches the router and passes validation.

A public healthcheck and unauthenticated 401 are Gate 4/5 evidence, not Gate 6 evidence.
