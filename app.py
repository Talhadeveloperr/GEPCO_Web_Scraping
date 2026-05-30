import sys
import requests
from flask import Flask, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def log_step(message: str):
    print(f"[RAILWAY HTTP LOG] {message}", file=sys.stdout, flush=True)

def scrape_gepco_bill_direct(reference_number):
    log_step(f"Initiating direct HTTP post request sequence for: {reference_number}")
    
    # We target the actual structural target endpoint directly
    url = "https://bill.pitc.com.pk/gepcobill/general"
    
    # Mirror realistic customer connection headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://bill.pitc.com.pk",
        "Referer": "https://bill.pitc.com.pk/gepcobill"
    }
    
    # Pack the exact form key-value pairs the site's search button sends
    payload = {
        "txtRefNo": reference_number,
        "btnSearch": "Search"
    }

    try:
        log_step("Sending payload over native connection socket...")
        response = requests.post(url, data=payload, headers=headers, timeout=20)
        log_step(f"Server responded with status code: {response.status_code}")
        
        if response.status_code != 200:
            return {"status": "error", "message": f"PITC Server rejected request with status code {response.status_code}"}

        raw_html = response.text
        log_step(f"HTML downloaded successfully. Content size: {len(raw_html)} characters.")
        
        if "Invalid Reference Number" in raw_html or len(raw_html) < 2000:
            return {"status": "error", "message": "The bill was not found or reference number is invalid."}

        log_step("Streaming document stream to BeautifulSoup parser...")
        soup = BeautifulSoup(raw_html, 'html.parser')
        
        # --- Parsing Logic ---
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
        log_step(f"Network processing exception triggered: {str(e)}")
        return {"status": "error", "message": f"Connection Failure: {str(e)}"}

@app.route('/', methods=['GET', 'HEAD'])
def health_check():
    return jsonify({"status": "healthy", "service": "gepco-scraper-http-direct"}), 200

@app.route('/get-bill/<string:ref_num>', methods=['GET'])
def get_bill(ref_num):
    log_step(f"Inbound request for path /get-bill/{ref_num}")
    if len(ref_num) != 14 or not ref_num.isdigit():
        return jsonify({"status": "error", "message": "Reference number must be exactly 14 digits."}), 400
        
    result = scrape_gepco_bill_direct(ref_num)
    if result.get("status") == "error":
        return jsonify(result), 500
    
    return jsonify(result), 200

if __name__ == '__main__':
    import os
    target_port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=target_port)
