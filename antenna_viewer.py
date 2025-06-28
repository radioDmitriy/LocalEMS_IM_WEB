# antenna_viewer.py

import math
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from site_config import site
from site_loader import process_site
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.ticker as mticker


class SmartFormatter(mticker.Formatter):
    def __call__(self, x, pos=None):
        if x == int(x):
            return f"{int(x)}"
        else:
            return f"{x:.1f}"


def draw_antenna(ax, ant, color='blue'):
    x, y, z = ant['coords']
    label = ant.get('label', '')
    print(f"Drawing antenna {label} at ({x}, {y}, {z}) with color {color}")

    az = math.radians(ant['azimuth'])
    el = math.radians(ant['elevation'])
    dx = math.sin(az) * math.cos(el)
    dy = math.cos(az) * math.cos(el)
    dz = math.sin(el)

    ax.scatter(x, y, z, s=100, color=color)
    ax.quiver(x, y, z, dx, dy, dz, length=3, color=color)
    ax.text(x, y, z + 2, label, color='black', fontsize=10)


def draw_mast(ax, width=5, depth=5, height=50, alpha=0.1):
    x0, y0, z0 = 0, 0, 0
    w, d, h = width, depth, height

    corners = [
        (x0 - w/2, y0 - d/2, z0),
        (x0 + w/2, y0 - d/2, z0),
        (x0 + w/2, y0 + d/2, z0),
        (x0 - w/2, y0 + d/2, z0),
        (x0 - w/2, y0 - d/2, z0 + h),
        (x0 + w/2, y0 - d/2, z0 + h),
        (x0 + w/2, y0 + d/2, z0 + h),
        (x0 - w/2, y0 + d/2, z0 + h),
    ]

    faces = [
        [corners[0], corners[1], corners[2], corners[3]],  # низ
        [corners[4], corners[5], corners[6], corners[7]],  # верх
        [corners[0], corners[1], corners[5], corners[4]],  # перед
        [corners[1], corners[2], corners[6], corners[5]],  # правая
        [corners[2], corners[3], corners[7], corners[6]],  # задняя
        [corners[3], corners[0], corners[4], corners[7]],  # левая
    ]

    ax.add_collection3d(Poly3DCollection(faces, facecolors='gray', linewidths=0.5, edgecolors='gray', alpha=alpha))


def check_antenna_position(ant, mast_size):
    w, d, h = mast_size

    if not isinstance(ant, dict) or 'coords' not in ant:
        return [f"⚠️ Антена без координат: {ant.get('label', '')}"]

    coords = ant['coords']
    if not isinstance(coords, (list, tuple)) or len(coords) != 3:
        return [f"⚠️ Невірний формат координат в антені: {ant.get('label', '')}"]

    x, y, z = coords
    margin = 1  # метр запаса

    warnings = []

    if not (-w/2 - margin <= x <= w/2 + margin):
        warnings.append(f"⚠️ Антена '{ant.get('label', '')}' по X={x:.2f} виходить за межі щогли ±{margin} м!")
    if not (-d/2 - margin <= y <= d/2 + margin):
        warnings.append(f"⚠️ Антена '{ant.get('label', '')}' по Y={y:.2f} виходить за межі щогли ±{margin} м!")
    if not (0 <= z <= h + margin):
        warnings.append(f"⚠️ Антена '{ant.get('label', '')}' по Z={z:.2f} виходить за межі щогли +{margin} м!")

    return warnings


def visualize_all_antennas(tx_list, rx_list, mast_size=(5, 5, 50), show=True, print_warnings=False):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    draw_mast(ax, *mast_size)

    all_warnings = []

    for i, tx in enumerate(tx_list):
        tx = tx.copy()
        tx.setdefault('label', f'TX{i + 1}')
        wns = check_antenna_position(tx, mast_size)
        all_warnings.extend(wns)
        draw_antenna(ax, tx, color='red')

    for j, rx in enumerate(rx_list):
        rx = rx.copy()
        rx.setdefault('label', f'RX{j + 1}')
        wns = check_antenna_position(rx, mast_size)
        all_warnings.extend(wns)
        draw_antenna(ax, rx, color='green')

    ax.set_xlabel('X [м]', fontsize=8)
    ax.set_ylabel('Y [м]', fontsize=8)
    ax.set_zlabel('Z [м]', fontsize=8)
    ax.set_title('Мачта та антени', fontsize=10, fontweight='bold')

    ax.xaxis.set_major_formatter(SmartFormatter())
    ax.yaxis.set_major_formatter(SmartFormatter())
    ax.zaxis.set_major_formatter(SmartFormatter())

    ax.tick_params(axis='both', which='major', labelsize=8)
    ax.tick_params(axis='z', which='major', labelsize=10)

    w, d, h = mast_size

    margin_xy = max(w, d) * 0.6
    margin_z = h * 0.05

    ax.set_xlim(-w/2 - margin_xy, w/2 + margin_xy)
    ax.set_ylim(-d/2 - margin_xy, d/2 + margin_xy)
    ax.set_zlim(0, h + margin_z)

    aspect_xy = 1
    aspect_z = min(3.0, max(1.2, h / max(w, d)))
    ax.set_box_aspect([aspect_xy, aspect_xy, aspect_z])

    ax.plot([], [], [], color='red', label='TX')
    ax.plot([], [], [], color='green', label='RX')
    ax.plot([], [], [], color='gray', linestyle='--', label='Мачта')

    leg = ax.legend(fontsize=8)
    for t in leg.get_texts():
        t.set_fontweight('bold')

    plt.tight_layout()

    if print_warnings:
        for w in all_warnings:
            print(w)

    if show:
        plt.show()

    return fig  # только fig, не (fig, warnings)

def get_antenna_warnings(tx_list, rx_list, mast_size=(5, 5, 50)):
    all_warnings = []
    for tx in tx_list:
        if isinstance(tx, dict) and 'coords' in tx:
            all_warnings.extend(check_antenna_position(tx, mast_size))
    for rx in rx_list:
        if isinstance(rx, dict) and 'coords' in rx:
            all_warnings.extend(check_antenna_position(rx, mast_size))
    return all_warnings


if __name__ == "__main__":
    processed_site = process_site(site, "DeviceDB.xlsx", "AntennaDN.xlsx")
    fig, warnings = visualize_all_antennas(
        processed_site['tx_list'],
        processed_site['rx_list'],
        mast_size=(10, 10, 60),
        show=True,
        print_warnings=True  # не show_warnings

    )
