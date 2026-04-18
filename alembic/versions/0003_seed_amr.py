# ─────────────────────────────────────────────────────────────────────────────
# alembic/versions/0003_seed_amr.py
# Seeds West Africa AMR data from WHONET/GLASS.
# ─────────────────────────────────────────────────────────────────────────────
"""Seed West Africa AMR data

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision      = "0003"
down_revision = "0002"

# (drug, pathogen, region, resistance_pct, source, year, confidence)
AMR_SEED = [
    ("amoxicilline",   "Salmonella typhi",           "West Africa", 0.62, "WHONET 2022", 2022, "high"),
    ("cotrimoxazole",  "Salmonella typhi",           "West Africa", 0.51, "WHONET 2022", 2022, "high"),
    ("ciprofloxacine", "Salmonella typhi",           "West Africa", 0.08, "WHONET 2022", 2022, "medium"),
    ("ceftriaxone",    "Salmonella typhi",           "West Africa", 0.01, "WHONET 2022", 2022, "high"),
    ("ampicilline",    "Shigella",                   "West Africa", 0.73, "GLASS 2023",  2023, "high"),
    ("cotrimoxazole",  "Shigella",                   "West Africa", 0.69, "GLASS 2023",  2023, "high"),
    ("azithromycine",  "Shigella",                   "West Africa", 0.06, "GLASS 2023",  2023, "medium"),
    ("ciprofloxacine", "Escherichia coli",           "West Africa", 0.34, "GLASS 2023",  2023, "high"),
    ("amoxicilline",   "Escherichia coli",           "West Africa", 0.58, "GLASS 2023",  2023, "high"),
    ("ceftriaxone",    "Escherichia coli",           "West Africa", 0.18, "GLASS 2023",  2023, "medium"),
    ("pénicilline G",  "Streptococcus pneumoniae",   "West Africa", 0.22, "ASTER 2022",  2022, "medium"),
    ("ceftriaxone",    "Streptococcus pneumoniae",   "West Africa", 0.04, "ASTER 2022",  2022, "medium"),
    ("chloroquine",    "Plasmodium falciparum",      "Togo",        0.35, "PNLP 2023",   2023, "high"),
    ("artéméther-luméfantrine", "Plasmodium falciparum", "Togo",   0.03, "PNLP 2023",   2023, "high"),
    ("métronidazole",  "Trichomonas vaginalis",      "West Africa", 0.05, "Literature",  2021, "low"),
]

def upgrade() -> None:
    for drug, pathogen, region, res, source, year, conf in AMR_SEED:
        op.execute(f"""
            INSERT INTO amr_data (drug, pathogen, region, resistance_pct, data_source, year, confidence)
            VALUES ('{drug}', '{pathogen}', '{region}', {res}, '{source}', {year}, '{conf}')
            ON CONFLICT DO NOTHING
        """)

def downgrade() -> None:
    op.execute("TRUNCATE amr_data")