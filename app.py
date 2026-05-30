import time
import json
import sys
from flask import Flask, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def log_step(message: str):
    """Forcefully flushes logs straight to the Railway dashboard terminal."""
    print(f"[RAILWAY SCRAPER LOG] {message}", file=sys.stdout, flush=True)

def dump_driver_subsystems(driver):
    """Extracts internal Chromium network handshake and console error logs."""
    log_step("=== STARTING CHROMIUM INTERNAL SUBSYSTEM DUMP ===")
    try:
        browser_logs = driver.get_log('browser')
        log_step(f"Captured {len(browser_logs)} standard console messages:")
        for log in browser_logs:
            log_step(f"  [BROWSER CONSOLE] [{log.get('level')}] {log.get('message')}")
    except Exception as le:
        log_step(f"Could not extract browser console logs: {le}")

    try:
        perf_logs = driver.get_log('performance')
        log_step(f"Captured {len(perf_logs)} network routing events.")
        # Isolate the final 15 network wire actions to identify firewalls or blocks
        for log in perf_logs[-15:]:
            try:
                log_data = json.loads(log['message'])['message']
                log_step(f"  [CHROME NET] {log_data.get('method')} -> {log_data.get('params', {}).get('errorText', '')}")
            except:
                log_step(f"  [CHROME PERF RAW] {log['message'][:120]}")
    except Exception as le:
        log_step(f"Could not extract performance tracing infrastructure logs: {le}")
    log_step("=== END OF CHROMIUM INTERNAL SUBSYSTEM DUMP ===")

def scrape_gepco_bill(reference_number):
    log_step(f"Initializing scraping workflow context for Reference: {reference_number}")
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1200,800')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_argument('--lang=en-US,en;q=0.9')
    
    # CRITICAL LOW-MEMORY OPTIMIZATIONS FOR 512MB-1GB CORES
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-dev-tools')
    options.add_argument('--dns-prefetch-disable')
    options.add_argument('--no-zygote')
    options.add_argument('--single-process')
    options.add_argument('--js-flags="--max-old-space-size=128"')
    
    # Instruct Chrome to move forward as soon as raw DOM text objects arrive
    options.page_load_strategy = 'eager'
    
    # Register logging targets inside Chromium engine core before execution
    options.set_capability('goog:loggingPrefs', {'browser': 'ALL', 'performance': 'ALL'})
    
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)

    log_step("Spawning headless Chromium Driver instance...")
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        # Give network loops up to 25 seconds to establish transport buffers
        driver.set_page_load_timeout(25)
        driver.set_script_timeout(25)
        log_step("Headless Chromium Driver initialized successfully.")
    except Exception as init_err:
        log_step(f"FATAL ERROR: Driver allocation failed during boot: {str(init_err)}")
        return {"status": "error", "message": f"WebDriver failed to initialize: {str(init_err)}"}
    
    try:
        url = "https://bill.pitc.com.pk/gepcobill"
        log_step(f"Dispatching network request targeting base endpoint: {url}")
        
        start_network_time = time.time()
        try:
            driver.get(url)
            log_step(f"Base page handshake successfully reached in {round(time.time() - start_network_time, 2)}s.")
        except Exception as net_err:
            log_step(f"CRITICAL DISPATCH FAILURE inside driver.get(): {str(net_err)}")
            dump_driver_subsystems(driver)
            raise net_err
        
        log_step(f"Driver confirmed location context. Resolved URL: {driver.current_url} | Title: {driver.title}")
        
        log_step("Polling DOM layout for search input node ('searchTextBox')...")
        wait = WebDriverWait(driver, 15)
        search_box = wait.until(EC.visibility_of_element_located((By.ID, "searchTextBox")))
        log_step("Target reference input element located successfully.")
        
        log_step("Clearing text field and populating 14-digit numeric string...")
        search_box.clear()
        search_box.send_keys(reference_number)
        
        log_step("Validating search execution element ('btnSearch')...")
        search_button = wait.until(EC.element_to_be_clickable((By.ID, "btnSearch")))
        log_step("Click transaction verified. Triggering submit execution...")
        search_button.click()
        
        log_step("Suspending execution thread for 2 seconds to yield window frame changes...")
        time.sleep(2) 
        
        log_step(f"Inspecting active engine contexts. Handles visible: {len(driver.window_handles)}")
        if len(driver.window_handles) > 1:
            log_step("External tab redirect sequence caught. Remapping active driver pointers...")
            driver.switch_to.window(driver.window_handles[-1])
            log_step(f"Pointers successfully bound to secondary window. URL: {driver.current_url}")
        
        log_step("Downloading raw outer HTML string content from active viewport...")
        raw_html = driver.page_source
        log_step(f"Download complete. Buffered string frame size: {len(raw_html)} elements.")
        
        log_step("Streaming string output to BeautifulSoup parsing engine...")
        soup = BeautifulSoup(raw_html, 'html.parser')
        
        log_step("Extracting consumer metrics data tags...")
        # Fallback safe matching array logic for BS4 text components across versions
        id_node = soup.find(string=lambda t: t and "CONSUMER ID" in t) or soup.find(text=lambda t: t and "CONSUMER ID" in t)
        consumer_id = id_node.find_next('tr').find_all('td')[0].text.strip() if id_node else "N/A"
        
        tariff_node = soup.find(string=lambda t: t and "TARIFF" in t) or soup.find(text=lambda t: t and "TARIFF" in t)
        tariff = tariff_node.find_next('tr').find_all('td')[1].text.strip() if tariff_node else "N/A"
        
        ref_table = soup.find('table', class_='nestable1')
        reference_no = "N/A"
        if ref_table:
            ref_rows = ref_table.find_all('tr', class_='content')
            if len(ref_rows) > 1:
                reference_no = ref_rows[1].find('td').text.strip()

        name_address_block = soup.find('p', style=lambda s: s and 'text-align: left' in s)
        address_lines = []
        if name_address_block:
            address_lines = [span.text.strip() for span in name_address_block.find_all('span') if span.text.strip()]
        
        consumer_name = address_lines[1] if len(address_lines) > 1 else "N/A"
        consumer_address = ", ".join(address_lines[2:]) if len(address_lines) > 2 else "N/A"

        meter_node = soup.find(string=lambda t: t and "METER NO" in t) or soup.find(text=lambda t: t and "METER NO" in t)
        meter_row = meter_node.find_all_next('tr', class_='content')[0] if meter_node else None
        if meter_row:
            meter_tds = [td.text.strip().replace('\n', ' ') for td in meter_row.find_all('td')]
            meter_no = meter_tds[0]
            prev_reading = meter_tds[1]
            pres_reading = meter_tds[2]
            units_consumed = meter_tds[4]
        else:
            meter_no = prev_reading = pres_reading = units_consumed = "N/A"

        history_table = soup.find('table', class_='nested6')
        history_data = []
        if history_table:
            history_rows = history_table.find_all('tr', class_='content')
            for row in history_rows:
                tds = [td.text.strip().replace('\n', ' ') for td in row.find_all('td')]
                if len(tds) >= 3:
                    history_data.append({
                        "month": tds[0],
                        "units": tds[1],
                        "bill_amount": tds[2],
                        "payment_status": tds[3] if len(tds) > 3 else "N/A"
                    })

        log_step("Data extraction successfully executed. Preparing dictionary construction...")
        return {
            "status": "success",
            "data": {
                "consumer_name": consumer_name,
                "consumer_address": consumer_address,
                "consumer_id": consumer_id,
                "reference_no": reference_no,
                "tariff": tariff,
                "meter_no": meter_no,
                "previous_reading": prev_reading,
                "present_reading": pres_reading,
                "units_consumed": units_consumed,
                "bill_history": history_data
            }
        }
    except Exception as e:
        log_step(f"EXCEPTION INTERCEPTED DURING SCRAPE THREAD PROCESSING: {str(e)}")
        if driver:
            try:
                dump_driver_subsystems(driver)
            except Exception as dump_fail:
                log_step(f"Subsystem dump failed: {dump_fail}")
        return {"status": "error", "message": str(e)}
    finally:
        if driver:
            log_step("Initiating context browser resource decommissioning routines...")
            try:
                driver.close()
                driver.quit()
                log_step("Sandbox structures isolated and cleaned down safely.")
            except Exception as cleanup_err:
                log_step(f"Resource cleanup notice: {cleanup_err}")

@app.route('/', methods=['GET', 'HEAD'])
def health_check():
    return jsonify({"status": "healthy", "service": "gepco-scraper-railway"}), 200

@app.route('/get-bill/<string:ref_num>', methods=['GET'])
def get_bill(ref_num):
    log_step(f"Inbound routing action captured for path /get-bill/{ref_num}")
    if len(ref_num) != 14 or not ref_num.isdigit():
        log_step("Routing error: Received string input parameter is not a valid 14-digit sequence.")
        return jsonify({"status": "error", "message": "Reference number must be exactly 14 digits."}), 400
        
    result = scrape_gepco_bill(ref_num)
    if result.get("status") == "error":
        log_step(f"Dispatching error dictionary to remote client context: {result.get('message')}")
        return jsonify(result), 500
    
    log_step("Dispatching structured JSON payload down to client destination.")
    return jsonify(result), 200

if __name__ == '__main__':
    # Default fallback to 8080 or port variables populated dynamically via hosting engine
    import os
    target_port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=target_port)
