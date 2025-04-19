import subprocess
import argparse
from datetime import datetime
import sys

def run(command):
    print(f"\n🔧 Running: {command}")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        print(f"❌ Failed: {command}")
        sys.exit(result.returncode)

def run_pipeline(date):
    print(f"\n🚀 Starting full pipeline for {date}")

    run(f"extractor\\extractor.exe --max_offset=4000")
    run(f"python run_cleaner.py --date {date}")
    run(f"python bq_json_converter.py --date {date}")
    run(f"python bq_jsonl_loader.py --date {date}")
    run(f"python bq_parquet_loader.py --date {date}")

    print(f"\n✅ Pipeline completed for {date}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full hygiene prediction pipeline")
    parser.add_argument("--date", type=str, default=None, help="Date to process in YYYY-MM-DD format")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    run_pipeline(date_str)