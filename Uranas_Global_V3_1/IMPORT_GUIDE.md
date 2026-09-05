# Uranas Global V3 – Data Import

The supplied January–August payment workbook and separate contact list are included
under `data_import/` for the initial migration.

The migration keeps source names intact, normalizes names only for matching, and
does not automatically merge uncertain matches. This prevents duplicate or incorrect
client/payment histories.

Dependencies added:
- openpyxl
- python-docx
