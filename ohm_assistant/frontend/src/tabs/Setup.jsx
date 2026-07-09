import { useEffect, useState } from "preact/hooks";
import { get, post, put } from "../api.js";

const card = "rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4";
const btnP = "px-3 py-1.5 rounded-lg bg-amber-500 text-white text-sm font-medium disabled:opacity-50";
const btn = "px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm";
const inp = "w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm";
const lbl = "text-xs text-gray-500 dark:text-gray-400";

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

      <div class="flex items-center gap-3">
        <button class={btnP} onClick={save}>Salva impostazioni</button>
        {saved && <span class="text-sm text-emerald-600">{saved}</span>}
      </div>
    </div>
  );
}
