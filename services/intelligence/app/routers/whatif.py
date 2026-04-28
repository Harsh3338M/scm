# app/routers/whatif.py — What-If simulation router (AlloyDB columnar engine)
from __future__ import annotations

import logging
import os
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("nexgen.whatif")
router = APIRouter()

ALLOYDB_DSN = os.getenv(
    "ALLOYDB_DSN",
    "postgresql://scm_app:changeme@localhost:5432/scm_db",
)


# ─────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────

class WhatIfScenario(BaseModel):
    """Parameters for a What-If route simulation."""
    origin_hub: str = Field(..., description="Origin hub code (e.g., 'DEL')")
    destination_hub: str = Field(..., description="Destination hub code (e.g., 'BOM')")
    cargo_weight_kg: float = Field(..., ge=0.1, le=50000)
    carrier_ids: list[str] = Field(default_factory=list, description="Filter to specific carrier IDs")
    max_transit_days: int = Field(default=7, ge=1, le=30)
    avoid_anomaly_routes: bool = Field(default=True)


class RouteOption(BaseModel):
    route_id: str
    carrier_id: str
    carrier_name: str
    estimated_transit_days: float
    estimated_cost_usd: float
    anomaly_risk_score: float
    waypoints: list[str]
    is_recommended: bool


class WhatIfResult(BaseModel):
    scenario: WhatIfScenario
    routes: list[RouteOption]
    simulation_duration_ms: float
    engine: str = "AlloyDB Columnar Engine"


# ─────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────

@router.post(
    "/simulate",
    response_model=WhatIfResult,
    summary="Run What-If route simulation using AlloyDB columnar engine",
)
async def simulate(body: WhatIfScenario) -> WhatIfResult:
    """
    Runs a What-If scenario simulation by querying the AlloyDB columnar engine.
    The columnar engine accelerates the complex analytical joins and window
    functions needed to score route options in real time.
    """
    import time
    start = time.monotonic()

    try:
        conn = await asyncpg.connect(ALLOYDB_DSN)
    except Exception as exc:
        logger.error(f"AlloyDB connection failed: {exc}")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    try:
        # This query leverages the AlloyDB columnar engine for the analytical
        # window functions and aggregations. The /*+ COLUMNAR */ hint is
        # not required — AlloyDB automatically routes eligible queries.
        rows = await conn.fetch(
            """
            WITH route_scores AS (
                SELECT
                    r.route_id,
                    r.carrier_id,
                    c.carrier_name,
                    r.estimated_transit_days,
                    -- Cost model: base rate + weight surcharge
                    (r.base_cost_usd + ($3 * r.cost_per_kg_usd)) AS estimated_cost_usd,
                    -- Anomaly risk: rolling average of last 30 days on this route
                    COALESCE(
                        AVG(a.anomaly_score) OVER (
                            PARTITION BY r.route_id
                            ORDER BY a.event_time
                            ROWS BETWEEN 30 PRECEDING AND CURRENT ROW
                        ),
                        0.0
                    ) AS anomaly_risk_score,
                    r.waypoints
                FROM routes r
                JOIN carriers c ON r.carrier_id = c.carrier_id
                LEFT JOIN anomaly_events a ON a.route_id = r.route_id
                WHERE
                    r.origin_hub = $1
                    AND r.destination_hub = $2
                    AND r.estimated_transit_days <= $4
                    AND ($5 OR ARRAY_LENGTH(r.carrier_ids_filter, 1) IS NULL
                         OR r.carrier_id = ANY($6::text[]))
                ORDER BY estimated_cost_usd ASC
                LIMIT 10
            )
            SELECT
                route_id,
                carrier_id,
                carrier_name,
                estimated_transit_days,
                estimated_cost_usd,
                anomaly_risk_score,
                waypoints,
                -- Recommend the lowest-cost route with anomaly_risk < 0.5
                (anomaly_risk_score < 0.5 AND estimated_cost_usd = MIN(estimated_cost_usd)
                 OVER ()) AS is_recommended
            FROM route_scores
            WHERE NOT ($7 AND anomaly_risk_score > 0.75)
            ORDER BY estimated_cost_usd ASC
            """,
            body.origin_hub,
            body.destination_hub,
            body.cargo_weight_kg,
            body.max_transit_days,
            len(body.carrier_ids) == 0,  # True = no carrier filter
            body.carrier_ids or [],
            body.avoid_anomaly_routes,
        )
    except Exception as exc:
        logger.error(f"What-If query failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Simulation query failed: {exc}")
    finally:
        await conn.close()

    routes = [
        RouteOption(
            route_id=str(row["route_id"]),
            carrier_id=str(row["carrier_id"]),
            carrier_name=str(row["carrier_name"]),
            estimated_transit_days=float(row["estimated_transit_days"]),
            estimated_cost_usd=float(row["estimated_cost_usd"]),
            anomaly_risk_score=float(row["anomaly_risk_score"]),
            waypoints=list(row["waypoints"] or []),
            is_recommended=bool(row["is_recommended"]),
        )
        for row in rows
    ]

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        f"What-If: {body.origin_hub}→{body.destination_hub} "
        f"returned {len(routes)} routes in {elapsed_ms:.1f}ms"
    )

    return WhatIfResult(
        scenario=body,
        routes=routes,
        simulation_duration_ms=round(elapsed_ms, 2),
    )
