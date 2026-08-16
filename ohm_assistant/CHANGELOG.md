# Changelog

## 1.5.0
- **Entrate nel registro spese** (SPEC 12bis): i soldi che arrivano e vanno
  divisi — **bonifico GSE** del fotovoltaico, **rimborso di tasse**, indennizzi —
  si inseriscono nella tab **Spese** scegliendo **💰 Entrata**. Si compilano come
  una spesa (chi l'ha incassata, divisione a metà / percentuali / cifre) e la
  **quota spettante all'altra unità scala dal debito**: 400 € dal GSE incassati
  da Andrea e divisi a metà tolgono 200 € da quello che devono i Genitori. Se il
  saldo passa sotto zero la freccia si gira da sola.
- **Categorie dedicate alle entrate** — Fotovoltaico, Rimborso tasse, Bonus &
  detrazioni, Rimborsi vari, Affitto — proposte dalla descrizione con lo stesso
  match locale delle spese ("bonifico GSE" → ☀️ Fotovoltaico, "rimborso IRPEF" →
  🏛️ Rimborso tasse). Niente AI, niente rete.
- Spese ed entrate restano **contate separatamente** nei totali (`paid`/`received`,
  `by_category`/`income_by_category` in `GET /api/expenses/summary`), e il saldo
  di Storico usa lo stesso calcolo di Spese: i due numeri non possono divergere.
- API: `kind` (`expense`|`income`) su `GET/POST/PUT /api/expenses` — anche come
  filtro in elenco — e su `/categories` e `/suggest`. Le righe già in archivio
  restano spese (migrazione automatica alla partenza).

## 1.4.3
- **Corretta la cache che nascondeva le novità dopo un aggiornamento**:
  `index.html` usciva senza header `Cache-Control`, così il browser applicava
  la propria cache euristica e poteva continuare a servire la pagina vecchia
  per giorni senza chiederne conferma — l'add-on risultava aggiornato ma
  l'interfaccia restava quella di prima (è il motivo per cui la tab Spese non
  compariva). Ora la pagina viene sempre rivalidata (`no-cache`, con ETag: la
  risposta tipica è un 304) mentre i bundle, che hanno il nome con l'hash,
  restano in cache per sempre.
- **Versione in chiaro** nell'intestazione dell'app e in `GET /api/health`, per
  vedere a colpo d'occhio quale versione sta girando dopo un aggiornamento.

## 1.4.2
- **Icona e logo** dell'add-on (`icon.png`, `logo.png`): un quadrato diviso in
  ambra e azzurro — i colori delle due unità — separati da un fulmine bianco.
  Il logotipo è in ambra per restare leggibile sia sul tema chiaro sia su quello
  scuro dello store. Sorgente rigenerabile in `tools/make_icons.py`.

## 1.4.1
- Nuova categoria **🔁 Abbonamenti** (Netflix, Spotify, Prime, palestra,
  rinnovi…), che prima finivano in "Altro". "Abbonamento TV" e "Abbonamento
  internet" restano in Internet & TV.
- Documentazione: la descrizione del registro spese non cita più Splitwise.

## 1.4.0
- **Registro spese condivise** (nuova tab **Spese**, SPEC 12): spese di casa
  divise fra le due unità — descrizione, importo, data, chi ha pagato e
  divisione **a metà / per percentuali / per cifre**, con anteprima delle quote.
  La **categoria è proposta automaticamente** dalla descrizione con un match su
  parole chiave, in locale: niente AI, niente rete, nessun costo.
- **Ponte bolletta → spese**: le bollette calcolate hanno il bottone
  **🧮 Aggiungi alle spese** (`POST /api/bills/{id}/to_expense`), che le porta nel
  registro con la ripartizione dei contatori come split a cifre fisse. Il flag
  "saldato" resta sincronizzato nei due sensi e le bollette già nel registro non
  vengono contate due volte nel saldo.
- Saldo unificato: `GET /api/stats/summary` espone ora `outstanding_bills` e
  `outstanding_expenses` oltre al totale, e Storico/Spese mostrano lo stesso
  numero.
- Nuove API `CRUD /api/expenses` + `/categories`, `/suggest`, `/summary`; nuova
  tabella `expenses` (creata da sola all'avvio, nessuna migrazione manuale).

## 1.3.1
- Setup Eurotherm: le tendine di assegnazione mostrano i **nomi delle unità
  abitative** scelti in "Unità e canone" invece dei generici "Unità 1/2", come
  già fa il resto dell'app.

## 1.3.0
- **Mappa dispositivo** (`POST /api/eurotherm/map`): sonda lo spazio indirizzi
  del regolatore ed elenca le zone di registri realmente esposte, distinguendo
  quelle documentate dal manuale da quelle che non lo sono. Serve a stabilire
  con i fatti se i parametri delle **Deuclima-VMC** — quelli visibili nel menu
  avanzato del pannello — siano raggiungibili via Modbus o vivano solo
  nell'interfaccia del pannello.
- Campiona un indirizzo ogni 8 e poi allarga ogni riscontro fino al rifiuto del
  dispositivo, così una scansione completa di 65536 indirizzi resta praticabile;
  le scansioni lunghe procedono a più riprese (`next_start`) con avanzamento
  mostrato nel Setup. Un clic su una zona trovata la apre nell'esploratore.
- Setup: intervalli pronti per prima delle Smart Base, dopo i blocchi
  documentati e tutto lo spazio indirizzi; le zone non documentate sono
  evidenziate.

## 1.2.0
- **Mappa registri ufficiale** (SmartComfort 365, *Modbus interface for home
  automation* rev. 05): l'integrazione non usa più indirizzi dedotti. Sistema
  50–59, zona i a `100 + i·130`, Smart Base b a `1140 + b·3260`, stanza r a
  `base + 60 + r·400`. Corretto l'indirizzamento oltre l'ottava stanza, che con
  la mappa precedente sarebbe finito fuori bersaglio.
- **Tre Smart Base con la loro unità aria**: Genitori (Deuclima-VMC 500 V),
  Andrea piano 1 e piano 2 (500 S), precompilate. Il Live raggruppa per Smart
  Base — mandata e setpoint di mandata, tipo di base, sensori collegati e in
  errore, macchina aria — con le schede delle stanze sotto.
- **Più parametri per stanza**: oltre a temperatura, umidità e obiettivo ora
  ci sono **punto di rugiada**, modo esteso (automatico, manuale, manuale
  temporaneo, party, early bird, buonanotte) e gli **allarmi del sensore**
  (condensa, umidità alta con raffrescamento inibito, batterie da sostituire…).
- **Rileva impianto** (`POST /api/eurotherm/discover`): il regolatore dichiara
  la propria topologia (registro 59, bitmap delle basi per zona, id di base e
  stanza) e l'add-on la percorre proponendo basi e stanze realmente presenti —
  niente più tentativi alla cieca.
- **Esplora registri** (`POST /api/eurotherm/explore`): spazza un intervallo di
  indirizzi isolando per bisezione quelli che rispondono con eccezione Modbus,
  annota i registri documentati, evidenzia quelli cambiati dall'ultima lettura
  e permette di **fissarne uno nel Live** (📌) con nome, scala e unità. Serve
  soprattutto per le **macchine aria**, che la rev. 05 non documenta: l'unico
  parametro aria esposto è il boost di rinnovo di zona.
- Temperature decodificate come da manuale (decimi di grado, negativi come
  65536 − valore), quindi le esterne sotto zero si leggono correttamente.

## 1.1.0
- **Clima Eurotherm nei dati live**: il regolatore Smart365 / SmartComfort365
  viene letto direttamente via **Modbus TCP** (sola lettura, nessuna scrittura di
  setpoint o modalità) e le sue zone compaiono nella tab **Live** insieme a
  stagione, presenza e temperatura esterna.
- Setup: pannello *Clima Eurotherm* con IP/porta/unit id, intervallo di
  aggiornamento, **Prova connessione**, **Cerca zone** (sonda gli slot e propone
  quelle che rispondono), nome per zona e assegnazione opzionale a un'unità
  abitativa. Mappa dei registri (base 1200, passo 400, +5/+6/+8/+9 e i registri
  di sistema 58/101/102/103) modificabile per impianti cablati diversamente.
- Client Modbus TCP interno (FC3/FC4, nessuna dipendenza aggiuntiva), letture in
  blocchi contigui e cache TTL pari all'intervallo configurato: la tab Live si
  aggiorna ogni 5 s senza sovraccaricare il bus. Regolatore irraggiungibile o
  disabilitato non compromette mai il resto del cruscotto.
- API: `GET/PUT /api/eurotherm/config`, `GET /api/eurotherm/live`,
  `POST /api/eurotherm/test`, `POST /api/eurotherm/scan`,
  `GET /api/eurotherm/registers`; blocco `eurotherm` aggiunto a `GET /api/live`.
- Le letture Eurotherm sono diagnostiche: la ripartizione delle bollette resta
  basata sulle quote di calore Zenner.

## 1.0.0 🎉
- Prima release stabile.
- Riepilogo bolletta stampabile/condivisibile: `GET /api/bills/{id}/report`
  (pagina self-contained) + pulsante "Riepilogo" sulle bollette calcolate.
- Documentazione in-app completa (DOCS.md): modello di calcolo, setup, come
  dividere una bolletta, storico/saldo, live, AI, bollette storiche, privacy,
  troubleshooting.
- README aggiornato; CI su actions/checkout@v5.

## 0.8.0
- AI PDF extraction (Milestone 5): upload the bill PDF and the configured AI
  provider (OpenAI/Anthropic, key in add-on options) fills in type, period,
  billed kWh/Smc, total cost and canone RAI — always a proposal you review
  before saving, and the PDF is attached to the bill on save.
- New `GET /api/ai/status`, `POST /api/ai/extract`; text extracted locally with
  pypdf, provider called for strict JSON. Scanned (image-only) PDFs are
  reported so you can enter the data by hand.

## 0.7.0
- Storico dashboard (Milestone 6): totals per unit, a stacked bar chart of each
  bill's cost split (Andrea/Genitori), and per-bill €/kWh.
- Cumulative balance: "Genitori owe Andrea €X" over the unsettled computed
  bills, with a per-bill "Saldato" toggle. New `settled` flag on bills
  (auto-migrated) and `GET /api/stats/summary`.

## 0.6.0
- Live dashboard (Milestone 7): the Live tab shows the instantaneous heat-cost-
  allocator readings for both units side by side (mandata, ritorno, ΔT, potenza
  termica, flusso), the total thermal power with an instantaneous heat-split bar
  (by thermal power), and the PV load power. Auto-refreshes every 5 s.
- New `GET /api/live` reading the configured instant sensors via the Supervisor.

## 0.5.0
- Web UI (Milestone 4/5): mobile-first Preact + Tailwind SPA with a bottom tab
  bar (Bollette · Storico · Live · Setup), served at the panel root; the dev
  console moves to `/dev`.
  - **Bollette**: add a bill, `Calcola` the split (with a one-tap "import HA
    history & recompute" when snapshots are missing for the period), attach/open
    the PDF, and expand the full breakdown (L, S, quote Zenner, prezzo,
    diagnostica).
  - **Setup**: unit names, canone RAI default, and the editable HA entity map
    with live verify per sensor.
  - Storico and Live tabs are placeholders (M6/M7).
- Attach the original bill PDF: `POST/GET /api/bills/{id}/pdf` (stored in /data).

## 0.4.0
- Ripartition engine (Milestone 3): the SPEC 4 formulas. Electric — all on
  gross consumption so PV self-consumption never mixes bases: `L = prelievo +
  autoconsumo`, `S = L − appartamento`, split `S` by Zenner heat quotas, canone
  RAI 100% to Andrea, PV benefit shared; plus diagnostics (prelievo vs billed,
  production vs export+self, unmetered load). Gas — Smc split by Zenner quotas.
- `POST /api/bills/{id}/compute`: computes who pays what from the period deltas,
  stores the full breakdown, or reports which sensors are missing for the period.
- History import (Milestone 3): `POST /api/snapshots/import_history` backfills a
  past period's snapshots from HA long-term statistics over the WebSocket API —
  so you can split a bill from before the add-on was installed (e.g. June).
- Dev console: per-bill "Calcola" + "Importa storico HA".

## 0.3.0
- Snapshot engine (Milestone 2): APScheduler daily job (00:05 UTC) that stores
  a reading of every cumulative meter (Zenner, Shelly, PV), plus one snapshot
  at add-on startup so a period always has a baseline point.
- Period-delta computation with meter-reset handling (a decrease counts the new
  reading), used later by the ripartition engine.
- API: `POST /api/snapshots/now`, `GET /api/snapshots`, `GET /api/snapshots/delta`
  (deltas for every calc key over a period), `POST /api/snapshots/manual`
  (bootstrap past billing periods by hand).
- Dev console: snapshot button + period-delta tester.

## 0.2.0
- Data layer (Milestone 1): SQLite in `/data`, SQLAlchemy models for config,
  bills and daily meter snapshots.
- CRUD REST API: `GET/PUT /api/config` (names, canone RAI default, editable
  entity map on top of the defaults), full `CRUD /api/bills`, plus
  `GET /api/ha/verify` now checking the *configured* entities.
- Ingress page turned into a dev console (settings + sensor verify + bills)
  until the SPA arrives (M5).

## 0.1.0
- Initial skeleton (Milestone 0): add-on boots, Ingress hello page, Supervisor
  API entity listing, and a "verify sensors" panel that checks every default
  meter/Shelly/PV entity the ripartition will rely on (SPEC 3).
