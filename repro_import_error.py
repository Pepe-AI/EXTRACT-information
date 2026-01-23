
import sys
import traceback

print("Attempting to import app.extractor...")
try:
    from app import extractor
    print("Import successful!")
except Exception:
    with open('error_log.txt', 'w') as f:
        traceback.print_exc(file=f)
    print("Error written to error_log.txt")
