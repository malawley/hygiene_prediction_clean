# 🧼 Hand Hygiene Violation Prediction in Chicago Restaurants

This project predicts whether a restaurant in Chicago is likely to receive a **hand hygiene–related violation** (e.g., lack of handwashing, missing soap, unsanitary sinks) during its next health inspection. Using publicly available inspection data from the City of Chicago, the goal is to identify risk patterns that can help public health departments prioritize inspections and prevent foodborne illness.

---

## 🔍 Project Overview

- **Domain:** Public Health, Machine Learning, City Data
- **Goal:** Binary classification (hygiene violation: yes/no)
- **Data Source:** [City of Chicago Food Inspections](https://data.cityofchicago.org/Health-Human-Services/Food-Inspections/4ijn-s7e5)
- **Tech Stack:** Python, Pandas, Polars, Scikit-learn, Jupyter, FastAPI, GCP, AWS

---

## 🗂️ Project Structure

```
hand_hygiene_prediction/
├── data/
│   └── chicago_food_inspections.csv       # raw dataset
├── notebooks/
│   ├── 01_eda.ipynb                        # initial data exploration
│   ├── 02_feature_engineering.ipynb        # target + feature prep
│   └── 03_model_training.ipynb             # training and evaluation
├── models/
│   └── hygiene_model.pkl                   # saved model (optional)
├── src/
│   └── hygiene_cleaning.py                 # data cleaning functions
├── hygiene_predictor.py                    # script for batch predictions
├── app.py                                  # (optional) FastAPI service
├── environment.yml                         # Conda environment
├── requirements.txt                        # pip-based environment
├── setup.bat                               # Windows setup script
├── post_setup.py                           # Downloads NLP resources
└── README.md
```

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

## 🛠️ Environment Setup

This project supports both **Conda (recommended)** and **pip-based** setups.

### ✅ Option 1: Conda (recommended)

```bash
conda env create -f environment.yml
conda activate hygiene-ml
python post_setup.py  # Downloads NLTK and spaCy models
```

### ✅ Option 2: pip (for virtualenv, Docker, etc.)

```bash
python -m venv venv
venv\Scripts\activate     # Windows
# or
source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

---

## 🚀 Running the Project

To launch JupyterLab:

```bash
jupyter lab
```

To launch classic Jupyter Notebook:

```bash
jupyter notebook
```

To run the FastAPI app (if included):

```bash
uvicorn app:app --reload
```

---

## 🧩 File Descriptions

- `environment.yml` – Full Conda-based environment with ML, NLP, and cloud tools  
- `requirements.txt` – Pip-based dependency list for virtualenv or Docker use  
- `setup.bat` – Windows batch script for quick setup  
- `post_setup.py` – Downloads NLTK and spaCy resources  

---

## 🤝 Contributing

Pull requests are welcome! Please open an issue first to discuss any major changes.  
Make sure your code follows the existing style and is well-documented.

---

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.
