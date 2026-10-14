import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import type { CheckinRow, CoolSpace, StationLatest } from "../lib/api";
import { deg, title } from "../lib/format";
import { BAND, riskHex } from "../lib/theme";

const SG_CENTER: [number, number] = [1.355, 103.82];
const TILES = "https://www.onemap.gov.sg/maps/tiles/Grey/{z}/{x}/{y}.png";
const ATTRIBUTION = '<img src="https://www.onemap.gov.sg/web-assets/images/logo/om_logo.png" style="height:16px;width:16px;display:inline;vertical-align:middle" alt=""/> <a href="https://www.onemap.gov.sg/" target="_blank" rel="noreferrer">OneMap</a> &copy; contributors | <a href="https://www.sla.gov.sg/" target="_blank" rel="noreferrer">Singapore Land Authority</a>';

function FitOnResize() {
  const map = useMap();
  useEffect(() => { const t = setTimeout(() => map.invalidateSize(), 50); return () => clearTimeout(t); }, [map]);
  return null;
}

function Base({ children, height }: { children: React.ReactNode; height: number }) {
  return (
    <MapContainer center={SG_CENTER} zoom={11} minZoom={11} maxZoom={18} maxBounds={[[1.144, 103.535], [1.494, 104.1]]} maxBoundsViscosity={1} scrollWheelZoom={false} style={{ height }} className="z-0 rounded-2xl">
      <TileLayer url={TILES} attribution={ATTRIBUTION} />
      <FitOnResize />
      {children}
    </MapContainer>
  );
}

export function AreaMap({ rows, coolSpaces, height = 560 }: { rows: CheckinRow[]; coolSpaces?: CoolSpace[]; height?: number }) {
  const navigate = useNavigate();
  return (
    <Base height={height}>
      {coolSpaces?.map((c) => (
        <CircleMarker key={`${c.name}-${c.latitude}`} center={[c.latitude, c.longitude]} radius={4}
          pathOptions={{ color: "#fff", weight: 1, fillColor: "#0284C7", fillOpacity: 0.9 }}>
          <Tooltip direction="top"><b>{c.name}</b><br />{c.space_type}</Tooltip>
        </CircleMarker>
      ))}
      {[...rows].reverse().map((r) => (
        <CircleMarker key={r.subzone_name} center={[r.centroid_latitude, r.centroid_longitude]}
          radius={Math.max(5, Math.min(22, Math.sqrt(r.pop_65_plus) / 5))}
          pathOptions={{ color: "#fff", weight: 1.5, fillColor: riskHex(r.risk_score), fillOpacity: 0.85 }}
          eventHandlers={{ click: () => navigate(`/area/${encodeURIComponent(r.subzone_name)}`) }}>
          <Tooltip direction="top" offset={[0, -6]}>
            <div className="text-[13px]">
              <div className="font-semibold">#{r.rank} {title(r.subzone_name)}</div>
              <div className="text-ink-500">{title(r.planning_area)}</div>
              <div className="mt-1">Risk {Math.round(r.risk_score)} · Heat {r.action_band ?? "—"} · {r.pop_65_plus.toLocaleString()} seniors</div>
              <div className="text-ink-400">Click for details</div>
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </Base>
  );
}

export function StationMap({ stations, height = 460 }: { stations: StationLatest[]; height?: number }) {
  return (
    <Base height={height}>
      {stations.map((s) => {
        const b = BAND[s.heat_band] ?? BAND.Low;
        return (
          <CircleMarker key={s.station_id} center={[s.latitude, s.longitude]} radius={11}
            pathOptions={{ color: "#fff", weight: 2, fillColor: b.hex, fillOpacity: 0.9 }}>
            <Tooltip direction="top" offset={[0, -8]}>
              <div className="text-[13px]">
                <div className="font-semibold">{s.station_name}</div>
                <div className="text-ink-500">{s.town_center}</div>
                <div className="mt-1">Now {deg(s.wbgt_c)} ({s.heat_band}) at {s.latest_time_sgt}</div>
                <div>Today's peak so far {deg(s.peak_so_far_today_c)}</div>
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </Base>
  );
}
