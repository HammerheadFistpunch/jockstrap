"""Offline smoke test running inside the actual packaged executable."""
import math
from pathlib import Path
import tempfile


def run_self_test(gui=True):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from . import __version__
    from .engine import analyze_network
    from .equipment import make_radio
    from .project import Project, Site, Link
    from .terrain import RasterTerrain
    checks = []
    a, b = Site("Smoke AP", 40.6, -111.9), Site("Smoke client", 40.6, -111.875)
    ra, rb = make_radio(a.id, "Generic sector"), make_radio(b.id, "Generic client dish")
    ra.azimuth_deg, ra.height_m, rb.height_m = 90, 40, 40
    project = Project(sites=[a,b], radios=[ra,rb], links=[Link("Smoke link",ra.id,rb.id)])
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project_path, dem = root / "project.json", root / "terrain.tif"
        project.save(project_path)
        project = Project.load(project_path)
        checks.append("Project save/load")
        with rasterio.open(dem, "w", driver="GTiff", width=100, height=100, count=1,
                           dtype="float32", crs="EPSG:4326", transform=from_origin(-112,40.7,.002,.002), nodata=-9999) as dst:
            dst.write(np.full((100,100),100,dtype="float32"),1)
        terrain = RasterTerrain(dem)
        results = analyze_network(project, terrain)
        if len(results) != 1 or results[0].get("status") != "Meets planning checks":
            raise RuntimeError(f"Packaged terrain/link check failed: {results}")
        checks.append("Rasterio/PROJ terrain and bidirectional link analysis")
        itm = analyze_network(project, terrain, "itm")
        if "error" in itm[0] or not math.isfinite(itm[0]["path_loss_db"]):
            raise RuntimeError(f"Packaged ITM check failed: {itm}")
        checks.append("ITM alternative path calculation")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        figure = Figure(figsize=(3,2))
        figure.add_subplot(111).plot([0,1],[0,1])
        FigureCanvasAgg(figure).print_png(str(root / "profile.png"))
        checks.append("Matplotlib raster renderer")
        if gui:
            from .ui import Planner
            app = Planner(project)
            try:
                if app.map is None:
                    raise RuntimeError("Map widget failed to initialize")
                app.withdraw()
                app.results = {results[0]["link_id"]: results[0]}
                app.refresh()
                app.links_table.selection_set(project.links[0].id)
                app.inspect_link()
                app.radio_catalog()
                app.update_idletasks()
                app.update()
                checks.append("Tk editor, map widget, radio catalog and TkAgg terrain-profile window")
            finally:
                app.destroy()
    example = Path(__file__).resolve().parents[1] / "examples" / "sector_network.json"
    if not example.is_file():
        raise RuntimeError("Bundled example project is missing")
    Project.load(example)
    checks.append("Bundled example and project schema")
    return dict(success=True, version=__version__, gui_tested=gui, checks=checks)
