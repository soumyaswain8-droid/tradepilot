-- Migration: ledger/migrations/001_ledger.sql
-- Purpose : TradePilot evidence ledger (spec: docs/superpowers/specs/2026-09-10-m0-truth-first-design.md §5)
-- Date    : 2026-09-10
-- Idempotent: YES (IF NOT EXISTS / OR REPLACE / DROP TRIGGER IF EXISTS; never DROP TABLE)
-- Scope   : schema `tradepilot` only. gen_random_uuid() is core in PostgreSQL 13+ (no extension needed).

BEGIN;

CREATE SCHEMA IF NOT EXISTS tradepilot;

-- Append-only guard: one function, attached to every ledger table.
CREATE OR REPLACE FUNCTION tradepilot.ledger_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'tradepilot.% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'P0001';
END;
$$;

-- Common columns on every table:
--   id uuid, seq (strict insertion order for chain verification), tenant, jurisdiction,
--   licence_scope, payload jsonb (the hashed content), row_hash (sha256 of canonical payload,
--   unique per table), prev_hash (row_hash of the previous row in seq order), created_at.

CREATE TABLE IF NOT EXISTS tradepilot.calls (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq                   bigserial   NOT NULL UNIQUE,
    tenant                text        NOT NULL DEFAULT 'tradepilot',
    jurisdiction          text        NOT NULL DEFAULT 'IN',
    licence_scope         text,
    payload               jsonb       NOT NULL,
    row_hash              text        NOT NULL UNIQUE,
    prev_hash             text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    symbol                text,
    market                text,
    side                  text,
    engine                text,
    published_at          timestamptz,
    pre_registered        boolean     NOT NULL DEFAULT false,
    pre_registration_hash text
);
CREATE INDEX IF NOT EXISTS calls_engine_published_idx ON tradepilot.calls (engine, published_at);
CREATE INDEX IF NOT EXISTS calls_symbol_idx           ON tradepilot.calls (symbol);
CREATE INDEX IF NOT EXISTS calls_tenant_idx           ON tradepilot.calls (tenant);

CREATE TABLE IF NOT EXISTS tradepilot.verdicts (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq           bigserial   NOT NULL UNIQUE,
    tenant        text        NOT NULL DEFAULT 'tradepilot',
    jurisdiction  text        NOT NULL DEFAULT 'IN',
    licence_scope text,
    payload       jsonb       NOT NULL,
    row_hash      text        NOT NULL UNIQUE,
    prev_hash     text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    test_id       text,
    hypothesis    text,
    result        text        CHECK (result IN ('PASS', 'KILL', 'PENDING')),
    author        text
);
CREATE INDEX IF NOT EXISTS verdicts_test_id_idx ON tradepilot.verdicts (test_id);
CREATE INDEX IF NOT EXISTS verdicts_result_idx  ON tradepilot.verdicts (result);

CREATE TABLE IF NOT EXISTS tradepilot.outcomes (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq           bigserial   NOT NULL UNIQUE,
    tenant        text        NOT NULL DEFAULT 'tradepilot',
    jurisdiction  text        NOT NULL DEFAULT 'IN',
    licence_scope text,
    payload       jsonb       NOT NULL,
    row_hash      text        NOT NULL UNIQUE,
    prev_hash     text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    call_id       uuid        REFERENCES tradepilot.calls (id),
    engine        text,
    trade_date    date,
    realized_net  numeric,
    cost          numeric
);
CREATE INDEX IF NOT EXISTS outcomes_engine_date_idx ON tradepilot.outcomes (engine, trade_date);
CREATE INDEX IF NOT EXISTS outcomes_call_id_idx     ON tradepilot.outcomes (call_id);

CREATE TABLE IF NOT EXISTS tradepilot.baselines (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq           bigserial   NOT NULL UNIQUE,
    tenant        text        NOT NULL DEFAULT 'tradepilot',
    jurisdiction  text        NOT NULL DEFAULT 'IN',
    licence_scope text,
    payload       jsonb       NOT NULL,
    row_hash      text        NOT NULL UNIQUE,
    prev_hash     text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    period_date   date,
    rule          text,
    net           numeric
);
CREATE INDEX IF NOT EXISTS baselines_date_rule_idx ON tradepilot.baselines (period_date, rule);

CREATE TABLE IF NOT EXISTS tradepilot.panels (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq           bigserial   NOT NULL UNIQUE,
    tenant        text        NOT NULL DEFAULT 'tradepilot',
    jurisdiction  text        NOT NULL DEFAULT 'IN',
    licence_scope text,
    payload       jsonb       NOT NULL,
    row_hash      text        NOT NULL UNIQUE,
    prev_hash     text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    panel_id      text,
    panel_date    date
);
CREATE INDEX IF NOT EXISTS panels_panel_date_idx ON tradepilot.panels (panel_id, panel_date);

CREATE TABLE IF NOT EXISTS tradepilot.disclosures (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq           bigserial   NOT NULL UNIQUE,
    tenant        text        NOT NULL DEFAULT 'tradepilot',
    jurisdiction  text        NOT NULL DEFAULT 'IN',
    licence_scope text,
    payload       jsonb       NOT NULL,
    row_hash      text        NOT NULL UNIQUE,
    prev_hash     text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    disclosure_type text,
    effective_date  date
);
CREATE INDEX IF NOT EXISTS disclosures_type_date_idx ON tradepilot.disclosures (disclosure_type, effective_date);

CREATE TABLE IF NOT EXISTS tradepilot.ledger_roots (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq           bigserial   NOT NULL UNIQUE,
    tenant        text        NOT NULL DEFAULT 'tradepilot',
    jurisdiction  text        NOT NULL DEFAULT 'IN',
    licence_scope text,
    payload       jsonb       NOT NULL,
    row_hash      text        NOT NULL UNIQUE,
    prev_hash     text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    root_date     date        NOT NULL,
    merkle_root   text        NOT NULL,
    row_count     integer     NOT NULL,
    CONSTRAINT ledger_roots_tenant_date_key UNIQUE (tenant, root_date)
);

-- Append-only triggers (DROP IF EXISTS first so the file re-runs cleanly).
DROP TRIGGER IF EXISTS trg_append_only ON tradepilot.calls;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON tradepilot.calls
    FOR EACH ROW EXECUTE FUNCTION tradepilot.ledger_append_only();

DROP TRIGGER IF EXISTS trg_append_only ON tradepilot.verdicts;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON tradepilot.verdicts
    FOR EACH ROW EXECUTE FUNCTION tradepilot.ledger_append_only();

DROP TRIGGER IF EXISTS trg_append_only ON tradepilot.outcomes;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON tradepilot.outcomes
    FOR EACH ROW EXECUTE FUNCTION tradepilot.ledger_append_only();

DROP TRIGGER IF EXISTS trg_append_only ON tradepilot.baselines;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON tradepilot.baselines
    FOR EACH ROW EXECUTE FUNCTION tradepilot.ledger_append_only();

DROP TRIGGER IF EXISTS trg_append_only ON tradepilot.panels;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON tradepilot.panels
    FOR EACH ROW EXECUTE FUNCTION tradepilot.ledger_append_only();

DROP TRIGGER IF EXISTS trg_append_only ON tradepilot.disclosures;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON tradepilot.disclosures
    FOR EACH ROW EXECUTE FUNCTION tradepilot.ledger_append_only();

DROP TRIGGER IF EXISTS trg_append_only ON tradepilot.ledger_roots;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON tradepilot.ledger_roots
    FOR EACH ROW EXECUTE FUNCTION tradepilot.ledger_append_only();

COMMIT;
