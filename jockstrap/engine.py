"""Explicit, bidirectional microwave link estimates."""
from dataclasses import asdict, dataclass, field
import math

from .terrain import GEOD
from .compatibility import compatibility

C = 299792458
EARTH_RADIUS_M = 6371000


def knife_edge_loss(v):
    """ITU-R P.526 knife-edge approximation; v=0 gives about 6 dB."""
    if v <= -0.78:
        return 0.
    return 6.9 + 20 * math.log10(math.sqrt((v - 0.1) ** 2 + 1) + v - 0.1)


def antenna_loss(radio, bearing, elevation):
    if radio.aim == "peer":
        return 0.
    az = (bearing - radio.azimuth_deg + 180) % 360 - 180
    if radio.antenna_pattern == 'omni':
        az = 0
    el = elevation - radio.tilt_deg
    return min(radio.pattern_floor_db,
               12 * (az / radio.az_beamwidth_deg) ** 2 + 12 * (el / radio.el_beamwidth_deg) ** 2)


@dataclass
class Direction:
    tx_radio: str
    rx_radio: str
    rx_dbm: float
    threshold_dbm: float
    margin_db: float
    tx_aim_loss_db: float
    rx_aim_loss_db: float


@dataclass
class LinkResult:
    link_id: str
    name: str
    distance_km: float
    status: str
    model: str
    forward: Direction
    reverse: Direction
    fspl_db: float
    path_loss_db: float
    diffraction_db: float | None
    min_fresnel_clearance_m: float | None
    min_los_clearance_m: float | None
    bearing_a_deg: float
    bearing_b_deg: float
    elevation_a_deg: float
    elevation_b_deg: float
    warnings: list[str] = field(default_factory=list)
    profile: dict | None = None
    compatibility: dict | None = None

    def to_dict(self):
        return asdict(self)


def analyze_link(project, link, profile=None, model="knife-edge"):
    project.validate()
    if model not in ("knife-edge", "itm"):
        raise ValueError("Choose knife-edge or itm model.")
    radios = {r.id: r for r in project.radios}
    sites = {s.id: s for s in project.sites}
    a, b = radios[link.a_radio_id], radios[link.b_radio_id]
    sa, sb = sites[a.site_id], sites[b.site_id]
    bearing_a, bearing_b, distance = GEOD.inv(sa.lon, sa.lat, sb.lon, sb.lat)
    if not 1 <= distance <= 200000:
        raise ValueError("Initial path engine supports 1 m–200 km links.")
    warnings = [a.assumptions, b.assumptions,
                "No throughput, airtime, interference, rain fading or availability prediction."]
    pairing = compatibility(a,b)
    compatible = pairing['status'] != 'Incompatible'
    warnings.append(f"Compatibility: {pairing['status']} — {pairing['reason']}")
    pol_loss = 0.
    if {a.polarization, b.polarization} == {"horizontal", "vertical"}:
        warnings.append("Cross-polarized H/V endpoints: 20 dB mismatch is an assumed value, not a hardware specification.")
        pol_loss = 20.
    elif a.polarization != b.polarization:
        warnings.append("Dual-to-single polarization: one matching channel only; multiple-stream operation is not established.")
    fspl = 32.45 + 20 * math.log10(a.frequency_ghz * 1000) + 20 * math.log10(distance / 1000)
    clearance_los = clearance_fresnel = diffraction = None
    plot = None
    za, zb = a.height_m, b.height_m
    path_loss = fspl
    model_name = "Ideal free space — terrain not evaluated"
    if profile is not None:
        profile.validate(distance)
        za += profile.elevations_m[0]
        zb += profile.elevations_m[-1]
        wavelength = C / (a.frequency_ghz * 1e9)
        effective_radius = EARTH_RADIUS_M * project.earth_k
        los, terrain, fresnel, clearances, fresnel_clearances, vs = [], [], [], [], [], []
        for s, z in zip(profile.distances_m, profile.elevations_m):
            line = za + (zb - za) * s / distance
            curved_z = z + s * (distance - s) / (2 * effective_radius)
            radius = math.sqrt(max(0, wavelength * s * (distance - s) / distance))
            los.append(line)
            terrain.append(curved_z)
            fresnel.append(radius)
            if 0 < s < distance:
                clearances.append(line - curved_z)
                fresnel_clearances.append(line - curved_z - 0.6 * radius)
                vs.append((curved_z - line) * math.sqrt(2 / (radius ** 2)))
        if not vs:
            raise ValueError("Terrain profile needs intermediate samples to assess clearance.")
        clearance_los = min(clearances)
        clearance_fresnel = min(fresnel_clearances)
        diffraction = knife_edge_loss(max(vs))
        path_loss = fspl + diffraction
        model_name = "Free space + P.526 dominant single knife-edge approximation"
        warnings.append("Dominant knife-edge approximation does not implement the full P.526 general terrain method; rounded/multiple ridges may differ.")
        warnings.append(f"Terrain source resolution about {profile.resolution_m:.1f} m; trees and buildings are absent unless included in the raster.")
        if project.sample_spacing_m > profile.resolution_m * 1.5:
            warnings.append("Profile sampling is coarser than the source terrain; small obstacles may be missed.")
        plot = dict(distance_m=profile.distances_m, ground_m=profile.elevations_m,
                    curved_terrain_m=terrain, sightline_m=los, fresnel_radius_m=fresnel,
                    source=profile.source, source_resolution_m=profile.resolution_m)
        if model == "itm":
            from .itm import path_loss as itm_loss
            polarizations = [0, 1] if a.polarization == b.polarization == "dual" else [int("vertical" in (a.polarization, b.polarization))]
            losses = [itm_loss(profile, a.frequency_ghz, a.height_m, b.height_m, p) for p in polarizations]
            path_loss = max(x[0] for x in losses)
            diffraction = None
            model_name = "ITM median total path loss (dual: weaker H/V channel)"
            warnings = [w for w in warnings if not w.startswith("Dominant knife-edge")]
            warnings.append("ITM comparison uses fixed climate 5, refractivity 301 N-units and ground constants; terrain geometry uses the project's Earth k separately.")
            if any(flag for _, flag in losses):
                warnings.append("ITM reported a parameter warning; inspect inputs before relying on this estimate.")
    else:
        if model == "itm":
            raise ValueError("ITM requires terrain; select a DEM or enable USGS terrain.")
        warnings.append("Terrain not evaluated. Free-space signal is provisional; LOS/Fresnel clearance is unknown.")
    curve = distance ** 2 / (2 * EARTH_RADIUS_M * project.earth_k)
    ea = math.degrees(math.atan2(zb - za - curve, distance))
    eb = math.degrees(math.atan2(za - zb - curve, distance))
    aim_a = antenna_loss(a, bearing_a, ea)
    aim_b = antenna_loss(b, bearing_b, eb)
    total_loss = path_loss + aim_a + aim_b + a.feeder_loss_db + b.feeder_loss_db + link.extra_loss_db + pol_loss
    def direction(tx, rx, tx_aim, rx_aim):
        signal = tx.tx_power_dbm + tx.gain_dbi + rx.gain_dbi - total_loss
        return Direction(tx.name, rx.name, signal, rx.rx_threshold_dbm,
                         signal - rx.rx_threshold_dbm - link.reserve_db, tx_aim, rx_aim)
    forward, reverse = direction(a, b, aim_a, aim_b), direction(b, a, aim_b, aim_a)
    if not compatible:
        status = "Incompatible settings"
    elif profile is None:
        status = "Provisional — terrain required"
    elif clearance_los < 0:
        status = "Terrain obstructed"
    elif min(forward.margin_db, reverse.margin_db) < 0:
        status = "Insufficient margin"
    elif clearance_fresnel < 0:
        status = "Fresnel clearance limited"
    else:
        status = "Meets planning checks"
    return LinkResult(link.id, link.name, distance / 1000, status, model_name, forward, reverse,
                      fspl, path_loss, diffraction, clearance_fresnel, clearance_los,
                      bearing_a % 360, bearing_b % 360, ea, eb, list(dict.fromkeys(warnings)), plot, pairing)


def analyze_network(project, terrain=None, model="knife-edge"):
    project.validate()
    sites = {s.id: s for s in project.sites}
    radios = {r.id: r for r in project.radios}
    results = []
    for link in project.links:
        try:
            profile = terrain.sample(sites[radios[link.a_radio_id].site_id], sites[radios[link.b_radio_id].site_id]) if terrain else None
            results.append(analyze_link(project, link, profile, model).to_dict())
        except Exception as exc:
            results.append(dict(link_id=link.id, name=link.name, status="Analysis unavailable", error=str(exc)))
    return results
