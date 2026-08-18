import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Evolució per comarca", layout="wide")


@st.cache_data
def load_data():
    return pd.read_csv("data_flourish_histo26_rs.csv")


df2 = load_data()

# CAMPANYA com a datetime (només any, format %Y)
df2["CAMPANYA"] = pd.to_datetime(df2["CAMPANYA"], format="%Y")

st.title("Evolució de variables agrícoles per comarca i cultiu")

# --- Construcció del nom de variable: Tipus + Font (IRTA/DARPA) + Regadiu/Secà ---
TIPUS_CODIS = {"Superfície": "ha", "Producció": "t", "Rendiment": "t/ha"}


def nom_variable(tipus_codi, empresa, reg_sec):
    if tipus_codi == "ha":
        return f"HA_{empresa}_{reg_sec}"
    elif tipus_codi == "t":
        return f"PROD_{empresa}(t)_{reg_sec}"
    else:  # "t/ha"
        return f"PROD_{empresa}(t/ha)_{reg_sec}"


def panell_variable():
    """Tipus de variable (un de sol, defineix la unitat de l'eix Y) +
    Regadiu/Secà + Font (IRTA/DARPA), aquests dos últims es poden triar a la
    vegada, sense amagar-ho dins de cap panell plegable.
    Retorna (llista_de_columnes, map_regsec {columna: 'R'}, map_font
    {columna: 'IRTA'}, títol eix Y)."""
    c1, c2, c3 = st.columns(3)
    with c1:
        tipus_label = st.segmented_control(
            "Tipus de variable",
            options=list(TIPUS_CODIS.keys()),
            default="Rendiment",
            key="tipus_unic",
        )
    with c2:
        reg_sec_sel = st.segmented_control(
            "Regadiu / Secà",
            options=["R", "S"],
            selection_mode="multi",
            default=["R"],
            key="regsec_unic",
        )
    with c3:
        empresa_sel = st.segmented_control(
            "Font",
            options=["IRTA", "DARPA"],
            selection_mode="multi",
            default=["IRTA"],
            key="empresa_unic",
        )

    if tipus_label is None:
        tipus_label = "Rendiment"
    if reg_sec_sel is None:
        reg_sec_sel = []
    if empresa_sel is None:
        empresa_sel = []

    tipus_codi = TIPUS_CODIS[tipus_label]

    cols_resultants = []
    map_regsec = {}
    map_font = {}
    for rs in ["R", "S"]:
        if rs not in reg_sec_sel:
            continue
        for emp in ["IRTA", "DARPA"]:
            if emp not in empresa_sel:
                continue
            col = nom_variable(tipus_codi, emp, rs)
            cols_resultants.append(col)
            map_regsec[col] = rs
            map_font[col] = emp

    eix_y_titol = f"{tipus_label} ({tipus_codi})"

    return cols_resultants, map_regsec, map_font, eix_y_titol


# --- Selectors ---
totes_comarques = sorted(df2["COMARCA"].dropna().unique())
default_comarca = ["Segrià"] if "Segrià" in totes_comarques else totes_comarques[:1]
comarques = st.multiselect(
    "Selecciona la(es) comarca(es)",
    options=totes_comarques,
    default=default_comarca,
)

variables, map_regsec, map_font, eix_y_titol = panell_variable()

# --- Validacions ---
if not comarques:
    st.warning("Selecciona almenys una comarca.")
elif not variables:
    st.warning("Selecciona almenys una combinació de Regadiu/Secà i Font per veure els gràfics.")
else:
    df_filtrat = df2[df2["COMARCA"].isin(comarques)]

    cultius = sorted(df_filtrat["CULTIU"].dropna().unique())

    if not cultius:
        st.info("No hi ha dades de cultiu per aquesta selecció.")
    else:
        n_cols = 2  # nombre de gràfics per fila al grid
        cols = st.columns(n_cols)

        for i, cultiu in enumerate(cultius):
            df_cultiu = df_filtrat[df_filtrat["CULTIU"] == cultiu]

            df_long = df_cultiu.melt(
                id_vars=["CAMPANYA", "COMARCA"],
                value_vars=variables,
                var_name="ColumnaOrigen",
                value_name="Valor",
            )

            # A l'origen, "sense dada" es codifica com a 0 (no com a NaN).
            # El convertim a NaN perquè Plotly deixi un buit en lloc de baixar a 0.
            df_long["Valor"] = df_long["Valor"].replace(0, pd.NA)

            # Separem Regadiu/Secà i Font com a dues dimensions independents,
            # perquè cadascuna controli un atribut visual FIX (no depenent de
            # què hagis seleccionat): R=línia contínua, S=discontínua;
            # IRTA=cercle, DARPA=quadrat. El color queda lliure per comarca.
            df_long["RegSec"] = df_long["ColumnaOrigen"].map(map_regsec)
            df_long["Font"] = df_long["ColumnaOrigen"].map(map_font)

            # Si per la mateixa CAMPANYA+COMARCA+RegSec+Font hi ha diverses files,
            # sumem. min_count=1 fa que si TOTS els valors del grup són NaN, el
            # resultat sigui NaN (i per tant no es dibuixi res) en lloc de 0.
            df_long = df_long.groupby(
                ["CAMPANYA", "COMARCA", "RegSec", "Font"], as_index=False
            )["Valor"].sum(min_count=1)

            fig = px.line(
                df_long,
                x="CAMPANYA",
                y="Valor",
                color="COMARCA",
                line_dash="RegSec",
                line_dash_map={"R": "solid", "S": "dash"},
                symbol="Font",
                symbol_map={"IRTA": "circle", "DARPA": "square"},
                line_shape="spline",
                markers=True,
                title=cultiu,
            )
            fig.update_traces(line=dict(smoothing=1.0))

            # Popup personalitzat: comarca en negreta amb el color de la línia,
            # i a sota "R-IRTA: Valor"
            for trace in fig.data:
                parts = trace.name.split(", ")
                comarca_nom = parts[0]
                variable_nom = "-".join(parts[1:]) if len(parts) > 1 else ""
                color = trace.line.color
                trace.hovertemplate = (
                    f'<b><span style="color:{color}">{comarca_nom}</span></b><br>'
                    f"{variable_nom}: %{{y:.2f}}<extra></extra>"
                )

            fig.update_layout(
                xaxis_title="Campanya",
                yaxis_title=eix_y_titol,
                legend_title=None,
                hovermode="x unified",
                height=400,
            )
            # Com que CAMPANYA és datetime, mostrem només l'any als ticks
            fig.update_xaxes(dtick="M12", tickformat="%Y", hoverformat="%Y")

            with cols[i % n_cols]:
                st.plotly_chart(fig, use_container_width=True)

        with st.expander("Veure dades filtrades"):
            st.dataframe(df_filtrat)