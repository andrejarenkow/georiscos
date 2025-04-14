import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import geojson
import json

st.set_page_config(page_title="Mapa de Hospitais, UBS e Alertas INMET", layout="wide")

# Título
st.title("Hospitais, UBS e Alertas do INMET no Rio Grande do Sul")

# Lê os dados
hospitais = pd.read_csv("dados/hospitais.csv", sep=';')
ubs = pd.read_csv("dados/ubs.csv", sep=';')
dados_indigenas = pd.read_excel('dados/Aldeias polo sul.xlsx')

# Ajusta colunas de coordenadas se necessário
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

# Função para buscar os alertas do INMET
def obter_alertas_rs():
    url = "https://apiprevmet3.inmet.gov.br/avisos/ativos"
    try:
        resposta = requests.get(url)
        resposta.raise_for_status()
        dados = resposta.json()
        
        lista_avisos_rs = []
        for aviso in dados.get('hoje', []):
            if 'Rio Grande do Sul' in aviso.get('estados', ''):
                lista_avisos_rs.append(aviso)
                
        for aviso in dados.get('futuro', []):
            if 'Rio Grande do Sul' in aviso.get('estados', ''):
                lista_avisos_rs.append(aviso)
                
        lista_features = []
        for aviso in lista_avisos_rs:
            feature = geojson.Feature(geometry=json.loads(aviso['poligono']), properties=aviso)
            lista_features.append(feature)

        feature_collection = geojson.FeatureCollection(lista_features)
        return json.loads(geojson.dumps(feature_collection))
    except Exception as e:
        st.error(f"Sem alertas para o Estado")
        return {"features": []}

# Recupera os dados dos alertas
geojson_data = obter_alertas_rs()

# Criação do mapa base
fig = go.Figure()

# Adiciona os pontos de hospitais/UBS
fig.add_trace(go.Scattermapbox(
    lat=dados["latitude"],
    lon=dados["longitude"],
    mode='markers',
    marker=go.scattermapbox.Marker(size=8, color="#0055CC" if tipo == "Hospitais" else "#C9372C" if tipo == "UBS" else dados["Tipo"].map({"Hospital": "#0055CC", "UBS": "#C9372C"})),
    text=dados["nome_da_unidade"] + " - " + dados["municipio"],
    name=label,
    hoverinfo='text',
    opacity = 0.8
))

# Adiciona os pontos de aldeias indigenas
fig.add_trace(go.Scattermapbox(
    lat=dados_indigenas["Latitude"],
    lon=dados_indigenas["Longitude"],
    mode='markers',
    marker=go.scattermapbox.Marker(size=8, color="green"),
    text=dados_indigenas["Aldeia"] + " - " + dados_indigenas["Município"],
    name=label,
    hoverinfo='text',
    opacity = 0.8
))

# Função para converter cor hex para rgba com opacidade
def hex_to_rgba(hex_color, alpha=0.5):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({r},{g},{b},{alpha})"
    else:
        return "rgba(255,0,0,0.5)"  # fallback para vermelho com opacidade

# Adiciona os polígonos dos alertas
for feature in geojson_data["features"]:
    coords = feature["geometry"]["coordinates"][0]
    lon, lat = zip(*coords)
    props = feature["properties"]
    cor_aviso = props.get("aviso_cor", "#FF0000")
    descricao = props.get("descricao", "Alerta")
    estados = props.get("estados", "")

    fig.add_trace(go.Scattermapbox(
        lat=lat,
        lon=lon,
        mode='lines',
        fill='toself',
        line=dict(width=2, color='black'),
        fillcolor=hex_to_rgba(cor_aviso, alpha=0.5),
        name=f"Alerta: {descricao}",
        hoverinfo='text',
        text=f"{descricao}<br>Estados: {estados}"
    ))


fig.update_layout(
    mapbox=dict(
        style="open-street-map",
        zoom=6,
        center={"lat": -30.537, "lon": -52.965}
    ),
    margin={"r": 0, "t": 30, "l": 0, "b": 0},
    height=800,
    title=f"Localização de {label} e Alertas INMET no RS"
)
    

# Exibe o mapa
st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})


