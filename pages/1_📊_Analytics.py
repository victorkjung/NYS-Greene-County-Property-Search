"""
Analytics Dashboard for Lanesville Property Finder
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json

st.set_page_config(
    page_title="Analytics | Lanesville Property Finder",
    page_icon="📊",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #1a1a2e;
    }
    h1, h2, h3 {
        color: #e94560 !important;
    }
    .metric-card {
        background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
        border: 1px solid #e94560;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    """Load parcel data"""
    # Import from main app
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app import load_parcel_data
    return load_parcel_data()


def main():
    st.title("📊 Lanesville Property Analytics")
    st.markdown("*Comprehensive analysis of property ownership and values*")
    
    df = load_data()
    
    # Top-level metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Parcels", f"{len(df):,}")
    with col2:
        st.metric("Total Acreage", f"{df['acreage'].sum():,.1f}")
    with col3:
        st.metric("Total Assessed Value", f"${df['assessed_value'].sum():,.0f}")
    with col4:
        st.metric("Unique Owners", df['owner'].nunique())
    with col5:
        st.metric("Avg. Parcel Size", f"{df['acreage'].mean():.1f} ac")
    
    st.markdown("---")
    
    # Charts row 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Property Types Distribution")
        prop_counts = df['property_class_desc'].value_counts().head(10)
        
        fig = px.pie(
            values=prop_counts.values,
            names=prop_counts.index,
            color_discrete_sequence=px.colors.sequential.RdBu,
            hole=0.4
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#eaeaea'
        )
        st.plotly_chart(fig, width="stretch")
    
    with col2:
        st.subheader("Assessed Value by Property Type")
        value_by_type = df.groupby('property_class_desc')['assessed_value'].sum().sort_values(ascending=True).tail(10)
        
        fig = px.bar(
            x=value_by_type.values,
            y=value_by_type.index,
            orientation='h',
            color=value_by_type.values,
            color_continuous_scale='RdBu'
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#eaeaea',
            showlegend=False,
            xaxis_title="Total Assessed Value ($)",
            yaxis_title=""
        )
        st.plotly_chart(fig, width="stretch")
    
    # Charts row 2
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Acreage Distribution")
        fig = px.histogram(
            df,
            x='acreage',
            nbins=30,
            color_discrete_sequence=['#e94560']
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#eaeaea',
            xaxis_title="Acreage",
            yaxis_title="Number of Parcels"
        )
        st.plotly_chart(fig, width="stretch")
    
    with col2:
        st.subheader("Value vs. Acreage")
        fig = px.scatter(
            df,
            x='acreage',
            y='assessed_value',
            color='property_class_desc',
            hover_data=['owner', 'parcel_id'],
            opacity=0.6
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#eaeaea',
            xaxis_title="Acreage",
            yaxis_title="Assessed Value ($)",
            legend_title="Property Type"
        )
        st.plotly_chart(fig, width="stretch")
    
    st.markdown("---")
    
    # Top owners analysis
    st.subheader("🏆 Top Property Owners")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### By Total Acreage")
        top_by_acres = df.groupby('owner').agg({
            'acreage': 'sum',
            'parcel_id': 'count',
            'assessed_value': 'sum'
        }).sort_values('acreage', ascending=False).head(10)
        top_by_acres.columns = ['Total Acres', 'Parcels', 'Total Value']
        top_by_acres['Total Value'] = top_by_acres['Total Value'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(top_by_acres, width="stretch")
    
    with col2:
        st.markdown("##### By Assessed Value")
        top_by_value = df.groupby('owner').agg({
            'assessed_value': 'sum',
            'parcel_id': 'count',
            'acreage': 'sum'
        }).sort_values('assessed_value', ascending=False).head(10)
        top_by_value.columns = ['Total Value', 'Parcels', 'Total Acres']
        top_by_value['Total Value'] = top_by_value['Total Value'].apply(lambda x: f"${x:,.0f}")
        st.dataframe(top_by_value, width="stretch")
    
    st.markdown("---")
    
    # Tax analysis
    st.subheader("💰 Tax Revenue Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_taxes = df['annual_taxes'].sum()
        st.metric("Estimated Annual Tax Revenue", f"${total_taxes:,.0f}")
    
    with col2:
        avg_tax = df['annual_taxes'].mean()
        st.metric("Average Tax per Parcel", f"${avg_tax:,.0f}")
    
    with col3:
        tax_per_acre = total_taxes / df['acreage'].sum()
        st.metric("Tax per Acre (avg)", f"${tax_per_acre:,.2f}")
    
    # Tax by property type
    tax_by_type = df.groupby('property_class_desc')['annual_taxes'].sum().sort_values(ascending=False).head(8)
    
    fig = px.bar(
        x=tax_by_type.index,
        y=tax_by_type.values,
        color=tax_by_type.values,
        color_continuous_scale='RdBu'
    )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#eaeaea',
        xaxis_title="Property Type",
        yaxis_title="Annual Tax Revenue ($)",
        showlegend=False
    )
    st.plotly_chart(fig, width="stretch")
    
    st.markdown("---")
    
    # Mailing location analysis
    st.subheader("📬 Owner Mailing Locations")
    
    location_counts = df['mailing_city'].value_counts().head(15)
    
    fig = px.bar(
        x=location_counts.values,
        y=location_counts.index,
        orientation='h',
        color=location_counts.values,
        color_continuous_scale='RdBu'
    )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#eaeaea',
        xaxis_title="Number of Properties",
        yaxis_title="Mailing City",
        showlegend=False,
        height=500
    )
    st.plotly_chart(fig, width="stretch")
    
    # Local vs non-local analysis
    local_cities = ['Lanesville', 'Hunter', 'Tannersville', 'Phoenicia', 'Prattsville']
    df['owner_type'] = df['mailing_city'].apply(
        lambda x: 'Local' if x in local_cities else 'Non-Local'
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        owner_type_counts = df['owner_type'].value_counts()
        st.metric("Local Owners", f"{owner_type_counts.get('Local', 0)} ({owner_type_counts.get('Local', 0)/len(df)*100:.1f}%)")
    
    with col2:
        st.metric("Non-Local Owners", f"{owner_type_counts.get('Non-Local', 0)} ({owner_type_counts.get('Non-Local', 0)/len(df)*100:.1f}%)")


if __name__ == "__main__":
    main()
