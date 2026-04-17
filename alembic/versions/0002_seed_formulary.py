# ─────────────────────────────────────────────────────────────────────────────
# alembic/versions/0002_seed_formulary.py
# Seeds a minimal CAME formulary for development / CI.
# ─────────────────────────────────────────────────────────────────────────────
"""Seed CAME formulary — essential antimalarials and antibiotics

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision    = "0002"
down_revision = "0001"
branch_labels = None
depends_on    = None

FORMULARY_SEED = [
    # (generic_name, atc_code, available, dosage_forms, notes)
    ("artésunate",                  "P01BE03", True,  ["Injectable","Comprimé"],  "Paludisme grave IV/IM"),
    ("artéméther-luméfantrine",     "P01BF01", True,  ["Comprimé"],               "Coartem® — paludisme non compliqué"),
    ("artésunate-amodiaquine",      "P01BE52", True,  ["Comprimé"],               "ASAQ — 2e intention"),
    ("dihydroartémisinine-pipéraquine", "P01BF02", True, ["Comprimé"],            "DHA-PPQ — Eurartesim®"),
    ("quinine",                     "P01BC01", True,  ["Injectable","Comprimé"],  "Paludisme grave si artésunate indispo; T1 grossesse"),
    ("chloroquine",                 "P01BA01", True,  ["Comprimé"],               "P. vivax uniquement"),
    ("primaquine",                  "P01BA03", True,  ["Comprimé"],               "Anti-rechute vivax — tester G6PD"),
    ("ceftriaxone",                 "J01DD04", True,  ["Injectable"],             "Méningite, typhoïde sévère"),
    ("amoxicilline",                "J01CA04", True,  ["Comprimé","Suspension"],  ""),
    ("amoxicilline-acide clavulanique", "J01CR02", True, ["Comprimé"],            ""),
    ("azithromycine",               "J01FA10", True,  ["Comprimé","Suspension"],  "Typhoïde, shigelloses"),
    ("doxycycline",                 "J01AA02", True,  ["Comprimé"],               "Leptospirose, brucellose"),
    ("ciprofloxacine",              "J01MA02", True,  ["Comprimé","Injectable"],  "Réserver aux infections sévères"),
    ("cotrimoxazole",               "J01EE01", True,  ["Comprimé","Suspension"],  "Prophylaxie VIH, pneumocystose"),
    ("métronidazole",               "P01AB01", True,  ["Comprimé","Injectable"],  "Amœbose, anaérobies"),
    ("rifampicine",                 "J04AB02", True,  ["Comprimé"],               "TB — jamais en monothérapie"),
    ("isoniazide",                  "J04AC01", True,  ["Comprimé"],               "TB + pyridoxine"),
    ("pyrazinamide",                "J04AK01", True,  ["Comprimé"],               "TB phase initiale"),
    ("éthambutol",                  "J04AK02", True,  ["Comprimé"],               "TB — surveiller acuité visuelle"),
    ("fluconazole",                 "J02AC01", True,  ["Comprimé","Injectable"],  "Cryptococcose, candidose"),
    ("praziquantel",                "P02BA01", True,  ["Comprimé"],               "Schistosomiase, cysticercose"),
    ("ivermectine",                 "P02CF01", True,  ["Comprimé"],               "Onchocercose, filariose"),
    ("albendazole",                 "P02CA03", True,  ["Comprimé"],               "STH, NCC"),
    ("mébendazole",                 "P02CA01", True,  ["Comprimé","Suspension"],  "STH"),
    ("chloramphénicol huileux",     "J01BA01", True,  ["Injectable"],             "Méningocoque (allergie péni) — dose unique IM"),
    ("paracétamol",                 "N02BE01", True,  ["Comprimé","Suppositoire","Sirop"], ""),
    ("ibuprofène",                  "M01AE01", True,  ["Comprimé"],               "Contre-indiqué dengue"),
    ("sulfate ferreux",             "B03AA07", True,  ["Comprimé","Sirop"],       "Anémie ferriprive"),
    ("acide folique",               "B03BB01", True,  ["Comprimé"],               ""),
    ("vitamine A",                  "A11CA01", True,  ["Capsule"],                "Rougeole — dose OMS"),
    ("TDF+3TC+DTG",                 "J05AR",   True,  ["Comprimé"],               "ARV 1re ligne — PNLS Togo 2023"),
    ("amphotéricine B déoxycholate","J02AA01", False, ["Injectable"],             "Cryptococcose — accès limité hors Lomé"),
    ("ribavirine",                  "J05AB04", False, ["Injectable"],             "Lassa — via OMS uniquement"),
    ("éflornithine",                "P01CX03", False, ["Injectable"],             "THA stade 2 — via OMS/DNDi"),
]

def upgrade() -> None:
    for row in FORMULARY_SEED:
        generic, atc, avail, forms, notes = row
        op.execute(
            f"""
            INSERT INTO came_formulary (generic_name, atc_code, available, dosage_forms, notes)
            VALUES (
                '{generic}', '{atc}', {'true' if avail else 'false'},
                ARRAY{forms!r}::text[], '{notes}'
            )
            ON CONFLICT DO NOTHING
            """
        )

def downgrade() -> None:
    op.execute("TRUNCATE came_formulary")
