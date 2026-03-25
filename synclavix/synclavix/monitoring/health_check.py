import os
import json
from datetime import datetime, timedelta
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.logger import setup_logger

logger = setup_logger("health_check")

def check_filter_status(data_dir="data", max_age_hours=2):
    """
    Check if filter_status.json exists and is recent.
    Returns True if healthy.
    """
    status_file = os.path.join(data_dir, "filter_status.json")
    if not os.path.exists(status_file):
        logger.warning("filter_status.json not found")
        return False

    try:
        with open(status_file, 'r') as f:
            data = json.load(f)
        timestamp = data.get("timestamp")
        if not timestamp:
            logger.warning("No timestamp in filter_status.json")
            return False
        ts = datetime.fromisoformat(timestamp)
        age = datetime.now() - ts
        if age > timedelta(hours=max_age_hours):
            logger.warning(f"filter_status.json is {age} old")
            return False
        logger.info(f"Filter status OK, age: {age}")
        return True
    except Exception as e:
        logger.error(f"Error reading filter_status.json: {e}")
        return False

def main():
    if check_filter_status():
        print("✅ Health check passed")
    else:
        print("❌ Health check failed")

if __name__ == "__main__":
    main()
