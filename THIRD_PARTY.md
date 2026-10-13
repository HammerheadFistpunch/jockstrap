# Source provenance and licenses

Source repository: https://github.com/HammerheadFistpunch/Viewshed

Pinned donor commit: `b07cde8c32fc6d131bbc8d75adb802916f115696`
(branch `feature/microwave-propagation`, retrieved 2026-10-13).

- `jockstrap/vendor/viewshed_dem.py` is based on `dem_sources.py`.
  Only its independent source-tile acquisition helpers are used by Jockstrap.
  Its station/mosaic preparation interface is retained for provenance but unused.
  Jockstrap corrects one-degree tile IDs and TNM fallback matching to use USGS's
  northwest-corner naming. The donor's south-edge convention selected the tile
  one degree south when requested individually; the older area mosaic could mask it.
- `jockstrap/itm.py` adapts the isolated `_itm_loss_for_slice` computation and
  polarization initialization from `aprs_viewshed_utah_parallel.py`. It imports
  no APRS module. Fixed environmental assumptions are exposed in analysis warnings.
- `LICENSE` is copied from Viewshed (GNU GPL version 2). Jockstrap is distributed
  under that license; preserve these notices when redistributing borrowed code.

External runtime dependencies retain their own licenses: NumPy, Rasterio/GDAL,
pyproj/PROJ, Requests, Matplotlib, TkinterMapView and itmlogic. Windows packages
also include those libraries and their licensing materials. This notice is not a
substitute for dependency notices included with a distributable package.

Planning references:

- ITU-R P.526-16, diffraction and knife-edge approximation:
  https://www.itu.int/rec/R-REC-P.526/en
- ITU-R P.530-19, fixed line-of-sight link design (future availability work):
  https://www.itu.int/rec/R-REC-P.530/en
- NTIA ITM: https://github.com/NTIA/itm
- USGS 3DEP downloads use the source URLs and TNMAccess catalog in the donor module.

Equipment references are listed in `jockstrap/equipment.py`. Exact rate/power,
sensitivity and measured antenna profiles still need catalog verification before
presets can be described as calibrated hardware models.
