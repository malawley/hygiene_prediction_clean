

def generate_inspection_report(inspector_id: int, seed: int = 42, sample_size: int = 10):
    import os
    from io import BytesIO
    import joblib
    import pandas as pd
    import numpy as np
    import random
    from datetime import datetime
    from google.cloud import bigquery, storage
    import re


    # === 1. Authenticate and connect ===
    
    bq_client = bigquery.Client(project='hygiene-prediction-434')
    gcs_client = storage.Client(project='hygiene-prediction-434')
    bucket_name = 'restaurant-risk-reports'

    # === 2. Load trained models from GCS ===
    model_bucket = gcs_client.bucket('ml-prediction-models')

    def load_model_from_gcs(blob_name):
        blob = model_bucket.blob(blob_name)
        model_bytes = blob.download_as_bytes()
        return joblib.load(BytesIO(model_bytes))

    log_model = load_model_from_gcs('logistic_model.pkl')
    xgb_model = load_model_from_gcs('xgboost_model.pkl')
    clf_tp_fp = load_model_from_gcs('tp_fp_classifier.pkl')

    print("✅ Models loaded successfully from GCS.")

    # === 3. Sample inspection_ids ===
    query_ids = f"""
    SELECT *
    FROM `hygiene-prediction-434.RestaurantModeling.Training_Data_Inspection_Classification_Final`
    ORDER BY RAND()
    LIMIT {sample_size}
    """
 
    df_ids = bq_client.query(query_ids).to_dataframe()
    all_inspection_ids = df_ids['inspection_id'].tolist()

    random.seed(seed)
    sampled_ids = random.sample(all_inspection_ids, sample_size)
    inspection_ids_str = ', '.join([f"CAST('{id}' AS INT64)" for id in sampled_ids])

    # === 4. Load features ===
    query_features = f"""
    SELECT *
    FROM `hygiene-prediction-434.RestaurantModeling.Training_Data_Inspection_Classification_Final`
    WHERE inspection_id IN ({inspection_ids_str})
    """
    df_features = bq_client.query(query_features).to_dataframe()
    print(f"✅ Loaded {df_features.shape[0]} rows of features for prediction.")

    y_sample = df_features['fail'].reset_index(drop=True)
    inspection_ids = df_features['inspection_id'].reset_index(drop=True)
    X_sample = df_features.drop(columns=['fail', 'inspection_id']).copy().reset_index(drop=True)

    original_names = list(log_model.feature_names_in_)
    cleaned_names = [col.replace(" ", "_").replace("(", "").replace(")", "").replace("__", "_") for col in original_names]
    column_name_map = dict(zip(cleaned_names, original_names))
    X_sample = X_sample.rename(columns=column_name_map)
    X_sample = X_sample[original_names]
    print("✅ Feature matrix aligned with model inputs.")

    # === 5. Predictions ===
    best_threshold = 0.25
    probs_log = log_model.predict_proba(X_sample)[:, 1]
    probs_xgb = xgb_model.predict_proba(X_sample)[:, 1]
    ensemble_probs_sample = (probs_log + probs_xgb) / 2
    ensemble_preds_sample = (ensemble_probs_sample >= best_threshold).astype(int)

    X_fails_only_sample = X_sample[ensemble_preds_sample == 1]
    tp_probs_sample = clf_tp_fp.predict_proba(X_fails_only_sample)[:, 1]
    confident_mask = tp_probs_sample >= 0.5
    marginal_mask = ~confident_mask

    final_pred_labels = pd.Series("pass", index=X_sample.index)
    final_pred_labels.loc[X_fails_only_sample.index[confident_mask]] = "confident_fail"
    final_pred_labels.loc[X_fails_only_sample.index[marginal_mask]] = "marginal_fail"
    print("✅ Model predictions complete.")

    # === 6. Metadata Query ===
    inspection_ids_formatted = ", ".join(f"'{id}'" for id in inspection_ids)

    query_metadata = f"""
    WITH deduped_training_data AS (
      SELECT *
      FROM (
        SELECT *,
              ROW_NUMBER() OVER (PARTITION BY inspection_id ORDER BY RAND()) AS rn
        FROM `hygiene-prediction-434.RestaurantModeling.TrainingData`
        WHERE CAST(inspection_id AS STRING) IN UNNEST([{inspection_ids_formatted}])
      )
      WHERE rn = 1
    ),
    deduped_restaurant_profile AS (
      SELECT *
      FROM (
        SELECT *,
              ROW_NUMBER() OVER (PARTITION BY dba_name ORDER BY RAND()) AS rn
        FROM `hygiene-prediction-434.RestaurantModeling.RestaurantProfile`
      )
      WHERE rn = 1
    )
    SELECT 
      td.inspection_id,
      td.violation_codes,
      td.dba_name,
      rp.matched_name,
      rp.address,
      rp.zip
    FROM deduped_training_data td
    LEFT JOIN deduped_restaurant_profile rp
      ON td.dba_name = rp.dba_name
    """

    df_metadata = bq_client.query(query_metadata).to_dataframe()
    print(f"✅ Retrieved metadata for {df_metadata.shape[0]} inspections.")

    # === 7. Assemble final output ===
    predictions_df = pd.DataFrame({
        'inspection_id': df_features['inspection_id'].astype(str),
        'model_prediction': final_pred_labels,
        'ensemble_score': ensemble_probs_sample,
        'num_violations': df_features['num_violations'],
        'critical_viol': df_features['has_critical_violation'],
        'rating': df_features['rating'],
        'price_level': df_features['price_level']
    })

    df_metadata['inspection_id'] = df_metadata['inspection_id'].astype(str)
    output_df = pd.merge(predictions_df, df_metadata, on='inspection_id', how='left')
    output_df['model_prediction'] = output_df['model_prediction'].replace('marginal_fail', 'conditional_pass')

    desired_order = [
        'inspection_id',
        'matched_name',
        'address',
        'zip',
        'rating',
        'price_level',
        'violation_codes',
        'critical_viol',
        'num_violations',     
        'model_prediction'
    ]
    output_df = output_df[desired_order]

    print("✅ Final report built.")

    # === Clean violation_codes BEFORE sorting or saving ===
    def format_violation_codes(val):
        # Handle NaN or empty list
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return ""
        
        # Convert arrays/lists to list of strings
        if isinstance(val, (list, np.ndarray)):
            return ", ".join(str(code) for code in val)
        
        # Handle string representations like "['55' '57']"
        codes = re.findall(r'\d+', str(val))
        return ", ".join(codes)

    output_df['violation_codes'] = output_df['violation_codes'].apply(format_violation_codes)

    import pandas as pd
    from pandas.api.types import CategoricalDtype

    # Define the desired order for model_prediction
    prediction_order = ['confident_fail', 'conditional_pass', 'pass']
    prediction_dtype = CategoricalDtype(categories=prediction_order, ordered=True)

    # Convert model_prediction to the categorical type with the specified order
    output_df['model_prediction'] = output_df['model_prediction'].astype(prediction_dtype)

    # Sort by model_prediction (ascending) and num_violations (descending)
    output_df = output_df.sort_values(
        by=['model_prediction', 'num_violations'],
        ascending=[True, False]
    ).reset_index(drop=True)



    # === 9. Save CSV directly to GCS ===
    from io import StringIO
    today_str = datetime.today().strftime("%m-%d-%Y")
    file_name = f"risk_report_I{inspector_id}_{today_str}_{seed}.csv"

    # Convert DataFrame to CSV in memory
    csv_buffer = StringIO()
    output_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    # Upload to GCS
    bucket = gcs_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_string(csv_buffer.getvalue(), content_type="text/csv")

    gcs_uri = f"gs://{bucket_name}/{file_name}"
    print(f"✅ Report uploaded to GCS: {gcs_uri}")
    return output_df, gcs_uri


def main():
    import os
    import yaml
    from dotenv import load_dotenv
    load_dotenv()

    input_file = os.path.join(os.path.dirname(__file__), "risk_report_inputs.yaml")

    # Read the input YAML file
    with open(input_file, "r") as f:
        params = yaml.safe_load(f)

    # Extract parameters from config
    inspector_id = int(params.get("inspector_id"))
    sample_size = int(params.get("sample_size", 100))
    seed = int(params.get("seed", 42))

    print(f"🚀 Starting inspection report for Inspector {inspector_id} using seed {seed} with {sample_size} rows")

    df, gcs_uri = generate_inspection_report(
        inspector_id=inspector_id,
        seed=seed,
        sample_size=sample_size
    )

    print("✅ Report generation complete.")
    print(f"📄 Report saved to: {gcs_uri}")


if __name__ == "__main__":
    main()



