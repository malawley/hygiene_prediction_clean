import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# === Output path ===
image_dir = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(image_dir, exist_ok=True)
output_path = os.path.join(image_dir, "dashboard_landing.png")

# === Create figure ===
fig, ax = plt.subplots(figsize=(12, 7))
ax.set_facecolor("#0e1117")  # dark mode background
fig.patch.set_facecolor("#0e1117")
ax.axis("off")

# === Draw a rounded box for the content ===
box = FancyBboxPatch(
    (0.05, 0.2), 0.9, 0.65,
    boxstyle="round,pad=0.02",
    edgecolor="#4ade80",
    facecolor="#1e293b",
    linewidth=2,
    mutation_scale=0.02
)
ax.add_patch(box)

# === Text content ===
title = "🧠 ML Hygiene Prediction Dashboard"
subtitle = "This dashboard provides:"
bullet_points = [
    "✔️ Model performance visualizations (metrics, confusion matrices, SHAP)",
    "✔️ A tool to explore model predictions interactively",
    "✔️ A ranked risk report for Chicago restaurants"
]

# === Add text ===
plt.text(0.5, 0.78, title, fontsize=24, fontweight="bold", ha="center", color="white")
plt.text(0.5, 0.70, subtitle, fontsize=18, ha="center", color="#a5b4fc")

for i, line in enumerate(bullet_points):
    plt.text(0.5, 0.60 - i*0.1, line, fontsize=14, ha="center", color="#f1f5f9")

# === Save image ===
plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"✅ Saved prettier image to {output_path}")



if __name__ == "__main__":
    ...
