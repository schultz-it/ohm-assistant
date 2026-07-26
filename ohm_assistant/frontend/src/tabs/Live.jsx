import { useEffect, useState } from "preact/hooks";
import { get } from "../api.js";

const card = "rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4";
const lbl = "text-xs text-gray-500 dark:text-gray-400";

const METRICS = [
  { k: "flow_temp", label: "Mandata", icon: "🔥" },
  { k: "return_temp", label: "Ritorno", icon: "❄️" },
  { k: "temp_diff", label: "ΔT", icon: "🌡️" },
  { k: "power", label: "Potenza termica", icon: "⚡" },
  { k: "volume_flow", label: "Flusso", icon: "💧" },
];

const fmt = (r) =>
  !r || !r.available ? "—" : `${(+r.value).toLocaleString("it-IT", { maximumFractionDigits: 2 })} ${r.unit}`;

const UNIT_COLOR = {
  andrea: "text-amber-600 dark:text-amber-400",
  genitori: "text-sky-600 dark:text-sky-400",
  comune: "text-gray-500",
};
const SEASON_ICON = { riscaldamento: "🔥", raffrescamento: "❄️" };

// Valore di un registro fissato dall'utente nel Setup.
const Pinned = ({ items }) =>
  !items || items.length === 0 ? null : (
    <div class="mt-2 space-y-1">
      {items.map((c) => (
        <div class="flex justify-between" key={c.address}>
          <span class={lbl}>📌 {c.name}</span>
          <span class="text-sm tabular-nums">
            {!c.available ? "—"
              : c.text != null ? c.text
              : `${(+c.value).toLocaleString("it-IT", { maximumFractionDigits: 2 })} ${c.unit}`}
          </span>
        </div>
      ))}
    </div>
  );

function Room({ room, names }) {
  const r = room.readings;
  const errors = r.errors.raw ? r.errors.text : null;
  return (
    <div class={card}>
      <div class="flex items-baseline justify-between gap-1">
        <div class="font-medium truncate text-sm">{room.name}</div>
        {room.unit && (
          <div class={"text-[10px] shrink-0 " + (UNIT_COLOR[room.unit] || "")}>
            {room.unit === "comune" ? "comune" : names[room.unit] || room.unit}
          </div>
        )}
      </div>
      <div class="text-2xl font-semibold tabular-nums mt-1">
        {r.temperature.available
          ? r.temperature.value.toLocaleString("it-IT", { minimumFractionDigits: 1 })
          : "—"}
        <span class="text-sm text-gray-500"> °C</span>
      </div>
      <div class="mt-1 space-y-1">
        <div class="flex justify-between">
          <span class={lbl}>🎯 Obiettivo</span>
          <span class="text-sm tabular-nums">{fmt(r.target)}</span>
        </div>
        <div class="flex justify-between">
          <span class={lbl}>💧 Umidità</span>
          <span class="text-sm tabular-nums">{fmt(r.humidity)}</span>
        </div>
        <div class="flex justify-between">
          <span class={lbl}>🫧 Rugiada</span>
          <span class="text-sm tabular-nums">{fmt(r.dewpoint)}</span>
        </div>
        <div class="flex justify-between">
          <span class={lbl}>⚙️ Modo</span>
          <span class="text-sm">{r.mode.text}</span>
        </div>
      </div>
      {errors && <div class="text-[11px] text-red-600 mt-1">⚠ {errors}</div>}
    </div>
  );
}

function Base({ base, names }) {
  const m = base.readings;
  const sensorIssue = base.available && m.sensor_errors.raw ? m.sensor_errors.text : null;
  return (
    <div class="space-y-3">
      <div class={card}>
        <div class="flex items-baseline justify-between gap-2">
          <div class="font-semibold truncate">
            {base.name}
            {base.unit && (
              <span class={"ml-2 text-[11px] font-normal " + (UNIT_COLOR[base.unit] || "")}>
                {base.unit === "comune" ? "comune" : names[base.unit] || base.unit}
              </span>
            )}
          </div>
          {base.available && (
            <div class="text-sm tabular-nums shrink-0">
              {fmt(m.flow_temp)}
              <span class={lbl}> / {fmt(m.flow_setpoint)}</span>
            </div>
          )}
        </div>
        {!base.available ? (
          <div class="text-xs text-red-600 mt-1">
            la Smart Base non risponde all'indirizzo {base.address}
          </div>
        ) : (
          <>
            <div class="flex justify-between mt-1">
              <span class={lbl}>🔧 {m.base_type.text}</span>
              <span class={lbl}>{m.sensor_count.value} sensori</span>
            </div>
            {sensorIssue && <div class="text-[11px] text-red-600 mt-1">⚠ {sensorIssue}</div>}
            {base.air_model && (
              <div class="flex justify-between mt-1">
                <span class={lbl}>🌬️ {base.air_model}</span>
                {base.air.custom.length === 0 && (
                  <span class="text-[11px] text-gray-400">nessun parametro fissato</span>
                )}
              </div>
            )}
            <Pinned items={base.air?.custom} />
            <Pinned items={base.custom} />
          </>
        )}
      </div>

      {base.rooms.length > 0 && (
        <div class="grid grid-cols-2 gap-3">
          {base.rooms.map((r) => (
            <Room room={r} names={names} key={`${r.base}.${r.room}`} />
          ))}
        </div>
      )}
    </div>
  );
}

// Eurotherm SmartComfort 365: sistema, zone, Smart Base e stanze via Modbus TCP.
function Eurotherm({ eu, names }) {
  if (!eu || !eu.enabled) return null;
  if (eu.error)
    return (
      <div class={card + " text-sm"}>
        <div class="font-semibold mb-1">🏠 Clima Eurotherm</div>
        <div class="text-red-600 text-xs">Regolatore non raggiungibile: {eu.error}</div>
      </div>
    );

  const sys = eu.system || {};
  const zone = eu.subsystems?.[0]?.readings;
  const season = zone?.operative_mode?.text;

  return (
    <div class="space-y-4">
      <div class={card + " space-y-2"}>
        <div class="flex items-center justify-between">
          <div class="font-semibold">🏠 Clima Eurotherm</div>
          <div class="text-sm">
            {season && <span class="mr-2">{SEASON_ICON[season] || "🌡️"} {season}</span>}
            {zone?.zone_mode && <span class="text-xs text-gray-500">· {zone.zone_mode.text}</span>}
          </div>
        </div>
        <div class="flex justify-between text-sm">
          <span class={lbl}>🌤️ Temperatura esterna</span>
          <span class="font-medium tabular-nums">{fmt(sys.external_temp)}</span>
        </div>
        {zone?.air_boost?.value ? (
          <div class="text-xs text-emerald-600">💨 boost rinnovo aria attivo</div>
        ) : null}
        <Pinned items={eu.custom} />
      </div>

      {eu.bases.length === 0 ? (
        <div class={card + " text-xs text-gray-500"}>
          Nessuna Smart Base attiva — usa “Rileva impianto” nel tab Setup.
        </div>
      ) : (
        eu.bases.map((b) => <Base base={b} names={names} key={b.id} />)
      )}
    </div>
  );
}

export function Live() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [ts, setTs] = useState(null);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      get("api/live")
        .then((x) => { if (alive) { setD(x); setErr(""); setTs(new Date()); } })
        .catch((e) => { if (alive) setErr(e.message); });
    tick();
    const id = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (err && !d)
    return <div class="text-center text-red-600 py-10">Impossibile leggere Home Assistant.<br />{err}</div>;
  if (!d) return <p class="text-center text-gray-500 py-6">Caricamento…</p>;

  const split = d.derived.heat_split_andrea;
  const pctA = split == null ? null : Math.round(split * 100);

  return (
    <div class="space-y-4">
      <div class={card}>
        <div class="flex justify-between items-baseline">
          <div class="font-semibold">Potenza termica totale</div>
          <div class="text-2xl font-semibold">
            {d.derived.total_power == null ? "—" : d.derived.total_power.toLocaleString("it-IT", { maximumFractionDigits: 2 })}
            <span class="text-sm text-gray-500"> kW</span>
          </div>
        </div>
        {pctA != null && (
          <div class="mt-3">
            <div class="flex h-3 rounded-full overflow-hidden">
              <div class="bg-amber-500" style={`width:${pctA}%`} />
              <div class="bg-sky-500" style={`width:${100 - pctA}%`} />
            </div>
            <div class="flex justify-between text-xs mt-1">
              <span class="text-amber-600">{d.names.andrea} {pctA}%</span>
              <span class="text-sky-600">{d.names.genitori} {100 - pctA}%</span>
            </div>
          </div>
        )}
      </div>

      <div class="grid grid-cols-2 gap-3">
        {["andrea", "genitori"].map((u) => (
          <div class={card} key={u}>
            <div class={"font-medium mb-2 " + (u === "andrea" ? "text-amber-600" : "text-sky-600")}>
              {d.names[u]}
            </div>
            <div class="space-y-1.5">
              {METRICS.map((m) => (
                <div class="flex justify-between items-center" key={m.k}>
                  <span class={lbl}>{m.icon} {m.label}</span>
                  <span class="text-sm font-medium tabular-nums">{fmt(d.units[u][m.k])}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div class={card + " flex justify-between items-center"}>
        <span class={lbl}>☀️ Potenza di carico FV</span>
        <span class="text-sm font-medium tabular-nums">{fmt(d.pv.load_power)}</span>
      </div>

      <Eurotherm eu={d.eurotherm} names={d.names} />

      <div class="text-center text-xs text-gray-400">
        {err ? <span class="text-red-500">errore aggiornamento</span>
             : ts && `aggiornato ${ts.toLocaleTimeString("it-IT")}`} · ogni 5s
      </div>
    </div>
  );
}
