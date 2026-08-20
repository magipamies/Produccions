import streamlit as st

st.set_page_config(page_title="Producció Agrícola de Catalunya", page_icon="🌾", layout="wide")

st.title("🌾 Producció Agrícola de Catalunya")
st.markdown(
    "Explora l'evolució de la superfície, la producció i el rendiment agrícola "
    "a Catalunya, per comarca, municipi i cultiu — comparant Regadiu/Secà i, "
    "segons la vista, també la font de la dada (IRTA/DARPA)."
)
st.markdown("Tria una de les vistes de sota per començar:")

st.divider()


def targeta(col, pagina, icona, titol, descripcio, experimental=False):
    with col:
        with st.container(border=True):
            st.page_link(pagina, label=f"**{titol}**", icon=icona)
            if experimental:
                st.caption("🧪 Vista experimental")
            st.write(descripcio)


col1, col2 = st.columns(2)
targeta(
    col1,
    "pages/1_Evolucio_per_comarca.py",
    "📈",
    "Evolució per comarca",
    "Gràfics d'evolució anual (superfície, producció, rendiment) per comarca "
    "i cultiu, un gràfic per cultiu, comparant Regadiu/Secà i IRTA/DARPA.",
)
targeta(
    col2,
    "pages/2_Evolucio_mensual.py",
    "📅",
    "Evolució mensual",
    "El mateix tipus d'evolució, però dins d'una campanya concreta, mes a mes "
    "en lloc d'any a any.",
)

col3, col4 = st.columns(2)
targeta(
    col3,
    "pages/3_Mapa_comarques.py",
    "🗺️",
    "Mapa de comarques",
    "Mapa interactiu de Catalunya per comarca, amb la variable, el cultiu i la "
    "campanya que triïs. Es poden comparar dues variables costat a costat.",
)
targeta(
    col4,
    "pages/4_Mapa_municipis.py",
    "📍",
    "Mapa de municipis",
    "El mateix mapa, a escala de municipi (~950), amb dades només d'IRTA.",
)

col5, _ = st.columns(2)
targeta(
    col5,
    "pages/5_Mapa_difuminat.py",
    "🌫️",
    "Mapa difuminat de municipis",
    "Variant visual del mapa de municipis: cada municipi conserva el seu "
    "valor real, però amb les vores difuminades en lloc dels límits exactes.",
    experimental=True,
)

st.divider()
st.caption("Font de les dades: IRTA / DARPA. Dades de producció agrícola de Catalunya.")