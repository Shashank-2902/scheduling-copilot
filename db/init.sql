-- The two tables of the copilot. Safe to run more than once.
-- (LangGraph creates its own checkpoint tables when the API starts.)

-- A plan that a human approved. This is the only place plans are saved.
CREATE TABLE IF NOT EXISTS committed_plans (
    id           bigserial   PRIMARY KEY,
    instance     text        NOT NULL,
    makespan     integer     NOT NULL,
    schedule     jsonb       NOT NULL,
    question     text,
    reviewer     text        NOT NULL,
    thread_id    text        NOT NULL,
    committed_at timestamptz NOT NULL DEFAULT now()
);

-- Everything that happens around a proposal: asked, approved, rejected, committed.
CREATE TABLE IF NOT EXISTS audit_log (
    id          bigserial   PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now(),
    event       text        NOT NULL,
    thread_id   text,
    details     jsonb       NOT NULL DEFAULT '{}'
);
