// app/api/whatif/route.ts — Proxy to FastAPI What-If simulation endpoint
import { NextRequest, NextResponse } from 'next/server'

const INTELLIGENCE_URL = process.env.INTELLIGENCE_ENGINE_URL ?? 'http://localhost:8080'

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const body = await request.json()

    const upstream = await fetch(`${INTELLIGENCE_URL}/whatif/simulate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30_000), // 30s timeout for simulation
    })

    const data = await upstream.json()

    return NextResponse.json(data, {
      status: upstream.status,
      headers: {
        'X-Simulation-Engine': 'alloydb-columnar',
      },
    })
  } catch (error) {
    console.error('[/api/whatif] Upstream error:', error)
    return NextResponse.json(
      { error: 'What-If simulation failed', details: String(error) },
      { status: 502 }
    )
  }
}
