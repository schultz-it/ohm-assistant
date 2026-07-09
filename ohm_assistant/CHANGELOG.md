# Changelog

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
