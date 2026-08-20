# -*- coding: utf-8 -*-
"""
Cada municipi conserva el seu color real (com al mapa de polígons), però es rasteritza a imatge i s'hi aplica un
difuminat gaussià per suavitzar les vores — a diferència d'un mapa de densitat, els valors NO es barregen amb els
municipis veïns.

Es pot modificar el nivell de difuminat amb:
BLUR_FIX = 2  # desenfocament fix, en px

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
def geometria_a_geojson(_gdf, clau=""):
    # 'clau' és necessària perquè la cache distingeixi aquesta crida d'altres
    # (per exemple, comarques vs municipis): _gdf, en portar '_', no compta
    # per la cache, i sense una clau diferent totes les crides compartirien
    # el mateix resultat cachejat.
    return json.loads(_gdf.to_json())


@st.cache_data
def load_geometria_comarques(tolerance=0.001):
    """Només per dibuixar-hi el contorn a sobre (no per unir-hi dades)."""
    gdf = gpd.read_file("comarques_cat.geojson")
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    gdf["geometry"] = gdf["geometry"].simplify(tolerance, preserve_topology=True)
    return gdf


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


BLUR_FIX = 2  # desenfocament fix, en px


def dibuixa_mapa(campanya, cultiu, variable, titol=None, mostra_comarques=False):
    """Rasteritza + difumina, i construeix la figura final. La traça de
    Plotly fa servir l'escala de color REAL (Viridis, zmin/zmax) perquè es
    vegi la colorbar, però amb el fill invisible (opacity=0): el que es veu
    és la imatge difuminada de sota; la traça només serveix pel popup i la
    colorbar."""
    img_base, coords_geo, df_map, n_sense_dada, zmin, zmax = rasteritza(campanya, cultiu, variable)
    img_final = img_base.filter(ImageFilter.GaussianBlur(radius=BLUR_FIX))
    data_uri = img_a_data_uri(img_final)

    df_amb_dada = df_map[df_map[variable].notna()]

    fig = go.Figure()
    fig.add_trace(
        go.Choroplethmap(
            geojson=geojson,
            locations=df_amb_dada["ID_MUN"],
            z=df_amb_dada[variable],
            zmin=zmin,
            zmax=zmax,
            featureidkey="properties.ID_MUN",
            colorscale="Viridis",
            showscale=True,
            colorbar_title=VARIABLE_A_UNITAT.get(variable, variable),
            marker=dict(opacity=0, line=dict(width=0)),  # fill invisible: es veu la imatge de sota
            hoverinfo="skip",  # sense popup per municipi
        )
    )

    capes = [dict(sourcetype="image", source=data_uri, coordinates=coords_geo, opacity=0.9)]
    if mostra_comarques:
        capes.append(
            dict(
                sourcetype="geojson",
                source=geojson_comarques,
                type="line",
                color="rgba(120,120,120,0.55)",
                line=dict(width=1.0),
            )
        )

    fig.update_layout(
        map_style="carto-positron",
        map_zoom=7.1,
        map_center=centre,
        map_layers=capes,
        margin=dict(l=0, r=0, t=30 if titol else 20, b=0),
        height=650,
        separators=",.",
        title=titol,
    )
    return fig, n_sense_dada


df_muni = load_data()
gdf_mun = load_geometria()
geojson = geometria_a_geojson(gdf_mun, clau="municipis")
rangs_fixos = calcula_rangs_fixos(df_muni)

gdf_com = load_geometria_comarques()
geojson_comarques = geometria_a_geojson(gdf_com, clau="comarques")

minx, miny, maxx, maxy = gdf_mun.total_bounds
centre = {"lat": (miny + maxy) / 2, "lon": (minx + maxx) / 2}

tots_cultius = sorted(df_muni["CULTIU"].dropna().unique())
default_cultiu = "BLAT" if "BLAT" in tots_cultius else tots_cultius[0]
totes_campanyes = sorted(df_muni["CAMPANYA"].dropna().unique(), reverse=True)

CONFIG_MAPA = {
    "displayModeBar": True,
    "modeBarButtonsToAdd": ["zoomInMap", "zoomOutMap", "resetViewMap"],
}

st.title("Mapa de municipis difuminat (prova)")
st.caption(
    "Variables de producció a nivell municipal"
)

comparar = st.checkbox("Comparar dues variables costat a costat")

if not comparar:
    col1, col2 = st.columns(2)
    with col1:
        cultiu_sel = st.segmented_control(
            "Cultiu", options=tots_cultius, default=default_cultiu, key="cultiu_dens"
        )
        if cultiu_sel is None:
            cultiu_sel = default_cultiu
    with col2:
        campanya_sel = st.slider(
            "Campanya",
            min_value=int(min(totes_campanyes)),
            max_value=int(max(totes_campanyes)),
            value=int(max(totes_campanyes)),
            step=1,
            key="campanya_dens",
        )

    col3, col4, col5 = st.columns([2, 1, 1.3])
    with col3:
        tipus_label = st.segmented_control(
            "Tipus de variable", options=list(TIPUS_CODIS.keys()), default="Rendiment", key="tipus_dens"
        )
        if tipus_label is None:
            tipus_label = "Rendiment"
    with col4:
        reg_sec = st.segmented_control(
            "Regadiu / Secà", options=["R", "S"], default="R", key="regsec_dens"
        )
        if reg_sec is None:
            reg_sec = "R"
    with col5:
        st.write("")  # petit espaiat per alinear amb els segmented_control
        mostra_comarques = st.checkbox("Mostra comarques", value=False, key="mostra_comarques_dens")

    variable_sel = nom_variable(TIPUS_CODIS[tipus_label], reg_sec)
    st.caption(f"→ `{variable_sel}`")

    fig, n_sense_dada = dibuixa_mapa(
        campanya_sel, cultiu_sel, variable_sel, mostra_comarques=mostra_comarques
    )
    st.plotly_chart(fig, width="stretch", config=CONFIG_MAPA, key="mapa_dens_unic")

    if n_sense_dada:
        st.caption(f"⚠️ {n_sense_dada} municipi(s) sense dada per aquesta selecció (queden transparents).")

else:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Mapa esquerre**")
        sub1, sub2 = st.columns(2)
        with sub1:
            cultiu_esq = st.segmented_control(
                "Cultiu", options=tots_cultius, default=default_cultiu, key="cultiu_esq_dens"
            )
            if cultiu_esq is None:
                cultiu_esq = default_cultiu
        with sub2:
            campanya_esq = st.slider(
                "Campanya",
                min_value=int(min(totes_campanyes)),
                max_value=int(max(totes_campanyes)),
                value=int(max(totes_campanyes)),
                step=1,
                key="campanya_esq_dens",
            )
        sub3, sub4, sub_c1 = st.columns([2, 1, 1.3])
        with sub3:
            tipus_esq = st.segmented_control(
                "Tipus de variable", options=list(TIPUS_CODIS.keys()), default="Rendiment", key="tipus_esq_dens"
            )
            if tipus_esq is None:
                tipus_esq = "Rendiment"
        with sub4:
            regsec_esq = st.segmented_control(
                "Regadiu / Secà", options=["R", "S"], default="R", key="regsec_esq_dens"
            )
            if regsec_esq is None:
                regsec_esq = "R"
        with sub_c1:
            st.write("")  # petit espaiat per alinear amb els segmented_control
            mostra_comarques_esq = st.checkbox("Mostra comarques", value=False, key="mostra_comarques_esq_dens")
        variable_esq = nom_variable(TIPUS_CODIS[tipus_esq], regsec_esq)
        st.caption(f"→ `{variable_esq}`")

    with col_b:
        st.markdown("**Mapa dret**")
        sub5, sub6 = st.columns(2)
        with sub5:
            cultiu_dre = st.segmented_control(
                "Cultiu", options=tots_cultius, default=default_cultiu, key="cultiu_dre_dens"
            )
            if cultiu_dre is None:
                cultiu_dre = default_cultiu
        with sub6:
            campanya_dre = st.slider(
                "Campanya",
                min_value=int(min(totes_campanyes)),
                max_value=int(max(totes_campanyes)),
                value=int(max(totes_campanyes)),
                step=1,
                key="campanya_dre_dens",
            )
        sub7, sub8, sub_c2 = st.columns([2, 1, 1.3])
        with sub7:
            tipus_dre = st.segmented_control(
                "Tipus de variable", options=list(TIPUS_CODIS.keys()), default="Rendiment", key="tipus_dre_dens"
            )
            if tipus_dre is None:
                tipus_dre = "Rendiment"
        with sub8:
            regsec_dre = st.segmented_control(
                "Regadiu / Secà", options=["R", "S"], default="S", key="regsec_dre_dens"
            )
            if regsec_dre is None:
                regsec_dre = "S"
        with sub_c2:
            st.write("")  # petit espaiat per alinear amb els segmented_control
            mostra_comarques_dre = st.checkbox("Mostra comarques", value=False, key="mostra_comarques_dre_dens")
        variable_dre = nom_variable(TIPUS_CODIS[tipus_dre], regsec_dre)
        st.caption(f"→ `{variable_dre}`")

    fig_esq, n_sense_esq = dibuixa_mapa(
        campanya_esq, cultiu_esq, variable_esq,
        titol=f"{variable_esq} · {cultiu_esq} · {campanya_esq}",
        mostra_comarques=mostra_comarques_esq,
    )
    fig_dre, n_sense_dre = dibuixa_mapa(
        campanya_dre, cultiu_dre, variable_dre,
        titol=f"{variable_dre} · {cultiu_dre} · {campanya_dre}",
        mostra_comarques=mostra_comarques_dre,
    )

    col_mapa_esq, col_mapa_dre = st.columns(2)
    with col_mapa_esq:
        st.plotly_chart(fig_esq, width="stretch", config=CONFIG_MAPA, key="mapa_dens_comp_esq")
        if n_sense_esq:
            st.caption(f"⚠️ {n_sense_esq} municipi(s) sense dada")
    with col_mapa_dre:
        st.plotly_chart(fig_dre, width="stretch", config=CONFIG_MAPA, key="mapa_dens_comp_dre")
        if n_sense_dre:
            st.caption(f"⚠️ {n_sense_dre} municipi(s) sense dada")