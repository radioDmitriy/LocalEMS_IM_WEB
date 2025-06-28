# spectrum_loss.py

import math
from polarization_loss import get_polarization_loss

def dbm_to_mw(p_dbm):
    return 10 ** (p_dbm / 10)

def mw_to_dbm(p_mw):
    return 10 * math.log10(p_mw)

def adjust_tx_gain_by_frequency(tx, rx):
    """
    Корректирует максимальное усиление антенны передатчика, если частота выходит за рабочий диапазон.
    Интерполяция между gain_max и gain_oob на основе отношения частот.
    """
    f = rx['frequency_mhz']
    f_min = tx.get('freq_min')
    f_max = tx.get('freq_max')
    gain_max = tx.get('gain_max', 0)
    gain_oob = tx.get('gain_oob', -30)

    if not all([f, f_min, f_max]):
        return gain_max  # Нет данных — ничего не делаем

    f_center = (f_min + f_max) / 2
    abs_ratio = max(f / f_center, f_center / f)

    # Выбор коэффициентов a и b в зависимости от усиления
    if gain_max < 6.01:
        a, b = 1.2, 2.0
    elif gain_max < 15.01:
        a, b = 1.15, 1.75
    else:
        a, b = 1.1, 1.5

    if abs_ratio <= a:
        return gain_max
    elif abs_ratio >= b:
        return gain_oob
    else:
        alpha = (abs_ratio - a) / (b - a)
        return gain_max * (1 - alpha) + gain_oob * alpha



def check_blocking_interference(tx, rx, d_km, gt, gr):
    freq_offset = abs(tx['frequency_mhz'] - rx['frequency_mhz'])

    freq_threshold = rx.get('Freq_offset_block', None)
    block_rej = rx.get('Block_Rej', None)
    sensitivity = rx.get('sensitivity_dbm', None)

    if freq_threshold is None or block_rej is None or sensitivity is None:
        return None  # Недостаточно данных

    if freq_offset > freq_threshold:
        return None  # Вне зоны блокировки

    fspl = 20 * math.log10(d_km) + 20 * math.log10(tx['frequency_mhz']) + 32.44
    polar_loss = get_polarization_loss(tx.get('polarization'), rx.get('polarization'))

    Pblock = tx['power_dbm'] + gt + gr - tx['loss'] - rx['loss'] - fspl - polar_loss
    threshold = sensitivity + block_rej
    result = {
        'Pblock': Pblock,
        'threshold': threshold,
        'passed': Pblock <= threshold,
        'freq_offset': freq_offset,
        'limit': freq_threshold
    }
    return result

def compute_interference_level(tx: dict, rx: dict, distance_km: float, gt: float, gr: float) -> float:
    """
    Вычисляет уровень помехи от передатчика tx на приёмник rx,
    с учётом направленных усилений gt и gr.

    :param tx: словарь параметров передатчика (EN_dBm, BW_khz, freq_mhz и др.)
    :param rx: словарь параметров приёмника (ACS, BW_khz, freq_mhz и др.)
    :param distance_km: расстояние между антеннами в км
    :param gt: усиление передающей антенны по направлению на приёмник (дБи)
    :param gr: усиление приёмной антенны по направлению на передатчик (дБи)
    :return: уровень помехи в дБм
    """

    fspl_tx = 20 * math.log10(distance_km) + 20 * math.log10(tx['frequency_mhz']) + 32.44
    fspl_rx = 20 * math.log10(distance_km) + 20 * math.log10(rx['frequency_mhz']) + 32.44
    polar_loss = get_polarization_loss(tx.get('polarization', ''), rx.get('polarization', ''))


    delta_f = abs(tx['frequency_mhz'] - rx['frequency_mhz'])  # МГц
    delta_bw = 1.5 * (tx['BW_khz'] + rx['BW_khz']) / 1000  # МГц

    if delta_f >= delta_bw:

        en_rule = tx.get('EN_dBm_rule')
        if en_rule:
            EN_rx = en_rule['below_limit'] if rx['frequency_mhz'] <= en_rule['freq_limit_mhz'] else en_rule[
                'above_limit']
        else:
            EN_rx = tx.get('EN_dBm', -40)

        # --- Для Pint3 можно взять среднее как компромисс ---
        freq_avg = (tx['frequency_mhz'] + rx['frequency_mhz']) / 2
        if en_rule:
            EN_avg = en_rule['below_limit'] if freq_avg <= en_rule['freq_limit_mhz'] else en_rule['above_limit']
        else:
            EN_avg = tx.get('EN_dBm', -40)

        # Внеполосная помеха
        Pint1 = tx['power_dbm'] + gt + gr - tx['loss'] - rx['loss'] - fspl_tx - rx.get('ACS', 0)
        Pint2 = EN_rx + gt + gr - tx['loss'] - rx['loss'] - fspl_rx
        Pint3 = EN_avg + gt + gr - tx['loss'] - rx['loss'] - (fspl_tx + fspl_rx) / 2 - rx.get('ACS', 0)

        Psum_mw = dbm_to_mw(Pint1) + dbm_to_mw(Pint2) + dbm_to_mw(Pint3)
        Psum = mw_to_dbm(Psum_mw) - polar_loss

        print("📉 Полосы не перекрываются → внеполосные компоненты учтены:")
        print(f"  ∆f = {delta_f:.3f} МГц, ∆BW = {delta_bw:.3f} МГц")
        print(f"  Pint1 = {Pint1:.2f} дБм, Pint2 = {Pint2:.2f} дБм, Pint3 = {Pint3:.2f} дБм")
        print(f"  Суммарная помеха: {Psum:.2f} дБм")
    else:
        # Прямое наложение
        Psum = tx['power_dbm'] + gt + gr - tx['loss'] - rx['loss'] - fspl_tx - polar_loss
        print("⚠️ Полосы перекрываются → прямая мощная помеха:")
        print(f"  ∆f = {delta_f:.3f} МГц, ∆BW = {delta_bw:.3f} МГц")
        print(f"  Суммарная помеха: {Psum:.2f} дБм")

    return Psum

def check_field_induced_interference(tx, rx, d_km, gt):
    """
    Проверка помехи наведения на приёмную антенну
    """
    c = 3e8  # скорость света, м/с
    freq_hz = tx['frequency_mhz'] * 1e6
    lambda_m = c / freq_hz
    distance_m = d_km

    gain_tx = tx.get('gain_max', 0)
    if gain_tx < 9.01:
        limit = 1 * lambda_m
    elif gain_tx < 18.01:
        limit = 3 * lambda_m
    else:
        limit = 10 * lambda_m

    if distance_m > limit:
        return {
            'considered': False,
            'distance': distance_m,
            'lambda': lambda_m,
            'distance_limit': limit
        }

    # Расчёт мощности наведённого сигнала
    Ptx_mw = dbm_to_mw(tx['power_dbm'] - tx['loss'] + gt)
    E = math.sqrt(30 * Ptx_mw) / distance_m  # В/м
    A_eff = (lambda_m ** 2) / (4 * math.pi)
    Pinduced_mw = (E ** 2) * A_eff / 377
    Pinduced_dbm = mw_to_dbm(Pinduced_mw)

    return {
        'considered': True,
        'distance': distance_m,
        'lambda': lambda_m,
        'Pinduced_dbm': Pinduced_dbm,
        'threshold_dbm': -10,
        'passed': Pinduced_dbm < -10,
        'distance_limit': limit
    }
