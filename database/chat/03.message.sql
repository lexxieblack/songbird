CREATE TABLE chat.message (
    id              UUID NOT NULL,
    user_id         BIGINT NOT NULL,
    role            chat.message_role NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_message_user_id PRIMARY KEY (id)
);

CREATE INDEX idx_message_user_id_created_at ON chat.message (user_id, created_at);
