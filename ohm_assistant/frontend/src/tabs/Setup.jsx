import { useEffect, useState } from "preact/hooks";
import { get, post, put } from "../api.js";

const card = "rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4";
const btnP = "px-3 py-1.5 rounded-lg bg-amber-500 text-white text-sm font-medium disabled:opacity-50";
const btn = "px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm";
const inp = "w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm";
const lbl = "text-xs text-gray-500 dark:text-gray-400";
// Same look as `inp` but width-free, for inputs sized by their flex container.
const inpAuto = inp.replace("w-full ", "");

const UNITS = [
  { v: "", label: "—" },
  { v: "andrea", label: "Unità 1" },
  { v: "genitori", label: "Unità 2" },
  { v: "comune", label: "Comune" },
];

// Eurotherm Smart365: il regolatore clima parla Modbus TCP, l'add-on lo legge
// direttamente (sola lettura), senza passare da Home Assistant.
function EurothermSetup() {
  const [eu, setEu] = useState(null);
  const [adv, setAdv] = useState(false);
  const [msg, setMsg] = useState("");
  const [test, setTest] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => { get("api/eurotherm/config").then(setEu).catch(() => {}); }, []);
  if (!eu) return null;

  const field = (k, cast = (x) => x) => (e) => setEu({ ...eu, [k]: cast(e.target.value) });
  const setZone = (i, patch) =>
    setEu({ ...eu, zones: eu.zones.map((z, j) => (j === i ? { ...z, ...patch } : z)) });

  const payload = () => ({
    enabled: eu.enabled, host: eu.host.trim(), port: +eu.port || 502,
    unit_id: +eu.unit_id, input_type: eu.input_type,
    poll_interval: +eu.poll_interval || 30,
    zone_base: +eu.zone_base, zone_stride: +eu.zone_stride,
    zones: eu.zones.map((z) => ({
      index: +z.index, name: z.name || `Zona ${z.index}`,
      enabled: !!z.enabled, unit: z.unit || null,
    })),
  });

  async function save() {
    setMsg("…");
    try {
      setEu(await put("api/eurotherm/config", payload()));
      setMsg("Salvato");
    } catch (e) { setMsg(e.message); }
    setTimeout(() => setMsg(""), 2500);
  }

  async function runTest() {
    setBusy("test"); setTest(null);
    try {
      await put("api/eurotherm/config", payload());   // prova ciò che vedi
      setTest(await post("api/eurotherm/test"));
    } catch (e) { setTest({ ok: false, error: e.message }); }
    setBusy("");
  }

  async function scan() {
    setBusy("scan"); setTest(null);
    try {
      await put("api/eurotherm/config", payload());
      const r = await post("api/eurotherm/scan");
      if (!r.ok) setTest({ ok: false, error: r.error });
      else if (!r.zones.length) setTest({ ok: false, error: "nessuna zona trovata" });
      else {
        setEu({ ...eu, zones: r.zones.map((z) => ({ ...z, unit: z.unit || "" })) });
        setTest({ ok: true, found: r.zones.length });
      }
    } catch (e) { setTest({ ok: false, error: e.message }); }
    setBusy("");
  }

  return (
    <div class={card + " space-y-3"}>
      <div class="flex items-center justify-between">
        <div class="font-semibold">🏠 Clima Eurotherm (Modbus TCP)</div>
        <label class="text-xs flex items-center gap-1.5">
          <input type="checkbox" checked={eu.enabled}
            onChange={(e) => setEu({ ...eu, enabled: e.target.checked })} />
          attivo
        </label>
      </div>
      <p class="text-xs text-gray-500">
        Indirizzo IP del regolatore SmartControl365. La lettura è di sola lettura:
        Ohm Assistant non scrive mai setpoint o modalità.
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

      <button class="text-xs text-gray-500 underline" onClick={() => setAdv(!adv)}>
        {adv ? "Nascondi" : "Mostra"} registri avanzati
      </button>
      {adv && (
        <div class="grid grid-cols-3 gap-2">
          <div><div class={lbl}>Tipo registri</div>
            <select class={inp} value={eu.input_type} onInput={field("input_type")}>
              <option value="holding">holding (FC3)</option>
              <option value="input">input (FC4)</option>
            </select></div>
          <div><div class={lbl}>Base zona 1</div>
            <input class={inp} type="number" value={eu.zone_base} onInput={field("zone_base")} /></div>
          <div><div class={lbl}>Passo tra zone</div>
            <input class={inp} type="number" value={eu.zone_stride} onInput={field("zone_stride")} /></div>
          <div class="col-span-3 text-xs text-gray-500">
            Zona N → base {eu.zone_base} + (N−1)×{eu.zone_stride}; +5 temperatura,
            +6 umidità, +8 setpoint, +9 modo.
          </div>
        </div>
      )}

      <div class="flex items-center gap-2 flex-wrap">
        <button class={btn} disabled={busy} onClick={runTest}>
          {busy === "test" ? "…" : "Prova connessione"}
        </button>
        <button class={btn} disabled={busy} onClick={scan}>
          {busy === "scan" ? "…" : "Cerca zone"}
        </button>
        {test && (test.ok
          ? <span class="text-xs text-emerald-600">
              {test.found != null ? `${test.found} zone trovate` : "regolatore raggiunto"}
            </span>
          : <span class="text-xs text-red-600">{test.error}</span>)}
      </div>

      {eu.zones.length > 0 && (
        <div class="space-y-2">
          <div class="text-sm font-medium">Zone</div>
          {eu.zones.map((z, i) => (
            <div class="flex items-center gap-2" key={z.index}>
              <input type="checkbox" checked={z.enabled}
                onChange={(e) => setZone(i, { enabled: e.target.checked })} />
              <span class="text-xs text-gray-400 w-6 tabular-nums">#{z.index}</span>
              <input class={inpAuto + " flex-1 min-w-0"} value={z.name}
                placeholder={`Zona ${z.index}`}
                onInput={(e) => setZone(i, { name: e.target.value })} />
              <select class={inpAuto + " w-24 shrink-0"} value={z.unit || ""}
                onInput={(e) => setZone(i, { unit: e.target.value })}>
                {UNITS.map((u) => <option value={u.v} key={u.v}>{u.label}</option>)}
              </select>
              <button class="text-gray-400 px-1"
                onClick={() => setEu({ ...eu, zones: eu.zones.filter((_, j) => j !== i) })}>✕</button>
            </div>
          ))}
        </div>
      )}
      <div class="flex items-center gap-3">
        <button class={btnP} onClick={save}>Salva clima</button>
        <button class={btn} onClick={() => setEu({
          ...eu,
          zones: [...eu.zones, {
            index: (eu.zones.reduce((m, z) => Math.max(m, z.index), 0) || 0) + 1,
            name: "", enabled: true, unit: "",
          }],
        })}>+ zona</button>
        {msg && <span class="text-sm text-emerald-600">{msg}</span>}
      </div>
    </div>
  );
}

export function Setup() {
  const [cfg, setCfg] = useState(null);
  const [groups, setGroups] = useState([]);
  const [map, setMap] = useState({});      // key -> entity_id (editable)
  const [verify, setVerify] = useState({}); // entity_id -> {found,state,unit}
  const [saved, setSaved] = useState("");

  const runVerify = () =>
    get("api/ha/verify").then((v) => {
      const by = {};
      v.entities.forEach((e) => (by[e.entity_id] = e));
      setVerify(by);
    }).catch(() => {});

  useEffect(() => {
    get("api/config").then((c) => { setCfg(c); setMap({ ...c.entity_map }); });
    get("api/config/entity_groups").then((g) => setGroups(g.groups));
    runVerify();
  }, []);

  if (!cfg) return <p class="text-center text-gray-500 py-6">Caricamento…</p>;

  const setField = (k) => (e) => setCfg({ ...cfg, [k]: e.target.value });

  async function save() {
    setSaved("…");
    await put("api/config", {
      andrea_name: cfg.andrea_name,
      genitori_name: cfg.genitori_name,
      canone_rai_default: parseFloat(cfg.canone_rai_default) || 0,
      entity_map: map,
    });
    setSaved("Salvato");
    runVerify();
    setTimeout(() => setSaved(""), 2000);
  }

  return (
    <div class="space-y-4">
      <div class={card + " space-y-2"}>
        <div class="font-semibold">Unità e canone</div>
        <div class="grid grid-cols-2 gap-2">
          <div><div class={lbl}>Nome unità 1</div>
            <input class={inp} value={cfg.andrea_name} onInput={setField("andrea_name")} /></div>
          <div><div class={lbl}>Nome unità 2</div>
            <input class={inp} value={cfg.genitori_name} onInput={setField("genitori_name")} /></div>
          <div><div class={lbl}>Canone RAI € (default)</div>
            <input class={inp} type="number" step="0.01" value={cfg.canone_rai_default} onInput={setField("canone_rai_default")} /></div>
        </div>
      </div>

      <div class={card + " space-y-3"}>
        <div class="flex items-center justify-between">
          <div class="font-semibold">Sensori Home Assistant</div>
          <button class={btn} onClick={runVerify}>Verifica</button>
        </div>
        {groups.map((grp) => (
          <div key={grp.title}>
            <div class="text-sm font-medium mb-1">{grp.title}</div>
            <div class="space-y-2">
              {Object.entries(grp.keys).map(([key, label]) => {
                const eid = map[key] || "";
                const v = verify[eid];
                return (
                  <div key={key}>
                    <div class="flex justify-between">
                      <span class={lbl}>{label}</span>
                      {v ? (v.found
                        ? <span class="text-xs text-emerald-600">{v.state} {v.unit}</span>
                        : <span class="text-xs text-red-600">non trovato</span>) : null}
                    </div>
                    <input class={inp + " font-mono text-xs"} value={eid}
                      onInput={(e) => setMap({ ...map, [key]: e.target.value })} />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <EurothermSetup />

      <div class="flex items-center gap-3">
        <button class={btnP} onClick={save}>Salva impostazioni</button>
        {saved && <span class="text-sm text-emerald-600">{saved}</span>}
      </div>
    </div>
  );
}
