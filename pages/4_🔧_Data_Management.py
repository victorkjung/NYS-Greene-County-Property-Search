"""
Data Management - Fetch and manage real NYS parcel data
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nys_data_fetcher import (
    NYSParcelFetcher, 
    fetch_greene_county_parcels,
    LANESVILLE_BBOX,
    GREENE_COUNTY_BBOX,
    PROPERTY_CLASS_DESC
)

st.set_page_config(
    page_title="Data Management | Lanesville Property Finder",
    page_icon="🔧",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #1a1a2e;
    }
    h1, h2, h3, h4 {
        color: #e94560 !important;
    }
    .success-box {
        background: #1b4332;
        border: 1px solid #40916c;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    .info-box {
        background: #0f3460;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    .warning-box {
        background: #5c4033;
        border: 1px solid #d4a373;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


def get_cache_info():
    """Get information about cached data files"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    cache_files = []
    for f in data_dir.glob("*.json"):
        stat = f.stat()
        try:
            with open(f, "r") as file:
                data = json.load(file)
                record_count = len(data) if isinstance(data, list) else 0
        except:
            record_count = 0
            
        cache_files.append({
            "filename": f.name,
            "path": str(f),
            "size_kb": stat.st_size / 1024,
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "records": record_count
        })
    
    return cache_files


def main():
    st.title("🔧 Data Management")
    st.markdown("*Fetch real parcel data from NYS GIS services*")
    
    # Tabs for different functions
    tab1, tab2, tab3 = st.tabs(["📡 Fetch NYS Data", "📁 Cached Data", "📤 Upload Data"])
    
    with tab1:
        st.markdown("### Fetch Real Parcel Data from NYS GIS")
        st.markdown("""
        This will connect to the NYS GIS Tax Parcel Public service and download 
        actual parcel data for Greene County / Lanesville area.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            area_choice = st.radio(
                "Coverage Area:",
                ["Lanesville/Hunter Area", "All of Greene County"],
                help="Lanesville area is faster, full county has more data"
            )
            
            area = "lanesville" if "Lanesville" in area_choice else "greene"
        
        with col2:
            max_records = st.number_input(
                "Maximum Records:",
                min_value=100,
                max_value=50000,
                value=5000,
                step=500,
                help="Limit the number of parcels to fetch"
            )
            
            use_cache = st.checkbox(
                "Use cached data if available",
                value=True,
                help="Skip fetching if recent data exists"
            )
        
        # Bounding box info
        bbox = LANESVILLE_BBOX if area == "lanesville" else GREENE_COUNTY_BBOX
        
        with st.expander("📍 Coverage Area Details"):
            st.write(f"**Bounding Box:**")
            st.write(f"- West: {bbox['xmin']:.4f}°")
            st.write(f"- East: {bbox['xmax']:.4f}°")
            st.write(f"- South: {bbox['ymin']:.4f}°")
            st.write(f"- North: {bbox['ymax']:.4f}°")
        
        st.markdown("---")
        
        # Fetch button
        if st.button("🚀 Fetch Data from NYS GIS", type="primary", width="stretch"):
            progress_container = st.empty()
            status_container = st.empty()
            
            def update_progress(msg):
                status_container.info(f"⏳ {msg}")
            
            with st.spinner("Connecting to NYS GIS services..."):
                try:
                    df = fetch_greene_county_parcels(
                        area=area,
                        max_records=max_records,
                        use_cache=use_cache,
                        progress_callback=update_progress
                    )
                    
                    if df is not None and not df.empty:
                        status_container.empty()
                        st.success(f"✅ Successfully fetched {len(df):,} parcels!")
                        
                        # Show summary
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Total Parcels", f"{len(df):,}")
                        col2.metric("Total Acreage", f"{df['acreage'].sum():,.1f}")
                        col3.metric("Unique Owners", f"{df['owner'].nunique():,}")
                        col4.metric("Avg. Value", f"${df['assessed_value'].mean():,.0f}")
                        
                        # Preview
                        st.markdown("##### Data Preview")
                        preview_cols = ['parcel_id', 'owner', 'property_class_desc', 'acreage', 'assessed_value', 'municipality']
                        available_cols = [c for c in preview_cols if c in df.columns]
                        st.dataframe(df[available_cols].head(20), width="stretch")
                        
                        # Property class breakdown
                        st.markdown("##### Property Types Found")
                        type_counts = df['property_class_desc'].value_counts().head(10)
                        st.bar_chart(type_counts)
                        
                        st.info("💡 Data has been cached. The main app will now use this real data!")
                        
                        # Clear the app cache so it reloads
                        st.cache_data.clear()
                        
                    else:
                        st.error("❌ Failed to fetch data. The NYS GIS service may be unavailable.")
                        st.markdown("""
                        **Troubleshooting:**
                        - The NYS GIS service may be down for maintenance
                        - Try again in a few minutes
                        - Check your internet connection
                        - Try fetching a smaller area
                        """)
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.exception(e)
        
        # Alternative data sources
        st.markdown("---")
        st.markdown("### Alternative Data Sources")
        
        with st.expander("🔗 Manual Data Download Options"):
            st.markdown("""
            If the automatic fetch doesn't work, you can download parcel data manually:
            
            **NYS GIS Clearinghouse**
            - Visit: [https://gis.ny.gov/](https://gis.ny.gov/)
            - Navigate to "Data" → "Tax Parcels"
            - Download Greene County shapefile
            
            **Greene County GIS**
            - Visit: [Greene County Website](https://www.greenegov.com/)
            - Contact Real Property Tax Services
            - Phone: (518) 719-3270
            
            **Data Formats Supported**
            - GeoJSON (.geojson)
            - JSON (our format)
            - Shapefile (.shp) - requires geopandas
            """)
    
    with tab2:
        st.markdown("### Cached Data Files")
        
        cache_files = get_cache_info()
        
        if cache_files:
            for cf in cache_files:
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.write(f"📄 **{cf['filename']}**")
                with col2:
                    st.write(f"{cf['records']:,} records")
                with col3:
                    st.write(f"{cf['size_kb']:.1f} KB")
                with col4:
                    st.write(cf['modified'].strftime("%Y-%m-%d"))
            
            st.markdown("---")
            
            # Option to delete cache
            if st.button("🗑️ Clear All Cached Data", type="secondary"):
                for cf in cache_files:
                    Path(cf['path']).unlink()
                st.success("Cache cleared!")
                st.cache_data.clear()
                st.rerun()
                
            # Option to set active dataset
            st.markdown("##### Set Active Dataset")
            active_file = st.selectbox(
                "Select dataset to use in main app:",
                [cf['filename'] for cf in cache_files]
            )
            
            if st.button("✅ Set as Active"):
                # Rename to lanesville_parcels.json (the default name the app looks for)
                source = Path("data") / active_file
                target = Path("data") / "lanesville_parcels.json"
                
                if source != target:
                    if target.exists():
                        target.unlink()
                    source.rename(target)
                    st.success(f"Set {active_file} as active dataset!")
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("No cached data files found. Use the 'Fetch NYS Data' tab to download data.")
    
    with tab3:
        st.markdown("### Upload Your Own Data")
        st.markdown("Upload a JSON or GeoJSON file with parcel data.")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["json", "geojson"],
            help="Upload JSON or GeoJSON parcel data"
        )
        
        if uploaded_file is not None:
            try:
                content = uploaded_file.read().decode('utf-8')
                data = json.loads(content)
                
                # Handle GeoJSON format
                if "type" in data and data["type"] == "FeatureCollection":
                    # Convert GeoJSON to our format
                    st.info("Detected GeoJSON format, converting...")
                    
                    records = []
                    for feature in data.get("features", []):
                        props = feature.get("properties", {})
                        geom = feature.get("geometry", {})
                        
                        record = {
                            "parcel_id": props.get("PRINT_KEY", props.get("parcel_id", "")),
                            "owner": props.get("OWNER1", props.get("owner", "Unknown")),
                            "sbl": props.get("SBL", props.get("sbl", "")),
                            "mailing_address": props.get("MAIL_ADDR", props.get("mailing_address", "")),
                            "mailing_city": props.get("MAIL_CITY", props.get("mailing_city", "")),
                            "mailing_state": props.get("MAIL_STATE", props.get("mailing_state", "NY")),
                            "mailing_zip": props.get("MAIL_ZIP", props.get("mailing_zip", "")),
                            "property_class": str(props.get("PROP_CLASS", props.get("property_class", ""))),
                            "property_class_desc": PROPERTY_CLASS_DESC.get(
                                str(props.get("PROP_CLASS", "")), 
                                props.get("property_class_desc", "Unknown")
                            ),
                            "acreage": float(props.get("CALC_ACRES", props.get("acreage", 0)) or 0),
                            "assessed_value": int(props.get("TOTAL_AV", props.get("assessed_value", 0)) or 0),
                            "land_value": int(props.get("LAND_AV", props.get("land_value", 0)) or 0),
                            "municipality": props.get("MUNI_NAME", props.get("municipality", "")),
                            "county": props.get("COUNTY_NAME", props.get("county", "Greene")),
                            "school_district": props.get("SCHOOL_NAME", props.get("school_district", "")),
                        }
                        
                        # Process geometry
                        if geom and geom.get("type") == "Polygon":
                            coords = geom.get("coordinates", [[]])[0]
                            record["coordinates"] = [[c[1], c[0]] for c in coords[:50]]
                            if coords:
                                record["latitude"] = sum(c[1] for c in coords) / len(coords)
                                record["longitude"] = sum(c[0] for c in coords) / len(coords)
                        
                        records.append(record)
                    
                    data = records
                
                # If it's already a list of records
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                    
                    st.success(f"✅ Loaded {len(df):,} records")
                    
                    # Preview
                    st.dataframe(df.head(10), width="stretch")
                    
                    # Save option
                    save_name = st.text_input(
                        "Save as:",
                        value="uploaded_parcels.json"
                    )
                    
                    if st.button("💾 Save to Cache", type="primary"):
                        output_path = Path("data") / save_name
                        output_path.parent.mkdir(exist_ok=True)
                        
                        with open(output_path, "w") as f:
                            json.dump(data, f, indent=2, default=str)
                        
                        st.success(f"Saved to {output_path}")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.error("Unsupported data format. Expected a list of records or GeoJSON FeatureCollection.")
                    
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
            except Exception as e:
                st.error(f"Error processing file: {e}")
    
    # Sidebar info
    with st.sidebar:
        st.markdown("### ℹ️ About NYS Data")
        st.markdown("""
        **NYS GIS Tax Parcel Service**
        
        The data comes from the NYS GIS 
        Tax Parcels Public dataset, which 
        is updated regularly by the state.
        
        **Data includes:**
        - Owner names
        - Property classifications
        - Assessed values
        - Acreage
        - Parcel boundaries
        - Mailing addresses
        
        **Limitations:**
        - Some fields may be incomplete
        - Updates are periodic, not real-time
        - Large downloads may be slow
        """)
        
        st.markdown("---")
        st.markdown("### 🔗 Resources")
        st.markdown("""
        - [NYS GIS Clearinghouse](https://gis.ny.gov/)
        - [Greene County GIS](https://www.greenegov.com/)
        - [NYS Real Property](https://www.tax.ny.gov/research/property/)
        """)


if __name__ == "__main__":
    main()
