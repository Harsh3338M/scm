'use client'

import { useState } from 'react'

interface Route {
  route_id: string
  carrier_id: string
  carrier_name: string
  estimated_transit_days: number
  estimated_cost_usd: number
  anomaly_risk_score: number
  waypoints: string[]
  is_recommended: boolean
}

interface SimulationResult {
  routes: Route[]
  simulation_duration_ms: number
  engine: string
}

export default function WhatIfPanel() {
  const [origin, setOrigin] = useState('DEL')
  const [destination, setDestination] = useState('BOM')
  const [cargoWeight, setCargoWeight] = useState(500)
  const [maxTransitDays, setMaxTransitDays] = useState(7)
  const [avoidAnomalyRoutes, setAvoidAnomalyRoutes] = useState(true)
  const [result, setResult] = useState<SimulationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runSimulation = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/whatif', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin_hub: origin,
          destination_hub: destination,
          cargo_weight_kg: cargoWeight,
          max_transit_days: maxTransitDays,
          avoid_anomaly_routes: avoidAnomalyRoutes,
        }),
      })
      if (!response.ok) throw new Error(await response.text())
      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full" id="whatif-panel">
      <h2 className="text-sm font-semibold text-slate-200 mb-4">
        What-If Scenario Simulator
        <span className="ml-2 text-[10px] text-neon-400 font-mono normal-case">
          AlloyDB Columnar Engine
        </span>
      </h2>

      {/* Controls */}
      <div className="space-y-3 mb-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wide font-medium">Origin Hub</label>
            <input
              id="whatif-origin"
              value={origin}
              onChange={(e) => setOrigin(e.target.value.toUpperCase())}
              maxLength={10}
              className="mt-1 w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200
                         focus:outline-none focus:border-neon-400/50 focus:ring-1 focus:ring-neon-400/20 transition-all font-mono"
            />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wide font-medium">Destination Hub</label>
            <input
              id="whatif-destination"
              value={destination}
              onChange={(e) => setDestination(e.target.value.toUpperCase())}
              maxLength={10}
              className="mt-1 w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200
                         focus:outline-none focus:border-neon-400/50 focus:ring-1 focus:ring-neon-400/20 transition-all font-mono"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wide font-medium">
              Cargo Weight (kg)
            </label>
            <input
              id="whatif-weight"
              type="number"
              value={cargoWeight}
              onChange={(e) => setCargoWeight(Number(e.target.value))}
              min={1}
              max={50000}
              className="mt-1 w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200
                         focus:outline-none focus:border-neon-400/50 transition-all"
            />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wide font-medium">
              Max Transit (days)
            </label>
            <input
              id="whatif-transit"
              type="number"
              value={maxTransitDays}
              onChange={(e) => setMaxTransitDays(Number(e.target.value))}
              min={1}
              max={30}
              className="mt-1 w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200
                         focus:outline-none focus:border-neon-400/50 transition-all"
            />
          </div>
        </div>

        <label className="flex items-center gap-3 cursor-pointer group" htmlFor="whatif-avoid-anomaly">
          <div className="relative">
            <input
              id="whatif-avoid-anomaly"
              type="checkbox"
              className="sr-only peer"
              checked={avoidAnomalyRoutes}
              onChange={(e) => setAvoidAnomalyRoutes(e.target.checked)}
            />
            <div className="w-9 h-5 bg-white/10 peer-focus:ring-1 peer-focus:ring-neon-400/30 rounded-full peer
                            peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px]
                            after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all
                            peer-checked:bg-neon-400/60" />
          </div>
          <span className="text-xs text-slate-400 group-hover:text-slate-300 transition-colors">
            Avoid high-risk anomaly routes
          </span>
        </label>

        <button
          id="whatif-run-btn"
          onClick={runSimulation}
          disabled={loading}
          className="w-full py-2.5 px-4 bg-gradient-to-r from-neon-500/80 to-violet-600/80 hover:from-neon-400/90
                     hover:to-violet-500/90 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm
                     font-semibold rounded-lg transition-all duration-200 shadow-neon-cyan hover:shadow-neon-violet
                     active:scale-95"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Simulating...
            </span>
          ) : (
            '⚡ Run Simulation'
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="glass-card border-crimson-500/30 bg-crimson-500/5 p-3 text-xs text-crimson-400 mb-4">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="flex-1 overflow-y-auto space-y-2 animate-fade-in">
          <div className="flex items-center justify-between text-[10px] text-slate-500 mb-2">
            <span>{result.routes.length} routes found</span>
            <span className="font-mono">{result.simulation_duration_ms.toFixed(0)}ms · {result.engine}</span>
          </div>

          {result.routes.map((route, idx) => (
            <div
              key={route.route_id}
              id={`route-${route.route_id}`}
              className={`glass-card p-3 transition-all duration-200 ${
                route.is_recommended
                  ? 'border-emerald-400/40 bg-emerald-400/5 shadow-[0_0_12px_rgba(52,211,153,0.1)]'
                  : 'hover:border-white/20'
              }`}
            >
              {route.is_recommended && (
                <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-semibold mb-2">
                  ⭐ Recommended Route
                </div>
              )}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-medium text-slate-200">{route.carrier_name}</p>
                  <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                    {route.waypoints.join(' → ') || `${origin} → ${destination}`}
                  </p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-bold text-neon-400">${route.estimated_cost_usd.toFixed(0)}</p>
                  <p className="text-[10px] text-slate-500">{route.estimated_transit_days}d</p>
                </div>
              </div>

              {/* Risk bar */}
              <div className="mt-2">
                <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                  <span>Anomaly Risk</span>
                  <span className={route.anomaly_risk_score > 0.5 ? 'text-crimson-400' : 'text-emerald-400'}>
                    {(route.anomaly_risk_score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      route.anomaly_risk_score > 0.75 ? 'bg-crimson-500' :
                      route.anomaly_risk_score > 0.5 ? 'bg-amber-400' : 'bg-emerald-400'
                    }`}
                    style={{ width: `${route.anomaly_risk_score * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
