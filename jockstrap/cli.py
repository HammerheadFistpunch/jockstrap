"""Launch the desktop editor or analyze a saved project without a GUI."""
import argparse
import json
from pathlib import Path

from .project import Project


def main():
    parser = argparse.ArgumentParser(description="Jockstrap microwave network planner")
    parser.add_argument("project", nargs="?", help="Network project JSON")
    parser.add_argument("--analyze", action="store_true", help="Analyze and print a JSON report without opening the editor")
    parser.add_argument("--dem", help="Local GeoTIFF with elevations in metres")
    parser.add_argument("--usgs", action="store_true", help="Download required USGS 3DEP source tiles (CONUS)")
    parser.add_argument("--model", choices=("knife-edge", "itm"), default="knife-edge")
    parser.add_argument("--output", help="Save the JSON analysis report")
    args = parser.parse_args()
    try:
        project = Project.load(args.project) if args.project else Project()
        if args.dem:
            project.terrain_path = str(Path(args.dem).resolve())
        elif project.terrain_path and args.project and not Path(project.terrain_path).is_absolute():
            project.terrain_path = str((Path(args.project).resolve().parent / project.terrain_path).resolve())
        if args.analyze:
            if not args.project:
                parser.error("--analyze needs a project file")
            from .engine import analyze_network
            from .terrain import RasterTerrain
            terrain = RasterTerrain(project.terrain_path, spacing_m=project.sample_spacing_m) if project.terrain_path or args.usgs else None
            # Donor download progress goes to stderr; stdout stays valid JSON.
            import contextlib, sys
            with contextlib.redirect_stdout(sys.stderr):
                results = analyze_network(project, terrain, args.model)
            report = json.dumps(dict(project=project.name, results=results), indent=2, allow_nan=False)
            if args.output:
                Path(args.output).write_text(report + "\n", encoding="utf-8")
            else:
                print(report)
            if any("error" in result for result in results):
                raise SystemExit(2)
        else:
            from .ui import Planner
            Planner(project, args.project, usgs=args.usgs, model=args.model).mainloop()
    except (ValueError, TypeError, OSError) as exc:
        parser.exit(2, f"Jockstrap: {exc}\n")
