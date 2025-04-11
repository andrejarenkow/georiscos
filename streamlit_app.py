import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Mapa de Hospitais e UBS", layout="wide")

# Título
st.title("Hospitais e UBS do Rio Grande do Sul")

# Lê os dados
hospitais = pd.read_csv("dados/hospitais.csv", sep = ';')
ubs = pd.read_csv("dados/ubs.csv", sep = ';')

# Verifica e renomeia colunas de coordenadas se necessário
for df in [hospitais, ubs]:
    if 'longitude' not in df.columns and 'x' in df.columns:
        df.rename(columns={"x": "longitude", "y": "latitude"}, inplace=True)
    elif 'X' in df.columns:
        df.rename(columns={"X": "longitude", "Y": "latitude"}, inplace=True)

# Filtro opcional
tipo = st.radio("Escolha o que mostrar no mapa:", ["Hospitais", "UBS", "Ambos"])

# Mapeamento dos dados
if tipo == "Hospitais":
    dados = hospitais
    cor = "blue"
    label = "Hospitais"
elif tipo == "UBS":
    dados = ubs
    cor = "green"
    label = "UBS"
else:
    hospitais["Tipo"] = "Hospital"
    ubs["Tipo"] = "UBS"
    dados = pd.concat([hospitais, ubs])
    cor = "Tipo"
    label = "Hospitais e UBS"

# Mapa
fig = px.scatter_mapbox(
    dados,
    lat="latitude",
    lon="longitude",
    color='ds_tipo_un',
    hover_name="NOME_MUNICIPIO" if "NOME_MUNICIPIO" in dados.columns else None,
    hover_data=[col for col in dados.columns if col not in ["latitude", "longitude"]],
    zoom=6,
    height=1000,
    title=f"Localização de {label} no RS"
)

fig.update_layout(mapbox_style="open-street-map")
fig.update_layout(margin={"r":0, "t":30, "l":0, "b":0})


# Exibe o mapa
st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
