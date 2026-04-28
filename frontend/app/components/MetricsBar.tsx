'use client'

import type { Shipment } from '@/app/api/shipments/route'

interface MetricsBarProps {
  shipments: Shipment[]
  lastUpdated: Date | null
}

export default function MetricsBar({ shipments, lastUpdated }: MetricsBarProps) {
  const total = shipments.length
  const inTransit = shipments.filter((s) => s.status === 'in_transit').length
  const delayed = shipments.filter((s) => s.status === 'delayed').length
  const anomalies = shipments.filter((s) => s.status === 'anomaly' || s.open_anomalies > 0).length
  const delivered = shipments.filter((s) => s.status === 'delivered').length

  const metrics = [
    {
      id: 'metric-total',
      label: 'Total Shipments',
      value: total,
      icon: '📦',
      color: 'text-slate-200',
      subtext: 'active fleet',
    },
    {
      id: 'metric-transit',
      label: 'In Transit',
      value: inTransit,
      icon: '🚀',
      color: 'text-neon-400',
      subtext: `${total > 0 ? ((inTransit / total) * 100).toFixed(0) : 0}% of fleet`,
    },
    {
      id: 'metric-delayed',
      label: 'Delayed',
      value: delayed,
      icon: '⏳',
      color: 'text-amber-400',
      subtext: delayed > 0 ? 'needs attention' : 'on schedule',
    },
    {
      id: 'metric-anomalies',
      label: 'Anomalies',
      value: anomalies,
      icon: '🚨',
      color: anomalies > 0 ? 'text-crimson-400' : 'text-emerald-400',
      subtext: anomalies > 0 ? 'active alerts' : 'all clear',
      pulse: anomalies > 0,
    },
    {
      id: 'metric-delivered',
      label: 'Delivered Today',
      value: delivered,
      icon: '✅',
      color: 'text-emerald-400',
      subtext: 'completed',
    },
  ]

  return (
    <div className="flex items-center gap-4 flex-wrap">
      {metrics.map((metric) => (
        <div
          key={metric.id}
          id={metric.id}
          className={`metric-card flex-1 min-w-[140px] ${
            metric.pulse ? 'border-crimson-500/30 animate-pulse-slow' : ''
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-lg">{metric.icon}</span>
            {metric.pulse && (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-crimson-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-crimson-500" />
              </span>
            )}
          </div>
          <div>
            <p className={`text-2xl font-bold tabular-nums ${metric.color}`}>
              {metric.value.toLocaleString()}
            </p>
            <p className="text-[11px] text-slate-400 font-medium">{metric.label}</p>
          </div>
          <p className="text-[10px] text-slate-600">{metric.subtext}</p>
        </div>
      ))}

      {/* Last updated timestamp */}
      {lastUpdated && (
        <div className="text-[10px] text-slate-600 font-mono ml-auto self-end pb-1">
          Updated {lastUpdated.toLocaleTimeString()}
        </div>
      )}
    </div>
  )
}
