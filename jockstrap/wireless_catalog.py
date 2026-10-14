"""Outdoor transceivers supported by the 1–10 GHz planner.

Manufacturer listings checked 2026-10-13. Stock is not guaranteed. Pattern
widths are editable assumptions unless explicitly described as published.
"""
CATALOG = {}
CHECKED = '2026-10-13'


def add(brand, model, family, gain, role='client', band=5, url='', az=10, el=10,
        external=False, status='Manufacturer listed', note='', key=None, **metadata):
    name = key or f'{brand} {model}'
    if external:
        note = ('External antenna required: 0 dBi and 90°/10° are placeholders. '
                'Enter the installed antenna gain, pattern and feeder loss before relying on RF results. ') + note
        gain, az, el = 0, 90, 10
    else:
        note += ' Beamwidths are provisional editable approximations unless stated otherwise.'
    note += ' TX/RX defaults are planning assumptions, not a rate-specific factory budget. Regional frequencies, firmware and security must match.'
    CATALOG[name] = dict(brand=brand, model=model, category=family, bands=[band],
        status=status, checked=CHECKED, source=url, note=note, external_antenna=external,
        radio=dict(role=role, aim='fixed' if role=='sector' else 'peer', protocol=family,
                   frequency_ghz={2.4:2.437,5:5.8,6:6.5}[band], gain_dbi=gain,
                   az_beamwidth_deg=az, el_beamwidth_deg=el, polarization='dual'), **metadata)


UI = 'https://techspecs.ui.com/uisp/wireless/'
for model, slug, gain, az, el in (
    ('LiteBeam 5AC Gen2','litebeam-5ac',23,7,7),
    ('NanoBeam 5AC Gen2','nanobeam-5ac',19,15,15),
    ('PowerBeam 5AC Gen2','powerbeam-5ac',25,8,8),
    ('PowerBeam 5AC 620','pbe-5ac-620',29,5,5),
    ('NanoStation 5AC Loco','loco5ac',13,45,45),
):
    add('Ubiquiti',model,'airmax-ac',gain,url=UI+slug,az=az,el=el,
        note='airMAX AC AP/station pairing only; not standard Wi-Fi or LTU. PtMP channel widths differ from PTP.', widths=[10,20,30,40,50,60,80])
for model,slug,gain,az in [('LTU Lite','ltu-lite',13,40),('LTU Pro','ltu-pro',24,14),
                          ('LTU Long-Range','ltu-lr',26,10),('LTU Extreme-Range','ltu-xr',29,6)]:
    add('Ubiquiti',model,'ltu',gain,url=UI+slug,az=az,el=az,
        note='LTU Rocket hub with LTU clients. Client-to-client PTP needs explicitly supported firmware; default client roles do not establish a PTP bridge.', widths=[10,20,30,40,50,60,80,100])
add('Ubiquiti','Rocket Prism 5AC Gen2','airmax-ac',0,role='sector',external=True,url='https://dl.ui.com/qsg/RP-5AC-Gen2/RP-5AC-Gen2_EN.html',widths=[10,20,30,40,50,60,80],ap_only=True)
add('Ubiquiti','LTU Rocket','ltu',0,role='sector',external=True,url=UI+'ltu-rocket',ap_only=True,widths=[10,20,30,40,50,60,80,100])
add('Ubiquiti','airFiber 5XHD','airfiber',0,role='ptp',external=True,url=UI+'airfiber-5xhd-1',note='Dedicated backhaul; matching AF-5XHD peer required. Does not associate to airMAX or LTU.')

MT = 'https://mikrotik.com/product/'
for model,slug,gain,role,band,az,el in (
    ('SXTsq 5 ax','sxtsq_5ax',16,'client',5,23,23),
    ('LHG 5 ax','lhg_5_ax',24.5,'client',5,7,7),
    ('LHG XL 5 ax','lhg_5_ax_xl',27,'client',5,6,6),
    ('mANTBox ax 15s','mantbox_ax_15s',15,'sector',5,120,10),
    ('mANTBox ax 15s','mantbox_ax_15s',12,'sector',2.4,120,10),
):
    add('MikroTik',model,'wifi-ax',gain,role,band,url=MT+slug,az=az,el=el,
        key=f'MikroTik {model} — {band:g} GHz' if band==2.4 else None,
        note='Standard Wi-Fi via wifi-qcom. Nv2/Nstreme are not supported by the AX WiFi driver. Transparent bridging needs compatible station-bridge/bridge configuration.')
add('MikroTik','NetMetal ax','wifi-ax',0,role='sector',external=True,url=MT+'netmetal_ax',note='Dual-band radio; this profile models its 5 GHz interface only.')
add('MikroTik','LHG 5 ac','wifi-ac',24.5,url=MT+'lhg_5_ac',az=7,el=7,status='Discontinued; existing installations',nv2=True,
    note='Legacy wireless driver supports Nv2; wifi-qcom-ac does not. Select the actual mode at both ends.')

CN='https://www.cambiumnetworks.com/products/epmp/'
AP=CN+'epmp-4500-5-ghz-fixed-wireless-access-point/'
for model in ('ePMP 4500C','ePMP 4500L'):
    add('Cambium',model,'epmp',0,role='sector',external=True,url=AP,ap_only=True,
        group='epmp-4500',note='4500 series APs support Force 400/4500 and backward-compatible Force 300 subscriber modules. Use supported firmware.')
for model,gain,slug,group in (
    ('Force 300-25',25,'epmp/','force300'),
    ('Force 425',25,'epmp-force-400-series/','force400'),
    ('Force 4525',25,'epmp/','force400'),
    ('Force 4518',18,'epmp-5-ghz-force-4518-series-fixed-wireless-subscriber-module/','force400'),
):
    add('Cambium',model,'epmp',gain,url='https://www.cambiumnetworks.com/products/epmp/' if slug=='epmp/' else CN+slug,
        az=8,el=8,group=group,note='Subscriber to ePMP 4500-series hub. Subscriber-to-subscriber PTP support is model/firmware specific.')
add('Cambium','Force 400C','epmp',0,external=True,url=CN+'epmp-force-400-series/',group='force400')
add('Cambium','ePMP 4600','epmp-6',0,role='sector',band=6,external=True,url=CN+'epmp-4600-6-ghz-fixed-wireless-access-point/',ap_only=True,group='epmp-4600',note='6 GHz ePMP hub: Force 4600-series clients, not 5 GHz Force clients. AFC/country configuration required where applicable.')
add('Cambium','Force 4625','epmp-6',25,band=6,url=CN+'epmp-6-ghz-force-4600-c/',az=8,el=8,group='force4600')
add('Cambium','Force 4600C','epmp-6',0,band=6,external=True,url=CN+'epmp-6-ghz-force-4600-c/',group='force4600')

MM='https://mimosa.co/products/'
add('Mimosa','A5x','mimosa5',0,role='sector',external=True,url=MM+'a5x',ap_only=True,note='Manufacturer documents A5x with C5x and C5c clients; match SRS/firmware settings.')
add('Mimosa','C5x (base 8 dBi)','mimosa5',8,url=MM+'c5x',az=60,el=60,model_family='C5x',note='Base integrated 8 dBi feed; twist-on antennas replace total gain, never add to the base gain.')
add('Mimosa','C5c','mimosa5',0,external=True,url=MM+'c5c',note='Connectorized client; A5x pairing documented. PTP operation needs matching supported peer firmware.')
add('Mimosa','B5x (base 8 dBi)','mimosa-backhaul',8,role='ptp',url=MM+'b5x',az=60,el=60,note='Dedicated B5x PTP backhaul; not an A5x subscriber. Twist-on antenna configurations require actual antenna gain/pattern.')
for band in (5,6):
    add('Mimosa','A6','mimosa6',16,role='sector',band=band,url=MM+'a6',az=90,el=10,ap_only=True,
        key=f'Mimosa A6 — {band} GHz',note='Integrated antenna 16 dBi; adaptive beamforming gain is not added. Manufacturer recommends C6x clients; country restrictions apply.')
    add('Mimosa','C6x (base 8 dBi)','mimosa6',8,band=band,url=MM+'c6x',az=60,el=60,
        key=f'Mimosa C6x (base 8 dBi) — {band} GHz',note='Base integrated 8 dBi feed. Model one band at a time; use actual gain/pattern when attaching a twist-on antenna.')

add('Ubiquiti','LiteAP AC LAP-120','airmax-ac',16,role='sector',url=UI+'lap-120',az=120,el=10,note='Integrated sector radio for airMAX AC stations; vertical beamwidth is provisional.')
add('Ubiquiti','LiteAP GPS LAP-GPS','airmax-ac',17,role='sector',url=UI+'lite-ap-gps',az=90,el=10,note='Integrated sector radio with GPS synchronization; synchronization does not imply interoperability with other radio families.')
