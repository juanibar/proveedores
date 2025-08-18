# app.py — Buscador de Proveedores por país (Streamlit)
# Instrucciones rápidas:
# 1) Colocá "Proveedores.xlsx" en la misma carpeta que este archivo.
# 2) Instalá dependencias: pip install streamlit pandas openpyxl
# 3) Ejecutá: streamlit run app.py

import os
import io
import re
import unicodedata
import pandas as pd
import streamlit as st

# ----------------------------------------------
# Configuración básica de la página
# ----------------------------------------------
st.set_page_config(page_title="Proveedores por país", page_icon="🍻", layout="wide")
st.markdown(
    "[Accede a todas nuestras calculadoras para productores de bebidas en nuestra membresia www.nosoynormalcerveceria.com](https://nosoynormalcerveceria.com/p/suscripcion-nosoynormal)",
    unsafe_allow_html=True,
)
st.title("🍻Buscador de Proveedores por País")
st.caption("Elegí el país, ingresa un termino de busqueda (por ej: latas) y presiona enter.")

EXCEL_FILENAME = "Proveedores.xlsx"

# ----------------------------------------------
# Utilidades
# ----------------------------------------------

def _normalize_col(col: str) -> str:
    """Normaliza nombres de columnas para mapear variantes comunes."""
    if not isinstance(col, str):
        return ""
    c = col.strip().lower()
    c = c.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    c = c.replace("/", " /").replace("  ", " ")
    return c

COL_ALIASES = {
    # destino               # variantes comunes
    "nombre": {"nombre", "proveedor", "razon social", "razon social / nombre"},
    "web": {"web", "sitio web", "pagina", "pagina web", "website", "url"},
    "telefono": {"telefono", "tel", "whatsapp", "wa", "telefono/whatsapp"},
    "email": {"email", "mail", "e-mail", "correo", "correo electronico"},
    "pais": {"pais"},
    "provincia / estado": {"provincia / estado", "provincia", "estado", "provincia-estado", "provincia/estado"},
    "ciudad": {"ciudad", "localidad"},
    "direccion": {"direccion", "direc", "domicilio"},
    "productos": {"productos", "producto", "items", "categorias", "categoria"},
}

DISPLAY_ORDER = [
    "nombre", "web", "telefono", "email", "pais", "provincia / estado", "ciudad", "direccion"
]

@st.cache_data(show_spinner=False)
def load_workbook_from_bytes(b: bytes) -> dict:
    """Lee todas las hojas del Excel (en bytes) y devuelve un dict nombre_hoja -> DataFrame."""
    return pd.read_excel(io.BytesIO(b), sheet_name=None, dtype=str)

@st.cache_data(show_spinner=False)
def load_workbook_from_path(path: str) -> dict:
    return pd.read_excel(path, sheet_name=None, dtype=str)


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Mapea columnas reales a nombres estandarizados, crea vacías si faltan."""
    if df is None or df.empty:
        return pd.DataFrame(columns=[*DISPLAY_ORDER, "productos"])  # asegura estructura

    cols_norm = {_normalize_col(c): c for c in df.columns}

    mapping = {}
    for target, variants in COL_ALIASES.items():
        found = None
        for v in variants:
            if v in cols_norm:
                found = cols_norm[v]
                break
        if found is not None:
            mapping[found] = target

    # renombrar y dejar otras columnas como están
    df2 = df.rename(columns=mapping).copy()

    # asegurar todas las columnas necesarias
    for needed in set(DISPLAY_ORDER + ["productos"]):
        if needed not in df2.columns:
            df2[needed] = ""

    # limpieza básica de espacios
    for c in df2.columns:
        df2[c] = df2[c].fillna("").astype(str).str.strip()

    return df2


def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        s = str(s) if s is not None else ""
    s = s.strip()
    # Normalizar acentos para hacer búsqueda más amigable
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.casefold()


def tokenize_query(q: str) -> list:
    q = normalize_text(q)
    # separa por coma o espacios múltiples
    parts = re.split(r"[\s,;\u200b]+", q)
    terms = [p for p in parts if p]
    return terms


def match_row(productos_text: str, terms: list) -> bool:
    p = normalize_text(productos_text or "")
    # Coincidencia tipo AND: todos los términos deben estar presentes
    return all(t in p for t in terms)


# ----------------------------------------------
# Carga del archivo Excel
# ----------------------------------------------
excel_bytes = None
workbook = None

# Si el archivo está junto al script, usarlo
if os.path.exists(EXCEL_FILENAME):
    try:
        workbook = load_workbook_from_path(EXCEL_FILENAME)
    except Exception as e:
        st.warning(f"No se pudo abrir '{EXCEL_FILENAME}' del disco: {e}")

# Si no existe localmente, permitir subirlo
if workbook is None:
    st.info("Subí tu archivo **Proveedores.xlsx** o colocá el archivo junto a este script.")
    up = st.file_uploader("Cargar Excel de Proveedores", type=["xlsx"], accept_multiple_files=False)
    if up is not None:
        try:
            excel_bytes = up.getvalue()
            workbook = load_workbook_from_bytes(excel_bytes)
        except Exception as e:
            st.error(f"Error al leer el Excel: {e}")

if workbook is None:
    st.stop()  # no continuar sin libro

# ----------------------------------------------
# Selección de país (hoja)
# ----------------------------------------------
country_list = list(workbook.keys())
if not country_list:
    st.error("El Excel no contiene hojas. Asegurate de que cada país sea una hoja.")
    st.stop()

selected_country = st.selectbox("1) Seleccioná el país (hoja)", country_list, index=0)

# Obtener DataFrame de la hoja seleccionada y normalizar columnas
raw_df = workbook.get(selected_country)
if raw_df is None or raw_df.empty:
    st.warning("La hoja seleccionada no tiene datos.")
    st.stop()

df = standardize_columns(raw_df)

# ----------------------------------------------
# Búsqueda en tiempo real
# ----------------------------------------------
q = st.text_input(
    "2) Buscá por término(s) dentro de 'productos'",
    placeholder="Ej.: malta, lupulo, botellas",
    help="La búsqueda es insensible a mayúsculas/acentos. Podés separar múltiples términos por espacio o coma."
)

terms = tokenize_query(q) if q else []

if terms:
    mask = df["productos"].apply(lambda x: match_row(x, terms))
    results = df.loc[mask, DISPLAY_ORDER].reset_index(drop=True)
else:
    results = pd.DataFrame(columns=DISPLAY_ORDER)

# ----------------------------------------------
# Resultados
# ----------------------------------------------
st.markdown("---")
left, right = st.columns([1, 1])
with left:
    st.subheader("Resultados")
    if terms and results.empty:
        st.warning("No se encontraron proveedores")
    elif not terms:
        st.info("Ingresá uno o más términos para iniciar la búsqueda.")
    else:
        st.success(f"Se encontraron **{len(results)}** proveedor(es) en **{selected_country}**.")

with right:
    if not results.empty:
        csv = results.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="⬇️ Descargar resultados (CSV)",
            data=csv,
            file_name=f"proveedores_{selected_country}.csv",
            mime="text/csv",
        )

# Mostrar la tabla (si hay resultados)
if not results.empty:
    st.dataframe(results, use_container_width=True, hide_index=True)