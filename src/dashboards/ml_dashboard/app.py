import streamlit as st
from PIL import Image
import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

# === Layout & Config ===
st.set_page_config(page_title="Risk Scoring Dashboard", layout="wide")
st.sidebar.header("📍 Navigation")
section = st.sidebar.radio("Go to", ["🖼️ ML Summary", "📊 Generate Risk Report"])

# === Shared Image Display with Optional Scaling ===
def show_image(filename, caption=None, scale=1.0):
    IMAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "images"))
    path = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(path):
        st.error(f"❌ Image not found: {filename}")
        return

    img = Image.open(path)
    if scale != 1.0:
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size)
    st.image(img, caption=caption, use_container_width=False)

# === 🖼️ ML Summary ===
if section == "🖼️ ML Summary":
    st.title("🖼️ ML Model & Risk Summary")

    image_options = {
        "Dashboard Landing": "dashboard_landing.png",
        "Two-Stage Classification Flowchart": "two_stage_flowchart_corrected_arrows.png",    
        "Ensemble Confusion Matrix": "ensemble_confusion_matrix.png",
        "Ensemble ROC Curve": "ensemble_roc_curve.png",
        "Ensemble Metrics Table": "ensemble_metrics_table_clean.png",
        "Ensemble Feature Importance": "ensemble_feature_importance.png",
        "SHAP Summary - XGBoost": "shap_summary_xgb.png",
        "TP vs FP Confusion Matrix": "tp_fp_confusion_matrix.png",
        "TP vs FP Feature Importance": "tp_fp_feature_importance.png",
        "Tiered Decision Precision-Recall Table": "tiered_decision_precision_recall_table.png",
        "Outcomes by Decision Group": "outcomes_by_decision_group.png",
        "Two-Stage Decision Tree": "two_stage_decision_with_guidance_no_emoji.png"
    }

    # List of images to scale down by 50%
    scaled_images = [
        "two_stage_flowchart_corrected_arrows.png",

        "ensemble_roc_curve.png",
        "ensemble_metrics_table_clean.png",
        "ensemble_confusion_matrix.png",
        "shap_summary_xgb.png",
     
        "tiered_decision_precision_recall_table.png",
        
        "two_stage_decision_with_guidance_no_emoji.png"
    ]

    for label, filename in image_options.items():
        st.subheader(label)
        scale = 0.5 if filename in scaled_images else 1.0
        show_image(filename, caption=label, scale=scale)

# === 📊 Generate Risk Report ===
elif section == "📊 Generate Risk Report":
    st.title("📊 Generate Restaurant Risk Report")
    
    with st.form("risk_form"):
        inspector_id = st.number_input("Inspector ID", min_value=1, step=1, value=23)
        sample_size = st.number_input("Number of Inspections to Evaluate", min_value=10, max_value=1000, value=100, step=10)
        seed = st.number_input("Random Seed", min_value=0, value=42, step=1)
        submitted = st.form_submit_button("🚀 Generate Report")

    if submitted:
        request_payload = {
            "inspector_id": int(inspector_id),
            "n": int(sample_size),
            "seed": int(seed)
        }

        st.info("⏳ Sending request to backend...")
        start_time = time.time()

        try:
            response = requests.post(
                "http://127.0.0.1:8090/generate_report",
                json=request_payload,
                headers={"Content-Type": "application/json"}
            )
            elapsed = int(time.time() - start_time)

            if response.status_code == 200:
                signed_url = response.json().get("download_url")
                st.success(f"✅ Report generated in {elapsed} seconds.")
                if signed_url:
                    st.markdown(f"[📥 Click here to download your CSV report]({signed_url})", unsafe_allow_html=True)
                else:
                    st.warning("⚠️ No download URL returned.")
            else:
                st.error(f"❌ API error {response.status_code}: {response.text}")

        except Exception as e:
            st.exception(f"🚨 Failed to reach backend: {e}")
            
            
