from google.cloud import bigquery
import logging
import os
from datetime import datetime

# Ensure the logs directory exists
os.makedirs("logs", exist_ok=True)

# Generate a timestamped log filename
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"logs/view_build_{timestamp}.log"

# Configure logging to write to the timestamped file
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# Initialize BigQuery client
client = bigquery.Client()


# ---- Define and build violation_code_sheet table
def create_violation_code_sheet_table():
    dataset_id = "hygiene-prediction.HygienePredictionRow"
    table_id = f"{dataset_id}.violation_code_sheet"
    
    script_dir = os.path.dirname(__file__)
    csv_path = os.path.join(script_dir, "violation_code_sheet.csv")

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    with open(csv_path, "rb") as file:
        job = client.load_table_from_file(file, table_id, job_config=job_config)
        job.result()  # Wait for the job to complete

    logging.info(f"Table {table_id} created or updated from CSV.")


# --- Define SQL for Each View ---

# View 1: violation_code_count
violation_code_count_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_code_count` AS
SELECT 
  code, 
  COUNT(*) AS violation_count
FROM `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`,
UNNEST(violation_codes) AS code
GROUP BY code
"""

# View 2: violation_code_count_description
violation_code_count_description_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_code_count_description` AS
SELECT 
  c.code,
  s.description,
  c.violation_count
FROM `hygiene-prediction.HygienePredictionRow.violation_code_count` AS c
LEFT JOIN `hygiene-prediction.HygienePredictionRow.violation_code_sheet` AS s
ON c.code = s.code
"""

# View 3: violation_code_by_facility_category
violation_by_facility_category_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_code_by_facility_category` AS
WITH exploded AS (
  SELECT 
    code,
    facility_category
  FROM `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`,
  UNNEST(violation_codes) AS code
)
SELECT 
  code, 
  facility_category, 
  COUNT(*) AS violation_count
FROM exploded
GROUP BY code, facility_category
ORDER BY code, violation_count DESC
"""

# View 4: violation_correlation_view
violation_correlation_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_correlation_view` AS
WITH violations_grouped AS (
  SELECT 
    inspection_id,
    ARRAY_AGG(DISTINCT code) AS violations
  FROM (
    SELECT 
      inspection_id, 
      code
    FROM `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`,
    UNNEST(violation_codes) AS code
  )
  GROUP BY inspection_id
),
violation_pairs AS (
  SELECT 
    v1 AS code_a,
    v2 AS code_b
  FROM violations_grouped,
  UNNEST(violations) AS v1,
  UNNEST(violations) AS v2
  WHERE v1 < v2
)
SELECT 
  code_a,
  code_b,
  COUNT(*) AS co_occurrence_count
FROM violation_pairs
GROUP BY code_a, code_b
ORDER BY co_occurrence_count DESC
"""

# View 5: violation_facility_labeled
violation_facility_labeled_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_facility_labeled` AS
WITH exploded AS (
  SELECT 
    code,
    facility_category
  FROM `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`,
  UNNEST(violation_codes) AS code
),
counts AS (
  SELECT 
    code,
    facility_category,
    COUNT(*) AS violation_count
  FROM exploded
  GROUP BY code, facility_category
),
joined AS (
  SELECT 
    c.code,
    c.facility_category,
    c.violation_count,
    s.description
  FROM counts AS c
  LEFT JOIN `hygiene-prediction.HygienePredictionRow.violation_code_sheet` AS s
  ON c.code = s.code
)
SELECT 
  *,
  CONCAT(CAST(code AS STRING), ' - ', description) AS code_description
FROM joined
"""

# View 6: violation_cooccurrence_labeled_top10
violation_cooccurrence_labeled_top10_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_cooccurrence_labeled_top10` AS
WITH top_codes AS (
  SELECT code
  FROM `hygiene-prediction.HygienePredictionRow.violation_code_count`
  ORDER BY violation_count DESC
  LIMIT 10
),
filtered AS (
  SELECT *
  FROM `hygiene-prediction.HygienePredictionRow.violation_correlation_view`
  WHERE code_a IN (SELECT code FROM top_codes)
    AND code_b IN (SELECT code FROM top_codes)
),
joined AS (
  SELECT 
    f.code_a,
    f.code_b,
    f.co_occurrence_count,
    sa.description AS description_a,
    sb.description AS description_b
  FROM filtered AS f
  LEFT JOIN `hygiene-prediction.HygienePredictionRow.violation_code_sheet` AS sa
    ON f.code_a = sa.code
  LEFT JOIN `hygiene-prediction.HygienePredictionRow.violation_code_sheet` AS sb
    ON f.code_b = sb.code
)
SELECT *, 
  CONCAT(CAST(code_a AS STRING), ' - ', description_a) AS code_a_label,
  CONCAT(CAST(code_b AS STRING), ' - ', description_b) AS code_b_label
FROM joined
"""

# View 7: Violation by Zipcode
violation_by_zip_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_by_zip` AS
SELECT 
  zip,
  code,
  COUNT(*) AS violation_count
FROM `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`,
UNNEST(violation_codes) AS code
GROUP BY zip, code
"""


# View 8: Top Violators by Name
violation_by_facility_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_by_facility` AS
WITH exploded AS (
  SELECT 
    dba_name,
    zip,
    facility_category,
    code
  FROM `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`,
  UNNEST(violation_codes) AS code
)
SELECT 
  dba_name,
  zip,
  facility_category,
  code,
  COUNT(*) AS violation_count
FROM exploded
GROUP BY dba_name, zip, facility_category, code
"""



# View 9: Violation trends by month
violation_trends_by_month_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_trends_by_month_labeled` AS
SELECT 
    t.month,
    t.code,
    s.description,
    t.violation_count,
    CONCAT(CAST(t.code AS STRING), ' - ', IFNULL(s.description, 'Unknown')) AS code_description
FROM `hygiene-prediction.HygienePredictionRow.violation_trends_by_month` t
LEFT JOIN `hygiene-prediction.HygienePredictionRow.violation_code_sheet` s
ON t.code = s.code
"""




# View 10: Violation by facility
violation_facility_map_sql = """
CREATE OR REPLACE VIEW `hygiene-prediction.HygienePredictionRow.violation_by_facility_map` AS
SELECT 
  dba_name,
  address,
  latitude,
  longitude,
  code,
  COUNT(*) AS violation_count
FROM (
  SELECT 
    dba_name,
    address,
    latitude,
    longitude,
    code
  FROM `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`,
  UNNEST(violation_codes) AS code
  WHERE latitude IS NOT NULL AND longitude IS NOT NULL
)
GROUP BY dba_name, address, latitude, longitude, code
"""


# --- Register and Run All Queries ---
ordered_views = [
    ("violation_code_count", violation_code_count_sql),
    ("violation_code_by_facility_category", violation_by_facility_category_sql),
    ("violation_correlation_view", violation_correlation_sql),
    ("violation_code_count_description", violation_code_count_description_sql),
    ("violation_facility_labeled", violation_facility_labeled_sql),
    ("violation_cooccurrence_labeled_top10", violation_cooccurrence_labeled_top10_sql),
    ("violation_by_zip", violation_by_zip_sql),
    ("violation_by_facility",violation_by_facility_sql), 
    ("violation_trends_by_month",violation_trends_by_month_sql),
    ("violation_by_facility_map", violation_facility_map_sql)
]


def main():
    try:
        create_violation_code_sheet_table()
        for name, sql in ordered_views:
            logging.info(f"Creating or replacing view: {name}")
            print(f"Creating or replacing view: {name}")
            client.query(sql).result()
        logging.info("✅ All views have been created or updated successfully.")

    except Exception as e:
        logging.exception("❌ An error occurred while building views.")
        print(f"Error: {e}")



if __name__ == "__main__":
    main()
