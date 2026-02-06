# 🗺️ Greene County Property Finder

An **OnXHunt-style** property owner identification application for Lanesville, NY (Town of Hunter, Greene County). Built with Streamlit, this application provides interactive mapping, parcel visualization, and owner lookup capabilities.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-red)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

### 🗺️ Interactive Property Map
- **Satellite/Topo/Street views** - Multiple base map options
- **Color-coded parcels** by property type (residential, vacant, state land, etc.)
- **Click for details** - View owner info, assessed values, and tax data
- **Drawing tools** - Mark areas of interest
- **GPS location** - Find your current position

### 🔍 Advanced Search
- Search by **owner name**
- Search by **parcel ID** or **SBL**
- Search by **mailing address**
- Filter by property type, acreage range, and value range

### 📊 Analytics Dashboard
- Property type distribution charts
- Top landowners by acreage and value
- Tax revenue analysis
- Local vs. non-local owner breakdown
- Mailing location analysis

### 👤 Owner Lookup
- Detailed owner portfolio analysis
- Multi-parcel owner mapping
- Export options (CSV, JSON)

### 📥 Download by Zip Code
- Download parcel datasets for specific zip codes
- Support for 17+ Catskills-area zip codes
- Multiple export formats (CSV, JSON, GeoJSON)
- Filter by property type
- Batch download multiple zip codes

### 🔧 Data Management (NEW)
- **Fetch real NYS GIS data** directly from state services
- Download actual Greene County tax parcels
- Support for up to 50,000 parcels
- Upload your own GeoJSON/JSON data files
- Manage cached datasets

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Clone or navigate to the project directory
cd lanesville_property_finder

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## 📡 Using Real NYS Data

The app can fetch **actual parcel data** directly from NYS GIS services:

1. **Open the app** and go to **🔧 Data Management** page
2. Select your coverage area:
   - **Lanesville/Hunter Area** - Faster, focused on local parcels
   - **All of Greene County** - Complete county data (slower)
3. Click **🚀 Fetch Data from NYS GIS**
4. Wait for download (may take a few minutes for large datasets)
5. Data is automatically cached and used by the main app

### Fetching from Command Line

```python
from nys_data_fetcher import fetch_greene_county_parcels

# Fetch Lanesville area (default)
df = fetch_greene_county_parcels(area="lanesville", max_records=5000)

# Fetch all of Greene County
df = fetch_greene_county_parcels(area="greene", max_records=20000)

print(f"Fetched {len(df)} parcels")
```

### Data Source

Real data comes from the **NYS GIS Tax Parcels Public** service:
- Updated regularly by NYS
- Includes owner names, assessed values, acreage, boundaries
- Coverage: All of New York State

## 📁 Project Structure

```
lanesville_property_finder/
├── app.py                     # Main application
├── nys_data_fetcher.py        # Real NYS GIS data fetcher
├── data_loader.py             # Data processing utilities
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── data/                      # Parcel data storage (auto-created)
│   └── lanesville_parcels.json
└── pages/
    ├── 1_📊_Analytics.py      # Analytics dashboard
    ├── 2_👤_Owner_Lookup.py    # Owner search page
    ├── 3_📥_Download_Data.py   # Download by zip code
    └── 4_🔧_Data_Management.py # Fetch real NYS data
```

## 📮 Supported Zip Codes

The download feature supports the following Catskills-area zip codes:

| Zip Code | Location | Town | County |
|----------|----------|------|--------|
| 12450 | Lanesville | Hunter | Greene |
| 12442 | Hunter | Hunter | Greene |
| 12485 | Tannersville | Hunter | Greene |
| 12434 | Haines Falls | Hunter | Greene |
| 12424 | Elka Park | Hunter | Greene |
| 12439 | Jewett | Jewett | Greene |
| 12436 | Hensonville | Windham | Greene |
| 12496 | Windham | Windham | Greene |
| 12468 | Prattsville | Prattsville | Greene |
| 12452 | Lexington | Lexington | Greene |
| 12492 | West Kill | Lexington | Greene |
| 12414 | Catskill | Catskill | Greene |
| 12451 | Leeds | Catskill | Greene |
| 12463 | Palenville | Catskill | Greene |
| 12464 | Phoenicia | Shandaken | Ulster |
| 12480 | Shandaken | Shandaken | Ulster |
| 12457 | Mt Tremper | Shandaken | Ulster |

## 🔧 Using Real Data

The application comes with sample data for demonstration. To use real parcel data:

### Option 1: NYS GIS Clearinghouse

1. Visit [NYS GIS Clearinghouse](https://gis.ny.gov/)
2. Navigate to Tax Parcels dataset
3. Download Greene County parcels
4. Use `data_loader.py` to process:

```python
from data_loader import GreeneCountyParcelLoader

loader = GreeneCountyParcelLoader()
gdf = loader.load_shapefile("path/to/parcels.shp")
gdf_filtered = loader.filter_lanesville(gdf)
df = loader.process_parcels(gdf_filtered)
loader.save_processed_data(df)
```

### Option 2: Greene County Real Property

Contact Greene County Real Property Tax Services for official assessment data:
- **Phone:** (518) 719-3270
- **Address:** 411 Main Street, Catskill, NY 12414

### Option 3: ArcGIS REST API

```python
from data_loader import download_and_process
download_and_process()  # Attempts to fetch from NYS GIS services
```

## 📊 Data Fields

| Field | Description |
|-------|-------------|
| `parcel_id` | Unique parcel identifier |
| `sbl` | Section-Block-Lot number |
| `owner` | Property owner name |
| `mailing_address` | Owner mailing address |
| `property_class` | NYS property class code |
| `property_class_desc` | Property class description |
| `acreage` | Parcel size in acres |
| `assessed_value` | Total assessed value |
| `land_value` | Land-only assessed value |
| `improvement_value` | Improvement assessed value |
| `annual_taxes` | Estimated annual taxes |
| `school_district` | School district name |
| `coordinates` | Parcel boundary coordinates |

## 🎨 Property Class Colors

| Color | Property Type |
|-------|--------------|
| 🟢 Green | Residential |
| 🟡 Yellow | Vacant Land |
| 🔵 Blue | State/Forest |
| 🟢 Light Green | Agricultural |
| 🟠 Orange | Commercial |
| 🟣 Purple | Recreation |
| ⚪ Gray | Community Service |

## ⚖️ Legal Notice

**Property boundary data is for reference only.** Always verify with official county records before making any decisions based on this information.

This application is not affiliated with or endorsed by Greene County, the Town of Hunter, or New York State. Data accuracy depends on source data quality.

## 🔗 Related Resources

- [Greene County GIS](https://www.discovergreene.com/)
- [NYS GIS Clearinghouse](https://gis.ny.gov/)
- [NYS Real Property Tax Services](https://www.tax.ny.gov/research/property/)
- [OnXHunt](https://www.onxmaps.com/) - Inspiration for this project

## 📝 License

MIT License - Feel free to use and modify for your purposes.

## 🤝 Contributing

Contributions welcome! Please feel free to submit issues and pull requests.

---

*Built for property research in the beautiful Catskill Mountains* 🏔️
