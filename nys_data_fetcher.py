"""
NYS Parcel Data Fetcher
Fetches real tax parcel data from NYS GIS REST services
"""

import requests
import pandas as pd
import json
from pathlib import Path
from typing import Optional, Dict, List
import time

from constants import PROPERTY_CLASS_DESC
# NYS GIS Tax Parcel Service URLs
NYS_TAX_PARCEL_SERVICE = "https://services6.arcgis.com/DZHaqZm9cxOD4CWM/arcgis/rest/services"

# Service endpoints to try (NYS updates these periodically)
PARCEL_ENDPOINTS = [
    "/NYS_Tax_Parcels_Public/FeatureServer/0",
    "/Tax_Parcels_Public/FeatureServer/0", 
    "/NYS_Tax_Parcels/FeatureServer/0",
]

# Greene County bounding box (covers all of Greene County)
GREENE_COUNTY_BBOX = {
    "xmin": -74.55,
    "ymin": 42.05,
    "xmax": -73.78,
    "ymax": 42.45
}

# Lanesville/Hunter area bounding box (more focused)
LANESVILLE_BBOX = {
    "xmin": -74.40,
    "ymin": 42.10,
    "xmax": -74.15,
    "ymax": 42.25
}

# Field mapping from NYS GIS to our schema
FIELD_MAPPING = {
    "PRINT_KEY": "parcel_id",
    "PARCEL_ADDR": "property_address",
    "OWNER1": "owner",
    "MAIL_ADDR": "mailing_address",
    "MAIL_CITY": "mailing_city",
    "MAIL_STATE": "mailing_state",
    "MAIL_ZIP": "mailing_zip",
    "PROP_CLASS": "property_class",
    "LAND_AV": "land_value",
    "TOTAL_AV": "assessed_value",
    "FULL_MV": "full_market_value",
    "CALC_ACRES": "acreage",
    "MUNI_NAME": "municipality",
    "COUNTY_NAME": "county",
    "SCHOOL_NAME": "school_district",
    "SBL": "sbl",
    "SWIS": "swis_code",
    # Alternative field names
    "NAME": "owner",
    "OWNER_NAME": "owner",
    "ACRES": "acreage",
    "ASSESSED_VALUE": "assessed_value",
    "LAND_VALUE": "land_value",
}



class NYSParcelFetcher:
    """Fetch parcel data from NYS GIS services"""
    
    def __init__(self, cache_dir: str = "data"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.base_url = NYS_TAX_PARCEL_SERVICE
        
    def _find_working_endpoint(self) -> Optional[str]:
        """Find a working parcel service endpoint"""
        for endpoint in PARCEL_ENDPOINTS:
            url = f"{self.base_url}{endpoint}"
            try:
                response = requests.get(f"{url}?f=json", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if "name" in data or "fields" in data:
                        print(f"Found working endpoint: {endpoint}")
                        return url
            except:
                continue
        return None
    
    def fetch_parcels(
        self,
        bbox: Dict = None,
        county: str = "Greene",
        max_records: int = 5000,
        progress_callback=None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch parcels from NYS GIS service
        
        Args:
            bbox: Bounding box dict with xmin, ymin, xmax, ymax
            county: County name to filter (default Greene)
            max_records: Maximum records to fetch
            progress_callback: Optional callback for progress updates
            
        Returns:
            DataFrame with parcel data or None if fetch fails
        """
        bbox = bbox or LANESVILLE_BBOX
        
        # Find working endpoint
        base_url = self._find_working_endpoint()
        if not base_url:
            print("Could not find working NYS GIS endpoint")
            return None
        
        url = f"{base_url}/query"
        
        all_features = []
        offset = 0
        batch_size = 1000  # NYS typically limits to 1000 per request
        
        while offset < max_records:
            params = {
                "where": f"COUNTY_NAME='{county}'" if county else "1=1",
                "geometry": json.dumps({
                    "xmin": bbox["xmin"],
                    "ymin": bbox["ymin"],
                    "xmax": bbox["xmax"],
                    "ymax": bbox["ymax"],
                    "spatialReference": {"wkid": 4326}
                }),
                "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": min(batch_size, max_records - offset)
            }
            
            try:
                if progress_callback:
                    progress_callback(f"Fetching records {offset} to {offset + batch_size}...")
                    
                response = requests.get(url, params=params, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                
                if "features" not in data:
                    print(f"No features in response: {data.get('error', 'Unknown error')}")
                    break
                    
                features = data["features"]
                
                if not features:
                    break
                    
                all_features.extend(features)
                
                if progress_callback:
                    progress_callback(f"Retrieved {len(all_features)} parcels so far...")
                
                # Check if we got fewer than requested (end of data)
                if len(features) < batch_size:
                    break
                    
                offset += batch_size
                time.sleep(0.5)  # Rate limiting
                
            except requests.RequestException as e:
                print(f"Request error at offset {offset}: {e}")
                break
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                break
        
        if not all_features:
            return None
            
        # Convert to DataFrame
        df = self._process_features(all_features)
        
        if progress_callback:
            progress_callback(f"Processed {len(df)} parcels")
            
        return df
    
    def _process_features(self, features: List[Dict]) -> pd.DataFrame:
        """Process GeoJSON features into DataFrame"""
        records = []
        
        for feature in features:
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            
            # Map fields
            record = {}
            for source_field, target_field in FIELD_MAPPING.items():
                if source_field in props:
                    record[target_field] = props[source_field]
            
            # Get property class description
            prop_class = str(record.get("property_class", ""))
            record["property_class_desc"] = PROPERTY_CLASS_DESC.get(
                prop_class, 
                PROPERTY_CLASS_DESC.get(prop_class[:2] + "0", "Unknown")
            )
            
            # Process geometry
            if geometry and geometry.get("type") == "Polygon":
                coords = geometry.get("coordinates", [[]])[0]
                # Convert to [lat, lon] format for Folium
                record["coordinates"] = [[c[1], c[0]] for c in coords[:50]]  # Limit points
                
                # Calculate centroid
                if coords:
                    lons = [c[0] for c in coords]
                    lats = [c[1] for c in coords]
                    record["longitude"] = sum(lons) / len(lons)
                    record["latitude"] = sum(lats) / len(lats)
            elif geometry and geometry.get("type") == "MultiPolygon":
                # Use first polygon of multipolygon
                coords = geometry.get("coordinates", [[[]]])[0][0]
                record["coordinates"] = [[c[1], c[0]] for c in coords[:50]]
                
                if coords:
                    lons = [c[0] for c in coords]
                    lats = [c[1] for c in coords]
                    record["longitude"] = sum(lons) / len(lons)
                    record["latitude"] = sum(lats) / len(lats)
            else:
                record["coordinates"] = []
                record["latitude"] = None
                record["longitude"] = None
            
            # Fill in missing fields with defaults
            record.setdefault("owner", "Unknown")
            record.setdefault("parcel_id", props.get("OBJECTID", "N/A"))
            record.setdefault("sbl", "")
            record.setdefault("mailing_address", "")
            record.setdefault("mailing_city", "")
            record.setdefault("mailing_state", "NY")
            record.setdefault("mailing_zip", "")
            record.setdefault("property_class", "")
            record.setdefault("acreage", 0)
            record.setdefault("assessed_value", 0)
            record.setdefault("land_value", 0)
            record.setdefault("municipality", "")
            record.setdefault("county", "Greene")
            record.setdefault("school_district", "")
            
            # Calculate derived fields
            if record["assessed_value"] and record["land_value"]:
                record["improvement_value"] = int(record["assessed_value"]) - int(record["land_value"])
            else:
                record["improvement_value"] = 0
                
            record["annual_taxes"] = round(float(record.get("assessed_value", 0) or 0) * 0.025, 2)
            record["tax_year"] = 2024
            record["deed_book"] = ""
            record["deed_page"] = ""
            record["last_sale_date"] = ""
            record["last_sale_price"] = None
            
            records.append(record)
        
        return pd.DataFrame(records)
    
    def save_to_cache(self, df: pd.DataFrame, filename: str = "lanesville_parcels.json"):
        """Save DataFrame to cache file"""
        output_path = self.cache_dir / filename
        
        records = df.to_dict(orient="records")
        
        with open(output_path, "w") as f:
            json.dump(records, f, indent=2, default=str)
            
        print(f"Saved {len(records)} parcels to {output_path}")
        return output_path
    
    def load_from_cache(self, filename: str = "lanesville_parcels.json") -> Optional[pd.DataFrame]:
        """Load DataFrame from cache file"""
        cache_path = self.cache_dir / filename
        
        if cache_path.exists():
            with open(cache_path, "r") as f:
                records = json.load(f)
            return pd.DataFrame(records)
        return None


def fetch_greene_county_parcels(
    area: str = "lanesville",
    max_records: int = 5000,
    use_cache: bool = True,
    progress_callback=None
) -> pd.DataFrame:
    """
    Convenience function to fetch Greene County parcel data
    
    Args:
        area: "lanesville" for focused area, "greene" for full county
        max_records: Maximum number of records to fetch
        use_cache: Whether to use cached data if available
        progress_callback: Optional callback for progress updates
        
    Returns:
        DataFrame with parcel data
    """
    fetcher = NYSParcelFetcher()
    
    cache_file = f"{area}_parcels.json"
    
    # Check cache first
    if use_cache:
        df = fetcher.load_from_cache(cache_file)
        if df is not None:
            if progress_callback:
                progress_callback(f"Loaded {len(df)} parcels from cache")
            return df
    
    # Fetch from API
    bbox = LANESVILLE_BBOX if area == "lanesville" else GREENE_COUNTY_BBOX
    
    df = fetcher.fetch_parcels(
        bbox=bbox,
        county="Greene",
        max_records=max_records,
        progress_callback=progress_callback
    )
    
    if df is not None and not df.empty:
        # Save to cache
        fetcher.save_to_cache(df, cache_file)
        return df
    
    return None


if __name__ == "__main__":
    # Test fetch
    print("Fetching Greene County parcels...")
    df = fetch_greene_county_parcels(
        area="lanesville",
        max_records=1000,
        use_cache=False,
        progress_callback=print
    )
    
    if df is not None:
        print(f"\nSuccessfully fetched {len(df)} parcels")
        print(f"Columns: {df.columns.tolist()}")
        print(f"\nSample:")
        print(df[['parcel_id', 'owner', 'acreage', 'assessed_value']].head(10))
    else:
        print("Failed to fetch data")
