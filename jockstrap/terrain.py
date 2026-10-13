"""Sample only the requested geodesic paths; retain native DEM fidelity."""
from dataclasses import dataclass
from pathlib import Path
from contextlib import ExitStack
import math
import os

from pyproj import Geod, Transformer

GEOD = Geod(ellps="WGS84")


@dataclass
class Profile:
    distances_m: list[float]
    elevations_m: list[float]
    source: str
    resolution_m: float

    def validate(self, distance):
        if len(self.distances_m) < 2 or len(self.distances_m) != len(self.elevations_m):
            raise ValueError("Terrain profile needs matching distances and elevations.")
        if not all(math.isfinite(x) for x in self.distances_m + self.elevations_m):
            raise ValueError("Terrain profile contains missing/non-finite samples.")
        if abs(self.distances_m[0]) > 0.001 or abs(self.distances_m[-1] - distance) > 0.1:
            raise ValueError("Terrain profile must include both exact endpoints.")
        if any(a >= b for a, b in zip(self.distances_m, self.distances_m[1:])):
            raise ValueError("Terrain distances must increase.")


def cache_directory():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache")))
    return base / "Jockstrap" / "terrain"


class RasterTerrain:
    def __init__(self, path=None, cache=None, spacing_m=30):
        self.path = Path(path) if path else None
        self.cache = Path(cache) if cache else cache_directory()
        self.spacing_m = float(spacing_m)

    def sample(self, a, b):
        bearing, _, distance = GEOD.inv(a.lon, a.lat, b.lon, b.lat)
        if not 1 <= distance <= 200000:
            raise ValueError("Initial path engine supports links from 1 m to 200 km.")
        segments = max(2, math.ceil(distance / self.spacing_m))
        if segments > 40000:
            raise ValueError("Too many terrain samples; increase sample spacing.")
        points = [(a.lon, a.lat), *GEOD.npts(a.lon, a.lat, b.lon, b.lat, segments - 1), (b.lon, b.lat)]
        elevations = []
        resolutions = []
        sources = set()
        import rasterio
        from rasterio.windows import Window
        with ExitStack() as stack:
            datasets = {}
            for lon, lat in points:
                if self.path:
                    source = self.path
                else:
                    # Reuse Viewshed's source-tile download/catalog recovery,
                    # with the USGS northwest-corner naming correction.
                    # No mosaics, station lists, seeds or resampling are needed.
                    if not (24 <= lat <= 50 and -125 <= lon <= -66):
                        raise ValueError("Automatic 3DEP terrain currently supports CONUS. Select a local metre-elevation GeoTIFF elsewhere.")
                    from .vendor.viewshed_dem import _download_tile
                    self.cache.mkdir(parents=True, exist_ok=True)
                    key = (math.floor(lat) + 1, math.ceil(-lon))
                    if key not in datasets:
                        source = _download_tile(*key, self.cache)
                    else:
                        source = datasets[key][2]
                key = str(source) if self.path else key
                if key not in datasets:
                    src = stack.enter_context(rasterio.open(source))
                    if src.crs is None:
                        raise ValueError("DEM needs a coordinate reference system.")
                    units = src.units[0] if src.units else None
                    if units and units.lower() not in ("m", "meter", "metre", "meters", "metres"):
                        raise ValueError("DEM elevations must be in metres.")
                    datasets[key] = (src, Transformer.from_crs("EPSG:4326", src.crs, always_xy=True), source)
                src, transform, source = datasets[key]
                x, y = transform.transform(lon, lat)
                row, col = src.index(x, y)
                if not (0 <= row < src.height and 0 <= col < src.width):
                    from rasterio.warp import transform_bounds
                    west, south, east, north = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
                    kind = 'Selected DEM' if self.path else 'Downloaded USGS tile'
                    remedy = 'Select a DEM covering both endpoints and the entire path, or enable USGS terrain.' if self.path else 'The downloaded tile has unexpected bounds; inspect or replace this cached tile.'
                    raise ValueError(f"{kind} does not cover the complete link: {Path(source).name}. "
                                     f"First uncovered point: latitude {lat:.6f}, longitude {lon:.6f}. "
                                     f"DEM bounds: latitude {south:.6f}–{north:.6f}, longitude {west:.6f}–{east:.6f}. {remedy}")
                sample = src.read(1, window=Window(col, row, 1, 1), masked=True)
                if sample.mask.any() or not math.isfinite(float(sample[0, 0])):
                    raise ValueError("DEM has missing terrain on this path; signal estimate withheld.")
                elevations.append(float(sample[0, 0]))
                if src.crs.is_geographic:
                    _, _, rx = GEOD.inv(lon, lat, lon + abs(src.res[0]), lat)
                    _, _, ry = GEOD.inv(lon, lat, lon, min(89.9999, lat + abs(src.res[1])))
                    resolutions.append(max(rx, ry))
                else:
                    resolutions.append(max(abs(r) for r in src.res) * src.crs.linear_units_factor[1])
                sources.add(str(source))
        return Profile([i * distance / segments for i in range(segments + 1)], elevations,
                       "; ".join(sorted(sources)), max(resolutions))
