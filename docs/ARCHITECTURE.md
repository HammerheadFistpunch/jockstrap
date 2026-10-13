# Architecture

Jockstrap is an independent repository and application. It does not modify or
import the Signal Peak application. A later shared terrain/propagation library
can be extracted after the interfaces have proved useful.

| Module | Responsibility |
| --- | --- |
| `project.py` | Versioned site/radio/link schema, validation, atomic project saves |
| `equipment.py` | Editable antenna presets and explicit assumptions |
| `terrain.py` | Geodesic path sampling, local GeoTIFFs, CONUS 3DEP source tiles |
| `vendor/viewshed_dem.py` | Pinned donor downloader and TNM catalog recovery |
| `engine.py` | Geometry, Fresnel clearance, pointing losses, bidirectional budgets |
| `itm.py` | Optional alternative median ITM total-loss estimate |
| `ui.py` | Native map, object editors, link inspector and background calculations |
| `cli.py` | Desktop launcher and headless project analysis |

A **site** is a location. A **radio** belongs to a site and owns its antenna,
mounting height, operating channel and pointing. A **link** connects two radios,
not two site-level antennas. A sector serves multiple links with one fixed aim.
A client can aim at its one peer. Two backhaul directions at a relay can use
different radios. This avoids changing a sector's direction per client.

The propagation engine accepts a validated `Profile`, independent of raster
loading or the UI. Missing terrain is an error, not an interpolated flat path.
Reports contain loss terms, source resolution, geometry, status and assumptions.
No RF protocol stack or airtime scheduler is simulated.

Background jobs analyze an immutable project snapshot. A revision comparison
discards results if the project or calculation options change before completion.
Edits clear results immediately. Project saves preserve IDs and relationships;
terrain caches and derived results are external to the project file.

Safety of the boundary here means software separation: no APRS dependencies,
independent releases and tests, and no code writes to the Viewshed repository.
