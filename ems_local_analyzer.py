# ems_local_analyzer.py

import math
from site_loader import process_site
from antenna_utils import load_antenna_pattern, interpolate_gain
from polarization_loss import get_polarization_loss
from spectrum_loss import compute_interference_level, check_blocking_interference, check_field_induced_interference, adjust_tx_gain_by_frequency
from site_config import site

def distance_3d(a, b):
    return math.sqrt(sum((ac - bc) ** 2 for ac, bc in zip(a, b))) / 1000

def horizontal_direction(dx, dy):
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360

def elevation_angle(dz, dx, dy):
    horizontal_dist = math.sqrt(dx**2 + dy**2)
    return -math.degrees(math.atan2(dz, horizontal_dist))

def angle_difference(a1, a2):
    return min(abs(a1 - a2), 360 - abs(a1 - a2))

def analyze_tx_to_rx(tx, rx):
    d_km = distance_3d(tx['coords'], rx['coords'])
    if d_km == 0:
        raise ValueError(f"🚫 Zero distance between TX and RX. Please check the coordinates.")

    dx, dy, dz = (rc - tc for rc, tc in zip(rx['coords'], tx['coords']))

    az_tx_to_rx = horizontal_direction(dx, dy)
    el_tx_to_rx = elevation_angle(dz, dx, dy)
    az_rx_to_tx = horizontal_direction(-dx, -dy)
    el_rx_to_tx = elevation_angle(-dz, -dx, -dy)

    az_diff_tx = angle_difference(tx['azimuth'], az_tx_to_rx)
    el_diff_tx = angle_difference(tx['elevation'], el_tx_to_rx)
    az_diff_rx = angle_difference(rx['azimuth'], az_rx_to_tx)
    el_diff_rx = angle_difference(rx['elevation'], el_rx_to_tx)

    hor_tx, vert_tx = load_antenna_pattern("AntennaDN.xlsx", tx['antenna_name'])
    hor_rx, vert_rx = load_antenna_pattern("AntennaDN.xlsx", rx['antenna_name'])

    G_hor_tx = 0 if dx == 0 and dy == 0 else interpolate_gain(hor_tx, az_diff_tx, 'azimuth_deg')
    G_vert_tx = interpolate_gain(vert_tx, el_diff_tx, 'elevation_deg')
    tx_max_gain = adjust_tx_gain_by_frequency(tx, rx)
    gt = tx_max_gain + G_hor_tx + G_vert_tx

    G_hor_rx = 0 if dx == 0 and dy == 0 else interpolate_gain(hor_rx, az_diff_rx, 'azimuth_deg')
    G_vert_rx = interpolate_gain(vert_rx, el_diff_rx, 'elevation_deg')
    gr = rx['gain_max'] + G_hor_rx + G_vert_rx

    Pint = compute_interference_level(tx, rx, d_km, gt, gr)
    polar_loss = get_polarization_loss(tx['polarization'], rx['polarization'])
    fspl = 20 * math.log10(d_km) + 20 * math.log10(tx['frequency_mhz']) + 32.44
    prx_dbm = tx['power_dbm'] + gt + gr - fspl - tx['loss'] - rx['loss']

    block_result = check_blocking_interference(tx, rx, d_km, gt, gr)
    induced_result = check_field_induced_interference(tx, rx, d_km * 1000, gt)

    result = {
        'tx_name': tx['device_name'],
        'rx_name': rx['device_name'],
        'distance_m': d_km * 1000,
        'az_diff_tx': az_diff_tx,
        'el_diff_tx': el_diff_tx,
        'az_diff_rx': az_diff_rx,
        'el_diff_rx': el_diff_rx,
        'gt': gt,
        'gr': gr,
        'Pint': Pint,
        'polar_loss': polar_loss,
        'fspl': fspl,
        'prx_dbm': prx_dbm,
        'block_result': block_result,
        'induced_result': induced_result
    }
    return result

def format_ems_result(res, tx_index=0):
    lines = []
    lines.append(f"📡 TX #{tx_index + 1} → RX: {res['tx_name']} → {res['rx_name']}")
    lines.append(f"  Distance: {res['distance_m']:.1f} m")
    #lines.append(f"  gt = {res['gt']:.2f} dBi, gr = {res['gr']:.2f} dBi")
    #lines.append(f"  FSPL = {res['fspl']:.2f} dB")
    #lines.append(f"  Received power = {res['prx_dbm']:.2f} dBm")
    lines.append(f"  Pint = {res['Pint']:.2f} dBm")

    block = res.get('block_result')
    if block:
        lines.append(f"  🛑 Blocking interference: Δf = {block['freq_offset']:.2f} MHz")
        lines.append(f"     → Pblock = {block['Pblock']:.2f} dBm, threshold = {block['threshold']:.2f} dBm")
        lines.append("     ✅ Allowed" if block['passed'] else "     ❌ Exceeded!")
    else:
        lines.append("  ℹ️ Blocking interference: not considered")

    induced = res.get('induced_result')
    if induced and induced.get('considered'):
        lines.append(
            f"  🧲 Induced interference: Pind = {induced['Pinduced_dbm']:.2f} dBm, threshold = {induced['threshold_dbm']} dBm")
        lines.append("     ✅ Allowed" if induced['passed'] else "     ❌ Exceeded!")
    elif induced:
        lines.append("  🧲 Induced interference: not considered (distance too far)")
    else:
        lines.append("  🧲 Induced interference: insufficient data")

    return "\n".join(lines)



if __name__ == "__main__":
    site_data = process_site(site, "DeviceDB.xlsx", "AntennaDN.xlsx")
    tx_list = site_data['tx_list']
    rx_list = site_data['rx_list']

    for tx_id, tx in enumerate(tx_list):
        for rx_id, rx in enumerate(rx_list):
            print("\n========================================")
            print(f"📡 TX #{tx_id + 1} → RX #{rx_id + 1}: {tx['device_name']} → {rx['device_name']}")
            try:
                res = analyze_tx_to_rx(tx, rx)
                print(f"📏 Distance: {res['distance_m']:.1f} m")
                print(f"▶ gt = {res['gt']:.2f} dBi, gr = {res['gr']:.2f} dBi")
                print(f"📉 Loss FSPL: {res['fspl']:.2f} dB")
                print(f"🔊 Level without EN/ACS consideration: {res['prx_dbm']:.2f} dBm")
                print(f"⚠️ Pint considering EN/ACS: {res['Pint']:.2f} dBm")
                # === Blocking interference ===
                block = res['block_result']
                if block:
                    print(
                        f"🛑 Blocking interference: Δf = {block['freq_offset']:.2f} MHz, threshold = {block['limit']:.2f} MHz")
                    print(f"    → Pblock = {block['Pblock']:.2f} dBm, threshold = {block['threshold']:.2f} dBm")
                    print("    ✅ Allowed" if block['passed'] else "    ❌ Exceeds allowed level!")
                else:
                    limit = rx.get('Freq_offset_block', None)
                    if limit is not None:
                        print(f"🛑 Blocking interference: Δf exceeds threshold {limit:.2f} MHz → not considered")
                    else:
                        print("🛑 Blocking interference: parameter 'Freq_offset_block' is not set")

                # === Induced interference ===
                ind = res['induced_result']
                if ind and ind.get('considered'):
                    print(f"🧲 Induced interference: distance = {ind['distance']:.1f} m, λ = {ind['lambda']:.2f} m")
                    print(f"    → Pind = {ind['Pinduced_dbm']:.2f} dBm, threshold = {ind['threshold_dbm']} dBm")
                    print("    ✅ Allowed" if ind['passed'] else "    ❌ Exceeds allowed level!")
                elif ind:
                    print(
                        f"🧲 Induced interference: distance = {ind['distance']:.1f} m ≥ {ind['distance_limit']:.1f} m → not considered")
                else:
                    print("🧲 Induced interference: insufficient data for assessment.")
            except Exception as e:
                print(f"🚫 Analysis error: {e}")
