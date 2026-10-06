import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.worker import run_worker_loop

if __name__ == "__main__":
    print("Starting DocumentFlow Worker process...")
    run_worker_loop()
