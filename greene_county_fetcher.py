"""
Greene County Tax Parcels Data Fetcher
Fetches all parcel data from Greene County ArcGIS REST API

API Endpoint: https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/Greene_County_Tax_Parcels/FeatureServer/0
Total Records: ~38,370 parcels
"""

import requests
import pandas as pd
import json
from pathlib import Path
from typing import Optional, Callable
import time

# Greene County Tax Parcels API
GREENE_COUNTY_API = "https://services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/Greene_County_Tax_Parcels/FeatureServer/0"

# ArcGIS typically limits to 1000-2000 records per request
BATCH_SIZE = 1000

# Property class descriptions
PROPERTY_CLASS_DESC = {
    "100": "Agricultural",
    "105": "Agricultural Vacant",
    "110": "Livestock",
    "112": "Dairy Farm",
    "113": "Cattle Farm",
    "117": "Horse Farm",
    "120": "Field Crops",
    "200": "Residential",
    "210": "One Family Residential",
    "220": "Two Family Residential",
    "230": "Three Family Residential",
    "240": "Rural Residence",
    "250": "Estate",
    "260": "Seasonal Residence",
    "270": "Mobile Home",
    "280": "Multiple Residences",
    "281": "Multiple Res - 2 to 3 Units",
    "283": "Multiple Res - 4 to 6 Units",
    "300": "Vacant Land",
    "311": "Vacant Land - Residential",
    "312": "Vacant Land - Under 10 Acres",
    "314": "Vacant Land - Rural",
    "322": "Vacant Land - Over 10 Acres",
    "323": "Vacant Land - Forest",
    "330": "Vacant Land - Commercial",
    "340": "Vacant Land - Industrial",
    "400": "Commercial",
    "411": "Apartments",
    "421": "Restaurant",
    "422": "Diner/Luncheonette",
    "425": "Bar",
    "430": "Motel",
    "432": "Hotel",
    "449": "Other Storage",
    "464": "Office Building",
    "480": "Multiple Use",
    "485": "One Story Small Structure",
    "500": "Recreation & Entertainment",
    "534": "Social Organization",
    "570": "Marina",
    "582": "Camping Facility",
    "590": "Park",
    "600": "Community Service",
    "612": "School",
    "620": "Religious",
    "632": "Health Facility",
    "651": "Highway Garage",
    "662": "Police/Fire Station",
    "700": "Industrial",
    "710": "Manufacturing",
    "800": "Public Service",
    "822": "Water Supply",
    "831": "Telephone",
    "900": "Wild/Forest/Conservation",
    "910": "Private Forest",
    "911": "Forest Land - Private",
    "920": "State Forest",
    "930": "State Owned - Other",
    "931": "State Owned - Forest",
    "940": "State Reforestation",
    "941": "State Land - Reforestation",
    "942": "State Land - Wilderness",
    "961": "State Owned - Other Agency",
    "962": "State Owned - DEC",
    "963": "State Park",
    "970": "Federal",
    "980": "County Land",
    "990": "Town Land",
}


def get_record_count(municipality: Optional[str] = None) -> int:
    """Get total number of records in the dataset
    
    Args:
        municipality: Optional municipality name to filter (e.g., "Hunter", "Catskill")
    """
    url = f"{GREENE_COUNTY_API}/query"
    
    # Build where clause
    if municipality:
        where_clause = f"MUNI_NAME='{municipality}' OR MuniName='{municipality}' OR MUNICIPALITY='{municipality}'"
    else:
        where_clause = "1=1"
    
    params = {
        "where": where_clause,
        "returnCountOnly": "true",
        "f": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("count", 0)
    except Exception as e:
        print(f"Error getting record count: {e}")
        return 0


def get_available_municipalities() -> list:
    """Get list of all municipalities in the dataset"""
    url = f"{GREENE_COUNTY_API}/query"
    params = {
        "where": "1=1",
        "outFields": "MUNI_NAME,MuniName,MUNICIPALITY",
        "returnDistinctValues": "true",
        "returnGeometry": "false",
        "f": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        municipalities = set()
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            muni = attrs.get("MUNI_NAME") or attrs.get("MuniName") or attrs.get("MUNICIPALITY")
            if muni:
                municipalities.add(muni)
        
        return sorted(list(municipalities))
    except Exception as e:
        print(f"Error getting municipalities: {e}")
        return []


def fetch_all_parcels(
    progress_callback: Optional[Callable] = None,
    max_records: Optional[int] = None,
    municipality: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    Fetch all parcels from Greene County API
    
    Args:
        progress_callback: Function to call with progress updates
        max_records: Optional limit on number of records (None = all)
        municipality: Optional municipality to filter (e.g., "Hunter" for Lanesville area)
        
    Returns:
        DataFrame with all parcel data
    """
    
    # Build where clause
    if municipality:
        where_clause = f"MUNI_NAME='{municipality}' OR MuniName='{municipality}' OR MUNICIPALITY='{municipality}'"
    else:
        where_clause = "1=1"
    
    # Get total count
    total_count = get_record_count(municipality)
    if total_count == 0:
        if progress_callback:
            progress_callback(f"Could not get record count from API (municipality: {municipality})")
        return None
    
    if progress_callback:
        if municipality:
            progress_callback(f"Found {total_count:,} parcels in {municipality}")
        else:
            progress_callback(f"Found {total_count:,} total parcels in Greene County")
    
    # Apply limit if specified
    if max_records:
        total_to_fetch = min(total_count, max_records)
    else:
        total_to_fetch = total_count
    
    url = f"{GREENE_COUNTY_API}/query"
    all_features = []
    offset = 0
    
    while offset < total_to_fetch:
        params = {
            "where": where_clause,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": min(BATCH_SIZE, total_to_fetch - offset)
        }
        
        try:
            if progress_callback:
                pct = (offset / total_to_fetch) * 100
                progress_callback(f"Fetching parcels {offset:,} - {min(offset + BATCH_SIZE, total_to_fetch):,} of {total_to_fetch:,} ({pct:.1f}%)")
            
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for errors
            if "error" in data:
                if progress_callback:
                    progress_callback(f"API Error: {data['error'].get('message', 'Unknown error')}")
                break
            
            features = data.get("features", [])
            
            if not features:
                break
            
            all_features.extend(features)
            
            # Check if we got fewer than requested (end of data)
            if len(features) < BATCH_SIZE:
                break
            
            offset += BATCH_SIZE
            
            # Rate limiting - be nice to the server
            time.sleep(0.3)
            
        except requests.exceptions.Timeout:
            if progress_callback:
                progress_callback(f"Timeout at offset {offset}, retrying...")
            time.sleep(2)
            continue
        except requests.RequestException as e:
            if progress_callback:
                progress_callback(f"Request error at offset {offset}: {e}")
            break
        except json.JSONDecodeError as e:
            if progress_callback:
                progress_callback(f"JSON decode error: {e}")
            break
    
    if not all_features:
        if progress_callback:
            progress_callback("No features retrieved")
        return None
    
    if progress_callback:
        progress_callback(f"Processing {len(all_features):,} parcels...")
    
    # Convert to DataFrame
    df = process_features(all_features)
    
    if progress_callback:
        progress_callback(f"Successfully processed {len(df):,} parcels")
    
    return df


def process_features(features: list) -> pd.DataFrame:
    """Process ArcGIS features into DataFrame"""
    records = []
    
    for feature in features:
        attrs = feature.get("attributes", {})
        geometry = feature.get("geometry", {})
        
        # Map fields - adjust based on actual field names in the API
        # Common field names in NYS parcel data
        record = {
            "parcel_id": (
                attrs.get("PRINT_KEY") or 
                attrs.get("PrintKey") or 
                attrs.get("PARCEL_ID") or 
                attrs.get("ParcelID") or 
                attrs.get("SBL") or
                str(attrs.get("OBJECTID", ""))
            ),
            "sbl": (
                attrs.get("SBL") or 
                attrs.get("SWIS_SBL") or 
                attrs.get("PARCEL_ID") or
                ""
            ),
            "owner": (
                attrs.get("OWNER") or
                attrs.get("Owner") or
                attrs.get("OWNER1") or 
                attrs.get("OWNER_NAME") or 
                attrs.get("NAME") or
                attrs.get("OwnerName") or
                "Unknown"
            ),
            "mailing_address": (
                attrs.get("MAIL_ADDR") or 
                attrs.get("MailAddr") or
                attrs.get("MAILING_ADDRESS") or
                attrs.get("Mail_Addr") or
                ""
            ),
            "mailing_city": (
                attrs.get("MAIL_CITY") or 
                attrs.get("MailCity") or
                attrs.get("MAILING_CITY") or
                attrs.get("PO") or
                ""
            ),
            "mailing_state": (
                attrs.get("MAIL_STATE") or 
                attrs.get("MailState") or
                attrs.get("MAILING_STATE") or
                "NY"
            ),
            "mailing_zip": str(
                attrs.get("MAIL_ZIP") or 
                attrs.get("MailZip") or
                attrs.get("MAILING_ZIP") or
                attrs.get("ZIP") or
                ""
            ),
            "property_address": (
                attrs.get("PROP_ADDR") or
                attrs.get("PropAddr") or
                attrs.get("PROPERTY_ADDRESS") or
                attrs.get("LOC_ADDR") or
                attrs.get("LOCATION") or
                ""
            ),
            "property_class": str(
                attrs.get("PROP_CLASS") or 
                attrs.get("PropClass") or
                attrs.get("PROPERTY_CLASS") or
                attrs.get("LUC") or
                attrs.get("CLASS") or
                ""
            ),
            "acreage": float(
                attrs.get("ACRES") or 
                attrs.get("Acres") or
                attrs.get("CALC_ACRES") or 
                attrs.get("ACREAGE") or
                attrs.get("GIS_ACRES") or
                0
            ),
            "assessed_value": int(
                attrs.get("TOTAL_AV") or 
                attrs.get("TotalAV") or
                attrs.get("ASSESSED_VALUE") or
                attrs.get("FULL_VAL") or
                attrs.get("TOTAL_VALUE") or
                0
            ),
            "land_value": int(
                attrs.get("LAND_AV") or 
                attrs.get("LandAV") or
                attrs.get("LAND_VALUE") or
                0
            ),
            "municipality": (
                attrs.get("MUNI_NAME") or 
                attrs.get("MuniName") or
                attrs.get("MUNICIPALITY") or
                attrs.get("TOWN") or
                attrs.get("CITY") or
                ""
            ),
            "school_district": (
                attrs.get("SCHOOL_NAME") or 
                attrs.get("SchoolName") or
                attrs.get("SCHOOL") or
                attrs.get("SCHOOL_DIST") or
                ""
            ),
            "swis_code": (
                attrs.get("SWIS") or
                attrs.get("SwisCode") or
                attrs.get("SWIS_CODE") or
                ""
            ),
        }
        
        # Get property class description
        prop_class = record["property_class"]
        if prop_class:
            record["property_class_desc"] = PROPERTY_CLASS_DESC.get(
                prop_class,
                PROPERTY_CLASS_DESC.get(prop_class[:2] + "0" if len(prop_class) >= 2 else prop_class, 
                PROPERTY_CLASS_DESC.get(prop_class[0] + "00" if len(prop_class) >= 1 else "", "Unknown"))
            )
        else:
            record["property_class_desc"] = "Unknown"
        
        # Process geometry (rings format from ArcGIS)
        if geometry and "rings" in geometry:
            rings = geometry.get("rings", [[]])
            if rings and rings[0]:
                coords = rings[0]
                # Convert to [lat, lon] format for Folium (ArcGIS uses [x, y] = [lon, lat])
                record["coordinates"] = [[c[1], c[0]] for c in coords[:100]]  # Limit points
                
                # Calculate centroid
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                record["longitude"] = sum(lons) / len(lons)
                record["latitude"] = sum(lats) / len(lats)
            else:
                record["coordinates"] = []
                record["latitude"] = None
                record["longitude"] = None
        else:
            record["coordinates"] = []
            record["latitude"] = None
            record["longitude"] = None
        
        # Derived fields
        record["county"] = "Greene"
        record["improvement_value"] = max(0, record["assessed_value"] - record["land_value"])
        record["annual_taxes"] = round(record["assessed_value"] * 0.025, 2)  # Estimate
        record["tax_year"] = 2024
        record["deed_book"] = attrs.get("DEED_BOOK", attrs.get("DeedBook", ""))
        record["deed_page"] = attrs.get("DEED_PAGE", attrs.get("DeedPage", ""))
        record["last_sale_date"] = attrs.get("SALE_DATE", attrs.get("SaleDate", ""))
        record["last_sale_price"] = attrs.get("SALE_PRICE", attrs.get("SalePrice", None))
        
        records.append(record)
    
    df = pd.DataFrame(records)
    
    # Clean up
    df = df.dropna(subset=["latitude", "longitude"])
    
    return df


def save_to_file(df: pd.DataFrame, filename: str = "greene_county_parcels.json") -> Path:
    """Save DataFrame to JSON file"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    output_path = data_dir / filename
    
    records = df.to_dict(orient="records")
    
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2, default=str)
    
    print(f"Saved {len(records):,} parcels to {output_path}")
    return output_path


def load_from_file(filename: str = "greene_county_parcels.json") -> Optional[pd.DataFrame]:
    """Load DataFrame from JSON file"""
    data_dir = Path("data")
    file_path = data_dir / filename
    
    if file_path.exists():
        with open(file_path, "r") as f:
            records = json.load(f)
        return pd.DataFrame(records)
    return None


# Convenience function for the app
def fetch_greene_county_data(
    use_cache: bool = True,
    max_records: Optional[int] = None,
    municipality: Optional[str] = None,
    progress_callback: Optional[Callable] = None
) -> Optional[pd.DataFrame]:
    """
    Main function to get Greene County parcel data
    
    Args:
        use_cache: If True, return cached data if available
        max_records: Limit number of records (None = all ~38,370)
        municipality: Filter by municipality (e.g., "Hunter" for Lanesville)
        progress_callback: Function for progress updates
        
    Returns:
        DataFrame with parcel data
    """
    # Determine cache file name
    if municipality:
        cache_file = f"{municipality.lower().replace(' ', '_')}_parcels.json"
    else:
        cache_file = "greene_county_parcels.json"
    
    # Check cache first
    if use_cache:
        df = load_from_file(cache_file)
        if df is not None and len(df) > 0:
            if progress_callback:
                progress_callback(f"Loaded {len(df):,} parcels from cache")
            return df
    
    # Fetch from API
    df = fetch_all_parcels(
        progress_callback=progress_callback,
        max_records=max_records,
        municipality=municipality
    )
    
    if df is not None and len(df) > 0:
        # Save to cache
        save_to_file(df, cache_file)
        
        # Also save as the default file the app looks for
        save_to_file(df, "lanesville_parcels.json")
        
        return df
    
    return None


if __name__ == "__main__":
    """Command-line usage to download all parcels"""
    import sys
    
    print("=" * 60)
    print("Greene County Tax Parcels Downloader")
    print("=" * 60)
    
    # Parse command line args
    max_records = None
    municipality = None
    
    args = sys.argv[1:]
    
    # Check for --list-municipalities flag
    if "--list" in args or "-l" in args:
        print("\nFetching available municipalities...")
        munis = get_available_municipalities()
        print(f"\nFound {len(munis)} municipalities:")
        for m in munis:
            count = get_record_count(m)
            print(f"  - {m}: {count:,} parcels")
        sys.exit(0)
    
    # Check for --municipality or -m flag
    for i, arg in enumerate(args):
        if arg in ["--municipality", "-m"] and i + 1 < len(args):
            municipality = args[i + 1]
        elif arg.isdigit():
            max_records = int(arg)
    
    # Also support --hunter shortcut for Lanesville area
    if "--hunter" in args or "--lanesville" in args:
        municipality = "Hunter"
    
    if max_records:
        print(f"Limiting to {max_records:,} records")
    if municipality:
        print(f"Filtering by municipality: {municipality}")
    
    def print_progress(msg):
        print(f"  {msg}")
    
    print(f"\nFetching data from Greene County API...")
    print(f"URL: {GREENE_COUNTY_API}")
    print()
    
    df = fetch_greene_county_data(
        use_cache=False,
        max_records=max_records,
        municipality=municipality,
        progress_callback=print_progress
    )
    
    if df is not None:
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"Total parcels: {len(df):,}")
        print(f"Total acreage: {df['acreage'].sum():,.1f}")
        print(f"Unique owners: {df['owner'].nunique():,}")
        print(f"Municipalities: {df['municipality'].nunique()}")
        print()
        print("Municipalities in dataset:")
        for muni in sorted(df['municipality'].unique()):
            if muni:
                count = len(df[df['municipality'] == muni])
                print(f"  - {muni}: {count:,} parcels")
        print()
        if municipality:
            print(f"Data saved to: data/{municipality.lower()}_parcels.json")
        else:
            print("Data saved to: data/greene_county_parcels.json")
        print("              data/lanesville_parcels.json")
        print()
        print("Usage examples:")
        print("  python greene_county_fetcher.py                    # All parcels")
        print("  python greene_county_fetcher.py 5000               # First 5000 parcels")
        print("  python greene_county_fetcher.py -m Hunter          # Hunter only (Lanesville)")
        print("  python greene_county_fetcher.py --lanesville       # Shortcut for Hunter")
        print("  python greene_county_fetcher.py --list             # List all municipalities")
    else:
        print("\nFAILED to fetch data")
        sys.exit(1)
