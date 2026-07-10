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
volume `/data` dell'add-on. L'unica chiamata esterna è, se abiliti l'AI, l'invio
del **testo** della bolletta al provider che hai scelto (OpenAI/Anthropic).

## Risoluzione problemi

- **Sensori "non trovato"**: l'entity_id in Setup non combacia con HA — correggi
  e salva.
- **"Mancano gli snapshot"**: usa l'import da storico, o attendi che gli
  snapshot notturni coprano il periodo.
- **Prelievo ≠ fatturato** (in Dettaglio): piccolo scostamento è normale
  (contatore inverter vs contatore fiscale).
- **AI non disponibile**: controlla `ai_provider` e `ai_api_key` nelle opzioni.
