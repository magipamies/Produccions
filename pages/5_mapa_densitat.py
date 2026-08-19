# -*- coding: utf-8 -*-
"""

author: magipamies
datetime:19/8/2026 15:16
"""
import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

st.set_page_config(page_title="Mapa de densitat (prova)", layout="wide")


@st.cache_data
def load_data():
    df = pd.read_csv("../data_flourish_muni_histo26_rs.csv")
    df["ID_MUN"] = df["ID_MUN"].astype("int64")
    return df


@st.cache_data
def load_centroides():
    """Centroide (lat, lon) de cada municipi, calculat a partir del geojson
    (en lloc dels polígons sencers, que és el que fa servir la pàgina 4)."""
    gdf = gpd.read_file("../muni_cat.geojson")
    gdf["ID_MUN"] = gdf["ID_MUN"].astype("int64")
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    centroides = gdf.geometry.centroid
    return pd.DataFrame(
        {
            "ID_MUN": gdf["ID_MUN"],
            "MUNICIPI": gdf["NOMMUNI"],
            "lat": centroides.y,
            "lon": centroides.x,
        }
    )


# --- Construcció del nom de variable: Tipus + Regadiu/Secà (només IRTA) ---
TIPUS_CODIS = {"Superfície": "ha", "Producció": "t", "Rendiment": "t/ha"}


def nom_variable(tipus_codi, reg_sec):
    if tipus_codi == "ha":
        return f"HA_IRTA_{reg_sec}"
    elif tipus_codi == "t":
        return f"PROD_IRTA(t)_{reg_sec}"
    else:  # "t/ha"
        return f"PROD_IRTA(t/ha)_{reg_sec}"


df_muni = load_data()
centroides = load_centroides()

centre = {"lat": centroides["lat"].mean(), "lon": centroides["lon"].mean()}

st.title("🧪 Mapa de densitat de municipis (prova)")
st.caption(
    "Cada municipi es representa pel seu centroide, ponderat pel valor de la "
    "variable triada, i es dibuixa com una superfície contínua de densitat "
    "en lloc dels polígons exactes — útil per detectar zones de concentració "
    "sense els límits administratius exactes."
)

# --- Selectors ---
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

radi = st.slider(
    "Radi de cada punt (px)",
    min_value=5,
    max_value=60,
    value=25,
    step=1,
    help="Controla com de \"difuminada\" es veu la densitat. Més radi = taques més grans i suaus.",
)

# --- Filtratge i unió amb els centroides ---
df_sel = df_muni[(df_muni["CAMPANYA"] == campanya_sel) & (df_muni["CULTIU"] == cultiu_sel)]
df_sel = df_sel.groupby("ID_MUN", as_index=False)[variable_sel].sum(min_count=1)

df_plot = centroides.merge(df_sel, on="ID_MUN", how="inner")
# El mapa de densitat necessita pesos positius: traiem els municipis sense
# dada o amb valor 0 (no hi ha polígon "en blanc" possible en aquest tipus
# de mapa, com sí que passava amb el choropleth).
df_plot = df_plot[df_plot[variable_sel].notna() & (df_plot[variable_sel] > 0)]

if df_plot.empty:
    st.warning("No hi ha dades per aquesta combinació.")
else:
    fig = go.Figure(
        go.Densitymap(
            lat=df_plot["lat"],
            lon=df_plot["lon"],
            z=df_plot[variable_sel],
            radius=radi,
            colorscale="Viridis",
            customdata=df_plot[["MUNICIPI", variable_sel]],
            hovertemplate=(
                '<b><span style="font-size:13px">%{customdata[0]}</span></b>'
                "<br>Valor: %{customdata[1]:,.2f}<extra></extra>"
            ),
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="#dddddd",
                font=dict(size=12, family="Arial, sans-serif", color="#222222"),
            ),
        )
    )
    fig.update_layout(
        map_style="carto-positron",
        map_zoom=6.3,
        map_center=centre,
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

    with st.expander("Veure els punts (centroides) utilitzats"):
        st.dataframe(
            df_plot[["MUNICIPI", variable_sel]].sort_values(variable_sel, ascending=False),
            width="stretch",
        )