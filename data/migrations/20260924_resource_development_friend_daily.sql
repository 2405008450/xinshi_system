BEGIN;
CREATE TABLE IF NOT EXISTS resource_development_friend_daily (
    id uuid PRIMARY KEY,
    work_date date NOT NULL UNIQUE,
    rows json NOT NULL DEFAULT '[]',
    applied json NOT NULL DEFAULT '[]',
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_by uuid NOT NULL REFERENCES app_user(id),
    updated_by uuid NOT NULL REFERENCES app_user(id),
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMIT;
