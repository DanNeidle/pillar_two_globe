import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import os
from pathlib import Path
import imageio
from PIL import Image
import io
import numpy as np

# dataset = "CRS"
# dataset = "PillarTwo"
dataset = "WealthTax"

make_gif = False
gif_frames = 120
geo_resolution = 110 # high res is 110,  # or 50 for low res



dataset_info = {
    "CRS": {
        "categories": {
            None: {
                'color': "#DDDDDD",
                'description': 'Not committed'
            },
            2017: {'color': 'lightgreen', 
                'description': 'Exchanged from 2017'
            },
            2018: {'color': 'palegreen', 
                'description': 'Exchanged from 2018'
            },
            2019: {'color': 'lime', 
                'description': 'Exchanged from 2019'
            },
            2020: {'color': 'limegreen', 
                'description': 'Exchanged from 2020'
            },
            2021: {'color': 'forestgreen', 
                'description': 'Exchanged from 2021'
            },
            2022: {'color': 'green', 
                'description': 'Exchanged from 2022'
            },
            2023: {'color': 'mediumorchid', 
                'description': 'Exchanging from 2023'
            },
            2024: {'color': 'orchid', 
                'description': 'Exchanging from 2024'
            },
            2025: {'color': 'purple', 
                'description': 'Exchanging from 2025'
            },
            2026: {'color': 'indigo', 
                'description': 'Exchanging from 2026'
            },
        }, 
        "column": 'CRS commitment year',
        "default_color": "#DDDDDD"
    },
    
    "PillarTwo": {
        "categories": {
            None: {
                'color': "#DDDDDD",
                'description': 'Not participating'
            },
            "EU": {
                'color': '#588B8B', 
                'description': 'EU implementation in progress'
            }, # DarkGreen
            "implementing": {
                'color': '#588B8B', 
                'description': 'Implementation in progress'
            }, # Green
            "progressing": {
                'color': '#F28F3B', 
                'description': 'Implementation discussions in progress'
            }, # LightGreen
            "ATAF": {
                'color': '#C8553D', 
                'description': 'African Tax Administration Forum planning implementation'
            }, # Orange
            "unique": {
                'color': '#FFD5C2', 
                'description': 'Planning unique/unclear implementation'
            }, # DarkOrchid
            "signatory": {
                'color': '#BBD686', 
                'description': 'Signatory to OECD statement'
            }, # Honeydew
        },
        "column": 'Pillar Two',
        "default_color": "#DDDDDD"
    },
    
    "WealthTax": {
        "categories": {
            "OECD": {
                'color': '#F24C3D', 
                'description': 'Wealth tax (OECD country)'
            },
            "Developing": {
                'color': '#D7C0AE', 
                'description': 'Wealth tax (developing country)'
            },
            None: {
                'color': "#9BABB8",
                'description': 'No wealth tax'
            }
        },
        "column": 'Wealth tax',
        "default_color": "#9BABB8"
    }
}


initial_countries = {}
all_countries = {}

# Load GeoDataFrame containing shapes of all countries
world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
world = world.dissolve(by='name').reset_index()

# more detailed sub-country units for fallback, stripping out china regions before dissolve
# data from https://www.naturalearthdata.com/downloads/110m-cultural-vectors/
world_additional = gpd.read_file('map_units/ne_10m_admin_0_map_units.shp')
china_regions = world_additional[world_additional['SOVEREIGNT'] == 'China']
world_additional = world_additional.dissolve(by='SOVEREIGNT').reset_index()

# directory with small island data, loaded individually from https://gadm.org/download_country.html (complete database is too large)
island_dir = Path('map_islands')

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    rgba = f"rgba{rgb + (alpha,)}"
    return rgba


def add_country_to_dict(country, iso_a3, name, all_countries, initial=False):
    if initial:
        initial_countries[iso_a3] = True
    
    if country['geometry'].geom_type == 'Polygon':
        lon = list(country['geometry'].exterior.coords.xy[0])
        lat = list(country['geometry'].exterior.coords.xy[1])
        all_countries[iso_a3] = {
            'name': name, 
            'shape_data': [(lon, lat)], 
            'color': hex_to_rgba(dataset_info[dataset]['default_color'], 10),
            'dataset_specific_data': None
        }
    elif country['geometry'].geom_type == 'MultiPolygon':
        shape_data = []
        for polygon in country['geometry'].geoms:
            lon = list(polygon.exterior.coords.xy[0])
            lat = list(polygon.exterior.coords.xy[1])
            shape_data.append((lon, lat))

        all_countries[iso_a3] = {
            'name': name, 
            'shape_data': shape_data, 
            'color': hex_to_rgba(dataset_info[dataset]['default_color'], 10),
            'dataset_specific_data': None
        }

# used for stripping out Macau and HKG
def update_country_geometry(region_data, region_code, region_name, all_countries):
    if not region_data.empty:
        region_geo = region_data.iloc[0]['geometry']
        all_countries[region_code] = {'name': region_name,
                                      'shape_data': [],
                                      'color': hex_to_rgba(dataset_info[dataset]['default_color'], 10),
                                      'dataset_specific_data': None}
        polygons = [region_geo] if region_geo.geom_type == 'Polygon' else region_geo.geoms
        for polygon in polygons:
            lon = list(polygon.exterior.coords.xy[0])
            lat = list(polygon.exterior.coords.xy[1])
            all_countries[region_code]['shape_data'].append((lon, lat))

def populate_countries():
    for _, country in world.iterrows():
        add_country_to_dict(country, country['iso_a3'], country["name"], all_countries, initial=True)

    # Add fallback countries
    for _, country in world_additional.iterrows():
        if country['ISO_A3'] in initial_countries:
            continue
        add_country_to_dict(country, country['ISO_A3'], country['SOVEREIGNT'], all_countries)

    # Add islands
    island_files = [file for file in os.listdir(island_dir) if file.endswith('.gpkg')]
    for file in island_files:
        island_world = gpd.read_file(island_dir / file)
        island_world = island_world.dissolve(by='COUNTRY').reset_index()
        for _, country in island_world.iterrows():
            if country['GID_0'] in all_countries:
                continue
            add_country_to_dict(country, country['GID_0'], country['COUNTRY'], all_countries)

    # fix china
    update_country_geometry(china_regions, 'CHN', 'China', all_countries)

    # Add Hong Kong as a separate entry
    hong_kong = china_regions[china_regions['ADMIN'] == 'Hong Kong S.A.R.']
    update_country_geometry(hong_kong, 'HKG', 'Hong Kong', all_countries)

    # Add Macau as a separate entry
    macau = china_regions[china_regions['ADMIN'] == 'Macao S.A.R']
    update_country_geometry(macau, 'MAC', 'Macau', all_countries)
    


def process_excel_data(dataset):
    
    # Process data from Excel file
    perfect_run = True
    df = pd.read_excel('tax_globe_data.xlsx')
    for _, row in df.iterrows():
        iso = row['ISO']
        if iso in all_countries:
            if pd.isnull(row[dataset_info[dataset]['column']]):
                # print(f"Found {row['Jurisdiction']} ({iso}): no data on {dataset}")
                pass
            else:
                
                relevant_data = row[dataset_info[dataset]['column']]
                all_countries[iso]['color'] = dataset_info[dataset]['categories'][relevant_data]['color']
                all_countries[iso]['dataset_specific_data'] = relevant_data
            # print(f"Found {row['Jurisdiction']} ({iso}): {commitment_year}")

        else:
            print(f"WARNING: cannot find {row['Jurisdiction']} ({iso})")
            perfect_run = False

    if perfect_run:
        print(f"Successfully found all {len(df)} jurisdictions")

# have to manually make a legend because the standard legend doesn't work well with geoplots
def create_legend():
    
    # Define start position for the legend items
    legend_x_start = 0.75
    legend_y_start = 0.95
    # Define the gap between legend items
    legend_y_gap = 0.03
    
    # gap between color and text
    text_gap = 0.02  
    
    # color box size
    color_box_size = 0.015

    # Define the position of color box relative to the legend text
    color_box_position = 0.93

    annotations = []
    shapes = []


    # Create legend items
    
    for i, item in enumerate(dataset_info[dataset]["categories"].items()):
        key, value = item
        
        # text
        annotations.append(dict(xref='paper', x=legend_x_start + text_gap, y=legend_y_start-i*legend_y_gap,
                                xanchor='left', yanchor='middle',
                                text=value['description'],
                                font=dict(family='Arial',
                                        size=14,
                                        color='white'),
                                showarrow=False))

        # colors
        shapes.append(dict(type="rect",
                        xref="paper", yref="paper",
                        x0=legend_x_start, y0=legend_y_start-i*legend_y_gap + 0.010,
                        x1=legend_x_start + color_box_size, y1=legend_y_start-i*legend_y_gap - 0.01,
                        line=dict(color='white', width=1),
                        fillcolor=value['color']))
        
    return annotations, shapes

def create_globe():

    # Create Plotly figure
    fig = go.Figure()

    # for country_info in all_countries.values():
        
    for i, item in enumerate(all_countries.items()):
        key, country_info = item
        
        if key == "GUF":
            # some weird bug with French Guiana which I can't be bothered to fix
            continue
        
        hover_text = f"{country_info['name']}: " + dataset_info[dataset]['categories'][country_info['dataset_specific_data']]['description']
        
        for coords in country_info['shape_data']:
            
            
            
            fig.add_trace(go.Scattergeo(lon=coords[0], lat=coords[1],
                                        mode='lines',
                                        line=dict(width=1, color='black'),
                                        hoverinfo='text',
                                        hovertext=hover_text,
                                        fill='toself',
                                        fillcolor=country_info['color'],
                                        showlegend=False))

    fig.update_geos(
        showcountries=True,
        showcoastlines=True,
        showland=True,
        showocean=True,
        resolution=geo_resolution,
        landcolor='rgb(204, 204, 204)',
        oceancolor='rgb(0, 119, 190)',
        coastlinecolor='rgb(173, 216, 230)',
        coastlinewidth=5,
        lakecolor='rgb(0, 119, 190)',
        countrycolor=hex_to_rgba(dataset_info[dataset]['default_color'], 10),
        projection_type="orthographic",
    )

    fig.update_layout(
        geo=dict(bgcolor='white' if make_gif else 'black'),
        paper_bgcolor='white' if make_gif else 'black',
        plot_bgcolor='white' if make_gif else 'black',
        autosize=True,
        margin=dict(l=20, r=20, b=20, t=20, pad=0),
    )
    
    # add legend if we're not making a gif
    
    if not make_gif:
        annotations, shapes = create_legend()
        fig.update_layout(annotations=annotations,
                        shapes=shapes)

    return fig


def create_gif(filename):
        
    # Set the animation frame duration
    frame_duration = 0.1  # in seconds

    gif_writer = imageio.get_writer(filename, mode='I', duration=frame_duration, loop=0)


    # Generate frames for the rotation animation
    for i in range(gif_frames):
        # lat 51.5 is greenwich
        crs_fig.update_geos(
            projection_rotation=dict(lon=180 * ((i / gif_frames * 2) % 2 - 1), lat=0, roll=0), 
        )
        # Convert the figure to an image
        img_bytes = crs_fig.to_image(format="png", width=800, height=600)
        img = Image.open(io.BytesIO(img_bytes))
        # Append the image to the GIF
        gif_writer.append_data(np.array(img))
        print(f"Done frame {i + 1}/{gif_frames}")

    gif_writer.close()

print(f"Starting to create country dict")

# Create a dictionary of all countries with their ISO, name, shape data, and color
populate_countries()
print(f"merging with {dataset} dataset")
# process excel CIS data
process_excel_data(dataset)

# create a globe with data
crs_fig = create_globe()

if make_gif:
    create_gif(dataset + "_globe.gif")
else:
    crs_fig.show()
