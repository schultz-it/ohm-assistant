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

// Eurotherm Smart365: zone climatiche lette via Modbus TCP dal regolatore.
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
  const season = sys.season?.text;

  return (
    <div class="space-y-3">
      <div class={card + " space-y-2"}>
        <div class="flex items-center justify-between">
          <div class="font-semibold">🏠 Clima Eurotherm</div>
          <div class="text-sm">
            {season && <span class="mr-2">{SEASON_ICON[season] || "🌡️"} {season}</span>}
            {sys.presence?.available && (
              <span class="text-xs text-gray-500">· {sys.presence.text}</span>
            )}
          </div>
        </div>
        <div class="flex justify-between text-sm">
          <span class={lbl}>🌤️ Temperatura esterna</span>
          <span class="font-medium tabular-nums">{fmt(sys.external_temp)}</span>
        </div>
        {sys.air_boost?.value ? (
          <div class="text-xs text-emerald-600">💨 boost aria attivo</div>
        ) : null}
      </div>

      {eu.zones.length === 0 ? (
        <div class={card + " text-xs text-gray-500"}>
          Nessuna zona configurata — usa “Cerca zone” nel tab Setup.
        </div>
      ) : (
        <div class="grid grid-cols-2 gap-3">
          {eu.zones.map((z) => {
            const r = z.readings;
            return (
              <div class={card} key={z.index}>
                <div class="flex items-baseline justify-between gap-1">
                  <div class="font-medium truncate text-sm">{z.name}</div>
                  {z.unit && (
                    <div class={"text-[10px] shrink-0 " + (UNIT_COLOR[z.unit] || "")}>
                      {z.unit === "comune" ? "comune" : names[z.unit] || z.unit}
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
                    <span class={lbl}>🎯 Setpoint</span>
                    <span class="text-sm tabular-nums">{fmt(r.setpoint)}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class={lbl}>💧 Umidità</span>
                    <span class="text-sm tabular-nums">{fmt(r.humidity)}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class={lbl}>⚙️ Modo</span>
                    <span class="text-sm">{r.mode.available ? r.mode.text : "—"}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
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
