# site_loader.py

import pandas as pd
from antenna_utils import load_antenna_pattern_with_info
import sys

def process_unit(unit, device_file, antenna_file, index=None, role='tx'):
    import sys

    device_name = unit.get('device_name', '').strip()
    prefix = f"{role.upper()} #{index+1}" if index is not None else role.upper()

    # === Загрузка базы устройств ===
    df = pd.read_excel(device_file, header=None)
    headers = df.iloc[0].dropna().astype(str).str.strip().tolist()

    if device_name not in headers:
        print(f"\n📛 Ошибка: {prefix} — пристрій '{device_name}' не знайдено в базі DeviceDB.xlsx", file=sys.stderr)
        print(f"🔎 Перевірте коректність написання назви пристрою в конфігурації сайта.", file=sys.stderr)
        sys.exit(1)

    device_col = df.columns[df.iloc[0].astype(str).str.strip() == device_name][0]
    param_col = df.columns[0]
    device_params = df[[param_col, device_col]].dropna().iloc[1:]
    param_dict = dict(zip(device_params.iloc[:, 0].astype(str).str.strip(), device_params.iloc[:, 1]))

    # === Проверка диапазонов и допустимых значений ===
    prefix = f"{role.upper()} #{index+1}" if index is not None else role.upper()

    def validate(value, key_min, key_max, label):
        min_val = param_dict.get(key_min, value)
        max_val = param_dict.get(key_max, value)
        if not (min_val <= value <= max_val):
            raise ValueError(
                f"❌ {prefix}: {label} = {value} поза допустимим діапазоном [{min_val}, {max_val}]"
            )
        return value

    def validate_choice(value, allowed_values, label):
        if value not in allowed_values:
            raise ValueError(
                f"❌ {prefix}: {label} = {value} не входить у допустимі значення: {allowed_values}"
            )
        return value

    # === Роль TX или RX ===
    if role == 'tx':
        unit['power_dbm'] = validate(unit.get('power_dbm', param_dict.get('TX Power Default (dBm)', 30)),
                                     'TX Power Min (dBm)', 'TX Power Max (dBm)', 'Потужність передавача')
    if role == 'rx':
        if 'RX Sensitivity Default  (dBm)' in param_dict:
            unit['sensitivity_dbm'] = validate(
                unit.get('sensitivity_dbm', param_dict['RX Sensitivity Default  (dBm)']),
                'RX Sensitivity Min  (dBm)', 'RX Sensitivity Max  (dBm)', 'Чутливість приймача')

    # === Частота ===
    unit['frequency_mhz'] = validate(unit.get('frequency_mhz', param_dict.get('TX Frequency Default (MHz)', 150)),
                                     'Freq Min (MHz)', 'Freq Max (MHz)', 'Частота')

    # === Ширина полосы ===
    bw_opts = param_dict.get('BW Options (kHz)', '12.5')
    try:
        allowed_bw = [float(b.strip()) for b in str(bw_opts).split(',')]
    except Exception:
        allowed_bw = [12.5]  # fallback
    unit['BW_khz'] = validate_choice(unit.get('BW_khz', allowed_bw[0]), allowed_bw, 'Ширина смуги (BW_khz)')

    # === Дополнительные параметры ===
    # === Уровень излучения вне полосы (EN_dBm) — только для TX
    if role == 'tx' and 'EN_dBm' not in unit and \
            'EN Freq Limit (MHz)' in param_dict and \
            'EN Below Limit (dBm)' in param_dict and \
            'EN Above Limit (dBm)' in param_dict:
        freq_limit = float(param_dict['EN Freq Limit (MHz)'])
        en_below = float(param_dict['EN Below Limit (dBm)'])
        en_above = float(param_dict['EN Above Limit (dBm)'])

        unit['EN_dBm_rule'] = {
            'freq_limit_mhz': freq_limit,
            'below_limit': en_below,
            'above_limit': en_above
        }

    if role == 'rx' and 'ACS' not in unit and 'RX ACS (dB)' in param_dict:
        unit['ACS'] = param_dict['RX ACS (dB)']
        # === Параметры блокирующей помехи ===
        if 'RX Freq_offset_block (MHz)' in param_dict:
            unit['Freq_offset_block'] = float(param_dict['RX Freq_offset_block (MHz)'])
        if 'RX Block_Rej (dB)' in param_dict:
            unit['Block_Rej'] = float(param_dict['RX Block_Rej (dB)'])
    # === Антенна ===
    ant_name = unit.get('antenna_name', '').strip()
    try:
        hor, vert, ant_info = load_antenna_pattern_with_info(antenna_file, ant_name)
    except Exception:
        print(f"\n📛 Помилка: {prefix} — антена '{ant_name}' не знайдена в базі AntennaDN.xlsx", file=sys.stderr)
        print(f"🔎 Перевірте коректність написання назви антени в конфигурації сайта.", file=sys.stderr)
        sys.exit(1)

    unit['gain_max'] = ant_info.get('Max Gain (dBi)', 0)
    unit['polarization'] = ant_info.get('Polarisation', 'вертик')
    unit['freq_min'] = ant_info.get('Freq Min (MHz)', 0)
    unit['freq_max'] = ant_info.get('Freq Max (MHz)', 0)
    unit['gain_oob'] = ant_info.get('Gain OOB (dBi)', -20)

    return unit

def process_site(site, device_file, antenna_file):
    site['tx_list'] = [process_unit(tx, device_file, antenna_file, index=i, role='tx') for i, tx in enumerate(site.get('tx_list', []))]
    site['rx_list'] = [process_unit(rx, device_file, antenna_file, index=i, role='rx') for i, rx in enumerate(site.get('rx_list', []))]
    return site
