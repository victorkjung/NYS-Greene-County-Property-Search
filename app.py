"""
Lanesville Property Finder - OnXHunt-style Property Owner Identification
A Streamlit application for exploring tax parcels and property ownership in Lanesville, NY
"""

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import json
from pathlib import Path
import random
import html
from sklearn.neighbors import NearestNeighbors
import requests
import hashlib
import os

from constants import PROPERTY_CLASS_DESC, CLASS_COLORS
from ui import apply_base_styles

# Page configuration
st.set_page_config(
    page_title="Lanesville Property Finder",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_base_styles("""
    /* Sidebar styling */
    [data-testid=\"stSidebar\"] {
        background-color: #16213e;
        border-right: 2px solid #e94560;
    }
    
    [data-testid=\"stSidebar\"] .stMarkdown {
        color: #eaeaea;
    }
    
    /* Property card styling */
    .property-card {
        background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
        border: 1px solid #e94560;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 4px 15px rgba(233, 69, 96, 0.2);
    }
    
    .property-card h4 {
        color: #e94560;
        margin-bottom: 10px;
    }
    
    .property-card p {
        color: #eaeaea;
        margin: 5px 0;
    }
    
    /* Stats boxes */
    .stat-box {
        background: #16213e;
        border: 1px solid #0f3460;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        margin: 5px;
    }
    
    .stat-box h3 {
        color: #e94560 !important;
        font-size: 28px;
        margin: 0;
    }
    
    .stat-box p {
        color: #eaeaea;
        font-size: 12px;
        margin: 5px 0 0 0;
    }
    
    /* Search input styling */
    .stTextInput input {
        background-color: #16213e;
        color: #eaeaea;
        border: 1px solid #0f3460;
        border-radius: 8px;
    }
    
    .stTextInput input:focus {
        border-color: #e94560;
        box-shadow: 0 0 10px rgba(233, 69, 96, 0.3);
    }
    
    /* Button styling */
    .stButton button {
        background: linear-gradient(135deg, #e94560 0%, #0f3460 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(233, 69, 96, 0.4);
    }
    
    /* Metrics styling */
    [data-testid=\"stMetricValue\"] {
        color: #e94560;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #16213e;
        border-radius: 8px;
    }
    
    /* Legend styling */
    .legend-item {
        display: flex;
        align-items: center;
        margin: 5px 0;
    }
    
    .legend-color {
        width: 20px;
        height: 20px;
        border-radius: 4px;
        margin-right: 10px;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: #666;
        padding: 20px;
        font-size: 12px;
    }
""")


@st.cache_data
def load_parcel_data(num_parcels: int = 500, seed: int | None = None):
    """Load parcel data from cache file or generate sample data for Lanesville, NY
    
    Priority:
    1. Load from cached real NYS data (data/lanesville_parcels.json)
    2. Generate sample data if no cache exists
    
    Args:
        num_parcels: Number of sample parcels to generate if no data file exists
    """
    data_file = Path("data/lanesville_parcels.json")
    geojson_file = Path("data/Greene_County_Tax_Parcels_-8841005964405968865.geojson")
    use_geojson = True
    config_file = Path("data/config.json")
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                cfg = json.load(f)
            use_geojson = bool(cfg.get("use_geojson", True))
        except Exception:
            use_geojson = True
    
    # Prefer GeoJSON if enabled
    if use_geojson and geojson_file.exists():
        try:
            with open(geojson_file, "r") as f:
                data = json.load(f)
            df = geojson_to_df(data)
            if df is not None and len(df) > 0:
                return df
        except Exception as e:
            print(f"Error loading GeoJSON data: {e}")
    
    # Try to load real data first
    if data_file.exists():
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            
            # Validate required columns exist
            required_cols = ['latitude', 'longitude', 'owner', 'parcel_id']
            if all(col in df.columns for col in required_cols):
                # Clean up any NaN values in critical columns
                df = df.dropna(subset=['latitude', 'longitude'])
                
                # Ensure coordinates column exists
                if 'coordinates' not in df.columns:
                    df['coordinates'] = df.apply(
                        lambda r: [[r['latitude'], r['longitude']]] if pd.notna(r['latitude']) else [],
                        axis=1
                    )
                
                # Ensure all required columns have values
                df['owner'] = df['owner'].fillna('Unknown')
                df['acreage'] = pd.to_numeric(df['acreage'], errors='coerce').fillna(0)
                df['assessed_value'] = pd.to_numeric(df['assessed_value'], errors='coerce').fillna(0)
                df['property_class'] = df['property_class'].fillna('999').astype(str)
                df['property_class_desc'] = df['property_class_desc'].fillna('Unknown')
                df['mailing_zip'] = df['mailing_zip'].fillna('').astype(str)
                df['annual_taxes'] = df.get('annual_taxes', df['assessed_value'] * 0.025)
                
                if len(df) > 0:
                    return df
        except Exception as e:
            print(f"Error loading cached data: {e}")
    
    # Fall back to sample data generation
    return generate_sample_data(num_parcels, seed=seed)


def geojson_to_df(data: dict) -> pd.DataFrame | None:
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        return None
    records = []
    for feature in data.get("features", []):
        props = feature.get("properties", {}) or {}
        geom = feature.get("geometry", {}) or {}
        coords = []
        lat = None
        lon = None
        if geom.get("type") == "Polygon":
            ring = (geom.get("coordinates") or [[]])[0]
            coords = [[c[1], c[0]] for c in ring[:100]] if ring else []
        elif geom.get("type") == "MultiPolygon":
            ring = (geom.get("coordinates") or [[[]]])[0][0]
            coords = [[c[1], c[0]] for c in ring[:100]] if ring else []
        if coords:
            lats = [c[0] for c in coords]
            lons = [c[1] for c in coords]
            lat = sum(lats) / len(lats)
            lon = sum(lons) / len(lons)
        record = {
            "parcel_id": props.get("parcel_id") or props.get("PRINT_KEY") or props.get("SBL") or props.get("PARCEL_ID") or "",
            "sbl": props.get("sbl") or props.get("SBL") or "",
            "owner": props.get("owner") or props.get("OWNER") or props.get("OWNER_NAME") or "Unknown",
            "mailing_address": props.get("mailing_address") or props.get("MAIL_ADDR") or "",
            "mailing_city": props.get("mailing_city") or props.get("MAIL_CITY") or "",
            "mailing_state": props.get("mailing_state") or props.get("MAIL_STATE") or "NY",
            "mailing_zip": str(props.get("mailing_zip") or props.get("MAIL_ZIP") or ""),
            "property_class": str(props.get("property_class") or props.get("PROP_CLASS") or ""),
            "property_class_desc": props.get("property_class_desc") or props.get("CLASS_DESC") or "Unknown",
            "acreage": float(props.get("acreage") or props.get("CALC_ACRES") or props.get("ACRES") or 0),
            "assessed_value": int(props.get("assessed_value") or props.get("TOTAL_AV") or 0),
            "land_value": int(props.get("land_value") or props.get("LAND_AV") or 0),
            "improvement_value": int(props.get("improvement_value") or 0),
            "tax_year": int(props.get("tax_year") or 2024),
            "annual_taxes": float(props.get("annual_taxes") or 0),
            "school_district": props.get("school_district") or props.get("SCHOOL_NAME") or "",
            "municipality": props.get("municipality") or props.get("MUNI_NAME") or "",
            "county": props.get("county") or "Greene",
            "latitude": lat,
            "longitude": lon,
            "coordinates": coords,
            "deed_book": str(props.get("deed_book") or props.get("DEED_BOOK") or ""),
            "deed_page": str(props.get("deed_page") or props.get("DEED_PAGE") or ""),
            "last_sale_date": props.get("last_sale_date") or props.get("SALE_DATE") or "",
            "last_sale_price": props.get("last_sale_price") or props.get("SALE_PRICE") or None
        }
        records.append(record)
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.dropna(subset=["latitude", "longitude"])
    df["property_class_desc"] = df["property_class_desc"].fillna("Unknown")
    df["owner"] = df["owner"].fillna("Unknown")
    df["annual_taxes"] = df["annual_taxes"].fillna(df["assessed_value"] * 0.025)
    return df


def generate_sample_data(num_parcels: int = 500, seed: int | None = None) -> pd.DataFrame:
    """Generate sample parcel data for demonstration
    
    Args:
        num_parcels: Number of sample parcels to generate
    """
    # Lanesville is located approximately at 42.1856° N, 74.2848° W
    # These are representative sample parcels - replace with real data
    
    rng = random.Random(seed)
    
    sample_owners = [
        "Johnson Family Trust", "Smith, Robert & Mary", "Mountain View LLC",
        "Catskill Properties Inc", "Williams, Thomas", "NYS DEC",
        "Greene County", "Hunter Mountain Resort", "Davis, Jennifer",
        "Anderson, Michael", "NYC DEP", "Lanesville Community Church",
        "Miller, David & Susan", "Brown Estate", "Taylor, Christopher",
        "Wilson Holdings LLC", "Martinez, Carlos", "Thompson, Patricia",
        "Garcia, Maria", "Robinson, James", "Clark, William",
        "Lewis, Barbara", "Lee, Richard", "Walker, Karen",
        "Hall, Steven", "Allen, Michelle", "Young, Daniel",
        "King, Elizabeth", "Wright, Joseph", "Hill, Nancy",
        "Scott, Kenneth", "Adams, Margaret", "Baker, George",
        "Nelson, Sandra", "Carter, Ronald", "Mitchell, Dorothy",
        "Perez, Anthony", "Roberts, Lisa", "Turner, Mark",
        "Phillips, Betty", "Campbell, Edward", "Parker, Helen",
        "Evans, Frank", "Edwards, Sharon", "Collins, Raymond",
        "Stewart, Donna", "Sanchez, Jack", "Morris, Carol",
        "Rogers, Larry", "Reed, Judith", "Cook, Gary",
        "Morgan, Ann", "Bell, Gerald", "Murphy, Diane",
        "Bailey, Roger", "Rivera, Deborah", "Cooper, Joe",
        "Richardson, Jane", "Cox, Albert", "Howard, Frances",
        "Ward, Russell", "Torres, Kathryn", "Peterson, Johnny",
        "Gray, Martha", "Ramirez, Henry", "James, Gloria",
        "Watson, Philip", "Brooks, Teresa", "Kelly, Jerry",
        "Sanders, Evelyn", "Price, Eugene", "Bennett, Cheryl",
        "Catskill Land Trust", "Mountain Heritage Foundation",
        "Windham Properties LLC", "Hudson Valley Homes Inc",
        "Greenwood Estates", "Kaaterskill Associates",
        "Tannersville Development Corp", "Hunter Valley LLC"
    ]
    
    property_classes = {k: v for k, v in PROPERTY_CLASS_DESC.items() if k in {
        "210", "220", "240", "260", "270", "280", "311", "312", "322",
        "910", "920", "930", "940", "105", "112", "117", "120", "421",
        "485", "582", "620", "651"
    }}
    
    # Zip codes in the coverage area
    local_zips = ["12450", "12442", "12485", "12434", "12424", "12439", "12468"]
    nonlocal_zips = ["10001", "10011", "10023", "10028", "11201", "11215", "11238", "12414"]
    
    # Generate sample parcels across a wider area (Lanesville and surrounding)
    parcels = []
    base_lat = 42.1856
    base_lon = -74.2848
    
    # Create a grid-like distribution with some randomness
    for i in range(num_parcels):
        # Distribute parcels across a larger area
        lat_offset = rng.uniform(-0.05, 0.05)
        lon_offset = rng.uniform(-0.07, 0.07)
        
        prop_class = rng.choice(list(property_classes.keys()))
        acreage = round(rng.uniform(0.5, 50.0), 2)
        
        # Adjust acreage based on property class
        if prop_class in ["322", "910", "920", "930", "940"]:
            acreage = round(rng.uniform(20.0, 200.0), 2)
        elif prop_class in ["311", "312"]:
            acreage = round(rng.uniform(0.5, 15.0), 2)
        
        assessed_value = int(acreage * rng.uniform(5000, 25000))
        if prop_class in ["210", "220", "240", "260"]:
            assessed_value += rng.randint(80000, 350000)
        
        # Generate parcel polygon (simplified rectangle)
        size_factor = min(acreage * 0.0001, 0.005)  # Cap size for display
        coords = [
            [base_lat + lat_offset, base_lon + lon_offset],
            [base_lat + lat_offset + size_factor, base_lon + lon_offset],
            [base_lat + lat_offset + size_factor, base_lon + lon_offset + size_factor * 1.5],
            [base_lat + lat_offset, base_lon + lon_offset + size_factor * 1.5],
        ]
        
        # Assign zip code - 70% local, 30% non-local
        if rng.random() > 0.3:
            mailing_zip = rng.choice(local_zips)
            mailing_city = rng.choice(["Lanesville", "Hunter", "Tannersville", "Haines Falls", "Jewett"])
        else:
            mailing_zip = rng.choice(nonlocal_zips)
            mailing_city = rng.choice(["New York", "Brooklyn", "Catskill"])
        
        # Street names (defined outside f-string to avoid escape issues)
        street_names = [
            'Main St', 'Mountain Rd', 'Route 214', 'Spruceton Rd', 'Notch Rd', 
            'Hollow Rd', 'Creek Rd', 'State Route 23A', 'Platte Clove Rd', 
            'Bloomer Rd', 'Clum Hill Rd', 'Devils Tombstone Rd'
        ]
        
        parcel = {
            "parcel_id": f"86.{rng.randint(1,25)}-{rng.randint(1,60)}-{rng.randint(1,99)}",
            "sbl": f"86.00-{rng.randint(1,9)}-{rng.randint(1,99)}.{rng.randint(0,999):03d}",
            "owner": rng.choice(sample_owners),
            "mailing_address": f"{rng.randint(1, 999)} {rng.choice(street_names)}",
            "mailing_city": mailing_city,
            "mailing_state": "NY",
            "mailing_zip": mailing_zip,
            "property_class": prop_class,
            "property_class_desc": property_classes[prop_class],
            "acreage": acreage,
            "assessed_value": assessed_value,
            "land_value": int(assessed_value * rng.uniform(0.2, 0.5)),
            "improvement_value": int(assessed_value * rng.uniform(0.5, 0.8)),
            "tax_year": 2024,
            "annual_taxes": round(assessed_value * 0.025, 2),
            "school_district": "Hunter-Tannersville CSD",
            "municipality": "Hunter",
            "county": "Greene",
            "latitude": base_lat + lat_offset,
            "longitude": base_lon + lon_offset,
            "coordinates": coords,
            "deed_book": f"{rng.randint(100, 999)}",
            "deed_page": f"{rng.randint(1, 500)}",
            "last_sale_date": f"{rng.randint(1990, 2024)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "last_sale_price": rng.randint(50000, 500000) if rng.random() > 0.3 else None
        }
        parcels.append(parcel)
    
    return pd.DataFrame(parcels)


def get_parcel_color(property_class):
    """Return color based on property classification"""
    if not property_class:
        return "#757575"
    return CLASS_COLORS.get(str(property_class)[0], "#757575")


def _map_style(style_name: str) -> str:
    styles = {
        "satellite": "mapbox://styles/mapbox/satellite-v9",
        "topo": "mapbox://styles/mapbox/outdoors-v12",
        "streets": "mapbox://styles/mapbox/streets-v12",
        "dark": "mapbox://styles/mapbox/dark-v11",
    }
    return styles.get(style_name, styles["satellite"])


def _prepare_deck_data(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    working = working.dropna(subset=["latitude", "longitude"])
    working["owner_safe"] = working["owner"].astype(str).apply(html.escape)
    working["parcel_id_safe"] = working["parcel_id"].astype(str).apply(html.escape)
    working["property_class_desc_safe"] = working["property_class_desc"].astype(str).apply(html.escape)
    working["color"] = working["property_class"].apply(get_parcel_color)
    # Pydeck expects [lng, lat]
    working["polygon"] = working["coordinates"].apply(
        lambda coords: [[c[1], c[0]] for c in coords] if isinstance(coords, list) else []
    )
    return working


def _build_layers(df: pd.DataFrame, show_labels: bool, aggregated: bool, hex_radius_m: int) -> list:
    layers = []
    if df.empty:
        return layers

    if aggregated:
        layers.append(
            pdk.Layer(
                "HexagonLayer",
                df,
                get_position="[longitude, latitude]",
                radius=hex_radius_m,
                elevation_scale=4,
                elevation_range=[0, 1200],
                pickable=True,
                extruded=True,
                coverage=0.88,
            )
        )
    else:
        polygon_df = df[df["polygon"].apply(lambda p: isinstance(p, list) and len(p) >= 3)]
        if not polygon_df.empty:
            layers.append(
                pdk.Layer(
                    "PolygonLayer",
                    polygon_df,
                    get_polygon="polygon",
                    get_fill_color="[r, g, b]",
                    get_line_color=[233, 69, 96],
                    line_width_min_pixels=1,
                    pickable=True,
                    opacity=0.45,
                )
            )
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                df,
                get_position="[longitude, latitude]",
                get_radius=20,
                get_fill_color=[233, 69, 96],
                pickable=True,
                opacity=0.6,
            )
        )

    if show_labels and len(df) <= 1500:
        layers.append(
            pdk.Layer(
                "TextLayer",
                df,
                get_position="[longitude, latitude]",
                get_text="owner_safe",
                get_size=10,
                get_color=[255, 255, 255],
                get_angle=0,
                billboard=True,
            )
        )
    return layers


def create_deck_map(df: pd.DataFrame, map_style: str, show_labels: bool, aggregated: bool, hex_radius_m: int):
    if df.empty or df["latitude"].isna().all():
        center_lat = 42.1856
        center_lon = -74.2848
        zoom = 12
    else:
        center_lat = df["latitude"].mean()
        center_lon = df["longitude"].mean()
        if pd.isna(center_lat) or pd.isna(center_lon):
            center_lat = 42.1856
            center_lon = -74.2848
        zoom = 12

    prepared = _prepare_deck_data(df)

    # Convert hex color to RGB list
    def hex_to_rgb(color: str) -> list:
        color = color.lstrip("#")
        return [int(color[i:i+2], 16) for i in (0, 2, 4)]

    prepared["r"] = prepared["color"].apply(lambda c: hex_to_rgb(c)[0])
    prepared["g"] = prepared["color"].apply(lambda c: hex_to_rgb(c)[1])
    prepared["b"] = prepared["color"].apply(lambda c: hex_to_rgb(c)[2])

    layers = _build_layers(prepared, show_labels=show_labels, aggregated=aggregated, hex_radius_m=hex_radius_m)
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        pitch=35,
    )

    tooltip = {
        "html": "<b>{owner_safe}</b><br/>Parcel: {parcel_id_safe}<br/>{property_class_desc_safe}<br/>Acres: {acreage}<br/>Assessed: ${assessed_value}",
        "style": {"backgroundColor": "#16213e", "color": "white"},
    }

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style=_map_style(map_style),
        tooltip=tooltip,
    )

def get_spatial_index(df: pd.DataFrame):
    coords = df[["latitude", "longitude"]].to_numpy()
    if coords.size == 0:
        return None, False
    coords_rounded = np.round(coords, 6)
    hash_key = hashlib.sha256(coords_rounded.tobytes()).hexdigest()
    cache = st.session_state.setdefault("spatial_index_cache", {})
    if hash_key in cache:
        return cache[hash_key], True
    nn = NearestNeighbors(n_neighbors=1, algorithm="ball_tree", metric="haversine")
    nn.fit(np.radians(coords_rounded))
    cache[hash_key] = nn
    return nn, False


@st.cache_data
def geocode_address(address: str):
    if not address:
        return None
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "lanesville-property-finder/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            raise ValueError("Nominatim no results")
        return float(data[0]["lat"]), float(data[0]["lon"])
    except requests.RequestException:
        pass
    except ValueError:
        pass
    
    # Fallback: Mapbox Geocoding API (requires MAPBOX_ACCESS_TOKEN)
    mapbox_token = os.environ.get("MAPBOX_ACCESS_TOKEN")
    if not mapbox_token:
        return None
    try:
        resp = requests.get(
            f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address}.json",
            params={"access_token": mapbox_token, "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        lon, lat = features[0]["center"]
        return float(lat), float(lon)
    except requests.RequestException:
        return None


def display_property_details(parcel):
    """Display detailed property information"""
    st.markdown(f"""
    <div class="property-card">
        <h4>📍 {parcel['owner']}</h4>
        <p><strong>Parcel ID:</strong> {parcel['parcel_id']}</p>
        <p><strong>SBL:</strong> {parcel['sbl']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 📋 Property Details")
        st.write(f"**Class:** {parcel['property_class']} - {parcel['property_class_desc']}")
        st.write(f"**Acreage:** {parcel['acreage']:.2f} acres")
        st.write(f"**Municipality:** {parcel['municipality']}")
        st.write(f"**School District:** {parcel['school_district']}")
        
    with col2:
        st.markdown("##### 💰 Tax Information")
        st.write(f"**Assessed Value:** ${parcel['assessed_value']:,}")
        st.write(f"**Land Value:** ${parcel['land_value']:,}")
        st.write(f"**Improvement Value:** ${parcel['improvement_value']:,}")
        st.write(f"**Annual Taxes:** ${parcel['annual_taxes']:,.2f}")
    
    st.markdown("##### 📬 Mailing Address")
    st.write(f"{parcel['mailing_address']}")
    st.write(f"{parcel['mailing_city']}, {parcel['mailing_state']} {parcel['mailing_zip']}")
    
    st.markdown("##### 📜 Deed Information")
    col1, col2, col3 = st.columns(3)
    col1.write(f"**Book:** {parcel['deed_book']}")
    col2.write(f"**Page:** {parcel['deed_page']}")
    if parcel['last_sale_price']:
        col3.write(f"**Last Sale:** ${parcel['last_sale_price']:,}")


def main():
    # Initialize session state for parcel count
    if 'num_parcels' not in st.session_state:
        st.session_state.num_parcels = 500
    if 'sample_seed' not in st.session_state:
        st.session_state.sample_seed = 42
    
    # Load data with current parcel count
    df = load_parcel_data(st.session_state.num_parcels, seed=st.session_state.sample_seed)
    if df is None or df.empty:
        df = generate_sample_data(st.session_state.num_parcels, seed=st.session_state.sample_seed)
    
    # Sidebar
    with st.sidebar:
        st.markdown("# 🗺️ Lanesville Property Finder")
        st.markdown("*OnXHunt-style Property Identification*")
        st.markdown("---")
        
        # Search functionality
        st.markdown("### 🔍 Search")
        search_type = st.radio(
            "Search by:",
            ["Owner Name", "Parcel ID", "Address"],
            horizontal=True
        )
        
        search_query = st.text_input(
            "Enter search term:",
            placeholder="Start typing..."
        )
        
        # Filter results based on search
        if search_query:
            if search_type == "Owner Name":
                filtered_df = df[df['owner'].str.lower().str.contains(search_query.lower())]
            elif search_type == "Parcel ID":
                filtered_df = df[df['parcel_id'].str.contains(search_query)]
            else:
                filtered_df = df[df['mailing_address'].str.lower().str.contains(search_query.lower())]
        else:
            filtered_df = df
        
        st.markdown("---")
        
        # Filters
        st.markdown("### 🎛️ Filters")
        
        # Property class filter
        property_classes = df['property_class_desc'].unique()
        selected_classes = st.multiselect(
            "Property Type:",
            options=property_classes,
            default=[]
        )
        
        if selected_classes:
            filtered_df = filtered_df[filtered_df['property_class_desc'].isin(selected_classes)]
        
        # Acreage filter
        min_acres, max_acres = st.slider(
            "Acreage Range:",
            min_value=0.0,
            max_value=float(df['acreage'].max()),
            value=(0.0, float(df['acreage'].max())),
            step=0.5
        )
        filtered_df = filtered_df[(filtered_df['acreage'] >= min_acres) & (filtered_df['acreage'] <= max_acres)]
        
        # Value filter
        min_value, max_value = st.slider(
            "Assessed Value Range:",
            min_value=0,
            max_value=int(df['assessed_value'].max()),
            value=(0, int(df['assessed_value'].max())),
            step=10000,
            format="$%d"
        )
        filtered_df = filtered_df[(filtered_df['assessed_value'] >= min_value) & (filtered_df['assessed_value'] <= max_value)]
        
        st.markdown("---")
        
        # Map options
        st.markdown("### 🗺️ Map Options")
        map_style = st.selectbox(
            "Base Map:",
            ["satellite", "topo", "streets", "dark"],
            index=0
        )
        
        show_labels = st.checkbox("Show Owner Labels", value=False)
        st.markdown("### ⚡ Performance")
        use_aggregate = st.checkbox("Aggregate large datasets", value=True)
        aggregate_threshold = st.slider(
            "Aggregation threshold (parcels)",
            min_value=1000,
            max_value=20000,
            value=3000,
            step=500,
        )
        global HEX_RADIUS_METERS
        hex_radius_m = st.slider(
            "Hex radius (meters)",
            min_value=30,
            max_value=200,
            value=80,
            step=10,
        )
        
        st.markdown("---")
        
        # Legend
        st.markdown("### 📊 Legend")
        st.markdown("""
        <div class="legend-item">
            <div class="legend-color" style="background-color: #4CAF50;"></div>
            <span style="color: #eaeaea;">Residential</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #FFC107;"></div>
            <span style="color: #eaeaea;">Vacant Land</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #2196F3;"></div>
            <span style="color: #eaeaea;">State/Forest</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #8BC34A;"></div>
            <span style="color: #eaeaea;">Agricultural</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #FF5722;"></div>
            <span style="color: #eaeaea;">Commercial</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Data settings
        st.markdown("### ⚙️ Data Settings")
        
        # Check data source
        data_file = Path("data/lanesville_parcels.json")
        if data_file.exists():
            try:
                with open(data_file, "r") as f:
                    cached_data = json.load(f)
                is_real_data = len(cached_data) > 0
                st.success(f"✅ **Real NYS Data**")
                st.write(f"📊 {len(df):,} parcels loaded")
                st.write(f"📍 {df['municipality'].nunique()} municipalities")
                
                if st.button("🔄 Clear & Use Sample"):
                    data_file.unlink()
                    st.cache_data.clear()
                    st.rerun()
            except:
                is_real_data = False
        else:
            is_real_data = False
        
        if not is_real_data:
            st.warning("⚠️ **Sample Data Mode**")
            st.write("Using generated sample data")
            
            new_num_parcels = st.slider(
                "Sample Parcels:",
                min_value=100,
                max_value=2000,
                value=st.session_state.num_parcels,
                step=100,
                help="Number of sample parcels to generate"
            )
            
            if new_num_parcels != st.session_state.num_parcels:
                st.session_state.num_parcels = new_num_parcels
                st.cache_data.clear()
                st.rerun()
            
            st.markdown("---")
            st.page_link("pages/4_🔧_Data_Management.py", label="🔧 Fetch Real NYS Data", icon="📡")
        
        st.markdown("---")
        
        # Quick zip code filter
        st.markdown("### 📮 Filter by Zip Code")
        available_zips = df['mailing_zip'].unique().tolist()
        selected_zip = st.selectbox(
            "Mailing Zip Code:",
            options=["All"] + sorted([str(z) for z in available_zips]),
            index=0
        )
        
        if selected_zip != "All":
            filtered_df = filtered_df[filtered_df['mailing_zip'].astype(str) == selected_zip]
        
        st.markdown("---")
        st.markdown(f"*Showing {len(filtered_df)} of {len(df)} parcels*")
    
    # Main content area
    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Parcels", len(filtered_df))
    with col2:
        st.metric("Total Acreage", f"{filtered_df['acreage'].sum():,.1f}" if not filtered_df.empty else "0.0")
    with col3:
        avg_value = filtered_df['assessed_value'].mean() if not filtered_df.empty else 0
        st.metric("Avg. Assessed Value", f"${avg_value:,.0f}")
    with col4:
        st.metric("Unique Owners", filtered_df['owner'].nunique() if not filtered_df.empty else 0)
    
    # Map and details layout
    map_col, details_col = st.columns([2, 1])
    
    with map_col:
        st.markdown("### 🗺️ Property Map")
        
        # Check if we have data to display
        if filtered_df.empty:
            st.warning("⚠️ No parcels match your current filters. Try adjusting your search criteria.")
        else:
            use_aggregate = use_aggregate and len(filtered_df) > aggregate_threshold
            deck = create_deck_map(
                filtered_df,
                map_style=map_style,
                show_labels=show_labels,
                aggregated=use_aggregate,
                hex_radius_m=hex_radius_m,
            )
            st.pydeck_chart(deck, height=600)
    
    with details_col:
        st.markdown("### 📋 Property Details")
        
        # Nearest parcel search
        st.markdown("##### 🎯 Find Nearest Parcel (by coordinates)")
        st.caption("Note: pydeck click events aren’t available in Streamlit yet, so use coordinates or address lookup.")
        address_query = st.text_input("Address (optional)")
        geocode_col1, geocode_col2 = st.columns([1, 3])
        with geocode_col1:
                if st.button("Geocode"):
                    result = geocode_address(address_query)
                    if result:
                        st.session_state["target_lat"] = result[0]
                        st.session_state["target_lon"] = result[1]
                        st.success(f"Geocoded to {result[0]:.6f}, {result[1]:.6f}")
                    else:
                        st.warning("Address not found. If you have a Mapbox token, set MAPBOX_ACCESS_TOKEN.")
        with geocode_col2:
            st.write("")
        
        coord_col1, coord_col2, coord_col3 = st.columns([1, 1, 1])
        with coord_col1:
            target_lat = st.number_input(
                "Latitude",
                value=st.session_state.get("target_lat", 42.1856),
                format="%.6f"
            )
        with coord_col2:
            target_lon = st.number_input(
                "Longitude",
                value=st.session_state.get("target_lon", -74.2848),
                format="%.6f"
            )
        with coord_col3:
            if st.button("Find Nearest"):
                if not filtered_df.empty:
                    nn, used_cache = get_spatial_index(filtered_df)
                    if nn is None:
                        st.warning("No valid coordinates available for spatial search.")
                    else:
                        if used_cache:
                            st.caption("Using cached spatial index.")
                        target = np.radians([[target_lat, target_lon]])
                        dist, idx = nn.kneighbors(target, n_neighbors=1)
                        nearest = filtered_df.iloc[int(idx[0][0])]
                        st.session_state['selected_owner'] = nearest['owner']
                        st.session_state['selected_parcel_id'] = nearest['parcel_id']
                        st.success(f"Nearest parcel: {nearest['parcel_id']} ({nearest['owner']})")
                else:
                    st.warning("No parcels available to search.")
        
        # Property selector
        owner_options = [""] + list(filtered_df['owner'].unique())
        selected_owner = st.selectbox(
            "Select Property:",
            options=owner_options,
            format_func=lambda x: "Choose a property..." if x == "" else x,
            index=(
                0 if st.session_state.get('selected_owner') not in filtered_df['owner'].unique()
                else owner_options.index(st.session_state.get('selected_owner'))
            ),
            key="selected_owner"
        )
        
        if selected_owner:
            owner_parcels = filtered_df[filtered_df['owner'] == selected_owner]
            
            if len(owner_parcels) > 1:
                parcel_options = owner_parcels['parcel_id'].tolist()
                selected_parcel_id = st.selectbox(
                    "Select Parcel:",
                    parcel_options,
                    index=(
                        0 if st.session_state.get('selected_parcel_id') not in parcel_options
                        else parcel_options.index(st.session_state.get('selected_parcel_id'))
                    ),
                    key="selected_parcel_id"
                )
                selected_parcel = owner_parcels[owner_parcels['parcel_id'] == selected_parcel_id].iloc[0]
            else:
                selected_parcel = owner_parcels.iloc[0]
            
            display_property_details(selected_parcel)
            
            # Export button
            st.download_button(
                label="📄 Download Property Report (JSON)",
                data=json.dumps(selected_parcel.to_dict(), indent=2, default=str),
                file_name=f"property_{selected_parcel['parcel_id'].replace('.', '_')}.json",
                mime="application/json"
            )
        else:
            st.info("👆 Click on a parcel in the map or select an owner above to view details.")
    
    # Search results table
    with st.expander("📊 Search Results Table", expanded=False):
        display_cols = ['parcel_id', 'owner', 'property_class_desc', 'acreage', 'assessed_value', 'mailing_address', 'mailing_city']
        st.dataframe(
            filtered_df[display_cols].rename(columns={
                'parcel_id': 'Parcel ID',
                'owner': 'Owner',
                'property_class_desc': 'Property Type',
                'acreage': 'Acres',
                'assessed_value': 'Assessed Value',
                'mailing_address': 'Address',
                'mailing_city': 'City'
            }),
            width="stretch",
            hide_index=True
        )
        
        # Export all results
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Download All Results (CSV)",
            data=csv,
            file_name="lanesville_parcels_export.csv",
            mime="text/csv"
        )
    
    # Data sources info
    with st.expander("ℹ️ Data Sources & Information"):
        st.markdown("""
        ### About This Application
        
        This application provides property ownership information for Lanesville, NY 
        (Town of Hunter, Greene County). It is designed to function similarly to OnXHunt 
        for identifying property boundaries and ownership.
        
        ### Data Sources
        
        For production use, integrate with official data sources:
        
        - **NYS GIS Clearinghouse**: [https://gis.ny.gov/](https://gis.ny.gov/)
        - **Greene County Real Property**: Tax parcel data and assessment rolls
        - **NYS ORPS**: Office of Real Property Tax Services data
        
        ### Features
        
        - 🗺️ Interactive satellite/topo maps with parcel boundaries
        - 🔍 Search by owner name, parcel ID, or address
        - 🎛️ Filter by property type, acreage, and assessed value
        - 📋 Detailed property information including tax data
        - 📥 Export capabilities (JSON, CSV)
        - 📍 GPS location support
        
        ### Legal Notice
        
        Property boundary data is for reference only. Always verify with official 
        county records before making any decisions based on this information.
        """)
    
    # Footer
    st.markdown("""
    <div class="footer">
        <p>Lanesville Property Finder | Data: Greene County Tax Parcels | 
        Built with Streamlit & Folium</p>
        <p>⚠️ For reference only - verify with official county records</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
