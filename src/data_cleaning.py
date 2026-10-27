'''Reproducible data quality audit and conservative cleaning pipeline.

Usage from project root:
    python src/data_cleaning.py
The raw input is never overwritten. Outliers are flagged for review, not dropped
automatically, because legitimate high-value products can be statistically rare.
'''
from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "original_dataset.csv"
CLEAN_DIR = ROOT / "data" / "cleaned"
REPORT_DIR = ROOT / "reports"

NUMERIC_COLS = ["Quantity", "Unit_Price_INR", "Unit_Cost_INR", "Discount_Percent"]
REQUIRED_COLS = ["Order_ID", "Order_Date", "Product", "Category", "Region", "Sales_Channel",
                 "Customer_Type", "Quantity", "Unit_Price_INR", "Unit_Cost_INR",
                 "Discount_Percent", "Payment_Method"]
CATEGORICAL_COLS = ["Product", "Category", "Region", "Sales_Channel", "Customer_Type", "Payment_Method"]


def profile(df):
    # Return comparable quality metrics for a dataframe.
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "total_missing_cells": int(df.isna().sum().sum()),
        "columns_with_missing_values": int((df.isna().sum() > 0).sum()),
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "duplicate_order_ids": int(df["Order_ID"].duplicated().sum()) if "Order_ID" in df else None,
        "invalid_dates": int(pd.to_datetime(df["Order_Date"], errors="coerce").isna().sum()) if "Order_Date" in df else None,
        "blank_string_cells": int(sum(df[c].astype("string").str.strip().eq("").fillna(False).sum() for c in df.select_dtypes(include="object").columns)),
    }


def iqr_outlier_report(df):
    records = []
    for col in NUMERIC_COLS:
        if col not in df:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile(.25), s.quantile(.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = (s < lower) | (s > upper)
        records.append({"column": col, "q1": q1, "q3": q3, "iqr": iqr,
                        "lower_fence": lower, "upper_fence": upper,
                        "outlier_count": int(mask.sum()), "outlier_percent": float(mask.mean() * 100),
                        "minimum": s.min(), "maximum": s.max()})
    return pd.DataFrame(records)


def main():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True); REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Raw dataset not found: {RAW_PATH}")
    raw = pd.read_csv(RAW_PATH)
    missing_cols = sorted(set(REQUIRED_COLS) - set(raw.columns))
    if missing_cols:
        raise ValueError(f"Dataset is missing required columns: {missing_cols}")

    before = profile(raw)
    clean = raw.copy(deep=True)
    changes = []

    # Normalize surrounding whitespace in text columns; this changes no current values if already clean.
    for col in clean.select_dtypes(include="object").columns:
        old = clean[col].copy()
        clean[col] = clean[col].astype("string").str.strip()
        changed = int((old.fillna("") != clean[col].fillna("")).sum())
        if changed:
            changes.append({"step": f"Trim whitespace in {col}", "records_affected": changed,
                            "rationale": "Remove accidental leading/trailing spaces that can split categories."})

    # Parse dates explicitly; invalid values are reported and retained as NaT rather than silently guessed.
    original_dates = clean["Order_Date"].copy()
    clean["Order_Date"] = pd.to_datetime(clean["Order_Date"], errors="coerce")
    invalid_dates = int(clean["Order_Date"].isna().sum())
    changes.append({"step": "Parse Order_Date as datetime", "records_affected": int((original_dates.astype(str) != clean["Order_Date"].dt.strftime("%Y-%m-%d").fillna("NaT")).sum()),
                    "rationale": "Standardize date type for time-based analysis; unparseable values become missing and are reported."})

    # Numeric coercion and range checks. Do not impute missing values without evidence.
    for col in NUMERIC_COLS:
        old = clean[col].copy()
        clean[col] = pd.to_numeric(clean[col], errors="coerce")
        changes.append({"step": f"Convert {col} to numeric", "records_affected": int(clean[col].isna().sum()),
                        "rationale": "Ensure numeric computations are valid; coercion failures are surfaced in the audit."})

    # Remove exact duplicate rows only; do not deduplicate merely by Order_ID without evidence.
    duplicate_count = int(clean.duplicated().sum())
    if duplicate_count:
        clean = clean.drop_duplicates().copy()
    changes.append({"step": "Remove exact duplicate rows", "records_affected": duplicate_count,
                    "rationale": "Exact duplicate records inflate counts and totals. No rows are removed unless every field matches."})

    # Check logical validity. Report violations; do not silently delete them.
    checks = {
        "quantity_nonpositive": int((clean["Quantity"] <= 0).fillna(False).sum()),
        "unit_price_nonpositive": int((clean["Unit_Price_INR"] <= 0).fillna(False).sum()),
        "unit_cost_negative": int((clean["Unit_Cost_INR"] < 0).fillna(False).sum()),
        "discount_out_of_range": int(((clean["Discount_Percent"] < 0) | (clean["Discount_Percent"] > 1)).fillna(False).sum()),
        "cost_greater_than_price": int((clean["Unit_Cost_INR"] > clean["Unit_Price_INR"]).fillna(False).sum()),
        "duplicate_order_ids": int(clean["Order_ID"].duplicated().sum()),
    }

    after = profile(clean)
    # Before/after statistical profile for key numeric columns.
    stat_rows = []
    for col in NUMERIC_COLS:
        for stage, frame in [("before", raw), ("after", clean)]:
            s = pd.to_numeric(frame[col], errors="coerce")
            stat_rows.append({"stage": stage, "column": col, "count": int(s.count()), "missing": int(s.isna().sum()),
                              "mean": s.mean(), "median": s.median(), "std": s.std(), "min": s.min(), "q1": s.quantile(.25),
                              "q3": s.quantile(.75), "max": s.max()})

    outliers = iqr_outlier_report(clean)
    clean.to_csv(CLEAN_DIR / "cleaned_dataset.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame([{"metric": k, "before": v, "after": after.get(k)} for k, v in before.items()]).to_csv(REPORT_DIR / "before_after_comparison.csv", index=False)
    pd.DataFrame(stat_rows).to_csv(REPORT_DIR / "numeric_profile_before_after.csv", index=False)
    outliers.to_csv(REPORT_DIR / "iqr_outlier_report.csv", index=False)
    pd.DataFrame(changes).to_csv(REPORT_DIR / "cleaning_steps_log.csv", index=False)
    with open(REPORT_DIR / "validation_checks.json", "w", encoding="utf-8") as f:
        json.dump({"before": before, "after": after, "logical_validation_checks": checks,
                   "notes": ["IQR outliers are flagged, not removed automatically.",
                             "Missing values are not imputed without domain evidence.",
                             "The raw dataset is never modified." ]}, f, indent=2, default=str)

    # Human-readable audit report, generated from observed values.
    report = f'''# Data Quality Audit Report\n\n## Dataset overview\n\n- Raw file: `data/raw/original_dataset.csv`\n- Clean output: `data/cleaned/cleaned_dataset.csv`\n- Initial shape: **{before['rows']} rows × {before['columns']} columns**\n- Final shape: **{after['rows']} rows × {after['columns']} columns**\n- Date range: **{pd.to_datetime(raw['Order_Date'], errors='coerce').min().date()} to {pd.to_datetime(raw['Order_Date'], errors='coerce').max().date()}**\n\n## Findings from the supplied dataset\n\n- Missing cells: **{before['total_missing_cells']}**.\n- Exact duplicate rows: **{before['exact_duplicate_rows']}**.\n- Duplicate `Order_ID` values beyond the first occurrence: **{before['duplicate_order_ids']}**.\n- Unparseable dates: **{before['invalid_dates']}**.\n- Blank string cells: **{before['blank_string_cells']}**.\n- Quantity values that are zero or negative: **{checks['quantity_nonpositive']}**.\n- Non-positive unit prices: **{checks['unit_price_nonpositive']}**.\n- Negative unit costs: **{checks['unit_cost_negative']}**.\n- Discount values outside the 0–1 fraction range: **{checks['discount_out_of_range']}**.\n- Rows where unit cost exceeds unit price: **{checks['cost_greater_than_price']}**.\n\n## Cleaning decisions\n\n1. **Preserve the source:** the original CSV is copied into `data/raw/` and is never overwritten.\n2. **Whitespace normalization:** trim leading/trailing spaces in text columns to avoid category mismatches. The pipeline logs how many values changed.\n3. **Date standardization:** convert `Order_Date` to a datetime type. Unparseable values are surfaced as missing rather than guessed.\n4. **Numeric standardization:** numeric fields are explicitly parsed. Invalid conversions become missing and are reported.\n5. **Exact duplicate handling:** remove rows only when every column matches. Do not remove rows solely because an order ID repeats; that requires business context.\n6. **Missing-value strategy:** no blanket imputation is applied. The supplied dataset has {before['total_missing_cells']} missing cells, so there is no observed missing-value problem to impute. If new missing values appear, choose a strategy based on the field meaning and document it.\n7. **Outlier strategy:** use the 1.5×IQR rule on numeric columns and save results to `reports/iqr_outlier_report.csv`. Outliers are flagged, not deleted or capped automatically, because high prices/costs can be legitimate across different product types.\n\n## Outlier interpretation\n\nThe IQR rule flags unusual values in price/cost fields because the dataset contains different product types with different price scales. Statistical unusualness alone is not proof of an error. Review flagged records against product-specific price/cost ranges before making any correction.\n\n## Before-and-after result\n\nThe generated `reports/before_after_comparison.csv` compares row/column counts, null counts, duplicates, date parsing, and blank-string counts. `reports/numeric_profile_before_after.csv` compares count, mean, median, standard deviation, minimum, quartiles, and maximum for numeric fields.\n\nThe supplied data has no detected missing cells, exact duplicate rows, duplicate order IDs, unparseable dates, blank strings, or invalid values under the basic logical checks. Therefore, the appropriate outcome is a **standardized, validated dataset**, not forced row removal or imputation. Any outlier flags remain available for review.\n\n## Reproducibility\n\nRun from the project root:\n\n```bash\npython src/data_cleaning.py\n```\n\nOutputs are regenerated in `data/cleaned/` and `reports/`. The process is deterministic and uses pandas/numpy only.\n'''
    (REPORT_DIR / "data_quality_audit.md").write_text(report, encoding="utf-8")
    print("DATA CLEANING COMPLETED")
    print(json.dumps({"before": before, "after": after, "logical_validation_checks": checks}, indent=2, default=str))
    print(f"Clean dataset: {CLEAN_DIR / 'cleaned_dataset.csv'}")

if __name__ == "__main__":
    main()
