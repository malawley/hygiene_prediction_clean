import pandas as pd
import os

def generate_and_save_risk_report(
    full_data: pd.DataFrame,
    models_dir: str,
    original_place_ids: list,
    df_restaurants_metadata: pd.DataFrame,
    top_n: int = 50
) -> pd.DataFrame:
    """
    Generate a risk-scored DataFrame of top risky facilities.

    Parameters:
    - full_data: cleaned inspection-level data
    - models_dir: path to where trained models are stored
    - original_place_ids: list of place_ids in original order
    - df_restaurants_metadata: restaurant names and locations
    - top_n: number of top-risk facilities to return

    Returns:
    - A DataFrame containing the top_n risk-ranked facilities
    """

    # === Placeholder scoring logic (replace with real model later) ===
    scored = full_data.copy()
    scored["risk_score"] = scored.index.to_series().rank(ascending=False).div(len(scored))  # dummy score
    scored["place_id"] = original_place_ids

    # === Join metadata ===
    result = scored.merge(df_restaurants_metadata, on="place_id", how="left")

    # === Sort and return top_n ===
    top_risk = result.sort_values("risk_score", ascending=False).head(top_n).reset_index(drop=True)
    return top_risk
