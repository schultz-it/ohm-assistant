import { useEffect, useRef, useState } from "preact/hooks";
import { get, post, put } from "../api.js";

const card = "rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4";
const btnP = "px-3 py-1.5 rounded-lg bg-amber-500 text-white text-sm font-medium disabled:opacity-50";
const btn = "px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm disabled:opacity-50";
const inp = "w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm";
const inpAuto = inp.replace("w-full ", "");
const lbl = "text-xs text-gray-500 dark:text-gray-400";

const UNITS = [
  { v: "", label: "—" },
  { v: "andrea", label: "Unità 1" },
  { v: "genitori", label: "Unità 2" },
  { v: "comune", label: "Comune" },
];
const SCALES = [
  { v: 1, label: "×1" },
  { v: 0.1, label: "×0,1" },
  { v: 0.01, label: "×0,01" },
];

// Dove finisce un registro fissato: sistema, una Smart Base o la sua macchina aria.
function groupOptions(bases) {
  return [
    { v: "sistema", label: "Sistema" },
    ...bases.map((b) => ({ v: `base:${b.id}`, label: `Base ${b.id + 1} — ${b.name}` })),
    ...bases.map((b) => ({
      v: `air:${b.id}`,
      label: `Aria ${b.id + 1}${b.air_model ? " — " + b.air_model : ""}`,
    })),
  ];
}

/**
 * Setup del regolatore Eurotherm SmartComfort 365: connessione, rilevamento
 * dell'impianto (zone → Smart Base → stanze), esploratore dei registri e
 * parametri fissati nel cruscotto Live.
 */
export function EurothermSetup() {
  const [eu, setEu] = useState(null);
  const [meta, setMeta] = useState(null);
  const [adv, setAdv] = useState(false);
  const [msg, setMsg] = useState("");
  const [test, setTest] = useState(null);
  const [busy, setBusy] = useState("");

  // Esploratore
  const [range, setRange] = useState({ start: 50, count: 256 });
  const [rows, setRows] = useState(null);
  const [onlyChanged, setOnlyChanged] = useState(false);
  const [hideZeros, setHideZeros] = useState(false);
  const [pin, setPin] = useState(null);
  const prev = useRef(new Map());

  // Mappa del dispositivo
  const [mapRes, setMapRes] = useState(null);
  const [mapProgress, setMapProgress] = useState("");

  const reload = () => Promise.all([
    get("api/eurotherm/config").then(setEu),
    get("api/eurotherm/registers").then(setMeta),
  ]).catch(() => {});

  useEffect(() => { reload(); }, []);
  if (!eu) return null;

  const field = (k) => (e) => setEu({ ...eu, [k]: e.target.value });
  const setBase = (i, patch) =>
    setEu({ ...eu, bases: eu.bases.map((b, j) => (j === i ? { ...b, ...patch } : b)) });
  const setRoom = (i, patch) =>
    setEu({ ...eu, rooms: eu.rooms.map((r, j) => (j === i ? { ...r, ...patch } : r)) });

  const payload = (over = {}) => ({
    enabled: eu.enabled, host: eu.host.trim(), port: +eu.port || 502,
    unit_id: +eu.unit_id, input_type: eu.input_type,
    poll_interval: +eu.poll_interval || 30,
    bases: eu.bases.map((b) => ({
      id: +b.id, name: b.name || `Smart Base ${+b.id + 1}`, unit: b.unit || null,
      enabled: !!b.enabled, air_model: b.air_model || "",
    })),
    rooms: eu.rooms.map((r) => ({
      base: +r.base, room: +r.room, name: r.name || `Stanza ${+r.room + 1}`,
      enabled: !!r.enabled, unit: r.unit || null,
    })),
    custom: eu.custom.map((c) => ({
      address: +c.address, name: c.name, group: c.group,
      scale: +c.scale, unit: c.unit || "", kind: c.kind || "number",
    })),
    ...over,
  });

  async function save(quiet, over) {
    if (!quiet) setMsg("…");
    const saved = await put("api/eurotherm/config", payload(over));
    setEu(saved);
    if (!quiet) { setMsg("Salvato"); setTimeout(() => setMsg(""), 2500); }
    return saved;
  }

  async function runTest() {
    setBusy("test"); setTest(null);
    try {
      await save(true);                       // prova esattamente ciò che vedi
      const r = await post("api/eurotherm/test");
      setTest(r.ok
        ? { ok: true, note: `esterna ${r.system.external_temp.value} °C · `
            + `${r.system.subsystem_count.value} zone` }
        : { ok: false, error: r.error });
    } catch (e) { setTest({ ok: false, error: e.message }); }
    setBusy("");
  }

  // Legge la topologia dal regolatore: zone → Smart Base → stanze.
  async function discover() {
    setBusy("discover"); setTest(null);
    try {
      await save(true);
      const d = await post("api/eurotherm/discover");
      if (!d.ok) { setTest({ ok: false, error: d.error }); setBusy(""); return; }
      const bases = d.bases.map((b) => ({
        id: b.id, name: b.name, unit: b.unit || "", enabled: b.enabled,
        air_model: b.air_model || "",
      }));
      const rooms = d.bases.flatMap((b) => b.rooms.map((r) => ({
        base: b.id, room: r.room, name: r.name, enabled: r.enabled,
        unit: r.unit || "",
      })));
      setEu(await save(true, {
        bases: bases.map((b) => ({ ...b, unit: b.unit || null })),
        rooms: rooms.map((r) => ({ ...r, unit: r.unit || null })),
      }));
      await get("api/eurotherm/registers").then(setMeta);
      setTest({ ok: true, note: `${bases.length} Smart Base, ${rooms.length} stanze` });
    } catch (e) { setTest({ ok: false, error: e.message }); }
    setBusy("");
  }

  async function explore(start, count) {
    setBusy("explore"); setPin(null);
    setRange({ start, count });
    try {
      await save(true);
      const r = await post("api/eurotherm/explore", { start, count });
      const next = (r.registers || []).map((x) => ({
        ...x,
        changed: prev.current.has(x.address) && prev.current.get(x.address) !== x.raw,
      }));
      prev.current = new Map(next.map((x) => [x.address, x.raw]));
      setRows({ ...r, registers: next });
    } catch (e) { setRows({ ok: false, error: e.message, registers: [] }); }
    setBusy("");
  }

  // Sonda l'intervallo a più riprese finché il backend non ha finito.
  async function runMap(preset) {
    setBusy("map"); setMapRes(null); setMapProgress("…");
    const islands = [];
    let start = preset.start;
    try {
      await save(true);
      for (let pass = 0; pass < 40; pass++) {
        const r = await post("api/eurotherm/map", {
          start, end: preset.end, stride: 8, max_probes: 2000,
        });
        if (!r.ok) { setMapRes({ ok: false, error: r.error, islands }); break; }
        islands.push(...r.islands);
        setMapProgress(`letto fino a ${r.next_start ?? preset.end} · `
          + `${islands.length} zone trovate`);
        if (r.next_start == null) { setMapRes({ ok: true, islands }); break; }
        start = r.next_start;
        if (pass === 39) setMapRes({ ok: true, islands, partial: true });
      }
    } catch (e) { setMapRes({ ok: false, error: e.message, islands }); }
    setMapProgress(""); setBusy("");
  }

  async function addPin() {
    const custom = [...eu.custom, {
      address: +pin.address, name: pin.name || `Registro ${pin.address}`,
      group: pin.group, scale: +pin.scale, unit: pin.unit, kind: pin.kind,
    }];
    setPin(null);
    await save(true, { custom });
    setMsg("Fissato nel Live"); setTimeout(() => setMsg(""), 2500);
  }

  const removePin = (i) =>
    save(true, { custom: eu.custom.filter((_, j) => j !== i) });

  const groups = groupOptions(eu.bases);
  const visible = (rows?.registers || []).filter(
    (r) => (!onlyChanged || r.changed) && (!hideZeros || r.raw !== 0));

  return (
    <div class={card + " space-y-3"}>
      <div class="flex items-center justify-between">
        <div class="font-semibold">🏠 Clima Eurotherm (SmartComfort 365)</div>
        <label class="text-xs flex items-center gap-1.5">
          <input type="checkbox" checked={eu.enabled}
            onChange={(e) => setEu({ ...eu, enabled: e.target.checked })} />
          attivo
        </label>
      </div>
      <p class="text-xs text-gray-500">
        Un solo SmartControl365 risponde per tutto l'impianto: stesso IP, Smart
        Base e stanze distinte dagli indirizzi dei registri. Sola lettura — Ohm
        Assistant non scrive mai setpoint o modalità.
      </p>

      <div class="grid grid-cols-2 gap-2">
        <div class="col-span-2"><div class={lbl}>Indirizzo IP</div>
          <input class={inp} placeholder="192.168.1.25" value={eu.host}
            onInput={field("host")} /></div>
        <div><div class={lbl}>Porta</div>
          <input class={inp} type="number" value={eu.port} onInput={field("port")} /></div>
        <div><div class={lbl}>Unit/slave id</div>
          <input class={inp} type="number" value={eu.unit_id} onInput={field("unit_id")} /></div>
        <div><div class={lbl}>Aggiornamento (s)</div>
          <input class={inp} type="number" min="5" value={eu.poll_interval}
            onInput={field("poll_interval")} /></div>
      </div>

      <div class="flex items-center gap-2 flex-wrap">
        <button class={btn} disabled={busy} onClick={runTest}>
          {busy === "test" ? "…" : "Prova connessione"}
        </button>
        <button class={btn} disabled={busy} onClick={discover}>
          {busy === "discover" ? "Rilevo…" : "Rileva impianto"}
        </button>
        {test && (test.ok
          ? <span class="text-xs text-emerald-600">{test.note || "regolatore raggiunto"}</span>
          : <span class="text-xs text-red-600">{test.error}</span>)}
      </div>

      {/* ---- Smart Base + macchina aria ---- */}
      <div class="space-y-2">
        <div class="text-sm font-medium">Smart Base e unità aria</div>
        {eu.bases.map((b, i) => (
          <div class="space-y-1" key={b.id}>
            <div class="flex items-center gap-2">
              <input type="checkbox" checked={b.enabled}
                onChange={(e) => setBase(i, { enabled: e.target.checked })} />
              <span class="text-xs text-gray-400 w-5 tabular-nums">#{b.id + 1}</span>
              <input class={inpAuto + " flex-1 min-w-0"} value={b.name}
                placeholder={`Smart Base ${b.id + 1}`}
                onInput={(e) => setBase(i, { name: e.target.value })} />
              <select class={inpAuto + " w-24 shrink-0"} value={b.unit || ""}
                onInput={(e) => setBase(i, { unit: e.target.value })}>
                {UNITS.map((u) => <option value={u.v} key={u.v}>{u.label}</option>)}
              </select>
            </div>
            <div class="flex items-center gap-2 pl-9">
              <span class={lbl + " shrink-0"}>🌬️ aria</span>
              <select class={inpAuto + " flex-1 min-w-0"} value={b.air_model}
                onInput={(e) => setBase(i, { air_model: e.target.value })}>
                {(meta?.air_models || [""]).map((m) => (
                  <option value={m} key={m}>{m || "senza macchina aria"}</option>
                ))}
              </select>
            </div>
          </div>
        ))}
        <div class="text-xs text-gray-500">
          Ogni Smart Base espone mandata, setpoint di mandata, tipo di base e
          stato dei sensori; le stanze sono lette in blocco sotto ciascuna.
        </div>
      </div>

      {/* ---- Stanze ---- */}
      {eu.rooms.length > 0 && eu.bases.map((b) => {
        const rows_ = eu.rooms.map((r, i) => ({ r, i })).filter(({ r }) => +r.base === +b.id);
        if (!rows_.length) return null;
        return (
          <div class="space-y-1" key={"rooms" + b.id}>
            <div class="text-sm font-medium">Stanze — {b.name}</div>
            {rows_.map(({ r, i }) => (
              <div class="flex items-center gap-2" key={`${r.base}.${r.room}`}>
                <input type="checkbox" checked={r.enabled}
                  onChange={(e) => setRoom(i, { enabled: e.target.checked })} />
                <span class="text-xs text-gray-400 w-5 tabular-nums">#{r.room + 1}</span>
                <input class={inpAuto + " flex-1 min-w-0"} value={r.name}
                  onInput={(e) => setRoom(i, { name: e.target.value })} />
                <select class={inpAuto + " w-24 shrink-0"} value={r.unit || ""}
                  onInput={(e) => setRoom(i, { unit: e.target.value })}>
                  {UNITS.map((u) => <option value={u.v} key={u.v}>{u.label}</option>)}
                </select>
              </div>
            ))}
          </div>
        );
      })}

      {/* ---- Registri fissati nel Live ---- */}
      {eu.custom.length > 0 && (
        <div class="space-y-1">
          <div class="text-sm font-medium">📌 Parametri nel Live</div>
          {eu.custom.map((c, i) => (
            <div class="flex items-center justify-between text-xs" key={c.address + c.name}>
              <span class="truncate">
                <span class="font-mono text-gray-400">{c.address}</span> {c.name}
                <span class="text-gray-400">
                  {" · "}{groups.find((g) => g.v === c.group)?.label || c.group}
                </span>
              </span>
              <button class="text-gray-400 px-1 shrink-0" onClick={() => removePin(i)}>✕</button>
            </div>
          ))}
        </div>
      )}

      {/* ---- Esploratore registri ---- */}
      <div class="space-y-2 border-t border-gray-200 dark:border-gray-800 pt-3">
        <div class="text-sm font-medium">🔎 Esplora registri</div>
        <p class="text-xs text-gray-500">
          Il protocollo documenta sistema, zone, Smart Base e stanze — non le
          macchine aria. Leggi un intervallo, guarda quali valori si muovono e
          fissa nel Live quelli che riconosci.
        </p>
        <div class="flex gap-1.5 flex-wrap">
          {(meta?.presets || []).map((p) => (
            <button class={btn} key={p.key} disabled={busy}
              title={p.hint} onClick={() => explore(p.start, p.count)}>
              {p.label}
            </button>
          ))}
        </div>
        <div class="space-y-1.5 border-l-2 border-gray-200 dark:border-gray-800 pl-2">
          <div class="text-xs text-gray-500">
            Non sai dove guardare? La <b>mappa</b> sonda lo spazio indirizzi e
            elenca le zone di registri che il regolatore espone davvero: quello
            che compare fuori dai blocchi documentati è un candidato per le
            macchine aria.
          </div>
          <div class="flex gap-1.5 flex-wrap">
            {(meta?.map_presets || []).map((p) => (
              <button class={btn} key={p.key} disabled={busy}
                title={p.hint} onClick={() => runMap(p)}>
                🗺️ {p.label}
              </button>
            ))}
          </div>
          {mapProgress && <div class="text-xs text-gray-500">{mapProgress}</div>}
          {mapRes && !mapRes.ok && (
            <div class="text-xs text-red-600">{mapRes.error}</div>
          )}
          {mapRes && (
            mapRes.islands.length === 0 ? (
              <div class="text-xs text-gray-500">
                nessun registro in questo intervallo
              </div>
            ) : (
              <div class="space-y-0.5">
                {mapRes.islands.map((z) => (
                  <button key={z.start}
                    class={"flex justify-between w-full text-xs px-1 py-0.5 rounded "
                      + (z.documented ? "text-gray-500"
                                      : "text-emerald-700 dark:text-emerald-400 font-medium")}
                    onClick={() => explore(z.start, Math.min(z.count, 2048))}>
                    <span class="font-mono">{z.start}–{z.end}</span>
                    <span class="truncate ml-2">
                      {z.known || (z.documented ? "" : "non documentato")}
                      <span class="text-gray-400"> · {z.count} reg.</span>
                    </span>
                  </button>
                ))}
              </div>
            )
          )}
        </div>

        <div class="flex items-end gap-2">
          <div><div class={lbl}>Da</div>
            <input class={inpAuto + " w-24"} type="number" value={range.start}
              onInput={(e) => setRange({ ...range, start: +e.target.value })} /></div>
          <div><div class={lbl}>Quanti</div>
            <input class={inpAuto + " w-24"} type="number" value={range.count}
              onInput={(e) => setRange({ ...range, count: +e.target.value })} /></div>
          <button class={btnP} disabled={busy}
            onClick={() => explore(range.start, range.count)}>
            {busy === "explore" ? "Leggo…" : "Leggi"}
          </button>
          {rows && (
            <button class={btn} disabled={busy}
              onClick={() => explore(range.start, range.count)}>Rileggi</button>
          )}
        </div>

        {rows && !rows.ok && <div class="text-xs text-red-600">{rows.error}</div>}
        {rows && rows.ok && (
          <>
            <div class="flex items-center gap-3 text-xs flex-wrap">
              <label class="flex items-center gap-1">
                <input type="checkbox" checked={onlyChanged}
                  onChange={(e) => setOnlyChanged(e.target.checked)} />
                solo cambiati
              </label>
              <label class="flex items-center gap-1">
                <input type="checkbox" checked={hideZeros}
                  onChange={(e) => setHideZeros(e.target.checked)} />
                nascondi zeri
              </label>
              <span class="text-gray-400">
                {rows.registers.length} letti · {rows.unreadable.length} non disponibili
              </span>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-xs">
                <thead class="text-gray-500">
                  <tr>
                    <th class="text-left font-normal px-1">Reg.</th>
                    <th class="text-right font-normal px-1">valore</th>
                    <th class="text-right font-normal px-1">×0,1</th>
                    <th class="text-left font-normal px-1">note</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visible.map((r) => (
                    <tr key={r.address}
                      class={"border-t border-gray-100 dark:border-gray-800 " +
                        (r.changed ? "bg-amber-50 dark:bg-amber-950/40" : "")}>
                      <td class="px-1 font-mono tabular-nums">{r.address}</td>
                      <td class="px-1 text-right tabular-nums">{r.int16}</td>
                      <td class="px-1 text-right tabular-nums">{r.x0_1}</td>
                      <td class="px-1 text-gray-500 truncate max-w-[10rem]">{r.known || ""}</td>
                      <td class="px-1 text-right">
                        <button class="text-gray-400" title="Fissa nel Live"
                          onClick={() => setPin({
                            address: r.address, name: r.known || "",
                            group: "sistema", scale: 1, unit: "", kind: "number",
                          })}>📌</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visible.length === 0 && (
                <div class="text-xs text-gray-500 py-2">nessun registro da mostrare</div>
              )}
            </div>
          </>
        )}

        {pin && (
          <div class="rounded-lg border border-amber-300 dark:border-amber-800 p-2 space-y-2">
            <div class="text-xs">
              Fissa il registro <span class="font-mono">{pin.address}</span> nel Live
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="col-span-2"><div class={lbl}>Nome</div>
                <input class={inp} value={pin.name} placeholder="es. Portata aria"
                  onInput={(e) => setPin({ ...pin, name: e.target.value })} /></div>
              <div><div class={lbl}>Dove</div>
                <select class={inp} value={pin.group}
                  onInput={(e) => setPin({ ...pin, group: e.target.value })}>
                  {groups.map((g) => <option value={g.v} key={g.v}>{g.label}</option>)}
                </select></div>
              <div><div class={lbl}>Tipo</div>
                <select class={inp} value={pin.kind}
                  onInput={(e) => setPin({ ...pin, kind: e.target.value })}>
                  <option value="number">numero</option>
                  <option value="temp">temperatura (0,1 °C)</option>
                  <option value="bool">on/off</option>
                </select></div>
              <div><div class={lbl}>Scala</div>
                <select class={inp} value={pin.scale} disabled={pin.kind !== "number"}
                  onInput={(e) => setPin({ ...pin, scale: +e.target.value })}>
                  {SCALES.map((s) => <option value={s.v} key={s.v}>{s.label}</option>)}
                </select></div>
              <div><div class={lbl}>Unità di misura</div>
                <input class={inp} value={pin.unit} placeholder="°C, %, m³/h…"
                  onInput={(e) => setPin({ ...pin, unit: e.target.value })} /></div>
            </div>
            <div class="flex gap-2">
              <button class={btnP} onClick={addPin}>Fissa</button>
              <button class={btn} onClick={() => setPin(null)}>Annulla</button>
            </div>
          </div>
        )}
      </div>

      <button class="text-xs text-gray-500 underline" onClick={() => setAdv(!adv)}>
        {adv ? "Nascondi" : "Mostra"} mappa dei registri
      </button>
      {adv && meta && (
        <div class="text-xs text-gray-500 space-y-1">
          <div>
            <span class={lbl}>Tipo registri</span>{" "}
            <select class={inpAuto + " ml-1"} value={eu.input_type}
              onInput={field("input_type")}>
              <option value="holding">holding (FC3)</option>
              <option value="input">input (FC4)</option>
            </select>
          </div>
          <div>Sistema {meta.layout.system_base}–{meta.layout.system_base + 9};
            zona i → {meta.layout.zone_base} + i×{meta.layout.zone_stride};
            Smart Base b → {meta.layout.module_base} + b×{meta.layout.module_stride};
            stanza r → base + {meta.layout.room_offset} + r×{meta.layout.room_stride}
            ({meta.layout.rooms_per_module} per base).</div>
          {Object.entries(meta.addresses || {}).map(([name, a]) => (
            <div key={name}>
              <span class="font-medium">{name}</span>: base {a.base}, stanze{" "}
              {a.rooms.slice(0, 4).join(", ")}…
            </div>
          ))}
        </div>
      )}

      <div class="flex items-center gap-3">
        <button class={btnP} onClick={() => save(false)}>Salva clima</button>
        {msg && <span class="text-sm text-emerald-600">{msg}</span>}
      </div>
    </div>
  );
}
