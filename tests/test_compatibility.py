import unittest
from jockstrap.equipment import make_radio, PRESETS, CATALOG
from jockstrap.compatibility import compatibility
from jockstrap.project import Project, Site
from jockstrap.engine import antenna_loss


class CompatibilityTests(unittest.TestCase):
    def pair(self,a,b,**values):
        first,second=make_radio('a',a),make_radio('b',b)
        for k,v in values.items(): setattr(first,k,v)
        return first,second

    def test_current_us_lineup_and_regional_labels(self):
        models={entry['model'] for entry in CATALOG.values() if entry['brand']=='TP-Link'}
        expected={'CPE210','CPE220','CPE510','CPE605','CPE610','CPE710',
                  'EAP100-Bridge','EAP115-Bridge','EAP211-Bridge','EAP215-Bridge',
                  'Flex Bridge 5','Sector Bridge 5','Beam Bridge 5 UR','Beam Bridge 7',
                  'EAP110-Outdoor','EAP225-Outdoor','EAP603-Outdoor','EAP610-Outdoor',
                  'EAP625-Outdoor HD','EAP650-Outdoor','EAP650 D120-Outdoor',
                  'EAP650 D30-Outdoor','EAP725-Outdoor','EAP772-Outdoor','EAP775-Outdoor'}
        self.assertEqual(models,expected)
        self.assertEqual(CATALOG['TP-Link Sector Bridge 5']['status'],'Coming soon (US)')
        self.assertEqual(CATALOG['TP-Link CPE220']['status'],'Regional listing')

    def test_all_presets_produce_valid_radios(self):
        for name in PRESETS:
            radio=make_radio('site',name)
            Project(sites=[Site('Site',40,-111,id='site')],radios=[radio]).validate()

    def test_old_project_radio_fields_remain_loadable(self):
        from dataclasses import asdict
        radio=asdict(make_radio('site','TP-Link CPE710'))
        for field in ('hardware_revision','wireless_mode','antenna_pattern'): radio.pop(field)
        project=Project.from_dict(dict(sites=[asdict(Site('Site',40,-111,id='site'))],radios=[radio]))
        self.assertEqual(project.radios[0].wireless_mode,'standard')
        self.assertEqual(project.radios[0].hardware_revision,'unspecified')

    def test_pharos_standard_and_maxtream(self):
        a,b=self.pair('TP-Link CPE710','TP-Link CPE510')
        self.assertEqual(compatibility(a,b)['status'],'Compatible')
        a.wireless_mode=b.wireless_mode='maxtream'
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')
        a,b=self.pair('TP-Link CPE510','TP-Link CPE610')
        a.wireless_mode=b.wireless_mode='maxtream'
        self.assertEqual(compatibility(a,b)['status'],'Compatible')

    def test_revision_groups_and_unknown_existing_projects(self):
        a,b=self.pair('TP-Link EAP215-Bridge V1','TP-Link EAP211-Bridge V3')
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')
        a,b=self.pair('TP-Link EAP215-Bridge V2','TP-Link EAP211-Bridge V3')
        self.assertEqual(compatibility(a,b)['status'],'Compatible')
        a,b=self.pair('TP-Link EAP215-Bridge','TP-Link EAP211-Bridge V3')
        self.assertEqual(compatibility(a,b)['status'],'Unverified')
        a.hardware_revision='V3.6'
        self.assertEqual(compatibility(a,b)['status'],'Compatible')

    def test_omada_tdma_and_client_limits(self):
        a,b=self.pair('TP-Link Flex Bridge 5','TP-Link EAP215-Bridge V3')
        self.assertEqual(compatibility(a,b)['status'],'Compatible')
        a.wireless_mode='tdma'
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')
        a,b=self.pair('TP-Link Sector Bridge 5','TP-Link Flex Bridge 5')
        a.wireless_mode='tdma'
        self.assertEqual(compatibility(a,b)['status'],'Compatible')
        self.assertEqual(a.max_clients,32)
        self.assertEqual(b.max_clients,8)
        self.assertEqual(make_radio('a','TP-Link EAP100-Bridge').max_clients,3)

    def test_mixed_bridge_families_and_bands(self):
        a,b=self.pair('TP-Link CPE710','TP-Link EAP215-Bridge V3')
        self.assertEqual(compatibility(a,b)['status'],'Unverified')
        a,b=self.pair('TP-Link CPE210','TP-Link CPE510')
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')
        a,b=self.pair('TP-Link Beam Bridge 5 UR','TP-Link EAP215-Bridge V3')
        self.assertEqual(compatibility(a,b)['status'],'Unverified')

    def test_ap_mesh_is_conditional_and_omni_has_no_azimuth_loss(self):
        a,b=self.pair('TP-Link EAP650-Outdoor — 5 GHz','TP-Link EAP610-Outdoor — 5 GHz')
        self.assertEqual(compatibility(a,b)['status'],'Conditional')
        self.assertEqual(antenna_loss(a,0,0),antenna_loss(a,180,0))
        a,b=self.pair('TP-Link EAP772-Outdoor — 6 GHz','TP-Link EAP775-Outdoor — 6 GHz')
        self.assertEqual(compatibility(a,b)['status'],'Unverified')

    def test_edited_protocol_and_width_are_respected(self):
        a,b=self.pair('TP-Link CPE710','TP-Link CPE710')
        a.protocol='omada-bridge'
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')
        a.protocol='pharos-ac'
        a.channel_width_mhz=b.channel_width_mhz=5
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')

    def test_network_report_uses_hardware_rules_not_only_family_names(self):
        from test_planner import network,flat_profile
        from jockstrap.engine import analyze_link
        project=network(2000)
        radios=[make_radio(site.id,preset) for site,preset in zip(project.sites,('TP-Link CPE710','TP-Link CPE510'))]
        project.radios=radios
        project.links[0].a_radio_id,project.links[0].b_radio_id=radios[0].id,radios[1].id
        result=analyze_link(project,project.links[0],flat_profile(project))
        self.assertEqual(result.compatibility['status'],'Compatible')
        self.assertNotEqual(result.status,'Incompatible settings')


if __name__=='__main__': unittest.main()

class OtherBrandsTests(unittest.TestCase):
    def pair(self,first,second):
        return make_radio('a',first),make_radio('b',second)

    def test_new_catalog_has_only_transceivers_and_valid_references(self):
        from jockstrap.wireless_catalog import CATALOG as other
        self.assertEqual({e['brand'] for e in other.values()}, {'Ubiquiti','MikroTik','Cambium','Mimosa'})
        for name,e in other.items():
            self.assertTrue(e['source'].startswith('https://'),name)
            self.assertIn(e['radio']['role'],('sector','client','ptp'))
            self.assertIn('planning assumptions',e['note'])

    def test_airmax_ltu_and_cross_brand_proprietary_do_not_interoperate(self):
        for first,second in [('Ubiquiti LiteBeam 5AC Gen2','Ubiquiti LTU Pro'),
                             ('Ubiquiti LiteBeam 5AC Gen2','TP-Link CPE710'),
                             ('Ubiquiti LiteBeam 5AC Gen2','Cambium Force 4525')]:
            self.assertEqual(compatibility(*self.pair(first,second))['status'],'Incompatible')

    def test_external_antenna_needs_configuration_before_pairing_claim(self):
        a,b=self.pair('Ubiquiti Rocket Prism 5AC Gen2','Ubiquiti LiteBeam 5AC Gen2')
        self.assertEqual(a.gain_dbi,0)
        self.assertEqual(compatibility(a,b)['status'],'Unverified')
        a.gain_dbi=21
        self.assertEqual(compatibility(a,b)['status'],'Conditional')
        a.channel_width_mhz=b.channel_width_mhz=80
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')

    def test_mikrotik_wifi_and_cross_vendor_bridging_are_conditional(self):
        a,b=self.pair('MikroTik mANTBox ax 15s','MikroTik SXTsq 5 ax')
        self.assertEqual(compatibility(a,b)['status'],'Conditional')
        a.wireless_mode=b.wireless_mode='tdma'
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')
        a,b=self.pair('MikroTik SXTsq 5 ax','TP-Link CPE710')
        self.assertEqual(compatibility(a,b)['status'],'Conditional')
        b.wireless_mode='maxtream'
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')

    def test_epmp_generation_and_subscriber_pairs(self):
        a,b=self.pair('Cambium ePMP 4500L','Cambium Force 300-25')
        a.gain_dbi=17
        self.assertEqual(compatibility(a,b)['status'],'Conditional')
        a,b=self.pair('Cambium Force 4625','Cambium Force 4525')
        b.frequency_ghz=6.5
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')
        a,b=self.pair('Ubiquiti LTU Pro','Ubiquiti LTU Long-Range')
        self.assertEqual(compatibility(a,b)['status'],'Unverified')

    def test_mimosa_base_gain_and_dedicated_backhaul(self):
        a,b=self.pair('Mimosa A6 — 6 GHz','Mimosa C6x (base 8 dBi) — 6 GHz')
        self.assertEqual((a.gain_dbi,b.gain_dbi),(16,8))
        self.assertEqual(compatibility(a,b)['status'],'Conditional')
        a,b=self.pair('Mimosa B5x (base 8 dBi)','Mimosa B5x (base 8 dBi)')
        self.assertEqual(compatibility(a,b)['status'],'Conditional')
        b.role='client'
        self.assertEqual(compatibility(a,b)['status'],'Incompatible')
