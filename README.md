#  Data Cleaning Report

## Objective
Audit a sales dataset for missing values, duplicates, inconsistent types, and statistical outliers; standardize the data; and document reproducible cleaning decisions.



## Requirements
Python 3.10+ recommended. Install packages:
```bash
pip install -r requirements.txt
```

## Run the cleaning pipeline
From the project root:
```bash
python src/data_cleaning.py
```
The script reads only `data/raw/original_dataset.csv`, never overwrites it, and writes standardized output and audit reports to dedicated folders.

## Actual initial findings
The supplied dataset contains **360 rows and 12 columns**. Initial checks found **0 missing cells, 0 exact duplicate rows, 0 duplicate order IDs, 0 unparseable dates, and 0 blank text cells**. Basic logical checks found no non-positive quantities/prices, negative costs, discounts outside 0–1, or unit costs exceeding unit prices. The date range is 2025-01-02 through 2026-09-28.

The IQR rule flags some values in unit price and unit cost. These are treated as *review candidates*, not automatically as errors: the dataset combines products with very different price levels. No outliers are dropped solely because they fall beyond an IQR fence.

## Cleaning approach
- Preserve the original raw file.
- Trim accidental whitespace in text columns.
- Parse dates into a consistent datetime type.
- Explicitly convert numeric fields.
- Remove only exact duplicate rows, if any exist.
- Report invalid values and missingness rather than silently imputing.
- Flag IQR outliers for human review; do not delete/cap them without domain evidence.
- Generate before/after profiles and a cleaning log on every run.

## Notebook
Open `notebooks/data_cleaning_analysis.ipynb` in Jupyter and run all cells. The notebook demonstrates the key checks and loads the generated report files.

## Limitations
The data-quality conclusions apply to this supplied sample and the implemented rules. A statistically unusual value is not necessarily a data error. Business owners should confirm product-specific valid ranges before any outlier correction.
