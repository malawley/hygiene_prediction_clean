import itertools
import json
import shutil
import csv
from pathlib import Path

# === PATH SETUP ===
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "parameter_ranges.json"
CONFIG_DIR = BASE_DIR / "configure_test_files"
REPORT_DIR = BASE_DIR / "reports"
CSV_INDEX_PATH = BASE_DIR / "config_index.csv"

# === SAFE DELETE CONTENTS ONLY ===
def safe_clear_dir(path):
    if path.exists():
        for item in path.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                print(f"⚠️ Could not delete {item}: {e}")
    path.mkdir(parents=True, exist_ok=True)

# === CLEAN DIRECTORIES ===
print("🧹 Cleaning directories...")
safe_clear_dir(CONFIG_DIR)
safe_clear_dir(REPORT_DIR)

# === LOAD PARAMETER RANGES FROM JSON ===
with open(CONFIG_PATH, "r") as f:
    config_data = json.load(f)

ranges = config_data.get("ranges", {})
param_names = list(ranges.keys())
param_values = list(ranges.values())

# === GENERATE PARAMETER GRID ===
grid = list(itertools.product(*param_values))
print(f"🧪 Generating {len(grid)} base configs × 2 runs each = {len(grid)*2} test runs...\n")

# === WRITE CONFIG FILES & LOG TO CSV ===
with open(CSV_INDEX_PATH, "w", newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["base_id", "run_id"] + param_names)

    for idx, values in enumerate(grid, start=1):
        base_id = f"test_{idx:03}"
        param_set = dict(zip(param_names, values))

        for run_num in [1, 2]:
            run_id = f"{base_id}_run{run_num}"
            config = {"name": run_id, **param_set}

            # Save JSON file
            path = CONFIG_DIR / f"{run_id}.json"
            with open(path, "w") as f:
                json.dump(config, f, indent=2)

            # Log to CSV
            writer.writerow([base_id, run_id] + [param_set[k] for k in param_names])

            # Print preview
            print(f"✅ {run_id}:")
            for k in param_names:
                print(f"  {k:<18} = {param_set[k]}")
            print()

print(f"\n🗂️  Config index saved to: {CSV_INDEX_PATH}")
