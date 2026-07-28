# Ohm Assistant — Documentazione

Ripartisce le bollette **luce** e **gas** di casa tra due unità abitative
(**Andrea** e **Genitori**) usando i consumi reali dei contabilizzatori Zenner,
dello Shelly Pro 3EM e dell'inverter fotovoltaico. Storico in dashboard e
cruscotto live dei contabilizzatori.

## Come funziona la divisione

### Luce (bolletta del POD di Andrea)
Sotto il contatore di Andrea ci sono: il suo appartamento, la centrale termica
(Beretta ibrida gas + pompa di calore, che serve tutta la casa), il
fotovoltaico e i servizi comuni. Regola:

- l'**appartamento di Andrea** è al 100% suo (misurato dallo Shelly);
- **tutto il resto** (centrale termica + comuni) si divide per le **quote calore
  Zenner** (chi scalda/raffresca di più paga di più);
- il **canone RAI** è al 100% di Andrea;
- il **fotovoltaico** è gestito sul consumo *lordo*, così il beneficio
  dell'autoconsumo si distribuisce in proporzione ai consumi (condiviso).

Formula: `L = prelievo + autoconsumo` (carico lordo del POD), `S = L −
appartamento`, si divide il costo della bolletta per le quote di consumo lordo.
Il prelievo misurato viene confrontato coi kWh fatturati come diagnostica.

### Gas
Gli Smc fatturati si dividono per le stesse **quote calore Zenner**. In stagione
fredda (quando arriva il gas) il raffrescamento è ~0, quindi la quota calore è
un buon proxy.

## Primo avvio

1. Apri **Ohm Assistant** dalla barra laterale.
2. Vai in **Setup**:
   - controlla i **nomi** delle due unità e il **canone RAI** di default;
   - verifica la **mappa sensori** (già precompilata). Premi **Verifica**: i
     sensori trovati mostrano il valore corrente, quelli sbagliati "non
     trovato" — correggi l'entity_id e **Salva**.
3. (Opzionale) Configura l'**AI** per leggere i PDF (vedi sotto).

Da subito l'add-on registra ogni notte (00:05 UTC) uno **snapshot** dei
contatori: più giorni passano, più i periodi futuri sono coperti.

## Dividere una bolletta

1. Tab **Bollette → Nuova bolletta**: scegli tipo (Luce/Gas), periodo, quantità
   fatturata (kWh/Smc), costo totale e canone RAI. Oppure usa **📄 Compila da
   PDF** (se hai configurato l'AI).
2. **Aggiungi**.
3. Premi **Calcola**. Vedrai quanto paga Andrea e quanto i Genitori.
   - Se compare "mancano gli snapshot per il periodo" (bolletta precedente
     all'installazione o al primo snapshot), premi **Importa storico HA e
     ricalcola**: recupera le letture dei contatori dallo storico *long-term*
     di Home Assistant e ricalcola.
4. **Riepilogo** apre una pagina stampabile da condividere; **Allega PDF**
   salva la bolletta originale.

## Storico

La tab **Storico** mostra:
- il **saldo cumulativo** "Genitori devono ad Andrea €X" (Andrea anticipa le
  bollette; ogni quota resta dovuta finché non la segni **Saldato**);
- i **totali** per unità;
- un **grafico** dello split per bolletta e il **€/kWh**.

## Cruscotto live

La tab **Live** mostra in tempo reale (aggiornamento ogni 5s) mandata, ritorno,
ΔT, potenza termica e flusso dei contabilizzatori di Andrea e Genitori, lo
split istantaneo del calore e la potenza di carico del fotovoltaico.

Se hai configurato il regolatore **Eurotherm** (sotto), in fondo alla tab
compaiono stagione, modo zona, temperatura esterna e — per ogni **Smart Base** —
mandata e setpoint di mandata, stato dei sensori, la macchina aria associata e
le schede delle sue stanze (temperatura, obiettivo, umidità, punto di rugiada,
modo, allarmi del sensore).

## Clima Eurotherm via Modbus (opzionale)

Il regolatore **Eurotherm SmartComfort 365** espone l'impianto su **Modbus TCP**
(porta 502, unit id 1 di default; il protocollo supporta anche RTU a 19200 8N1).
Ohm Assistant lo legge direttamente, senza passare da Home Assistant, e **solo
in lettura**: non scrive mai setpoint o modalità.

Un solo SmartControl365 risponde per tutto l'impianto — stesso IP per tutte le
Smart Base — e le parti si distinguono dagli indirizzi dei registri.

### Come è fatto l'impianto

Il protocollo organizza tutto su tre livelli:

- **Zona** (sottosistema, fino a 8): stagione caldo/freddo, modo casa/assente/
  vacanza, boost di rinnovo aria, e quali Smart Base ne fanno parte;
- **Smart Base** (fino a 8, 8 stanze ciascuna): temperatura e setpoint di
  mandata, tipo di base (con o senza miscelazione), numero di sensori collegati
  e loro stato di errore;
- **Stanza**: temperatura, umidità, **punto di rugiada**, temperatura
  obiettivo, modo (automatico, manuale, party, early bird, buonanotte…),
  temperatura manuale e la diagnostica del sensore (condensa, umidità alta con
  raffrescamento inibito, batterie da sostituire…).

### Configurazione

In **Setup → Clima Eurotherm**:

1. spunta **attivo** e scrivi l'**indirizzo IP** del regolatore;
2. **Prova connessione** — legge il blocco di sistema e mostra temperatura
   esterna e numero di zone;
3. **Rileva impianto** — il regolatore dichiara la propria topologia (registro
   59, mappa delle basi in ogni zona, id di base e stanza): l'add-on la percorre
   e propone Smart Base e stanze realmente presenti;
4. dai un **nome** a basi e stanze, scegli il **modello di macchina aria** di
   ogni base e, se vuoi, assegna base o stanza a un'unità abitativa (serve solo
   a raggruppare nel Live: le letture Eurotherm **non entrano nel calcolo della
   bolletta**, che resta basato sulle quote Zenner);
5. **Salva clima**.

L'intervallo di **aggiornamento** (default 30 s) è quello con cui l'add-on
interroga davvero il bus: la tab Live si aggiorna ogni 5 s ma riusa il dato in
cache, così il regolatore non viene sovraccaricato.

### Mappa dei registri (rev. 05)

| Blocco | Indirizzo | Contenuto |
|---|---|---|
| Sistema | 50–59 | seriale, data/ora, temperatura esterna (58), numero di zone (59) |
| Zona i | 100 + i×130 | stagione (0 freddo, 1 caldo), modo zona, boost aria, mappa delle basi |
| Smart Base b | 1140 + b×3260 | id base/zona, sensori, errori, tipo base, setpoint e temperatura di mandata |
| Stanza r della base b | 1140 + b×3260 + 60 + r×400 | +5 temperatura, +6 umidità, +7 rugiada, +8 obiettivo, +9 modo, +10 temperatura manuale |

Le temperature sono in decimi di grado; i negativi sono scritti come
65536 − valore. Con tre Smart Base gli indirizzi di partenza sono **1140**,
**4400** e **7660**, e le rispettive stanze cominciano a **1200**, **4460** e
**7720**.

### Macchine aria (VMC)

⚠️ Il protocollo rev. 05 **non pubblica registri per le Deuclima-VMC / SmartAir**:
l'unico parametro dell'aria che espone è il **boost di rinnovo** a livello di
zona (registro 103 + offset). Il modello della macchina associata a ogni base è
quindi solo un'etichetta.

Questo però dice solo cosa è *documentato*. I valori che vedi nel menu avanzato
del pannello il regolatore li ha in memoria — li legge dalle macchine sul bus
interno — quindi restano due possibilità: che siano esposti anche sul Modbus
esterno a indirizzi non documentati, oppure che vivano solo dentro
l'interfaccia del pannello. Per stabilirlo ci sono due strumenti.

**🗺️ Mappa dispositivo.** Sonda lo spazio indirizzi ed elenca le **zone di
registri che il regolatore espone davvero**, marcando in verde quelle fuori dai
blocchi documentati — le candidate per le macchine aria. Tre intervalli pronti:
prima delle Smart Base (0–1139), dopo i blocchi documentati, e tutto lo spazio
0–65535. Le scansioni lunghe procedono a più riprese, con avanzamento a video.
Un clic su una zona la apre nell'esploratore. Nota: campiona un indirizzo ogni
8, quindi blocchi più corti di 8 registri possono sfuggirle.

**🔎 Esplora registri.** Legge un intervallo e mostra ogni registro che
risponde (valore, ×0,1, e l'etichetta se il manuale lo documenta) evidenziando
quelli **cambiati** dall'ultima lettura. È il modo pratico per identificarli:
cambia una cosa sul pannello — velocità di ventilazione, boost, un setpoint —
poi premi **Rileggi** con **solo cambiati** spuntato, e resta ciò che si è
mosso. Quando riconosci un registro, **📌** lo fissa nel cruscotto Live con
nome, scala e unità di misura, sotto il sistema, una Smart Base o la sua
macchina aria.

Se la mappa non trova nulla fuori dai blocchi documentati, allora quei valori
sul Modbus TCP non ci sono, e le strade restano due: leggere le Deuclima
**direttamente** sul loro bus RS-485 con un gateway Modbus, oppure chiedere a
Eurotherm una revisione più recente del documento di protocollo (questa è la
rev. 05 del 2022).

## AI per i PDF (opzionale)

Nelle **opzioni dell'add-on**:
- `ai_provider`: `openai` (o `anthropic`)
- `ai_api_key`: la tua chiave API
- `ai_model`: opzionale (default `gpt-4o-mini` per OpenAI)

Poi in **Bollette** appare **📄 Compila da PDF**: carica la bolletta, l'AI
compila tipo/periodo/quantità/costo/canone, tu **rivedi** e salvi. È sempre una
proposta: l'AI non calcola e non salva nulla da sola. I PDF solo-immagine
(scansioni senza testo) non sono supportati: inserisci i dati a mano.

## Bollette storiche (prima dell'installazione)

Puoi dividere anche bollette passate: inserisci la bolletta col suo periodo e
usa **Importa storico HA e ricalcola**. Funziona se i contatori hanno le
statistiche a lungo termine in HA (i sensori di energia le hanno). In
alternativa i valori dei contatori si possono inserire a mano.

## Privacy

Tutto gira in locale nell'add-on. I dati (bollette, snapshot, PDF) restano nel
volume `/data` dell'add-on. L'unica chiamata **esterna** è, se abiliti l'AI,
l'invio del **testo** della bolletta al provider che hai scelto
(OpenAI/Anthropic). Il regolatore Eurotherm viene interrogato sulla tua **rete
locale**, in sola lettura.

## Risoluzione problemi

- **Sensori "non trovato"**: l'entity_id in Setup non combacia con HA — correggi
  e salva.
- **"Mancano gli snapshot"**: usa l'import da storico, o attendi che gli
  snapshot notturni coprano il periodo.
- **Prelievo ≠ fatturato** (in Dettaglio): piccolo scostamento è normale
  (contatore inverter vs contatore fiscale).
- **AI non disponibile**: controlla `ai_provider` e `ai_api_key` nelle opzioni.
- **Eurotherm "non raggiungibile"**: verifica IP e che la porta 502 sia
  raggiungibile dalla rete di HA; controlla anche l'unit id (1 di default, si
  cambia dall'interfaccia del regolatore).
- **Eurotherm: nessuna Smart Base rilevata**: "Rileva impianto" si basa sul
  registro 59 e sulla mappa delle basi; se il regolatore le dichiara a zero,
  usa **Esplora registri** partendo da 1140 per vedere cosa risponde.
- **Una stanza non compare**: viene esclusa quando il sensore risulta
  scollegato o il tipo di sensore non è valido — controlla la stanza nel
  regolatore, poi rilancia "Rileva impianto".
