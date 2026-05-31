import os
import glob
from worker import process_pdf_task

RAW_DATA_DIR = "data/raw"

def submit_jobs():
    """Scans the raw data directory and pushes PDFs into the Redis queue for the Celery workers."""
    print("Scanning for PDFs to submit to the background worker queue...")
    
    pdf_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.pdf"))
    
    if not pdf_files:
        print(f"\n⚠️ No PDFs found in '{RAW_DATA_DIR}/'. Please drop your documents there and run this script again.")
        return

    print(f"\nFound {len(pdf_files)} documents. Submitting jobs to Redis Message Broker...")

    for file_path in pdf_files:
        # .delay() is the Celery magic! 
        # It instantly pushes the function arguments to Redis instead of executing it locally.
        task = process_pdf_task.delay(file_path)
        print(f"✅ Job submitted successfully! [Task ID: {task.id}] -> {file_path}")

    print("\n🎉 All jobs are in the queue. The Celery workers will process them in the background.")

if __name__ == "__main__":
    if not os.path.exists(RAW_DATA_DIR):
        os.makedirs(RAW_DATA_DIR)
    
    submit_jobs()
