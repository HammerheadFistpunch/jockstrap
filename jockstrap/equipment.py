"""Antenna presets, never implicit rate-specific factory link budgets."""
from .project import Radio
from .tplink_catalog import CATALOG

PRESETS = {
    "Generic sector": dict(role="sector", protocol="custom", gain_dbi=16, az_beamwidth_deg=90, el_beamwidth_deg=10),
    "Generic client dish": dict(role="client", protocol="custom", gain_dbi=23, az_beamwidth_deg=9, el_beamwidth_deg=7, aim="peer"),
    "TP-Link CPE710": dict(role="client", protocol="pharos-ac", gain_dbi=23, az_beamwidth_deg=9, el_beamwidth_deg=7, aim="peer"),
    "TP-Link EAP211-Bridge": dict(role="sector", protocol="omada-bridge", gain_dbi=7, az_beamwidth_deg=70, el_beamwidth_deg=70, max_clients=4),
    "TP-Link EAP215-Bridge": dict(role="sector", protocol="omada-bridge", gain_dbi=11, az_beamwidth_deg=35, el_beamwidth_deg=35, max_clients=4),
    "Ubiquiti Rocket Prism + AM-5AC21-60": dict(role="sector", protocol="airmax-ac", gain_dbi=21, az_beamwidth_deg=60, el_beamwidth_deg=4),
    "Ubiquiti LiteBeam 5AC Gen2": dict(role="client", protocol="airmax-ac", gain_dbi=23, az_beamwidth_deg=7, el_beamwidth_deg=7, aim="peer"),
    "MikroTik mANTBox ax 15s": dict(role="sector", protocol="wifi-ax", gain_dbi=15, az_beamwidth_deg=120, el_beamwidth_deg=10),
    "MikroTik SXTsq 5 ax": dict(role="client", protocol="wifi-ax", gain_dbi=16, az_beamwidth_deg=23, el_beamwidth_deg=23, aim="peer"),
    "Cambium ePMP 4500L + generic sector": dict(role="sector", protocol="epmp", gain_dbi=17, az_beamwidth_deg=90, el_beamwidth_deg=10),
    "Cambium Force 4525": dict(role="client", protocol="epmp", gain_dbi=25, az_beamwidth_deg=8, el_beamwidth_deg=8, aim="peer"),
}

for _name, _entry in CATALOG.items():
    PRESETS[_name] = dict(_entry['radio'])

SOURCES = {
    "TP-Link": "https://www.tp-link.com/us/business-networking/solution/wifi-for-farms-barns-parking-lots/",
    "CPE710": "https://www.tp-link.com/us/business-networking/outdoor-radio/cpe710/v1/",
    "Ubiquiti": "https://techspecs.ui.com/uisp/wireless",
    "MikroTik": "https://mikrotik.com/product/mantbox_ax_15s",
    "Cambium": "https://www.cambiumnetworks.com/products/epmp/",
}


def make_radio(site_id, preset, name=None):
    values = dict(PRESETS[preset])
    # Unverified pattern widths remain explicit assumptions, not measured patterns.
    assumptions = "TX 20 dBm and RX -85 dBm are planning assumptions; replace for the selected bandwidth/MCS. Quadratic antenna pattern is approximate."
    if preset in CATALOG:
        entry = CATALOG[preset]
        assumptions += f" {entry['status']}; catalog checked {entry['checked']}. {entry['note']}"
    else:
        assumptions += " Beamwidths are provisional editable approximations until verified against the specific antenna datasheet."
    return Radio(name=name or preset, site_id=site_id, equipment=preset, assumptions=assumptions, **values)
