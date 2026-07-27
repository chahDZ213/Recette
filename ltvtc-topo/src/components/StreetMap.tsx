import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

type Props = {
  geometry: [number, number][][]
  streetCenter: [number, number]
  beginPoint: [number, number]
  endPoint: [number, number]
  /** Les repères Début/Fin n'apparaissent qu'une fois la réponse révélée. */
  showAnswer: boolean
}

export default function StreetMap({
  geometry,
  streetCenter,
  beginPoint,
  endPoint,
  showAnswer,
}: Props) {
  const host = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)

  useEffect(() => {
    if (!host.current) return
    if (!map.current) {
      map.current = L.map(host.current, {
        zoomControl: false,
        attributionControl: false,
      })
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
      }).addTo(map.current)
    }
    const m = map.current

    // On repart d'une carte vierge à chaque rue, sans détruire la couche de tuiles.
    m.eachLayer((layer) => {
      if (!(layer instanceof L.TileLayer)) m.removeLayer(layer)
    })

    const bounds: L.LatLngExpression[] = []
    for (const seg of geometry) {
      if (seg.length < 2) continue
      L.polyline(seg, { color: '#4da3ff', weight: 6, opacity: 0.9 }).addTo(m)
      bounds.push(...seg)
    }

    if (showAnswer) {
      L.circleMarker(beginPoint, {
        radius: 11,
        color: '#fff',
        weight: 2,
        fillColor: '#43d17c',
        fillOpacity: 1,
      })
        .bindTooltip('Début', { permanent: true, direction: 'top' })
        .addTo(m)
      L.circleMarker(endPoint, {
        radius: 11,
        color: '#fff',
        weight: 2,
        fillColor: '#ff5fa2',
        fillOpacity: 1,
      })
        .bindTooltip('Fin', { permanent: true, direction: 'top' })
        .addTo(m)
      bounds.push(beginPoint, endPoint)
    }

    if (bounds.length) m.fitBounds(L.latLngBounds(bounds).pad(0.3), { maxZoom: 17 })
    else m.setView(streetCenter, 15)

    // Le conteneur est souvent mesuré avant sa mise en page définitive.
    const t = setTimeout(() => m.invalidateSize(), 60)
    return () => clearTimeout(t)
  }, [geometry, streetCenter, beginPoint, endPoint, showAnswer])

  return <div ref={host} className="map" aria-label="Carte de la rue" />
}
