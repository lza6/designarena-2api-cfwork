import os
import shutil
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
AUTH_FILE = os.path.join(DATA_DIR, "auth", "accounts.json")

def cleanup_orphaned_data():
    print(f"Checking {DATA_DIR} for orphaned data folders...")
    
    valid_ids = set()
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for acc in data.get("accounts", []):
                    valid_ids.add(acc.get("id"))
        except Exception as e:
            print(f"Error reading accounts.json: {e}")

    print(f"Found {len(valid_ids)} active accounts in accounts.json")

    if not os.path.exists(DATA_DIR):
        print("Data directory does not exist.")
        return

    prefixes = ["storage_", "cache_", "mirror_"]
    
    deleted_count = 0
    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
        if not os.path.isdir(item_path):
            continue

        for prefix in prefixes:
            if item.startswith(prefix):
                # Extra check: if it's chrome_mirror, leave it!
                if item == "chrome_mirror":
                    continue
                
                # Check if it corresponds to an active account
                account_id = item[len(prefix):]
                if account_id not in valid_ids:
                    print(f"Deleting orphaned folder: {item}")
                    try:
                        shutil.rmtree(item_path, ignore_errors=True)
                        deleted_count += 1
                    except Exception as e:
                        print(f"Failed to delete {item}: {e}")
                break

    print(f"Cleanup complete. Deleted {deleted_count} orphaned folders.")

if __name__ == "__main__":
    cleanup_orphaned_data()
