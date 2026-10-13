# Microwave planner roadmap

## Initial foundation (0.1.0)

- Independent native desktop editor and versioned network projects.
- Multiple radios per site; fixed sectors and automatically aimed clients.
- Manually connected links; forward/reverse budgets and visible assumptions.
- Native DEM path sampling, USGS source-tile reuse and local rasters.
- Terrain/Fresnel profiles and an explicitly limited knife-edge estimate.
- Optional alternative median ITM model; no double counting of diffraction.
- Headless JSON reports, example network, unit/integration tests and Windows build workflow.

## Next: validate the core experience

1. Windows GUI/package smoke test on Pat's machine, including real DEM downloads.
2. Verify equipment TX power per stream versus aggregate power, per-MCS/per-width
   sensitivity, antenna patterns and protocol-specific limits for all named presets.
3. Compare clear and obstructed real links against field RSSI measurements.
4. Improve map editing: draggable sites, direct radio-to-radio link creation,
   project naming and clearer panels for equipment assumptions/loss terms.

## Propagation improvements

- Full P.526 general-path/multiple-obstacle treatment, with reference comparisons.
- Documented vertical datum handling, higher-resolution DEM sources, clutter inputs.
- Measured H/V antenna patterns and explicit cross-polar discrimination.
- Configurable ITM environment parameters and parameter warning handling.
- P.530 fading/availability and atmospheric/rain models within their valid ranges.

## Network planning

- Candidate-link discovery and sector coverage shading.
- Hardware compatibility matrices and channel/frequency/EIRP constraints.
- Sector airtime demand, shared-capacity estimates and channel-reuse analysis.
- Relay routes, alternative paths and connectivity summaries.
- GIS/KMZ reports and project import/export.

Possible future convergence with Signal Peak should share stable data/terrain
libraries first, rather than couple either application to the other's UI.
