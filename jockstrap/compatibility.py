"""Configuration-aware link compatibility; uncertain pairings stay uncertain."""
import re
from .catalog import CATALOG
from .tplink_catalog import PAIRING_SOURCE


def catalog_entry(radio):
    return CATALOG.get(radio.equipment)


def hardware_generation(radio, entry):
    if entry.get('generation') not in ('unknown','v1','modern'):
        return entry.get('generation')
    match = re.match(r'v?(\d+)', radio.hardware_revision.strip(), re.I)
    if match:
        return 'v1' if match.group(1)=='1' else 'modern' if match.group(1) in ('2','3') else 'unknown'
    return entry.get('generation','unknown')


def compatibility(a,b):
    def result(status,reason): return dict(status=status,reason=reason)
    if abs(a.frequency_ghz-b.frequency_ghz)>1e-6:
        return result('Incompatible','Operating frequencies differ.')
    if abs(a.channel_width_mhz-b.channel_width_mhz)>1e-6:
        return result('Incompatible','Channel widths differ.')
    ea,eb=catalog_entry(a),catalog_entry(b)
    for radio,entry in ((a,ea),(b,eb)):
        if entry:
            if radio.protocol != entry['radio']['protocol']:
                return result('Incompatible',f"{entry['model']}: configured protocol does not match its equipment preset. Reapply the preset or select the actual hardware.")
            freq=radio.frequency_ghz
            band=2.4 if 2.4<=freq<2.5 else 5 if 5.15<=freq<5.925 else 6 if 5.925<=freq<=7.125 else None
            if band not in entry.get('bands',[]):
                return result('Incompatible',f"{entry['model']} preset does not support the selected band. Select its correct band preset.")
            if entry['category']=='Pharos CPE':
                widths=(20,40,80) if entry['model']=='CPE710' else (5,10,20,40)
                if radio.channel_width_mhz not in widths:
                    return result('Incompatible',f"{entry['model']} does not support this channel width.")
            if entry.get('ap_only') and radio.role!='sector':
                return result('Incompatible',f"{entry['model']} is a hub, not a client radio.")
            if entry.get('widths') and radio.channel_width_mhz not in entry['widths']:
                return result('Incompatible',f"{entry['model']}: channel width is outside this catalog profile.")
    if any(e and e['brand']!='TP-Link' for e in (ea,eb)):
        if not ea or not eb:
            return result('Unverified','Choose catalog equipment at both ends to check hardware pairing.')
        fa,fb=ea['radio']['protocol'],eb['radio']['protocol']
        wifi={'wifi-ax','wifi-ac','pharos-n','pharos-ac','omada-mesh'}
        if ea['brand']!=eb['brand'] or fa!=fb:
            if fa in wifi and fb in wifi:
                if a.wireless_mode!='standard' or b.wireless_mode!='standard':
                    return result('Incompatible','Cross-vendor Wi-Fi requires standard mode, not proprietary TDMA/MAXtream/mesh.')
                return result('Conditional','Standard Wi-Fi association may work with matching security and common PHY modes. Transparent Ethernet bridging is not established across vendors/drivers.')
            return result('Incompatible','Different proprietary radio families; shared bands or management do not establish interoperability.')
        if a.wireless_mode!=b.wireless_mode:
            return result('Incompatible','Wireless modes differ.')
        if fa.startswith('wifi-'):
            if a.wireless_mode!='standard':
                return result('Incompatible','This profile uses standard Wi-Fi. AX WiFi drivers do not support Nv2/Nstreme; legacy driver selection must be verified separately.')
            return result('Conditional','Same-band MikroTik Wi-Fi peers. Verify AP/station roles, common PHY modes, security, driver packages and transparent station-bridge configuration.')
        if a.wireless_mode not in ('standard','tdma'):
            return result('Incompatible','Unsupported wireless mode for this proprietary radio family.')
        if a.role==b.role=='sector':
            return result('Incompatible','Two hub radios do not form a hub/client link; configure a supported station or PTP peer.')
        hub=a if a.role=='sector' else b if b.role=='sector' else None
        if fa=='airmax-ac' and hub and a.channel_width_mhz>40:
            return result('Incompatible','airMAX AC PtMP uses channel widths up to 40 MHz in these profiles; wider widths require supported PTP mode.')
        for radio,entry in ((a,ea),(b,eb)):
            if entry.get('external_antenna') and radio.gain_dbi==0:
                return result('Unverified','External antenna has not been configured: enter its actual gain, beamwidth and feeder loss. Radio-family pairing alone is insufficient for a usable link budget.')
        if fa in ('airfiber','mimosa-backhaul'):
            if ea['model']!=eb['model']:
                return result('Unverified','Backhaul model/firmware pairing has not been verified.')
            if a.role!='ptp' or b.role!='ptp':
                return result('Incompatible','Dedicated backhaul profiles require PTP roles at both ends.')
            return result('Conditional','Matching dedicated PTP models; verify firmware, security and channel configuration.')
        if not hub:
            if fa=='airmax-ac' and a.role==b.role=='ptp':
                return result('Conditional','airMAX AC PTP peers; configure one AP and one station on supported firmware with matching security.')
            return result('Unverified','Two subscriber radios need explicitly supported PTP firmware and roles; client-to-client compatibility is not assumed.')
        return result('Conditional','Documented hub/client family. Match firmware, security, country settings and network mode; RF estimates do not predict throughput or airtime capacity.')
    if 'custom' in (a.protocol,b.protocol):
        return result('Unverified','Generic/custom equipment: no hardware interoperability claim.')
    if ea and eb:
        ca,cb=ea['category'],eb['category']
        if ca==cb=='Pharos CPE':
            if 'maxtream' in (a.wireless_mode,b.wireless_mode):
                if not ea.get('maxtream') or not eb.get('maxtream'):
                    return result('Incompatible','MAXtream is not supported by CPE710; use standard mode at both ends.')
                if a.wireless_mode!=b.wireless_mode:
                    return result('Incompatible','Both ends must use the same MAXtream network mode.')
                return result('Compatible','Same-band Pharos MAXtream-capable peers. Match security and hardware settings.')
            if a.wireless_mode!='standard' or b.wireless_mode!='standard':
                return result('Incompatible','Pharos peers require standard mode or supported MAXtream mode.')
            return result('Compatible','Same-band Pharos standard Wi-Fi peers; mixed N/AC operates using common supported modes.')
        if ca==cb=='Omada bridge':
            ga,gb=hardware_generation(a,ea),hardware_generation(b,eb)
            if 'unknown' in (ga,gb):
                return result('Unverified','Select actual EAP bridge hardware revisions. V1 and V2/V3 generations do not interoperate.')
            if 'v1' in (ga,gb) and ga!=gb:
                return result('Incompatible','EAP bridge V1 cannot pair with V2/V3 or the modern Flex/Sector generation.')
            if 'beam7' in (ga,gb) and ea['model']!=eb['model']:
                return result('Unverified','Beam Bridge 7 mixed-model interoperability is not documented; use its matching PTP pair.')
            if 'Beam Bridge 5 UR' in (ea['model'],eb['model']) and ea['model']!=eb['model']:
                return result('Unverified','Beam Bridge 5 UR mixed-model pairing is not yet verified in this catalog.')
            hub=a if a.role=='sector' else b if b.role=='sector' else None
            peer=b if hub is a else a
            if ea.get('ap_only') and eb.get('ap_only'):
                return result('Incompatible','Two Sector Bridge hubs cannot be configured as a hub/client pair.')
            if hub and hub.wireless_mode=='tdma':
                other=catalog_entry(peer)
                if not other.get('tdma'):
                    return result('Incompatible','Disable hub TDMA when serving EAP/Beam bridge clients; TDMA pairing is documented for Flex clients.')
            elif a.wireless_mode in ('maxtream','mesh') or b.wireless_mode in ('maxtream','mesh'):
                return result('Incompatible','Omada bridge kits do not use Pharos MAXtream or outdoor-AP mesh mode.')
            return result('Compatible','Documented Omada bridge pairing; configure main/client roles, matching security and pairing settings. '+PAIRING_SOURCE)
        if ca==cb=='Omada outdoor AP':
            if a.wireless_mode!= 'mesh' or b.wireless_mode!='mesh':
                return result('Unverified','Two coverage APs do not automatically form a wireless bridge. Configure a supported mesh uplink.')
            if not ea.get('mesh') or not eb.get('mesh'):
                return result('Incompatible','This AP does not have verified Omada Mesh uplink support.')
            if a.frequency_ghz>=5.925:
                return result('Unverified','6 GHz mesh uplink support requires model/firmware/controller verification; AFC alone does not establish compatibility.')
            return result('Conditional','Omada Mesh-capable APs: matching controller, firmware, uplink band and mesh settings required. Not bridge-kit interoperability.')
        if 'Omada bridge' in (ca,cb):
            return result('Unverified','Omada bridge-to-Pharos/outdoor-AP wireless pairing is not documented. Omada management does not imply radio compatibility.')
        if {ca,cb}=={'Pharos CPE','Omada outdoor AP'}:
            if 'maxtream' in (a.wireless_mode,b.wireless_mode):
                return result('Incompatible','An Omada outdoor AP cannot use Pharos MAXtream.')
            return result('Conditional','Pharos client association to a same-band standard Wi-Fi AP may work with matching security. Transparent Ethernet bridging/mesh is not established.')
    if a.protocol==b.protocol:
        return result('Compatible','Same protocol family; verify hardware/firmware interoperability and security settings.')
    if a.protocol.startswith('pharos') and b.protocol.startswith('pharos'):
        return result('Unverified','Choose catalog presets to verify Pharos capabilities and operating mode.')
    return result('Incompatible','Different radio protocol families; RF strength does not establish interoperability.')
