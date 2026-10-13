# Jockstrap

Standalone desktop microwave **PtMP / PtP network planner**, based on selected
terrain components from Signal Peak (Viewshed). No APRS station acquisition,
seeds, station corrections, callsigns or dependencies on the Signal Peak app.

Initial development version: **0.1.0**. This is a working planning foundation,
not a calibrated commercial link-design package.

## Run

Python 3.11+ with Tk is required. On Windows, the standard Python installer
includes Tk. On Linux install your distribution's `python3-tk` package.

```powershell
python -m pip install -r requirements.txt
python -m jockstrap
```

Or double-click `run_jockstrap.bat` after installing dependencies.
An editable package installation also provides a `jockstrap` command:

```powershell
python -m pip install -e .
jockstrap examples/sector_network.json
```

The Windows workflow builds automatically on pushes to `main` and can also be
run manually under GitHub Actions. Download the **Jockstrap-Windows-0.1.0** artifact,
extract the ZIP and run **Jockstrap.exe**. It is a single portable executable;
no Python installation is needed. The build tests the packaged terrain/ITM
calculations, desktop map and terrain-profile window before uploading it.

The executable bundles this README, licensing notices and the example project.
`Jockstrap.exe --self-test --self-test-report report.json` runs its offline smoke
checks. The bundled tests do not verify Internet tile availability or real-world
radio accuracy. Build configuration is maintained in `jockstrap.spec`.

## First project

1. Right-click the map to add a site, or enter latitude/longitude with **Add site**.
2. Select the site and choose **Add radio**. A site can host multiple radios.
3. For the central AP choose a sector preset, height, frequency/channel width,
   fixed azimuth and tilt. Angles use true north; positive tilt points upward.
4. Add client sites and radios. Choose **peer** aiming to align each client with
   its one linked radio. A sector remains fixed across all its clients.
5. Use **Connect radios** to draw each link. Set required reserve and additional
   combined system loss. Double-click a site/radio to edit it, then recalculate.
6. Select a local metre-elevation GeoTIFF or enable **USGS terrain** for CONUS.
   **Path settings** controls effective Earth radius and sample spacing.
7. **Analyze network**, then double-click a link to inspect both signal directions,
   aiming, clearance and the terrain/Fresnel profile. Export results as JSON.
8. Save the network as a versioned JSON project. Results are recalculated, not
   loaded as if they were current after an equipment/location edit.

Wedges show antenna orientation, **not predicted coverage or range**. The map
uses an Internet basemap; coordinates and local terrain analysis work offline.

## Equipment

Starting presets cover generic sectors/dishes, TP-Link CPE710 and Omada bridges,
Ubiquiti airMAX, MikroTik ax and Cambium ePMP. Radio properties stay editable.
TX power and receiver threshold are explicitly **planning assumptions**, not
guaranteed manufacturer specifications for a bandwidth/modulation. Some antenna
beamwidths are also provisional approximations; their equipment notes say so.

Changing a preset changes its antenna/role/protocol fields. It does not secretly
apply a maximum TX power, select an MCS, or overwrite mounting height/aim.
Change an Omada bridge's role to client and aim to peer when using it remotely.
Known Omada four-client limits are validated. Protocol-family and frequency/
channel mismatches prevent a link from being labelled as meeting planning checks.
Family compatibility is a preliminary check, not a complete firmware compatibility
matrix. Generic/custom radio interoperability remains unverified.

## Calculation scope

- WGS84 geodesic distances/bearings, terrain elevation and per-radio AGL heights.
- Native source-tile samples along each path, without an area mosaic or terrain
  resampling. Automatic USGS downloads reuse Viewshed's downloader/catalog recovery.
- Effective Earth curvature, sightline and 60% first-Fresnel clearance.
- Free-space loss plus a **dominant single knife-edge approximation using the
  P.526 knife-edge equation**. This does **not** implement the full general-path
  P.526 model; multiple/rounded obstacles need later work.
- Optional ITM median loss as an **alternative**, never added to knife-edge loss.
  Initial ITM comparison uses fixed environmental constants and 1–200 km paths.
- Both antenna pointing losses, feeder/additional losses, editable polarization
  mismatch assumption, forward/reverse received power and margin after reserve.

Without terrain, results are **provisional free-space estimates**. Missing terrain
withholds the estimate instead of substituting flat ground. Obstructed links are
flagged even when their predicted signal exceeds the threshold. Terrain resolution,
DEM vertical units/datums and absent trees/buildings limit accuracy. Local rasters
must contain metre elevations in a consistent vertical datum across the path;
files with no vertical-unit metadata are assumed to be metres.

The initial path engine accepts 1–10 GHz and 1 m–200 km links. It does not estimate
throughput, sector airtime, external interference, rain fading, regulatory power
limits, automatic routing, availability percentages or hardware beamforming gain.
Dual polarization adds no arbitrary gain; the ITM alternative checks both H/V and
uses the weaker prediction when both endpoints are dual.

## Headless analysis

```powershell
python -m jockstrap examples/sector_network.json --analyze
python -m jockstrap examples/sector_network.json --analyze --dem C:\terrain\area.tif --output results.json
python -m jockstrap examples/sector_network.json --analyze --usgs --model itm --output results.json
```

Source-tile progress goes to stderr; stdout is JSON. A terrain/analysis failure
produces an explicit error record and exit code 2. Links failing planning checks
still produce successful calculations; inspect their statuses/margins.

```powershell
python -m unittest discover -s tests -v
```

See [ARCHITECTURE.md](docs/ARCHITECTURE.md), [ROADMAP.md](docs/ROADMAP.md) and
[THIRD_PARTY.md](THIRD_PARTY.md) for boundaries, source provenance and next steps.
