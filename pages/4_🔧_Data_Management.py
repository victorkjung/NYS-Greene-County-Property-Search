"""
Data Management - Fetch real Greene County parcel data
API: https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/Greene_County_Tax_Parcels/FeatureServer/0
Total Records: ~38,370 parcels
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
import sys

from ui import apply_base_styles
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from greene_county_fetcher import (
    fetch_greene_county_data,
    get_record_count,
    get_available_municipalities,
    save_to_file,
    load_from_file,
    GREENE_COUNTY_API,
    PROPERTY_CLASS_DESC
)
from app import geojson_to_df

st.set_page_config(
    page_title="Data Management | Lanesville Property Finder",
    page_icon="🔧",
    layout="wide"
)

apply_base_styles("""
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
    .api-url {
        background: #1a1a2e;
        border: 1px solid #0f3460;
        border-radius: 4px;
        padding: 8px;
        font-family: monospace;
        font-size: 12px;
        word-break: break-all;
    }
""")


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
            "size_mb": stat.st_size / (1024 * 1024),
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "records": record_count
        })
    
    return cache_files


def get_config():
    cfg_path = Path("data/config.json")
    if cfg_path.exists():
        try:
            with open(cfg_path, "r") as f:
                return json.load(f)
        except Exception:
            return {"use_geojson": True}
    return {"use_geojson": True}


def save_config(cfg: dict):
    cfg_path = Path("data/config.json")
    cfg_path.parent.mkdir(exist_ok=True)
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)


def main():
    st.title("🔧 Data Management")
    st.markdown("*Fetch real parcel data from Greene County ArcGIS*")
    
    # Show API info
    st.markdown("##### 📡 Data Source")
    st.markdown(f"""
    <div class="api-url">
    {GREENE_COUNTY_API}
    </div>
    """, unsafe_allow_html=True)
    
    # Get current record count from API
    with st.spinner("Checking API..."):
        api_count = get_record_count()
    
    if api_count > 0:
        st.success(f"✅ API Online - **{api_count:,}** parcels available")
    else:
        st.error("❌ Could not connect to API")
    
    st.markdown("---")
    
    # Tabs for different functions
    tab1, tab2, tab3, tab4 = st.tabs(["📡 Fetch Data", "📁 Cached Data", "📤 Upload Data", "⚙️ Data Source"])
    
    with tab1:
        st.markdown("### Download Greene County Parcels")
        st.markdown("""
        Download tax parcel data directly from Greene County's official ArcGIS server.
        You can download **all parcels** or filter by **municipality**.
        """)
        
        # Get available municipalities
        with st.spinner("Loading municipalities..."):
            municipalities = get_available_municipalities()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 📍 Area Selection")
            
            area_option = st.radio(
                "Select Area:",
                [
                    "🏔️ Hunter (Lanesville Area) - Recommended",
                    "🗺️ All of Greene County",
                    "🎯 Choose Municipality"
                ],
                help="Hunter includes Lanesville, Tannersville, Hunter Mountain areas"
            )
            
            municipality = None
            if "Hunter" in area_option:
                municipality = "Hunter"
            elif "Choose" in area_option:
                municipality = st.selectbox(
                    "Select Municipality:",
                    municipalities if municipalities else ["Hunter", "Catskill", "Windham", "Cairo", "Durham", "Coxsackie"]
                )
            
            # Get count for selected area
            with st.spinner("Getting record count..."):
                if municipality:
                    area_count = get_record_count(municipality)
                else:
                    area_count = get_record_count()
            
            st.info(f"📊 **{area_count:,}** parcels available" + (f" in {municipality}" if municipality else ""))
        
        with col2:
            st.markdown("##### ⚙️ Options")
            
            limit_download = st.checkbox("Limit number of records", value=False)
            
            if limit_download:
                max_records = st.number_input(
                    "Max records:",
                    min_value=100,
                    max_value=area_count if area_count > 0 else 50000,
                    value=min(5000, area_count) if area_count > 0 else 5000,
                    step=500
                )
            else:
                max_records = None
            
            st.markdown("##### ⏱️ Estimated Time")
            records_to_fetch = max_records if max_records else area_count
            if records_to_fetch:
                est_time = records_to_fetch / 1000 * 0.5
                st.write(f"⏱️ ~{est_time:.1f} minutes")
                st.write(f"📦 ~{records_to_fetch * 2 / 1024:.1f} MB")
        
        st.markdown("---")
        
        # Data includes info
        with st.expander("📋 Data Includes"):
            st.markdown("""
            - **Owner names** and mailing addresses
            - **Property classifications** (residential, vacant, commercial, etc.)
            - **Assessed values** (total, land, improvements)
            - **Acreage** for each parcel
            - **Parcel boundaries** (polygon coordinates for mapping)
            - **School districts** and tax information
            """)
        
        # Progress tracking
        if "fetch_running" not in st.session_state:
            st.session_state.fetch_running = False
        
        # Fetch button
        btn_label = f"🚀 Download {municipality or 'Greene County'} Parcels"
        if st.button(btn_label, type="primary", disabled=st.session_state.fetch_running):
            st.session_state.fetch_running = True
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(msg):
                status_text.info(f"⏳ {msg}")
                if "%" in msg:
                    try:
                        pct = float(msg.split("(")[1].split("%")[0])
                        progress_bar.progress(int(pct))
                    except:
                        pass
            
            try:
                df = fetch_greene_county_data(
                    use_cache=False,
                    max_records=max_records,
                    municipality=municipality,
                    progress_callback=update_progress
                )
                
                if df is not None and len(df) > 0:
                    progress_bar.progress(100)
                    status_text.empty()
                    
                    st.success(f"✅ Successfully downloaded {len(df):,} parcels!")
                    
                    # Summary stats
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Parcels", f"{len(df):,}")
                    col2.metric("Total Acreage", f"{df['acreage'].sum():,.0f}")
                    col3.metric("Unique Owners", f"{df['owner'].nunique():,}")
                    col4.metric("Municipalities", df['municipality'].nunique())
                    
                    # Municipality breakdown
                    if df['municipality'].nunique() > 1:
                        st.markdown("##### Parcels by Municipality")
                        muni_counts = df['municipality'].value_counts()
                        st.bar_chart(muni_counts)
                    
                    # Property types
                    st.markdown("##### Property Types")
                    type_counts = df['property_class_desc'].value_counts().head(15)
                    st.bar_chart(type_counts)
                    
                    # Preview
                    st.markdown("##### Data Preview")
                    preview_cols = ['parcel_id', 'owner', 'property_class_desc', 'acreage', 'assessed_value', 'municipality']
                    available_cols = [c for c in preview_cols if c in df.columns]
                    st.dataframe(df[available_cols].head(20), width="stretch")
                    
                    st.balloons()
                    st.info("💡 Data saved! The main app will now use this real data.")
                    
                    st.cache_data.clear()
                    
                else:
                    st.error("❌ Failed to fetch data. Please try again.")
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.exception(e)
            finally:
                st.session_state.fetch_running = False
    
    with tab2:
        st.markdown("### Cached Data Files")
        
        cache_files = get_cache_info()
        
        if cache_files:
            st.markdown("##### Available Datasets")
            
            for cf in cache_files:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        st.write(f"📄 **{cf['filename']}**")
                    with col2:
                        st.write(f"{cf['records']:,} records")
                    with col3:
                        st.write(f"{cf['size_mb']:.1f} MB")
                    with col4:
                        st.write(cf['modified'].strftime("%Y-%m-%d %H:%M"))
            
            st.markdown("---")
            
            # Actions
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🗑️ Clear All Cached Data"):
                    for cf in cache_files:
                        try:
                            Path(cf['path']).unlink()
                        except:
                            pass
                    st.success("Cache cleared!")
                    st.cache_data.clear()
                    st.rerun()
            
            with col2:
                # Export option
                if cache_files:
                    selected_file = st.selectbox(
                        "Export dataset:",
                        [cf['filename'] for cf in cache_files]
                    )
                    
                    if selected_file:
                        file_path = Path("data") / selected_file
                        if file_path.exists():
                            with open(file_path, "r") as f:
                                data = f.read()
                            st.download_button(
                                "📥 Download JSON",
                                data=data,
                                file_name=selected_file,
                                mime="application/json"
                            )
        else:
            st.info("No cached data files found. Use the 'Fetch Data' tab to download data.")
    
    with tab3:
        st.markdown("### Upload Your Own Data")
        st.markdown("""
        Upload a JSON or GeoJSON file with parcel data. The file should contain
        records with fields like: parcel_id, owner, acreage, assessed_value, 
        latitude, longitude, coordinates, etc.
        """)
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["json", "geojson"],
            help="Upload JSON or GeoJSON parcel data"
        )
        
        if uploaded_file is not None:
            try:
                content = uploaded_file.read().decode('utf-8')
                data = json.loads(content)
                
                # Handle GeoJSON FeatureCollection
                if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                    st.info("Detected GeoJSON format, converting...")
                    
                    records = []
                    for feature in data.get("features", []):
                        props = feature.get("properties", {})
                        geom = feature.get("geometry", {})
                        
                        record = dict(props)  # Start with all properties
                        
                        # Process geometry
                        if geom:
                            if geom.get("type") == "Polygon":
                                coords = geom.get("coordinates", [[]])[0]
                                record["coordinates"] = [[c[1], c[0]] for c in coords[:100]]
                                if coords:
                                    record["latitude"] = sum(c[1] for c in coords) / len(coords)
                                    record["longitude"] = sum(c[0] for c in coords) / len(coords)
                            elif geom.get("type") == "Point":
                                coords = geom.get("coordinates", [0, 0])
                                record["longitude"] = coords[0]
                                record["latitude"] = coords[1]
                                record["coordinates"] = [[coords[1], coords[0]]]
                        
                        records.append(record)
                    
                    data = records
                
                # Convert to DataFrame
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                    
                    st.success(f"✅ Loaded {len(df):,} records")
                    st.write(f"**Columns:** {', '.join(df.columns.tolist())}")
                    
                    # Preview
                    st.dataframe(df.head(10), width="stretch")
                    
                    # Save option
                    save_name = st.text_input(
                        "Save as:",
                        value="uploaded_parcels.json"
                    )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("💾 Save to Cache"):
                            output_path = Path("data") / save_name
                            output_path.parent.mkdir(exist_ok=True)
                            
                            with open(output_path, "w") as f:
                                json.dump(data, f, indent=2, default=str)
                            
                            st.success(f"Saved to {output_path}")
                            st.cache_data.clear()
                    
                    with col2:
                        if st.button("💾 Save as Main Dataset"):
                            # Save as the main file the app uses
                            output_path = Path("data") / "lanesville_parcels.json"
                            output_path.parent.mkdir(exist_ok=True)
                            
                            with open(output_path, "w") as f:
                                json.dump(data, f, indent=2, default=str)
                            
                            st.success("Saved as main dataset! The app will now use this data.")
                            st.cache_data.clear()
                            st.rerun()
                else:
                    st.error("Unsupported format. Expected a list of records or GeoJSON FeatureCollection.")
                    
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
            except Exception as e:
                st.error(f"Error processing file: {e}")

    with tab4:
        st.markdown("### ⚙️ Active Data Source")
        cfg = get_config()
        use_geojson = st.radio(
            "Preferred dataset:",
            ["GeoJSON", "Cached JSON"],
            index=0 if cfg.get("use_geojson", True) else 1,
            help="GeoJSON is preferred if available."
        )
        cfg["use_geojson"] = use_geojson == "GeoJSON"
        if st.button("Save Preference"):
            save_config(cfg)
            st.success("Saved data source preference.")
            st.cache_data.clear()
            st.rerun()
    
    # Sidebar info
    with st.sidebar:
        st.markdown("### ℹ️ About the Data")
        st.markdown(f"""
        **Greene County Tax Parcels**
        
        Source: Greene County ArcGIS
        
        Total Available: **{api_count:,}** parcels
        
        **Data includes:**
        - Owner names
        - Mailing addresses
        - Property classifications
        - Assessed values
        - Acreage
        - Parcel boundaries
        - School districts
        - Municipalities
        """)
        
        st.markdown("---")
        
        # Quick stats if data is loaded
        cache_files = get_cache_info()
        main_cache = next((cf for cf in cache_files if cf['filename'] == 'lanesville_parcels.json'), None)
        geojson_file = Path("data/Greene_County_Tax_Parcels_-8841005964405968865.geojson")
        geojson_active = False
        geojson_records = None
        if geojson_file.exists():
            try:
                with open(geojson_file, "r") as f:
                    data = json.load(f)
                geojson_records = len(data.get("features", [])) if isinstance(data, dict) else None
                geojson_active = get_config().get("use_geojson", True)
            except Exception:
                geojson_records = None
        
        if main_cache:
            st.markdown("### 📊 Current Dataset")
            st.write(f"**Records:** {main_cache['records']:,}")
            st.write(f"**Size:** {main_cache['size_mb']:.1f} MB")
            st.write(f"**Updated:** {main_cache['modified'].strftime('%Y-%m-%d')}")
        else:
            st.warning("No data loaded yet")
            st.write("Click **Fetch Data** to download")
        
        if geojson_file.exists():
            st.markdown("### 🗺️ GeoJSON Dataset")
            if geojson_records is not None:
                st.write(f"**Records:** {geojson_records:,}")
            st.write(f"**File:** {geojson_file.name}")
            st.write(f"**Active:** {'Yes' if geojson_active else 'No'}")


if __name__ == "__main__":
    main()
