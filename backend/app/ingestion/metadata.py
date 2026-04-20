# ─────────────────────────────────────────────────────────────────────────────
# tropicare_ingestion/metadata.py
# Extracts disease tags (ICD-11), drug tags (ATC), and content type.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import re

# Lightweight keyword → ICD-11 map (augment from PNLP terminology)
_DISEASE_KEYWORDS: dict[str, str] = {
    "paludisme": "1F40", "malaria": "1F40", "plasmodium": "1F40",
    "falciparum": "1F40", "vivax": "1F41",
    "méningite": "1C1A", "meningocoque": "1C1A",
    "typhoïde": "1A07", "salmonella": "1A07",
    "choléra": "1A00", "vibrio": "1A00",
    "tuberculose": "1B10", "tb": "1B10", "mdr": "1B10",
    "dengue": "1D2Z",
    "lassa": "1D6Y",
    "schistosom": "1F60", "bilharziose": "1F60",
    "filariose": "1F68", "bancroftii": "1F68",
    "onchocercose": "1F5Y", "onchocerca": "1F5Y",
    "trypanosomiase": "1C62", "sommeil": "1C62",
    "cryptococcose": "5A11", "cryptococcus": "5A11",
    "buruli": "1B2Z", "ulcère mycobact": "1B2Z",
    "leptospirose": "1A96", "leptospira": "1A96",
    "leishmaniose": "1F53", "leishmania": "1F53",
    "pian": "1C1Z",
    "cysticercose": "1F51", "taenia": "1F51",
}

_DRUG_KEYWORDS: dict[str, str] = {
    # Antimalarials
    "artésunate": "P01BE03", "artesunate": "P01BE03",
    "artéméther": "P01BE02", "artemether": "P01BE02",
    "luméfantrine": "P01BF01", "lumefantrine": "P01BF01",
    "chloroquine": "P01BA01",
    "quinine": "P01BC01",
    "amodiaquine": "P01BA06",
    "méfloquine": "P01BC02", "mefloquine": "P01BC02",
    "primaquine": "P01BA03",
    "pyriméthamine": "P01BD01", "pyrimethamine": "P01BD01",
    "sulfadoxine": "P01BD51",
    "dihydroartémisinine": "P01BE05", "dihydroartemisinin": "P01BE05",
    "pipéraquine": "P01BF05", "piperaquine": "P01BF05",
    # Antibiotics
    "ceftriaxone": "J01DD04",
    "amoxicilline": "J01CA04", "amoxicillin": "J01CA04",
    "azithromycine": "J01FA10", "azithromycin": "J01FA10",
    "doxycycline": "J01AA02",
    "ciprofloxacine": "J01MA02", "ciprofloxacin": "J01MA02",
    "gentamicine": "J01GB03", "gentamicin": "J01GB03",
    "métronidazole": "P01AB01", "metronidazole": "P01AB01",
    "cotrimoxazole": "J01EE01", "trimethoprim": "J01EE01",
    "ampicilline": "J01CA01", "ampicillin": "J01CA01",
    "clindamycine": "J01FF01", "clindamycin": "J01FF01",
    "érythromycine": "J01FA01", "erythromycin": "J01FA01",
    "pénicilline": "J01CE01", "penicillin": "J01CE01",
    "chloramphénicol": "J01BA01", "chloramphenicol": "J01BA01",
    "vancomycine": "J01XA01", "vancomycin": "J01XA01",
    "céfixime": "J01DD08", "cefixime": "J01DD08",
    # Anti-TB
    "rifampicine": "J04AB02", "rifampicin": "J04AB02", "rifampin": "J04AB02",
    "isoniazide": "J04AC01", "isoniazid": "J04AC01",
    "éthambutol": "J04AK02", "ethambutol": "J04AK02",
    "pyrazinamide": "J04AK01",
    # Antifungals
    "fluconazole": "J02AC01",
    "amphotéricine": "J02AA01", "amphotericin": "J02AA01",
    # Antiparasitics
    "praziquantel": "P02BA01",
    "ivermectine": "P02CF01", "ivermectin": "P02CF01",
    "albendazole": "P02CA03",
    "mébendazole": "P02CA01", "mebendazole": "P02CA01",
    # Antivirals
    "acyclovir": "J05AB01", "aciclovir": "J05AB01",
    "oseltamivir": "J05AH02",
    # ORS / supportive
    "sro": "A07CA", "ors": "A07CA",
    "zinc": "A12CB",
    "paracétamol": "N02BE01", "paracetamol": "N02BE01", "acetaminophen": "N02BE01",
}

_CONTENT_TYPE_HINTS: dict[str, str] = {
    "formulaire": "formulary", "came": "formulary", "médicament essentiel": "formulary",
    "resistance": "amr_data", "antibiogramme": "amr_data", "susceptibilité": "amr_data",
    "épidémiologie": "epidemiology", "surveillance": "epidemiology", "bulletin": "epidemiology",
    "protocole": "guideline", "directive": "guideline", "guideline": "guideline",
    "pnlp": "guideline", "who": "guideline", "oms": "guideline",
}


def extract_metadata(text: str, section: str = "", doc_type: str = "pdf") -> dict:
    combined = (text + " " + section).lower()

    disease_tags = list({
        icd for kw, icd in _DISEASE_KEYWORDS.items() if kw in combined
    })
    drug_tags = list({
        atc for kw, atc in _DRUG_KEYWORDS.items() if kw in combined
    })
    content_type = "guideline"
    for hint, ctype in _CONTENT_TYPE_HINTS.items():
        if hint in combined:
            content_type = ctype
            break

    return {
        "disease_tags":  disease_tags,
        "drug_tags":     drug_tags,
        "content_type":  content_type,
        "language":      "fr" if "le " in combined or "la " in combined else "en",
    }

