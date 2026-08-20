import streamlit as st

st.set_page_config(page_title="Prediccions de collita IRTA", page_icon="🌾", layout="wide")

st.title("Prediccions de collita IRTA")
st.markdown(
    "Aquesta aplicació permet visualitzar les **prediccions de collita** que fa l'IRTA "
    "(Blat, Ordi, Blat de Moro i Ametller) i comparar-les amb les **estadístiques oficials** "
    "que publica el DARPA (Departament d'Agricultura, Ramaderia, Pesca i Alimentació de la "
    "Generalitat de Catalunya). Per a la campanya del **2026** només hi ha "
    "disponibles les prediccions de l'IRTA."
)
st.markdown(
    "Aquesta eina forma part del programa de recerca de l'IRTA "
    "[**Ús eficient de l'aigua en agricultura**]"
    "(https://www.irta.cat/programa-de-recerca/us-eficient-de-laigua-en-agricultura/)."
)

st.markdown("#### 🌱 Què hi trobaràs")
col_cultius, col_variables = st.columns(2)
with col_cultius:
    st.markdown("**Cultius**")
    st.markdown("🌾 Blat &nbsp;·&nbsp; 🌾 Ordi &nbsp;·&nbsp; 🌽 Blat de Moro &nbsp;·&nbsp; 🌳 Ametller")
with col_variables:
    st.markdown("**Variables** (per Regadiu / Secà)")
    st.markdown("📐 Superfície (ha) &nbsp;·&nbsp; 🌾 Producció (t) &nbsp;·&nbsp; 📊 Rendiment (t/ha)")

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
    "pages/1_Comparativa_per_comarca.py",
    "📈",
    "Comparativa de les prediccions anuals",
    "Compara any a any les prediccions de l'IRTA amb les dades del DARPA "
    "(superfície, producció, rendiment), per comarca, cultiu i regadiu/secà.",
)
targeta(
    col2,
    "pages/2_Evolucio_mensual.py",
    "📅",
    "Evolució mensual de les prediccions 2026",
    "Com han anat evolucionant, mes a mes, les prediccions que ha fet l'IRTA "
    "durant la campanya 2026, per comarca, cultiu i regadiu/secà.",
)

col3, col4 = st.columns(2)
targeta(
    col3,
    "pages/3_Mapa_comarques.py",
    "🗺️",
    "Mapa de comarques",
    "Distribució espacial de les dades a nivell de comarca, comparant IRTA i "
    "DARPA. Permet comparar dues variables una al costat de l'altre.",
)
targeta(
    col4,
    "pages/4_Mapa_municipis.py",
    "📍",
    "Mapa de municipis",
    "El mateix tipus de mapa, a escala municipal. Només amb "
    "les prediccions de l'IRTA, ja que el DARPA no publica a aquest detall.",
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

st.markdown("##### Fonts de les dades")
st.markdown(
    "- **IRTA**: prediccions generades pel programa de recerca "
    "[Ús eficient de l'aigua en agricultura]"
    "(https://www.irta.cat/programa-de-recerca/us-eficient-de-laigua-en-agricultura/).\n"
    "- **DARPA**: [Estadístiques definitives de conreus]"
    "(https://agricultura.gencat.cat/ca/departament/observatori-agroambiental/"
    "estadistiques/agricultura/estadistiques-definitives-conreus/), "
    "Departament d'Agricultura, Ramaderia, Pesca i Alimentació de la Generalitat de Catalunya."
)