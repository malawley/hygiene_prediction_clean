from google.cloud import bigquery
import pandas as pd

def run_query_and_save_csv():
    client = bigquery.Client()

    query = """
    SELECT *
    FROM `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`
    WHERE inspection_date > '2025-03-01'
    LIMIT 2
    """
    df = client.query(query).to_dataframe()

    df.to_csv("CleanedInspectionRow_sample.csv", index=False)
    print("✅ Saved CleanedInspectionRow_sample.csv")

if __name__ == "__main__":
    run_query_and_save_csv()
