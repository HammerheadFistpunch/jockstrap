"""TP-Link outdoor catalog checked against manufacturer pages, 2026-10-13.

US-listed models plus clearly labelled regional and announced products. Antenna
figures are per antenna, not summed over chains. No invented MCS sensitivity.
"""
CHECKED = '2026-10-13'
BASE = 'https://www.omadanetworks.com/us/business-networking/'
PAIRING_SOURCE = 'https://support.omadanetworks.com/us/document/128124/'
CATALOG = {}


def add(model, category, radio, status='US listed', note='', url=None, key=None, **metadata):
    CATALOG[key or 'TP-Link '+model] = dict(model=model, category=category,
        status=status, checked=CHECKED, source=url or BASE+'omada-wifi-wireless-bridge/'+model.lower().replace(' ','-')+'/',
        note=note, radio=radio, **metadata)


for model, gain, az, el, frequency, pol, status in (
    ('CPE210',9,65,35,2.437,'dual','US listed'),
    ('CPE220',12,60,30,2.437,'dual','Regional listing'),
    ('CPE510',13,45,30,5.8,'dual','US listed'),
    ('CPE605',23,7,10,5.8,'vertical','Regional listing'),
    ('CPE610',23,9,7,5.8,'dual','Regional listing'),
    ('CPE710',23,9,7,5.8,'dual','US listed'),
):
    add(model,'Pharos CPE',dict(role='client',aim='peer',protocol='pharos-ac' if model=='CPE710' else 'pharos-n',
        gain_dbi=gain,az_beamwidth_deg=az,el_beamwidth_deg=el,frequency_ghz=frequency,polarization=pol),
        status=status, bands=[2.4] if frequency<3 else [5], maxtream=model!='CPE710',
        url='https://www.tp-link.com/'+('us' if status=='US listed' else 'uk')+'/business-networking/outdoor-radio/'+model.lower()+'/',
        note='Pharos standard Wi-Fi mode: same-band CPE peers. MAXtream needs capable Pharos devices at both ends; CPE710 cannot use MAXtream. Beamwidth can vary with hardware revision.')

CATALOG['TP-Link CPE605']['note'] += ' Single-polarized feed orientation is assumed vertical; verify physical orientation.'

for model, gain, az, el, limit in [('EAP211-Bridge',10,60,30,4),('EAP215-Bridge',14,43,18,4),('EAP115-Bridge',14,43,18,4)]:
    for revision in ('V1','V2','V3'):
        old=revision!='V3'
        # Old revisions have their own published antenna specs; preserve them.
        g, h, v = (7,70,70) if old and model.startswith('EAP211') else (11,35,35) if old else (gain,az,el)
        add(model,'Omada bridge',dict(role='sector',protocol='omada-bridge',gain_dbi=g,
            az_beamwidth_deg=h,el_beamwidth_deg=v,max_clients=limit,hardware_revision=revision),
            key=f'TP-Link {model} {revision}',status='Older hardware' if old else 'US listed',bands=[5],generation='v1' if revision=='V1' else 'modern',
            url=BASE+'omada-wifi-wireless-bridge/'+model.lower()+'-kit/'+revision.lower()+'/',
            note='V1 pairs with V1 bridge generation only. V2 and V3 interoperate. Modern bridges can join Flex/Sector Bridge networks; disable hub TDMA for EAP clients. Verify revision-specific antenna specs; EAP115 V3 page has conflicting 35°/43° horizontal figures (43° uses its comparison table).')
    # Preserve existing projects without silently assigning them a newer revision.
    add(model,'Omada bridge',dict(role='sector',protocol='omada-bridge',gain_dbi=7 if model.startswith('EAP211') else 11,
        az_beamwidth_deg=70 if model.startswith('EAP211') else 35,el_beamwidth_deg=70 if model.startswith('EAP211') else 35,max_clients=4),
        status='Revision unspecified',bands=[5],generation='unknown',hidden=True,
        url=BASE+'omada-wifi-wireless-bridge/'+model.lower()+'-kit/',note='Existing unversioned preset: choose the actual hardware revision to verify compatibility.')

add('EAP100-Bridge','Omada bridge',dict(role='sector',protocol='omada-bridge',frequency_ghz=2.437,
    gain_dbi=8,az_beamwidth_deg=70,el_beamwidth_deg=70,max_clients=3),bands=[2.4],generation='2.4-only',
    url=BASE+'omada-wifi-wireless-bridge/eap100-bridge-kit/',note='2.4 GHz only; does not link to 5 GHz Omada bridges. Up to three remote bridges.')
add('Flex Bridge 5','Omada bridge',dict(role='sector',protocol='omada-bridge',gain_dbi=17,
    az_beamwidth_deg=40,el_beamwidth_deg=18,max_clients=8),bands=[5],generation='modern',tdma=True,
    note='Eight remote bridges as hub. Sector Bridge 5 and modern EAP bridges are documented peers. Disable TDMA when serving EAP bridge clients.')
add('Sector Bridge 5','Omada bridge',dict(role='sector',protocol='omada-bridge',gain_dbi=16,
    az_beamwidth_deg=120,el_beamwidth_deg=13,max_clients=32),status='Coming soon (US)',bands=[5],generation='modern',tdma=True,ap_only=True,
    note='Hub-only role: serves up to 32 Flex or modern EAP clients. US category page still says coming soon; support/firmware already published. Disable TDMA for EAP clients.')
add('Beam Bridge 5 UR','Omada bridge',dict(role='client',aim='peer',protocol='omada-bridge',gain_dbi=23,
    az_beamwidth_deg=9,el_beamwidth_deg=7,max_clients=8),bands=[5],generation='modern',
    url=BASE+'omada-wifi-wireless-bridge/beam-bridge-5-ur-kit/',note='Same-kit pairing documented. Mixed-model pairing is marked unverified until explicitly documented.')
add('Beam Bridge 7','Omada bridge',dict(role='ptp',aim='peer',protocol='omada-bridge',gain_dbi=14,
    az_beamwidth_deg=45,el_beamwidth_deg=45,max_clients=1),status='Coming soon (US)',bands=[5,6],generation='beam7',
    url=BASE+'omada-wifi-wireless-bridge/beam-bridge-7-kit/',note='PTP pair; model one 5/6 GHz link at a time. MLO/automatic failover not modeled. Cross-family pairing unverified; 6 GHz requires applicable AFC configuration.')

# All models on the US outdoor-AP category page. Per-band variants keep gain
# reference explicit and avoid carrying a 5 GHz gain into a 2.4 GHz link.
for model, gains, az, el in (
    ('EAP110-Outdoor',{2.4:3},360,180),
    ('EAP225-Outdoor',{2.4:3,5:4},360,180),
    ('EAP603-Outdoor',{2.4:4,5:5},360,180),
    ('EAP610-Outdoor',{2.4:4,5:5},360,180),
    ('EAP625-Outdoor HD',{2.4:3,5:5},360,180),
    ('EAP650-Outdoor',{2.4:4,5:5},360,180),
    ('EAP650 D120-Outdoor',{2.4:8,5:10},120,30),
    ('EAP650 D30-Outdoor',{2.4:12,5:15},30,30),
    ('EAP772-Outdoor',{2.4:4,5:6,6:6},360,180),
    ('EAP725-Outdoor',{2.4:4.5,5:5.3},360,180),
    ('EAP775-Outdoor',{2.4:4.5,5:5.3,6:7},360,180),
):
    for band,gain in gains.items():
        add(model,'Omada outdoor AP',dict(role='sector',protocol='omada-mesh',wireless_mode='standard' if model=='EAP110-Outdoor' else 'mesh',
            antenna_pattern='omni' if az==360 else 'directional',frequency_ghz={2.4:2.437,5:5.8,6:6.5}[band],
            gain_dbi=gain,az_beamwidth_deg=az,el_beamwidth_deg=el),key=f'TP-Link {model} — {band:g} GHz',
            status='Coming soon (US)' if model=='EAP775-Outdoor' else 'US listed',bands=[band],mesh=model!='EAP110-Outdoor',
            url=BASE+'omada-wifi-outdoor/'+model.lower().replace(' ','-')+'/',
            note='Coverage AP, not an Omada bridge-kit device. AP-to-AP links need supported Omada Mesh, controller and firmware configuration. Omni vertical pattern is an editable approximation; no beamforming bonus. EAP110 mesh support is not established. 6 GHz AFC/mesh uplink availability must be checked separately.')
    if model in ('EAP725-Outdoor','EAP775-Outdoor'):
        directional = {2.4:(8.3,90,90),5:(13.2,45,45)} if model.startswith('EAP725') else {2.4:(8.7,90,75),5:(10.5,90,45),6:(12,90,30)}
        for band,(gain,h,v) in directional.items():
            add(model,'Omada outdoor AP',dict(role='sector',protocol='omada-mesh',wireless_mode='mesh',frequency_ghz={2.4:2.437,5:5.8,6:6.5}[band],
                gain_dbi=gain,az_beamwidth_deg=h,el_beamwidth_deg=v),key=f'TP-Link {model} directional — {band:g} GHz',
                status='Coming soon (US)' if model.startswith('EAP775') else 'US listed',bands=[band],mesh=True,
                url=BASE+'omada-wifi-outdoor/'+model.lower()+'/',note='Select internal directional antenna mode on the hardware. EAP725 elevation beamwidth is provisional: page gives only one beamwidth. Omada Mesh configuration required for AP-to-AP uplink; 6 GHz uplink support unverified.')
