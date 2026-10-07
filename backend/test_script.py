import os
import sys
sys.path.insert(0, os.path.abspath("."))
from app.services.processors.pipeline import process_document

res = process_document("../samples/marksheet/sample_transcript.pdf")
print("RESULT:", res)
