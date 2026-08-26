CREATE TABLE management.blackwall (
    guild_id            BIGINT NOT NULL,
    channel_id          BIGINT,
    log_channel_id      BIGINT,
    whitelisted_roles   BIGINT[] NOT NULL DEFAULT '{}',
    banned_count        INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_management_blackwall_guild_id PRIMARY KEY (guild_id)
);