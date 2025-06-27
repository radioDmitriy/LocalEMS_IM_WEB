# antenna_utils.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_antenna_pattern(file_path, sheet_name):
    """Загружает горизонтальную и вертикальную ДН из Excel"""
    df = pd.read_excel(file_path, sheet_name=sheet_name)

    hor_df = df.iloc[:, [0, 1]].dropna()
    hor_df.columns = ['azimuth_deg', 'attenuation_db']
    hor_df['azimuth_deg'] = pd.to_numeric(hor_df['azimuth_deg'], errors='coerce')
    hor_df['attenuation_db'] = pd.to_numeric(hor_df['attenuation_db'], errors='coerce')
    hor_df = hor_df.dropna()

    vert_df = df.iloc[:, [4, 5]].dropna()
    vert_df.columns = ['elevation_deg', 'attenuation_db']
    vert_df['elevation_deg'] = pd.to_numeric(vert_df['elevation_deg'], errors='coerce')
    vert_df['attenuation_db'] = pd.to_numeric(vert_df['attenuation_db'], errors='coerce')
    vert_df = vert_df.dropna()

    return hor_df, vert_df

def load_antenna_pattern_with_info(file_path, sheet_name):
    """
    Загружает ДН (горизонтальную и вертикальную) и параметры антенны из Excel.
    Возвращает: hor_df, vert_df, info
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    info = {}
    for i in range(6):
        key = str(df.iloc[i, 0]).strip()
        val = df.iloc[i, 1]
        info[key] = val

    hor_start = df[df.iloc[:, 0] == "Azimuth (°)"].index[0] + 1
    vert_start = df[df.iloc[:, 4] == "Elevation (°)"].index[0] + 1

    hor_df = df.iloc[hor_start:, [0, 1]].dropna()
    hor_df.columns = ['azimuth_deg', 'attenuation_db']
    hor_df['azimuth_deg'] = pd.to_numeric(hor_df['azimuth_deg'], errors='coerce')
    hor_df['attenuation_db'] = pd.to_numeric(hor_df['attenuation_db'], errors='coerce')
    hor_df = hor_df.dropna()

    vert_df = df.iloc[vert_start:, [4, 5]].dropna()
    vert_df.columns = ['elevation_deg', 'attenuation_db']
    vert_df['elevation_deg'] = pd.to_numeric(vert_df['elevation_deg'], errors='coerce')
    vert_df['attenuation_db'] = pd.to_numeric(vert_df['attenuation_db'], errors='coerce')
    vert_df = vert_df.dropna()

    return hor_df, vert_df, info

def interpolate_gain(df, angle, angle_col):
    """
    Интерполирует ослабление по направлению.
    angle_col — 'azimuth_deg' или 'elevation_deg'
    Возвращает отрицательное значение усиления (ослабление в дБ)
    """
    angles = pd.to_numeric(df[angle_col], errors='coerce')
    gains = pd.to_numeric(df['attenuation_db'], errors='coerce')

    mask = angles.notna() & gains.notna()
    angles = angles[mask].values.astype(float)
    gains = gains[mask].values.astype(float)

    if angle_col == 'azimuth_deg':
        angle %= 360
        angles = np.concatenate([angles, angles + 360])
        gains = np.concatenate([gains, gains])

    return float(np.interp(angle, angles, gains))

def auto_scale(ax, data, title):
    min_val = np.min(data)
    max_val = 0.5
    step = 3 if min_val > -30 else 10
    lower_limit = step * (int(min_val / step) - 1)

    ax.set_ylim(lower_limit, max_val)
    ax.set_yticks(np.arange(0, lower_limit - 1, -step))
    ax.set_title(title)
    ax.grid(True)

def plot_antenna_patterns(hor_df, vert_df, sheet_name=""):
    plt.close('all')
    angles_hor = np.deg2rad(hor_df['azimuth_deg'].values)
    gains_hor = hor_df['attenuation_db'].values

    angles_vert = np.deg2rad(vert_df['elevation_deg'].values)
    gains_vert = vert_df['attenuation_db'].values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), subplot_kw={'projection': 'polar'})

    ax1.plot(angles_hor, gains_hor, label='Ослаблення (дБ)')
    ax1.set_theta_zero_location('N')
    ax1.set_theta_direction(-1)
    auto_scale(ax1, gains_hor, f'Горизонтальна ДН\n{sheet_name}')
    ax1.legend(loc='lower right')
    ax1.format_coord = lambda theta, r: f"Азимут: {np.rad2deg(theta):.1f}°  Ослаблення: {r:.1f} дБ"

    ax2.plot(angles_vert, gains_vert, label='Ослаблення (дБ)', color='orange')
    ax2.set_theta_zero_location('E')
    ax2.set_theta_direction(-1)
    auto_scale(ax2, gains_vert, f'Вертикальна ДН\n{sheet_name}')
    ax2.legend(loc='lower right')
    ax2.format_coord = lambda theta, r: f"Кут місця: {np.rad2deg(theta):.1f}°  Ослаблення: {r:.1f} дБ"

    plt.tight_layout()
    return fig  # повертає matplotlib-об'єкт
   # plt.show()


