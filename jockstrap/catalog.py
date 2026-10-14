"""Unified transceiver catalog; manufacturer datasets remain independent."""
from .tplink_catalog import CATALOG as TPLINK
from .wireless_catalog import CATALOG as OTHER

CATALOG = {**{name: dict(entry, brand='TP-Link') for name, entry in TPLINK.items()}, **OTHER}
