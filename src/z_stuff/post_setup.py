# post_setup.py
import nltk
import spacy

print("Downloading NLTK data...")
nltk.download('punkt')
nltk.download('stopwords')

print("Downloading spaCy model...")
import subprocess
subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
