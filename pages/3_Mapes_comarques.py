# -*- coding: utf-8 -*-
"""

author: magipamies
datetime:17/8/2026 12:36
"""
import json

import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

st.set_page_config(page_title="Mapa per comarques", layout="wide")


@st.cache_data
def load_data():
    return pd.read_csv("data_flourish_histo26_rs.csv")


@st.cache_data
def load_geometria(tolerance=0.001):
    # Substitueix pel path real del teu geojson (gdf_c: id_comarca, COMARCA, geometry)
    gdf = gpd.read_file("comarques_cat.geojson")
    # Plotly necessita coordenades en WGS84 (lat/lon, EPSG:4326)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    # Simplifiquem els polígons: molts menys vèrtexs -> molt més ràpid de pintar.
    # tolerance en graus (~0.001 ≈ 100m); si les formes es veuen massa "anguloses"
    # baixa el valor, si encara va lent, puja'l.
    gdf["geometry"] = gdf["geometry"].simplify(tolerance, preserve_topology=True)
    return gdf


@st.cache_data
def geometria_a_geojson(_gdf):
    # Aquesta conversió és la part cara: la cachegem a part perquè només
    # es recalculi si canvia la geometria (mai, un cop simplificada).
    return json.loads(_gdf.to_json())


df2 = load_data()
gdf_c = load_geometria()
geojson = geometria_a_geojson(gdf_c)

# Centre del mapa calculat automàticament a partir de la geometria
minx, miny, maxx, maxy = gdf_c.total_bounds
centre = {"lat": (miny + maxy) / 2, "lon": (minx + maxx) / 2}

st.title("Mapa de comarques")

# --- Selectors ---
col1, col2, col3 = st.columns(3)

with col1:
    campanya_sel = st.selectbox(
        "Campanya",
        options=sorted(df2["CAMPANYA"].dropna().unique(), reverse=True),
    )

with col2:
    cultiu_sel = st.selectbox(
        "Cultiu",
        options=sorted(df2["CULTIU"].dropna().unique()),
    )

variables_disponibles = [
    c for c in df2.columns if c not in ["COMARCA", "CULTIU", "CAMPANYA"]
]
default_var = "PROD_IRTA(t/ha)_R"
with col3:
    variable_sel = st.selectbox(
        "Variable pel color del mapa",
        options=variables_disponibles,
        index=variables_disponibles.index(default_var)
        if default_var in variables_disponibles
        else 0,
    )

# --- Filtratge i unió amb la geometria ---
df_sel = df2[(df2["CAMPANYA"] == campanya_sel) & (df2["CULTIU"] == cultiu_sel)]

# Si per algun motiu hi ha diverses files per comarca, les sumem (NaN si totes ho són)
df_sel = df_sel.groupby("COMARCA", as_index=False)[variables_disponibles].sum(min_count=1)

# Left join: totes les comarques de gdf_c es mantenen, tinguin dada o no
df_map = gdf_c.merge(df_sel, on="COMARCA", how="left")

df_amb_dada = df_map[df_map[variable_sel].notna()]
df_sense_dada = df_map[df_map[variable_sel].isna()]

# Hovertemplate amb TOTES les variables, no només la seleccionada pel color
linies_hover = "<br>".join(
    f"{var}: %{{customdata[{i}]:.2f}}" for i, var in enumerate(variables_disponibles)
)

fig = go.Figure()

# --- Capa 1: comarques amb dada (color segons variable_sel) ---
if not df_amb_dada.empty:
    fig.add_trace(
        go.Choroplethmapbox(
            geojson=geojson,
            locations=df_amb_dada["COMARCA"],
            z=df_amb_dada[variable_sel],
            featureidkey="properties.COMARCA",
            customdata=df_amb_dada[variables_disponibles],
            colorscale="YlOrRd",
            marker_line_color="white",
            marker_line_width=0.8,
            colorbar_title=variable_sel,
            hovertemplate="<b>%{location}</b><br>" + linies_hover + "<extra></extra>",
        )
    )

# --- Capa 2: comarques sense dada, en blanc ---
if not df_sense_dada.empty:
    fig.add_trace(
        go.Choroplethmapbox(
            geojson=geojson,
            locations=df_sense_dada["COMARCA"],
            z=[0] * len(df_sense_dada),
            featureidkey="properties.COMARCA",
            colorscale=[[0, "white"], [1, "white"]],
            showscale=False,
            marker_line_color="lightgrey",
            marker_line_width=0.8,
            hovertemplate="<b>%{location}</b><br>Sense dades<extra></extra>",
        )
    )

fig.update_layout(
    mapbox_style="carto-positron",  # base senzilla i lleugera, sense token
    mapbox_zoom=6.3,
    mapbox_center=centre,
    margin=dict(l=0, r=0, t=20, b=0),
    height=650,
)

st.plotly_chart(fig, use_container_width=True)

if not df_sense_dada.empty:
    with st.expander(f"⚠️ {len(df_sense_dada)} comarca(es) sense dada per aquesta selecció"):
        st.write(df_sense_dada["COMARCA"].tolist())