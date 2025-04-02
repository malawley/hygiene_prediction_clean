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
def cleaner_9_tokenize_violations(df: pl.DataFrame, logger=None) -> pl.DataFrame:
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
        matches = re.findall(r"(?:^|\s)(\d{1,2})(?=\s)", text)
        return [int(code) for code in matches]

    def has_hand_hygiene(codes):
        return int(any(code in [5, 9, 10, 33, 34, 36, 61] for code in codes))

    df = df.with_columns([
        pl.col("violations").map_elements(extract_violation_codes, return_dtype=pl.List(pl.Int64)).alias("violation_codes")
    ])

    df = df.with_columns([
        pl.col("violation_codes").list.len().alias("violation_count"),
        pl.col("violation_codes").map_elements(has_hand_hygiene, return_dtype=pl.Int8).alias("hand_hygiene_flag")
    ])

    return df