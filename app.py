"""
Lanesville Property Finder - OnXHunt-style Property Owner Identification
A Streamlit application for exploring tax parcels and property ownership in Lanesville, NY
"""

import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import Draw, MousePosition, Fullscreen, LocateControl
from streamlit_folium import st_folium
import json
from pathlib import Path
import random

# Page configuration
st.set_page_config(
    page_title="Lanesville Property Finder",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for OnXHunt-style UI
st.markdown("""
<style>
    /* Main container styling */
    .stApp {
        background-color: #1a1a2e;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #16213e;
        border-right: 2px solid #e94560;
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: #eaeaea;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #e94560 !important;
        font-family: 'Segoe UI', sans-serif;
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
    [data-testid="stMetricValue"] {
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
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_parcel_data(num_parcels: int = 500):
    """Load parcel data from cache file or generate sample data for Lanesville, NY
    
    Priority:
    1. Load from cached real NYS data (data/lanesville_parcels.json)
    2. Generate sample data if no cache exists
    
    Args:
        num_parcels: Number of sample parcels to generate if no data file exists
    """
    data_file = Path("data/lanesville_parcels.json")
    
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
    return generate_sample_data(num_parcels)


def generate_sample_data(num_parcels: int = 500) -> pd.DataFrame:
    """Generate sample parcel data for demonstration
    
    Args:
        num_parcels: Number of sample parcels to generate
    """
    # Lanesville is located approximately at 42.1856° N, 74.2848° W
    # These are representative sample parcels - replace with real data
    
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
    
    property_classes = {
        "210": "One Family Residential",
        "220": "Two Family Residential",
        "240": "Rural Residence",
        "260": "Seasonal Residence",
        "270": "Mobile Home",
        "280": "Multiple Residences",
        "311": "Vacant Land - Residential",
        "312": "Vacant Land - Under 10 Acres",
        "322": "Vacant Land - Over 10 Acres",
        "910": "Private Forest",
        "920": "State Forest",
        "930": "State Owned - Other",
        "940": "State Reforestation",
        "105": "Agricultural Vacant",
        "112": "Dairy Farm",
        "117": "Horse Farm",
        "120": "Field Crops",
        "421": "Restaurant",
        "485": "One Story Small Structure",
        "582": "Camping Facility",
        "620": "Religious",
        "651": "Highway Garage"
    }
    
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
        lat_offset = random.uniform(-0.05, 0.05)
        lon_offset = random.uniform(-0.07, 0.07)
        
        prop_class = random.choice(list(property_classes.keys()))
        acreage = round(random.uniform(0.5, 50.0), 2)
        
        # Adjust acreage based on property class
        if prop_class in ["322", "910", "920", "930", "940"]:
            acreage = round(random.uniform(20.0, 200.0), 2)
        elif prop_class in ["311", "312"]:
            acreage = round(random.uniform(0.5, 15.0), 2)
        
        assessed_value = int(acreage * random.uniform(5000, 25000))
        if prop_class in ["210", "220", "240", "260"]:
            assessed_value += random.randint(80000, 350000)
        
        # Generate parcel polygon (simplified rectangle)
        size_factor = min(acreage * 0.0001, 0.005)  # Cap size for display
        coords = [
            [base_lat + lat_offset, base_lon + lon_offset],
            [base_lat + lat_offset + size_factor, base_lon + lon_offset],
            [base_lat + lat_offset + size_factor, base_lon + lon_offset + size_factor * 1.5],
            [base_lat + lat_offset, base_lon + lon_offset + size_factor * 1.5],
        ]
        
        # Assign zip code - 70% local, 30% non-local
        if random.random() > 0.3:
            mailing_zip = random.choice(local_zips)
            mailing_city = random.choice(["Lanesville", "Hunter", "Tannersville", "Haines Falls", "Jewett"])
        else:
            mailing_zip = random.choice(nonlocal_zips)
            mailing_city = random.choice(["New York", "Brooklyn", "Catskill"])
        
        # Street names (defined outside f-string to avoid escape issues)
        street_names = [
            'Main St', 'Mountain Rd', 'Route 214', 'Spruceton Rd', 'Notch Rd', 
            'Hollow Rd', 'Creek Rd', 'State Route 23A', 'Platte Clove Rd', 
            'Bloomer Rd', 'Clum Hill Rd', 'Devils Tombstone Rd'
        ]
        
        parcel = {
            "parcel_id": f"86.{random.randint(1,25)}-{random.randint(1,60)}-{random.randint(1,99)}",
            "sbl": f"86.00-{random.randint(1,9)}-{random.randint(1,99)}.{random.randint(0,999):03d}",
            "owner": random.choice(sample_owners),
            "mailing_address": f"{random.randint(1, 999)} {random.choice(street_names)}",
            "mailing_city": mailing_city,
            "mailing_state": "NY",
            "mailing_zip": mailing_zip,
            "property_class": prop_class,
            "property_class_desc": property_classes[prop_class],
            "acreage": acreage,
            "assessed_value": assessed_value,
            "land_value": int(assessed_value * random.uniform(0.2, 0.5)),
            "improvement_value": int(assessed_value * random.uniform(0.5, 0.8)),
            "tax_year": 2024,
            "annual_taxes": round(assessed_value * 0.025, 2),
            "school_district": "Hunter-Tannersville CSD",
            "municipality": "Hunter",
            "county": "Greene",
            "latitude": base_lat + lat_offset,
            "longitude": base_lon + lon_offset,
            "coordinates": coords,
            "deed_book": f"{random.randint(100, 999)}",
            "deed_page": f"{random.randint(1, 500)}",
            "last_sale_date": f"{random.randint(1990, 2024)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "last_sale_price": random.randint(50000, 500000) if random.random() > 0.3 else None
        }
        parcels.append(parcel)
    
    return pd.DataFrame(parcels)


def get_parcel_color(property_class):
    """Return color based on property classification"""
    class_colors = {
        "2": "#4CAF50",   # Residential - Green
        "3": "#FFC107",   # Vacant Land - Yellow
        "9": "#2196F3",   # State/Forest - Blue
        "1": "#8BC34A",   # Agricultural - Light Green
        "4": "#FF5722",   # Commercial - Orange
        "5": "#9C27B0",   # Recreation - Purple
        "6": "#607D8B",   # Community Service - Gray
    }
    return class_colors.get(property_class[0], "#757575")


def create_map(df, selected_parcel=None, show_labels=True, map_style="satellite"):
    """Create the interactive Folium map"""
    
    # Handle empty dataframe - default to Lanesville center
    if df.empty or df['latitude'].isna().all():
        center_lat = 42.1856
        center_lon = -74.2848
    else:
        center_lat = df['latitude'].mean()
        center_lon = df['longitude'].mean()
        
        # Additional NaN check
        if pd.isna(center_lat) or pd.isna(center_lon):
            center_lat = 42.1856
            center_lon = -74.2848
    
    # Map tile options
    tiles_map = {
        "satellite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "topo": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "streets": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "dark": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    }
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles=None
    )
    
    # Add base layers
    folium.TileLayer(
        tiles=tiles_map.get(map_style, tiles_map["satellite"]),
        attr="Esri/OpenStreetMap/OpenTopoMap",
        name="Base Map"
    ).add_to(m)
    
    # Add satellite layer option
    folium.TileLayer(
        tiles=tiles_map["satellite"],
        attr="Esri",
        name="Satellite",
        overlay=False
    ).add_to(m)
    
    # Add topo layer option
    folium.TileLayer(
        tiles=tiles_map["topo"],
        attr="OpenTopoMap",
        name="Topographic",
        overlay=False
    ).add_to(m)
    
    # Create feature groups for different property types
    residential_group = folium.FeatureGroup(name="🏠 Residential", show=True)
    vacant_group = folium.FeatureGroup(name="🌲 Vacant Land", show=True)
    state_group = folium.FeatureGroup(name="🏛️ State/Public", show=True)
    other_group = folium.FeatureGroup(name="📍 Other", show=True)
    
    for _, row in df.iterrows():
        color = get_parcel_color(row['property_class'])
        is_selected = selected_parcel and row['parcel_id'] == selected_parcel
        
        # Create polygon for parcel
        polygon = folium.Polygon(
            locations=row['coordinates'],
            color='#e94560' if is_selected else color,
            weight=3 if is_selected else 1,
            fill=True,
            fillColor=color,
            fillOpacity=0.6 if is_selected else 0.35,
            popup=folium.Popup(
                f"""
                <div style="font-family: Arial; min-width: 250px;">
                    <h4 style="color: #e94560; margin-bottom: 10px;">{row['owner']}</h4>
                    <hr style="border-color: #e94560;">
                    <p><strong>Parcel ID:</strong> {row['parcel_id']}</p>
                    <p><strong>SBL:</strong> {row['sbl']}</p>
                    <p><strong>Class:</strong> {row['property_class_desc']}</p>
                    <p><strong>Acreage:</strong> {row['acreage']:.2f} acres</p>
                    <p><strong>Assessed Value:</strong> ${row['assessed_value']:,}</p>
                    <p><strong>Annual Taxes:</strong> ${row['annual_taxes']:,.2f}</p>
                    <hr>
                    <p><strong>Mailing Address:</strong><br>
                    {row['mailing_address']}<br>
                    {row['mailing_city']}, {row['mailing_state']} {row['mailing_zip']}</p>
                </div>
                """,
                max_width=300
            ),
            tooltip=f"{row['owner']} - {row['acreage']:.1f} ac"
        )
        
        # Add to appropriate group
        prop_class = row['property_class'][0]
        if prop_class == "2":
            polygon.add_to(residential_group)
        elif prop_class == "3":
            polygon.add_to(vacant_group)
        elif prop_class == "9":
            polygon.add_to(state_group)
        else:
            polygon.add_to(other_group)
        
        # Add label if enabled
        if show_labels:
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                icon=folium.DivIcon(
                    html=f'<div style="font-size: 8px; color: white; text-shadow: 1px 1px 2px black; white-space: nowrap;">{row["owner"][:15]}</div>',
                    icon_size=(100, 20),
                    icon_anchor=(50, 10)
                )
            ).add_to(m)
    
    # Add feature groups to map
    residential_group.add_to(m)
    vacant_group.add_to(m)
    state_group.add_to(m)
    other_group.add_to(m)
    
    # Add controls
    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen(position="topleft").add_to(m)
    LocateControl(auto_start=False, position="topleft").add_to(m)
    MousePosition(position="bottomleft").add_to(m)
    
    # Add drawing tools
    Draw(
        draw_options={
            "polyline": True,
            "polygon": True,
            "circle": False,
            "marker": True,
            "circlemarker": False,
            "rectangle": True
        },
        edit_options={"edit": True, "remove": True}
    ).add_to(m)
    
    return m


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
    
    # Load data with current parcel count
    df = load_parcel_data(st.session_state.num_parcels)
    
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
            st.info("💡 Go to **Data Management** page to fetch real NYS parcel data")
        
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
            # Show empty map centered on Lanesville
            m = folium.Map(
                location=[42.1856, -74.2848],
                zoom_start=14,
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri"
            )
            st_folium(m, width=None, height=600)
        else:
            # Create and display map
            m = create_map(filtered_df, show_labels=show_labels, map_style=map_style)
            map_data = st_folium(m, width=None, height=600, returned_objects=["last_object_clicked"])
            
            # Handle map clicks
            if map_data and map_data.get("last_object_clicked"):
                clicked_lat = map_data["last_object_clicked"].get("lat")
                clicked_lng = map_data["last_object_clicked"].get("lng")
                st.session_state['clicked_location'] = (clicked_lat, clicked_lng)
    
    with details_col:
        st.markdown("### 📋 Property Details")
        
        # Property selector
        selected_owner = st.selectbox(
            "Select Property:",
            options=[""] + list(filtered_df['owner'].unique()),
            format_func=lambda x: "Choose a property..." if x == "" else x
        )
        
        if selected_owner:
            owner_parcels = filtered_df[filtered_df['owner'] == selected_owner]
            
            if len(owner_parcels) > 1:
                parcel_options = owner_parcels['parcel_id'].tolist()
                selected_parcel_id = st.selectbox("Select Parcel:", parcel_options)
                selected_parcel = owner_parcels[owner_parcels['parcel_id'] == selected_parcel_id].iloc[0]
            else:
                selected_parcel = owner_parcels.iloc[0]
            
            display_property_details(selected_parcel)
            
            # Export button
            if st.button("📄 Export Property Report"):
                st.download_button(
                    label="Download JSON",
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
