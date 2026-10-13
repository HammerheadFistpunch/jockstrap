"""Versioned network projects; independent of APRS and the application UI."""
from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import uuid


def new_id():
    return uuid.uuid4().hex


def bounded(name, value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a finite number between {low} and {high}.")


@dataclass
class Site:
    name: str
    lat: float
    lon: float
    id: str = field(default_factory=new_id)


@dataclass
class Radio:
    name: str
    site_id: str
    role: str = "client"
    equipment: str = "Generic client dish"
    protocol: str = "custom"
    frequency_ghz: float = 5.8
    channel_width_mhz: float = 20
    tx_power_dbm: float = 20
    rx_threshold_dbm: float = -85
    gain_dbi: float = 23
    az_beamwidth_deg: float = 9
    el_beamwidth_deg: float = 7
    pattern_floor_db: float = 30
    height_m: float = 10
    polarization: str = "dual"
    feeder_loss_db: float = 0
    aim: str = "fixed"
    azimuth_deg: float = 0
    tilt_deg: float = 0
    max_clients: int | None = None
    assumptions: str = "TX power and RX threshold are editable planning assumptions."
    id: str = field(default_factory=new_id)


@dataclass
class Link:
    name: str
    a_radio_id: str
    b_radio_id: str
    reserve_db: float = 15
    extra_loss_db: float = 2
    id: str = field(default_factory=new_id)


@dataclass
class Project:
    name: str = "New microwave network"
    sites: list[Site] = field(default_factory=list)
    radios: list[Radio] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    terrain_path: str = ""
    earth_k: float = 4 / 3
    sample_spacing_m: float = 30
    schema_version: int = 1

    def validate(self):
        if self.schema_version != 1:
            raise ValueError("Unsupported project schema version.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Project name is required.")
        bounded("Effective Earth radius factor", self.earth_k, 0.5, 3)
        bounded("Terrain sample spacing", self.sample_spacing_m, 5, 1000)
        seen = set()
        for obj in [*self.sites, *self.radios, *self.links]:
            if not isinstance(obj.id, str) or not obj.id or obj.id in seen:
                raise ValueError("Project IDs must be nonempty and unique.")
            seen.add(obj.id)
            if not isinstance(obj.name, str) or not obj.name.strip():
                raise ValueError("Every site, radio and link needs a name.")
        sites = {s.id: s for s in self.sites}
        radios = {r.id: r for r in self.radios}
        for site in self.sites:
            bounded("Latitude", site.lat, -90, 90)
            bounded("Longitude", site.lon, -180, 180)
        limits = dict(frequency_ghz=(1, 10), channel_width_mhz=(5, 160),
                      tx_power_dbm=(-20, 60), rx_threshold_dbm=(-140, -20), gain_dbi=(-10, 60),
                      az_beamwidth_deg=(1, 360), el_beamwidth_deg=(1, 180),
                      pattern_floor_db=(0, 60), height_m=(0.5, 500), feeder_loss_db=(0, 30),
                      azimuth_deg=(0, 360), tilt_deg=(-90, 90))
        for radio in self.radios:
            if radio.site_id not in sites:
                raise ValueError("Radio references a missing site.")
            if radio.role not in ("sector", "client", "ptp"):
                raise ValueError("Radio role must be sector, client or ptp.")
            if radio.aim not in ("fixed", "peer") or (radio.role == "sector" and radio.aim != "fixed"):
                raise ValueError("Sectors need a fixed aim; clients/PTP may aim at their peer.")
            if radio.polarization not in ("horizontal", "vertical", "dual"):
                raise ValueError("Choose horizontal, vertical or dual polarization.")
            if radio.max_clients is not None and (type(radio.max_clients) is not int or radio.max_clients < 1):
                raise ValueError("Client limit must be a positive integer.")
            for key, (low, high) in limits.items():
                bounded(key.replace('_', ' '), getattr(radio, key), low, high)
        pairs = set()
        client_counts = {}
        for link in self.links:
            if link.a_radio_id not in radios or link.b_radio_id not in radios:
                raise ValueError("Link references a missing radio.")
            a, b = radios[link.a_radio_id], radios[link.b_radio_id]
            if a.site_id == b.site_id:
                raise ValueError("A wireless link must connect different sites.")
            pair = tuple(sorted((a.id, b.id)))
            if pair in pairs:
                raise ValueError("Duplicate radio link.")
            pairs.add(pair)
            for radio in (a, b):
                client_counts[radio.id] = client_counts.get(radio.id, 0) + 1
            bounded("Link reserve", link.reserve_db, 0, 60)
            bounded("Additional link losses", link.extra_loss_db, 0, 60)
        for radio in self.radios:
            count = client_counts.get(radio.id, 0)
            if radio.aim == "peer" and count > 1:
                raise ValueError(f"{radio.name}: a peer-aimed radio can have only one link. Add another radio or choose fixed aim.")
            if radio.max_clients is not None and count > radio.max_clients:
                raise ValueError(f"{radio.name}: exceeds its {radio.max_clients}-client limit.")

    def to_dict(self):
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Project must be a JSON object.")
        values = dict(data)
        for key, kind in (("sites", Site), ("radios", Radio), ("links", Link)):
            values[key] = [kind(**item) for item in values.get(key, [])]
        project = cls(**values)
        project.validate()
        return project

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path):
        path = Path(path)
        content = json.dumps(self.to_dict(), indent=2, allow_nan=False) + "\n"
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
