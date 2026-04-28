# app/db/alloydb.py — AlloyDB async connection management and schema
from __future__ import annotations

import logging
import os
from typing import Any

import asyncpg

logger = logging.getLogger("nexgen.db")

ALLOYDB_DSN = os.getenv(
    "ALLOYDB_DSN",
    "postgresql://scm_app:changeme@localhost:5432/scm_db",
)
POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN", "5"))
POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX", "20"))

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the global connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=ALLOYDB_DSN,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            command_timeout=30,
            statement_cache_size=100,
        )
        logger.info(
            f"AlloyDB connection pool created: min={POOL_MIN_SIZE}, max={POOL_MAX_SIZE}"
        )
    return _pool


async def close_pool() -> None:
    """Close the connection pool gracefully."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("AlloyDB connection pool closed")


# ─────────────────────────────────────────────
# Schema Migration (idempotent)
# ─────────────────────────────────────────────

SCHEMA_SQL = """
-- Enable the pgcrypto extension for UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Shipments ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id     TEXT PRIMARY KEY,
    origin_hub      TEXT NOT NULL,
    destination_hub TEXT NOT NULL,
    carrier_id      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'in_transit',  -- in_transit | delayed | delivered | anomaly
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB
);

-- ── Telemetry (time-series, partitioned by day via inheritance) ───────────
CREATE TABLE IF NOT EXISTS telemetry (
    id              BIGSERIAL,
    device_id       TEXT NOT NULL,
    shipment_id     TEXT NOT NULL REFERENCES shipments(shipment_id),
    event_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    temperature     DOUBLE PRECISION,
    humidity        DOUBLE PRECISION,
    speed_kmh       DOUBLE PRECISION,
    battery_pct     DOUBLE PRECISION,
    PRIMARY KEY (id, event_time)
) PARTITION BY RANGE (event_time);

-- Create monthly partitions for the current and next 3 months
DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE);
    i INT;
BEGIN
    FOR i IN 0..3 LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS telemetry_%s PARTITION OF telemetry
             FOR VALUES FROM (%L) TO (%L)',
            TO_CHAR(start_date + (i || ' months')::INTERVAL, 'YYYY_MM'),
            start_date + (i || ' months')::INTERVAL,
            start_date + ((i + 1) || ' months')::INTERVAL
        );
    END LOOP;
END $$;

-- ── Anomaly Events ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS anomaly_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id       TEXT NOT NULL,
    shipment_id     TEXT NOT NULL,
    route_id        TEXT,
    anomaly_score   DOUBLE PRECISION NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    details         JSONB
);

-- ── Routes ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS routes (
    route_id                TEXT PRIMARY KEY,
    origin_hub              TEXT NOT NULL,
    destination_hub         TEXT NOT NULL,
    carrier_id              TEXT NOT NULL,
    estimated_transit_days  DOUBLE PRECISION NOT NULL,
    base_cost_usd           DOUBLE PRECISION NOT NULL,
    cost_per_kg_usd         DOUBLE PRECISION NOT NULL DEFAULT 0.01,
    waypoints               TEXT[],
    carrier_ids_filter      TEXT[],
    active                  BOOLEAN NOT NULL DEFAULT TRUE
);

-- ── Carriers ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS carriers (
    carrier_id   TEXT PRIMARY KEY,
    carrier_name TEXT NOT NULL,
    country_code TEXT,
    active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- ── Indexes ───────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_telemetry_shipment ON telemetry (shipment_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_device ON telemetry (device_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_shipment ON anomaly_events (shipment_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_score ON anomaly_events (anomaly_score DESC) WHERE NOT resolved;
CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments (status, updated_at DESC);

-- ── Updated_at trigger ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS shipments_updated_at ON shipments;
CREATE TRIGGER shipments_updated_at
    BEFORE UPDATE ON shipments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
"""


async def run_migrations() -> None:
    """Run idempotent schema migrations on startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    logger.info("AlloyDB schema migrations applied successfully")


# ─────────────────────────────────────────────
# Query Helpers
# ─────────────────────────────────────────────

async def get_shipments_summary(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch latest shipments with their most recent telemetry."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                s.shipment_id,
                s.origin_hub,
                s.destination_hub,
                s.carrier_id,
                s.status,
                s.updated_at,
                t.lat,
                t.lon,
                t.temperature,
                t.speed_kmh,
                t.event_time AS last_telemetry_at,
                COALESCE(ae.open_anomalies, 0) AS open_anomalies
            FROM shipments s
            LEFT JOIN LATERAL (
                SELECT lat, lon, temperature, speed_kmh, event_time
                FROM telemetry
                WHERE shipment_id = s.shipment_id
                ORDER BY event_time DESC
                LIMIT 1
            ) t ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS open_anomalies
                FROM anomaly_events
                WHERE shipment_id = s.shipment_id AND NOT resolved
            ) ae ON TRUE
            ORDER BY s.updated_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def upsert_shipment(shipment: dict[str, Any]) -> None:
    """Insert or update a shipment record."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO shipments (shipment_id, origin_hub, destination_hub, carrier_id, status, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            ON CONFLICT (shipment_id) DO UPDATE
            SET status = EXCLUDED.status,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            shipment["shipment_id"],
            shipment["origin_hub"],
            shipment["destination_hub"],
            shipment["carrier_id"],
            shipment.get("status", "in_transit"),
            __import__("json").dumps(shipment.get("metadata", {})),
        )
