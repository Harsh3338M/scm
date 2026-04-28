'use client'

import { formatDistanceToNow } from 'date-fns'
import { useState } from 'react'
import type { Shipment } from '@/app/api/shipments/route'

interface AnomalyFeedProps {
  shipments: Shipment[]
}

const SEVERITY_MAP = {
  anomaly:    { label: 'Critical', className: 'badge-error', icon: '🚨' },
  delayed:    { label: 'Warning',  className: 'badge-warn',  icon: '⚠️' },
  in_transit: { label: 'Normal',   className: 'badge-ok',    icon: '✅' },
  delivered:  { label: 'OK',       className: 'badge-ok',    icon: '📦' },
}

export default function AnomalyFeed({ shipments }: AnomalyFeedProps) {
  const [filter, setFilter] = useState<'all' | 'anomaly' | 'delayed'>('all')

  const alerts = shipments
    .filter((s) => {
      if (filter === 'anomaly') return s.status === 'anomaly' || s.open_anomalies > 0
      if (filter === 'delayed') return s.status === 'delayed'
      return s.status !== 'delivered'
    })
    .sort((a, b) => {
      // Anomalies first, then delayed, then in_transit
      const priority: Record<string, number> = { anomaly: 0, delayed: 1, in_transit: 2, delivered: 3 }
      return (priority[a.status] ?? 4) - (priority[b.status] ?? 4)
    })
    .slice(0, 50)

  const anomalyCount = shipments.filter((s) => s.status === 'anomaly' || s.open_anomalies > 0).length
  const delayedCount = shipments.filter((s) => s.status === 'delayed').length

  return (
    <div className="flex flex-col h-full" id="anomaly-feed">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-200">Anomaly Feed</h2>
          {anomalyCount > 0 && (
            <span className="badge badge-error animate-pulse-slow">
              {anomalyCount} Critical
            </span>
          )}
        </div>
        {/* Live indicator */}
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          Live
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 bg-white/5 rounded-lg p-1">
        {[
          { key: 'all',     label: 'All Events' },
          { key: 'anomaly', label: `Critical (${anomalyCount})` },
          { key: 'delayed', label: `Delayed (${delayedCount})` },
        ].map(({ key, label }) => (
          <button
            key={key}
            id={`feed-filter-${key}`}
            onClick={() => setFilter(key as typeof filter)}
            className={`flex-1 text-xs py-1.5 px-2 rounded-md transition-all duration-200 font-medium ${
              filter === key
                ? 'bg-neon-400/20 text-neon-400 border border-neon-400/30'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Feed list */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-600 text-sm gap-2">
            <span className="text-2xl">🎉</span>
            <p>No active alerts</p>
          </div>
        ) : (
          alerts.map((shipment) => {
            const severity = SEVERITY_MAP[shipment.status] ?? SEVERITY_MAP.in_transit
            return (
              <div
                key={shipment.shipment_id}
                className={`glass-card p-3 animate-slide-up hover:border-white/20 transition-all duration-200 cursor-pointer group ${
                  shipment.status === 'anomaly' ? 'border-crimson-500/30 bg-crimson-500/5' :
                  shipment.status === 'delayed' ? 'border-amber-400/30 bg-amber-400/5' : ''
                }`}
                id={`alert-${shipment.shipment_id}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-base flex-shrink-0">{severity.icon}</span>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-slate-200 truncate">
                        {shipment.shipment_id}
                      </p>
                      <p className="text-xs text-slate-500 truncate">
                        {shipment.origin_hub} → {shipment.destination_hub}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className={severity.className}>{severity.label}</span>
                    {shipment.open_anomalies > 0 && (
                      <span className="text-[10px] text-crimson-400 font-mono">
                        {shipment.open_anomalies} alerts
                      </span>
                    )}
                  </div>
                </div>

                {/* Details row */}
                <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-500 font-mono">
                  <span>{shipment.carrier_id}</span>
                  {shipment.temperature != null && (
                    <span>🌡 {shipment.temperature.toFixed(1)}°C</span>
                  )}
                  {shipment.speed_kmh != null && (
                    <span>⚡ {shipment.speed_kmh.toFixed(0)} km/h</span>
                  )}
                  {shipment.last_telemetry_at && (
                    <span className="ml-auto">
                      {formatDistanceToNow(new Date(shipment.last_telemetry_at), { addSuffix: true })}
                    </span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
