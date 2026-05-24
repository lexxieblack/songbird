CREATE TABLE chat.guild_message (
    id              UUID NOT NULL,
    guild_id        BIGINT NOT NULL,
    role            chat.message_role NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_guild_message_id PRIMARY KEY (id)
);

CREATE INDEX idx_message_guild_id_created_at ON chat.guild_message (guild_id, created_at);
