import streamlit as st
from PIL import Image
import os
import sys
import requests
import yaml
import time

# === Add project root to Python path ===
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# === App Layout ===
st.set_page_config(page_title="ML Model Performance Dashboard", layout="wide")
st.sidebar.header("📍 Choose Section")
section = st.sidebar.radio("Navigation", [
    "🏠 Welcome",
    "🖼️ Image Explorer",
    "📊 Generate Risk Report"
])

st.title("🧠 ML Model Performance Dashboard")

# === Shared image loader ===
def show_image(filename, caption=None):
    IMAGE_DIR = os.path.join(os.path.dirname(__file__), "images")
    path = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(path):
        st.error(f"Image not found: {filename}")
        return
    img = Image.open(path)

    custom_resize = {
        "training_pipeline_flowchart.png"
    }

    no_resize = {
        "dashboard_landing.png",
        "predicted_failure_probabilities_summary.png",
        "shap_general_interpretation_summary.png",
    }

    if filename in custom_resize:
        resized = img.resize((int(img.width * 0.6), int(img.height * 0.6)))
        st.image(resized, caption=caption)
    elif filename in no_resize:
        st.image(img, caption=caption, use_container_width=True)
    else:
        resized = img.resize((int(img.width * 0.25), int(img.height * 0.25)))
        st.image(resized, caption=caption)

# === Welcome page ===
if section == "🏠 Welcome":
    st.subheader("Welcome")
    show_image("dashboard_landing.png", caption="Welcome")

# === Image Explorer ===
elif section == "🖼️ Image Explorer":
    IMAGE_DIR = os.path.join(os.path.dirname(__file__), "images")

    image_options = {
        "Distribution of Historical Inspection Outcomes": "distribution_of_inspection_outcomes.png",
        "XGBoost Predicted Risk Distribution Across Restaurants": "risk_zone_breakdown_callout.png",
        "XGBoost Training Pipeline Flowchart": "training_pipeline_flowchart.png",
        "Ensemble Failure Probabilities Before Splitting": "probability_of_failure_distribution.png",
        "XGBoost Failure Probabilities After Splitting": "predicted_failure_probabilities_histogram_with_median.png",
        "Interpretation: Failure Probabilities After Splitting": "predicted_failure_probabilities_summary.png",
        "XGBoost Performance Across Folds": "model_performance_across_folds.png",
        "Average XGBoost Metrics": "average_model_metrics_from_real_data.png",
        "High-Risk XGBoost Confusion Matrix": "high_risk_confusion_matrix_heatmap.png",
        "Low-Risk XGBoost Confusion Matrix": "low_risk_confusion_matrix_heatmap.png",
        "High-Risk XGBoost Feature Importance": "high_risk_xgb_feature_importance.png",
        "Low-Risk XGBoost Feature Importance": "low_risk_xgb_feature_importance.png",
        "High-Risk SHAP Summary": "high_risk_xgb_shap_summary_labeled.png",
        "Low-Risk SHAP Summary": "low_risk_xgb_shap_summary.png",
        "Interpretation: SHAP Images ": "shap_general_interpretation_summary.png"
    }

    # Validate images exist
    missing = [f for f in image_options.values() if not os.path.exists(os.path.join(IMAGE_DIR, f))]
    if missing:
        st.warning("⚠️ Missing image files:")
        for m in missing:
            st.text(m)

    st.sidebar.header("Select a Visualization")
    selected_label = st.sidebar.radio("Choose what to display:", list(image_options.keys()))
    selected_filename = image_options[selected_label]

    st.subheader(selected_label)
    show_image(selected_filename, caption=selected_label)

# === Risk Report Microservice (Client) ===
# === Risk Report Microservice (Client) ===
# === Risk Report Trigger Only (No download) ===
elif section == "📊 Generate Risk Report":
    import requests
    import yaml
    import time

    st.header("📊 Generate a Risk Ranking Report")

    with st.form("risk_form"):
        inspector_id = st.text_input("Inspector ID", "I23")
        month_year_tag = str(st.text_input("Month-Year Tag", "04-28-2025"))
        n = st.number_input("Total number of facilities to evaluate (n)", min_value=10, max_value=5000, value=40, step=10)
        top_n = st.number_input("Number of top risky facilities to include", min_value=10, max_value=500, value=20, step=10)
        seed = st.number_input("Random seed for reproducibility", min_value=0, value=42, step=1)
        submitted = st.form_submit_button("🚀 Generate Risk Report")

    if submitted:
        request_payload = {
            "inspector_id": inspector_id,
            "month_year_tag": month_year_tag,
            "n": int(n),
            "top_n": int(top_n),
            "seed": int(seed)
        }

        #st.code(yaml.dump(request_payload), language="yaml")

        spinner = st.empty()
        start_time = time.time()

        with spinner.status("🔄 Starting pipeline..."):
            try:
                response = requests.post(
                    "http://localhost:8090/generate_report",
                    json=request_payload,
                    headers={"Content-Type": "application/json"}
                )
                st.write("🔍 Raw response:", response.text)
                spinner.empty()
                elapsed = int(time.time() - start_time)

                if response.status_code == 200:
                    signed_url = response.json().get("download_url")
                    st.session_state["pipeline_done"] = True
                    st.session_state["pipeline_elapsed"] = elapsed
                    st.session_state["signed_url"] = signed_url
                else:
                    st.error(f"❌ FastAPI returned {response.status_code}:\n{response.text}")

            except Exception as e:
                spinner.empty()
                st.error(f"❌ Failed to contact microservice: {e}")

    if st.session_state.get("pipeline_done"):
        elapsed = st.session_state.get("pipeline_elapsed", "?")
        signed_url = st.session_state.get("signed_url")

        st.success(f"✅ Pipeline completed successfully in {elapsed} seconds.")

        if signed_url:
            st.markdown(f"[📥 Click here to download the report]({signed_url})", unsafe_allow_html=True)
        else:
            st.warning("⚠️ Report is ready, but download link is missing.")

        if st.button("🔄 Refresh page"):
            for key in ("pipeline_done", "pipeline_elapsed", "signed_url"):
                st.session_state.pop(key, None)
            st.rerun()
