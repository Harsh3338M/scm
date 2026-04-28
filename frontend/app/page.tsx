'use client'

import { useEffect, useState, useCallback } from 'react'
import dynamic from 'next/dynamic'
import useSWR from 'swr'
import type { Shipment } from '@/app/api/shipments/route'
import AnomalyFeed from '@/app/components/AnomalyFeed'
import MetricsBar from '@/app/components/MetricsBar'
import WhatIfPanel from '@/app/components/WhatIfPanel'

// SSR-safe Leaflet map
const ShipmentMap = dynamic(() => import('@/app/components/ShipmentMap'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-slate-600">
        <svg className="animate-spin h-8 w-8 text-neon-400/50" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        <p className="text-sm">Loading map...</p>
      </div>
    </div>
  ),
})

const fetcher = (url: string) => fetch(url).then((r) => r.json())

// ── Mock data for development (shown when AlloyDB is not connected) ──────────
const MOCK_SHIPMENTS: Shipment[] = [
  { shipment_id: 'SHP-2026-001', origin_hub: 'DEL', destination_hub: 'BOM', carrier_id: 'FedEx',
    status: 'anomaly', updated_at: new Date().toISOString(), lat: 22.0, lon: 72.6,
    temperature: 38.5, speed_kmh: 0, last_telemetry_at: new Date().toISOString(), open_anomalies: 2 },
  { shipment_id: 'SHP-2026-002', origin_hub: 'BLR', destination_hub: 'HYD', carrier_id: 'DHL',
    status: 'in_transit', updated_at: new Date().toISOString(), lat: 15.9, lon: 77.0,
    temperature: 24.1, speed_kmh: 85, last_telemetry_at: new Date().toISOString(), open_anomalies: 0 },
  { shipment_id: 'SHP-2026-003', origin_hub: 'MUM', destination_hub: 'CHE', carrier_id: 'BlueDart',
    status: 'delayed', updated_at: new Date().toISOString(), lat: 17.5, lon: 75.8,
    temperature: 29.3, speed_kmh: 12, last_telemetry_at: new Date().toISOString(), open_anomalies: 1 },
  { shipment_id: 'SHP-2026-004', origin_hub: 'DEL', destination_hub: 'PUN', carrier_id: 'DTDC',
    status: 'in_transit', updated_at: new Date().toISOString(), lat: 28.0, lon: 76.5,
    temperature: 21.0, speed_kmh: 110, last_telemetry_at: new Date().toISOString(), open_anomalies: 0 },
  { shipment_id: 'SHP-2026-005', origin_hub: 'CHE', destination_hub: 'BLR', carrier_id: 'FedEx',
    status: 'delivered', updated_at: new Date().toISOString(), lat: 12.9, lon: 77.6,
    temperature: 26.0, speed_kmh: 0, last_telemetry_at: new Date().toISOString(), open_anomalies: 0 },
]

export default function ControlTowerPage() {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Poll AlloyDB every 5 seconds via Route Handler
  const { data, error, isLoading } = useSWR<{ shipments: Shipment[] }>(
    '/api/shipments?limit=200',
    fetcher,
    {
      refreshInterval: 5000,
      onSuccess: () => setLastUpdated(new Date()),
      revalidateOnFocus: true,
    }
  )

  const shipments: Shipment[] = data?.shipments ?? MOCK_SHIPMENTS

  return (
    <div className="flex flex-col min-h-screen">
      {/* ── Top Navigation Bar ──────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-[#080b14]/80 backdrop-blur-md">
        <div className="max-w-[1800px] mx-auto px-6 h-14 flex items-center justify-between gap-4">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-400 to-violet-500 flex items-center justify-center shadow-neon-cyan">
              <span className="text-white text-sm font-black">N</span>
            </div>
            <div>
              <h1 className="text-sm font-bold text-gradient-neon leading-none">NexGen SCM</h1>
              <p className="text-[10px] text-slate-500 leading-none mt-0.5">Control Tower</p>
            </div>
          </div>

          {/* Nav links */}
          <nav className="hidden md:flex items-center gap-6">
            <a href="#" className="nav-link text-neon-400" id="nav-dashboard">Dashboard</a>
            <a href="#whatif-panel" className="nav-link" id="nav-whatif">What-If</a>
            <a href="#anomaly-feed" className="nav-link" id="nav-anomalies">Anomalies</a>
          </nav>

          {/* Status indicators */}
          <div className="flex items-center gap-4">
            {isLoading && (
              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Syncing
              </div>
            )}
            {error && (
              <span className="badge badge-warn text-[10px]">⚠ Using demo data</span>
            )}
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping-slow absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              Live
            </div>
            <div className="text-xs text-slate-500">
              {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
            </div>
          </div>
        </div>
      </header>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-[1800px] mx-auto w-full px-6 py-6 space-y-6">
        {/* Metrics bar */}
        <MetricsBar shipments={shipments} lastUpdated={lastUpdated} />

        {/* Main grid: Map (center) + Feed (right) */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6" style={{ height: '520px' }}>
          {/* Shipment Map */}
          <div className="glass-card overflow-hidden p-0">
            <ShipmentMap shipments={shipments} />
          </div>

          {/* Anomaly Feed */}
          <div className="glass-card p-4 overflow-hidden">
            <AnomalyFeed shipments={shipments} />
          </div>
        </div>

        {/* Bottom grid: What-If (left) + Platform info (right) */}
        <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-6">
          {/* What-If Simulator */}
          <div className="glass-card p-5" style={{ minHeight: '480px' }}>
            <WhatIfPanel />
          </div>

          {/* System Status */}
          <div className="glass-card p-5">
            <h2 className="text-sm font-semibold text-slate-200 mb-4">
              Platform Infrastructure
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
              {[
                { name: 'Pub/Sub Ingestion', status: 'Operational', latency: '< 50ms', icon: '📡', color: 'badge-ok' },
                { name: 'AlloyDB (Columnar)', status: 'Operational', latency: '< 10ms', icon: '🗄️', color: 'badge-ok' },
                { name: 'Vertex AI Endpoint', status: 'Serving', latency: '~120ms', icon: '🤖', color: 'badge-ok' },
                { name: 'Cloud Armor (WAF)', status: 'Active', latency: 'L7 DDoS', icon: '🛡️', color: 'badge-ok' },
                { name: 'Cloud NGFW', status: 'Inspecting', latency: 'East-West', icon: '🔒', color: 'badge-ok' },
                { name: 'OTel Trace', status: 'Collecting', latency: 'OTLP/gRPC', icon: '📊', color: 'badge-ok' },
                { name: 'Go Ingestion Service', status: 'Running', latency: '3 replicas', icon: '⚙️', color: 'badge-ok' },
                { name: 'FastAPI Intelligence', status: 'Running', latency: 'Cloud Run', icon: '🧠', color: 'badge-ok' },
                { name: 'Flutter Mobile App', status: 'v1.0.0', latency: 'Android', icon: '📱', color: 'badge-info' },
              ].map((service) => (
                <div
                  key={service.name}
                  id={`service-${service.name.replace(/\s+/g, '-').toLowerCase()}`}
                  className="glass-card p-3 hover:border-white/20 transition-all duration-200"
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="text-lg">{service.icon}</span>
                    <span className={service.color}>{service.status}</span>
                  </div>
                  <p className="text-xs font-medium text-slate-300">{service.name}</p>
                  <p className="text-[10px] text-slate-600 font-mono mt-0.5">{service.latency}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-4 px-6">
        <div className="max-w-[1800px] mx-auto flex items-center justify-between text-[11px] text-slate-600">
          <span>NexGen SCM Digital Twin — Google Solution Challenge 2026</span>
          <span className="font-mono">
            Powered by Vertex AI · AlloyDB · Cloud Pub/Sub · Cloud Run
          </span>
        </div>
      </footer>
    </div>
  )
}
