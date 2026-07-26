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
compaiono anche stagione (riscaldamento/raffrescamento), presenza, temperatura
esterna e una scheda per ogni zona con temperatura, setpoint, umidità e modo.

## Clima Eurotherm via Modbus (opzionale)

Il regolatore **Eurotherm Smart365 / SmartComfort365** espone l'impianto su
**Modbus TCP** (porta 502). Ohm Assistant lo legge direttamente, senza passare
da Home Assistant, e **solo in lettura**: non scrive mai setpoint o modalità.

In **Setup → Clima Eurotherm (Modbus TCP)**:

1. spunta **attivo** e scrivi l'**indirizzo IP** del regolatore (porta 502,
   unit/slave id 1 nella configurazione standard);
2. **Prova connessione** — legge i registri di sistema e conferma che risponde;
3. **Cerca zone** — sonda gli slot delle zone e propone quelle che rispondono;
4. dai un **nome** a ogni zona e, se vuoi, assegnala a un'unità abitativa
   (serve solo a raggrupparle nel Live: le letture Eurotherm **non entrano nel
   calcolo della bolletta**, che resta basato sulle quote Zenner);
5. **Salva clima**.

L'intervallo di **aggiornamento** (default 30 s) è quello con cui l'add-on
interroga davvero il bus: la tab Live si aggiorna ogni 5 s ma riusa il dato in
cache, così il regolatore non viene sovraccaricato.

### Mappa dei registri

Sotto **Mostra registri avanzati** puoi cambiare tutto se il tuo impianto è
cablato diversamente. Il default è la mappa Smart365:

| Registro | Contenuto |
|---|---|
| 58 | temperatura esterna (×0,1 °C) |
| 101 | stagione: 0 = raffrescamento, 1 = riscaldamento |
| 102 | presenza: 0 = casa, 1 = spento, 2 = assente, 3 = vacanza |
| 103 | boost aria |
| base + 5 | temperatura zona (×0,1 °C) |
| base + 6 | umidità zona (%) |
| base + 8 | setpoint zona (×0,1 °C) |
| base + 9 | modo zona (0 = off, 1 = auto, 2 = manuale) |

dove `base` della zona N = **1200 + (N−1) × 400** → zona 1 = 1200, zona 2 = 1600,
zona 3 = 2000… I registri sono *holding* (function code 3); alcuni impianti li
espongono come *input* (FC 4) e si cambia dallo stesso pannello.

> Nota: gli indirizzi qui sono quelli del **protocollo** (base 0). I manuali
> Eurotherm a volte li elencano a partire da 1: in quel caso sottrai 1.

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
  raggiungibile dalla rete di HA; se risponde ma i valori sono assurdi, controlla
  unit id e tipo di registri (holding/input) in Setup.
- **Eurotherm "nessuna zona trovata"**: la base/passo dei registri del tuo
  impianto è diversa — impostala in **Mostra registri avanzati** e riprova.
