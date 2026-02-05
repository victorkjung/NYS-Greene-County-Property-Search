"""
Data Loader for Lanesville Property Finder
Utilities for loading real parcel data from official NYS/Greene County sources
"""

import requests
import json
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import shape, mapping
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GreeneCountyParcelLoader:
    """
    Load parcel data from Greene County and NYS GIS sources.
    
    Official data sources:
    - NYS GIS Clearinghouse: https://gis.ny.gov/
    - Greene County Real Property Tax Services
    - NYS Tax Parcel Centroids and Polygons
    """
    
    # NYS GIS REST Service endpoints
    NYS_PARCEL_SERVICE = "https://services6.arcgis.com/DZHaqZm9cxOD4CWM/arcgis/rest/services"
    
    # Greene County FIPS code: 39
    GREENE_COUNTY_FIPS = "39"
    
    # Town of Hunter code (where Lanesville is located)
    HUNTER_TOWN_CODE = "040"  # Example - verify with county
    
    # Lanesville approximate bounding box
    LANESVILLE_BBOX = {
        "min_lon": -74.35,
        "max_lon": -74.22,
        "min_lat": 42.14,
        "max_lat": 42.22
    }
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
    def fetch_nys_parcels(self, bbox: dict = None) -> gpd.GeoDataFrame:
        """
        Fetch parcel data from NYS GIS services.
        
        Note: The actual endpoint and parameters may need to be adjusted
        based on the current NYS GIS service configuration.
        """
        bbox = bbox or self.LANESVILLE_BBOX
        
        # NYS Tax Parcel service (example endpoint - verify current URL)
        url = f"{self.NYS_PARCEL_SERVICE}/NYS_Tax_Parcels_Public/FeatureServer/0/query"
        
        params = {
            "where": f"COUNTY_NAME='Greene'",
            "geometry": f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}",
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "geojson"
        }
        
        try:
            logger.info(f"Fetching parcels from NYS GIS...")
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            
            geojson = response.json()
            gdf = gpd.GeoDataFrame.from_features(geojson['features'])
            gdf.set_crs(epsg=4326, inplace=True)
            
            logger.info(f"Retrieved {len(gdf)} parcels")
            return gdf
            
        except requests.RequestException as e:
            logger.error(f"Error fetching NYS parcel data: {e}")
            return None
    
    def load_shapefile(self, shapefile_path: str) -> gpd.GeoDataFrame:
        """
        Load parcel data from a local shapefile.
        
        Greene County may provide parcel shapefiles for download.
        """
        try:
            gdf = gpd.read_file(shapefile_path)
            
            # Reproject to WGS84 if needed
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            
            logger.info(f"Loaded {len(gdf)} parcels from shapefile")
            return gdf
            
        except Exception as e:
            logger.error(f"Error loading shapefile: {e}")
            return None
    
    def load_assessment_roll(self, csv_path: str) -> pd.DataFrame:
        """
        Load assessment roll data from CSV.
        
        Greene County provides annual assessment rolls that can be joined
        with parcel geometry data.
        """
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} assessment records")
            return df
        except Exception as e:
            logger.error(f"Error loading assessment roll: {e}")
            return None
    
    def process_parcels(self, gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        """
        Process GeoDataFrame to standard format for the app.
        """
        records = []
        
        for idx, row in gdf.iterrows():
            # Extract centroid for marker placement
            centroid = row.geometry.centroid
            
            # Get exterior coordinates for polygon display
            if row.geometry.geom_type == 'Polygon':
                coords = [list(c)[::-1] for c in row.geometry.exterior.coords]
            elif row.geometry.geom_type == 'MultiPolygon':
                # Use the largest polygon
                largest = max(row.geometry.geoms, key=lambda x: x.area)
                coords = [list(c)[::-1] for c in largest.exterior.coords]
            else:
                coords = [[centroid.y, centroid.x]]
            
            # Map fields (adjust based on actual field names in source data)
            record = {
                "parcel_id": row.get('PRINT_KEY', row.get('SBL', f'PARCEL_{idx}')),
                "sbl": row.get('SBL', row.get('SWIS_PRINT_KEY', '')),
                "owner": row.get('OWNER_NAME', row.get('NAME', 'Unknown')),
                "mailing_address": row.get('MAIL_ADDR', row.get('ADDRESS', '')),
                "mailing_city": row.get('MAIL_CITY', row.get('PO', '')),
                "mailing_state": row.get('MAIL_STATE', 'NY'),
                "mailing_zip": str(row.get('MAIL_ZIP', row.get('ZIP', ''))),
                "property_class": str(row.get('PROP_CLASS', row.get('LAND_USE', '999'))),
                "property_class_desc": row.get('CLASS_DESC', row.get('LAND_USE_DESC', 'Unknown')),
                "acreage": float(row.get('CALC_ACRES', row.get('ACRES', 0))),
                "assessed_value": int(row.get('TOTAL_AV', row.get('ASSESSED_VALUE', 0))),
                "land_value": int(row.get('LAND_AV', 0)),
                "improvement_value": int(row.get('IMPR_AV', 0)),
                "tax_year": int(row.get('TAX_YEAR', 2024)),
                "annual_taxes": float(row.get('TAX_AMT', 0)),
                "school_district": row.get('SCHOOL_NAME', 'Unknown'),
                "municipality": row.get('MUNI_NAME', row.get('CITY', 'Hunter')),
                "county": "Greene",
                "latitude": centroid.y,
                "longitude": centroid.x,
                "coordinates": coords[:50],  # Limit coordinate points for performance
                "deed_book": str(row.get('DEED_BOOK', '')),
                "deed_page": str(row.get('DEED_PAGE', '')),
                "last_sale_date": row.get('SALE_DATE', ''),
                "last_sale_price": row.get('SALE_PRICE', None)
            }
            records.append(record)
        
        return pd.DataFrame(records)
    
    def save_processed_data(self, df: pd.DataFrame, filename: str = "lanesville_parcels.json"):
        """Save processed parcel data to JSON for the app."""
        output_path = self.data_dir / filename
        
        # Convert to JSON-serializable format
        records = df.to_dict(orient='records')
        
        with open(output_path, 'w') as f:
            json.dump(records, f, indent=2, default=str)
        
        logger.info(f"Saved {len(records)} parcels to {output_path}")
        return output_path
    
    def filter_lanesville(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Filter parcels to Lanesville area using bounding box.
        """
        bbox = self.LANESVILLE_BBOX
        
        # Create bounding box filter
        filtered = gdf.cx[
            bbox['min_lon']:bbox['max_lon'],
            bbox['min_lat']:bbox['max_lat']
        ]
        
        logger.info(f"Filtered to {len(filtered)} parcels in Lanesville area")
        return filtered


def download_and_process():
    """
    Main function to download and process parcel data.
    
    Usage:
        python data_loader.py
    
    Or in Python:
        from data_loader import download_and_process
        download_and_process()
    """
    loader = GreeneCountyParcelLoader()
    
    # Try to fetch from NYS GIS
    gdf = loader.fetch_nys_parcels()
    
    if gdf is not None and len(gdf) > 0:
        # Filter to Lanesville area
        gdf_filtered = loader.filter_lanesville(gdf)
        
        # Process to standard format
        df = loader.process_parcels(gdf_filtered)
        
        # Save for app use
        loader.save_processed_data(df)
        
        print(f"✅ Successfully processed {len(df)} parcels")
        return df
    else:
        print("⚠️ Could not fetch data from NYS GIS. Using sample data.")
        print("\nTo use real data, you can:")
        print("1. Download parcel shapefiles from Greene County GIS")
        print("2. Download from NYS GIS Clearinghouse: https://gis.ny.gov/")
        print("3. Request data from Greene County Real Property office")
        return None


if __name__ == "__main__":
    download_and_process()
