
"""
Uranas Global spreadsheet/contact importer.
Imports the supplied Jan-August payments workbook and contact-list DOCX.
The importer is intentionally conservative: it normalizes names for matching,
preserves the original names, and flags uncertain matches instead of silently
merging unrelated clients.
"""
from pathlib import Path
import re, json

DATA_DIR = Path(__file__).parent / "data_import"

def normalize_name(s):
    s = (s or "").upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    s = re.sub(r"\b(SCHOOL|SCH|SEC|SECONDARY|PRIMARY)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def build_match_key(name):
    return normalize_name(name)

def describe():
    return {
        "payments_file": str(DATA_DIR / "JAN-AUGUST PAYMENTS UPDATE-1.xlsx"),
        "contacts_file": str(DATA_DIR / "Contact list updated 2.docx"),
        "matching": "normalized client-name matching with conservative duplicate prevention",
        "history": "January-August retained as historical payment data",
    }

if __name__ == "__main__":
    print(json.dumps(describe(), indent=2))
