# im3_web.py

from im3_analyzer import analyze_im3_candidates
from site_loader import process_unit
from ems_local_analyzer import analyze_tx_to_rx, format_ems_result
import pandas as pd
from antenna_utils import load_antenna_pattern, plot_antenna_patterns
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

st.title("Аналізатор впливу інтермодуляції (ІМ) та локальної ЕМС")

if "tx_list" not in st.session_state:
    st.session_state.tx_list = []

st.sidebar.subheader("➕ Додати передавач")
if st.sidebar.button("Додати TX"):
    st.session_state.tx_list.append({})

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
        tx['coords'] = (
            st.number_input(f"📍 X TX #{i+1} (м)", value=tx.get("coords", (0.0, 0.0, 20.0))[0],step=0.1, key=f"x_tx_{i}"),
            st.number_input(f"📍 Y TX #{i+1} (м)", value=tx.get("coords", (0.0, 0.0, 20.0))[1],step=0.1, key=f"y_tx_{i}"),
            st.number_input(f"📍 Z TX #{i+1} (м)", value=tx.get("coords", (0.0, 0.0, 20.0))[2],step=0.1, key=f"z_tx_{i}")
        )
        tx['loss'] = st.number_input(f"📉 Втрати TX #{i+1} (дБ)", value=tx.get("loss", 2.0),step=0.1, key=f"loss_tx_{i}")

        try:
            process_unit(tx, "DeviceDB.xlsx", "AntennaDN.xlsx", index=i, role="tx")
            st.success("✅ Передавач успішно перевірено на відповідність параметрів.")
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
    rx['coords'] = (
        st.number_input("📍 X RX (м)", value=rx.get("coords", (0.0, 0.0, 25.0))[0],step=0.1, key="x_rx"),
        st.number_input("📍 Y RX (м)", value=rx.get("coords", (0.0, 0.0, 25.0))[1],step=0.1, key="y_rx"),
        st.number_input("📍 Z RX (м)", value=rx.get("coords", (0.0, 0.0, 25.0))[2],step=0.1, key="z_rx")
    )
    rx['loss'] = st.number_input("📉 Втрати RX (дБ)", value=rx.get("loss", 2.0),step=0.1, key="loss_rx")
    rx['sensitivity_dbm'] = st.number_input("🎚️ Чутливість RX (дБм)", value=rx.get("sensitivity_dbm", -117.0),step=0.1, key="sens_rx")

    try:
        process_unit(rx, "DeviceDB.xlsx", "AntennaDN.xlsx", index=0, role="rx")
        st.success("✅ Приймач успішно перевірено на відповідність параметрів.")
    except ValueError as e:
        st.error(str(e))

st.markdown("---")
st.subheader("📡 Побудова діаграм направленості антен")

antenna_to_plot = st.selectbox("📁 Виберіть антену для побудови ДН", ANTENNA_NAMES)

if st.button("📈 Побудувати ДН"):
    try:
        hor_df, vert_df = load_antenna_pattern("AntennaDN.xlsx", sheet_name=antenna_to_plot)
        fig = plot_antenna_patterns(hor_df, vert_df, sheet_name=antenna_to_plot)
        st.pyplot(fig)
    except Exception as e:
        st.error(f"Не вдалося побудувати ДН: {e}")

st.markdown("---")

if st.button("▶️ Виконати аналіз IM"):
    st.subheader("📈 Результати IM3")

    if len(tx_list) < 2:
        warning = "⚠️ At least two transmitters must be selected to perform intermodulation analysis."
        st.warning(warning)
        st.session_state.report_text = warning
    else:
        result = analyze_im3_candidates(
            {"tx_list": tx_list, "rx_list": [rx]},
            tx_ids=list(range(len(tx_list))),
            rx_id=0,
            show_levels=True,
            use_markdown=True
        )
        st.markdown(result.replace("\n", "<br>"), unsafe_allow_html=True)
        st.session_state.report_text = result

if st.button("📡 Виконати аналіз локальної ЕМС"):
    st.subheader("📈 Результати локального ЕМС")

    full_text = ""

    for i, tx in enumerate(tx_list):
        try:
            res = analyze_tx_to_rx(tx, rx)
            formatted = format_ems_result(res, tx_index=i)
            full_text += formatted + "\n\n"
        except Exception as e:
            full_text += f"❌ TX #{i+1} → RX: Помилка: {e}\n\n"

    st.markdown(full_text.replace("\n", "<br>"), unsafe_allow_html=True)
    st.session_state.local_ems_report = full_text



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
