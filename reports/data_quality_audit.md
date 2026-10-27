# Data Quality Audit Report

## Dataset overview

- Raw file: `data/raw/original_dataset.csv`
- Clean output: `data/cleaned/cleaned_dataset.csv`
- Initial shape: **360 rows × 12 columns**
- Final shape: **360 rows × 12 columns**
- Date range: **2025-01-02 to 2026-09-28**

## Findings from the supplied dataset

- Missing cells: **0**.
- Exact duplicate rows: **0**.
- Duplicate `Order_ID` values beyond the first occurrence: **0**.
- Unparseable dates: **0**.
- Blank string cells: **0**.
- Quantity values that are zero or negative: **0**.
- Non-positive unit prices: **0**.
- Negative unit costs: **0**.
- Discount values outside the 0–1 fraction range: **0**.
- Rows where unit cost exceeds unit price: **0**.

## Cleaning decisions

1. **Preserve the source:** the original CSV is copied into `data/raw/` and is never overwritten.
2. **Whitespace normalization:** trim leading/trailing spaces in text columns to avoid category mismatches. The pipeline logs how many values changed.
3. **Date standardization:** convert `Order_Date` to a datetime type. Unparseable values are surfaced as missing rather than guessed.
4. **Numeric standardization:** numeric fields are explicitly parsed. Invalid conversions become missing and are reported.
5. **Exact duplicate handling:** remove rows only when every column matches. Do not remove rows solely because an order ID repeats; that requires business context.
6. **Missing-value strategy:** no blanket imputation is applied. The supplied dataset has 0 missing cells, so there is no observed missing-value problem to impute. If new missing values appear, choose a strategy based on the field meaning and document it.
7. **Outlier strategy:** use the 1.5×IQR rule on numeric columns and save results to `reports/iqr_outlier_report.csv`. Outliers are flagged, not deleted or capped automatically, because high prices/costs can be legitimate across different product types.

## Outlier interpretation

The IQR rule flags unusual values in price/cost fields because the dataset contains different product types with different price scales. Statistical unusualness alone is not proof of an error. Review flagged records against product-specific price/cost ranges before making any correction.

## Before-and-after result

The generated `reports/before_after_comparison.csv` compares row/column counts, null counts, duplicates, date parsing, and blank-string counts. `reports/numeric_profile_before_after.csv` compares count, mean, median, standard deviation, minimum, quartiles, and maximum for numeric fields.

The supplied data has no detected missing cells, exact duplicate rows, duplicate order IDs, unparseable dates, blank strings, or invalid values under the basic logical checks. Therefore, the appropriate outcome is a **standardized, validated dataset**, not forced row removal or imputation. Any outlier flags remain available for review.

## Reproducibility

Run from the project root:

```bash
python src/data_cleaning.py
```

Outputs are regenerated in `data/cleaned/` and `reports/`. The process is deterministic and uses pandas/numpy only.
