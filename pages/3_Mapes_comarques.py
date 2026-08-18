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


# --- Construcció del nom de variable a partir de 3 tries ---
TIPUS_CODIS = {"Superfície": "ha", "Producció": "t", "Rendiment": "t/ha"}


def nom_variable(tipus_codi, empresa, reg_sec):
    if tipus_codi == "ha":
        return f"HA_{empresa}_{reg_sec}"
    elif tipus_codi == "t":
        return f"PROD_{empresa}(t)_{reg_sec}"
    else:  # "t/ha"
        return f"PROD_{empresa}(t/ha)_{reg_sec}"


# Colors molt subtils per distingir regadiu (blau) de secà (vermell) al popup
COLOR_R = "#5B84B1"
COLOR_S = "#B1615B"


def build_hover_extra(variables_disponibles):
    """Cos del popup (sense la capçalera de comarca ni <extra></extra>): un bloc
    per Superfície/Producció (sense decimals) i Rendiment (amb 2 decimals),
    amb el regadiu (R) en blau subtil i el secà (S) en vermell subtil."""
    idx = {v: i for i, v in enumerate(variables_disponibles)}

    def valor(tipus_codi, empresa, reg_sec, format_spec):
        i = idx.get(nom_variable(tipus_codi, empresa, reg_sec))
        return f"%{{customdata[{i}]:{format_spec}}}" if i is not None else "–"

    blocs = []
    for tipus_codi, etiqueta, unitat, format_spec in [
        ("ha", "Superfície", "ha", ",.0f"),
        ("t", "Producció", "t", ",.0f"),
        ("t/ha", "Rendiment", "t/ha", ",.2f"),
    ]:
        linia_r = (
            f'<span style="color:{COLOR_R}">R</span> IRTA {valor(tipus_codi, "IRTA", "R", format_spec)}'
            f' · DARPA {valor(tipus_codi, "DARPA", "R", format_spec)}'
        )
        linia_s = (
            f'<span style="color:{COLOR_S}">S</span> IRTA {valor(tipus_codi, "IRTA", "S", format_spec)}'
            f' · DARPA {valor(tipus_codi, "DARPA", "S", format_spec)}'
        )
        blocs.append(f"<b>{etiqueta} ({unitat})</b><br>{linia_r}<br>{linia_s}")

    return "<br><br>".join(blocs)


def build_hovertemplate(variables_disponibles):
    return (
        '<b><span style="font-size:13px">%{location}</span></b><br><br>'
        + build_hover_extra(variables_disponibles)
        + "<extra></extra>"
    )


HOVERLABEL = {
    "bgcolor": "white",
    "bordercolor": "#dddddd",
    "font": {"size": 12, "family": "Arial, sans-serif", "color": "#222222"},
}


def traces_js_per_variable(df_map, variable, variables_disponibles, cultiu_sel, rangs_fixos):
    """Retorna (com a text JS) les 2 traces choroplethmapbox (amb dada + blanc)
    per a una variable concreta. 'geojson' es referencia com a variable JS
    compartida (no es duplica dins de cada trace)."""
    df_amb = df_map[df_map[variable].notna()]
    df_sense = df_map[df_map[variable].isna()]

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
        "hovertemplate": build_hovertemplate(variables_disponibles),
        "hoverlabel": HOVERLABEL,
    }
    trace_sense = {
        "type": "choroplethmapbox",
        "locations": df_sense["COMARCA"].tolist(),
        "z": [0] * len(df_sense),
        "featureidkey": "properties.COMARCA",
        "colorscale": [[0, "white"], [1, "white"]],
        "showscale": False,
        "marker": {"line": {"color": "lightgrey", "width": 0.8}},
        "hovertemplate": '<b><span style="font-size:13px">%{location}</span></b><br><i>Sense dades</i><extra></extra>',
        "hoverlabel": HOVERLABEL,
    }

    # geojson s'insereix com a referència a la variable JS "geojson", no com a JSON literal
    js_amb = json.dumps(trace_amb)[:-1] + ', "geojson": geojson}'
    js_sense = json.dumps(trace_sense)[:-1] + ', "geojson": geojson}'
    return f"[{js_amb}, {js_sense}]"


def panell_variable(key_prefix, tipus_default="Rendiment", reg_sec_default="R", empresa_default="IRTA"):
    """Panell plegable: Tipus (Superfície/Producció/Rendiment) + Reg./Secà + Font,
    tot en una sola línia. Retorna el nom real de la columna resultant,
    p.ex. 'PROD_IRTA(t/ha)_R'."""
    with st.expander("🔧 Variable", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tipus_label = st.segmented_control(
                "Tipus de variable",
                options=list(TIPUS_CODIS.keys()),
                default=tipus_default,
                key=f"tipus_{key_prefix}",
            )
        with c2:
            reg_sec = st.segmented_control(
                "Regadiu / Secà",
                options=["R", "S"],
                default=reg_sec_default,
                key=f"regsec_{key_prefix}",
            )
        with c3:
            empresa = st.segmented_control(
                "Font",
                options=["IRTA", "DARPA"],
                default=empresa_default,
                key=f"empresa_{key_prefix}",
            )

        if tipus_label is None:
            tipus_label = tipus_default
        if reg_sec is None:
            reg_sec = reg_sec_default
        if empresa is None:
            empresa = empresa_default

        variable = nom_variable(TIPUS_CODIS[tipus_label], empresa, reg_sec)
        st.caption(f"→ `{variable}`")
    return variable


def slider_campanya(key_prefix, totes_campanyes):
    minim, maxim = int(min(totes_campanyes)), int(max(totes_campanyes))
    return st.slider(
        "Campanya", min_value=minim, max_value=maxim, value=maxim, step=1, key=f"campanya_{key_prefix}"
    )


def selector_cultiu(key_prefix, tots_cultius):
    default = "BLAT" if "BLAT" in tots_cultius else tots_cultius[0]
    valor = st.segmented_control(
        "Cultiu", options=tots_cultius, default=default, key=f"cultiu_{key_prefix}"
    )
    return valor if valor is not None else default


st.title("Mapa de comarques")

variables_disponibles = [
    c for c in df2.columns if c not in ["COMARCA", "CULTIU", "CAMPANYA"]
]
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
    col1, col2 = st.columns(2)
    with col1:
        cultiu_sel = selector_cultiu("unic", tots_cultius)
    with col2:
        campanya_sel = slider_campanya("unic", totes_campanyes)

    variable_sel = panell_variable("unic")

    df_map = construeix_df_map(campanya_sel, cultiu_sel, totes_comarques)
    df_amb_dada = df_map[df_map[variable_sel].notna()]
    df_sense_dada = df_map[df_map[variable_sel].isna()]

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
                hovertemplate=build_hovertemplate(variables_disponibles),
                hoverlabel=HOVERLABEL,
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
                hovertemplate='<b><span style="font-size:13px">%{location}</span></b><br><i>Sense dades</i><extra></extra>',
                hoverlabel=HOVERLABEL,
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
    # --- Mode comparació: cada banda amb la seva pròpia campanya/cultiu/variable ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Mapa esquerre**")
        sub1, sub2 = st.columns(2)
        with sub1:
            cultiu_esq = selector_cultiu("esq", tots_cultius)
        with sub2:
            campanya_esq = slider_campanya("esq", totes_campanyes)
        variable_esq = panell_variable(
            "esq", tipus_default="Rendiment", reg_sec_default="R", empresa_default="IRTA"
        )

    with col_b:
        st.markdown("**Mapa dret**")
        sub3, sub4 = st.columns(2)
        with sub3:
            cultiu_dre = selector_cultiu("dre", tots_cultius)
        with sub4:
            campanya_dre = slider_campanya("dre", totes_campanyes)
        variable_dre = panell_variable(
            "dre", tipus_default="Rendiment", reg_sec_default="S", empresa_default="IRTA"
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
        "hoverlabel": HOVERLABEL,
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