from playwright.sync_api import sync_playwright
import subprocess
import time
from datetime import datetime

# === Prepare log file ===
now = datetime.now()
timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"ui_test_log_{timestamp}.txt"
log_lines = [f"=== UI Test Log @ {now.strftime('%Y-%m-%d %H:%M:%S')} ===\n"]

def log(msg):
    print(msg)
    log_lines.append(msg)

# === Step 1: Launch Streamlit ===
streamlit_proc = subprocess.Popen(
    ["streamlit", "run", "app.py", "--server.port=8501"],
    cwd=".."
)
time.sleep(5)  # Give Streamlit time to start

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # === Load Streamlit UI ===
        page.goto("http://localhost:8501", wait_until="load")
        page.wait_for_timeout(3000)

        # === Save HTML for debugging
        with open("page_dump.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        log("📄 Saved page HTML to page_dump.html")

        # === Select the report section
        log("🔘 Selecting '📊 Generate Risk Report' from sidebar...")
        page.get_by_text("📊 Generate Risk Report").click()
        page.wait_for_timeout(1000)

        # === Wait for all inputs to appear
        log("🔍 Waiting for all input fields...")
        for attempt in range(5):
            page.wait_for_timeout(1000)
            text_inputs = page.locator("input[type='text'], input[type='number']")
            count = text_inputs.count()
            log(f"Attempt {attempt + 1}: found {count} inputs")
            if count >= 5:
                break
        else:
            log("❌ Not all input fields appeared. Aborting.")
            raise SystemExit

        # === Fill all inputs
        text_inputs.nth(0).fill("insp_a")
        text_inputs.nth(1).fill("2023_12")
        text_inputs.nth(2).fill("50")
        text_inputs.nth(3).fill("10")
        text_inputs.nth(4).fill("42")
        log("✅ All input fields filled.")

        # === Click the Generate Report button
        log("🚀 Clicking '🚀 Generate Risk Report' button...")
        page.wait_for_selector("text=🚀 Generate Risk Report", timeout=15000)
        page.get_by_text("🚀 Generate Risk Report").click()

        # === Wait for pipeline completion
        log("⏳ Waiting up to 70 seconds for pipeline success...")
        page.wait_for_selector("text=✅ Pipeline completed successfully", timeout=70000)
        log("✅ Pipeline completed successfully.")

        # === Look for GCS download link
        log("🔍 Checking for download link...")
        page.wait_for_timeout(2000)

        links = page.locator("a")
        found = False
        for i in range(links.count()):
            href = links.nth(i).get_attribute("href")
            if href and "storage.googleapis.com" in href:
                log(f"✅ Found download link: {href}")
                found = True
                break

        if not found:
            log("⚠️ Pipeline succeeded, but no download link was found.")

        browser.close()

finally:
    streamlit_proc.terminate()
    streamlit_proc.wait()
    log("🧼 Streamlit app terminated.")

    with open(log_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    print(f"📝 Log written to {log_filename}")
