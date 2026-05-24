CREATE TABLE IF NOT EXISTS chat.user_info (
    user_id         BIGINT NOT NULL,
    user_info       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_user_info_user_id PRIMARY KEY (user_id)
);

CREATE INDEX idx_user_info_user_id ON chat.user_info (user_id);
