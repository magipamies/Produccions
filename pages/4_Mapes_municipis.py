# -*- coding: utf-8 -*-
"""

author: magipamies
datetime:19/8/2026 13:32
"""
import json

import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import plotly.graph_objects as go

st.set_page_config(page_title="Mapa per municipis", layout="wide")


@st.cache_data
def load_data():
    df = pd.read_csv("data_flourish_muni_histo26_rs.csv")
    # Assegurem tipus consistent per poder unir amb la geometria
    df["ID_MUN"] = df["ID_MUN"].astype("int64")
    return df


@st.cache_data
def load_geometria(tolerance=0.0008):
    # gdf_mun: CODIMUNI, NOMMUNI, CAPMUNI, NOMCOMAR, NOMVEGUE, NOMPROV, ID_MUN, geometry
    gdf = gpd.read_file("muni_cat.geojson")
    gdf["ID_MUN"] = gdf["ID_MUN"].astype("int64")
    # Plotly necessita coordenades en WGS84 (lat/lon, EPSG:4326)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    # Amb ~950 municipis, la simplificació és encara més important que amb
    # comarques perquè el mapa vagi fluid. Ajusta el tolerance si cal.
    gdf["geometry"] = gdf["geometry"].simplify(tolerance, preserve_topology=True)
    return gdf


@st.cache_data
def load_geometria_comarques(tolerance=0.001):
    """Només per dibuixar-hi el contorn a sobre del mapa de municipis (no
    per unir-hi dades) — per això no cal ID_MUN ni res més que la geometria."""
    gdf = gpd.read_file("comarques_cat.geojson")
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


# Grups de variables que comparteixen unitat -> comparteixen rang de color.
# Només IRTA (a diferència del mapa de comarques), així que cada grup té
# una única columna.
GRUPS_VARIABLES = {
    "HA_R": ["HA_IRTA_R"],
    "HA_S": ["HA_IRTA_S"],
    "PROD(t)_R": ["PROD_IRTA(t)_R"],
    "PROD(t)_S": ["PROD_IRTA(t)_S"],
    "PROD(t/ha)_R": ["PROD_IRTA(t/ha)_R"],
    "PROD(t/ha)_S": ["PROD_IRTA(t/ha)_S"],
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
    """Rang de color (percentil baix/alt) per CULTIU + grup de variable, agafant
    TOTES les campanyes, perquè el rang no canviï en moure el slider d'any."""
    rangs = {}
    for cultiu, df_c in df.groupby("CULTIU"):
        for grup, cols in GRUPS_VARIABLES.items():
            cols_presents = [c for c in cols if c in df_c.columns]
            valors = df_c[cols_presents].to_numpy().flatten()
            valors = valors[~pd.isna(valors)]
            if len(valors) > 0:
                baix, alt = np.percentile(valors, [percentil_baix, percentil_alt])
                rangs[(cultiu, grup)] = (float(baix), float(alt))
    return rangs


df_muni = load_data()
gdf_mun = load_geometria()
geojson = geometria_a_geojson(gdf_mun)
rangs_fixos = calcula_rangs_fixos(df_muni)

gdf_com = load_geometria_comarques()
geojson_comarques = geometria_a_geojson(gdf_com)

# Centre del mapa calculat automàticament a partir de la geometria
minx, miny, maxx, maxy = gdf_mun.total_bounds
centre = {"lat": (miny + maxy) / 2, "lon": (minx + maxx) / 2}

# Colors molt subtils per distingir regadiu (blau) de secà (vermell) al popup
COLOR_R = "#5B84B1"
COLOR_S = "#B1615B"


def build_hover_extra(variables_disponibles):
    """Cos del popup (sense la capçalera de municipi ni <extra></extra>): un
    bloc per Superfície/Producció (sense decimals) i Rendiment (amb 2
    decimals), amb Regadiu (R) en blau subtil i Secà (S) en vermell subtil.
    Com que només hi ha IRTA, cada fila té un únic valor (no cal desglossar
    per font com al mapa de comarques). customdata[0] és el nom del
    municipi, per això els índexs de variable es desplacen +1."""
    idx = {v: i + 1 for i, v in enumerate(variables_disponibles)}

    def valor(tipus_codi, reg_sec, format_spec):
        i = idx.get(nom_variable(tipus_codi, reg_sec))
        return f"%{{customdata[{i}]:{format_spec}}}" if i is not None else "–"

    blocs = []
    for tipus_codi, etiqueta, unitat, format_spec in [
        ("ha", "Superfície", "ha", ",.2f"),
        ("t", "Producció", "t", ",.2f"),
        ("t/ha", "Rendiment", "t/ha", ",.2f"),
    ]:
        linia_r = f'<span style="color:{COLOR_R}">R</span> {valor(tipus_codi, "R", format_spec)}'
        linia_s = f'<span style="color:{COLOR_S}">S</span> {valor(tipus_codi, "S", format_spec)}'
        blocs.append(f"<b>{etiqueta} ({unitat})</b><br>{linia_r}<br>{linia_s}")

    return "<br><br>".join(blocs)


def build_hovertemplate(variables_disponibles):
    # %{location} seria l'ID_MUN (un número), per això fem servir
    # customdata[0] (MUNICIPI) com a capçalera llegible.
    return (
        '<b><span style="font-size:13px">%{customdata[0]}</span></b><br><br>'
        + build_hover_extra(variables_disponibles)
        + "<extra></extra>"
    )


HOVER_SENSE_DADA = (
    '<b><span style="font-size:13px">%{customdata[0]}</span></b>'
    "<br><i>Sense dades</i><extra></extra>"
)

HOVERLABEL = {
    "bgcolor": "white",
    "bordercolor": "#dddddd",
    "font": {"size": 12, "family": "Arial, sans-serif", "color": "#222222"},
}


def panell_variable(key_prefix, tipus_default="Rendiment", reg_sec_default="R"):
    """Panell plegable: Tipus (Superfície/Producció/Rendiment) + Reg./Secà,
    en una sola línia. No hi ha selector de Font: aquí només hi ha IRTA.
    Retorna el nom real de la columna resultant, p.ex. 'PROD_IRTA(t/ha)_R'."""
    with st.expander("🔧 Variable", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            tipus_label = st.segmented_control(
                "Tipus de variable",
                options=list(TIPUS_CODIS.keys()),
                default=tipus_default,
                key=f"tipus_{key_prefix}_muni",
            )
        with c2:
            reg_sec = st.segmented_control(
                "Regadiu / Secà",
                options=["R", "S"],
                default=reg_sec_default,
                key=f"regsec_{key_prefix}_muni",
            )

        if tipus_label is None:
            tipus_label = tipus_default
        if reg_sec is None:
            reg_sec = reg_sec_default

        variable = nom_variable(TIPUS_CODIS[tipus_label], reg_sec)
        st.caption(f"→ `{variable}`")
    return variable


def slider_campanya(key_prefix, totes_campanyes):
    minim, maxim = int(min(totes_campanyes)), int(max(totes_campanyes))
    return st.slider(
        "Campanya",
        min_value=minim,
        max_value=maxim,
        value=maxim,
        step=1,
        key=f"campanya_{key_prefix}_muni",
    )


def selector_cultiu(key_prefix, tots_cultius):
    default = "BLAT" if "BLAT" in tots_cultius else tots_cultius[0]
    valor = st.segmented_control(
        "Cultiu", options=tots_cultius, default=default, key=f"cultiu_{key_prefix}_muni"
    )
    return valor if valor is not None else default


st.title("Mapa de municipis")

variables_disponibles = [
    c for c in df_muni.columns if c not in ["COMARCA", "ID_MUN", "MUNICIPI", "CULTIU", "CAMPANYA"]
]
totes_campanyes = sorted(df_muni["CAMPANYA"].dropna().unique(), reverse=True)
tots_cultius = sorted(df_muni["CULTIU"].dropna().unique())


def construeix_df_map(campanya, cultiu):
    df_sel = df_muni[(df_muni["CAMPANYA"] == campanya) & (df_muni["CULTIU"] == cultiu)]
    df_sel = df_sel.groupby(["ID_MUN", "MUNICIPI"], as_index=False)[variables_disponibles].sum(
        min_count=1
    )
    df_map = gdf_mun.merge(df_sel, on="ID_MUN", how="left")
    # Si un municipi no té cap fila de dades per aquesta selecció, MUNICIPI
    # queda buit després del merge; ho omplim amb el nom de la geometria
    # (NOMMUNI) perquè el popup sempre mostri algun nom.
    df_map["MUNICIPI"] = df_map["MUNICIPI"].fillna(df_map["NOMMUNI"])
    return df_map


def dibuixa_mapa(df_map, variable, cultiu_sel, titol=None):
    """Construeix la figura (2 capes: amb dada + blanc) per a una variable
    concreta. Reutilitzada pel mode senzill i pel mode comparació."""
    df_amb_dada = df_map[df_map[variable].notna()]
    df_sense_dada = df_map[df_map[variable].isna()]

    fig = go.Figure()

    if not df_amb_dada.empty:
        grup_sel = VARIABLE_A_GRUP.get(variable)
        zmin, zmax = rangs_fixos.get((cultiu_sel, grup_sel), (None, None))
        fig.add_trace(
            go.Choroplethmap(
                geojson=geojson,
                locations=df_amb_dada["ID_MUN"],
                z=df_amb_dada[variable],
                zmin=zmin,
                zmax=zmax,
                featureidkey="properties.ID_MUN",
                customdata=df_amb_dada[["MUNICIPI"] + variables_disponibles],
                colorscale="Viridis",
                marker_line_color="white",
                marker_line_width=0.4,
                colorbar_title=VARIABLE_A_UNITAT.get(variable, variable),
                hovertemplate=build_hovertemplate(variables_disponibles),
                hoverlabel=HOVERLABEL,
            )
        )

    if not df_sense_dada.empty:
        fig.add_trace(
            go.Choroplethmap(
                geojson=geojson,
                locations=df_sense_dada["ID_MUN"],
                z=[0] * len(df_sense_dada),
                featureidkey="properties.ID_MUN",
                customdata=df_sense_dada[["MUNICIPI"]],
                colorscale=[[0, "white"], [1, "white"]],
                showscale=False,
                marker_line_color="lightgrey",
                marker_line_width=0.4,
                hovertemplate=HOVER_SENSE_DADA,
                hoverlabel=HOVERLABEL,
            )
        )

    # Contorn de comarca: traça (no "layer" de layout) afegida DESPRÉS de les
    # anteriors, perquè quedi per sobre del polígons opacs dels municipis en
    # lloc d'amagar-se per sota. Fill transparent, només es veu la vora.
    fig.add_trace(
        go.Choroplethmap(
            geojson=geojson_comarques,
            locations=gdf_com["COMARCA"],
            z=[0] * len(gdf_com),
            featureidkey="properties.COMARCA",
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False,
            marker_line_color="#444444",
            marker_line_width=1.3,
            hoverinfo="skip",
        )
    )

    fig.update_layout(
        map_style="carto-positron",
        map_zoom=7.1,
        map_center=centre,
        margin=dict(l=0, r=0, t=30 if titol else 20, b=0),
        height=650,
        separators=",.",
        title=titol,
    )
    return fig, df_sense_dada


comparar = st.checkbox("Comparar dues variables costat a costat")

if not comparar:
    # --- Mode senzill: selectors compartits, un sol mapa ---
    col1, col2 = st.columns(2)
    with col1:
        cultiu_sel = selector_cultiu("unic", tots_cultius)
    with col2:
        campanya_sel = slider_campanya("unic", totes_campanyes)

    variable_sel = panell_variable("unic")

    df_map = construeix_df_map(campanya_sel, cultiu_sel)
    fig, df_sense_dada = dibuixa_mapa(df_map, variable_sel, cultiu_sel)

    st.plotly_chart(
        fig,
        width="stretch",
        config={
            "displayModeBar": True,
            "modeBarButtonsToAdd": ["zoomInMap", "zoomOutMap", "resetViewMap"],
        },
    )

    if not df_sense_dada.empty:
        with st.expander(f"⚠️ {len(df_sense_dada)} municipi(s) sense dada per aquesta selecció"):
            st.write(sorted(df_sense_dada["MUNICIPI"].tolist()))

else:
    # --- Mode comparació: cada banda amb la seva pròpia campanya/cultiu/variable ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Mapa esquerre**")
        sub1, sub2 = st.columns(2)
        with sub1:
            cultiu_esq = selector_cultiu("esq", tots_cultius)
        with sub2:
            campanya_esq = slider_campanya("esq", totes_campanyes)
        variable_esq = panell_variable("esq", tipus_default="Rendiment", reg_sec_default="R")

    with col_b:
        st.markdown("**Mapa dret**")
        sub3, sub4 = st.columns(2)
        with sub3:
            cultiu_dre = selector_cultiu("dre", tots_cultius)
        with sub4:
            campanya_dre = slider_campanya("dre", totes_campanyes)
        variable_dre = panell_variable("dre", tipus_default="Rendiment", reg_sec_default="S")

    df_map_esq = construeix_df_map(campanya_esq, cultiu_esq)
    df_map_dre = construeix_df_map(campanya_dre, cultiu_dre)

    fig_esq, df_sense_esq = dibuixa_mapa(
        df_map_esq, variable_esq, cultiu_esq, titol=f"{variable_esq} · {cultiu_esq} · {campanya_esq}"
    )
    fig_dre, df_sense_dre = dibuixa_mapa(
        df_map_dre, variable_dre, cultiu_dre, titol=f"{variable_dre} · {cultiu_dre} · {campanya_dre}"
    )

    config_mapa = {
        "displayModeBar": True,
        "modeBarButtonsToAdd": ["zoomInMap", "zoomOutMap", "resetViewMap"],
    }

    col_mapa_esq, col_mapa_dre = st.columns(2)
    with col_mapa_esq:
        st.plotly_chart(fig_esq, width="stretch", config=config_mapa, key="mapa_muni_comp_esq")
        if not df_sense_esq.empty:
            with st.expander(f"⚠️ {len(df_sense_esq)} municipi(s) sense dada"):
                st.write(sorted(df_sense_esq["MUNICIPI"].tolist()))

    with col_mapa_dre:
        st.plotly_chart(fig_dre, width="stretch", config=config_mapa, key="mapa_muni_comp_dre")
        if not df_sense_dre.empty:
            with st.expander(f"⚠️ {len(df_sense_dre)} municipi(s) sense dada"):
                st.write(sorted(df_sense_dre["MUNICIPI"].tolist()))