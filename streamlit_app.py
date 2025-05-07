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
from shapely.geometry import shape
from shapely.ops import unary_union

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

# Layout
coluna_mapa, coluna_metricas = st.columns([3,1])

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
escolas_estaduais = pd.read_csv("dados/escolas_estaduais.csv", sep=';')
barragens = pd.read_csv("dados/barragens_risco_danopotencial_alto.csv", sep=';')
barragens = barragens[barragens['risco'] == 'Alto']

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
            if 'Rio Grande do Sul' in aviso.get('estados', '') and 'Potencial' not in aviso.get('severidade', ''):
                lista_avisos_rs.append(aviso)
        for aviso in dados.get('futuro', []):
            if 'Rio Grande do Sul' in aviso.get('estados', '') and 'Potencial' not in aviso.get('severidade', ''):
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

# Percorrer todos os features e transformar cada geometry em shapely object
polygons = [shape(feature['geometry']) for feature in geojson_data['features']]

# Unir todos os polígonos em um só
polygon_union = unary_union(polygons)

# Deixar apenas os pontos dentro dos alertas
# --- Função para transformar um DataFrame em GeoDataFrame ---
def df_para_gdf(df, lon_col='longitude', lat_col='latitude'):
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
        crs="EPSG:4326"
    )

# --- Converte todos os seus DataFrames em GeoDataFrames ---
gdf_hospitais = df_para_gdf(hospitais)
gdf_ubs = df_para_gdf(ubs)
gdf_dados_indigenas = df_para_gdf(dados_indigenas, lon_col='Longitude', lat_col='Latitude')
gdf_escolas_estaduais = df_para_gdf(escolas_estaduais)
gdf_barragens = df_para_gdf(barragens)
gdf_deslizamentos = df_para_gdf(df_deslizamentos, lon_col='Longitude', lat_col='Latitude')

# --- Filtra os pontos que estão dentro do polígono ---
hospitais_dentro = gdf_hospitais[gdf_hospitais.within(polygon_union)]
ubs_dentro = gdf_ubs[gdf_ubs.within(polygon_union)]
dados_indigenas_dentro = gdf_dados_indigenas[gdf_dados_indigenas.within(polygon_union)]
escolas_estaduais_dentro = gdf_escolas_estaduais[gdf_escolas_estaduais.within(polygon_union)]
barragens_dentro = gdf_barragens[gdf_barragens.within(polygon_union)]
df_deslizamentos_dentro = gdf_deslizamentos[gdf_deslizamentos.within(polygon_union)]

# Mapa base centrado no RS
m = folium.Map(location=[-30.537, -52.965], zoom_start=6, tiles="OpenStreetMap")

# Criando as camadas do mapa
layer_municipios = folium.FeatureGroup(name='Municipios')
layer_hospitais = folium.FeatureGroup(name='Hospitais')
layer_ubs = folium.FeatureGroup(name='UBS')
layer_indigena = folium.FeatureGroup(name='Território Indígena')
layer_deslizamentos = folium.FeatureGroup(name='Deslizamentos')
layer_escolas_estaduais = folium.FeatureGroup(name='Escolas Estaduais')
layer_barragens = folium.FeatureGroup(name='Barragens')
layer_alertas = folium.FeatureGroup(name='Alertas INMET')
layer_topo = folium.FeatureGroup(name='Topografia')

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
    ).add_to(layer_municipios)

except Exception as e:
    st.warning(f"Não foi possível carregar os municípios do RS: {e}")

# Adiciona hospitais
for _, row in hospitais_dentro.iterrows():
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
for _, row in ubs_dentro.iterrows():
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
for _, row in dados_indigenas_dentro.iterrows():
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        icon=folium.Icon(color="orange", icon="campground", prefix = 'fa'),
        popup=f'Aldeia: {row["Aldeia"]} - {row["Município"]}'
    ).add_to(layer_indigena)

# Adiciona deslizamentos
for _, row in df_deslizamentos_dentro.iterrows():
    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        radius=6,
        color="#8c592f",
        fill=True,
        fill_color="#8c592f",
        fill_opacity=0.7,
        popup=f'Deslizamento: {row["Magnitude_evento"]} - {row["Data Ocorrência"]}'
    ).add_to(layer_deslizamentos)

# Adiciona Escolas Estaduais
for _, row in escolas_estaduais_dentro.iterrows():
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=5,
        color="#64508C",
        #fill=True,
        #fill_color="#c90101",
        #fill_opacity=0.7,
        popup=f'Escola: {row["escola"]} - {row["municipio"]}'
    ).add_to(layer_escolas_estaduais)

# Adiciona Barragens
for _, row in barragens_dentro.iterrows():
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=5,
        color="black",
        #fill=True,
        #fill_color="#c90101",
        #fill_opacity=0.7,
        popup=f'Barragem: {row["nm_barragem"]}, Uso:{row["uso_principal"]}  - {row["municipio"]}'
    ).add_to(layer_barragens)

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
    ).add_to(layer_alertas)



    #folium.LayerControl(collapsed=True).add_to(m)

m.add_child(layer_alertas)
m.add_child(layer_hospitais)
m.add_child(layer_ubs)
m.add_child(layer_indigena)
m.add_child(layer_deslizamentos)
m.add_child(layer_escolas_estaduais)
m.add_child(layer_barragens)


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
).add_to(layer_topo)

# Adiciona as camadas no mapa
for layer in [layer_municipios, layer_alertas, layer_hospitais, layer_ubs, layer_indigena, layer_deslizamentos, layer_escolas_estaduais, layer_barragens, layer_topo]:
    layer.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
# Exibe o mapa
with coluna_mapa:
    # Exibindo as tabelas
    # --- Cria as abas ---
    aba_mapa, aba_hospitais, aba_ubs, aba_indigenas, aba_escolas = st.tabs(['Mapa', "Hospitais", "UBS", "Aldeias Indígenas", "Escolas Estaduais"])
    
    aba_ubs.dataframe(pd.DataFrame(ubs_dentro))
    aba_hospitais.dataframe(pd.DataFrame(hospitais_dentro))
    aba_indigenas.dataframe(pd.DataFrame(dados_indigenas_dentro))
    aba_escolas.dataframe(pd.DataFrame(escolas_estaduais_dentro))
    
    with aba_mapa:
        st_data = st_folium(m, width=900, height=700, returned_objects=[])

# Exibe as métricas
with coluna_metricas:
    st.metric('UBS em área de alerta', value = len(ubs_dentro))   
    st.metric('Hospitais em área de alerta', value = len(hospitais_dentro))
    st.metric('Terras indígenas em área de alerta', value = len(dados_indigenas_dentro))
    st.metric('Histórico de deslizamentos em área de alerta', value = len(df_deslizamentos_dentro))
    st.metric('Escolas estaduais em área de alerta', value = len(escolas_estaduais_dentro))
    st.metric('Barragens em área de alerta', value = len(barragens_dentro))

# Implementação de chat
@st.fragment
def my_fragment():
        messages = st.container(height=300)
        if prompt := st.chat_input("Pergunte algo"):
            messages.chat_message("user").write(prompt)
            messages.chat_message("assistant").write(f"Echo: {prompt}")

with st.sidebar:
    my_fragment()
