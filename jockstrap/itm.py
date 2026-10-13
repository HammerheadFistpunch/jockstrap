"""Optional median ITM path estimate, extracted from Viewshed's loss worker.

This is an alternative total path-loss model, never added to P.526 diffraction.
"""
import math


def path_loss(profile, frequency_ghz, tx_height_m, rx_height_m, polarization):
    from itmlogic.preparatory_subroutines.qlrps import qlrps
    from itmlogic.preparatory_subroutines.qlrpfl import qlrpfl
    from itmlogic.statistics.avar import avar
    distance = profile.distances_m[-1]
    if not 1000 <= distance <= 200000:
        raise ValueError("ITM comparison currently supports 1–200 km paths.")
    freq = frequency_ghz * 1000
    count = len(profile.elevations_m)
    step = distance / (count - 1)
    if any(abs((b - a) - step) > 0.001 for a, b in zip(profile.distances_m, profile.distances_m[1:])):
        raise ValueError("ITM requires uniformly spaced terrain samples.")
    _, _, _, impedance = qlrps(freq, 0, 301, polarization, 15, 0.005)
    prop = dict(pfl=[count - 1, distance / (count - 1), *profile.elevations_m],
                wn=2 * math.pi * freq * 1e6 / 299792458, hg=[tx_height_m, rx_height_m],
                ens=301, gme=(1 / 6370e3) * (1 - 0.04665 * math.exp(0.005577 * 301)),
                zgnd=impedance, he=[0., 0.], dl=[0., 0.], the=[0., 0.], dh=0., dist=0.,
                kwx=0, mdp=-1, dlsa=0., dx=0., tha=0., dbxa=0., xae=0., sgc=0.,
                lvar=5, mdvar=1, klim=5, kdv=-1, mdvarx=-1, klimx=-1)
    qlrpfl(prop)
    result = avar(0, 0, 0, prop)
    attenuation = result[0] if isinstance(result, tuple) else result
    loss = 32.45 + 20 * math.log10(distance / 1000) + 20 * math.log10(freq) + attenuation
    if not math.isfinite(loss):
        raise ValueError("ITM returned a non-finite result.")
    return loss, prop.get("kwx", 0)
