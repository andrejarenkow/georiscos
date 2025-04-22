import streamlit as st
import pandas as pd
import requests
import geojson
import json
from bs4 import BeautifulSoup
import re
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# Configuração da página
st.set_page_config(
    page_title="Georiscos",
    page_icon=":foggy:",
    layout="wide",
    initial_sidebar_state='expanded'
)

# Cabeçalho
col1, col2, col3 = st.columns([1, 4, 1])
col1.image('https://github.com/andrejarenkow/csv/blob/master/logo_cevs%20(2).png?raw=true', width=100)
col2.header('Mapa de Riscos no Rio Grande do Sul')
col3.image('https://github.com/andrejarenkow/csv/blob/master/logo_estado%20(3)%20(1).png?raw=true', width=150)

st.sidebar.header("Georiscos")
st.sidebar.write("Protótipo para análise de risco baseada nos alertas do INMET e do CEMADEM.")

# Busca dados de deslizamentos
url = "https://georisk.cemaden.gov.br/?dia=0&grid=intermediaria&markers=LocaisDeslizamentosMarker"
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers)

dados = []

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    scripts = soup.find_all("script")

    for script in scripts:
        texto = script.text.replace('\\', '')
        match_push = re.search(r'self\.__next_f\.push\(\[(.*?)\]\)', texto, re.DOTALL)
        if not match_push:
            continue

        conteudo = match_push.group(1)
        blocos = re.findall(r'{[^}]*"Latitude":[^}]*"Longitude":[^}]*}', conteudo)

        for bloco in blocos:
            try:
                data = re.search(r'"Data Ocorrência":"(.*?)"', bloco)
                mag = re.search(r'"Magnitude_evento":"(.*?)"', bloco)
                prec = re.search(r'"Precisão_localização":"(.*?)"', bloco)
                fonte = re.search(r'"Fonte_informação":"(.*?)"', bloco)
                lat = re.search(r'"Latitude":(-?\d+\.?\d*)', bloco)
                lon = re.search(r'"Longitude":(-?\d+\.?\d*)', bloco)

                if data and mag and prec and fonte and lat and lon:
                    dados.append({
                        "Data Ocorrência": data.group(1),
                        "Magnitude_evento": mag.group(1),
                        "Precisão_localização": prec.group(1),
                        "Fonte_informação": fonte.group(1),
                        "Latitude": float(lat.group(1)),
                        "Longitude": float(lon.group(1))
                    })
            except Exception:
                continue

df = pd.DataFrame(dados).drop_duplicates().reset_index(drop=True)

# Filtros para RS
lat_min, lat_max = -33.75, -27.0
lon_min, lon_max = -57.65, -49.5
df_deslizamentos = df[
    (df['Latitude'] >= lat_min) & (df['Latitude'] <= lat_max) &
    (df['Longitude'] >= lon_min) & (df['Longitude'] <= lon_max)
].reset_index(drop=True)

# Lê dados locais
hospitais = pd.read_csv("dados/hospitais.csv", sep=';')
ubs = pd.read_csv("dados/ubs.csv", sep=';')
dados_indigenas = pd.read_excel('dados/Aldeias polo sul.xlsx')
dados_indigenas['Latitude'] = pd.to_numeric(dados_indigenas['Latitude'], errors = 'coerce')
dados_indigenas = dados_indigenas.dropna(subset = 'Latitude')

# Ajusta colunas
for df_local in [hospitais, ubs]:
    if 'longitude' not in df_local.columns and 'x' in df_local.columns:
        df_local.rename(columns={"x": "longitude", "y": "latitude"}, inplace=True)
    elif 'X' in df_local.columns:
        df_local.rename(columns={"X": "longitude", "Y": "latitude"}, inplace=True)

# Tipo de dados no mapa
tipo = "Ambos"
if tipo == "Hospitais":
    dados = hospitais
elif tipo == "UBS":
    dados = ubs
else:
    hospitais["Tipo"] = "Hospital"
    ubs["Tipo"] = "UBS"
    dados = pd.concat([hospitais, ubs])
label = "Hospitais e UBS"

# Função para buscar alertas do INMET
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
    except Exception:
        st.error("Sem alertas para o Estado")
        return {"features": []}

# Carrega os alertas
geojson_data = obter_alertas_rs()

# Mapa base centrado no RS
m = folium.Map(location=[-30.537, -52.965], zoom_start=6, tiles="OpenStreetMap")

# Criando as camadas do mapa
layer_hospitais = folium.FeatureGroup(name='Hospitais')
layer_ubs = folium.FeatureGroup(name='UBS')
layer_indigena = folium.FeatureGroup(name='Território Indígena')
layer_deslizamentos = folium.FeatureGroup(name='Deslizamentos')

# Adiciona camada com os municípios do RS
url_municipios_rs = "https://raw.githubusercontent.com/andrejarenkow/geodata/refs/heads/main/municipios_rs_CRS/RS_Municipios_2021.json"

try:
    gjson_municipios = requests.get(url_municipios_rs).json()

    folium.GeoJson(
        gjson_municipios,
        control=False,
        name="Municípios do RS",
        style_function=lambda feature: {
            'fillColor': 'none',
            'color': '#555',
            'weight': 1,
            'fillOpacity': 0.1
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NM_MUN"],  # nome da coluna no GeoJSON
            aliases=["Município:"],
            localize=True
        )
    ).add_to(m)

except Exception as e:
    st.warning(f"Não foi possível carregar os municípios do RS: {e}")

# Adiciona hospitais
for _, row in hospitais.iterrows():
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=8,
        color="#0055CC",
        #fill=True,
        #fill_color="#0055CC",
        #fill_opacity=0.7,
        popup=f'Hospital: {row["nome_da_unidade"]} - {row["municipio"]}'
    ).add_to(layer_hospitais)

# Adiciona UBS
for _, row in ubs.iterrows():
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=5,
        color="#c90101",
        #fill=True,
        #fill_color="#c90101",
        #fill_opacity=0.7,
        popup=f'UBS: {row["nome_da_unidade"]} - {row["municipio"]}'
    ).add_to(layer_ubs)

# Adiciona aldeias indígenas
for _, row in dados_indigenas.iterrows():
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        icon=folium.Icon(color="orange", icon="campground", prefix = 'fa'),
        popup=f'Aldeia: {row["Aldeia"]} - {row["Município"]}'
    ).add_to(layer_indigena)

# Adiciona deslizamentos
for _, row in df_deslizamentos.iterrows():
    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        radius=6,
        color="#8c592f",
        fill=True,
        fill_color="#8c592f",
        fill_opacity=0.7,
        popup=f'Deslizamento: {row["Magnitude_evento"]} - {row["Data Ocorrência"]}'
    ).add_to(layer_deslizamentos)

# Adiciona polígonos dos alertas
for feature in geojson_data["features"]:
    coords = feature["geometry"]["coordinates"][0]
    props = feature["properties"]
    descricao = props.get("descricao", "Alerta")
    estados = props.get("estados", "")
    cor_aviso = props.get("aviso_cor", "#FF0000")

    rgba_cor = cor_aviso if cor_aviso.startswith("rgba") else cor_aviso
    folium.Polygon(
        locations=[[lat, lon] for lon, lat in coords],
        color="black",
        fill_color=rgba_cor,
        fill_opacity=0.4,
        weight=2,
        popup=f"{descricao} - Estados: {estados}"
    ).add_to(m)



    folium.LayerControl(collapsed=False).add_to(m)


m.add_child(layer_hospitais)
m.add_child(layer_ubs)
m.add_child(layer_indigena)
m.add_child(layer_deslizamentos)

# Tile Layer do OpenTopoMap
folium.TileLayer(
    tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    name='Topografia',
    attr='Map data: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, '
         '<a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: © <a href="https://opentopomap.org">OpenTopoMap</a> '
         '(<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
    max_zoom=17,
    overlay=True,
    control=True
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
# Exibe o mapa
st_data = st_folium(m, width=1400, height=800, returned_objects=[])
