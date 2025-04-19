import polars as pl
import re
from difflib import get_close_matches

# === cleaner_1_drop ===
def cleaner_1_drop(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    def log(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    log(f"Starting with {df.height} rows")

    columns_to_drop = ["aka_name", "license_", "location"]
    df = df.drop(columns_to_drop).unique()

    columns_except_violations = [col for col in df.columns if col != "violations"]
    for col in columns_except_violations:
        df = df.filter(pl.col(col).is_not_null())

    after_null_filter_rows = df.height
    log(f"After dropping nulls (except 'violations'): {after_null_filter_rows} rows")

    initial_violations_null = df.filter(pl.col("violations").is_null()).height
    drop_condition = (
        (pl.col("violations").is_null()) &
        (~pl.col("results").is_in(["Pass", "Pass w/ Conditions"]))
    )
    df = df.filter(~drop_condition)

    remaining_violations_null = df.filter(pl.col("violations").is_null()).height
    removed_due_to_violations = initial_violations_null - remaining_violations_null

    log(f"Dropped {removed_due_to_violations} rows with missing violations and invalid results")
    log(f"Preserved {remaining_violations_null} 'Pass' rows with no violations")
    log(f"Final cleaned row count: {df.height}")

    return df

# === cleaner_2_inspection_id ===
def cleaner_2_inspection_id(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    """
    Step 2 cleaner: Validates and filters the inspection_id column.
    - Drops rows with duplicate inspection_id
    - Drops rows where inspection_id does not match 7-digit numeric string
    - Logs action counts

    Parameters:
        df (pl.DataFrame): DataFrame after cleaner_1
        logger (optional): Logger object

    Returns:
        pl.DataFrame: Cleaned DataFrame
    """
    def log(msg):
        if logger:
            try:
                logger.info(msg.encode("ascii", "ignore").decode())
            except Exception:
                logger.info("LOG ERROR (unicode removed): " + msg)
        else:
            print(msg)

    before = df.height

    # Step 1: Drop duplicates by inspection_id
    df = df.unique(subset=["inspection_id"])
    after_dedup = df.height
    dropped_duplicates = before - after_dedup
    log(f"Dropped {dropped_duplicates} duplicate inspection_id rows")

    # Step 2: Drop rows where inspection_id is not 7 digits
    pattern = r"^\d{7}$"
    df = df.filter(pl.col("inspection_id").str.contains(pattern))
    after_pattern = df.height
    dropped_bad_ids = after_dedup - after_pattern
    log(f"Dropped {dropped_bad_ids} rows with invalid inspection_id format")

    log(f"Final row count after inspection_id checks: {df.height}")
    return df


# === cleaner_3_text_normalization ===
def cleaner_3_text_normalization(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    text_cols = ["dba_name", "facility_type", "risk", "address", "city", "state", "inspection_type", "results", "violations"]

    def normalize(text):
        if not text:
            return text
        return (
            text.lower()
                .strip()
                .replace("\n", " ")
                .replace("\t", " ")
                .replace("/", " ")
                .replace("-", " ")
        )

    df = df.with_columns([
        pl.col(col).map_elements(normalize, return_dtype=pl.Utf8).alias(col)
        for col in text_cols if col in df.columns
    ])

    if logger:
        for col in text_cols:
            if col in df.columns:
                before = df.select(pl.col(col)).n_unique()
                after = df.select(pl.col(col)).n_unique()
                logger.info(f"Column Normalization Summary: {col:<20} | Unique after: {after}")                
    return df

# === cleaner_4_values_consolidation ===
def cleaner_4_values_consolidation(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    def fuzzy_fix_city(city: str):
        if not city:
            return city
        city = city.lower().strip()
        options = ["chicago", "berwyn"]
        match = get_close_matches(city, options, n=1, cutoff=0.8)
        return match[0] if match else city

    df = df.with_columns([
        pl.col("city").map_elements(fuzzy_fix_city, return_dtype=pl.Utf8).alias("city")
    ])

    risk_map = {
        "risk 1 high": "high",
        "risk 2 medium": "medium",
        "risk 3 low": "low"
    }
    df = df.with_columns([
        pl.when(pl.col("risk").is_in(risk_map.keys()))
          .then(pl.col("risk").map_elements(lambda x: risk_map.get(x, x), return_dtype=pl.Utf8))
          .otherwise(pl.col("risk"))
          .alias("risk")
    ])
    return df

# === cleaner_5_facility_type ===
def cleaner_5_facility_type(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    category_tags = {
        "condiments": ["juice bar", "ice cream", "dessert", "donut", "snack", "gym", "herbal"],
        "school": ["school", "charter", "public shcool", "teaching"],
        "butcher": ["butcher", "meat", "slaughter", "live"],
        "supportive_living": ["assisted living", "supportive", "senior", "rehab", "adult daycare", "nursing home", "long term care"],
        "event": ["event", "venue", "hall", "rooftop", "banquet", "banquets", "theater", "catering", "stadium"],
        "gas_station": ["gas station", "station store", "station", "convenient store"],
        "restaurant": ["restaurant", "banquet", "diner", "taqueria", "bar", "pub", "cafeteria"],
        "mobile": ["mobile", "mobil", "dispenser", "truck", "prepared", "hot dog"],
        "grocery": ["grocery", "market", "store", "food mart"],
        "coffee": ["coffee", "tea", "cafe", "espresso", "kiosk"],
        "bakery": ["bakery", "paleteria", "donut", "dessert"],
        "bar": ["tavern", "liquor", "bar", "lounge", "brewery"],
        "cooking_school": ["cooking", "culinary", "training", "chef"],
        "child_services": ["daycare", "after school", "child", "children", "youth"],
        "church": ["church", "faith", "religious"],
        "commissary": ["commissary", "shared kitchen", "shelter"],
        "pantry": ["pantry", "free food"],
        "hotel": ["hotel", "lodge", "inn"],
        "warehouse": ["warehouse", "distribution"],
        "facility": ["facility", "services"]
    }

    def categorize(text):
        if not text:
            return "unknown"
        text = text.lower()
        for category, keywords in category_tags.items():
            if any(keyword in text for keyword in keywords):
                return category
        return "unknown"

    df = df.with_columns([
        pl.col("facility_type").map_elements(categorize, return_dtype=pl.Utf8).alias("facility_category")
    ])
    return df

# === cleaner_6_inspection_type ===
def cleaner_6_inspection_type(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    if "inspection_type" in df.columns:
        df = df.with_columns([
            pl.col("inspection_type").str.replace_all("license reinspection", "license")
        ])
    return df

# === cleaner_7_results ===
def cleaner_7_results(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    if "results" in df.columns:
        df = df.with_columns([
            pl.col("results").str.replace_all("pass w conditions", "pass_w_conditions")
        ])
    return df

# === cleaner_8_geolocation ===
def cleaner_8_geolocation(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    df = df.with_columns([
        pl.col("zip").cast(pl.Utf8, strict=False)
            .str.strip_chars()
            .str.zfill(5)
            .alias("zip")
    ])

    df = df.filter(
        pl.col("zip").is_not_null() & (pl.col("zip").str.len_chars() == 5)
    )

    df = df.with_columns([
        pl.col("latitude").cast(pl.Float64, strict=False),
        pl.col("longitude").cast(pl.Float64, strict=False)
    ])

    df = df.filter(
        pl.col("latitude").is_not_null() &
        pl.col("longitude").is_not_null()
    )

    df = df.with_columns([
        pl.col("latitude").round(5),
        pl.col("longitude").round(5)
    ])

    return df

# === cleaner_9_tokenize_violations ===
# === cleaner_9_tokenize_violations (Optimized) ===
def cleaner_9_tokenize_violations(df: pl.DataFrame, logger=None) -> pl.DataFrame:
    import re

    def log(msg):
        if logger:
            try:
                logger.info(str(msg).encode("ascii", "ignore").decode())
            except Exception:
                logger.info("LOG ERROR (unicode removed)")
        else:
            print(msg)

    def extract_violation_codes(text):
        if not text:
            return []
        return [int(c) for c in re.findall(r"(?:^|\s)(\d{1,2})(?=\s)", text)]

    high_freq_codes = [1, 2, 3, 4, 6, 7, 38]
    category_map = {
        "has_supervision_violation": [1, 2],
        "has_employee_health_violation": [3, 4],
        "has_contamination_violation": [23, 24, 25, 26, 27, 28],
        "has_temp_control_violation": [18, 19, 20, 21, 22],
        "has_food_source_violation": [11, 12, 13, 14],
        "has_equipment_violation": [47, 49, 50, 51, 52],
    }

    # Extract all features in one map_elements call
    def extract_features(text):
        codes = extract_violation_codes(text)
        features = {
            "violation_codes": codes,
            "violation_count": len(codes),
        }
        for code in high_freq_codes:
            features[f"has_violation_{code}"] = int(code in codes)
        for name, group in category_map.items():
            features[name] = int(any(code in codes for code in group))
        return features

    # Use struct dtype to batch all columns
    df = df.with_columns([
        pl.col("violations").map_elements(
            extract_features,
            return_dtype=pl.Struct([
                pl.Field("violation_codes", pl.List(pl.Int64)),
                pl.Field("violation_count", pl.Int64),
                *[
                    pl.Field(f"has_violation_{code}", pl.Int64) for code in high_freq_codes
                ],
                *[
                    pl.Field(cat, pl.Int64) for cat in category_map.keys()
                ]
            ])
        ).alias("violations_struct")
    ])

    # Unpack struct fields into top-level columns
    df = df.unnest("violations_struct")

    log("✅ cleaner_9_tokenize_violations completed.")
    return df
