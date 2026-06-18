CREATE TABLE IF NOT EXISTS feedback.thread (
    user_id         BIGINT NOT NULL,
    thread_id       BIGINT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_thread PRIMARY KEY (user_id)
);

CREATE INDEX idx_thread_user_id_thread_id ON feedback.thread (user_id, thread_id);
