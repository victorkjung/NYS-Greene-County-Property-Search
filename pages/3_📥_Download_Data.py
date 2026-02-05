"""
Data Download - Download parcel datasets by zip code or area
"""

import streamlit as st
import pandas as pd
import requests
import json
from pathlib import Path
from datetime import datetime
import io

from nys_data_fetcher import NYSParcelFetcher
from ui import apply_base_styles
st.set_page_config(
    page_title="Download Data | Lanesville Property Finder",
    page_icon="📥",
    layout="wide"
)

apply_base_styles("""
    .download-card {
        background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
        border: 1px solid #e94560;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    }
    .info-box {
        background: #0f3460;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
""")

# Greene County / Catskills area zip codes
AREA_ZIP_CODES = {
    "12450": {"name": "Lanesville", "town": "Hunter", "county": "Greene"},
    "12442": {"name": "Hunter", "town": "Hunter", "county": "Greene"},
    "12485": {"name": "Tannersville", "town": "Hunter", "county": "Greene"},
    "12464": {"name": "Phoenicia", "town": "Shandaken", "county": "Ulster"},
    "12480": {"name": "Shandaken", "town": "Shandaken", "county": "Ulster"},
    "12457": {"name": "Mt Tremper", "town": "Shandaken", "county": "Ulster"},
    "12468": {"name": "Prattsville", "town": "Prattsville", "county": "Greene"},
    "12434": {"name": "Haines Falls", "town": "Hunter", "county": "Greene"},
    "12436": {"name": "Hensonville", "town": "Windham", "county": "Greene"},
    "12496": {"name": "Windham", "town": "Windham", "county": "Greene"},
    "12414": {"name": "Catskill", "town": "Catskill", "county": "Greene"},
    "12451": {"name": "Leeds", "town": "Catskill", "county": "Greene"},
    "12463": {"name": "Palenville", "town": "Catskill", "county": "Greene"},
    "12492": {"name": "West Kill", "town": "Lexington", "county": "Greene"},
    "12452": {"name": "Lexington", "town": "Lexington", "county": "Greene"},
    "12424": {"name": "Elka Park", "town": "Hunter", "county": "Greene"},
    "12439": {"name": "Jewett", "town": "Jewett", "county": "Greene"},
}

# Approximate coordinates for zip codes
ZIP_COORDINATES = {
    "12450": {"lat": 42.1856, "lon": -74.2848, "radius": 0.03},
    "12442": {"lat": 42.2037, "lon": -74.2153, "radius": 0.04},
    "12485": {"lat": 42.1962, "lon": -74.1337, "radius": 0.03},
    "12464": {"lat": 42.0821, "lon": -74.3137, "radius": 0.04},
    "12480": {"lat": 42.1176, "lon": -74.3965, "radius": 0.04},
    "12457": {"lat": 42.0432, "lon": -74.2587, "radius": 0.03},
    "12468": {"lat": 42.3176, "lon": -74.4337, "radius": 0.04},
    "12434": {"lat": 42.1962, "lon": -74.0837, "radius": 0.02},
    "12436": {"lat": 42.3012, "lon": -74.2337, "radius": 0.03},
    "12496": {"lat": 42.3112, "lon": -74.2537, "radius": 0.04},
    "12414": {"lat": 42.2176, "lon": -73.8637, "radius": 0.05},
    "12451": {"lat": 42.2676, "lon": -73.9137, "radius": 0.03},
    "12463": {"lat": 42.1762, "lon": -74.0237, "radius": 0.03},
    "12492": {"lat": 42.2376, "lon": -74.3837, "radius": 0.03},
    "12452": {"lat": 42.2576, "lon": -74.3637, "radius": 0.04},
    "12424": {"lat": 42.1862, "lon": -74.1537, "radius": 0.02},
    "12439": {"lat": 42.2562, "lon": -74.2037, "radius": 0.03},
}


@st.cache_data
def load_all_data():
    """Load full parcel dataset"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app import load_parcel_data
    seed = st.session_state.get("sample_seed", 42)
    num_parcels = st.session_state.get("num_parcels", 500)
    return load_parcel_data(num_parcels=num_parcels, seed=seed)


def filter_by_zip(df: pd.DataFrame, zip_code: str) -> pd.DataFrame:
    """Filter parcels by zip code using mailing address or geographic proximity"""
    
    # First try to match by mailing zip
    zip_match = df[df['mailing_zip'].astype(str).str.startswith(zip_code[:5])]
    
    # Also include parcels geographically within the zip code area
    if zip_code in ZIP_COORDINATES:
        coords = ZIP_COORDINATES[zip_code]
        geo_match = df[
            (df['latitude'].between(coords['lat'] - coords['radius'], coords['lat'] + coords['radius'])) &
            (df['longitude'].between(coords['lon'] - coords['radius'], coords['lon'] + coords['radius']))
        ]
        # Combine both filters
        combined = pd.concat([zip_match, geo_match]).drop_duplicates(subset=['parcel_id'])
        return combined
    
    return zip_match


def filter_by_town(df: pd.DataFrame, town: str) -> pd.DataFrame:
    """Filter parcels by municipality/town"""
    return df[df['municipality'].str.lower() == town.lower()]


def filter_by_property_class(df: pd.DataFrame, class_prefix: str) -> pd.DataFrame:
    """Filter by property class prefix (e.g., '2' for residential)"""
    return df[df['property_class'].str.startswith(class_prefix)]


def generate_sample_data_for_zip(zip_code: str, num_parcels: int = 50, seed: int | None = None) -> pd.DataFrame:
    """Generate sample parcel data for a specific zip code"""
    import random
    
    if zip_code not in ZIP_COORDINATES:
        return pd.DataFrame()
    
    coords = ZIP_COORDINATES[zip_code]
    zip_info = AREA_ZIP_CODES.get(zip_code, {"name": "Unknown", "town": "Unknown", "county": "Greene"})
    
    rng = random.Random(seed)
    sample_owners = [
        "Johnson Family Trust", "Smith, Robert & Mary", "Mountain View LLC",
        "Catskill Properties Inc", "Williams, Thomas", "NYS DEC",
        "Greene County", "Davis, Jennifer", "Anderson, Michael",
        "Miller, David & Susan", "Brown Estate", "Taylor, Christopher",
        "Wilson Holdings LLC", "Martinez, Carlos", "Thompson, Patricia",
        "Garcia, Maria", "Robinson, James", "Clark, William",
        "Lewis, Barbara", "Lee, Richard", "Walker, Karen",
        "Hall, Steven", "Allen, Michelle", "Young, Daniel",
        "King, Elizabeth", "Wright, Joseph", "Hill, Nancy"
    ]
    
    property_classes = {
        "210": "One Family Residential",
        "220": "Two Family Residential",
        "240": "Rural Residence",
        "260": "Seasonal Residence",
        "270": "Mobile Home",
        "311": "Vacant Land - Residential",
        "312": "Vacant Land - Under 10 Acres",
        "322": "Vacant Land - Over 10 Acres",
        "910": "Private Forest",
        "920": "State Forest",
        "105": "Agricultural Vacant",
        "120": "Field Crops",
        "421": "Restaurant",
        "485": "One Story Small Structure",
    }
    
    parcels = []
    for i in range(num_parcels):
        lat_offset = rng.uniform(-coords['radius'], coords['radius'])
        lon_offset = rng.uniform(-coords['radius'] * 1.3, coords['radius'] * 1.3)
        
        prop_class = rng.choice(list(property_classes.keys()))
        acreage = round(rng.uniform(0.5, 50.0), 2)
        
        if prop_class in ["322", "910", "920"]:
            acreage = round(rng.uniform(20.0, 150.0), 2)
        elif prop_class in ["311", "312"]:
            acreage = round(rng.uniform(0.5, 12.0), 2)
        
        assessed_value = int(acreage * rng.uniform(5000, 20000))
        if prop_class in ["210", "220", "240", "260"]:
            assessed_value += rng.randint(100000, 400000)
        
        lat = coords['lat'] + lat_offset
        lon = coords['lon'] + lon_offset
        
        size_factor = acreage * 0.0001
        parcel_coords = [
            [lat, lon],
            [lat + size_factor, lon],
            [lat + size_factor, lon + size_factor * 1.5],
            [lat, lon + size_factor * 1.5],
        ]
        
        parcel = {
            "parcel_id": f"{rng.randint(80,90)}.{rng.randint(1,20)}-{rng.randint(1,50)}-{rng.randint(1,99)}",
            "sbl": f"{rng.randint(80,90)}.00-{rng.randint(1,9)}-{rng.randint(1,99)}.{rng.randint(0,999):03d}",
            "owner": rng.choice(sample_owners),
            "mailing_address": f"{rng.randint(1, 999)} {rng.choice(['Main St', 'Mountain Rd', 'Route 214', 'Route 23A', 'Hollow Rd', 'Creek Rd'])}",
            "mailing_city": rng.choice([zip_info['name'], zip_info['town'], "New York", "Brooklyn"]),
            "mailing_state": "NY",
            "mailing_zip": zip_code if rng.random() > 0.3 else rng.choice(["10001", "11201", "12414"]),
            "property_class": prop_class,
            "property_class_desc": property_classes[prop_class],
            "acreage": acreage,
            "assessed_value": assessed_value,
            "land_value": int(assessed_value * rng.uniform(0.2, 0.5)),
            "improvement_value": int(assessed_value * rng.uniform(0.5, 0.8)),
            "tax_year": 2024,
            "annual_taxes": round(assessed_value * 0.025, 2),
            "school_district": f"{zip_info['town']}-Tannersville CSD",
            "municipality": zip_info['town'],
            "county": zip_info['county'],
            "latitude": lat,
            "longitude": lon,
            "coordinates": parcel_coords,
            "deed_book": f"{rng.randint(100, 999)}",
            "deed_page": f"{rng.randint(1, 500)}",
            "last_sale_date": f"{rng.randint(1995, 2024)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "last_sale_price": rng.randint(75000, 600000) if rng.random() > 0.4 else None
        }
        parcels.append(parcel)
    
    return pd.DataFrame(parcels)


def fetch_from_nys_gis(zip_code: str) -> pd.DataFrame:
    """
    Attempt to fetch real parcel data from NYS GIS services.
    Falls back to sample data if unavailable.
    """
    if zip_code not in ZIP_COORDINATES:
        st.warning(f"Zip code {zip_code} not in coverage area.")
        return pd.DataFrame()
    
    coords = ZIP_COORDINATES[zip_code]
    
    # Build bounding box
    bbox = {
        "xmin": coords['lon'] - coords['radius'] * 1.3,
        "ymin": coords['lat'] - coords['radius'],
        "xmax": coords['lon'] + coords['radius'] * 1.3,
        "ymax": coords['lat'] + coords['radius']
    }
    
    try:
        with st.spinner(f"Fetching data from NYS GIS for {zip_code}..."):
            fetcher = NYSParcelFetcher()
            df = fetcher.fetch_parcels(bbox=bbox, county="Greene", max_records=2000)
            
            if df is not None and not df.empty:
                st.success(f"Retrieved {len(df)} parcels from NYS GIS")
                return df
            
            st.info("No data returned from NYS GIS. Using sample data.")
            seed = st.session_state.get("sample_seed", 42)
            return generate_sample_data_for_zip(zip_code, seed=seed)
                
    except requests.RequestException as e:
        st.warning(f"Could not connect to NYS GIS: {e}")
        st.info("Generating sample data for demonstration...")
        seed = st.session_state.get("sample_seed", 42)
        return generate_sample_data_for_zip(zip_code, seed=seed)


def main():
    st.title("📥 Download Parcel Data")
    st.markdown("*Download property datasets by zip code, town, or custom area*")
    
    # Tabs for different download methods
    tab1, tab2, tab3 = st.tabs(["📮 By Zip Code", "🏘️ By Town", "📊 Full Dataset"])
    
    with tab1:
        st.markdown("### Download by Zip Code")
        st.markdown("Select one or more zip codes to download parcel data.")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Zip code selector
            zip_options = [f"{code} - {info['name']}, {info['town']}" 
                         for code, info in AREA_ZIP_CODES.items()]
            
            selected_zips = st.multiselect(
                "Select Zip Code(s):",
                options=zip_options,
                default=["12450 - Lanesville, Hunter"]
            )
            
            # Extract just the zip codes
            zip_codes = [z.split(" - ")[0] for z in selected_zips]
        
        with col2:
            st.markdown("##### Coverage Area")
            st.markdown("""
            Currently covers:
            - Greene County
            - Parts of Ulster County
            - Catskill Mountains region
            """)
        
        # Data source selection
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            data_source = st.radio(
                "Data Source:",
                ["Sample Data (Demo)", "NYS GIS (Live)"],
                help="Sample data is for demonstration. NYS GIS attempts to fetch real data."
            )
        
        with col2:
            num_parcels = st.slider(
                "Parcels per zip (sample mode):",
                min_value=25,
                max_value=200,
                value=50,
                step=25
            )
        
        # Property type filter
        st.markdown("##### Filter Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            include_residential = st.checkbox("Residential (2xx)", value=True)
        with col2:
            include_vacant = st.checkbox("Vacant Land (3xx)", value=True)
        with col3:
            include_other = st.checkbox("Other (1xx, 4xx, 9xx)", value=True)
        
        # Download button
        if st.button("🔍 Fetch Data", type="primary", width="stretch"):
            if not zip_codes:
                st.error("Please select at least one zip code.")
            else:
                all_data = []
                
                progress_bar = st.progress(0)
                
                for i, zip_code in enumerate(zip_codes):
                    if data_source == "Sample Data (Demo)":
                        seed = st.session_state.get("sample_seed", 42)
                        df = generate_sample_data_for_zip(zip_code, num_parcels, seed=seed)
                    else:
                        df = fetch_from_nys_gis(zip_code)
                    
                    if not df.empty:
                        # Apply filters
                        filtered = df.copy()
                        
                        class_filters = []
                        if include_residential:
                            class_filters.append(filtered['property_class'].str.startswith('2'))
                        if include_vacant:
                            class_filters.append(filtered['property_class'].str.startswith('3'))
                        if include_other:
                            class_filters.append(
                                filtered['property_class'].str.startswith('1') |
                                filtered['property_class'].str.startswith('4') |
                                filtered['property_class'].str.startswith('9')
                            )
                        
                        if class_filters:
                            combined_filter = class_filters[0]
                            for f in class_filters[1:]:
                                combined_filter = combined_filter | f
                            filtered = filtered[combined_filter]
                        
                        filtered['source_zip'] = zip_code
                        all_data.append(filtered)
                    
                    progress_bar.progress((i + 1) / len(zip_codes))
                
                if all_data:
                    combined_df = pd.concat(all_data, ignore_index=True)
                    st.session_state['downloaded_data'] = combined_df
                    
                    st.success(f"✅ Retrieved {len(combined_df)} parcels from {len(zip_codes)} zip code(s)")
                    
                    # Show preview
                    st.markdown("##### Data Preview")
                    preview_cols = ['parcel_id', 'owner', 'property_class_desc', 'acreage', 
                                   'assessed_value', 'mailing_city', 'source_zip']
                    st.dataframe(combined_df[preview_cols].head(20), width="stretch")
                    
                    # Summary stats
                    st.markdown("##### Summary Statistics")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Parcels", len(combined_df))
                    col2.metric("Total Acreage", f"{combined_df['acreage'].sum():,.1f}")
                    col3.metric("Total Value", f"${combined_df['assessed_value'].sum():,.0f}")
                    col4.metric("Unique Owners", combined_df['owner'].nunique())
                    
                    # Download options
                    st.markdown("---")
                    st.markdown("##### Export Options")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        csv = combined_df.to_csv(index=False)
                        st.download_button(
                            "📄 Download CSV",
                            data=csv,
                            file_name=f"parcels_{'_'.join(zip_codes)}_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                            width="stretch"
                        )
                    
                    with col2:
                        # JSON export (without coordinates for smaller file)
                        export_df = combined_df.drop(columns=['coordinates'], errors='ignore')
                        json_data = export_df.to_json(orient='records', indent=2, default_handler=str)
                        st.download_button(
                            "📄 Download JSON",
                            data=json_data,
                            file_name=f"parcels_{'_'.join(zip_codes)}_{datetime.now().strftime('%Y%m%d')}.json",
                            mime="application/json",
                            width="stretch"
                        )
                    
                    with col3:
                        # GeoJSON export
                        features = []
                        for _, row in combined_df.iterrows():
                            coords = row.get('coordinates', [])
                            if not coords or len(coords) < 3:
                                continue
                            feature = {
                                "type": "Feature",
                                "properties": {
                                    "parcel_id": row['parcel_id'],
                                    "owner": row['owner'],
                                    "acreage": row['acreage'],
                                    "assessed_value": row['assessed_value'],
                                    "property_class": row['property_class'],
                                    "property_class_desc": row['property_class_desc']
                                },
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[
                                        [coord[1], coord[0]] for coord in coords
                                    ] + [[coords[0][1], coords[0][0]]]]
                                }
                            }
                            features.append(feature)
                        
                        geojson = {
                            "type": "FeatureCollection",
                            "features": features
                        }
                        
                        st.download_button(
                            "🗺️ Download GeoJSON",
                            data=json.dumps(geojson, indent=2),
                            file_name=f"parcels_{'_'.join(zip_codes)}_{datetime.now().strftime('%Y%m%d')}.geojson",
                            mime="application/geo+json",
                            width="stretch"
                        )
                else:
                    st.error("No data retrieved. Please try again.")
    
    with tab2:
        st.markdown("### Download by Town/Municipality")
        
        # Get unique towns from zip codes
        towns = list(set([info['town'] for info in AREA_ZIP_CODES.values()]))
        towns.sort()
        
        selected_town = st.selectbox("Select Town:", options=towns)
        
        if st.button("🔍 Fetch Town Data", type="primary"):
            # Get all zip codes for this town
            town_zips = [code for code, info in AREA_ZIP_CODES.items() 
                        if info['town'] == selected_town]
            
            all_data = []
            for zip_code in town_zips:
                df = generate_sample_data_for_zip(zip_code, 40)
                if not df.empty:
                    all_data.append(df)
            
            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)
                
                st.success(f"✅ Retrieved {len(combined_df)} parcels for {selected_town}")
                
                # Download
                csv = combined_df.to_csv(index=False)
                st.download_button(
                    "📄 Download CSV",
                    data=csv,
                    file_name=f"parcels_{selected_town}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
    
    with tab3:
        st.markdown("### Download Full Dataset")
        st.markdown("Download the complete parcel database currently loaded in the application.")
        
        df = load_all_data()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Parcels", len(df))
        col2.metric("Total Acreage", f"{df['acreage'].sum():,.1f}")
        col3.metric("Unique Owners", df['owner'].nunique())
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv = df.to_csv(index=False)
            st.download_button(
                "📄 Download Full CSV",
                data=csv,
                file_name=f"lanesville_all_parcels_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width="stretch"
            )
        
        with col2:
            export_df = df.drop(columns=['coordinates'], errors='ignore')
            json_data = export_df.to_json(orient='records', indent=2, default_handler=str)
            st.download_button(
                "📄 Download Full JSON",
                data=json_data,
                file_name=f"lanesville_all_parcels_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                width="stretch"
            )
    
    # Sidebar info
    with st.sidebar:
        st.markdown("### 📮 Supported Zip Codes")
        
        for code, info in sorted(AREA_ZIP_CODES.items()):
            st.write(f"**{code}** - {info['name']}")
        
        st.markdown("---")
        st.markdown("### ℹ️ Data Sources")
        st.markdown("""
        **Sample Mode:** Generates realistic sample data for demonstration.
        
        **NYS GIS Mode:** Attempts to fetch real data from:
        - NYS Tax Parcel Public dataset
        - ArcGIS REST services
        
        For production use, contact Greene County Real Property for official data.
        """)
        
        st.markdown("---")
        st.markdown("### 📁 Export Formats")
        st.markdown("""
        - **CSV:** Spreadsheet compatible
        - **JSON:** For programming/APIs
        - **GeoJSON:** For GIS applications
        """)


if __name__ == "__main__":
    main()
