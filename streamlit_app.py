import streamlit as st

st.set_page_config(page_title="Prediccions de collita IRTA vs DARPA", page_icon="🌾", layout="wide")

st.title("🌾 Prediccions de collita: IRTA vs DARPA")
st.markdown(
    "Aquesta aplicació compara les **prediccions de collita** que fa l'IRTA "
    "(Blat, Ordi, Blat de Moro i Ametller) amb les **estadístiques oficials** "
    "que publica el DARPA (Departament d'Agricultura de la Generalitat de "
    "Catalunya). Per a la campanya del **2026**, encara només hi ha "
    "disponibles les prediccions de l'IRTA."
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
    "Compara any a any les prediccions de l'IRTA amb les dades del DARPA "
    "(superfície, producció, rendiment), per comarca i cultiu.",
)
targeta(
    col2,
    "pages/2_Evolucio_mensual.py",
    "📅",
    "Evolució mensual de les prediccions 2026",
    "Com han anat evolucionant, mes a mes, les prediccions que ha fet l'IRTA "
    "durant la campanya 2026, per comarca i cultiu.",
)

col3, col4 = st.columns(2)
targeta(
    col3,
    "pages/3_Mapa_comarques.py",
    "🗺️",
    "Mapa de comarques",
    "Distribució espacial de les dades a nivell de comarca, comparant IRTA i "
    "DARPA. Es poden veure dues variables costat a costat.",
)
targeta(
    col4,
    "pages/4_Mapa_municipis.py",
    "📍",
    "Mapa de municipis",
    "El mateix tipus de mapa, a escala de municipi (~950) — aquí només amb "
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
    "- **DARPA**: [Estadístiques definitives de conreus]"
    "(https://agricultura.gencat.cat/ca/departament/observatori-agroambiental/"
    "estadistiques/agricultura/estadistiques-definitives-conreus/), "
    "Departament d'Agricultura de la Generalitat de Catalunya.\n"
    "- **IRTA**: prediccions generades pel programa de recerca "
    "[Ús eficient de l'aigua en agricultura]"
    "(https://www.irta.cat/programa-de-recerca/us-eficient-de-laigua-en-agricultura/)."
)