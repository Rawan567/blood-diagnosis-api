"""
Automated cleanup job for soft-deleted accounts
Run daily via cron: 0 2 * * * python scripts/cleanup_job.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.services.deletion_service import permanent_delete_expired_accounts

def main():
    print("🔄 Starting cleanup job...")
    db = SessionLocal()
    try:
        count = permanent_delete_expired_accounts(db)
        print(f"✅ Cleanup completed: {count} accounts permanently deleted")
    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()