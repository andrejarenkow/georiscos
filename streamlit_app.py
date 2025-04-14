import streamlit as st
import pandas as pd
import plotly.express as px
import geopandas as gpd
import json
import requests

st.set_page_config(page_title="Mapa de Hospitais e UBS", layout="wide")

st.title("Hospitais e UBS do Rio Grande do Sul")

# === Função para buscar alertas do INMET ===
def buscar_alertas_rs():
    url = "https://apiprevmet3.inmet.gov.br/avisos/rs"
    try:
        response = requests.get(url)
        alertas = response.json()

        features = []
        for alerta in alertas:
            if "geometry" in alerta and alerta["geometry"]:
                features.append({
                    "type": "Feature",
                    "geometry": alerta["geometry"],
                    "properties": {
                        "titulo": alerta["titulo"],
                        "nivel": alerta.get("nivel"),
                        "inicio": alerta.get("inicio"),
                        "fim": alerta.get("fim"),
                        "descricao": alerta.get("descricao")
                    }
                })

        geojson_alertas = {
            "type": "FeatureCollection",
            "features": features
        }

        gdf_alertas = gpd.GeoDataFrame.from_features(geojson_alertas, crs="EPSG:4326")
        return gdf_alertas

    except Exception as e:
        st.error(f"Erro ao buscar alertas: {e}")
        return gpd.GeoDataFrame()

# === Lê os dados de hospitais e UBS ===
hospitais = pd.read_csv("dados/hospitais.csv", sep=';')
ubs = pd.read_csv("dados/ubs.csv", sep=';')

# Corrige colunas
for df in [hospitais, ubs]:
    if 'longitude' not in df.columns and 'x' in df.columns:
        df.rename(columns={"x": "longitude", "y": "latitude"}, inplace=True)
    elif 'X' in df.columns:
        df.rename(columns={"X": "longitude", "Y": "latitude"}, inplace=True)

# === Busca os alertas ===
gdf_alertas = buscar_alertas_rs()
geojson_alertas = json.loads(gdf_alertas.to_json()) if not gdf_alertas.empty else None

# === Filtro de tipo ===
tipo = st.radio("Escolha o que mostrar no mapa:", ["Hospitais", "UBS", "Ambos"])

if tipo == "Hospitais":
    dados = hospitais
    label = "Hospitais"
elif tipo == "UBS":
    dados = ubs
    label = "UBS"
else:
    hospitais["Tipo"] = "Hospital"
    ubs["Tipo"] = "UBS"
    dados = pd.concat([hospitais, ubs])
    label = "Hospitais e UBS"

# === Mapa base ===
fig = px.scatter_mapbox(
    dados,
    lat="latitude",
    lon="longitude",
    color='ds_tipo_un',
    hover_name="NOME_MUNICIPIO" if "NOME_MUNICIPIO" in dados.columns else None,
    hover_data=[col for col in dados.columns if col not in ["latitude", "longitude"]],
    zoom=6,
    height=800,
    width=800,
    title=f"Localização de {label} no RS",
    center={'lat': -30.537, 'lon': -52.965}
)

fig.update_layout(mapbox_style="open-street-map")

# === Adiciona polígonos dos alertas, se existirem ===
if geojson_alertas:
    fig.update_layout(
        mapbox_layers=[
            {
                "sourcetype": "geojson",
                "source": geojson_alertas,
                "type": "fill",
                "color": "rgba(255,0,0,0.2)",
                "opacity": 0.3
            },
            {
                "sourcetype": "geojson",
                "source": geojson_alertas,
                "type": "line",
                "color": "red",
                "line": {"width": 2}
            }
        ]
    )

fig.update_layout(margin={"r": 0, "t": 30, "l": 0, "b": 0})
st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
