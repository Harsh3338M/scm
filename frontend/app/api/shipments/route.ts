// app/api/shipments/route.ts — Server Route Handler: query AlloyDB for shipment data
import { NextRequest, NextResponse } from 'next/server'
import { Pool } from 'pg'

// Singleton pool — reused across requests in the same server instance
let pool: Pool | null = null

function getPool(): Pool {
  if (!pool) {
    pool = new Pool({
      connectionString: process.env.ALLOYDB_DSN ?? 'postgresql://scm_app:changeme@localhost:5432/scm_db',
      max: 10,
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 5_000,
      ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
    })
  }
  return pool
}

export interface Shipment {
  shipment_id: string
  origin_hub: string
  destination_hub: string
  carrier_id: string
  status: 'in_transit' | 'delayed' | 'delivered' | 'anomaly'
  updated_at: string
  lat: number | null
  lon: number | null
  temperature: number | null
  speed_kmh: number | null
  last_telemetry_at: string | null
  open_anomalies: number
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { searchParams } = new URL(request.url)
  const limit = Math.min(Number(searchParams.get('limit') ?? '100'), 500)
  const status = searchParams.get('status') // Optional filter

  try {
    const db = getPool()

    const query = status
      ? `
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
          WHERE s.status = $1
          ORDER BY s.updated_at DESC
          LIMIT $2
        `
      : `
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
        `

    const result = status
      ? await db.query<Shipment>(query, [status, limit])
      : await db.query<Shipment>(query, [limit])

    return NextResponse.json(
      { shipments: result.rows, total: result.rows.length },
      {
        headers: {
          'Cache-Control': 'no-store', // Always fresh — real-time data
          'X-Data-Source': 'alloydb-columnar',
        },
      }
    )
  } catch (error) {
    console.error('[/api/shipments] AlloyDB query error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch shipments', details: String(error) },
      { status: 502 }
    )
  }
}
