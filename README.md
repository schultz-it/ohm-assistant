# ⚡ Ohm Assistant — Ripartizione bollette per Home Assistant

> *Home Assistant gestisce la casa. Ohm Assistant divide le bollette.*

Ohm Assistant è un **add-on** di Home Assistant che ripartisce le bollette **luce** e
**gas** di casa tra due unità abitative usando i consumi reali dei contabilizzatori Zenner,
di uno Shelly Pro 3EM e dell'inverter fotovoltaico. Tiene lo storico bolletta-per-bolletta
in una dashboard e mostra un cruscotto live dei contabilizzatori.

**Stato: ✅ 1.0 rilasciata.** La documentazione completa è nell'add-on (tab
Documentazione / [DOCS.md](ohm_assistant/DOCS.md)); la specifica è in [SPEC.md](SPEC.md).

## Installazione

[![Add repository to my Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fschultz-it%2Fohm-assistant)

Clicca il badge, oppure manualmente:

1. In Home Assistant: **Impostazioni → Add-on → Store → ⋮ → Repository**
2. Aggiungi: `https://github.com/schultz-it/ohm-assistant`
3. Installa **Ohm Assistant** e avvialo. Apri l'interfaccia dalla barra laterale.

## Come funziona (in breve)

- Dalla bolletta **luce** di Andrea: l'appartamento di Andrea è tutto suo; tutto il resto
  (centrale termica + comuni) si divide per le **quote calore Zenner**. Il canone RAI è di
  Andrea. Il fotovoltaico è gestito sul consumo lordo, così il beneficio dell'autoconsumo è
  condiviso in proporzione ai consumi.
- Dalla bolletta **gas**: gli Smc si dividono per le stesse quote Zenner.

## Funzionalità

- **Bollette**: inserimento manuale o **estrazione AI dal PDF** (OpenAI/Anthropic),
  calcolo della ripartizione, allegato PDF, riepilogo stampabile.
- **Storico**: totali per unità, grafico dello split per bolletta, €/kWh e
  **saldo cumulativo** con spunta "saldato".
- **Live**: contabilizzatori Andrea/Genitori in tempo reale + fotovoltaico.
- **Setup**: mappa sensori editabile con verifica, nomi unità, canone RAI, AI.
- **Bollette storiche**: import dei consumi dallo storico long-term di HA.

Dettaglio del modello di calcolo: [SPEC.md](SPEC.md).

## Licenza

MIT
