import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Clock, Info, Navigation, Snowflake } from "lucide-react";
import { useState } from "react";
import LocationPicker, { type Picked } from "../components/LocationPicker";
import MapKit, { type Marker } from "../components/MapKit";
import { ErrorState, PageHeader, Skeleton } from "../components/ui";
import { features } from "../lib/api";
import { title } from "../lib/format";
import { heatWords } from "../lib/heat";

export default function CoolPlacesPage() {
  const [place, setPlace] = useState<Picked | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["cool", place?.latitude, place?.longitude], queryFn: () => features.coolPlaces(place!.latitude, place!.longitude), enabled: !!place });
  const d = q.data;

  const markers: Marker[] = d && place ? [
    { id: "me", lat: place.latitude, lon: place.longitude, color: "#111827", radius: 8, label: "•", tooltip: place.label },
    ...d.places.map((p, i) => ({ id: `${p.name}-${i}`, lat: p.latitude, lon: p.longitude, color: "#0284C7", radius: 11, label: String(i + 1),
      selected: focus === `${p.name}-${i}`, onClick: () => setFocus(`${p.name}-${i}`), tooltip: <span><b>{title(p.name)}</b><br />{p.type}</span> })),
  ] : [];

  return (
    <>
      <PageHeader title="Cool places nearby" subtitle="Air-conditioned community clubs and libraries where seniors can rest out of the heat." />
      <section className="mb-5 rounded-3xl border border-ink-200 bg-white p-5 shadow-card"><LocationPicker value={place} onChange={(p) => { setPlace(p); setFocus(null); }} /></section>

      {!place ? <p className="text-sm text-ink-500">Use your location, your centre, or search for an address to see the nearest cool places.</p> :
        q.isPending ? <div className="grid gap-5 lg:grid-cols-[1fr_400px]"><Skeleton className="h-[460px] rounded-3xl" /><Skeleton className="h-[460px] rounded-3xl" /></div> :
        q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} title="Couldn't load cool places" /> : d && (
        <div className="space-y-4">
          {d.heat_now && (
            <div className={clsx("flex flex-wrap items-center gap-2 rounded-2xl p-3.5 text-sm", heatWords(d.heat_now.value_c).cls)}>
              <Snowflake className="h-4 w-4" />Heat right now near you: <b>{heatWords(d.heat_now.value_c).word}</b> ({d.heat_now.value_c.toFixed(1)} °C WBGT, measured at {d.heat_now.station}).
            </div>)}
          <div className="grid gap-5 lg:grid-cols-[1fr_400px]">
            <section className="order-2 rounded-3xl border border-ink-200 bg-white p-3 shadow-card lg:order-1">
              <MapKit markers={markers} fitKey={`${place.latitude},${place.longitude}`} />
            </section>
            <section className="order-1 space-y-3 lg:order-2 lg:max-h-[490px] lg:overflow-y-auto lg:pr-1">
              {d.places.map((p, i) => {
                const id = `${p.name}-${i}`;
                return (
                  <div key={id} className={clsx("rounded-2xl border bg-white p-4 shadow-card", focus === id ? "border-ink-900" : "border-ink-200")} onMouseEnter={() => setFocus(id)}>
                    <div className="flex items-start gap-3">
                      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sky-600 text-xs font-semibold text-white">{i + 1}</span>
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-ink-900">{title(p.name)}</div>
                        <div className="text-sm text-ink-600">{p.type} · {p.straight_km < 1 ? `${Math.round(p.straight_km * 1000)} m` : `${p.straight_km.toFixed(1)} km`} away · about {p.walk_min_estimate} min walk</div>
                        {p.address && <div className="mt-0.5 text-xs text-ink-500">{title(p.address)}</div>}
                        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-500"><Clock className="h-3.5 w-3.5" />Opening hours: not verified — check before going</div>
                      </div>
                    </div>
                    <a href={p.directions_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-ink-900 text-sm font-medium text-white hover:bg-ink-800">
                      <Navigation className="h-4 w-4" />Walking directions
                    </a>
                  </div>);
              })}
            </section>
          </div>
          <p className="flex items-start gap-1.5 text-xs text-ink-500"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />{d.coverage} Walking times are estimates (4 km/h, allowing for street layout); directions open in Google Maps. Source: {d.source}.</p>
        </div>
      )}
    </>
  );
}
