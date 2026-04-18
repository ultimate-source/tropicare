# ═════════════════════════════════════════════════════════════════════════════
# scripts/seed_kb.py — upload priority-1 seed documents
# ═════════════════════════════════════════════════════════════════════════════

#!/usr/bin/env python3
"""
Upload seed documents to the KB via the admin API.
Place PDF/DOCX files in data/seed_documents/ before running.

Expected structure:
  data/seed_documents/
    pnlp_togo_2023.pdf          source_type=guideline
    who_malaria_2023.pdf        source_type=guideline
    came_formulary_2024.json    source_type=formulary
    whonet_amr_2022.csv         (import directly to DB — not via KB)
    msf_guidelines_2022.pdf     source_type=guideline
"""

import argparse
import os
import httpx
from pathlib import Path

SEED_DOCS = [
    ("pnlp_togo_2023.pdf",       "guideline",     "Directives nationales paludisme PNLP Togo", "2023"),
    ("who_malaria_2023.pdf",      "guideline",     "WHO Guidelines for Malaria Treatment",       "2023"),
    ("came_formulary_2024.json",  "formulary",     "Formulaire CAME Togo",                       "2024"),
    ("msf_guidelines_2022.pdf",   "guideline",     "MSF Clinical Guidelines — Infectious Diseases", "2022"),
    ("who_tb_2022.pdf",           "guideline",     "WHO TB Treatment Guidelines",                 "2022"),
    ("who_ntd_2021.pdf",          "guideline",     "WHO NTD Control — West Africa",               "2021"),
]
