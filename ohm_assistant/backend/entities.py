"""Canonical entity map for Ohm Assistant (SPEC 3).

``DEFAULT_MAP`` maps a stable internal *key* to the user's real HA entity_id.
The keys never change; the entity_ids are user-editable (stored in Config) so
the whole app is driven by these keys, not by hardcoded ids. ``GROUPS`` only
adds labels/ordering for the Setup UI.
"""

DEFAULT_MAP: dict[str, str] = {
    # Cumulative energy (kWh) — used by the ripartition math.
    "zenner_andrea": "sensor.zenner_energia_totale_andrea",
    "zenner_genitori": "sensor.zenner_energia_totale_genitori",
    "shelly_app_andrea": "sensor.3_shelly_pro_3em_app_andrea_total_active_energy",
    "shelly_clima": "sensor.shelly_pro_3em_clima_total_active_energy",
    "pv_ac_output": "sensor.sh60rs_a2251102546_total_ac_output_energy",
    "pv_feed_in": "sensor.sh60rs_a2251102546_total_feed_in_energy",
    "pv_self_consumption": "sensor.sh60rs_a2251102546_total_load_energy_consumption_from_pv",
    "pv_purchased": "sensor.sh60rs_a2251102546_total_purchased_energy",
    # Instantaneous heat-cost-allocator readings — Andrea.
    "andrea_flow_temp": "sensor.contabilizzatore_andrea_flow_temperature_7",
    "andrea_return_temp": "sensor.contabilizzatore_andrea_return_temperature_8",
    "andrea_temp_diff": "sensor.contabilizzatore_andrea_temperature_difference_9",
    "andrea_power": "sensor.contabilizzatore_andrea_power_11",
    "andrea_volume_flow": "sensor.contabilizzatore_andrea_volume_flow_10",
    # Instantaneous heat-cost-allocator readings — Genitori.
    "genitori_flow_temp": "sensor.contabilizzatore_genitori_flow_temperature_7",
    "genitori_return_temp": "sensor.contabilizzatore_genitori_return_temperature_8",
    "genitori_temp_diff": "sensor.contabilizzatore_genitori_temperature_difference_9",
    "genitori_power": "sensor.contabilizzatore_genitori_power_11",
    "genitori_volume_flow": "sensor.contabilizzatore_genitori_volume_flow_10",
    # Instantaneous PV.
    "pv_load_power": "sensor.sh60rs_a2251102546_total_load_active_power",
}

# Keys whose delta over a billing period feeds the calculation (SPEC 4/6).
CALC_CUMULATIVE_KEYS: list[str] = [
    "zenner_andrea", "zenner_genitori", "shelly_app_andrea", "shelly_clima",
    "pv_ac_output", "pv_feed_in", "pv_self_consumption", "pv_purchased",
]

# Display grouping/labels for the Setup UI (key -> label).
GROUPS: list[dict] = [
    {"title": "Calore Zenner (kWh)", "keys": {
        "zenner_andrea": "Energia totale Andrea",
        "zenner_genitori": "Energia totale Genitori"}},
    {"title": "Shelly Pro 3EM (kWh)", "keys": {
        "shelly_app_andrea": "Appartamento Andrea",
        "shelly_clima": "Centrale termica (clima)"}},
    {"title": "Fotovoltaico Sungrow", "keys": {
        "pv_ac_output": "Produzione AC (kWh)",
        "pv_feed_in": "Immissione/export (kWh)",
        "pv_self_consumption": "Autoconsumo (kWh)",
        "pv_purchased": "Prelievo da rete (kWh)",
        "pv_load_power": "Potenza di carico (W)"}},
    {"title": "Contabilizzatore Andrea", "keys": {
        "andrea_flow_temp": "Mandata (°C)",
        "andrea_return_temp": "Ritorno (°C)",
        "andrea_temp_diff": "ΔT (°C)",
        "andrea_power": "Potenza termica (kW)",
        "andrea_volume_flow": "Flusso"}},
    {"title": "Contabilizzatore Genitori", "keys": {
        "genitori_flow_temp": "Mandata (°C)",
        "genitori_return_temp": "Ritorno (°C)",
        "genitori_temp_diff": "ΔT (°C)",
        "genitori_power": "Potenza termica (kW)",
        "genitori_volume_flow": "Flusso"}},
]


def merged_map(overrides: dict | None) -> dict[str, str]:
    """Effective entity map: defaults with any stored overrides applied."""
    m = dict(DEFAULT_MAP)
    if overrides:
        m.update({k: v for k, v in overrides.items() if k in DEFAULT_MAP and v})
    return m
