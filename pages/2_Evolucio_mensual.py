import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Evolució mensual per comarca", layout="wide")


@st.cache_data
def load_data():
    # Substitueix això per la teva font real de dades si cal
    return pd.read_csv("data_flourish_evolprod_rs.csv")


df3 = load_data()

# DATE com a datetime real (format dia/mes/any)
df3["DATE"] = pd.to_datetime(df3["DATE"], format="%d/%m/%Y")

st.title("Evolució mensual de variables agrícoles per comarca i cultiu")

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

# Columnes numèriques disponibles per graficar
variables_disponibles = [
    c for c in df3.columns if c not in ["COMARCA", "CULTIU", "DATE", "DATE2"]
]

with col2:
    default_variables = [
        v for v in ["PROD(t/ha)_R", "PROD(t/ha)_S"] if v in variables_disponibles
    ]
    variables = st.multiselect(
        "Selecciona la(es) variable(s) a mostrar",
        options=variables_disponibles,
        default=default_variables or variables_disponibles[:1],
    )

# --- Validacions ---
if not comarques:
    st.warning("Selecciona almenys una comarca.")
elif not variables:
    st.warning("Selecciona almenys una variable per veure els gràfics.")
else:
    df_filtrat = df3[df3["COMARCA"].isin(comarques)]

    cultius = sorted(df_filtrat["CULTIU"].dropna().unique())

    if not cultius:
        st.info("No hi ha dades de cultiu per aquesta selecció.")
    else:
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
                line_dash="Variable" if len(variables) > 1 else None,
                line_shape="spline",
                markers=True,
                title=cultiu,
            )
            fig.update_traces(line=dict(smoothing=1.0))

            # Popup personalitzat: comarca en negreta amb el color de la línia,
            # i a sota "Variable: Valor"
            for trace in fig.data:
                parts = trace.name.split(", ")
                comarca_nom = parts[0]
                variable_nom = parts[1] if len(parts) > 1 else variables[0]
                color = trace.line.color
                trace.hovertemplate = (
                    f'<b><span style="color:{color}">{comarca_nom}</span></b><br>'
                    f"{variable_nom}: %{{y:.2f}}<extra></extra>"
                )

            fig.update_layout(
                xaxis_title="Data",
                yaxis_title="Valor",
                legend_title=None,
                hovermode="x unified",
                height=400,
            )
            # Ticks mensuals, mostrant mes i any
            fig.update_xaxes(dtick="M1", tickformat="%b %Y", hoverformat="%b %Y")

            with cols[i % n_cols]:
                st.plotly_chart(fig, use_container_width=True)

        with st.expander("Veure dades filtrades"):
            st.dataframe(df_filtrat)
