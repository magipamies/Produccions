# -*- coding: utf-8 -*-
"""

author: magipamies
datetime:17/8/2026 12:36
"""
import json

import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px

st.set_page_config(page_title="Mapa per comarques", layout="wide")


@st.cache_data
def load_data():
    return pd.read_csv("data_flourish_histo26_rs.csv")


@st.cache_data
def load_geometria():
    # Substitueix pel path real del teu geojson (gdf_c: id_comarca, COMARCA, geometry)
    gdf = gpd.read_file("comarques_cat.geojson")
    # Plotly necessita coordenades en WGS84 (lat/lon, EPSG:4326)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


df2 = load_data()
gdf_c = load_geometria()
geojson = json.loads(gdf_c.to_json())

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
        "Variable a mostrar al mapa",
        options=variables_disponibles,
        index=variables_disponibles.index(default_var)
        if default_var in variables_disponibles
        else 0,
    )

# --- Filtratge i unió amb la geometria ---
df_sel = df2[(df2["CAMPANYA"] == campanya_sel) & (df2["CULTIU"] == cultiu_sel)]

# Si per algun motiu hi ha diverses files per comarca, les sumem (NaN si totes ho són)
df_sel = df_sel.groupby("COMARCA", as_index=False)[variable_sel].sum(min_count=1)

df_map = gdf_c.merge(df_sel, on="COMARCA", how="left")

# Comarques de gdf_c sense dada corresponent a df2 (útil per detectar noms que no casen)
sense_dada = df_map[df_map[variable_sel].isna()]["COMARCA"].tolist()

fig = px.choropleth(
    df_map,
    geojson=geojson,
    locations="COMARCA",
    featureidkey="properties.COMARCA",
    color=variable_sel,
    color_continuous_scale="YlOrRd",
)
fig.update_traces(
    hovertemplate="<b>%{location}</b><br>" + variable_sel + ": %{z:.2f}<extra></extra>"
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=650)

st.plotly_chart(fig, use_container_width=True)

if sense_dada:
    with st.expander(f"⚠️ {len(sense_dada)} comarca(es) sense dada per aquesta selecció"):
        st.write(sense_dada)