import time
import os
from flask import Flask, jsonify, request
from flask_cors import CORS  # <-- Added for CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)  # <-- This enables CORS for all routes, fixing the origin block

def scrape_gepco_bill(reference_number):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # FIX FOR 502 ERROR: Point Selenium directly to where your render.yaml installs Chrome
    chrome_bin_path = "/home/render/.chrome/chrome-linux64/chrome"
    if os.path.exists(chrome_bin_path):
        options.binary_location = chrome_bin_path
    
    try:
        # Standard Selenium startup
        driver = webdriver.Chrome(options=options)
    except Exception as init_err:
        return {"status": "error", "message": f"WebDriver failed to initialize: {str(init_err)}"}
    
    try:
        url = "https://bill.pitc.com.pk/gepcobill"
        driver.get(url)
        
        wait = WebDriverWait(driver, 10)
        search_box = wait.until(EC.visibility_of_element_located((By.ID, "searchTextBox")))
        
        search_box.clear()
        search_box.send_keys(reference_number)
        
        search_button = wait.until(EC.element_to_be_clickable((By.ID, "btnSearch")))
        search_button.click()
        
        time.sleep(3) 
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. Extract Consumer & Billing Information
        consumer_id = soup.find(text=lambda t: t and "CONSUMER ID" in t).find_next('tr').find_all('td')[0].text.strip() if soup.find(text=lambda t: t and "CONSUMER ID" in t) else "N/A"
        tariff = soup.find(text=lambda t: t and "TARIFF" in t).find_next('tr').find_all('td')[1].text.strip() if soup.find(text=lambda t: t and "TARIFF" in t) else "N/A"
        
        ref_table = soup.find('table', class_='nestable1')
        reference_no = "N/A"
        if ref_table:
            ref_rows = ref_table.find_all('tr', class_='content')
            if len(ref_rows) > 1:
                reference_no = ref_rows[1].find('td').text.strip()

        # 2. Extract Name & Address
        name_address_block = soup.find('p', style=lambda s: s and 'text-align: left' in s)
        address_lines = []
        if name_address_block:
            address_lines = [span.text.strip() for span in name_address_block.find_all('span') if span.text.strip()]
        
        consumer_name = address_lines[1] if len(address_lines) > 1 else "N/A"
        consumer_address = ", ".join(address_lines[2:]) if len(address_lines) > 2 else "N/A"

        # 3. Extract Meter Readings
        meter_row = soup.find(text=lambda t: t and "METER NO" in t).find_all_next('tr', class_='content')[0] if soup.find(text=lambda t: t and "METER NO" in t) else None
        if meter_row:
            meter_tds = [td.text.strip().replace('\n', ' ') for td in meter_row.find_all('td')]
            meter_no = meter_tds[0]
            prev_reading = meter_tds[1]
            pres_reading = meter_tds[2]
            units_consumed = meter_tds[4]
        else:
            meter_no = prev_reading = pres_reading = units_consumed = "N/A"

        # 4. Extract 12-Month Bill History
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
        return {"status": "error", "message": str(e)}
        
    finally:
        try:
            driver.quit()
        except:
            pass

@app.route('/get-bill/<string:ref_num>', methods=['GET'])
def get_bill(ref_num):
    if len(ref_num) != 14:
        return jsonify({"status": "error", "message": "Reference number must be exactly 14 digits."}), 400
        
    result = scrape_gepco_bill(ref_num)
    if result.get("status") == "error":
        return jsonify(result), 500
    return jsonify(result), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)