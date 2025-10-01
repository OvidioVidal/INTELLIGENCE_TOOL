# Installing PE Classifier Dependencies

The analytics system uses a trained machine learning classifier to accurately identify PE firms from deal descriptions. This classifier requires additional Python dependencies.

## Quick Install

```bash
pip3 install --break-system-packages fuzzywuzzy python-Levenshtein
```

**Or using a virtual environment (recommended):**

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows

# Install dependencies
pip install fuzzywuzzy python-Levenshtein pandas numpy openpyxl streamlit plotly
```

## What You Get With The Classifier

### ✅ With Classifier (Recommended)
- **Highly accurate PE firm identification** using trained ML model
- Filters out false positives (e.g., "Executive Management", non-PE entities)
- Validates firm names against patterns like:
  - Holdco, Topco, Bidco structures
  - Capital, Partners, Equity, Ventures naming
  - Multi-language PE terms (English, German, Spanish, French, Dutch)
- **Classification confidence scores** for each firm
- Better ranking of most active PE investors

### ⚠️ Without Classifier (Basic Mode)
- Simple regex pattern matching
- May include non-PE entities in results
- Less accurate firm extraction
- No confidence scoring

## Training Data

The classifier is trained on `testing_results.xlsx` which contains labeled examples of PE funds vs non-PE entities. The model achieves:
- High precision on PE structure entities (Holdco, Bidco, etc.)
- Multilingual support
- TF-IDF-like word scoring approach

## Verifying Installation

After installing dependencies, run:

```bash
python3 analytics_calculator.py
```

You should see:
```
[OK] PE Fund Classifier loaded successfully
```

Instead of:
```
[INFO] Using basic pattern matching for PE firm extraction
```

## Dashboard Usage

The Streamlit dashboard automatically uses the classifier if available:

```bash
streamlit run analytics_dashboard.py
```

No code changes needed - it will detect the classifier automatically!

## Troubleshooting

### Issue: "externally-managed-environment"
**Solution:** Use `--break-system-packages` flag or create a virtual environment (recommended).

### Issue: "No module named 'fuzzywuzzy'"
**Solution:** Install with: `pip3 install fuzzywuzzy python-Levenshtein`

### Issue: Classifier not loading even after install
**Solution:**
1. Check if `testing_results.xlsx` exists in the same directory
2. Restart your Python interpreter/terminal
3. Verify imports: `python3 -c "from fuzzywuzzy import fuzz; print('OK')"`

## Manual Alternative

If you prefer not to install the dependencies, the system will work in basic mode using regex pattern matching. This is sufficient for most use cases but may include some false positives in PE firm rankings.
