# 🧼 Hand Hygiene Violation Prediction in Chicago Restaurants

This project predicts whether a restaurant in Chicago is likely to receive a **hand hygiene–related violation** (e.g., lack of handwashing, missing soap, unsanitary sinks) during its next health inspection. Using publicly available inspection data from the City of Chicago, the goal is to identify risk patterns that can help public health departments prioritize inspections and prevent foodborne illness.

---

## 🔍 Project Overview

- **Domain:** Public Health, Machine Learning, City Data
- **Goal:** Binary classification (hygiene violation: yes/no)
- **Data Source:** [City of Chicago Food Inspections](https://data.cityofchicago.org/Health-Human-Services/Food-Inspections/4ijn-s7e5)
- **Tech Stack:** Python, Pandas, Scikit-learn, Jupyter

---

## 🗂️ Project Structure

hand_hygiene_prediction/
│
├── data/
│   └── chicago_food_inspections.csv  # raw dataset
│
├── notebooks/
│   └── 01_eda.ipynb                  # initial data exploration
│   └── 02_feature_engineering.ipynb  # target + feature prep
│   └── 03_model_training.ipynb       # training and evaluation
│
├── models/
│   └── hygiene_model.pkl             # saved model (optional)
│
├── hygiene_predictor.py              # script for batch predictions
└── README.md



---

## 🧪 Modeling Approach

1. **Target variable:** 
   - 1 if the inspection report includes a hand hygiene–related violation
   - 0 otherwise

2. **Key features:**
   - Risk level (`risk`)
   - Inspection type (`inspection_type`)
   - Date info (month, day of week)
   - ZIP code
   - Past violation counts (if available)

3. **Models used:**
   - Logistic Regression
   - Random Forest
   - XGBoost (optional)

4. **Evaluation Metrics:**
   - Accuracy, Precision, Recall, F1 Score
   - ROC-AUC for imbalanced classification

---

## 📈 Example Use Cases

- Public health inspectors can prioritize high-risk locations.
- Restaurant groups can monitor compliance and reduce violations.
- Future expansion to other hygiene categories or cities.

---

## 🚀 How to Run

1. Clone the repo:
```bash
git clone https://github.com/malawley/hand-hygiene-prediction.git
cd hand-hygiene-prediction
