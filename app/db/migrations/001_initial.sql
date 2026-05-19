-- Lyra Chat Router API — initial schema
-- Target database: lyra_chat_router

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS spaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    space_name text NOT NULL UNIQUE,
    display_name text,
    space_type text NOT NULL DEFAULT 'unknown',
    status text NOT NULL DEFAULT 'active',
    default_policy_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    google_user_name text NOT NULL UNIQUE,
    email text,
    display_name text,
    status text NOT NULL DEFAULT 'unknown',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key text NOT NULL UNIQUE,
    name text NOT NULL,
    description text,
    allowed_intents jsonb NOT NULL DEFAULT '[]'::jsonb,
    blocked_intents jsonb NOT NULL DEFAULT '[]'::jsonb,
    allowed_handlers jsonb NOT NULL DEFAULT '[]'::jsonb,
    requires_owner_approval boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_spaces_default_policy'
    ) THEN
        ALTER TABLE spaces
            ADD CONSTRAINT fk_spaces_default_policy
            FOREIGN KEY (default_policy_id) REFERENCES policies(id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS space_users (
    space_id uuid NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role text NOT NULL DEFAULT 'unknown',
    allowed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (space_id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_message_id text,
    space_id uuid REFERENCES spaces(id),
    user_id uuid REFERENCES users(id),
    thread_name text,
    direction text NOT NULL,
    event_type text NOT NULL,
    text text,
    payload_redacted jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS routing_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id uuid REFERENCES messages(id),
    policy_id uuid REFERENCES policies(id),
    classified_intent text NOT NULL,
    handler text NOT NULL,
    decision text NOT NULL,
    reason text,
    latency_ms integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS handler_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    routing_event_id uuid REFERENCES routing_events(id),
    handler text NOT NULL,
    status text NOT NULL DEFAULT 'queued',
    request_redacted jsonb NOT NULL DEFAULT '{}'::jsonb,
    response_redacted jsonb NOT NULL DEFAULT '{}'::jsonb,
    error text,
    started_at timestamptz,
    finished_at timestamptz
);

INSERT INTO policies (key, name, description, allowed_intents, blocked_intents, allowed_handlers)
VALUES (
    'mkt_performance_analysis_only',
    'Mkt Performance — somente análise',
    'Permite análises e relatórios de marketing performance; bloqueia execução operacional.',
    '["marketing_analysis","performance_report","tracking_diagnosis","metric_explanation","recommendation"]'::jsonb,
    '["campaign_change","budget_change","tag_change","pixel_change","code_change","deploy","external_message_send","unknown_operational_execution"]'::jsonb,
    '["direct_reply","analytics_handler","deny_handler"]'::jsonb
)
ON CONFLICT (key) DO NOTHING;
