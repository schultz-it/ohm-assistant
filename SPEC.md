# Bill Splitter — Add-on Home Assistant per la ripartizione bollette

> Divide le bollette **luce** e **gas** di casa tra due unità abitative (**Andrea** e
> **Genitori**) usando i consumi reali dei contabilizzatori Zenner, dello Shelly Pro 3EM
> e dell'inverter fotovoltaico. Tiene lo storico bolletta-per-bolletta e un cruscotto live.
>
> Uso personale, ma distribuito come add-on (repo GitHub) esattamente come Petrichor /
> `hose_assistant`.

## 1. Panoramica

### Contesto fisico
Casa indipendente con due appartamenti. **Andrea e Genitori hanno due contatori (POD)
elettrici separati.** Sotto il **POD di Andrea** stanno:
- l'appartamento di Andrea,
- la **centrale termica** (Beretta Tower Hybrid: gas + pompa di calore; fa riscaldamento,
  raffrescamento e ACS per tutta la casa),
- l'**impianto fotovoltaico** (inverter ibrido Sungrow SH60RS),
- i servizi comuni (cancello automatico, luci giardino, …).

Poiché la centrale termica e i comuni servono entrambe le unità ma pesano sulla bolletta
di Andrea, **i Genitori devono ad Andrea la quota di tutto ciò che sulla bolletta di
Andrea non è "appartamento Andrea"**. La loro corrente di appartamento è sul loro POD
(fuori scope).

### Obiettivi
- Inserire (a mano o via estrazione AI del PDF) i dati di una bolletta luce o gas.
- Calcolare **quanto paga Andrea** e **quanto pagano i Genitori**.
- Storico + dashboard dei consumi/costi bolletta per bolletta.
- Cruscotto live dei contabilizzatori e del FV.
- Saldo/conguaglio cumulativo (Andrea anticipa, i Genitori rimborsano).

### Non-obiettivi (v1)
- Non gestisce la bolletta luce del POD Genitori (è interamente loro).
- Non attua nulla su HA (sola lettura degli stati). Nessun controllo attuativo.

## 2. Architettura
Identica a `hose_assistant`:
- **Add-on HA** con `ingress`, Docker su `ghcr.io/home-assistant/*-base`, s6 `run` in
  `rootfs/etc/services.d/bill_splitter/run`.
- **Backend**: FastAPI + SQLite (SQLAlchemy) su `/data` (persistente, micro-migrazioni a
  runtime). `httpx` verso `http://supervisor/core/api` con `SUPERVISOR_TOKEN`
  (`homeassistant_api: true`). APScheduler per lo snapshot giornaliero.
- **Frontend**: Preact + Vite + Tailwind v4, mobile-first, nav a tab in basso, i18n it/en.
- **AI**: opzione add-on `ai_provider` (`none`/`openai`/`anthropic`/`ha_conversation`) +
  `ai_api_key`. Solo estrazione dati dal PDF → sempre proposta rivedibile dall'utente.

Slug add-on: `bill_splitter`. Codename repo: **da scegliere** (stile Petrichor).

## 3. Entità HA (default precompilati nel Setup)

Calore Zenner (kWh, cumulativi):
- `sensor.zenner_energia_totale_andrea`
- `sensor.zenner_energia_totale_genitori`

Contabilizzatori — valori istantanei (il gemello `_genitori` esiste per ognuno):
- mandata: `sensor.contabilizzatore_andrea_flow_temperature_7`
- ritorno: `sensor.contabilizzatore_andrea_return_temperature_8`
- ΔT: `sensor.contabilizzatore_andrea_temperature_difference_9`
- potenza termica (kW): `sensor.contabilizzatore_andrea_power_11`
- flusso: `sensor.contabilizzatore_andrea_volume_flow_10`

Shelly Pro 3EM (kWh cumulativi, pinze sul quadro generale, misura **lorda**):
- appartamento Andrea: `sensor.3_shelly_pro_3em_app_andrea_total_active_energy`
- centrale termica: `sensor.shelly_pro_3em_clima_total_active_energy`
  *(non usato nel calcolo di ripartizione; serve solo per statistiche caldaia/PdC)*

Inverter FV Sungrow SH60RS (kWh cumulativi, + una potenza):
- produzione AC: `sensor.sh60rs_a2251102546_total_ac_output_energy`
- immissione (export): `sensor.sh60rs_a2251102546_total_feed_in_energy`
- potenza di carico totale (W): `sensor.sh60rs_a2251102546_total_load_active_power`
- **autoconsumo** (FV→carichi): `sensor.sh60rs_a2251102546_total_load_energy_consumption_from_pv`
- **prelievo da rete**: `sensor.sh60rs_a2251102546_total_purchased_energy`

## 4. Modello di calcolo (DEFINITIVO)

Tutte le grandezze sono **delta sul periodo di fatturazione** `[d0, d1]`, ricavati dagli
snapshot giornalieri (§6). Regola d'oro: **il fotovoltaico non deve mescolare basi
diverse** — si lavora tutto sul consumo *lordo* e la bolletta è solo il "totale € da
dividere".

### 4.1 Luce (bolletta del POD Andrea)
Dalla bolletta: `E_fatt` (kWh fatturati), `C_tot` (€ totali), `canone_RAI` (€), periodo.

```
A_app = Δ(app_andrea)                        # appartamento Andrea, LORDO → 100% Andrea
L     = Δ(total_purchased_energy) + Δ(total_load_energy_consumption_from_pv)
                                             # carico LORDO totale del POD = prelievo + autoconsumo
S     = L − A_app                            # bucket condiviso: clima + comuni (tutto il non-appartamento)
f_a   = ΔZenner_andrea / (ΔZenner_andrea + ΔZenner_genitori)
f_g   = 1 − f_a

Andrea_lordo   = A_app + f_a · S
Genitori_lordo =         f_g · S             # Andrea_lordo + Genitori_lordo = L

Andrea paga   = (C_tot − canone_RAI) · Andrea_lordo   / L + canone_RAI
Genitori pag. = (C_tot − canone_RAI) · Genitori_lordo / L
```

Decisioni fissate:
- **Tutto il bucket `S` si divide per le quote Zenner** (`f_a`/`f_g`). I consumi extra-clima
  (cancello, luci giardino) sono trascurabili → una chiave sola.
- **Canone RAI → 100% Andrea.**
- **Beneficio FV condiviso**: dividendo `C_tot` per le quote di consumo *lordo*, il
  risparmio da autoconsumo si distribuisce in proporzione ai consumi.
- Costi fissi/oneri: spalmati nel prezzo medio (blended €/kWh). Raffinabile in v2.

Diagnostica da mostrare (non entra nel conto):
- `imp = Δ(total_purchased_energy)` deve essere ≈ `E_fatt` della bolletta (scostamento =
  differenza tra contatore inverter e contatore fiscale).
- `produzione ≈ export + autoconsumo` (check di coerenza inverter).
- `L − A_app − Δ(Shelly_clima)` = carichi non misurati (dovrebbe essere piccolo).

### 4.2 Gas (centrale termica ibrida)
Dalla bolletta: `Smc_fatt`, `C_tot_gas`, periodo.
```
Smc_Andrea   = f_a · Smc_fatt
Smc_Genitori = f_g · Smc_fatt
Andrea   = C_tot_gas · f_a
Genitori = C_tot_gas · f_g
```
Nota: il gas arriva in stagione fredda, quando il raffrescamento è ≈0, quindi la
`energia_totale` Zenner ≈ solo riscaldamento → il rapporto è un buon proxy. Da rivedere
se emergessero registri separati riscaldamento/raffrescamento.

### 4.3 Persistenza dei risultati
Per ogni bolletta si salva **l'intero breakdown calcolato** (`f_a`, `L`, `A_app`, `S`,
autoconsumo, prelievo, importi, ecc.), così lo storico resta immutabile anche se in futuro
si cambia la formula.

## 5. Modello dati (SQLite)
- **Config** (singleton): nomi unità, mappa entity_id (JSON, coi default §3), `canone_rai`
  di default, valuta, opzioni AI (mirror delle options add-on).
- **Bill**: `type` (electric|gas), `period_start`, `period_end`, `billed` (kWh o Smc),
  `cost_total`, `canone_rai`, `pdf_path`, `source` (manual|ai), `status` (draft|final),
  `notes`, `created_at`.
- **BillAllocation**: importi e quote calcolate + `breakdown_json` (snapshot completo).
- **MeterSnapshot**: `date`, `entity_id`, `value` (letture giornaliere).
- **Settlement**: righe di conguaglio/saldo (chi deve quanto, segnato come saldato).

## 6. Snapshot engine
- Job APScheduler ~00:05: legge via Supervisor `/states/<entity>` tutti i sensori
  cumulativi e li scrive in `MeterSnapshot`.
- Delta periodo `[d0,d1]` = valore allo snapshot ≥ d1 meno valore allo snapshot ≤ d0, con
  **gestione reset** (se la serie decresce, somma degli incrementi positivi).
- **Bootstrap / bollette storiche**: lettura delle long-term statistics HA se disponibili,
  altrimenti inserimento manuale dei valori contatore per il periodo.

## 7. UI — 4 tab (mobile-first)
1. **Bollette** — nuova bolletta luce/gas: carica PDF → estrazione AI *oppure* inserimento
   manuale; rivedi i valori; l'app calcola i delta e mostra **"Andrea paga X / Genitori
   pagano Y"** con dettaglio; salva (allega PDF in `/data`).
2. **Storico & Dashboard** — elenco bollette + grafici (costo per unità nel tempo, kWh,
   €/kWh, Smc gas, quota % nel tempo, totali annui) + **saldo cumulativo** + export.
3. **Cruscotto live** — contabilizzatori Andrea/Genitori affiancati (mandata, ritorno, ΔT,
   potenza termica, flusso), potenza clima Shelly, FV (produzione, autoconsumo %,
   prelievo/immissione), efficienza caldaia (kWh termici Zenner ÷ kWh elettrici clima).
4. **Setup** — mappa entity_id (precompilati), nomi unità, provider/chiave AI, canone RAI,
   opzioni di ripartizione, valuta/lingua.

## 8. Estrazione AI del PDF
Provider da opzioni add-on (default OpenAI, come Petrichor). PDF → JSON strutturato:
`billed`, `cost_total`, `period_start/end`, `canone_rai`, oneri. **Sempre proposta
rivedibile**, fallback all'inserimento manuale. L'AI non calcola le ripartizioni, solo
estrae i dati di input.

## 9. Idee extra
- Riepilogo stampabile/PDF per bolletta da condividere coi Genitori.
- Saldo cumulativo "Genitori devono ad Andrea €X" con segna-come-saldato.
- Note per bolletta + archivio PDF originali.
- Notifica HA se uno snapshot fallisce o un sensore è `unavailable`.

## 10. Milestone (ordine di build, un pezzo per commit/PR)
- **M0 — Scaffold**: repo, `repository.yaml`, add-on skeleton (config/build/Dockerfile/
  rootfs), ingress "hello", GitHub Action di build. → installabile da HA.
- **M1 — Data layer**: SQLite, modelli, CRUD API, mappatura entità nel Setup.
- **M2 — Snapshot engine**: job giornaliero + lettura Supervisor + gestione reset + delta.
- **M3 — Motore ripartizione**: formule §4 luce/gas, endpoint "calcola", test con numeri veri.
- **M4 — Tab Bollette (manuale)**: inserimento, calcolo, salvataggio, allegato PDF.
- **M5 — Estrazione AI PDF**: OpenAI → proposta rivedibile.
- **M6 — Storico & Dashboard**: grafici + saldo cumulativo + export.
- **M7 — Cruscotto live**: valori istantanei contabilizzatori + FV.
- **M8 — Rifiniture**: i18n it/en, DOCS.md, riepilogo stampabile, README/badge, release 1.0.

## 11. Punti ancora aperti (minori, non bloccanti)
- Batteria sull'ibrido Sungrow? Se presente, `L` va corretto col flusso batteria (i
  sensori elencati non la citano → assunzione: nessuna batteria; da validare a runtime).
- 3° canale dello Shelly Pro 3EM: cosa misura (per completare la diagnostica).
- ACS: se non è misurata dallo Zenner e pesa, valutare in v2 una chiave dedicata.
