# === Final Full Risk Report Generator with Proper Sorting ===
    # """
    # Full End-to-End Risk Scoring Pipeline for Restaurant Inspections.

    # This function performs the complete risk scoring process:
    # - Accepts a list of place_ids to be scored (either manually selected or pulled randomly)
    # - Pulls restaurant profiles for these place_ids from BigQuery
    # - Pulls all past inspection events for these restaurants from BigQuery
    # - Engineers historical inspection features (fail rate, prior violations, etc.)
    # - Merges inspection features with restaurant profile metadata
    # - Drops first inspections (since no prior history exists)
    # - Scores restaurants using pre-trained ensemble models (Logistic, RF, XGB)
    # - Routes inspections based on ensemble probability threshold into low/high risk models
    # - Generates a risk prioritization report
    # - Augments the report to include all submitted restaurants, even if not scorable
    # - Saves:
    #     - Full feature dataset to BigQuery (ModelInput table)
    #     - Final risk report to BigQuery (RiskReport table)
    # - Displays the final sorted risk report

    # Output tables and files are named dynamically:
    # - Format: {inspector_id}_ScoringRun_{month_year_tag}_Restaurants
    # - Example: I1_ScoringRun_0425_ModelInput, I1_ScoringRun_0425_RiskReport

    # Parameters:
    #     inspector_id (str): Inspector ID (e.g., 'I1', 'I2', etc.)
    #     month_year_tag (str): Month and Year tag for the run (e.g., '0425' for April 2025)
    #     place_ids (list): List of place_ids (str) representing restaurants to score
    #     models_dir (str): Directory path where trained ML models are saved
    #     output_dataset (str): BigQuery dataset where outputs will be saved

    # Returns:
    #     None
    # """

import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
from datetime import datetime
import joblib
from google.cloud import bigquery
from google.cloud import storage
import io
import random

# === Full Final Risk Scoring Pipeline with Augmentation ===

def run_full_risk_scoring_pipeline(inspector_id, month_year_tag, top_n, place_ids, models_dir='/content/drive/MyDrive/msds434_project/models/', output_dataset='hygiene-prediction-434.RestaurantModeling'):
    """
    Full end-to-end risk scoring pipeline:
    - Pull restaurants by given place_ids
    - Pull inspection events
    - Engineer historical features
    - Merge with restaurant profiles
    - Score failure risk using ensemble and specialized models
    - Save model input (full_data) to BigQuery
    - Save risk report to BigQuery

    Parameters:
        inspector_id (str): Inspector ID (e.g., 'I1')
        month_year_tag (str): MonthYear tag (e.g., '0425')
        place_ids (list): List of place_id strings to score
        models_dir (str): Path to saved models
        output_dataset (str): BigQuery dataset

    Returns:
        None
    """


    # Create base run name
    base_name = f"{inspector_id}_ScoringRun_{month_year_tag}"

    client = bigquery.Client(project='hygiene-prediction-434')

    # === Step 1: Create Restaurants Table ===
    query_create_restaurants = f"""
    CREATE OR REPLACE TABLE `{output_dataset}.{base_name}_Restaurants` AS
    SELECT
      place_id,
      dba_name,
      address,
      zip,
      rating,
      price_level,
      user_ratings_total,
      business_status,
      types,
      CASE WHEN 'cafe' IN UNNEST(types) THEN 1 ELSE 0 END AS is_cafe,
      CASE WHEN 'bar' IN UNNEST(types) THEN 1 ELSE 0 END AS is_bar,
      CASE WHEN 'bakery' IN UNNEST(types) THEN 1 ELSE 0 END AS is_bakery,
      CASE WHEN 'meal_takeaway' IN UNNEST(types) THEN 1 ELSE 0 END AS is_meal_takeaway,
      CASE WHEN 'meal_delivery' IN UNNEST(types) THEN 1 ELSE 0 END AS is_meal_delivery,
      CASE WHEN 'night_club' IN UNNEST(types) THEN 1 ELSE 0 END AS is_night_club
    FROM
      `hygiene-prediction-434.RestaurantModeling.RestaurantProfile`
    WHERE
      place_id IN UNNEST(@place_ids)
    """

    job_config_restaurants = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("place_ids", "STRING", place_ids)]
    )

    client.query(query_create_restaurants, job_config=job_config_restaurants).result()
    print(f"✅ Created {base_name}_Restaurants table with {len(place_ids)} restaurants.")

    # === Step 2: Create InspectionEvents Table ===
    query_create_inspections = f"""
    CREATE OR REPLACE TABLE `{output_dataset}.{base_name}_InspectionEvents` AS
    SELECT
      i.inspection_id,
      i.place_id,
      i.inspection_date,
      i.inspection_type,
      i.result,
      i.violation_codes,
      i.num_violations,
      i.has_critical_violation,
      i.risk
    FROM
      `hygiene-prediction-434.RestaurantModeling.InspectionEvents` AS i
    INNER JOIN
      `{output_dataset}.{base_name}_Restaurants` AS r
    ON
      i.place_id = r.place_id
    """
    client.query(query_create_inspections).result()
    print(f"✅ Created {base_name}_InspectionEvents table.")

    # === Step 3: Load and Engineer Features ===
    query_load_inspections = f"""
    SELECT
      inspection_id,
      place_id,
      inspection_date,
      inspection_type,
      result,
      violation_codes,
      num_violations,
      has_critical_violation,
      risk
    FROM
      `{output_dataset}.{base_name}_InspectionEvents`
    ORDER BY
      place_id,
      inspection_date
    """
    df_next_inspections = client.query(query_load_inspections).to_dataframe()
    print(f"✅ Loaded {len(df_next_inspections)} rows from {base_name}_InspectionEvents.")

    # Feature Engineering
    df_next_inspections['inspection_date'] = pd.to_datetime(df_next_inspections['inspection_date'])
    df_next_inspections['fail'] = df_next_inspections['result'].apply(lambda x: 1 if x == 'fail' else 0)
    df_next_inspections['inspection_number'] = df_next_inspections.groupby('place_id').cumcount() + 1
    df_next_inspections['total_prior_inspections'] = df_next_inspections['inspection_number'] - 1
    df_next_inspections['prior_critical_violations'] = df_next_inspections.groupby('place_id')['has_critical_violation'].cumsum().shift(1).fillna(0)
    df_next_inspections['prior_total_violations'] = df_next_inspections.groupby('place_id')['num_violations'].cumsum().shift(1).fillna(0)
    df_next_inspections['avg_prior_violations_per_inspection'] = (df_next_inspections['prior_total_violations'] / df_next_inspections['total_prior_inspections']).replace([np.inf, -np.inf], 0).fillna(0)
    df_next_inspections['prior_failures'] = df_next_inspections.groupby('place_id')['fail'].cumsum().shift(1).fillna(0)
    df_next_inspections['fail_rate'] = (df_next_inspections['prior_failures'] / df_next_inspections['total_prior_inspections']).replace([np.inf, -np.inf], 0).fillna(0)
    print(f"✅ Engineered features successfully.")

    # === Step 4: Load Restaurants Metadata ===
    query_load_restaurants = f"""
    SELECT
      place_id,
      dba_name,
      address,
      zip,
      rating,
      price_level,
      user_ratings_total,
      business_status,
      is_cafe,
      is_bar,
      is_bakery,
      is_meal_takeaway,
      is_meal_delivery,
      is_night_club
    FROM
      `{output_dataset}.{base_name}_Restaurants`
    """
    df_restaurants = client.query(query_load_restaurants).to_dataframe()
    print(f"✅ Loaded {len(df_restaurants)} rows from {base_name}_Restaurants.")

    # Merge
    full_data = df_next_inspections.merge(df_restaurants, how='left', on='place_id')
    print(f"✅ Joined inspections with restaurant profiles. Final dataset has {full_data.shape[0]} rows.")

    # Drop first inspections
    full_data = full_data[full_data['total_prior_inspections'] > 0].copy()
    print(f"✅ Dropped first inspections. Remaining {full_data.shape[0]} rows.")

    # === Step 5: Score and Generate Risk Report ===
    top_risk_report = generate_and_save_risk_report(
      full_data,
      models_dir=models_dir,
      original_place_ids=place_ids,
      df_restaurants_metadata=df_restaurants,
      inspector_id=inspector_id,
      month_year_tag=month_year_tag,
      top_n=top_n
    )


    # === Step 6: Save full_data and risk_report to BigQuery ===
    full_data_table = f"{output_dataset}.{base_name}_ModelInput"
    client.load_table_from_dataframe(full_data, full_data_table).result()
    print(f"✅ Saved full_data to BigQuery table: {full_data_table}")

    top_risk_report_table = f"{output_dataset}.{base_name}_RiskReport"
    client.load_table_from_dataframe(top_risk_report, top_risk_report_table).result()
    print(f"✅ Saved risk report to BigQuery table: {top_risk_report_table}")

    # === Step 7: Display Risk Report ===
    #display(top_risk_report)
    print(top_risk_report.head(10))
    print("✅ Full risk scoring pipeline completed successfully.")
    return top_risk_report



#def generate_and_save_risk_report(new_data, models_dir, original_place_ids, df_restaurants_metadata, top_n=50, output_dir='/content/drive/MyDrive/msds434_project/outputs/'):
def generate_and_save_risk_report(new_data, models_dir, original_place_ids, df_restaurants_metadata, inspector_id, month_year_tag, top_n=50, output_dir='/content/drive/MyDrive/msds434_project/outputs/'):

    """
    Full scoring pipeline:
    - Loads models and objects
    - Scores new restaurants
    - Ensures one row per restaurant (highest risk)
    - Adds missing restaurants with 'Not enough history'
    - Sorts scored first, unscored second
    - Saves final risk report to Google Drive

    Parameters:
        new_data (DataFrame): New restaurant data with features matching 'feature_columns'
        models_dir (str): Directory where models and objects are saved
        original_place_ids (list): All place_ids that were supposed to be scored
        df_restaurants_metadata (DataFrame): Basic metadata (dba_name, address, zip, place_id)
        top_n (int): Number of top risky restaurants to keep
        output_dir (str): Where to save the risk report CSV

    Returns:
        DataFrame: Final augmented risk report
    """

    # 1. Load models and objects

    def load_joblib_from_gcs(bucket_name, blob_name):
        """Load a joblib object directly from a GCS bucket."""
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        bytes_data = blob.download_as_bytes()
        joblib_obj = joblib.load(io.BytesIO(bytes_data))

        return joblib_obj


    bucket_name = 'ml-prediction-models'

    logistic_model = load_joblib_from_gcs(bucket_name, 'models/logistic_model.pkl')
    rf_model = load_joblib_from_gcs(bucket_name, 'models/rf_model.pkl')
    xgb_model = load_joblib_from_gcs(bucket_name, 'models/xgb_model.pkl')
    low_risk_model = load_joblib_from_gcs(bucket_name, 'models/low_risk_model.pkl')
    high_risk_model = load_joblib_from_gcs(bucket_name, 'models/high_risk_model.pkl')
    feature_columns = load_joblib_from_gcs(bucket_name, 'models/feature_columns.pkl')
    median_threshold = load_joblib_from_gcs(bucket_name, 'models/median_threshold.pkl')


    # logistic_model = joblib.load(os.path.join(models_dir, 'logistic_model.pkl'))
    # rf_model = joblib.load(os.path.join(models_dir, 'rf_model.pkl'))
    # xgb_model = joblib.load(os.path.join(models_dir, 'xgb_model.pkl'))
    # low_risk_model = joblib.load(os.path.join(models_dir, 'low_risk_model.pkl'))
    # high_risk_model = joblib.load(os.path.join(models_dir, 'high_risk_model.pkl'))
    # feature_columns = joblib.load(os.path.join(models_dir, 'feature_columns.pkl'))
    # median_threshold = joblib.load(os.path.join(models_dir, 'median_threshold.pkl'))

    # 2. Prepare input
    X_new = new_data[feature_columns].copy()
    X_new = np.nan_to_num(X_new, nan=0.0, posinf=0.0, neginf=0.0)

    # 3. Score with ensemble
    logistic_probs = logistic_model.predict_proba(X_new)[:, 1]
    rf_probs = rf_model.predict_proba(X_new)[:, 1]
    xgb_probs = xgb_model.predict_proba(X_new)[:, 1]
    ensemble_probs = (logistic_probs + rf_probs + xgb_probs) / 3

    # 4. Routing based on median
    low_risk_idx = ensemble_probs < median_threshold
    high_risk_idx = ensemble_probs >= median_threshold

    # 5. Specialized model predictions
    low_probs = np.zeros_like(ensemble_probs)
    high_probs = np.zeros_like(ensemble_probs)

    if np.sum(low_risk_idx) > 0:
        low_probs[low_risk_idx] = low_risk_model.predict_proba(X_new[low_risk_idx])[:, 1]
    if np.sum(high_risk_idx) > 0:
        high_probs[high_risk_idx] = high_risk_model.predict_proba(X_new[high_risk_idx])[:, 1]

    # 6. Final risk probabilities
    final_probs = np.zeros_like(ensemble_probs)
    final_probs[low_risk_idx] = low_probs[low_risk_idx]
    final_probs[high_risk_idx] = high_probs[high_risk_idx]

    # 7. Assign risk zones
    def assign_risk_zone(prob):
        if prob >= 0.75:
            return 'high'
        elif prob >= 0.5:
            return 'medium'
        else:
            return 'low'

    risk_zones = [assign_risk_zone(prob) for prob in final_probs]

    # 8. Build output DataFrame
    output_scores = pd.DataFrame({
        'predicted_failure_probability': final_probs,
        'risk_zone': risk_zones
    }).reset_index(drop=True)
    
    output_scores['predicted_failure_probability'] = output_scores['predicted_failure_probability'].round(2)

    # 9. Add metadata if available
    if 'dba_name' in new_data.columns or 'zip' in new_data.columns or 'address' in new_data.columns:
        metadata_cols = [col for col in ['dba_name', 'address', 'zip', 'place_id'] if col in new_data.columns]
        output_scores = new_data[metadata_cols].reset_index(drop=True).join(output_scores)

    # 10. Scoring status
    output_scores['scoring_status'] = output_scores['predicted_failure_probability'].apply(
        lambda x: 'Scored' if pd.notnull(x) else 'Unscored'
    )

    # 11. Highest risk per restaurant
    output_scores = output_scores.sort_values(by='predicted_failure_probability', ascending=False)
    output_scores = output_scores.drop_duplicates(subset=['place_id'])

    # 12. Augment with missing restaurants
    output_scores = augment_risk_report_with_unscored(output_scores, original_place_ids, df_restaurants_metadata)

    # === FINAL SORT ===
    # 13. Separate scored and unscored
    scored_df = output_scores[output_scores['scoring_status'] == 'Scored'].copy()
    unscored_df = output_scores[output_scores['scoring_status'] == 'Not enough history'].copy()

    # 14. Sort scored restaurants by predicted_failure_probability descending
    scored_df = scored_df.sort_values(by='predicted_failure_probability', ascending=False)

    # 15. Concatenate
    final_risk_report = pd.concat([scored_df, unscored_df], ignore_index=True).head(top_n)

    # 16. Save to CSV
    def upload_df_to_gcs(df, bucket_name, destination_blob_name):
        """Uploads a pandas DataFrame as CSV to a GCS bucket."""
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        csv_data = df.to_csv(index=False)
        blob.upload_from_string(csv_data, content_type='text/csv')
        print(f"✅ Uploaded risk report to: gs://{bucket_name}/{destination_blob_name}")

    # Inside your main function (generate_and_save_risk_report)

    gcs_filename = f"{inspector_id}_{month_year_tag}_risk_report.csv"


    # Upload the final risk report DataFrame
    upload_df_to_gcs(
        final_risk_report,
        bucket_name='restaurant-risk-reports',
        destination_blob_name=gcs_filename
    )

    return final_risk_report



# === Augment Risk Report to Include Unscored Restaurants ===

def augment_risk_report_with_unscored(top_risk_report, original_place_ids, df_restaurants_metadata):
    """
    Ensure every submitted restaurant appears in the final risk report,
    even if no inspection history allowed scoring.

    Parameters:
        top_risk_report (DataFrame): Scored restaurants (subset)
        original_place_ids (list): All place_ids submitted
        df_restaurants_metadata (DataFrame): Metadata table (must have place_id, dba_name, address, zip)

    Returns:
        DataFrame: Final augmented risk report with all restaurants
    """

    # 1. Find missing place_ids
    scored_place_ids = top_risk_report['place_id'].unique()
    missing_place_ids = [pid for pid in original_place_ids if pid not in scored_place_ids]

    print(f"✅ Found {len(missing_place_ids)} restaurants with no scorable inspections.")

    # 2. Build DataFrame for missing restaurants
    missing_df = df_restaurants_metadata[df_restaurants_metadata['place_id'].isin(missing_place_ids)].copy()

    missing_df['predicted_failure_probability'] = float('nan')
    missing_df['risk_zone'] = 'Not Enough History to Score'
    missing_df['scoring_status'] = 'Not enough history'

    # 3. Select columns in right order
    columns = ['dba_name', 'address', 'zip', 'place_id',
               'predicted_failure_probability', 'risk_zone', 'scoring_status']

    missing_df = missing_df[columns]

    # 4. Align top_risk_report to same column order
    top_risk_report = top_risk_report[columns]

    # 5. Combine
    final_risk_report = pd.concat([top_risk_report, missing_df], ignore_index=True)

    # 6. Sort
    final_risk_report = final_risk_report.sort_values(
        by=['risk_zone', 'predicted_failure_probability'],
        ascending=[True, False]
    ).reset_index(drop=True)

    print(f"✅ Final risk report completed: {final_risk_report.shape[0]} restaurants.")

    return final_risk_report


# === Master Function to Pull Random Restaurants and Run Full Scoring ===

import traceback

def pull_and_score(inspector_id, month_year_tag, n=30, top_n=50, seed=42,
                   models_dir='/content/drive/MyDrive/msds434_project/models/',
                   output_dataset='hygiene-prediction-434.RestaurantModeling'):
    """
    Pulls random place_ids and runs the full risk scoring pipeline in one call.

    Parameters:
        inspector_id (str): Inspector ID (e.g., 'I1')
        month_year_tag (str): Month and year tag (e.g., '0425')
        n (int): Number of random restaurants to pull
        seed (int): Optional random seed for reproducibility
        models_dir (str): Path to saved models
        output_dataset (str): BigQuery dataset where results are saved

    Returns:
        DataFrame: Final risk report
    """
    print("🚨 pull_and_score() started")

    try:
        # ✅ Fix: pass seed!
        place_ids = pull_random_place_ids(n=n, seed=seed)
        print(f"✅ pulled {len(place_ids)} place_ids")

        # ✅ Run and return the result
        top_risk_report = run_full_risk_scoring_pipeline(
            inspector_id=inspector_id,
            month_year_tag=month_year_tag,
            top_n=top_n,
            place_ids=place_ids,
            models_dir=models_dir,
            output_dataset=output_dataset
        )

        print("✅ pull_and_score() completed with rows:", top_risk_report.shape[0])
        return top_risk_report

    except Exception as e:
        print("🔥 EXCEPTION in pull_and_score()")
        traceback.print_exc()
        raise



def pull_random_place_ids(n=30, seed=42):
    """
    Pulls n random place_ids from the RestaurantProfile table.

    Parameters:
        n (int): Number of place_ids to pull
        seed (int): Random seed for reproducibility (optional)

    Returns:
        list: List of random place_ids
    """
    client = bigquery.Client(project='hygiene-prediction-434')

    query = """
    SELECT place_id
    FROM `hygiene-prediction-434.RestaurantModeling.RestaurantProfile`
    WHERE business_status = 'OPERATIONAL'
    """

    df = client.query(query).to_dataframe()
    df_sorted = df.sort_values(by='place_id') 

    if seed is not None:
        random.seed(seed)

    place_ids = random.sample(df_sorted['place_id'].tolist(), n)

    print(f"✅ Pulled {n} random place_ids.")

    return place_ids


# === CLI Entry Point ===

# === CLI Entry Point ===

# === CLI Entry Point (Read inputs from YAML file) ===

if __name__ == "__main__":
    import os
    import yaml

    input_file = os.path.join(os.path.dirname(__file__), "risk_report_inputs.yaml")

    # Read the input template
    with open(input_file, "r") as f:
        params = yaml.safe_load(f)

    # Extract parameters
    inspector_id = params.get("inspector_id")
    month_year_tag = params.get("month_year_tag")
    n = int(params.get("n", 30))
    top_n = int(params.get("top_n", 50))
    seed = int(params.get("seed", 42))

    print(f"🚀 Starting full risk scoring pipeline for Inspector {inspector_id}, Tag {month_year_tag}")

    pull_and_score(
        inspector_id=inspector_id,
        month_year_tag=month_year_tag,
        n=n,
        top_n=top_n,
        seed=seed,
        models_dir='models/',
        output_dataset='hygiene-prediction-434.RestaurantModeling'
    )

    print("✅ Finished full risk scoring pipeline.")
