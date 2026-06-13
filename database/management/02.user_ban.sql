CREATE TABLE management.user_ban (
    user_id         BIGINT NOT NULL,
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_management_user_id PRIMARY KEY (user_id)
);

CREATE INDEX idx_management_user_id_created_at ON management.user_ban (user_id, created_at);
