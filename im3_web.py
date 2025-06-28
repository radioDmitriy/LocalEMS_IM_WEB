# im3_web.py

from im3_analyzer import analyze_im3_candidates
from site_loader import process_unit
from ems_local_analyzer import analyze_tx_to_rx, format_ems_result
import pandas as pd
from antenna_utils import load_antenna_pattern, plot_antenna_patterns
from antenna_viewer import visualize_all_antennas
from antenna_viewer import check_antenna_position, get_antenna_warnings
import streamlit as st
import os
from fpdf import FPDF
import base64
import tempfile


# === Завантаження даних ===
def load_device_names_from_columns(filename, sheet_name=0):
    df = pd.read_excel(filename, sheet_name=sheet_name, header=0)
    return list(df.columns[1:])

def load_antenna_sheet_names(filename):
    xls = pd.ExcelFile(filename)
    return xls.sheet_names

DEVICE_NAMES = load_device_names_from_columns("DeviceDB.xlsx")
ANTENNA_NAMES = load_antenna_sheet_names("AntennaDN.xlsx")

st.header("Аналізатор ЕМС між радіоелектроними засобами на локальному об'єкті")

if "tx_list" not in st.session_state:
    st.session_state.tx_list = []

# --- Sidebar ---
st.sidebar.subheader("➕ Додати передавач")

if st.sidebar.button("Додати TX"):
    st.session_state.tx_list.append({
        'device_name': DEVICE_NAMES[0],
        'antenna_name': ANTENNA_NAMES[0],
        'power_dbm': 44.0,
        'frequency_mhz': 160.0,
        'BW_khz': 12.5,
        'azimuth': 0.0,
        'elevation': 0.0,
        'coords': (0.0, 0.0, 20.0),  # обязательно инициализируем coords
        'loss': 4.0
    })

st.sidebar.markdown("### Розміри мачти")

mast_x = st.sidebar.number_input("Ширина мачти X (м)", min_value=1.0, value=10.0, step=0.1, key="mast_x")
mast_y = st.sidebar.number_input("Глибина мачти Y (м)", min_value=1.0, value=10.0, step=0.1, key="mast_y")
mast_z = st.sidebar.number_input("Висота мачти Z (м)", min_value=1.0, value=40.0, step=0.1, key="mast_z")

mast_size = (mast_x, mast_y, mast_z)

if "show_mast" not in st.session_state:
    st.session_state.show_mast = False

if st.sidebar.button("Візуалізувати мачту з антенами"):
    st.session_state.show_mast = True
    st.session_state.expand_im3_results = False  # ⬅️ Сброс
    st.session_state.expand_ems_results = False

if st.sidebar.button("Закрити візуалізацію"):
    st.session_state.show_mast = False

if st.session_state.show_mast:
    tx_list = st.session_state.tx_list
    rx = st.session_state.rx
    if (len(tx_list) == 0 and (not rx or rx == {})):
        st.sidebar.warning("⚠️ Потрібно додати хоча б один передавач або приймач.")
    else:
        fig = visualize_all_antennas(tx_list, [rx], mast_size=mast_size, show=False)
        st.pyplot(fig)

if "rx" not in st.session_state:
    st.session_state.rx = {}
if "expanded_rx" not in st.session_state:
    st.session_state.expanded_rx = False

st.subheader("📡 Налаштування передавачів")
tx_list = st.session_state.tx_list
for i, tx in enumerate(tx_list):
    with st.expander(f"📡 Передавач #{i+1}", expanded=False):
        tx['device_name'] = st.selectbox(f"📻 Пристрій TX #{i+1}", DEVICE_NAMES, index=DEVICE_NAMES.index(tx.get("device_name", DEVICE_NAMES[0])), key=f"device_name_tx_{i}")
        tx['antenna_name'] = st.selectbox(f"📡 Антена TX #{i+1}", ANTENNA_NAMES, index=ANTENNA_NAMES.index(tx.get("antenna_name", ANTENNA_NAMES[0])), key=f"antenna_tx_{i}")
        tx['power_dbm'] = st.number_input(f"🔌 Потужність TX #{i+1} (дБм)", value=tx.get("power_dbm", 44.0), step=0.1, key=f"power_tx_{i}")
        tx['frequency_mhz'] = st.number_input(f"📶 Частота TX #{i+1} (МГц)", value=tx.get("frequency_mhz", 160.0),step=0.1, key=f"freq_tx_{i}")
        tx['BW_khz'] = st.number_input(f"📏 Ширина смуги TX #{i + 1} (кГц)", value=tx.get("BW_khz", 12.5), step=0.1, key=f"bw_tx_{i}")
        tx['azimuth'] = st.number_input(f"🧭 Азимут TX #{i+1} (°)", value=tx.get("azimuth", 0.0),step=0.1, key=f"azimuth_tx_{i}")
        tx['elevation'] = st.number_input(f"🎯 Кут місця TX #{i+1} (°)", value=tx.get("elevation", 0.0),step=0.1, key=f"elevation_tx_{i}")
        coords = tx.get("coords")
        if not coords or len(coords) != 3:
            coords = (0.0, 0.0, 20.0)

        tx['coords'] = (
            st.number_input(f"📍 X TX #{i + 1} (м)", value=coords[0], step=0.1, key=f"x_tx_{i}"),
            st.number_input(f"📍 Y TX #{i + 1} (м)", value=coords[1], step=0.1, key=f"y_tx_{i}"),
            st.number_input(f"📍 Z TX #{i + 1} (м)", value=coords[2], step=0.1, key=f"z_tx_{i}")
        )

        tx['loss'] = st.number_input(f"📉 Втрати TX #{i+1} (дБ)", value=tx.get("loss", 4.0),step=0.1, key=f"loss_tx_{i}")

        try:
            process_unit(tx, "DeviceDB.xlsx", "AntennaDN.xlsx", index=i, role="tx")
            st.success("✅ Передавач успішно перевірено на відповідність параметрів.")

            # Показываем предупреждения по позициям для всех антенн текущего набора:
            warnings = get_antenna_warnings(st.session_state.tx_list, [st.session_state.rx],
                                            mast_size=(mast_x, mast_y, mast_z))
            for w in warnings:
                st.warning(w)

        except ValueError as e:
            st.error(str(e))

st.subheader("📡 Налаштування приймача")
rx = st.session_state.rx
with st.expander("📡 Приймач", expanded=st.session_state.expanded_rx):
    rx['device_name'] = st.selectbox("📻 Пристрій RX", options=DEVICE_NAMES, index=DEVICE_NAMES.index(rx.get("device_name", DEVICE_NAMES[0])), key="device_name_rx")
    rx['antenna_name'] = st.selectbox("📡 Антена RX", options=ANTENNA_NAMES, index=ANTENNA_NAMES.index(rx.get("antenna_name", ANTENNA_NAMES[0])), key="antenna_rx")
    rx['frequency_mhz'] = st.number_input("📶 Частота RX (МГц)", value=rx.get("frequency_mhz", 150.0),step=0.1, key="freq_rx")
    rx['BW_khz'] = st.number_input("📏 Ширина смуги RX (кГц)", value=rx.get("BW_khz", 12.5), step=0.1, key="bw_rx")
    rx['azimuth'] = st.number_input("🧭 Азимут RX (°)", value=rx.get("azimuth", 0.0),step=0.1, key="azimuth_rx")
    rx['elevation'] = st.number_input("🎯 Кут місця RX (°)", value=rx.get("elevation", 0.0),step=0.1, key="elevation_rx")
    coords = rx.get("coords")
    if not coords or len(coords) != 3:
        coords = (0.0, 0.0, 25.0)

    rx['coords'] = (
        st.number_input(f"📍 X RX (м)", value=coords[0], step=0.1, key=f"x_rx"),
        st.number_input(f"📍 Y RX (м)", value=coords[1], step=0.1, key=f"y_rx"),
        st.number_input(f"📍 Z RX (м)", value=coords[2], step=0.1, key=f"z_rx")
    )
    rx['loss'] = st.number_input("📉 Втрати RX (дБ)", value=rx.get("loss", 4.0),step=0.1, key="loss_rx")
    rx['sensitivity_dbm'] = st.number_input("🎚️ Чутливість RX (дБм)", value=rx.get("sensitivity_dbm", -117.0),step=0.1, key="sens_rx")

    try:
        process_unit(rx, "DeviceDB.xlsx", "AntennaDN.xlsx", index=0, role="rx")
        st.success("✅ Приймач успішно перевірено на відповідність параметрів.")

        warnings = get_antenna_warnings(st.session_state.tx_list, [rx], mast_size=(mast_x, mast_y, mast_z))
        for w in warnings:
            st.warning(w)

    except ValueError as e:
        st.error(str(e))

st.markdown("---")
st.subheader("📡 Побудова діаграм направленості антен")

# Добавляем флаг отображения диаграммы направленості, если его ещё нет
if "show_antenna_pattern" not in st.session_state:
    st.session_state.show_antenna_pattern = False

antenna_to_plot = st.selectbox("📁 Виберіть антену для побудови ДН", ANTENNA_NAMES)

if st.button("📈 Побудувати ДН", key="build_pattern"):
    st.session_state.show_antenna_pattern = True
    st.session_state.expand_im3_results = False  # ⬅️ Сброс
    st.session_state.expand_ems_results = False  # ⬅️ Сброс

if st.session_state.show_antenna_pattern:
    try:
        hor_df, vert_df = load_antenna_pattern("AntennaDN.xlsx", sheet_name=antenna_to_plot)
        fig = plot_antenna_patterns(hor_df, vert_df, sheet_name=antenna_to_plot)
        st.pyplot(fig)

        if st.button("❌ Закрити ДН", key="close_pattern"):
            st.session_state.show_antenna_pattern = False
    except Exception as e:
        st.error(f"Не вдалося побудувати ДН: {e}")

st.markdown("---")

if st.button("▶️ Виконати аналіз IM"):
    if len(tx_list) < 2:
        warning = "⚠️ At least two transmitters must be selected to perform intermodulation analysis."
        st.warning(warning)
        st.session_state.report_text = warning
        st.session_state.expand_im3_results = True
    else:
        result = analyze_im3_candidates(
            {"tx_list": tx_list, "rx_list": [rx]},
            tx_ids=list(range(len(tx_list))),
            rx_id=0,
            show_levels=True,
            use_markdown=True
        )
        st.session_state.report_text = result
        st.session_state.expand_im3_results = True

if st.button("📡 Виконати аналіз локальної ЕМС"):
    if not tx_list:
        warning = "⚠️ t least one transmitter must be selected to perform local EMC analysis."
        st.warning(warning)
        st.session_state.report_text = warning
        st.session_state.expand_ems_results = True
    else:
        full_text = ""
        for i, tx in enumerate(tx_list):
            try:
                res = analyze_tx_to_rx(tx, rx)
                formatted = format_ems_result(res, tx_index=i, rx=rx)
                full_text += formatted + "\n\n"
            except Exception as e:
                full_text += f"❌ TX #{i+1} → RX: Помилка: {e}\n\n"
        st.session_state.local_ems_report = full_text
        st.session_state.expand_ems_results = True




# === Collect TX/RX info in English ===
def format_tx_info(tx_list):
    lines = []
    for i, tx in enumerate(tx_list):
        lines.append(f"Transmitter #{i+1}:")
        lines.append(f"  Device: {tx.get('device_name', '')}")
        lines.append(f"  Antenna: {tx.get('antenna_name', '')}")
        lines.append(f"  Power: {tx.get('power_dbm', '')} dBm")
        lines.append(f"  Frequency: {tx.get('frequency_mhz', '')} MHz")
        lines.append(f"  Bandwidth: {tx.get('BW_khz', '')} kHz")
        lines.append(f"  Azimuth: {tx.get('azimuth', '')} °")
        lines.append(f"  Elevation: {tx.get('elevation', '')} °")
        x, y, z = tx.get('coords', (0, 0, 0))
        lines.append(f"  Coordinates: X={x}, Y={y}, Z={z} m")
        lines.append(f"  Cable loss: {tx.get('loss', '')} dB\n")
    return "\n".join(lines)

def format_rx_info(rx):
    lines = []
    lines.append("Receiver:")
    lines.append(f"  Device: {rx.get('device_name', '')}")
    lines.append(f"  Antenna: {rx.get('antenna_name', '')}")
    lines.append(f"  Frequency: {rx.get('frequency_mhz', '')} MHz")
    lines.append(f"  Bandwidth: {rx.get('BW_khz', '')} kHz")
    lines.append(f"  Azimuth: {rx.get('azimuth', '')} °")
    lines.append(f"  Elevation: {rx.get('elevation', '')} °")
    x, y, z = rx.get('coords', (0, 0, 0))
    lines.append(f"  Coordinates: X={x}, Y={y}, Z={z} m")
    lines.append(f"  Cable loss: {rx.get('loss', '')} dB")
    lines.append(f"  Sensitivity: {rx.get('sensitivity_dbm', '')} dBm\n")
    return "\n".join(lines)

if "expand_im3_results" not in st.session_state:
    st.session_state.expand_im3_results = False

if "expand_ems_results" not in st.session_state:
    st.session_state.expand_ems_results = False


# Показываем оба отчёта в разворачиваемых блоках
if 'report_text' in st.session_state:
    with st.expander("📈 Результати IM3", expanded=st.session_state.expand_im3_results):
        st.markdown(st.session_state.report_text.replace("\n", "<br>"), unsafe_allow_html=True)

if 'local_ems_report' in st.session_state:
    with st.expander("📈 Результати локального ЕМС", expanded=st.session_state.expand_ems_results):
        st.markdown(st.session_state.local_ems_report.replace("\n", "<br>"), unsafe_allow_html=True)


# === Save PDF Report ===
if 'report_text' in st.session_state and 'local_ems_report' in st.session_state and 'tx_list' in st.session_state and 'rx' in st.session_state:
    if st.button("💾 Завантажити звіт в PDF"):
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)

            intro = "EMC Analysis Module - LocalEMS\nAuthor: dikatama.dm@mail.com\n\n"
            tx_info = format_tx_info(st.session_state.tx_list)
            rx_info = format_rx_info(st.session_state.rx)
            im3_analysis = st.session_state.report_text.encode("ascii", errors="ignore").decode("ascii")
            ems_analysis = st.session_state.local_ems_report.encode("ascii", errors="ignore").decode("ascii")

            full_text = intro + tx_info + "\n" + rx_info + "\n" + im3_analysis + "\n" + ems_analysis
            pdf.multi_cell(0, 6, full_text)

            temp_pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            pdf.output(temp_pdf_path)

            with open(temp_pdf_path, "rb") as f:
                b64_pdf = base64.b64encode(f.read()).decode("utf-8")
            os.remove(temp_pdf_path)

            href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="EMC_report.pdf">📄 Завантажити звіт в PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error creating PDF: {e}")
