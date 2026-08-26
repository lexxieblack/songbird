CREATE TYPE management.log_action AS ENUM (
    'blackwall_ban'    -- honeypot trigger
);

CREATE TABLE management.audit_log (
    id          UUID NOT NULL,
    action      management.log_action NOT NULL,
    actor_id    BIGINT,
    target_id   BIGINT,
    guild_id    BIGINT,
    channel_id  BIGINT,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_management_audit_log_id PRIMARY KEY (id)
);

CREATE INDEX idx_management_audit_log_guild_action ON management.audit_log (guild_id, action, created_at DESC);
CREATE INDEX idx_management_audit_log_target ON management.audit_log (target_id, created_at DESC);
