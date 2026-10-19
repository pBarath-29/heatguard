import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";

const TILES = "https://www.onemap.gov.sg/maps/tiles/Grey/{z}/{x}/{y}.png";
const ATTRIBUTION = '<a href="https://www.onemap.gov.sg/" target="_blank" rel="noreferrer">OneMap</a> © contributors | <a href="https://www.sla.gov.sg/" target="_blank" rel="noreferrer">Singapore Land Authority</a>';

function Fit({ points, version }: { points: [number, number][]; version: string }) {
  const map = useMap();
  useEffect(() => {
    const t = setTimeout(() => {
      map.invalidateSize();
      if (points.length === 1) map.setView(points[0], 16);
      else if (points.length > 1) map.fitBounds(points as LatLngBoundsExpression, { padding: [40, 40], maxZoom: 17 });
    }, 60);
    return () => clearTimeout(t);
  }, [map, version]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export interface Marker {
  id: string; lat: number; lon: number; color: string; radius?: number; label?: string; tooltip: React.ReactNode;
  selected?: boolean; onClick?: () => void; ring?: string;
}

/** OneMap base map with circle markers and an optional line (e.g. a walking order). Zoom with +/−; fits to the markers. */
export default function MapKit({ markers, line, height = 460, fitKey }: { markers: Marker[]; line?: [number, number][]; height?: number; fitKey: string }) {
  const pts: [number, number][] = markers.map((m) => [m.lat, m.lon]);
  return (
    <MapContainer center={[1.355, 103.82] as LatLngExpression} zoom={12} minZoom={11} maxZoom={19} scrollWheelZoom={false}
      maxBounds={[[1.144, 103.535], [1.494, 104.1]]} style={{ height }} className="z-0 rounded-2xl">
      <TileLayer url={TILES} attribution={ATTRIBUTION} maxNativeZoom={19} />
      <Fit points={pts} version={fitKey} />
      {line && line.length > 1 && <Polyline positions={line} pathOptions={{ color: "#C2410C", weight: 4, opacity: 0.8, dashArray: "8 8" }} />}
      {markers.map((m) => (
        <CircleMarker key={m.id} center={[m.lat, m.lon]} radius={(m.radius ?? 8) + (m.selected ? 3 : 0)}
          pathOptions={{ color: m.selected ? "#111827" : m.ring ?? "#fff", weight: m.selected ? 3 : 2, fillColor: m.color, fillOpacity: 0.92 }}
          eventHandlers={m.onClick ? { click: m.onClick } : undefined}>
          {/* Leaflet allows one tooltip per marker: numbered markers keep the number visible and show details on tap */}
          {m.label ? <><Tooltip permanent direction="center" className="hg-label">{m.label}</Tooltip><Popup offset={[0, -6]}>{m.tooltip}</Popup></>
            : <Tooltip direction="top" offset={[0, -8]}>{m.tooltip}</Tooltip>}
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
