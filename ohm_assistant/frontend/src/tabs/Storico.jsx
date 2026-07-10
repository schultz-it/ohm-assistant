import { useEffect, useState } from "preact/hooks";
import { get, put, eur } from "../api.js";

const card = "rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4";
const lbl = "text-xs text-gray-500 dark:text-gray-400";

const monthLabel = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString("it-IT", { month: "short", year: "2-digit" });

export function Storico() {
  const [bills, setBills] = useState([]);
  const [sum, setSum] = useState(null);

  const load = () =>
    Promise.all([get("api/bills"), get("api/stats/summary")]).then(([b, s]) => {
      setBills(b.filter((x) => x.andrea_amount != null)
                .sort((a, c) => a.period_start.localeCompare(c.period_start)));
      setSum(s);
    });
  useEffect(() => { load(); }, []);

  if (!sum) return <p class="text-center text-gray-500 py-6">Caricamento…</p>;
  if (sum.count === 0)
    return <div class="text-center text-gray-500 py-10">
      <div class="text-4xl mb-2">📊</div>Nessuna bolletta calcolata. Calcola una bolletta nella tab Bollette.
    </div>;

  const names = sum.names;
  const maxTotal = Math.max(...bills.map((b) => b.cost_total), 1);

  async function toggle(b) {
    await put(`api/bills/${b.id}`, { settled: !b.settled });
    load();
  }

  return (
    <div class="space-y-4">
      <div class={card + " text-center"}>
        <div class={lbl}>{names.genitori} devono a {names.andrea}</div>
        <div class="text-3xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
          {eur(sum.outstanding_genitori_to_andrea)}
        </div>
        <div class="text-xs text-gray-400 mt-1">saldo delle bollette non ancora saldate</div>
      </div>

      <div class="grid grid-cols-3 gap-2">
        <Stat label={names.andrea} value={eur(sum.totals.andrea)} color="text-amber-600" />
        <Stat label={names.genitori} value={eur(sum.totals.genitori)} color="text-sky-600" />
        <Stat label="Bollette" value={sum.count} />
      </div>

      <div class={card}>
        <div class="font-semibold mb-3">Andamento</div>
        <div class="space-y-2">
          {bills.map((b) => {
            const w = (b.cost_total / maxTotal) * 100;
            const aPct = (b.andrea_amount / b.cost_total) * 100;
            return (
              <div key={b.id} class="flex items-center gap-2 text-xs">
                <span class="w-14 shrink-0 text-gray-500">{monthLabel(b.period_start)}</span>
                <div class="flex-1 h-5 rounded bg-gray-100 dark:bg-gray-800 overflow-hidden">
                  <div class="h-full flex" style={`width:${w}%`}>
                    <div class="bg-amber-500 h-full" style={`width:${aPct}%`} />
                    <div class="bg-sky-500 h-full" style={`width:${100 - aPct}%`} />
                  </div>
                </div>
                <span class="w-16 shrink-0 text-right tabular-nums">{eur(b.cost_total)}</span>
                <span>{b.type === "gas" ? "🔥" : "⚡"}</span>
              </div>
            );
          })}
        </div>
        <div class="flex gap-4 text-xs mt-3">
          <span class="text-amber-600">■ {names.andrea}</span>
          <span class="text-sky-600">■ {names.genitori}</span>
        </div>
      </div>

      <div class={card}>
        <div class="font-semibold mb-2">Dettaglio</div>
        <div class="space-y-2">
          {bills.map((b) => (
            <div key={b.id} class="flex items-center justify-between text-sm border-b border-gray-100 dark:border-gray-800 pb-2">
              <div>
                <div class="font-medium">{b.type === "gas" ? "🔥" : "⚡"} {monthLabel(b.period_start)}</div>
                <div class="text-xs text-gray-500">
                  {names.andrea} {eur(b.andrea_amount)} · {names.genitori} {eur(b.genitori_amount)}
                  {b.type === "electric" && b.breakdown?.price_eur_kwh
                    ? ` · ${b.breakdown.price_eur_kwh} €/kWh` : ""}
                </div>
              </div>
              <label class="flex items-center gap-1 text-xs shrink-0">
                <input type="checkbox" checked={b.settled} onChange={() => toggle(b)} />
                Saldato
              </label>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div class={card + " text-center py-3"}>
      <div class="text-xs text-gray-500 truncate">{label}</div>
      <div class={"text-base font-semibold " + (color || "")}>{value}</div>
    </div>
  );
}
