# ─────────────────────────────────────────────────────────────────────────────
# alembic/versions/0005_seed_formulary_expansion.py
# Expands the CAME formulary to ≥80 entries for comprehensive drug coverage.
# ─────────────────────────────────────────────────────────────────────────────
"""Seed CAME formulary expansion — antibiotics, antifungals, antiparasitics,
supportive care, ARVs, anti-TB, vaccines

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision      = "0005"
down_revision = "0004"
branch_labels = None
depends_on    = None

FORMULARY_EXPANSION = [
    # (generic_name, atc_code, available, dosage_forms, notes)

    # ── Additional Antibiotics ───────────────────────────────────────────────
    ("gentamicine",                 "J01GB03", True,  ["Injectable"],                "Aminoside — surveiller fonction rénale"),
    ("érythromycine",               "J01FA01", True,  ["Comprimé","Suspension"],      "Alternative macrolide"),
    ("clindamycine",                "J01FF01", True,  ["Comprimé","Injectable"],      "Anaérobies, toxoplasmose"),
    ("pénicilline V",               "J01CE02", True,  ["Comprimé","Suspension"],      "Angine streptococcique"),
    ("benzathine benzylpénicilline","J01CE08", True,  ["Injectable"],                "Syphilis, RAA prophylaxie"),
    ("ampicilline",                 "J01CA01", True,  ["Injectable","Comprimé"],      "Méningite néonatale, listériose"),
    ("tétracycline",                "J01AA07", True,  ["Comprimé","Pommade ophtalmique"], "Trachome, choléra"),
    ("nitrofurantoïne",             "J01XE01", True,  ["Comprimé"],                  "Infection urinaire basse"),
    ("spectinomycine",              "J01XX04", False, ["Injectable"],                "Gonorrhée résistante — accès limité"),
    ("céfixime",                    "J01DD08", True,  ["Comprimé","Suspension"],      "Gonorrhée, otite moyenne"),
    ("sulfadiazine argentique",     "D06BA01", True,  ["Crème"],                     "Brûlures — usage topique"),
    ("acide nalidixique",           "J01MB02", True,  ["Comprimé"],                  "Infection urinaire — quinolone 1re gén"),

    # ── Additional Antifungals ───────────────────────────────────────────────
    ("kétoconazole",                "J02AB02", True,  ["Comprimé","Crème"],           "Dermatophytose, candidose cutanée"),
    ("nystatine",                   "A07AA02", True,  ["Suspension","Comprimé vaginal"], "Candidose orale et vaginale"),
    ("griséofulvine",               "D01BA01", True,  ["Comprimé"],                  "Teigne — traitement prolongé"),
    ("itraconazole",                "J02AC02", False, ["Comprimé"],                  "Histoplasmose, sporotrichose — accès limité"),
    ("miconazole",                  "D01AC02", True,  ["Crème","Gel buccal"],         "Candidose cutanée et buccale"),
    ("clotrimazole",                "G01AF02", True,  ["Crème","Comprimé vaginal"],   "Candidose vaginale"),

    # ── Additional Antiparasitics ────────────────────────────────────────────
    ("diéthylcarbamazine",          "P02CB02", True,  ["Comprimé"],                  "Filariose lymphatique"),
    ("niclosamide",                 "P02DA01", True,  ["Comprimé"],                  "Téniase — Taenia saginata/solium"),
    ("pyrantel",                    "P02CC01", True,  ["Comprimé","Suspension"],      "Oxyurose, ascaridiose"),
    ("tinidazole",                  "P01AB02", True,  ["Comprimé"],                  "Giardiase, amœbose — dose unique"),
    ("suramine",                    "P01CX02", False, ["Injectable"],                "THA stade 1 — via OMS"),
    ("pentamidine",                 "P01CX01", False, ["Injectable"],                "THA, leishmaniose — via OMS/DNDi"),
    ("artéméther injectable",       "P01BE02", True,  ["Injectable"],                "Paludisme grave — alternative artésunate IM"),
    ("proguanil",                   "P01BB01", True,  ["Comprimé"],                  "Chimioprophylaxie paludisme"),
    ("sulfadoxine-pyriméthamine",   "P01BD51", True,  ["Comprimé"],                  "TPI grossesse — PNLP"),
    ("triclabendazole",             "P02BX04", False, ["Comprimé"],                  "Fasciolose — accès limité"),

    # ── Supportive Care ──────────────────────────────────────────────────────
    ("sels de réhydratation orale", "A07CA",   True,  ["Sachet"],                    "SRO — diarrhée aiguë OMS"),
    ("sulfate de zinc",             "A12CB01", True,  ["Comprimé","Sirop"],           "Diarrhée pédiatrique — 10-14 jours"),
    ("diazépam",                    "N05BA01", True,  ["Comprimé","Injectable","Rectal"], "Convulsions, état de mal épileptique"),
    ("phénobarbital",               "N03AA02", True,  ["Comprimé","Injectable"],      "Épilepsie — 1re ligne pays à ressources limitées"),
    ("furosémide",                  "C03CA01", True,  ["Comprimé","Injectable"],      "Œdème, insuffisance cardiaque"),
    ("hydrocortisone",              "H02AB09", True,  ["Injectable","Crème"],         "Insuffisance surrénalienne, choc"),
    ("dexaméthasone",               "H02AB02", True,  ["Injectable","Comprimé"],      "Méningite bactérienne, œdème cérébral"),
    ("épinéphrine",                 "C01CA24", True,  ["Injectable"],                "Anaphylaxie, arrêt cardiaque"),
    ("atropine",                    "A03BA01", True,  ["Injectable"],                "Bradycardie, intoxication organophosphorés"),
    ("aminophylline",               "R03DA05", True,  ["Injectable","Comprimé"],      "Asthme sévère, bronchospasme"),
    ("salbutamol",                  "R03AC02", True,  ["Inhalateur","Nébulisation","Comprimé"], "Asthme, bronchospasme aigu"),
    ("morphine",                    "N02AA01", True,  ["Injectable","Comprimé"],      "Douleur sévère — usage contrôlé"),
    ("lidocaïne",                   "N01BB02", True,  ["Injectable"],                "Anesthésie locale, arythmie ventriculaire"),
    ("charbon activé",              "A07BA01", True,  ["Poudre"],                    "Intoxication orale — dans les 2h"),
    ("gluconate de calcium",        "A12AA03", True,  ["Injectable"],                "Hypocalcémie, hyperkaliémie sévère"),
    ("glucose hypertonique",        "V06DC01", True,  ["Injectable"],                "Hypoglycémie sévère — G30/G50"),

    # ── Antiretrovirals ──────────────────────────────────────────────────────
    ("AZT+3TC+NVP",                "J05AR",   True,  ["Comprimé"],                  "ARV — ancien schéma 1re ligne"),
    ("ABC+3TC",                     "J05AR",   True,  ["Comprimé","Sirop"],           "ARV pédiatrique — backbone INRT"),
    ("lopinavir/ritonavir",         "J05AR10", True,  ["Comprimé","Sirop"],           "LPV/r — 2e ligne IP"),
    ("efavirenz",                   "J05AG03", True,  ["Comprimé"],                  "EFV — INNRT (éviter T1 grossesse)"),
    ("névirapine",                  "J05AG01", True,  ["Comprimé","Suspension"],      "NVP — PTME, pédiatrique"),
    ("atazanavir/ritonavir",        "J05AR",   True,  ["Comprimé"],                  "ATV/r — 2e ligne alternative"),

    # ── Anti-TB supplémentaires ──────────────────────────────────────────────
    ("streptomycine",               "J04AM01", True,  ["Injectable"],                "TB — phase initiale si résistance"),
    ("lévofloxacine",               "J01MA12", True,  ["Comprimé","Injectable"],      "TB-MDR, fluoroquinolone"),
    ("bédaquiline",                 "J04AK05", False, ["Comprimé"],                  "TB-XDR — via programme national"),
    ("linézolide",                  "J01XX08", False, ["Comprimé"],                  "TB-XDR — accès limité"),

    # ── Vaccins / Immunoglobulines ───────────────────────────────────────────
    ("sérum antitétanique",         "J06BB02", True,  ["Injectable"],                "SAT — prophylaxie tétanos"),
    ("immunoglobuline antirabique", "J06BB05", True,  ["Injectable"],                "Post-exposition rage — protocole Essen"),
    ("sérum antivenimeux polyvalent","J06AA03", True,  ["Injectable"],                "Envenimation ophidienne — FAV-Afrique"),
]


def upgrade() -> None:
    for row in FORMULARY_EXPANSION:
        generic, atc, avail, forms, notes = row
        # Escape single quotes in string values
        generic_escaped = generic.replace("'", "''")
        notes_escaped = notes.replace("'", "''")
        forms_literal = "ARRAY[" + ",".join(f"''{f}''" if "'" in f else f"'{f}'" for f in forms) + "]::text[]"
        op.execute(
            f"""
            INSERT INTO came_formulary (generic_name, atc_code, available, dosage_forms, notes)
            VALUES (
                '{generic_escaped}', '{atc}', {'true' if avail else 'false'},
                {forms_literal}, '{notes_escaped}'
            )
            ON CONFLICT DO NOTHING
            """
        )


def downgrade() -> None:
    names = [row[0].replace("'", "''") for row in FORMULARY_EXPANSION]
    name_list = ", ".join(f"'{n}'" for n in names)
    op.execute(f"DELETE FROM came_formulary WHERE generic_name IN ({name_list})")
