"""
Owner Lookup - Detailed owner research and portfolio analysis
"""

import streamlit as st
import pandas as pd
import pydeck as pdk
from pathlib import Path
import html

from constants import CLASS_COLORS
from ui import apply_base_styles
st.set_page_config(
    page_title="Owner Lookup | Lanesville Property Finder",
    page_icon="👤",
    layout="wide"
)

apply_base_styles("""
    .owner-card {
        background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
        border: 1px solid #e94560;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    }
    .parcel-item {
        background: #0f3460;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #e94560;
    }
""")


@st.cache_data
def load_data():
    """Load parcel data"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app import load_parcel_data
    seed = st.session_state.get("sample_seed", 42)
    num_parcels = st.session_state.get("num_parcels", 500)
    return load_parcel_data(num_parcels=num_parcels, seed=seed)


def get_parcel_color(property_class):
    """Return color based on property classification"""
    if not property_class:
        return "#757575"
    return CLASS_COLORS.get(str(property_class)[0], "#757575")


def create_owner_map(parcels_df):
    """Create map showing all parcels for an owner using pydeck"""
    center_lat = parcels_df['latitude'].mean()
    center_lon = parcels_df['longitude'].mean()
    if pd.isna(center_lat) or pd.isna(center_lon):
        center_lat = 42.1856
        center_lon = -74.2848
    
    working = parcels_df.dropna(subset=["latitude", "longitude"]).copy()
    working["owner_safe"] = working["owner"].astype(str).apply(html.escape)
    working["parcel_id_safe"] = working["parcel_id"].astype(str).apply(html.escape)
    working["property_class_desc_safe"] = working["property_class_desc"].astype(str).apply(html.escape)
    working["color"] = working["property_class"].apply(get_parcel_color)
    working["polygon"] = working["coordinates"].apply(
        lambda coords: [[c[1], c[0]] for c in coords] if isinstance(coords, list) else []
    )
    
    def hex_to_rgb(color: str) -> list:
        color = color.lstrip("#")
        return [int(color[i:i+2], 16) for i in (0, 2, 4)]
    
    working["r"] = working["color"].apply(lambda c: hex_to_rgb(c)[0])
    working["g"] = working["color"].apply(lambda c: hex_to_rgb(c)[1])
    working["b"] = working["color"].apply(lambda c: hex_to_rgb(c)[2])
    
    polygon_df = working[working["polygon"].apply(lambda p: isinstance(p, list) and len(p) >= 3)]
    
    layers = []
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
            working,
            get_position="[longitude, latitude]",
            get_radius=20,
            get_fill_color=[233, 69, 96],
            pickable=True,
            opacity=0.6,
        )
    )
    
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=13,
        pitch=35,
    )
    
    tooltip = {
        "html": "<b>{parcel_id_safe}</b><br/>{property_class_desc_safe}<br/>Acres: {acreage}<br/>Assessed: ${assessed_value}",
        "style": {"backgroundColor": "#16213e", "color": "white"},
    }
    
    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/satellite-v9",
        tooltip=tooltip,
    )


def main():
    st.title("👤 Owner Lookup")
    st.markdown("*Search and analyze property portfolios by owner*")
    
    df = load_data()
    
    # Owner search
    col1, col2 = st.columns([2, 1])
    
    with col1:
        search_query = st.text_input(
            "🔍 Search Owner Name:",
            placeholder="Enter owner name..."
        )
    
    with col2:
        sort_by = st.selectbox(
            "Sort Results By:",
            ["Total Acreage", "Total Value", "Number of Parcels", "Name"]
        )
    
    # Get unique owners with stats
    owner_stats = df.groupby('owner').agg({
        'parcel_id': 'count',
        'acreage': 'sum',
        'assessed_value': 'sum',
        'annual_taxes': 'sum'
    }).reset_index()
    owner_stats.columns = ['owner', 'parcel_count', 'total_acreage', 'total_value', 'total_taxes']
    
    # Filter by search
    if search_query:
        owner_stats = owner_stats[owner_stats['owner'].str.lower().str.contains(search_query.lower())]
    
    # Sort
    sort_col = {
        "Total Acreage": "total_acreage",
        "Total Value": "total_value",
        "Number of Parcels": "parcel_count",
        "Name": "owner"
    }[sort_by]
    owner_stats = owner_stats.sort_values(sort_col, ascending=(sort_by == "Name"))
    
    st.markdown(f"*Found {len(owner_stats)} owners*")
    st.markdown("---")
    
    # Owner selection
    if len(owner_stats) > 0:
        selected_owner = st.selectbox(
            "Select Owner to View Details:",
            options=owner_stats['owner'].tolist(),
            format_func=lambda x: f"{x} ({owner_stats[owner_stats['owner']==x]['parcel_count'].values[0]} parcels)"
        )
        
        if selected_owner:
            owner_info = owner_stats[owner_stats['owner'] == selected_owner].iloc[0]
            owner_parcels = df[df['owner'] == selected_owner]
            
            st.markdown("---")
            
            # Owner summary
            st.subheader(f"📋 {selected_owner}")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Parcels", int(owner_info['parcel_count']))
            with col2:
                st.metric("Total Acreage", f"{owner_info['total_acreage']:.2f}")
            with col3:
                st.metric("Total Value", f"${owner_info['total_value']:,.0f}")
            with col4:
                st.metric("Annual Taxes", f"${owner_info['total_taxes']:,.0f}")
            
            # Map and details
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("##### 🗺️ Property Locations")
                deck = create_owner_map(owner_parcels)
                st.pydeck_chart(deck, height=400)
            
            with col2:
                st.markdown("##### 📬 Mailing Address")
                first_parcel = owner_parcels.iloc[0]
                st.write(f"{first_parcel['mailing_address']}")
                st.write(f"{first_parcel['mailing_city']}, {first_parcel['mailing_state']} {first_parcel['mailing_zip']}")
                
                st.markdown("##### 📊 Property Breakdown")
                type_breakdown = owner_parcels['property_class_desc'].value_counts()
                for prop_type, count in type_breakdown.items():
                    st.write(f"• {prop_type}: {count}")
            
            st.markdown("---")
            
            # Individual parcels
            st.markdown("##### 🏠 Individual Parcels")
            
            for _, parcel in owner_parcels.iterrows():
                with st.expander(f"📍 {parcel['parcel_id']} - {parcel['property_class_desc']} ({parcel['acreage']:.2f} ac)"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**SBL:** {parcel['sbl']}")
                        st.write(f"**Class:** {parcel['property_class']}")
                        st.write(f"**Acreage:** {parcel['acreage']:.2f}")
                    
                    with col2:
                        st.write(f"**Assessed Value:** ${parcel['assessed_value']:,}")
                        st.write(f"**Land Value:** ${parcel['land_value']:,}")
                        st.write(f"**Improvement:** ${parcel['improvement_value']:,}")
                    
                    with col3:
                        st.write(f"**Annual Taxes:** ${parcel['annual_taxes']:,.2f}")
                        st.write(f"**Deed Book:** {parcel['deed_book']}")
                        st.write(f"**Deed Page:** {parcel['deed_page']}")
                    
                    if parcel['last_sale_price']:
                        st.write(f"**Last Sale:** ${parcel['last_sale_price']:,} on {parcel['last_sale_date']}")
            
            # Export options
            st.markdown("---")
            st.markdown("##### 📥 Export Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                csv = owner_parcels.to_csv(index=False)
                st.download_button(
                    "📄 Download CSV",
                    data=csv,
                    file_name=f"{selected_owner.replace(' ', '_')}_parcels.csv",
                    mime="text/csv"
                )
            
            with col2:
                import json
                json_data = owner_parcels.to_json(orient='records', default_handler=str)
                st.download_button(
                    "📄 Download JSON",
                    data=json_data,
                    file_name=f"{selected_owner.replace(' ', '_')}_parcels.json",
                    mime="application/json"
                )
    
    else:
        st.info("No owners found matching your search criteria.")
    
    # Quick stats in sidebar
    with st.sidebar:
        st.markdown("### 📊 Quick Stats")
        st.write(f"**Total Owners:** {len(owner_stats)}")
        st.write(f"**Total Parcels:** {len(df)}")
        
        st.markdown("---")
        st.markdown("### 🏆 Top Landowners")
        top_owners = owner_stats.nlargest(5, 'total_acreage')
        for _, owner in top_owners.iterrows():
            st.write(f"• {owner['owner'][:20]}... ({owner['total_acreage']:.0f} ac)")


if __name__ == "__main__":
    main()
