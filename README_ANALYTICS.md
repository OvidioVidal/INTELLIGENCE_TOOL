# M&A Intelligence Analytics Dashboard

## Overview

This analytics system provides comprehensive insights into your M&A deal intelligence data, including sector analysis, PE firm activity tracking, and temporal trends.

## Files

### 1. `analytics_calculator.py`
Core calculation engine that queries the SQLite database and computes all analytics metrics.

**Key Features:**
- Deal count metrics (All Time, YTD, Current Month)
- Sector-based analysis and trends
- PE firm extraction and ranking
- Deal quality (grade) distribution
- Geographic breakdown
- Time-series analysis

### 2. `analytics_dashboard.py`
Interactive Streamlit dashboard for visualizing the analytics.

**Key Features:**
- Big KPI metrics display
- Interactive charts (bar, pie, line, trend charts)
- Date range filtering (All Time, YTD, Current Month, Custom)
- Sector distribution and monthly trends
- Top 20 PE firms ranking
- Deal grade and geographic analysis
- CSV export functionality

## How to Run

### Start the Analytics Dashboard

```bash
streamlit run analytics_dashboard.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`

### Test the Calculator (Command Line)

```bash
python3 analytics_calculator.py
```

This runs diagnostic tests and prints sample analytics to the terminal.

## Dashboard Sections

### 1. Key Metrics
- **Total Deals (All Time)**: Complete deal count in database
- **Deals This Month**: Current month deal count
- **Deals Year-to-Date**: YTD deal count
- **Active Sectors**: Number of sectors with deals

### 2. Sector Analysis
- **Bar Chart**: Deal count by sector
- **Pie Chart**: Sector distribution percentage
- **Metrics Table**: Total deals and average deals per month by sector

### 3. Monthly Trends
- **Line Chart**: 12-month trend showing deal volume by sector
- **Data Table**: Pivot table view of monthly data

### 4. Most Active PE Firms
- **Bar Chart**: Top 20 PE firms by deal count
- **Ranking Table**: Ordered list of most active investors

### 5. Deal Quality & Geography
- **Grade Distribution**: Pie chart showing deal grades (Confirmed, Strong Evidence, Rumoured)
- **Geographic Breakdown**: Bar chart showing deals by region

### 6. Export Functionality
- Export sector data to CSV
- Export PE firms ranking to CSV
- Export monthly trend data to CSV

## Filter Options

**Time Period Filters:**
- **All Time**: Show all deals in database
- **Year to Date**: From January 1st to today
- **Current Month**: This month only
- **Custom Range**: Select specific start and end dates

## Analytics Calculated

### Deal Metrics
- Total deal count by time period
- Deals per sector
- Average deals per month per sector
- Monthly deal trends (12-month rolling)

### PE Firm Analytics
- Top PE firms by deal count
- Firm activity patterns
- Extracted from deal body text using pattern matching:
  - "backed by [Firm Name]"
  - "owned by [Firm Name]"
  - "portfolio company of [Firm Name]"
  - "acquired by [Firm Name]"
  - "[Firm Name] Capital/Partners/Equity/Ventures"

### Quality Metrics
- Deal grade distribution (Confirmed vs Rumoured)
- Geographic distribution by alert type

## Data Source

All analytics are calculated from the `intelligence.db` SQLite database, which is populated by the `json_to_db.py` script from the parsed email intelligence data.

## Requirements

### Core Requirements
- Python 3.7+
- streamlit
- plotly
- pandas
- sqlite3 (built-in)

### Optional (Recommended for Better PE Firm Detection)
- fuzzywuzzy
- python-Levenshtein

**To install optional dependencies:**
```bash
pip3 install --break-system-packages fuzzywuzzy python-Levenshtein
```

See [INSTALL_PE_CLASSIFIER.md](INSTALL_PE_CLASSIFIER.md) for detailed installation instructions.

## PE Firm Extraction

The system uses a **trained machine learning classifier** ([classifier.py](classifier.py)) to accurately identify PE firms:

### With Classifier (Recommended)
- ✅ Highly accurate PE firm identification using ML model trained on real data
- ✅ Filters out false positives (e.g., non-PE entities, operating companies)
- ✅ Validates firm names against PE structure patterns (Holdco, Bidco, Topco, etc.)
- ✅ Multi-language support (English, German, Spanish, French, Dutch)
- ✅ Confidence scoring for each classification

### Without Classifier (Basic Mode)
- ⚠️ Falls back to regex pattern matching
- ⚠️ May include some false positives
- ⚠️ Less accurate firm extraction

The system automatically detects which mode to use based on available dependencies.

## Notes

- **PE Firm Extraction**: Uses a trained classifier when available, otherwise falls back to pattern matching. Some firms may be missed if they don't follow standard naming conventions.
- **Deal Values**: Currently focused on deal count metrics since monetary values are inconsistently recorded in the source data.
- **Date Filtering**: All date filtering is based on the `parsed_date` field from the email metadata.
- **Performance**: Dashboard uses Streamlit caching for optimal performance. Click "Refresh Data" to reload if database is updated.

## Future Enhancements

Potential additions:
- Deal value analysis (when more value data is available)
- Sentiment analysis of deal descriptions
- Predictive analytics for sector trends
- Email alerts for specific metrics
- PDF report generation
- Multi-database comparison
