import { useEffect, useState } from "preact/hooks";
import { get, post, del, upload, eur } from "../api.js";

const card = "rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4";
const btn = "px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm disabled:opacity-50";
const btnP = "px-3 py-1.5 rounded-lg bg-amber-500 text-white text-sm font-medium disabled:opacity-50";
const inp = "w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm";
const lbl = "text-xs text-gray-500 dark:text-gray-400";

const emptyForm = () => ({
  type: "electric", period_start: "", period_end: "",
  billed: "", cost_total: "", canone_rai: "", notes: "",
});

export function Bollette() {
  const [bills, setBills] = useState([]);
  const [cfg, setCfg] = useState({ andrea_name: "Andrea", genitori_name: "Genitori" });
  const [form, setForm] = useState(emptyForm());
  const [msg, setMsg] = useState({});      // per-bill message {id: {text, needImport}}
  const [busy, setBusy] = useState(null);
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState("");

  const load = () => get("api/bills").then(setBills).catch((e) => setErr(e.message));
  useEffect(() => {
    load();
    get("api/config").then((c) => {
      setCfg(c);
      setForm((f) => ({ ...f, canone_rai: c.canone_rai_default || "" }));
    });
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function add(e) {
    e.preventDefault();
    setErr("");
    try {
      await post("api/bills", {
        type: form.type,
        period_start: form.period_start,
        period_end: form.period_end,
        billed: parseFloat(form.billed),
        cost_total: parseFloat(form.cost_total),
        canone_rai: parseFloat(form.canone_rai) || 0,
        notes: form.notes || null,
      });
      setForm({ ...emptyForm(), canone_rai: cfg.canone_rai_default || "" });
      load();
    } catch (e2) { setErr(e2.message); }
  }

  async function compute(bill) {
    setBusy(bill.id);
    setMsg({ ...msg, [bill.id]: null });
    try {
      const r = await post(`api/bills/${bill.id}/compute`);
      if (r.ok) { await load(); setMsg({ ...msg, [bill.id]: { warnings: r.warnings } }); }
      else if (r.missing) setMsg({ ...msg, [bill.id]: { needImport: true, missing: r.missing } });
      else setMsg({ ...msg, [bill.id]: { error: r.error || "errore" } });
    } catch (e) { setMsg({ ...msg, [bill.id]: { error: e.message } }); }
    setBusy(null);
  }

  async function importAndCompute(bill) {
    setBusy(bill.id);
    try {
      const im = await post(`api/snapshots/import_history?from_=${bill.period_start}&to=${bill.period_end}`);
      setMsg({ ...msg, [bill.id]: { text: `Import: ${im.keys_imported}/${im.keys_total} sensori` } });
      await compute(bill);
    } catch (e) { setMsg({ ...msg, [bill.id]: { error: e.message } }); setBusy(null); }
  }

  async function pickPdf(bill, e) {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(bill.id);
    try { await upload(`api/bills/${bill.id}/pdf`, file); await load(); }
    catch (e2) { setMsg({ ...msg, [bill.id]: { error: e2.message } }); }
    setBusy(null);
  }

  return (
    <div class="space-y-4">
      <form class={card + " space-y-2"} onSubmit={add}>
        <div class="font-semibold">Nuova bolletta</div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <div class={lbl}>Tipo</div>
            <select class={inp} value={form.type} onChange={set("type")}>
              <option value="electric">Luce</option>
              <option value="gas">Gas</option>
            </select>
          </div>
          <div>
            <div class={lbl}>{form.type === "gas" ? "Smc fatturati" : "kWh fatturati"}</div>
            <input class={inp} type="number" step="0.01" value={form.billed} onInput={set("billed")} required />
          </div>
          <div>
            <div class={lbl}>Dal</div>
            <input class={inp} type="date" value={form.period_start} onInput={set("period_start")} required />
          </div>
          <div>
            <div class={lbl}>Al</div>
            <input class={inp} type="date" value={form.period_end} onInput={set("period_end")} required />
          </div>
          <div>
            <div class={lbl}>Costo totale €</div>
            <input class={inp} type="number" step="0.01" value={form.cost_total} onInput={set("cost_total")} required />
          </div>
          {form.type === "electric" && (
            <div>
              <div class={lbl}>Canone RAI €</div>
              <input class={inp} type="number" step="0.01" value={form.canone_rai} onInput={set("canone_rai")} />
            </div>
          )}
        </div>
        <input class={inp} placeholder="Note (opzionale)" value={form.notes} onInput={set("notes")} />
        <button class={btnP} type="submit">Aggiungi</button>
        {err && <div class="text-red-600 text-sm">{err}</div>}
      </form>

      {bills.length === 0 && <p class="text-center text-gray-500 py-6">Nessuna bolletta.</p>}

      {bills.map((b) => (
        <div class={card} key={b.id}>
          <div class="flex items-center justify-between">
            <div>
              <span class="text-lg mr-1">{b.type === "gas" ? "🔥" : "⚡"}</span>
              <span class="font-medium">{b.period_start} → {b.period_end}</span>
            </div>
            <div class="text-sm text-gray-500">
              {b.billed} {b.type === "gas" ? "Smc" : "kWh"} · {eur(b.cost_total)}
            </div>
          </div>

          {b.andrea_amount != null && (
            <div class="grid grid-cols-2 gap-2 mt-3">
              <div class="rounded-lg bg-amber-50 dark:bg-amber-950/40 p-3 text-center">
                <div class={lbl}>{cfg.andrea_name}</div>
                <div class="text-xl font-semibold text-amber-700 dark:text-amber-300">{eur(b.andrea_amount)}</div>
                <div class="text-xs text-gray-500">{b.andrea_qty} {b.type === "gas" ? "Smc" : "kWh"}</div>
              </div>
              <div class="rounded-lg bg-sky-50 dark:bg-sky-950/40 p-3 text-center">
                <div class={lbl}>{cfg.genitori_name}</div>
                <div class="text-xl font-semibold text-sky-700 dark:text-sky-300">{eur(b.genitori_amount)}</div>
                <div class="text-xs text-gray-500">{b.genitori_qty} {b.type === "gas" ? "Smc" : "kWh"}</div>
              </div>
            </div>
          )}

          <div class="flex flex-wrap gap-2 mt-3 items-center">
            <button class={btnP} disabled={busy === b.id} onClick={() => compute(b)}>
              {busy === b.id ? "…" : "Calcola"}
            </button>
            <label class={btn + " cursor-pointer"}>
              {b.pdf_path ? "Sostituisci PDF" : "Allega PDF"}
              <input type="file" accept="application/pdf" class="hidden" onChange={(e) => pickPdf(b, e)} />
            </label>
            {b.pdf_path && <a class={btn} href={`api/bills/${b.id}/pdf`} target="_blank">Apri PDF</a>}
            {b.breakdown && (
              <button class={btn} onClick={() => setOpen(open === b.id ? null : b.id)}>Dettaglio</button>
            )}
            <button class={btn + " ml-auto text-red-600"} onClick={() => del(`api/bills/${b.id}`).then(load)}>Elimina</button>
          </div>

          {msg[b.id]?.needImport && (
            <div class="mt-2 text-sm">
              <div class="text-amber-600 mb-1">Mancano gli snapshot per questo periodo.</div>
              <button class={btnP} disabled={busy === b.id} onClick={() => importAndCompute(b)}>
                Importa storico HA e ricalcola
              </button>
            </div>
          )}
          {msg[b.id]?.text && <div class="mt-2 text-sm text-gray-500">{msg[b.id].text}</div>}
          {msg[b.id]?.error && <div class="mt-2 text-sm text-red-600">{msg[b.id].error}</div>}
          {msg[b.id]?.warnings?.length > 0 && (
            <div class="mt-2 text-sm text-amber-600">⚠ {msg[b.id].warnings.join("; ")}</div>
          )}

          {open === b.id && b.breakdown && <Breakdown bd={b.breakdown} />}
        </div>
      ))}
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div class="flex justify-between border-b border-gray-100 dark:border-gray-800 py-1">
      <span class="text-gray-500">{k}</span><span>{v}</span>
    </div>
  );
}

function Breakdown({ bd }) {
  const d = bd.diagnostics || {};
  return (
    <div class="mt-3 text-sm rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3">
      {bd.type === "electric" ? (
        <>
          <Row k="Carico lordo L (prelievo+autoconsumo)" v={`${bd.L} kWh`} />
          <Row k="Appartamento Andrea (A_app)" v={`${bd.A_app} kWh`} />
          <Row k="Bucket condiviso S = L − A_app" v={`${bd.S} kWh`} />
          <Row k="Quota Zenner Andrea (f_a)" v={bd.f_andrea} />
          <Row k="Zenner Andrea / Genitori" v={`${bd.zenner_andrea} / ${bd.zenner_genitori} kWh`} />
          <Row k="Prezzo medio" v={`€ ${bd.price_eur_kwh}/kWh`} />
          <Row k="Canone RAI (→ Andrea)" v={eur(bd.canone_rai)} />
          <div class="mt-2 text-xs text-gray-500">Diagnostica</div>
          <Row k="Prelievo − fatturato" v={`${d.imp_minus_billed} kWh`} />
          <Row k="Produzione − (export+autocons.)" v={d.production_residual == null ? "n/d" : `${d.production_residual} kWh`} />
          <Row k="Carichi non misurati" v={d.unmetered_load == null ? "n/d" : `${d.unmetered_load} kWh`} />
        </>
      ) : (
        <>
          <Row k="Quota Zenner Andrea (f_a)" v={bd.f_andrea} />
          <Row k="Zenner Andrea / Genitori" v={`${bd.zenner_andrea} / ${bd.zenner_genitori} kWh`} />
          <Row k="Smc fatturati" v={bd.billed_smc} />
        </>
      )}
    </div>
  );
}
