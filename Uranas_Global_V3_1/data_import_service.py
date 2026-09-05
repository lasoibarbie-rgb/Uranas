
from pathlib import Path
import re, json, csv
from collections import defaultdict

def norm(v):
    s = "" if v is None else str(v)
    s = s.upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def name_key(v):
    s = norm(v)
    # Common school/business abbreviations are removed only for matching.
    s = re.sub(r"\b(SCH|SCHOOL|SEC|SECONDARY|PRIMARY)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()

def read_xlsx(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    rows = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            vals = [x for x in row]
            if any(x not in (None, "") for x in vals):
                rows.append(vals)
    return {"sheets": wb.sheetnames, "rows": rows}

def read_docx(path):
    from docx import Document
    doc = Document(path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]

def prepare_import(payments_path, contacts_path):
    payments = read_xlsx(payments_path)
    contacts = read_docx(contacts_path)

    # Preserve source data for auditability. Actual row-to-row interpretation
    # is performed by the application's import screen/preview.
    return {
        "payments": payments,
        "contacts": contacts,
        "match_rule": "normalized client-name",
        "uncertain_matches_require_review": True,
    }
