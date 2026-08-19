import random
import colorsys

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Evolució mensual per comarca", layout="wide")


def colors_aleatoris(n):
    """Genera n colors amb to (hue) aleatori, saturació i lluminositat fixes
    dins d'un rang que garanteix bon contrast sobre fons blanc."""
    colors = []
    for _ in range(n):
        h = random.random()
        s = random.uniform(0.55, 0.85)
        l = random.uniform(0.35, 0.55)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        colors.append(f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}")
    return colors


def colors_per_comarca(comarques):
    """Colors aleatoris per comarca, cachejats a session_state perquè no
    canviïn cada vegada que es refà l'script (només quan canvia la selecció
    de comarques)."""
    clau = "colors_comarca_" + "|".join(sorted(comarques))
    if clau not in st.session_state:
        st.session_state[clau] = dict(zip(comarques, colors_aleatoris(len(comarques))))
    return st.session_state[clau]


@st.cache_data
def load_data():
    # Substitueix això per la teva font real de dades si cal
    return pd.read_csv("data_flourish_evolprod_rs.csv")


df3 = load_data()

# DATE com a datetime real (format dia/mes/any)
df3["DATE"] = pd.to_datetime(df3["DATE"], format="%d/%m/%Y")

st.title("Evolució mensual de variables agrícoles per comarca i cultiu")

# --- Construcció del nom de variable: Tipus + Regadiu/Secà ---
TIPUS_CODIS = {"Superfície": "ha", "Producció": "t", "Rendiment": "t/ha"}


def nom_variable(tipus_codi, reg_sec):
    if tipus_codi == "ha":
        return f"HA_{reg_sec}"
    elif tipus_codi == "t":
        return f"PROD(t)_{reg_sec}"
    else:  # "t/ha"
        return f"PROD(t/ha)_{reg_sec}"


def panell_variable():
    """Tipus de variable (un de sol, defineix la unitat de l'eix Y) +
    Regadiu/Secà (es poden triar els dos a la vegada), sense amagar-ho
    dins de cap panell plegable. Retorna (llista_de_columnes, unitat)."""
    c1, c2 = st.columns(2)
    with c1:
        tipus_label = st.segmented_control(
            "Tipus de variable",
            options=list(TIPUS_CODIS.keys()),
            default="Rendiment",
            key="tipus_evol",
        )
    with c2:
        reg_sec_sel = st.segmented_control(
            "Regadiu / Secà",
            options=["R", "S"],
            selection_mode="multi",
            default=["R"],
            key="regsec_evol",
        )

    if tipus_label is None:
        tipus_label = "Rendiment"
    if reg_sec_sel is None:
        reg_sec_sel = []

    tipus_codi = TIPUS_CODIS[tipus_label]
    cols_resultants = [nom_variable(tipus_codi, rs) for rs in ["R", "S"] if rs in reg_sec_sel]
    eix_y_titol = f"{tipus_label} ({tipus_codi})"

    return cols_resultants, eix_y_titol


# --- Selectors ---
col1, col2 = st.columns(2)

with col1:
    totes_comarques = sorted(df3["COMARCA"].dropna().unique())
    default_comarca = ["Segrià"] if "Segrià" in totes_comarques else totes_comarques[:1]
    comarques = st.multiselect(
        "Selecciona la(es) comarca(es)",
        options=totes_comarques,
        default=default_comarca,
    )

with col2:
    variables, eix_y_titol = panell_variable()

# --- Validacions ---
if not comarques:
    st.warning("Selecciona almenys una comarca.")
elif not variables:
    st.warning("Selecciona Regadiu i/o Secà per veure els gràfics.")
else:
    df_filtrat = df3[df3["COMARCA"].isin(comarques)]

    cultius = sorted(df_filtrat["CULTIU"].dropna().unique())

    if not cultius:
        st.info("No hi ha dades de cultiu per aquesta selecció.")
    else:
        comarca_colors = colors_per_comarca(comarques)

        n_cols = 2  # nombre de gràfics per fila al grid
        cols = st.columns(n_cols)

        for i, cultiu in enumerate(cultius):
            df_cultiu = df_filtrat[df_filtrat["CULTIU"] == cultiu]

            df_long = df_cultiu.melt(
                id_vars=["DATE", "COMARCA"],
                value_vars=variables,
                var_name="Variable",
                value_name="Valor",
            )

            # A la llegenda/popup només volem "R"/"S", no el nom sencer de la
            # columna (la unitat ja queda clara amb el títol de l'eix Y)
            df_long["Variable"] = df_long["Variable"].str.rsplit("_", n=1).str[-1]

            # Si per la mateixa DATE+COMARCA+Variable hi ha diverses files, sumem.
            # min_count=1 fa que si TOTS els valors del grup són NaN, el resultat
            # sigui NaN (i per tant no es dibuixi res) en lloc de 0.
            df_long = df_long.groupby(
                ["DATE", "COMARCA", "Variable"], as_index=False
            )["Valor"].sum(min_count=1)

            fig = px.line(
                df_long,
                x="DATE",
                y="Valor",
                color="COMARCA",
                color_discrete_map=comarca_colors,
                line_dash="Variable",
                line_dash_map={"R": "solid", "S": "dash"},
                line_shape="spline",
                markers=True,
                title=cultiu,
            )
            fig.update_traces(line=dict(smoothing=1.0))

            # Popup personalitzat: comarca en negreta amb el color de la línia,
            # i a sota "R"/"S": Valor
            for trace in fig.data:
                parts = trace.name.split(", ")
                comarca_nom = parts[0]
                variable_nom = parts[1] if len(parts) > 1 else ""
                color = trace.line.color
                trace.name = f"{comarca_nom} · {variable_nom}" if variable_nom else comarca_nom
                trace.hovertemplate = (
                    f'<b><span style="color:{color}">{comarca_nom}</span></b><br>'
                    f"{variable_nom}: %{{y:.2f}}<extra></extra>"
                )

            fig.update_layout(
                xaxis_title="Data",
                yaxis_title=eix_y_titol,
                legend_title=None,
                hovermode="x unified",
                height=400,
            )
            # Ticks mensuals, mostrant mes i any
            fig.update_xaxes(dtick="M1", tickformat="%b %Y", hoverformat="%b %Y")

            with cols[i % n_cols]:
                st.plotly_chart(fig, width="stretch")

        with st.expander("Veure dades filtrades"):
            st.dataframe(df_filtrat)