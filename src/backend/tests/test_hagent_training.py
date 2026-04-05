"""
Test HAgent training flow end-to-end.
1. Upload dataset via API
2. Send chat message to HAgent asking to train
3. Check backend logs for training API call
"""
import urllib.request
import json
import sys
import os
import time

TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TOKEN", "")
USER_ID = sys.argv[2] if len(sys.argv) > 2 else os.getenv("USER_ID", "")

BASE_URL = "http://localhost:8585"
HAGENT_URL = "http://localhost:8900"

def api_request(method, url, data=None, headers=None, content_type="application/json"):
    """Simple HTTP request helper."""
    if headers is None:
        headers = {}
    headers["Authorization"] = f"Bearer {TOKEN}"
    
    if data and content_type == "application/json":
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body}")
        return {"error": e.code, "detail": body}

def upload_dataset():
    """Upload adult.csv as test dataset."""
    file_path = os.path.join(os.path.dirname(__file__), "..", "data", "adult.csv")
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return None

    boundary = "----BOUNDARY12345"
    with open(file_path, "rb") as f:
        file_data = f.read()

    body = b""
    body += ("--" + boundary + "\r\n").encode()
    body += b'Content-Disposition: form-data; name="file_data"; filename="adult.csv"\r\n'
    body += b"Content-Type: text/csv\r\n\r\n"
    body += file_data
    body += b"\r\n"
    body += ("--" + boundary + "\r\n").encode()
    body += b'Content-Disposition: form-data; name="data_name"\r\n\r\nadult_test_dataset\r\n'
    body += ("--" + boundary + "\r\n").encode()
    body += b'Content-Disposition: form-data; name="data_type"\r\n\r\ncsv\r\n'
    body += ("--" + boundary + "--\r\n").encode()

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = urllib.request.Request(
        f"{BASE_URL}/upload-dataset?user_id={USER_ID}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        return result
    except urllib.error.HTTPError as e:
        print(f"  Upload error {e.code}: {e.read().decode()}")
        return None

def list_datasets():
    """List user's datasets."""
    return api_request("POST", f"{BASE_URL}/get-list-data-by-userid?id={USER_ID}")

def get_available_models():
    """Get available classification models."""
    return api_request("GET", f"{BASE_URL}/api/v1/available-models/classification")

def send_chat(message):
    """Send chat message to HAgent via Bridge."""
    payload = {
        "message": message,
        "conversation_id": None,
        "context": {}
    }
    return api_request("POST", f"{HAGENT_URL}/api/v1/chat/", data=payload)


# ═══════════════════════════════════════════════════════════
# MAIN TEST FLOW
# ═══════════════════════════════════════════════════════════

print("=" * 60)
print("TEST: HAgent Training Flow")
print("=" * 60)

# Step 1: Upload dataset
print("\n[1/5] Uploading dataset...")
upload_result = upload_dataset()
if upload_result and "_id" in upload_result:
    dataset_id = upload_result["_id"]
    print(f"  OK - Dataset uploaded: {dataset_id}")
    print(f"  Name: {upload_result.get('dataName')}")
else:
    print(f"  Upload result: {upload_result}")
    # Try to use existing dataset
    print("  Trying to list existing datasets...")
    datasets = list_datasets()
    if isinstance(datasets, list) and len(datasets) > 0:
        dataset_id = datasets[0]["_id"]
        print(f"  Using existing dataset: {dataset_id} ({datasets[0].get('dataName')})")
    else:
        print(f"  ERROR: No datasets available. Cannot continue.")
        sys.exit(1)

# Step 2: Check available models
print("\n[2/5] Checking available models...")
models = get_available_models()
if "models" in models:
    print(f"  Available models: {models['models']}")
    print(f"  Available metrics: {models['metrics']}")
else:
    print(f"  Response: {models}")

# Step 3: Get dataset info
print(f"\n[3/5] Getting dataset info for {dataset_id}...")
data_info = api_request("GET", f"{BASE_URL}/get-data-info?id={dataset_id}")
print(f"  Dataset info: {json.dumps(data_info, indent=2, ensure_ascii=False)[:500]}")

# Step 4: Send training request to HAgent
print("\n[4/5] Sending training request to HAgent...")
chat_message = (
    f"Hãy train một model classification trên dataset ID {dataset_id} "
    f"với target column là 'income', dùng thuật toán Random Forest, "
    f"metric là accuracy, và search strategy là grid_search. "
    f"Dùng tất cả các feature có sẵn."
)
print(f"  Message: {chat_message}")
print(f"  Waiting for HAgent response (may take up to 2 mins)...")

chat_result = send_chat(chat_message)
print(f"\n  HAgent Response:")
print(f"  {'-' * 50}")
if isinstance(chat_result, dict):
    msg = chat_result.get("message", "No message")
    print(f"  {msg[:1000]}")
    if chat_result.get("sources"):
        print(f"  Sources: {chat_result['sources']}")
    if chat_result.get("suggestions"):
        print(f"  Suggestions: {chat_result['suggestions']}")
    conv_id = chat_result.get("conversation_id")
    print(f"  Conversation ID: {conv_id}")
else:
    print(f"  Raw: {chat_result}")

# Step 5: Check training jobs
print(f"\n[5/5] Checking training jobs for user {USER_ID}...")
time.sleep(3)  # Wait a bit for job to be created
jobs = api_request("POST", f"{BASE_URL}/get-list-job-by-userId?user_id={USER_ID}")
if isinstance(jobs, list):
    print(f"  Total jobs: {len(jobs)}")
    for j in jobs[:3]:
        print(f"  - Job {j.get('_id')}: status={j.get('status')}, model={j.get('best_model_name', 'N/A')}")
else:
    print(f"  Jobs response: {jobs}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
