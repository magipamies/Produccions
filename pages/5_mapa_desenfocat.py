# -*- coding: utf-8 -*-
"""

author: magipamies
datetime:19/8/2026 15:16
"""
import base64
import io
import json

import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import plotly.graph_objects as go
import plotly.colors as pcolors
from PIL import Image, ImageDraw, ImageFilter

st.set_page_config(page_title="Mapa difuminat de municipis (prova)", layout="wide")


@st.cache_data
def load_data():
    df = pd.read_csv("data_flourish_muni_histo26_rs.csv")
    df["ID_MUN"] = df["ID_MUN"].astype("int64")
    return df


@st.cache_data
def load_geometria(tolerance=0.0008):
    gdf = gpd.read_file("muni_cat.geojson")
    gdf["ID_MUN"] = gdf["ID_MUN"].astype("int64")
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    gdf["geometry"] = gdf["geometry"].simplify(tolerance, preserve_topology=True)
    return gdf


@st.cache_data
def geometria_a_geojson(_gdf):
    return json.loads(_gdf.to_json())


# --- Construcció del nom de variable: Tipus + Regadiu/Secà (només IRTA) ---
TIPUS_CODIS = {"Superfície": "ha", "Producció": "t", "Rendiment": "t/ha"}


def nom_variable(tipus_codi, reg_sec):
    if tipus_codi == "ha":
        return f"HA_IRTA_{reg_sec}"
    elif tipus_codi == "t":
        return f"PROD_IRTA(t)_{reg_sec}"
    else:  # "t/ha"
        return f"PROD_IRTA(t/ha)_{reg_sec}"


GRUPS_VARIABLES = {
    "HA_R": ["HA_IRTA_R"], "HA_S": ["HA_IRTA_S"],
    "PROD(t)_R": ["PROD_IRTA(t)_R"], "PROD(t)_S": ["PROD_IRTA(t)_S"],
    "PROD(t/ha)_R": ["PROD_IRTA(t/ha)_R"], "PROD(t/ha)_S": ["PROD_IRTA(t/ha)_S"],
}
VARIABLE_A_GRUP = {v: grup for grup, cols in GRUPS_VARIABLES.items() for v in cols}
UNITATS = {
    "ha": ["HA_IRTA_R", "HA_IRTA_S"],
    "t": ["PROD_IRTA(t)_R", "PROD_IRTA(t)_S"],
    "t/ha": ["PROD_IRTA(t/ha)_R", "PROD_IRTA(t/ha)_S"],
}
VARIABLE_A_UNITAT = {v: unitat for unitat, cols in UNITATS.items() for v in cols}


@st.cache_data
def calcula_rangs_fixos(df, percentil_baix=5, percentil_alt=95):
    rangs = {}
    for cultiu, df_c in df.groupby("CULTIU"):
        for grup, cols in GRUPS_VARIABLES.items():
            valors = df_c[cols].to_numpy().flatten()
            valors = valors[~pd.isna(valors)]
            if len(valors) > 0:
                baix, alt = np.percentile(valors, [percentil_baix, percentil_alt])
                rangs[(cultiu, grup)] = (float(baix), float(alt))
    return rangs


@st.cache_data
def rasteritza(campanya, cultiu, variable, mida_px=900):
    """Dibuixa els municipis (colorejats segons el seu valor REAL, escala
    Viridis, sense barrejar-los amb els veïns) en una imatge RGBA amb fons
    transparent. És la part cara (recórrer ~950 polígons), per això es
    cacheja a part del difuminat."""
    df_sel = df_muni[(df_muni["CAMPANYA"] == campanya) & (df_muni["CULTIU"] == cultiu)]
    df_sel = df_sel.groupby(["ID_MUN", "MUNICIPI"], as_index=False)[variable].sum(min_count=1)
    df_map = gdf_mun.merge(df_sel, on="ID_MUN", how="left")
    # Si algun municipi no té dada per aquesta selecció, MUNICIPI queda buit
    # després del merge; ho omplim amb el nom de la geometria (NOMMUNI).
    df_map["MUNICIPI"] = df_map["MUNICIPI"].fillna(df_map["NOMMUNI"])

    grup = VARIABLE_A_GRUP.get(variable)
    zmin, zmax = rangs_fixos.get((cultiu, grup), (0.0, 1.0))

    minx, miny, maxx, maxy = gdf_mun.total_bounds
    lat_mitjana = (miny + maxy) / 2
    factor_aspecte = np.cos(np.radians(lat_mitjana))
    amplada_geo = (maxx - minx) * factor_aspecte
    alcada_geo = maxy - miny
    if amplada_geo >= alcada_geo:
        ample_px, alt_px = mida_px, max(1, int(mida_px * alcada_geo / amplada_geo))
    else:
        alt_px, ample_px = mida_px, max(1, int(mida_px * amplada_geo / alcada_geo))

    img = Image.new("RGBA", (ample_px, alt_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def geo_a_px(x, y):
        px = (x - minx) / (maxx - minx) * ample_px
        py = (maxy - y) / (maxy - miny) * alt_px
        return (px, py)

    n_sense_dada = 0
    for _, fila in df_map.iterrows():
        valor = fila[variable]
        if pd.isna(valor):
            n_sense_dada += 1
            continue
        norm = 0.0 if zmax == zmin else max(0.0, min(1.0, (valor - zmin) / (zmax - zmin)))
        color_str = pcolors.sample_colorscale("Viridis", norm)[0]
        r, g, b = [int(v) for v in color_str.strip("rgb()").split(",")]
        geom = fila.geometry
        if geom is None:
            continue
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            coords_px = [geo_a_px(x, y) for x, y in poly.exterior.coords]
            draw.polygon(coords_px, fill=(r, g, b, 255))

    coords_geo = [[minx, maxy], [maxx, maxy], [maxx, miny], [minx, miny]]
    return img, coords_geo, df_map, n_sense_dada, zmin, zmax


def img_a_data_uri(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


df_muni = load_data()
gdf_mun = load_geometria()
geojson = geometria_a_geojson(gdf_mun)
rangs_fixos = calcula_rangs_fixos(df_muni)

minx, miny, maxx, maxy = gdf_mun.total_bounds
centre = {"lat": (miny + maxy) / 2, "lon": (minx + maxx) / 2}

st.title("🧪 Mapa difuminat de municipis (prova)")
st.caption(
    "Cada municipi conserva el seu color real (com al mapa de polígons), però "
    "es rasteritza a imatge i s'hi aplica un difuminat gaussià per suavitzar "
    "les vores — a diferència d'un mapa de densitat, els valors NO es "
    "barregen amb els municipis veïns."
)

col1, col2 = st.columns(2)
with col1:
    tots_cultius = sorted(df_muni["CULTIU"].dropna().unique())
    default_cultiu = "BLAT" if "BLAT" in tots_cultius else tots_cultius[0]
    cultiu_sel = st.segmented_control("Cultiu", options=tots_cultius, default=default_cultiu)
    if cultiu_sel is None:
        cultiu_sel = default_cultiu
with col2:
    totes_campanyes = sorted(df_muni["CAMPANYA"].dropna().unique(), reverse=True)
    campanya_sel = st.slider(
        "Campanya",
        min_value=int(min(totes_campanyes)),
        max_value=int(max(totes_campanyes)),
        value=int(max(totes_campanyes)),
        step=1,
    )

col3, col4 = st.columns(2)
with col3:
    tipus_label = st.segmented_control(
        "Tipus de variable", options=list(TIPUS_CODIS.keys()), default="Rendiment"
    )
    if tipus_label is None:
        tipus_label = "Rendiment"
with col4:
    reg_sec = st.segmented_control("Regadiu / Secà", options=["R", "S"], default="R")
    if reg_sec is None:
        reg_sec = "R"

variable_sel = nom_variable(TIPUS_CODIS[tipus_label], reg_sec)
st.caption(f"→ `{variable_sel}`")

blur = st.slider(
    "Desenfocament (px)",
    min_value=0,
    max_value=25,
    value=8,
    step=1,
    help="Com més gran, més se suavitzen les vores i menys es distingeix el límit exacte de cada municipi.",
)

# Rasterització (cara, cachejada) + desenfocament (barat, es recalcula lliurement)
img_base, coords_geo, df_map, n_sense_dada, zmin, zmax = rasteritza(
    campanya_sel, cultiu_sel, variable_sel
)
img_final = img_base.filter(ImageFilter.GaussianBlur(radius=blur)) if blur > 0 else img_base
data_uri = img_a_data_uri(img_final)

fig = go.Figure()

# Traça transparent NOMÉS per al popup (hover), amb els valors reals —
# el que es VEU és la imatge difuminada, però el hover segueix sent precís.
df_amb_dada = df_map[df_map[variable_sel].notna()]
fig.add_trace(
    go.Choroplethmap(
        geojson=geojson,
        locations=df_amb_dada["ID_MUN"],
        z=df_amb_dada[variable_sel],
        featureidkey="properties.ID_MUN",
        customdata=df_amb_dada[["MUNICIPI", variable_sel]],
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
        showscale=False,
        marker_line_width=0,
        hovertemplate=(
            '<b><span style="font-size:13px">%{customdata[0]}</span></b>'
            "<br>Valor: %{customdata[1]:,.2f}<extra></extra>"
        ),
        hoverlabel=dict(
            bgcolor="white", bordercolor="#dddddd",
            font=dict(size=12, family="Arial, sans-serif", color="#222222"),
        ),
    )
)

fig.update_layout(
    map_style="carto-positron",
    map_zoom=7.1,
    map_center=centre,
    map_layers=[
        dict(
            sourcetype="image",
            source=data_uri,
            coordinates=coords_geo,
            opacity=0.9,
        )
    ],
    margin=dict(l=0, r=0, t=20, b=0),
    height=650,
    separators=",.",
)

st.plotly_chart(
    fig,
    width="stretch",
    config={
        "displayModeBar": True,
        "modeBarButtonsToAdd": ["zoomInMap", "zoomOutMap", "resetViewMap"],
    },
)

st.caption(f"Escala de color: {zmin:,.2f} – {zmax:,.2f} ({VARIABLE_A_UNITAT.get(variable_sel, '')})")

if n_sense_dada:
    st.caption(f"⚠️ {n_sense_dada} municipi(s) sense dada per aquesta selecció (queden transparents).")