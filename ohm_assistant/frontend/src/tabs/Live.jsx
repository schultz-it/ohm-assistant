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

      <div class="text-center text-xs text-gray-400">
        {err ? <span class="text-red-500">errore aggiornamento</span>
             : ts && `aggiornato ${ts.toLocaleTimeString("it-IT")}`} · ogni 5s
      </div>
    </div>
  );
}
