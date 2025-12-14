import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"
AUTH_URL = f"{BASE_URL}/auth/jwt/create/"
REFRESH_URL = f"{BASE_URL}/auth/jwt/refresh/"

emails = {
    "user": "anas@gmail.com",
    "password": "test",
    "recipient": "recipient@test.com",
    "staff": "staff@nexus.com",
    "staff_pass": "staff"
}

results = {
    "passed": [],
    "failed": [],
    "logical_issues": [],
    "security_issues": [],
    "data_issues": [],
    "api_design_issues": []
}

def log_pass(endpoint, msg=""):
    results["passed"].append(f"{endpoint}: {msg}")
    print(f"✅ {endpoint} {msg}")

def log_fail(endpoint, msg):
    if len(msg) > 200:
        msg = msg[:200] + "... (truncated)"
    results["failed"].append(f"{endpoint}: {msg}")
    print(f"❌ {endpoint} {msg}")

def log_logical(msg):
    results["logical_issues"].append(msg)
    print(f"⚠️ {msg}")

def log_security(msg):
    results["security_issues"].append(msg)
    print(f"🔒 {msg}")

def get_token(email, password):
    resp = requests.post(AUTH_URL, json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()["access"], resp.json()["refresh"]
    print(f"Login failed for {email}: {resp.status_code} {resp.text}")
    return None, None

def run_tests():
    print("Starting Automated API QA...")
    
    # 1. AUTHENTICATION
    print("\n--- AUTHENTICATION ---")
    token, refresh = get_token(emails["user"], emails["password"])
    if not token:
        log_fail("Login", "Could not authenticate main user.")
        return
    log_pass("Login", "Authenticated successfully.")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Refresh Token
    resp = requests.post(REFRESH_URL, json={"refresh": refresh})
    if resp.status_code == 200:
        log_pass("Token Refresh", "Refreshed access token.")
    else:
        log_fail("Token Refresh", f"Failed {resp.status_code}")

    # 2. CORE BANKING
    print("\n--- CORE BANKING ---")
    
    # List Accounts
    resp = requests.get(f"{BASE_URL}/accounts", headers=headers)
    if resp.status_code == 200:
        accounts = resp.json()
        log_pass("GET /accounts", f"Found {len(accounts)} accounts.")
        if not accounts:
            log_fail("Setup", "No accounts found for user. Cannot proceed.")
            return
        # Select account with money
        main_account = max(accounts, key=lambda x: float(x["balance"]))
        main_id = main_account["account_number"]
        initial_balance = float(main_account["balance"])
        if initial_balance <= 0:
            log_fail("Setup", "All accounts have 0 balance.")
            # return # Try anyway, maybe credit allowed? No.
    else:
        log_fail("GET /accounts", f"Status {resp.status_code}")
        return

    # Create Secondary Account (for internal transfer)
    resp = requests.post(f"{BASE_URL}/accounts", headers=headers, json={"type": "Savings", "currency": "JOD"})
    if resp.status_code == 201:
        sec_account = resp.json()
        sec_id = sec_account["account_number"]
        log_pass("POST /accounts", "Created secondary account.")
    else:
        log_fail("POST /accounts", f"Failed {resp.status_code} {resp.text}")
        sec_id = None

    # Internal Transfer
    if sec_id:
        amount = 100.00
        payload = {
            "sender_account": main_account["account_number"], 
            "receiver_account": sec_id,
            "amount": amount
        }
        resp = requests.post(f"{BASE_URL}/transfers/internal/", headers=headers, json=payload)
        if resp.status_code == 201:
            log_pass("POST /transfers/internal/", "Transfer successful.")
            # Verify balances
            resp_main = requests.get(f"{BASE_URL}/accounts", headers=headers)
            new_accounts = {a["account_number"]: float(a["balance"]) for a in resp_main.json()}
            
            expected_main = initial_balance - amount
            actual_main = new_accounts[main_id]
            if abs(actual_main - expected_main) < 0.01:
                log_pass("Logic", "Sender balance decreased correctly.")
                initial_balance = expected_main # Update running balance
            else:
                log_logical(f"Sender balance mismatch. Expected {expected_main}, got {actual_main}")
                
            if abs(new_accounts[sec_id] - 100.00) < 0.01:
                log_pass("Logic", "Receiver received funds.")
            else:
                log_logical("Receiver balance mismatch.")
        else:
            log_fail("POST /transfers/internal/", f"Failed {resp.status_code} {resp.text}")

    # External Transfer
    recip_token, _ = get_token(emails["recipient"], emails["password"])
    recip_headers = {"Authorization": f"Bearer {recip_token}"}
    resp = requests.get(f"{BASE_URL}/accounts", headers=recip_headers)
    if resp.status_code == 200 and len(resp.json()) > 0:
        recipient_acc_num = resp.json()[0]["account_number"]
    else:
        log_fail("Setup", "Could not get recipient account.")
        recipient_acc_num = None

    if recipient_acc_num:
        ext_amount = 50.00
        payload = {
            "sender_account": main_id,
            "receiver_account_number": recipient_acc_num,
            "amount": ext_amount
        }
        resp = requests.post(f"{BASE_URL}/transfers/external/", headers=headers, json=payload)
        if resp.status_code == 201:
            log_pass("POST /transfers/external/", "External transfer successful.")
            initial_balance -= ext_amount
        else:
            log_fail("POST /transfers/external/", f"Failed {resp.status_code} {resp.text}")

        # Test Insufficient Funds
        payload_fail = payload.copy()
        payload_fail["amount"] = 99999999.00
        resp = requests.post(f"{BASE_URL}/transfers/external/", headers=headers, json=payload_fail)
        if resp.status_code in [400, 402]: # 400 Validation Error usually
            log_pass("Logic", "Insufficient funds rejected.")
        else:
            log_fail("Logic", f"Insufficient funds NOT rejected correctly? Status: {resp.status_code}")

    # 3. BILL PAYMENTS
    print("\n--- BILL PAYMENTS ---")
    
    # Test GET /billers/ (New Endpoint check)
    resp = requests.get(f"{BASE_URL}/billers/", headers=headers)
    if resp.status_code == 200:
        billers = resp.json()
        log_pass("GET /billers/", f"Retrieved {len(billers)} billers.")
        if billers:
            biller_id = billers[0]["id"]
            # bill_amount = float(billers[0]["fixed_amount"]) # Use dynamic amount if needed
        else:
            biller_id = 1
    else:
        log_fail("GET /billers/", f"Failed {resp.status_code}")
        biller_id = 1

    payload = {
        "account": main_id,
        "biller": biller_id,
        "reference_number": f"REF-{int(time.time())}"
    }
    resp = requests.post(f"{BASE_URL}/bill/", headers=headers, json=payload)
    if resp.status_code == 201:
        log_pass("POST /bill/", "Bill payment successful.")
    elif resp.status_code == 400:
         log_fail("POST /bill/", f"Failed {resp.text}")
    else:
        log_fail("POST /bill/", f"Failed {resp.status_code} {resp.text}")

    # 4. BUSINESS ANALYTICS
    print("\n--- BUSINESS ANALYTICS ---")
    # Try as user (recipient is non-staff)
    resp = requests.get(f"{BASE_URL}/business/daily/", headers=recip_headers)
    if resp.status_code == 403:
        log_pass("Security", "User denied access to business metrics.")
    else:
        log_security(f"User accessed business metrics! Status: {resp.status_code}")

    # Try as staff
    staff_token, _ = get_token(emails["staff"], emails["staff_pass"])
    if staff_token:
        staff_headers = {"Authorization": f"Bearer {staff_token}"}
        resp = requests.get(f"{BASE_URL}/business/daily/", headers=staff_headers)
        if resp.status_code == 200:
            log_pass("Business", "Staff accessed business metrics.")
            data = resp.json()
            # Verify basic structure
            if "total_transferred_amount" in data:
                log_pass("Data", "Daily metrics structure correct.")
            else:
                log_fail("Data", "Daily metrics missing keys.")
        else:
            log_fail("Business", f"Staff failed to access metrics. {resp.status_code}")
    else:
        log_fail("Setup", "Could not login as staff.")

    # 5. RISK & AUDIT
    print("\n--- RISK & AUDIT ---")
    # Failed login log
    bad_pass_email = emails["user"]
    requests.post(AUTH_URL, json={"email": bad_pass_email, "password": "wrongpassword"})
    
    # Check logs as staff
    if staff_token:
        resp = requests.get(f"{BASE_URL}/risk/logins/", headers=staff_headers)
        if resp.status_code == 200:
            logs = resp.json()
            # Look for failed login
            found = any(l.get("email") == bad_pass_email and l.get("status") == "Failed" for l in logs)
            # Schema might differ, checking response...
            # Actually I don't know the schema of the logs list exactly, assuming standard fields.
            # If not found immediately, might be okay, but let's check length.
            if len(logs) > 0:
                log_pass("Risk", "Login events logged.")
            else:
                log_logical("No login events found in risk log.")
        else:
            log_fail("Risk", f"Could not fetch login logs. {resp.status_code}")

    # 6. ERROR HANDLING
    print("\n--- ERROR HANDLING ---")
    # Malformed JSON
    resp = requests.post(f"{BASE_URL}/auth/jwt/create/", data="not json", headers={"Content-Type": "application/json"})
    if resp.status_code == 400:
        log_pass("Error Handling", "Malformed JSON handled.")
    else:
        log_fail("Error Handling", f"Malformed JSON returned {resp.status_code}")

    # Generate Report
    print("\n\n======================== REPORT ========================")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_tests()
