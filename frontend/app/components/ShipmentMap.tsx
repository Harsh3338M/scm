'use client'

import { useEffect, useRef } from 'react'
import type { Shipment } from '@/app/api/shipments/route'

interface ShipmentMapProps {
  shipments: Shipment[]
}

const STATUS_COLORS: Record<string, string> = {
  in_transit: '#00d4ff',
  delayed:    '#ffaa00',
  delivered:  '#34d399',
  anomaly:    '#ef4444',
}

export default function ShipmentMap({ shipments }: ShipmentMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapInstanceRef = useRef<any>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markersLayerRef = useRef<any>(null)

  useEffect(() => {
    if (typeof window === 'undefined' || !mapRef.current) return

    // Lazy-load Leaflet (SSR-safe)
    import('leaflet').then((L) => {
      // Fix default icon paths for Next.js
      delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      })

      if (!mapInstanceRef.current) {
        const map = L.map(mapRef.current!, {
          center: [20, 0],
          zoom: 2,
          zoomControl: true,
          attributionControl: false,
        })

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 18,
        }).addTo(map)

        mapInstanceRef.current = map
        markersLayerRef.current = L.layerGroup().addTo(map)
      }

      // Update markers
      const markersLayer = markersLayerRef.current as ReturnType<typeof L.layerGroup>
      markersLayer.clearLayers()

      shipments.forEach((ship) => {
        if (ship.lat == null || ship.lon == null) return

        const color = STATUS_COLORS[ship.status] ?? '#94a3b8'
        const isAnomaly = ship.open_anomalies > 0

        const icon = L.divIcon({
          className: '',
          html: `
            <div style="
              position:relative;
              width:${isAnomaly ? 20 : 14}px;
              height:${isAnomaly ? 20 : 14}px;
            ">
              ${isAnomaly ? `
                <div style="
                  position:absolute;inset:0;
                  background:${color}33;
                  border-radius:50%;
                  animation:ping 1.5s cubic-bezier(0,0,0.2,1) infinite;
                "></div>
              ` : ''}
              <div style="
                position:absolute;inset:${isAnomaly ? 3 : 0}px;
                background:${color};
                border-radius:50%;
                border:2px solid ${color}aa;
                box-shadow:0 0 8px ${color}66;
              "></div>
            </div>
          `,
          iconSize: [isAnomaly ? 20 : 14, isAnomaly ? 20 : 14],
          iconAnchor: [isAnomaly ? 10 : 7, isAnomaly ? 10 : 7],
        })

        const marker = L.marker([ship.lat, ship.lon], { icon })
        marker.bindPopup(`
          <div style="
            background:#0d1117;
            color:#e2e8f0;
            border:1px solid #1e293b;
            border-radius:8px;
            padding:12px;
            min-width:200px;
            font-family:system-ui,sans-serif;
            font-size:13px;
          ">
            <div style="font-weight:600;margin-bottom:8px;color:#00d4ff;">
              📦 ${ship.shipment_id}
            </div>
            <div style="display:grid;gap:4px;">
              <div><span style="color:#64748b;">Route:</span> ${ship.origin_hub} → ${ship.destination_hub}</div>
              <div><span style="color:#64748b;">Carrier:</span> ${ship.carrier_id}</div>
              <div><span style="color:#64748b;">Status:</span>
                <span style="color:${color};font-weight:500;"> ${ship.status}</span>
              </div>
              ${ship.temperature != null ? `<div><span style="color:#64748b;">Temp:</span> ${ship.temperature.toFixed(1)}°C</div>` : ''}
              ${ship.speed_kmh != null ? `<div><span style="color:#64748b;">Speed:</span> ${ship.speed_kmh.toFixed(0)} km/h</div>` : ''}
              ${ship.open_anomalies > 0 ? `
                <div style="margin-top:6px;padding:6px;background:#ef444420;border-radius:4px;color:#f87171;">
                  ⚠️ ${ship.open_anomalies} open anomal${ship.open_anomalies === 1 ? 'y' : 'ies'}
                </div>
              ` : ''}
            </div>
          </div>
        `, {
          className: 'nexgen-popup',
          maxWidth: 280,
        })

        markersLayer.addLayer(marker)
      })
    })

    // Cleanup on unmount
    return () => {
      if (mapInstanceRef.current) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (mapInstanceRef.current as any).remove()
        mapInstanceRef.current = null
        markersLayerRef.current = null
      }
    }
  }, [])

  // Update markers when shipments change without re-creating the map
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current) return

    import('leaflet').then((L) => {
      const markersLayer = markersLayerRef.current as ReturnType<typeof L.layerGroup>
      markersLayer.clearLayers()

      shipments.forEach((ship) => {
        if (ship.lat == null || ship.lon == null) return
        const color = STATUS_COLORS[ship.status] ?? '#94a3b8'
        const icon = L.divIcon({
          className: '',
          html: `<div style="width:12px;height:12px;background:${color};border-radius:50%;border:2px solid ${color}aa;box-shadow:0 0 6px ${color}66;"></div>`,
          iconSize: [12, 12],
          iconAnchor: [6, 6],
        })
        L.marker([ship.lat, ship.lon], { icon })
          .bindTooltip(ship.shipment_id)
          .addTo(markersLayer)
      })
    })
  }, [shipments])

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden">
      {/* Map container */}
      <div ref={mapRef} className="w-full h-full" id="shipment-map" />

      {/* Legend overlay */}
      <div className="absolute bottom-4 right-4 glass-card p-3 text-xs space-y-1.5 z-[1000]">
        <p className="text-slate-400 font-medium mb-2">Legend</p>
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <div key={status} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }}
            />
            <span className="text-slate-300 capitalize">{status.replace('_', ' ')}</span>
          </div>
        ))}
      </div>

      {/* Shipment count badge */}
      <div className="absolute top-4 left-4 badge badge-info z-[1000]">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping-slow absolute inline-flex h-full w-full rounded-full bg-neon-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-neon-400" />
        </span>
        {shipments.length} Active Shipments
      </div>
    </div>
  )
}
