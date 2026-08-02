import { useEffect, useMemo, useState } from "preact/hooks";
import { get, post, put, del, eur } from "../api.js";

const card = "rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4";
const btnP = "px-3 py-1.5 rounded-lg bg-amber-500 text-white text-sm font-medium disabled:opacity-50";
const inp = "w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm";
const lbl = "text-xs text-gray-500 dark:text-gray-400";

const today = () => new Date().toISOString().slice(0, 10);
const num = (v) => (v === "" || v == null ? 0 : parseFloat(v) || 0);
const r2 = (n) => Math.round(n * 100) / 100;

const MODES = [
  { id: "equal", label: "Metà" },
  { id: "percent", label: "Percentuali" },
  { id: "amount", label: "Cifre" },
];

const emptyForm = () => ({
  date: today(), description: "", amount: "", category: "",
  paid_by: "andrea", split_mode: "equal", pa: 50, aa: "", notes: "",
});

/** Shares previewed client-side; the server recomputes them authoritatively. */
function previewShares(form) {
  const amount = r2(num(form.amount));
  if (form.split_mode === "percent") {
    const a = r2((amount * num(form.pa)) / 100);
    return [a, r2(amount - a)];
  }
  if (form.split_mode === "amount") {
    const a = r2(num(form.aa));
    return [a, r2(amount - a)];
  }
  const a = r2(amount / 2);
  return [a, r2(amount - a)];
}

export function Spese() {
  const [items, setItems] = useState([]);
  const [sum, setSum] = useState(null);
  const [stats, setStats] = useState(null);
  const [cats, setCats] = useState([]);
  const [form, setForm] = useState(emptyForm());
  const [catTouched, setCatTouched] = useState(false);
  const [hint, setHint] = useState(null);   // category proposed from the description
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [showSettled, setShowSettled] = useState(false);

  const byId = useMemo(
    () => Object.fromEntries(cats.map((c) => [c.id, c])), [cats]);

  const load = () =>
    Promise.all([get("api/expenses"), get("api/expenses/summary"), get("api/stats/summary")])
      .then(([e, s, st]) => { setItems(e); setSum(s); setStats(st); })
      .catch((e) => setErr(e.message));

  useEffect(() => {
    load();
    get("api/expenses/categories").then((d) => setCats(d.categories)).catch(() => {});
  }, []);

  // Propose a category while typing (local keyword match, debounced).
  useEffect(() => {
    if (catTouched || !form.description.trim()) { setHint(null); return; }
    const t = setTimeout(() => {
      get(`api/expenses/suggest?description=${encodeURIComponent(form.description)}`)
        .then((r) => {
          setHint(r.matched ? r.category : null);
          if (r.matched) setForm((f) => ({ ...f, category: r.category }));
        })
        .catch(() => {});
    }, 350);
    return () => clearTimeout(t);
  }, [form.description, catTouched]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const [prevA, prevG] = previewShares(form);
  const names = sum?.names || { andrea: "Andrea", genitori: "Genitori" };

  async function add(e) {
    e.preventDefault();
    setErr(""); setBusy(true);
    const amount = r2(num(form.amount));
    const body = {
      date: form.date,
      description: form.description.trim(),
      amount,
      category: form.category || null,
      paid_by: form.paid_by,
      split_mode: form.split_mode,
      notes: form.notes || null,
    };
    if (form.split_mode === "percent")
      body.split_config = { andrea: num(form.pa), genitori: r2(100 - num(form.pa)) };
    if (form.split_mode === "amount")
      body.split_config = { andrea: r2(num(form.aa)), genitori: r2(amount - num(form.aa)) };
    try {
      await post("api/expenses", body);
      setForm(emptyForm()); setCatTouched(false); setHint(null);
      await load();
    } catch (e2) { setErr(e2.message); }
    setBusy(false);
  }

  async function toggle(x) {
    await put(`api/expenses/${x.id}`, { settled: !x.settled });
    load();
  }

  async function remove(x) {
    const q = x.bill_id
      ? "Togliere questa bolletta dal registro spese? La bolletta resta nella tab Bollette."
      : "Eliminare la spesa?";
    if (!confirm(q)) return;
    await del(`api/expenses/${x.id}`);
    load();
  }

  if (!sum) return <p class="text-center text-gray-500 py-6">Caricamento…</p>;

  const net = stats?.outstanding_genitori_to_andrea ?? sum.net;
  const debtor = net >= 0 ? names.genitori : names.andrea;
  const creditor = net >= 0 ? names.andrea : names.genitori;
  const visible = items.filter((x) => showSettled || !x.settled);

  return (
    <div class="space-y-4">
      <div class={card + " text-center"}>
        {Math.abs(net) < 0.005 ? (
          <>
            <div class={lbl}>Siete in pari</div>
            <div class="text-3xl font-bold text-gray-400 mt-1">{eur(0)}</div>
          </>
        ) : (
          <>
            {/* Arrow instead of a verb: either unit can be the debtor. */}
            <div class={lbl}>Saldo · {debtor} → {creditor}</div>
            <div class="text-3xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
              {eur(Math.abs(net))}
            </div>
          </>
        )}
        <div class="text-xs text-gray-400 mt-1">
          spese {eur(Math.abs(sum.net))}
          {stats && Math.abs(stats.outstanding_bills) >= 0.005 &&
            ` · bollette non in registro ${eur(stats.outstanding_bills)}`}
        </div>
      </div>

      <form class={card + " space-y-2"} onSubmit={add}>
        <div class="font-semibold">Nuova spesa</div>

        <input class={inp} placeholder="Descrizione (es. idraulico, TARI, giardiniere)"
               value={form.description} onInput={set("description")} required />

        <div class="grid grid-cols-2 gap-2">
          <div>
            <div class={lbl}>Importo €</div>
            <input class={inp} type="number" step="0.01" min="0.01" value={form.amount}
                   onInput={set("amount")} required />
          </div>
          <div>
            <div class={lbl}>Data</div>
            <input class={inp} type="date" value={form.date} onInput={set("date")} required />
          </div>
        </div>

        <div>
          <div class={lbl}>
            Categoria
            {hint && !catTouched && <span class="text-emerald-600"> · proposta automatica</span>}
          </div>
          <select class={inp} value={form.category}
                  onChange={(e) => { setCatTouched(true); setForm({ ...form, category: e.target.value }); }}>
            <option value="">— proponi tu —</option>
            {cats.map((c) => (
              <option key={c.id} value={c.id}>{c.icon} {c.label}</option>
            ))}
          </select>
        </div>

        <div>
          <div class={lbl}>Pagato da</div>
          <div class="flex gap-2">
            {["andrea", "genitori"].map((p) => (
              <button key={p} type="button"
                      onClick={() => setForm({ ...form, paid_by: p })}
                      class={`flex-1 py-1.5 rounded-lg text-sm border ${
                        form.paid_by === p
                          ? "bg-amber-500 text-white border-amber-500"
                          : "border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"}`}>
                {names[p]}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div class={lbl}>Come dividere</div>
          <div class="flex gap-2">
            {MODES.map((m) => (
              <button key={m.id} type="button"
                      onClick={() => setForm({ ...form, split_mode: m.id })}
                      class={`flex-1 py-1.5 rounded-lg text-sm border ${
                        form.split_mode === m.id
                          ? "bg-gray-900 text-white border-gray-900 dark:bg-gray-100 dark:text-gray-900"
                          : "border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"}`}>
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {form.split_mode === "percent" && (
          <div class="grid grid-cols-2 gap-2">
            <div>
              <div class={lbl}>{names.andrea} %</div>
              <input class={inp} type="number" step="1" min="0" max="100" value={form.pa}
                     onInput={(e) => setForm({ ...form, pa: num(e.target.value) })} />
            </div>
            <div>
              <div class={lbl}>{names.genitori} %</div>
              <input class={inp} type="number" step="1" min="0" max="100"
                     value={r2(100 - num(form.pa))}
                     onInput={(e) => setForm({ ...form, pa: r2(100 - num(e.target.value)) })} />
            </div>
          </div>
        )}

        {form.split_mode === "amount" && (
          <div class="grid grid-cols-2 gap-2">
            <div>
              <div class={lbl}>{names.andrea} €</div>
              <input class={inp} type="number" step="0.01" min="0" value={form.aa}
                     onInput={(e) => setForm({ ...form, aa: e.target.value })} />
            </div>
            <div>
              <div class={lbl}>{names.genitori} €</div>
              <input class={inp} type="number" step="0.01" min="0"
                     value={r2(num(form.amount) - num(form.aa))}
                     onInput={(e) => setForm({ ...form, aa: r2(num(form.amount) - num(e.target.value)) })} />
            </div>
          </div>
        )}

        <div class="grid grid-cols-2 gap-2 pt-1">
          <div class="rounded-lg bg-amber-50 dark:bg-amber-950/40 p-2 text-center">
            <div class={lbl}>{names.andrea}</div>
            <div class="font-semibold text-amber-700 dark:text-amber-300">{eur(prevA)}</div>
          </div>
          <div class="rounded-lg bg-sky-50 dark:bg-sky-950/40 p-2 text-center">
            <div class={lbl}>{names.genitori}</div>
            <div class="font-semibold text-sky-700 dark:text-sky-300">{eur(prevG)}</div>
          </div>
        </div>

        <input class={inp} placeholder="Note (opzionale)" value={form.notes} onInput={set("notes")} />
        <button class={btnP} type="submit" disabled={busy}>{busy ? "…" : "Aggiungi spesa"}</button>
        {err && <div class="text-red-600 text-sm">{err}</div>}
      </form>

      <div class="flex items-center justify-between">
        <div class="font-semibold">Spese</div>
        <label class="flex items-center gap-1 text-xs text-gray-500">
          <input type="checkbox" checked={showSettled}
                 onChange={() => setShowSettled(!showSettled)} />
          Mostra saldate
        </label>
      </div>

      {visible.length === 0 && (
        <div class="text-center text-gray-500 py-10">
          <div class="text-4xl mb-2">🧮</div>
          {items.length ? "Nessuna spesa da saldare." : "Nessuna spesa registrata."}
        </div>
      )}

      {visible.map((x) => {
        const c = byId[x.category] || { icon: "📌", label: x.category };
        const owed = x.paid_by === "andrea" ? x.genitori_share : x.andrea_share;
        const who = x.paid_by === "andrea" ? names.genitori : names.andrea;
        return (
          <div class={card + (x.settled ? " opacity-60" : "")} key={x.id}>
            <div class="flex items-baseline justify-between gap-2">
              <div class="font-medium min-w-0 truncate">
                <span class="mr-1">{c.icon}</span>{x.description}
                {x.bill_id && <span class="ml-1 text-xs text-gray-400">🧾</span>}
              </div>
              <div class="font-semibold shrink-0">{eur(x.amount)}</div>
            </div>
            <div class="text-xs text-gray-500 mt-0.5">
              {x.date} · {c.label} · pagato da {names[x.paid_by]}
            </div>
            <div class="text-xs text-gray-500">
              {names.andrea} {eur(x.andrea_share)} · {names.genitori} {eur(x.genitori_share)}
            </div>
            {x.notes && <div class="text-xs text-gray-500 mt-1">{x.notes}</div>}
            <div class="flex items-center gap-3 mt-2">
              <span class="text-xs text-gray-500">
                {x.settled ? "saldata" : `${who} ${eur(owed)} da saldare`}
              </span>
              <label class="flex items-center gap-1 text-xs ml-auto">
                <input type="checkbox" checked={x.settled} onChange={() => toggle(x)} />
                Saldata
              </label>
              <button class="text-xs text-red-600" onClick={() => remove(x)}>Elimina</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
