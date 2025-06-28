# im3_analyzer.py

import math
import itertools
from site_loader import process_site
from site_config import site
from polarization_loss import get_polarization_loss
from antenna_utils import load_antenna_pattern, interpolate_gain
import io
import contextlib

def compute_fspl(freq_mhz, distance_km):
    if distance_km <= 0:
        distance_km = 1  # минимальное значение
    return 20 * math.log10(distance_km) + 20 * math.log10(freq_mhz) + 32.44

def distance_3d(p1, p2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2))) / 1000

def horizontal_direction(dx, dy):
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360

def elevation_angle(dz, dx, dy):
    horizontal_dist = math.sqrt(dx ** 2 + dy ** 2)
    return -math.degrees(math.atan2(dz, horizontal_dist))

def angle_difference(a1, a2):
    return min(abs(a1 - a2), 360 - abs(a1 - a2))

def compute_directional_gains(tx, rx):
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
    gt = tx['gain_max'] + G_hor_tx + G_vert_tx

    G_hor_rx = 0 if dx == 0 and dy == 0 else interpolate_gain(hor_rx, az_diff_rx, 'azimuth_deg')
    G_vert_rx = interpolate_gain(vert_rx, el_diff_rx, 'elevation_deg')
    gr = rx['gain_max'] + G_hor_rx + G_vert_rx

    return gt, gr

def compute_im3_level(tx1, tx2, rx, f_im3):
    d_km = distance_3d(tx1['coords'], rx['coords'])
    gt, gr = compute_directional_gains(tx1, rx)
    fspl_tx1 = compute_fspl(tx1['frequency_mhz'], d_km)
    fspl_tx2 = compute_fspl(tx2['frequency_mhz'], d_km)
    fspl_rx = compute_fspl(rx['frequency_mhz'], d_km)
    polar_loss = get_polarization_loss(tx1.get('polarization'), rx.get('polarization'))

    delta_f = abs(f_im3 - rx['frequency_mhz'])
    delta_bw = 1.5 * (tx1['BW_khz'] + rx['BW_khz']) / 1000
    im3_offset_db = 25

    if delta_f < delta_bw:
        Pim1 = tx1['power_dbm'] - im3_offset_db + gt + gr - tx1['loss'] - rx['loss'] - fspl_tx1 - polar_loss
        Pim2 = tx2['power_dbm'] - im3_offset_db + gt + gr - tx2['loss'] - rx['loss'] - fspl_tx2 - polar_loss
        p_sum_mw = 10 ** (Pim1 / 10) + 10 ** (Pim2 / 10)
    else:
        en_rule1 = tx1.get('EN_dBm_rule')
        en_rule2 = tx2.get('EN_dBm_rule')
        EN_rx1 = en_rule1['below_limit'] if rx['frequency_mhz'] <= en_rule1['freq_limit_mhz'] else en_rule1['above_limit']
        EN_rx2 = en_rule2['below_limit'] if rx['frequency_mhz'] <= en_rule2['freq_limit_mhz'] else en_rule2['above_limit']

        Pint11 = tx1['power_dbm'] - im3_offset_db + gt + gr - tx1['loss'] - rx['loss'] - fspl_tx1 - rx.get('ACS', 0)
        Pint12 = EN_rx1 - im3_offset_db + gt + gr - tx1['loss'] - rx['loss'] - fspl_rx
        Pint21 = tx2['power_dbm'] - im3_offset_db + gt + gr - tx2['loss'] - rx['loss'] - fspl_tx2 - rx.get('ACS', 0)
        Pint22 = EN_rx2 - im3_offset_db + gt + gr - tx2['loss'] - rx['loss'] - fspl_rx

        p_sum_mw = sum([10 ** (p / 10) for p in [Pint11, Pint12, Pint21, Pint22]])

    return 10 * math.log10(p_sum_mw)

def generate_im3_frequencies(tx_list, selected_tx_ids):
    im3_list = []
    for i, j in itertools.combinations(selected_tx_ids, 2):
        f1 = tx_list[i]['frequency_mhz']
        f2 = tx_list[j]['frequency_mhz']
        im3_list.append((2 * f1 - f2, i, j))
        im3_list.append((2 * f2 - f1, j, i))
    return im3_list

def analyze_im3_candidates(site, tx_ids, rx_id, show_levels=False, use_markdown=False):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        site = process_site(site, "DeviceDB.xlsx", "AntennaDN.xlsx")
        tx_list = site['tx_list']
        rx = site['rx_list'][rx_id]

        im3_list = generate_im3_frequencies(tx_list, tx_ids)
        print(f"🔎 Third-order intermodulation frequency analysis for #{rx_id + 1} ({rx['frequency_mhz']} MHz):")

        for f_im3, i, j in im3_list:
            delta_f = abs(f_im3 - rx['frequency_mhz'])
            delta_bw = 1.5 * (tx_list[i]['BW_khz'] + rx['BW_khz']) / 1000

            # Формируем строку без HTML, просто с текстом
            print(f"  ▶ 2f{i + 1} - f{j + 1} = {f_im3:.2f} MHz (|Δf - f_rx| = {delta_f:.2f} MHz)")

            if show_levels:
                try:
                    level = compute_im3_level(tx_list[i], tx_list[j], rx, f_im3)
                    threshold = rx.get('sensitivity_dbm', -100) + 10  # +10 dB for 90% coverage margin
                    if level > threshold:
                        print(
                            f"     ⮑ IM interference level above sensitivity ({threshold:.0f} dBm for 90% coverage): {level:.2f} dBm")
                    else:
                        print(f"     ⮑ IM interference level estimate: {level:.2f} dBm")
                except Exception as e:
                    print(f"     ⚠️ Error calculating IM level: {e}")

    return buffer.getvalue()

if __name__ == "__main__":
    try:
        result = analyze_im3_candidates(site, tx_ids=[0, 1, 2], rx_id=0, show_levels=True, use_markdown=False)
        print(result)
    except ValueError as e:
        print("🚫 ПОМИЛКА ПІД ЧАС ПЕРЕВІРКИ:")
        print(e)
