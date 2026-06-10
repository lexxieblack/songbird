CREATE TABLE management.guild_ban (
    guild_id         BIGINT NOT NULL,
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_management_guild_id PRIMARY KEY (guild_id)
);

CREATE INDEX idx_management_guild_id_created_at ON management.guild_ban (guild_id, created_at);
