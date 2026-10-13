import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from concurrent.futures import Future
from unittest.mock import patch

from jockstrap.engine import analyze_link, analyze_network, antenna_loss, knife_edge_loss
from jockstrap.equipment import make_radio
from jockstrap.project import Project, Site, Link
from jockstrap.terrain import GEOD, Profile, RasterTerrain


def network(distance=10000):
    a = Site('Sector site', 40.6, -111.9)
    lon, lat, _ = GEOD.fwd(a.lon, a.lat, 90, distance)
    b = Site('Remote site', lat, lon)
    ra = make_radio(a.id, 'Generic sector', 'Sector')
    ra.azimuth_deg, ra.az_beamwidth_deg, ra.height_m = 90, 90, 40
    rb = make_radio(b.id, 'Generic client dish', 'Client')
    rb.height_m = 40
    link = Link('Sector–client', ra.id, rb.id)
    return Project(sites=[a, b], radios=[ra, rb], links=[link])


def flat_profile(project, count=101):
    _, _, distance = GEOD.inv(project.sites[0].lon, project.sites[0].lat,
                              project.sites[1].lon, project.sites[1].lat)
    return Profile([i*distance/(count-1) for i in range(count)], [100.]*count, 'synthetic', 30)


class ProjectTests(unittest.TestCase):
    def test_roundtrip_multiple_radios_and_ids(self):
        project = network()
        project.radios.append(make_radio(project.sites[0].id, 'Generic client dish', 'Backhaul'))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'network.json'
            project.save(path)
            self.assertEqual(Project.load(path).to_dict(), project.to_dict())

    def test_invalid_coordinates_numbers_and_references(self):
        for field, value in (('lat', math.nan), ('lon', 200)):
            project = network()
            setattr(project.sites[0], field, value)
            with self.assertRaises(ValueError): project.validate()
        for field, value in (('tx_power_dbm', math.inf), ('height_m', 0), ('gain_dbi', True)):
            project = network()
            setattr(project.radios[0], field, value)
            with self.assertRaises(ValueError): project.validate()
        project = network()
        project.links[0].b_radio_id = 'missing'
        with self.assertRaises(ValueError): project.validate()

    def test_client_limit_and_peer_aim_constraints(self):
        project = network()
        project.radios[0].max_clients = 1
        client = copy.deepcopy(project.radios[1])
        client.id = 'new-client'
        project.radios.append(client)
        project.links.append(Link('Extra client', project.radios[0].id, client.id))
        with self.assertRaisesRegex(ValueError, 'client limit'): project.validate()
        project.radios[0].max_clients = None
        project.validate()
        project.radios[0].role, project.radios[0].aim = 'ptp', 'peer'
        with self.assertRaisesRegex(ValueError, 'only one link'): project.validate()

    def test_sector_cannot_reaim_itself_for_each_client(self):
        project = network()
        project.radios[0].aim = 'peer'
        with self.assertRaisesRegex(ValueError, 'fixed aim'): project.validate()

    def test_duplicate_links_and_schema_are_rejected(self):
        project = network()
        project.links.append(Link('Duplicate', project.radios[1].id, project.radios[0].id))
        with self.assertRaisesRegex(ValueError, 'Duplicate'): project.validate()
        with self.assertRaises(ValueError): Project.from_dict({'schema_version': 99})


class EngineTests(unittest.TestCase):
    def test_knife_edge_reference_values(self):
        self.assertEqual(knife_edge_loss(-.78), 0)
        self.assertAlmostEqual(knife_edge_loss(0), 6.03285220856)
        self.assertGreater(knife_edge_loss(1), knife_edge_loss(0))

    def test_antenna_half_power_and_wraparound(self):
        r = network().radios[0]
        r.azimuth_deg, r.az_beamwidth_deg = 350, 30
        self.assertAlmostEqual(antenna_loss(r, 5, 0), 3)
        self.assertEqual(antenna_loss(r, 170, 0), 30)
        r.aim = 'peer'
        self.assertEqual(antenna_loss(r, 170, 40), 0)

    def test_free_space_budget_and_asymmetric_reverse_link(self):
        project = network()
        project.radios[0].aim, project.radios[0].role = 'peer', 'ptp'
        project.radios[1].tx_power_dbm = 10
        result = analyze_link(project, project.links[0])
        self.assertAlmostEqual(result.fspl_db, 127.718559870, places=6)
        self.assertAlmostEqual(result.forward.rx_dbm, 20+16+23-result.fspl_db-2)
        self.assertAlmostEqual(result.reverse.rx_dbm, result.forward.rx_dbm-10)
        self.assertAlmostEqual(result.forward.margin_db, result.forward.rx_dbm+85-15)
        self.assertIn('Provisional', result.status)

    def test_flat_clearance_and_curvature(self):
        project = network()
        result = analyze_link(project, project.links[0], flat_profile(project))
        self.assertGreater(result.min_fresnel_clearance_m, 0)
        self.assertEqual(result.diffraction_db, 0)
        self.assertGreater(result.profile['curved_terrain_m'][50], 100)
        self.assertAlmostEqual(result.profile['sightline_m'][50], 140)

    def test_blocking_ridge_is_flagged_even_with_large_budget(self):
        project = network()
        profile = flat_profile(project)
        profile.elevations_m[50] = 160
        project.radios[0].tx_power_dbm = project.radios[1].tx_power_dbm = 50
        result = analyze_link(project, project.links[0], profile)
        self.assertEqual(result.status, 'Terrain obstructed')
        self.assertGreater(result.diffraction_db, 6)
        self.assertLess(result.min_los_clearance_m, 0)

    def test_both_antenna_directions_affect_signal(self):
        project = network(2000)
        before = analyze_link(project, project.links[0], flat_profile(project))
        project.radios[0].azimuth_deg = 270
        rotated = analyze_link(project, project.links[0], flat_profile(project))
        self.assertLess(rotated.forward.rx_dbm, before.forward.rx_dbm - 20)
        self.assertAlmostEqual(rotated.forward.rx_dbm-before.forward.rx_dbm, rotated.reverse.rx_dbm-before.reverse.rx_dbm)
        project.radios[1].aim, project.radios[1].azimuth_deg = 'fixed', 90
        client_rotated = analyze_link(project, project.links[0], flat_profile(project))
        self.assertLess(client_rotated.forward.rx_dbm, rotated.forward.rx_dbm - 20)

    def test_incompatible_protocol_and_channel_are_flagged(self):
        project = network()
        project.radios[0].protocol, project.radios[1].protocol = 'epmp', 'airmax-ac'
        self.assertEqual(analyze_link(project, project.links[0]).status, 'Incompatible settings')
        project.radios[1].protocol = 'epmp'
        project.radios[1].channel_width_mhz = 40
        self.assertEqual(analyze_link(project, project.links[0]).status, 'Incompatible settings')

    def test_dual_adds_no_extra_gain_and_cross_pol_is_explicit(self):
        project = network()
        dual = analyze_link(project, project.links[0])
        for radio in project.radios: radio.polarization = 'vertical'
        vertical = analyze_link(project, project.links[0])
        self.assertEqual(dual.forward.rx_dbm, vertical.forward.rx_dbm)
        project.radios[0].polarization = 'horizontal'
        crossed = analyze_link(project, project.links[0])
        self.assertAlmostEqual(crossed.forward.rx_dbm, vertical.forward.rx_dbm-20)

    def test_bad_terrain_withholds_estimate(self):
        project = network()
        class Missing:
            def sample(self, *_): raise ValueError('DEM has missing terrain')
        results = analyze_network(project, Missing())
        self.assertEqual(results[0]['status'], 'Analysis unavailable')
        self.assertNotIn('forward', results[0])
        profile = flat_profile(project)
        profile.elevations_m[10] = math.nan
        with self.assertRaises(ValueError): analyze_link(project, project.links[0], profile)

    def test_itm_is_alternative_not_additive(self):
        project = network()
        profile = flat_profile(project)
        from jockstrap.itm import path_loss
        expected = max(path_loss(profile, 5.8, 40, 40, p)[0] for p in (0,1))
        actual = analyze_link(project, project.links[0], profile, 'itm')
        self.assertEqual(actual.path_loss_db, expected)
        self.assertIsNone(actual.diffraction_db)
        self.assertIn('ITM', actual.model)
        with self.assertRaises(ValueError): analyze_link(project, project.links[0], model='itm')


class TerrainTests(unittest.TestCase):
    def test_automatic_usgs_tile_uses_northwest_corner_and_caches_it(self):
        import re
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin
        from jockstrap.vendor import viewshed_dem
        self.assertEqual(viewshed_dem._tile_id(41, 112), 'n41w112')
        downloads = []
        def download(requests, url, target, timeout=120):
            match = re.search(r'/n(\d+)w(\d+)/USGS_1_n\d+w\d+\.tif$', url)
            self.assertIsNotNone(match)
            north, west = map(int, match.groups())
            downloads.append((north, west))
            with rasterio.open(target, 'w', driver='GTiff', width=100, height=100, count=1,
                               dtype='float32', crs='EPSG:4269', transform=from_origin(-west,north,.01,.01), nodata=-9999) as dst:
                dst.write(np.full((100,100), 100, dtype='float32'), 1)
        with tempfile.TemporaryDirectory() as tmp:
            terrain = RasterTerrain(cache=tmp)
            project = network(2000)
            with patch.object(viewshed_dem, '_download_url', side_effect=download):
                first = terrain.sample(*project.sites)
                second = terrain.sample(*project.sites)
            self.assertEqual(downloads, [(41,112)])
            self.assertIn('USGS_1_n41w112.tif', first.source)
            self.assertEqual(first.elevations_m, second.elevations_m)

    def raster(self, path, nodata=False):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin
        data = np.full((300,300), 100, dtype='float32')
        if nodata: data[:] = -9999
        with rasterio.open(path, 'w', driver='GTiff', width=300, height=300, count=1,
                           dtype='float32', crs='EPSG:4326', transform=from_origin(-112,40.7,.001,.001), nodata=-9999) as dst:
            dst.write(data,1)

    def test_local_dem_profile_exact_endpoints_and_native_resolution(self):
        project = network()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'terrain.tif'
            self.raster(path)
            profile = RasterTerrain(path).sample(*project.sites)
            self.assertEqual(profile.elevations_m[0], 100)
            self.assertEqual(profile.elevations_m[-1], 100)
            self.assertGreater(profile.resolution_m, 100)
            self.assertGreater(len(profile.elevations_m), 300)
            self.assertAlmostEqual(profile.distances_m[-1], 10000, places=5)
            profile.validate(10000)

    def test_missing_dem_is_not_flat_terrain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'nodata.tif'
            self.raster(path, True)
            with self.assertRaisesRegex(ValueError, 'missing terrain'):
                RasterTerrain(path).sample(*network().sites)

    def test_outside_raster_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'terrain.tif'
            self.raster(path)
            with self.assertRaisesRegex(ValueError, 'does not cover'):
                RasterTerrain(path).sample(*network(50000).sites)

    def test_outside_dem_error_identifies_file_point_bounds_and_remedy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'terrain.tif'
            self.raster(path)
            with self.assertRaises(ValueError) as error:
                RasterTerrain(path).sample(*network(50000).sites)
            for fragment in ('Selected DEM', 'terrain.tif', 'First uncovered point', 'DEM bounds', 'enable USGS'):
                self.assertIn(fragment, str(error.exception))

    def test_cli_json_output_and_local_dem_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = network(2000)
            path, dem = Path(tmp)/'project.json', Path(tmp)/'terrain.tif'
            project.save(path)
            self.raster(dem)
            run = subprocess.run([sys.executable, '-m', 'jockstrap', str(path), '--analyze', '--dem', str(dem)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)['results'][0]
            self.assertEqual(result['status'], 'Meets planning checks')
            self.assertTrue(result['profile']['distance_m'])


class EditorJobTests(unittest.TestCase):
    def test_results_from_earlier_revision_are_discarded(self):
        from jockstrap.ui import Planner
        messages = []
        future = Future()
        future.set_result((3, [{'link_id': 'old', 'status': 'Meets planning checks'}]))
        ui = SimpleNamespace(future=future, revision=4, results={},
                             status=SimpleNamespace(set=messages.append),
                             refresh=lambda: self.fail('Stale results must not refresh the map'),
                             after=lambda *args: None, poll=lambda: None)
        Planner.poll(ui)
        self.assertEqual(ui.results, {})
        self.assertIsNone(ui.future)
        self.assertIn('changed during analysis', messages[0])

    def test_current_results_update_the_editor(self):
        from jockstrap.ui import Planner
        future = Future()
        future.set_result((4, [{'link_id': 'current', 'status': 'Terrain obstructed'}]))
        refreshes = []
        ui = SimpleNamespace(future=future, revision=4, results={},
                             status=SimpleNamespace(set=lambda *args: None),
                             refresh=lambda: refreshes.append(True), after=lambda *args: None, poll=lambda: None)
        Planner.poll(ui)
        self.assertEqual(ui.results['current']['status'], 'Terrain obstructed')
        self.assertEqual(refreshes, [True])


if __name__ == '__main__': unittest.main()
