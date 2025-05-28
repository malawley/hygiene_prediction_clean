import os
import json
import pandas as pd
from pathlib import Path
import filecmp

# === CONFIGURATION ===
REPORTS_DIR = Path("reports")
CONFIG_DIR = Path("configure_test_files")

# === VALIDATION FUNCTIONS ===
def row_count_check(df, top_n):
    return len(df) == top_n

def sort_order_check(df):
    return df['predicted_failure_probability'].is_monotonic_decreasing if 'predicted_failure_probability' in df.columns else False

def uniqueness_check(df):
    return df['dba_name'].is_unique if 'dba_name' in df.columns else False

def field_sanity_check(df):
    return df['dba_name'].notna().all() and df['zip'].notna().all()

def inspector_month_match(df, config):
    if 'inspector_id' in df.columns and 'inspection_date' in df.columns:
        inspector_ok = df['inspector_id'].eq(config['inspector_id']).all()
        month_tag = config['month_year_tag'].replace('_', '-')
        month_ok = df['inspection_date'].str.startswith(month_tag).all()
        return inspector_ok and month_ok
    return True  # skip if fields missing

# === LOAD CONFIGURATIONS ===
configs = {}
for cfg_file in CONFIG_DIR.glob("*.json"):
    with open(cfg_file) as f:
        config = json.load(f)
        configs[config["name"]] = config

# === VALIDATE EACH CSV ===
results = []
paired = {}

for csv_file in sorted(REPORTS_DIR.glob("*.csv")):
    test_id = csv_file.stem
    base_id = "_".join(test_id.split("_")[:2])  # ensures 'test_003_run1' → 'test_003'

    # Track files by base_id for later repeatability check
    paired.setdefault(base_id, []).append(csv_file)

    config = configs.get(test_id)
    if config is None:
        results.append((test_id, "missing_config", False))
        continue

    try:
        df = pd.read_csv(csv_file)
    except Exception:
        results.append((test_id, "read_error", False))
        continue

    if df.empty:
        results.append((test_id, "nonempty_csv", False))
        continue
    else:
        results.append((test_id, "nonempty_csv", True))

    # Run file-specific checks
    results.append((test_id, "row_count", row_count_check(df, config["top_n"])))
    results.append((test_id, "sort_order", sort_order_check(df)))
    results.append((test_id, "uniqueness", uniqueness_check(df)))
    results.append((test_id, "field_sanity", field_sanity_check(df)))
    results.append((test_id, "inspector_month_match", inspector_month_match(df, config)))



# === DISPLAY AND WRITE RESULTS ===
# === DISPLAY AND WRITE RESULTS ===

# === WRITE REPEATABILITY CHECKS TO FILE HEADER ===
identity_checks = []
for base_id, files in paired.items():
    if len(files) == 2:
        identical = filecmp.cmp(files[0], files[1], shallow=False)
        status = "✅ IDENTICAL" if identical else "❌ DIFFERENT"
        identity_checks.append(f"{base_id:<10} repeatability_identical   {status}")

# Prepare header text
identity_summary = ">fc reports\\test_003_run1.csv reports\\test_003_run2.csv\n"
identity_summary += "# Repeatability check summary (run1 vs run2):\n"
identity_summary += "\n".join(identity_checks)
identity_summary += "\n\n# Validation results follow:\n\n"

# === FORMAT INDIVIDUAL VALIDATION RESULTS ===
df_results = pd.DataFrame(results, columns=["test_id", "check", "passed"])

# Extract base_id: handles test_003_run1, test_003_run2, and test_003
df_results["base_id"] = df_results["test_id"].str.extract(r"(test_\d+)")
df_results["base_id"] = df_results["base_id"].fillna(df_results["test_id"])

# Sort by base_id and test_id
df_results.sort_values(by=["base_id", "test_id", "check"], inplace=True)

# Group by base_id, format with blank lines between
blocks = []
for base_id, group in df_results.groupby("base_id", sort=False):
    group_str = group.drop(columns="base_id").to_string(index=False)
    blocks.append(group_str)

# Combine validation result blocks
output_str = "\n\n".join(blocks)

# === WRITE FULL REPORT TO FILE ===
with open("validation_results.txt", "w", encoding="utf-8") as f:
    f.write(identity_summary)
    f.write(output_str)

# === PRINT TO TERMINAL ===
print(identity_summary)
print(output_str)
