# -*- coding: utf-8 -*-
"""

author: magipamies
datetime:17/8/2026 12:36
"""
import json

import streamlit as st
import streamlit.components.v1 as components
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


# Grups de variables que comparteixen unitat -> comparteixen rang de color
GRUPS_VARIABLES = {
    "HA_R": ["HA_IRTA_R", "HA_DARPA_R"],
    "HA_S": ["HA_IRTA_S", "HA_DARPA_S"],
    "PROD(t)_R": ["PROD_IRTA(t)_R", "PROD_DARPA(t)_R"],
    "PROD(t)_S": ["PROD_IRTA(t)_S", "PROD_DARPA(t)_S"],
    "PROD(t/ha)_R": ["PROD_IRTA(t/ha)_R", "PROD_DARPA(t/ha)_R"],
    "PROD(t/ha)_S": ["PROD_IRTA(t/ha)_S", "PROD_DARPA(t/ha)_S"],
}
VARIABLE_A_GRUP = {v: grup for grup, cols in GRUPS_VARIABLES.items() for v in cols}

# Unitat de mesura de cada variable, per mostrar-la com a títol de la barra de colors
# en lloc del nom sencer de la variable
UNITATS = {
    "ha": ["HA_IRTA_R", "HA_IRTA_S", "HA_DARPA_R", "HA_DARPA_S"],
    "t": ["PROD_IRTA(t)_R", "PROD_IRTA(t)_S", "PROD_DARPA(t)_R", "PROD_DARPA(t)_S"],
    "t/ha": [
        "PROD_IRTA(t/ha)_R",
        "PROD_IRTA(t/ha)_S",
        "PROD_DARPA(t/ha)_R",
        "PROD_DARPA(t/ha)_S",
    ],
}
VARIABLE_A_UNITAT = {v: unitat for unitat, cols in UNITATS.items() for v in cols}


@st.cache_data
def calcula_rangs_fixos(df):
    """Min/max per CULTIU + grup de variable, agafant TOTES les campanyes.
    Així el rang de color no canvia en canviar d'any i es poden comparar."""
    rangs = {}
    for cultiu, df_c in df.groupby("CULTIU"):
        for grup, cols in GRUPS_VARIABLES.items():
            cols_presents = [c for c in cols if c in df_c.columns]
            valors = df_c[cols_presents].to_numpy().flatten()
            valors = valors[~pd.isna(valors)]
            if len(valors) > 0:
                rangs[(cultiu, grup)] = (float(valors.min()), float(valors.max()))
    return rangs


df2 = load_data()
gdf_c = load_geometria()
geojson = geometria_a_geojson(gdf_c)
rangs_fixos = calcula_rangs_fixos(df2)

# Centre del mapa calculat automàticament a partir de la geometria
minx, miny, maxx, maxy = gdf_c.total_bounds
centre = {"lat": (miny + maxy) / 2, "lon": (minx + maxx) / 2}


def traces_js_per_variable(df_map, variable, variables_disponibles, cultiu_sel, rangs_fixos):
    """Retorna (com a text JS) les 2 traces choroplethmapbox (amb dada + blanc)
    per a una variable concreta. 'geojson' es referencia com a variable JS
    compartida (no es duplica dins de cada trace)."""
    df_amb = df_map[df_map[variable].notna()]
    df_sense = df_map[df_map[variable].isna()]

    linies_hover = "<br>".join(
        f"{var}: %{{customdata[{i}]:.2f}}" for i, var in enumerate(variables_disponibles)
    )

    grup = VARIABLE_A_GRUP.get(variable)
    zmin, zmax = rangs_fixos.get((cultiu_sel, grup), (None, None))

    trace_amb = {
        "type": "choroplethmapbox",
        "locations": df_amb["COMARCA"].tolist(),
        "z": df_amb[variable].tolist(),
        "zmin": zmin,
        "zmax": zmax,
        "featureidkey": "properties.COMARCA",
        "customdata": df_amb[variables_disponibles].values.tolist(),
        "colorscale": "YlOrRd",
        "marker": {"line": {"color": "white", "width": 0.8}},
        "colorbar": {"title": {"text": VARIABLE_A_UNITAT.get(variable, variable)}},
        "hovertemplate": "<b>%{location}</b><br>" + linies_hover + "<extra></extra>",
    }
    trace_sense = {
        "type": "choroplethmapbox",
        "locations": df_sense["COMARCA"].tolist(),
        "z": [0] * len(df_sense),
        "featureidkey": "properties.COMARCA",
        "colorscale": [[0, "white"], [1, "white"]],
        "showscale": False,
        "marker": {"line": {"color": "lightgrey", "width": 0.8}},
        "hovertemplate": "<b>%{location}</b><br>Sense dades<extra></extra>",
    }

    # geojson s'insereix com a referència a la variable JS "geojson", no com a JSON literal
    js_amb = json.dumps(trace_amb)[:-1] + ', "geojson": geojson}'
    js_sense = json.dumps(trace_sense)[:-1] + ', "geojson": geojson}'
    return f"[{js_amb}, {js_sense}]"

st.title("Mapa de comarques")

variables_disponibles = [
    c for c in df2.columns if c not in ["COMARCA", "CULTIU", "CAMPANYA"]
]
default_var = "PROD_IRTA(t/ha)_R"
totes_comarques = sorted(df2["COMARCA"].dropna().unique())
totes_campanyes = sorted(df2["CAMPANYA"].dropna().unique(), reverse=True)
tots_cultius = sorted(df2["CULTIU"].dropna().unique())


def construeix_df_map(campanya, cultiu, comarques_sel):
    df_sel = df2[(df2["CAMPANYA"] == campanya) & (df2["CULTIU"] == cultiu)]
    df_sel = df_sel.groupby("COMARCA", as_index=False)[variables_disponibles].sum(min_count=1)
    gdf_subset = gdf_c[gdf_c["COMARCA"].isin(comarques_sel)]
    return gdf_subset.merge(df_sel, on="COMARCA", how="left")


comparar = st.checkbox("Comparar dues variables costat a costat")

if not comparar:
    # --- Mode senzill: selectors compartits, un sol mapa (com fins ara) ---
    col1, col2, col3 = st.columns(3)
    with col1:
        campanya_sel = st.selectbox("Campanya", options=totes_campanyes)
    with col2:
        cultiu_sel = st.selectbox("Cultiu", options=tots_cultius)
    with col3:
        variable_sel = st.selectbox(
            "Variable pel color del mapa",
            options=variables_disponibles,
            index=variables_disponibles.index(default_var)
            if default_var in variables_disponibles
            else 0,
        )

    df_map = construeix_df_map(campanya_sel, cultiu_sel, totes_comarques)
    df_amb_dada = df_map[df_map[variable_sel].notna()]
    df_sense_dada = df_map[df_map[variable_sel].isna()]

    linies_hover = "<br>".join(
        f"{var}: %{{customdata[{i}]:.2f}}" for i, var in enumerate(variables_disponibles)
    )

    fig = go.Figure()

    if not df_amb_dada.empty:
        grup_sel = VARIABLE_A_GRUP.get(variable_sel)
        zmin, zmax = rangs_fixos.get((cultiu_sel, grup_sel), (None, None))
        fig.add_trace(
            go.Choroplethmapbox(
                geojson=geojson,
                locations=df_amb_dada["COMARCA"],
                z=df_amb_dada[variable_sel],
                zmin=zmin,
                zmax=zmax,
                featureidkey="properties.COMARCA",
                customdata=df_amb_dada[variables_disponibles],
                colorscale="YlOrRd",
                marker_line_color="white",
                marker_line_width=0.8,
                colorbar_title=VARIABLE_A_UNITAT.get(variable_sel, variable_sel),
                hovertemplate="<b>%{location}</b><br>" + linies_hover + "<extra></extra>",
            )
        )

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
        mapbox_style="carto-positron",
        mapbox_zoom=7.1,
        mapbox_center=centre,
        margin=dict(l=0, r=0, t=20, b=0),
        height=650,
    )

    st.plotly_chart(fig, use_container_width=True)

    if not df_sense_dada.empty:
        with st.expander(f"⚠️ {len(df_sense_dada)} comarca(es) sense dada per aquesta selecció"):
            st.write(df_sense_dada["COMARCA"].tolist())

else:
    # --- Mode comparació: cada banda amb la seva pròpia campanya/cultiu/comarques/variable ---
    default_esq = default_var if default_var in variables_disponibles else variables_disponibles[0]
    default_dre = (
        "PROD_IRTA(t/ha)_S" if "PROD_IRTA(t/ha)_S" in variables_disponibles else variables_disponibles[-1]
    )

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Mapa esquerre**")
        campanya_esq = st.selectbox("Campanya", options=totes_campanyes, key="campanya_esq")
        cultiu_esq = st.selectbox("Cultiu", options=tots_cultius, key="cultiu_esq")
        variable_esq = st.selectbox(
            "Variable",
            options=variables_disponibles,
            index=variables_disponibles.index(default_esq),
            key="variable_esq",
        )

    with col_b:
        st.markdown("**Mapa dret**")
        campanya_dre = st.selectbox("Campanya", options=totes_campanyes, key="campanya_dre")
        cultiu_dre = st.selectbox("Cultiu", options=tots_cultius, key="cultiu_dre")
        variable_dre = st.selectbox(
            "Variable",
            options=variables_disponibles,
            index=variables_disponibles.index(default_dre),
            key="variable_dre",
        )

    df_map_esq = construeix_df_map(campanya_esq, cultiu_esq, totes_comarques)
    df_map_dre = construeix_df_map(campanya_dre, cultiu_dre, totes_comarques)

    traces_esq = traces_js_per_variable(
        df_map_esq, variable_esq, variables_disponibles, cultiu_esq, rangs_fixos
    )
    traces_dre = traces_js_per_variable(
        df_map_dre, variable_dre, variables_disponibles, cultiu_dre, rangs_fixos
    )

    layout_comu = {
        "mapbox": {"style": "carto-positron", "zoom": 7.1, "center": centre},
        "margin": {"l": 0, "r": 0, "t": 30, "b": 0},
        "height": 650,
    }
    layout_esq = json.dumps(
        {**layout_comu, "title": {"text": f"{variable_esq} · {cultiu_esq} · {campanya_esq}"}}
    )
    layout_dre = json.dumps(
        {**layout_comu, "title": {"text": f"{variable_dre} · {cultiu_dre} · {campanya_dre}"}}
    )

    html = f"""
    <div style="display:flex; gap:8px;">
      <div id="mapa_esq" style="width:50%; height:680px;"></div>
      <div id="mapa_dre" style="width:50%; height:680px;"></div>
    </div>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <script>
      const geojson = {json.dumps(geojson)};

      Plotly.newPlot('mapa_esq', {traces_esq}, {layout_esq}, {{displayModeBar: true, responsive: true}});
      Plotly.newPlot('mapa_dre', {traces_dre}, {layout_dre}, {{displayModeBar: true, responsive: true}});
    </script>
    """
    components.html(html, height=700, scrolling=False)