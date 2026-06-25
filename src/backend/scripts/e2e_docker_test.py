import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path
import httpx

# URLs
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5370").rstrip("/")
HAGENT_URL = os.environ.get("HAGENT_URL", "http://localhost:5360").rstrip("/")
DATASET_PATH = os.environ.get(
    "HAGENT_TEST_DATASET",
    str(Path(__file__).parent.parent / "assets" / "online_shoppers" / "online_shoppers_intention.csv"),
)

async def test_e2e_docker():
    print("=" * 60)
    print("  🚀 DeerFlow-AutoML — Full System Docker E2E Test")
    print("=" * 60)
    print(f"  HAutoML Toolkit URL: {BASE_URL}")
    print(f"  HAgent Bridge URL:   {HAGENT_URL}")
    print(f"  Dataset path:        {DATASET_PATH}")
    print("=" * 60)

    # 1. Register User
    username = f"ci_test_{int(time.time())}"
    email = f"{username}@example.com"
    password = "password123"

    print("\n[1/6] Registering test user...")
    async with httpx.AsyncClient(timeout=30) as client:
        # Check if we can sign up
        signup_payload = {
            "username": username,
            "email": email,
            "gender": "male",
            "date": "01/01/2026",
            "number": "0123456789",
            "fullName": "CI Test User",
            "password": password
        }
        try:
            r = await client.post(f"{BASE_URL}/signup", json=signup_payload)
            if r.status_code == 200:
                print("  ✓ User registered successfully!")
            elif r.status_code == 409:
                print("  ! User already exists, proceeding to login...")
            else:
                print(f"  ✗ Signup failed (HTTP {r.status_code}): {r.text}")
                sys.exit(1)
        except Exception as e:
            print(f"  ✗ Connection to master failed: {e}")
            sys.exit(1)

    # 2. Login to get token and user ID
    print("\n[2/6] Logging in to retrieve JWT token...")
    async with httpx.AsyncClient(timeout=30) as client:
        login_payload = {
            "username": username,
            "password": password
        }
        r = await client.post(f"{BASE_URL}/login", json=login_payload)
        if r.status_code != 200:
            print(f"  ✗ Login failed (HTTP {r.status_code}): {r.text}")
            sys.exit(1)
        
        token_data = r.json()
        token = token_data["access_token"]
        print("  ✓ Login success!")
        
        # Decode JWT token to get User ID
        token_parts = token.split('.')
        payload_b64 = token_parts[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
        user_id = payload.get('sub')
        print(f"  👤 User ID: {user_id}")

    # 3. Upload dataset
    print("\n[3/6] Uploading Online Shoppers Intention dataset...")
    if not os.path.exists(DATASET_PATH):
        print(f"  ✗ Dataset file not found at: {DATASET_PATH}")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=60) as client:
        with open(DATASET_PATH, "rb") as f:
            files = {"file_data": ("online_shoppers_intention.csv", f, "text/csv")}
            data = {
                "data_name": "online_shoppers_intention_ci",
                "data_type": "csv"
            }
            r = await client.post(
                f"{BASE_URL}/upload-dataset?user_id={user_id}",
                data=data,
                files=files,
                headers=headers
            )
            if r.status_code != 200:
                print(f"  ✗ Dataset upload failed (HTTP {r.status_code}): {r.text}")
                sys.exit(1)
            
            ds_result = r.json()
            dataset_id = ds_result.get("_id")
            print(f"  ✓ Dataset uploaded successfully!")
            print(f"    Dataset ID: {dataset_id}")

    # 4. Trigger training via HAgent Chat
    print("\n[4/6] Sending training prompt to HAgent Bridge...")
    chat_prompt = (
        f"Hãy train một model classification trên dataset ID {dataset_id} "
        f"với target column là 'Revenue', dùng 3 thuật toán: RandomForestClassifier, XGBClassifier, SVC. "
        f"Dùng metric là accuracy. Hãy cấu hình và bắt đầu training giúp tôi."
    )
    print(f"  Prompt: \"{chat_prompt}\"")
    
    chat_payload = {
        "message": chat_prompt,
        "conversation_id": None,
        "context": {}
    }
    
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{HAGENT_URL}/api/v1/chat/",
            json=chat_payload,
            headers=headers
        )
        if r.status_code != 200:
            print(f"  ✗ Chat request failed (HTTP {r.status_code}): {r.text}")
            sys.exit(1)
            
        chat_res = r.json()
        conversation_id = chat_res["conversation_id"]
        response_msg = chat_res["message"]
        print("  ✓ Prompt accepted by agent!")
        print(f"    Conversation ID: {conversation_id}")
        print(f"    Agent Response:   {response_msg}")

    # 5. Poll for training results
    print("\n[5/6] Polling conversation history for training results...")
    print("  (AutoML worker container will pick up the task and train model...)")
    
    max_retries = 30
    retry_interval = 10
    training_success = False
    final_messages = []

    for attempt in range(1, max_retries + 1):
        print(f"  [{attempt}/{max_retries}] Polling messages...")
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{HAGENT_URL}/api/v1/chat/conversation/{conversation_id}",
                headers=headers
            )
            if r.status_code == 200:
                history = r.json()
                messages = history.get("messages", [])
                final_messages = messages
                
                # Check if we have an assistant message stating completion
                for msg in messages:
                    if msg["role"] == "assistant" and ("Job training đã hoàn tất" in msg["content"] or "✅ Job training" in msg["content"]):
                        print("\n  🎉 Training results found in conversation history!")
                        print(f"  {'-' * 60}")
                        print(msg["content"])
                        print(f"  {'-' * 60}")
                        training_success = True
                        break
            else:
                print(f"  ! Warning: failed to fetch messages (HTTP {r.status_code})")

        if training_success:
            break
        await asyncio.sleep(retry_interval)

    # 6. Verify Jobs in Master DB
    print("\n[6/6] Checking training jobs status from AutoML Master...")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/get-list-job-by-userId?user_id={user_id}",
            headers=headers
        )
        if r.status_code == 200:
            jobs = r.json()
            if isinstance(jobs, list):
                print(f"  ✓ Found {len(jobs)} job(s) for user {user_id}:")
                for job in jobs:
                    jid = job.get("_id")
                    status = job.get("status")
                    best_model = job.get("best_model_name", "N/A")
                    best_score = job.get("best_score", "N/A")
                    print(f"    - Job ID: {jid} | Status: {status} | Best Model: {best_model} | Score: {best_score}")
            else:
                print(f"  ! List jobs response not a list: {jobs}")
        else:
            print(f"  ✗ Failed to query jobs list (HTTP {r.status_code})")

    if training_success:
        print("\n" + "=" * 60)
        print("  ✅ DOCKER FULL SYSTEM E2E TEST PASSED SUCCESSFULLY!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("  ❌ DOCKER FULL SYSTEM E2E TEST FAILED OR TIMED OUT!")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_e2e_docker())
