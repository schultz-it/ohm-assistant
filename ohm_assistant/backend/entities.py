"""Default Home Assistant entity IDs used by Ohm Assistant (SPEC 3).

These are the user's real entities, prefilled as defaults. In M1 they become
editable from the Setup tab and are stored in the config; for M0 they drive the
"verify sensors" section of the ingress hello page.
"""

# Cumulative energy meters (kWh) — the ones the ripartition math relies on.
CUMULATIVE = {
    "zenner_andrea": "sensor.zenner_energia_totale_andrea",
    "zenner_genitori": "sensor.zenner_energia_totale_genitori",
    "shelly_app_andrea": "sensor.3_shelly_pro_3em_app_andrea_total_active_energy",
    "shelly_clima": "sensor.shelly_pro_3em_clima_total_active_energy",
    "pv_ac_output": "sensor.sh60rs_a2251102546_total_ac_output_energy",
    "pv_feed_in": "sensor.sh60rs_a2251102546_total_feed_in_energy",
    "pv_self_consumption": "sensor.sh60rs_a2251102546_total_load_energy_consumption_from_pv",
    "pv_purchased": "sensor.sh60rs_a2251102546_total_purchased_energy",
}

# Instantaneous heat-cost-allocator readings (per unit) — for the live dashboard.
INSTANT = {
    "andrea": {
        "flow_temp": "sensor.contabilizzatore_andrea_flow_temperature_7",
        "return_temp": "sensor.contabilizzatore_andrea_return_temperature_8",
        "temp_diff": "sensor.contabilizzatore_andrea_temperature_difference_9",
        "power": "sensor.contabilizzatore_andrea_power_11",
        "volume_flow": "sensor.contabilizzatore_andrea_volume_flow_10",
    },
    "genitori": {
        "flow_temp": "sensor.contabilizzatore_genitori_flow_temperature_7",
        "return_temp": "sensor.contabilizzatore_genitori_return_temperature_8",
        "temp_diff": "sensor.contabilizzatore_genitori_temperature_difference_9",
        "power": "sensor.contabilizzatore_genitori_power_11",
        "volume_flow": "sensor.contabilizzatore_genitori_volume_flow_10",
    },
}

# One extra instantaneous PV reading, handy on the live dashboard.
INSTANT_PV = {"load_power": "sensor.sh60rs_a2251102546_total_load_active_power"}


def all_default_ids() -> list[str]:
    """Flat list of every default entity id, for the M0 verification page."""
    ids = list(CUMULATIVE.values())
    for unit in INSTANT.values():
        ids.extend(unit.values())
    ids.extend(INSTANT_PV.values())
    return ids
