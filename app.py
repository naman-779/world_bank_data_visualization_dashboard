import wbgapi as wb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output
import os
import warnings
warnings.filterwarnings('ignore')

def fetch_world_bank_data(indicators, start_year=2000, end_year=2022):
    """
    Fetch data from World Bank API for multiple indicators in a single batch
    """
    print("Fetching data from World Bank API...")
    
    data_frames = []
    
    for code, name in indicators.items():
        try:
            print(f"Fetching {name} ({code})...")
            d = wb.data.DataFrame(code, time=range(start_year, end_year + 1), labels=True).reset_index()
            
            d.columns = [c.replace('YR', '') if isinstance(c, str) and c.startswith('YR') else c for c in d.columns]
            
            id_vars = [c for c in d.columns if not str(c).isdigit()]
            value_vars = [c for c in d.columns if str(c).isdigit()]
            
            d_melted = d.melt(id_vars=id_vars, value_vars=value_vars, var_name='Year', value_name=name)
            d_melted['Year'] = d_melted['Year'].astype(int)
            
            if 'economy' not in d_melted.columns:
                print(f"Warning: 'economy' column missing for {name}, skipping.")
                continue
            
            if not data_frames:
                data_frames.append(d_melted)
            else:
                subset = d_melted[['economy', 'Year', name]]
                data_frames[0] = pd.merge(data_frames[0], subset, on=['economy', 'Year'], how='outer')

        except Exception as e:
            print(f"Error fetching {name} ({code}): {e}")
            print(f"Attempting year-by-year fallback for {name}...")
            
            yearly_frames = []
            for year in range(start_year, end_year + 1):
                try:
                    d_year = wb.data.DataFrame(code, time=year, labels=True).reset_index()
                    
                    d_year.columns = [c.replace('YR', '') if isinstance(c, str) and c.startswith('YR') else c for c in d_year.columns]
                    
                    id_vars = [c for c in d_year.columns if not str(c).isdigit()]
                    value_vars = [c for c in d_year.columns if str(c).isdigit()]
                    
                    d_melted = d_year.melt(id_vars=id_vars, value_vars=value_vars, var_name='Year', value_name=name)
                    d_melted['Year'] = d_melted['Year'].astype(int)
                    
                    if 'economy' in d_melted.columns:
                        yearly_frames.append(d_melted)
                        
                except Exception as ye:
                    pass
            
            if yearly_frames:
                print(f"Successfully fetched {len(yearly_frames)} years for {name} via fallback.")
                combined_year_df = pd.concat(yearly_frames, ignore_index=True)
                
                subset = combined_year_df[['economy', 'Year', name]]
                
                if not data_frames:
                    data_frames.append(combined_year_df)
                else:
                    data_frames[0] = pd.merge(data_frames[0], subset, on=['economy', 'Year'], how='outer')
            else:
                print(f"Fallback failed for {name}. Skipping.")
                continue
            
    if not data_frames:
        return pd.DataFrame()
        
    return data_frames[0]


def get_country_codes():
    """Get country name to ISO code mapping"""
    try:
        countries = wb.economy.DataFrame()
        country_map = dict(zip(countries['name'], countries.index))
        return country_map
    except:
        return {}


INDICATORS = {
    'NY.GDP.PCAP.CD': 'GDP per Capita',
    'SP.POP.TOTL': 'Population',
    'SP.DYN.LE00.IN': 'Life Expectancy',
    'SE.XPD.TOTL.GD.ZS': 'Education Expenditure (% GDP)',
    'SH.XPD.CHEX.GD.ZS': 'Health Expenditure (% GDP)',
    'NY.GDP.MKTP.KD.ZG': 'GDP Growth Rate',
}

CACHE_FILE = 'world_bank_data_v3.csv'

if os.path.exists(CACHE_FILE):
    print(f"Loading data from cache ({CACHE_FILE})...")
    df = pd.read_csv(CACHE_FILE)
else:
    df = fetch_world_bank_data(INDICATORS, start_year=2010, end_year=2022)
    if not df.empty:
        print(f"Saving data to cache ({CACHE_FILE})...")
        df.to_csv(CACHE_FILE, index=False)

if df.empty:
    print("Failed to fetch data. Please check your internet connection or indicator codes.")
    exit(1)

try:
    countries_metadata = wb.economy.DataFrame(skipAggs=True)
    valid_economies = set(countries_metadata.index)
    
    if 'region' in countries_metadata.columns:
        country_to_region_code = countries_metadata['region'].to_dict()
    else:
        country_to_region_code = {}

    try:
        regions_metadata = wb.region.DataFrame()
        region_code_to_name = regions_metadata['name'].to_dict()
    except:
        region_code_to_name = {}
        
    if 'name' in countries_metadata.columns:
        country_to_name = countries_metadata['name'].to_dict()
    else:
        country_to_name = {}
        
except:
    valid_economies = set(df['economy'].unique())
    country_to_region_code = {}
    region_code_to_name = {}
    country_to_name = {}

df['iso_alpha'] = df['economy']

df['Region_Code'] = df['economy'].map(country_to_region_code)
df['Region'] = df['Region_Code'].map(region_code_to_name)
df['Region'] = df['Region'].fillna(df['Region_Code'])

df['Country Name'] = df['economy'].map(country_to_name)

df['Country Name'] = df['Country Name'].fillna(df['economy'])

df_countries = df[df['economy'].isin(valid_economies)].copy()

if df_countries.empty:
    print("Warning: No valid country data found after filtering aggregates. Using raw data.")
    df_countries = df.copy()

df_countries = df_countries.fillna(method='ffill').fillna(method='bfill')

df_countries['GDP Category'] = pd.cut(
    df_countries['GDP per Capita'], 
    bins=[0, 1000, 5000, 15000, 50000, float('inf')],
    labels=['Low Income', 'Lower Middle', 'Upper Middle', 'High Income', 'Very High Income']
)

latest_year = df_countries['Year'].max()

app = dash.Dash(__name__)
server = app.server

colors = {
    'background': '#0f172a',
    'text': '#e2e8f0',
    'primary': '#3b82f6',
    'secondary': '#8b5cf6'
}

app.layout = html.Div(style={'backgroundColor': colors['background'], 'height': '100vh', 'padding': '10px', 'boxSizing': 'border-box', 'display': 'flex', 'flexDirection': 'column'}, children=[
    
    html.Div([
        html.Div([
            html.H1('World Bank Dashboard', style={'color': colors['text'], 'fontSize': '24px', 'margin': '0', 'whiteSpace': 'nowrap'}),
            
            html.Div([
                html.Label(f'Year: ', style={'color': colors['text'], 'fontWeight': 'bold', 'marginRight': '10px', 'marginLeft': '20px'}),
                html.Div([
                    dcc.Slider(
                        id='year-slider',
                        min=int(df_countries['Year'].min()),
                        max=int(df_countries['Year'].max()),
                        value=latest_year,
                        marks={str(year): str(year) for year in range(int(df_countries['Year'].min()), int(df_countries['Year'].max()) + 1, 4)},
                        step=1
                    )
                ], style={'width': '300px'}) 
            ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '20px'})
        ], style={'display': 'flex', 'alignItems': 'center'}),
        
        html.Div([
            html.Div([
                html.Label('Country: ', style={'color': colors['text'], 'fontWeight': 'bold', 'marginRight': '5px'}),
                dcc.Dropdown(
                    id='country-filter',
                    options=[{'label': c, 'value': c} for c in sorted(df_countries['Country Name'].unique())],
                    placeholder="All Countries",
                    style={'width': '200px', 'color': '#000'}
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '20px'}),

            html.Div([
                html.Label('Indicator: ', style={'color': colors['text'], 'fontWeight': 'bold', 'marginRight': '5px'}),
                dcc.Dropdown(
                    id='map-indicator',
                    options=[{'label': v, 'value': k} for k, v in INDICATORS.items()],
                    value='NY.GDP.PCAP.CD',
                    style={'width': '250px', 'color': '#000'} 
                ),
            ], style={'display': 'flex', 'alignItems': 'center'}),
            
        ], style={'display': 'flex', 'alignItems': 'center'}),
        
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'marginBottom': '10px', 'flex': '0 0 auto'}),
    
    html.Div([
        html.Div([dcc.Graph(id='world-map', style={'height': '100%'})], style={'flex': '1', 'marginRight': '10px'}),
        
        html.Div([dcc.Graph(id='bubble-chart', style={'height': '100%'})], style={'flex': '0 0 35%'})
        
    ], style={'display': 'flex', 'flex': '0 0 50%', 'marginBottom': '10px'}),
    
    html.Div([
        html.Div([dcc.Graph(id='time-series', style={'height': '100%'})], style={'flex': '1', 'marginRight': '10px'}),
        
        html.Div([dcc.Graph(id='correlation-scatter', style={'height': '100%'})], style={'flex': '1', 'marginRight': '10px'}),
        
        html.Div([dcc.Graph(id='regional-comparison', style={'height': '100%'})], style={'flex': '1'})
        
    ], style={'display': 'flex', 'flex': '0 0 40%'}),
    
    html.Div([
        html.P('Data Source: World Bank', style={'textAlign': 'center', 'color': colors['text'], 'margin': '5px', 'fontSize': '12px', 'opacity': '0.7'})
    ], style={'flex': '0 0 auto'})
])

@app.callback(
    [Output('world-map', 'figure'),
     Output('time-series', 'figure'),
     Output('bubble-chart', 'figure'),
     Output('correlation-scatter', 'figure'),
     Output('regional-comparison', 'figure')],
    [Input('map-indicator', 'value'),
     Input('year-slider', 'value'),
     Input('country-filter', 'value')]
)
def update_dashboard(selected_indicator, selected_year, selected_country):
    """Update all visualizations based on user selections"""
    
    indicator_name = INDICATORS[selected_indicator]
    
    df_year = df_countries[df_countries['Year'] == selected_year].copy()
    
    if selected_country:
        df_year = df_year[df_year['Country Name'] == selected_country]
    
    fig_map = px.choropleth(
        df_year,
        locations='iso_alpha',
        color=indicator_name,
        hover_name='Country Name', 
        hover_data={
            'iso_alpha': False,
            'Region': True, 
            indicator_name: ':.2f',
            'GDP per Capita': ':.0f',
            'Population': ':.0f',
            'Life Expectancy': ':.1f'
        },
        color_continuous_scale='Plasma',
        title=f'{indicator_name} by Country ({selected_year})',
    )
    
    fig_map.update_layout(
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        font_color=colors['text'],
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type='natural earth',
            bgcolor=colors['background']
        ),
        margin=dict(l=0, r=0, t=30, b=0), 
        title_font_size=16
    )
    
    if selected_country:
         df_top10 = df_countries[(df_countries['Country Name'] == selected_country) & (df_countries[indicator_name].notna())].sort_values('Year')
         ts_title = f'Trend: {selected_country} ({indicator_name})'
    else:
        top_countries = df_year.nlargest(10, indicator_name)['economy'].tolist()
        df_top10 = df_countries[df_countries['economy'].isin(top_countries)].sort_values('Year')
        ts_title = f'Trend: Top 10 Countries ({indicator_name})'
    
    fig_ts = px.line(
        df_top10,
        x='Year',
        y=indicator_name,
        color='Country Name', 
        hover_data=['Region'], 
        title=ts_title,
        markers=True
    )
    
    fig_ts.update_layout(
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        font_color=colors['text'],
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        legend=dict(orientation='v', x=1.02, y=1)
    )
    
    fig_bubble = px.scatter(
        df_year.dropna(subset=['GDP per Capita', 'Life Expectancy', 'Population']),
        x='GDP per Capita',
        y='Life Expectancy',
        size='Population',
        color='GDP Category',
        hover_name='Country Name', 
        hover_data=['Region'], 
        log_x=True,
        size_max=60,
        title=f'GDP per Capita vs Life Expectancy ({selected_year})',
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    
    fig_bubble.update_layout(
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        font_color=colors['text'],
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
    )
    
    top_20 = df_year.nlargest(20, indicator_name).sort_values(indicator_name, ascending=True)
    
    fig_corr = px.bar(
        top_20,
        x=indicator_name,
        y='Country Name', 
        orientation='h',
        title=f'Top 20 Countries: {indicator_name} ({selected_year})',
        text=indicator_name,
        hover_data=['Region'],
        color='Region' if 'Region' in df_year.columns else indicator_name,
        color_discrete_sequence=px.colors.qualitative.Prism
    )
    
    fig_corr.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    fig_corr.update_layout(
        plot_bgcolor=colors['background'],
        paper_bgcolor=colors['background'],
        font_color=colors['text'],
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(title='Country'), 
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis_tickfont=dict(size=10)
    )
    
    if 'Region' in df_year.columns and df_year['Region'].notna().any():
        fig_regional = px.box(
            df_year,
            x='Region',
            y=indicator_name,
            color='Region',
            points='all', 
            hover_name='Country Name', 
            title=f'{indicator_name} Distribution by Region ({selected_year})'
        )
        
        fig_regional.update_layout(
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            font_color=colors['text'],
            xaxis=dict(showgrid=False, title='Region'),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            xaxis_tickangle=-45,
            showlegend=False
        )
    else:
        fig_regional = go.Figure()
        fig_regional.update_layout(
            title="Region Data Unavailable",
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            font_color=colors['text']
        )
    
    return fig_map, fig_ts, fig_bubble, fig_corr, fig_regional


if __name__ == '__main__':
    print("WORLD BANK DASHBOARD")
    print(f"Data loaded: {len(df_countries)} country-year observations")
    print(f"Year range: {df_countries['Year'].min()} - {df_countries['Year'].max()}")
    print(f"Indicators: {len(INDICATORS)}")
    if 'Region' in df_countries.columns:
        print(f"Regions loaded: {df_countries['Region'].nunique()}")
    print("Starting dashboard server...")
    app.run(debug=False)