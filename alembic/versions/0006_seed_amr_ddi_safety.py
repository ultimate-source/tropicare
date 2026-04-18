# ─────────────────────────────────────────────────────────────────────────────
# alembic/versions/0006_seed_amr_ddi_safety.py
# Seeds AMR expansion, DDI interactions, and drug safety data.
# ─────────────────────────────────────────────────────────────────────────────
"""Seed AMR expansion, DDI interactions, and drug safety data

Revision ID: 0006
Revises: 0005
"""
from alembic import op

revision      = "0006"
down_revision = "0005"
branch_labels = None
depends_on    = None

# ═══════════════════════════════════════════════════════════════════════════════
# AMR DATA — 40 new entries (total ≥55 with 15 from 0003)
# (drug, pathogen, region, resistance_pct, data_source, year, confidence)
# ═══════════════════════════════════════════════════════════════════════════════
AMR_EXPANSION = [
    # Staphylococcus aureus
    ("oxacilline",          "Staphylococcus aureus",       "Togo",        0.28, "WHONET 2023",  2023, "high"),
    ("oxacilline",          "Staphylococcus aureus",       "West Africa", 0.31, "GLASS 2023",   2023, "high"),
    ("gentamicine",         "Staphylococcus aureus",       "Togo",        0.18, "WHONET 2023",  2023, "medium"),
    ("cotrimoxazole",       "Staphylococcus aureus",       "West Africa", 0.42, "GLASS 2023",   2023, "high"),
    ("vancomycine",         "Staphylococcus aureus",       "West Africa", 0.01, "GLASS 2023",   2023, "high"),
    ("ciprofloxacine",      "Staphylococcus aureus",       "Togo",        0.22, "WHONET 2023",  2023, "medium"),
    # Klebsiella pneumoniae
    ("ampicilline",         "Klebsiella pneumoniae",       "Togo",        0.89, "WHONET 2023",  2023, "high"),
    ("ceftriaxone",         "Klebsiella pneumoniae",       "Togo",        0.38, "WHONET 2023",  2023, "high"),
    ("ceftriaxone",         "Klebsiella pneumoniae",       "West Africa", 0.42, "GLASS 2023",   2023, "high"),
    ("ciprofloxacine",      "Klebsiella pneumoniae",       "West Africa", 0.29, "GLASS 2023",   2023, "high"),
    ("imipénème",           "Klebsiella pneumoniae",       "West Africa", 0.06, "GLASS 2023",   2023, "medium"),
    ("gentamicine",         "Klebsiella pneumoniae",       "Togo",        0.35, "WHONET 2023",  2023, "medium"),
    # Neisseria meningitidis
    ("pénicilline G",       "Neisseria meningitidis",      "Togo",        0.12, "WHO 2023",     2023, "medium"),
    ("ceftriaxone",         "Neisseria meningitidis",      "Togo",        0.01, "WHO 2023",     2023, "high"),
    ("chloramphénicol",     "Neisseria meningitidis",      "West Africa", 0.08, "WHO 2023",     2023, "medium"),
    # Neisseria gonorrhoeae
    ("ciprofloxacine",      "Neisseria gonorrhoeae",       "Togo",        0.67, "WHONET 2022",  2022, "high"),
    ("ceftriaxone",         "Neisseria gonorrhoeae",       "West Africa", 0.03, "GLASS 2023",   2023, "high"),
    ("azithromycine",       "Neisseria gonorrhoeae",       "West Africa", 0.12, "GLASS 2023",   2023, "medium"),
    # Vibrio cholerae
    ("tétracycline",        "Vibrio cholerae",             "Togo",        0.15, "WHO 2022",     2022, "medium"),
    ("azithromycine",       "Vibrio cholerae",             "West Africa", 0.04, "WHO 2022",     2022, "medium"),
    ("ciprofloxacine",      "Vibrio cholerae",             "West Africa", 0.09, "WHO 2022",     2022, "medium"),
    # Mycobacterium tuberculosis
    ("isoniazide",          "Mycobacterium tuberculosis",  "Togo",        0.11, "WHO 2023",     2023, "high"),
    ("rifampicine",         "Mycobacterium tuberculosis",  "Togo",        0.04, "WHO 2023",     2023, "high"),
    ("isoniazide",          "Mycobacterium tuberculosis",  "West Africa", 0.13, "WHO 2023",     2023, "high"),
    ("rifampicine",         "Mycobacterium tuberculosis",  "West Africa", 0.05, "WHO 2023",     2023, "high"),
    # Haemophilus influenzae
    ("ampicilline",         "Haemophilus influenzae",      "Togo",        0.45, "WHONET 2022",  2022, "medium"),
    ("amoxicilline",        "Haemophilus influenzae",      "West Africa", 0.38, "GLASS 2023",   2023, "high"),
    ("ceftriaxone",         "Haemophilus influenzae",      "West Africa", 0.02, "GLASS 2023",   2023, "high"),
    # Pseudomonas aeruginosa
    ("ciprofloxacine",      "Pseudomonas aeruginosa",      "Togo",        0.25, "WHONET 2023",  2023, "medium"),
    ("ceftazidime",         "Pseudomonas aeruginosa",      "West Africa", 0.22, "GLASS 2023",   2023, "medium"),
    ("imipénème",           "Pseudomonas aeruginosa",      "West Africa", 0.15, "GLASS 2023",   2023, "medium"),
    ("gentamicine",         "Pseudomonas aeruginosa",      "Togo",        0.30, "WHONET 2023",  2023, "medium"),
    # Enterococcus faecalis
    ("ampicilline",         "Enterococcus faecalis",       "West Africa", 0.08, "GLASS 2023",   2023, "medium"),
    ("vancomycine",         "Enterococcus faecalis",       "West Africa", 0.03, "GLASS 2023",   2023, "low"),
    # Acinetobacter baumannii
    ("imipénème",           "Acinetobacter baumannii",     "Togo",        0.48, "WHONET 2023",  2023, "medium"),
    ("ciprofloxacine",      "Acinetobacter baumannii",     "West Africa", 0.62, "GLASS 2023",   2023, "medium"),
    ("gentamicine",         "Acinetobacter baumannii",     "West Africa", 0.55, "GLASS 2023",   2023, "medium"),
    # Plasmodium falciparum (antimalarials)
    ("sulfadoxine-pyriméthamine", "Plasmodium falciparum", "Togo",        0.18, "PNLP 2023",   2023, "high"),
    ("amodiaquine",         "Plasmodium falciparum",       "Togo",        0.12, "PNLP 2023",   2023, "high"),
    ("artéméther-luméfantrine", "Plasmodium falciparum",   "West Africa", 0.02, "WHO 2023",     2023, "high"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# DDI INTERACTIONS — 32 entries
# (drug_a, drug_b, severity, mechanism, clinical_effect, management)
# ═══════════════════════════════════════════════════════════════════════════════
DDI_DATA = [
    # Antimalarial interactions
    ("artéméther-luméfantrine", "lopinavir/ritonavir", "major",
     "Inhibition CYP3A4 par lopinavir augmente taux de luméfantrine",
     "Risque accru de prolongation QTc et arythmie cardiaque",
     "Surveiller ECG; envisager quinine + clindamycine comme alternative"),
    ("artéméther-luméfantrine", "efavirenz", "major",
     "Induction CYP3A4 par efavirenz réduit taux de luméfantrine",
     "Diminution efficacité antipaludique, risque d''échec thérapeutique",
     "Augmenter surveillance parasitémie; envisager artésunate-amodiaquine"),
    ("artéméther-luméfantrine", "kétoconazole", "major",
     "Inhibition CYP3A4 par kétoconazole augmente taux d''artéméther",
     "Risque de toxicité artéméther et prolongation QTc",
     "Éviter association; utiliser fluconazole si antifongique nécessaire"),
    ("artéméther-luméfantrine", "rifampicine", "contraindicated",
     "Induction puissante CYP3A4 par rifampicine",
     "Réduction drastique des taux plasmatiques d''artéméther et luméfantrine",
     "Contre-indiqué; utiliser quinine pendant traitement anti-TB"),
    ("quinine", "lopinavir/ritonavir", "major",
     "Inhibition CYP3A4 augmente taux de quinine",
     "Risque de cinchonisme sévère, hypoglycémie, arythmie",
     "Réduire dose quinine de 30-50%; surveiller glycémie et ECG"),
    ("quinine", "rifampicine", "major",
     "Induction CYP3A4 par rifampicine réduit taux de quinine",
     "Diminution efficacité antipaludique",
     "Augmenter dose quinine; surveiller parasitémie étroitement"),
    ("quinine", "méfloquine", "contraindicated",
     "Effets cardiotoxiques additifs",
     "Risque élevé de convulsions et arythmie cardiaque",
     "Contre-indiqué; attendre 12h après arrêt méfloquine avant quinine"),
    ("chloroquine", "métronidazole", "moderate",
     "Potentialisation effets neurotoxiques",
     "Risque accru de neuropathie périphérique et convulsions",
     "Surveiller signes neurologiques; espacer prises si possible"),
    ("chloroquine", "ciprofloxacine", "moderate",
     "Effets additifs sur prolongation QTc",
     "Risque accru d''arythmie cardiaque",
     "Surveiller ECG; éviter chez patients avec QTc prolongé"),
    # Antibiotic interactions
    ("ciprofloxacine", "métronidazole", "moderate",
     "Effets additifs sur système nerveux central",
     "Risque accru de convulsions et neuropathie",
     "Surveiller signes neurologiques; ajuster si convulsions"),
    ("ciprofloxacine", "doxycycline", "minor",
     "Chélation possible avec cations divalents co-administrés",
     "Légère diminution absorption des deux antibiotiques",
     "Espacer prises de 2 heures; impact clinique minimal"),
    ("ciprofloxacine", "sulfate de zinc", "moderate",
     "Chélation de ciprofloxacine par zinc",
     "Diminution significative absorption ciprofloxacine",
     "Administrer ciprofloxacine 2h avant ou 6h après zinc"),
    ("métronidazole", "lopinavir/ritonavir", "moderate",
     "Interaction avec excipient alcoolique du lopinavir/ritonavir sirop",
     "Effet antabuse: nausées, vomissements, flush, céphalées",
     "Utiliser forme comprimé de lopinavir/ritonavir; éviter sirop"),
    ("rifampicine", "lopinavir/ritonavir", "contraindicated",
     "Induction puissante CYP3A4 par rifampicine",
     "Réduction de 75% des taux de lopinavir — échec virologique",
     "Contre-indiqué; utiliser rifabutine avec ajustement posologique"),
    ("rifampicine", "efavirenz", "major",
     "Induction CYP2B6 par rifampicine réduit taux d''efavirenz",
     "Risque d''échec virologique",
     "Augmenter efavirenz à 800mg/j si poids >60kg; surveiller charge virale"),
    ("rifampicine", "névirapine", "contraindicated",
     "Induction CYP3A4 et CYP2B6 par rifampicine",
     "Réduction de 20-58% des taux de névirapine — échec virologique",
     "Contre-indiqué; utiliser efavirenz avec rifampicine"),
    ("rifampicine", "fluconazole", "major",
     "Induction enzymatique par rifampicine réduit taux de fluconazole",
     "Diminution efficacité antifongique",
     "Augmenter dose fluconazole; surveiller réponse clinique"),
    ("rifampicine", "doxycycline", "major",
     "Induction CYP3A4 réduit demi-vie de doxycycline",
     "Diminution efficacité antibiotique",
     "Augmenter fréquence doxycycline à 2x/j ou utiliser alternative"),
    # Antifungal interactions
    ("fluconazole", "artéméther-luméfantrine", "major",
     "Inhibition CYP3A4 par fluconazole",
     "Augmentation taux luméfantrine, risque prolongation QTc",
     "Surveiller ECG; réduire durée co-administration"),
    ("kétoconazole", "lopinavir/ritonavir", "major",
     "Double inhibition CYP3A4",
     "Augmentation marquée taux des deux médicaments",
     "Limiter kétoconazole à 200mg/j; surveiller hépatotoxicité"),
    ("kétoconazole", "efavirenz", "major",
     "Efavirenz induit CYP3A4, réduit taux kétoconazole",
     "Diminution efficacité antifongique",
     "Éviter association; utiliser fluconazole comme alternative"),
    # ARV interactions
    ("lopinavir/ritonavir", "amodiaquine", "contraindicated",
     "Inhibition CYP2C8 par ritonavir augmente taux d''amodiaquine",
     "Hépatotoxicité sévère et neutropénie",
     "Contre-indiqué; utiliser artéméther-luméfantrine avec surveillance"),
    ("efavirenz", "amodiaquine", "contraindicated",
     "Induction CYP2C8 et hépatotoxicité additive",
     "Hépatotoxicité sévère",
     "Contre-indiqué; utiliser artéméther-luméfantrine"),
    ("névirapine", "fluconazole", "major",
     "Fluconazole augmente taux de névirapine via inhibition CYP3A4",
     "Risque accru d''hépatotoxicité",
     "Surveiller transaminases toutes les 2 semaines"),
    # Anti-TB interactions
    ("isoniazide", "kétoconazole", "moderate",
     "Isoniazide peut réduire absorption de kétoconazole",
     "Diminution efficacité antifongique",
     "Administrer kétoconazole 2h après isoniazide"),
    ("pyrazinamide", "allopurinol", "moderate",
     "Pyrazinamide augmente acide urique; allopurinol le diminue",
     "Antagonisme pharmacologique sur uricémie",
     "Surveiller uricémie; ajuster allopurinol si nécessaire"),
    # Antiparasitic interactions
    ("ivermectine", "lopinavir/ritonavir", "moderate",
     "Inhibition CYP3A4 augmente taux d''ivermectine",
     "Risque accru de neurotoxicité",
     "Surveiller signes neurologiques; réduire dose si nécessaire"),
    ("praziquantel", "rifampicine", "major",
     "Induction CYP3A4 réduit taux de praziquantel de 85%",
     "Échec thérapeutique contre schistosomiase",
     "Reporter traitement praziquantel à 4 semaines après arrêt rifampicine"),
    ("albendazole", "dexaméthasone", "moderate",
     "Dexaméthasone augmente taux de métabolite actif albendazole sulfoxide",
     "Augmentation efficacité mais aussi toxicité potentielle",
     "Surveiller NFS; association parfois intentionnelle (neurocysticercose)"),
    ("méfloquine", "divalproex", "major",
     "Méfloquine diminue taux sériques d''acide valproïque",
     "Risque de convulsions par perte contrôle épileptique",
     "Éviter méfloquine chez épileptiques; utiliser doxycycline en prophylaxie"),
    ("primaquine", "dapsone", "contraindicated",
     "Stress oxydatif additif sur érythrocytes",
     "Risque élevé d''hémolyse sévère, surtout si déficit G6PD",
     "Contre-indiqué; vérifier G6PD avant toute utilisation"),
    ("doxycycline", "antiacides", "moderate",
     "Chélation par cations divalents (Al, Mg, Ca)",
     "Diminution significative absorption doxycycline",
     "Administrer doxycycline 2h avant ou après antiacides"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# DRUG SAFETY — 45 entries
# (drug, pregnancy_category, lactation_safe, t1_notes, t2_notes, t3_notes, source)
# ═══════════════════════════════════════════════════════════════════════════════
DRUG_SAFETY_DATA = [
    # ── Antimalarials ─────────────────────────────────────────────────────────
    ("artéméther-luméfantrine", "C", True,
     "Données limitées au T1; éviter si alternative disponible",
     "Traitement de choix paludisme non compliqué T2-T3",
     "Traitement de choix paludisme non compliqué T2-T3",
     "OMS 2023"),
    ("quinine", "C", True,
     "Utilisable au T1 pour paludisme sévère; risque hypoglycémie",
     "Alternative si ACT indisponible; surveiller glycémie",
     "Risque accru contractions utérines; surveiller étroitement",
     "OMS 2023"),
    ("chloroquine", "B", True,
     "Sûr au T1; utilisé en prophylaxie zones sensibles",
     "Sûr; pas de tératogénicité démontrée",
     "Sûr; compatible avec allaitement",
     "OMS 2023"),
    ("méfloquine", "C", True,
     "Éviter au T1 sauf si pas d''alternative; risque neuropsychiatrique",
     "Utilisable en prophylaxie si bénéfice > risque",
     "Utilisable; surveiller effets neuropsychiatriques",
     "OMS 2023"),
    ("sulfadoxine-pyriméthamine", "C", False,
     "Contre-indiqué au T1 (antifolate, risque tératogène)",
     "TPI recommandé à partir du T2 (≥13 SA)",
     "TPI recommandé; dernière dose ≥1 mois avant terme",
     "PNLP Togo 2023"),
    ("amodiaquine", "C", False,
     "Données insuffisantes au T1; éviter",
     "Utilisable en combinaison ASAQ si ACT de choix indisponible",
     "Utilisable; surveiller hépatotoxicité",
     "OMS 2023"),
    ("primaquine", "X", False,
     "Contre-indiqué: risque hémolyse fœtale (statut G6PD inconnu)",
     "Contre-indiqué pendant toute la grossesse",
     "Contre-indiqué pendant toute la grossesse",
     "OMS 2023"),
    ("artésunate", "C", True,
     "Données limitées T1; utiliser si paludisme sévère (bénéfice vital)",
     "Traitement de choix paludisme sévère",
     "Traitement de choix paludisme sévère",
     "OMS 2023"),
    # ── Antibiotiques ─────────────────────────────────────────────────────────
    ("amoxicilline", "B", True,
     "Sûr au T1; pas de tératogénicité",
     "Sûr; antibiotique de choix pendant grossesse",
     "Sûr; compatible avec allaitement",
     "WHO AWaRe 2023"),
    ("ampicilline", "B", True,
     "Sûr au T1; utilisé couramment",
     "Sûr; alternative parentérale à amoxicilline",
     "Sûr; compatible avec allaitement",
     "WHO AWaRe 2023"),
    ("ceftriaxone", "B", True,
     "Sûr au T1; pas de tératogénicité connue",
     "Sûr; céphalosporine de choix en grossesse",
     "Éviter proche du terme (risque ictère néonatal théorique)",
     "WHO AWaRe 2023"),
    ("ciprofloxacine", "C", False,
     "Éviter au T1; risque théorique arthropathie fœtale",
     "Éviter sauf si pas d''alternative; risque cartilage",
     "Éviter; utiliser ceftriaxone ou azithromycine en alternative",
     "WHO AWaRe 2023"),
    ("doxycycline", "D", False,
     "Contre-indiqué: risque coloration dentaire et dysplasie émail",
     "Contre-indiqué à partir de la 16e semaine",
     "Contre-indiqué; utiliser azithromycine en alternative",
     "WHO AWaRe 2023"),
    ("métronidazole", "B", True,
     "Éviter au T1 si possible (données contradictoires mutagénicité)",
     "Sûr au T2; traitement de choix amibiase et giardiase",
     "Sûr; compatible avec allaitement (dose unique préférable)",
     "WHO AWaRe 2023"),
    ("azithromycine", "B", True,
     "Sûr au T1; pas de tératogénicité démontrée",
     "Sûr; alternative aux fluoroquinolones en grossesse",
     "Sûr; compatible avec allaitement",
     "WHO AWaRe 2023"),
    ("cotrimoxazole", "C", False,
     "Éviter au T1 (antifolate; supplémenter en acide folique 5mg/j)",
     "Utilisable T2 pour prophylaxie IO chez VIH+; supplémenter folates",
     "Éviter proche du terme (risque ictère néonatal, kernictère)",
     "OMS VIH 2023"),
    ("gentamicine", "D", True,
     "Éviter au T1; risque ototoxicité fœtale",
     "Utiliser uniquement si infection sévère sans alternative",
     "Risque néphro/ototoxicité néonatale; surveiller fonction rénale",
     "WHO AWaRe 2023"),
    ("chloramphénicol", "C", False,
     "Éviter au T1; risque aplasie médullaire",
     "Éviter si alternative disponible",
     "Contre-indiqué proche du terme (syndrome du bébé gris)",
     "WHO AWaRe 2023"),
    ("érythromycine", "B", True,
     "Sûr au T1 (forme base); éviter estolate (hépatotoxicité)",
     "Sûr; alternative aux macrolides en grossesse",
     "Sûr; compatible avec allaitement",
     "WHO AWaRe 2023"),
    ("clindamycine", "B", True,
     "Sûr au T1; pas de tératogénicité",
     "Sûr; alternative en cas d''allergie pénicilline",
     "Sûr; compatible avec allaitement",
     "WHO AWaRe 2023"),
    ("nitrofurantoïne", "B", False,
     "Sûr au T1 pour infections urinaires",
     "Sûr au T2; traitement de choix cystite en grossesse",
     "Éviter après 36 SA (risque anémie hémolytique néonatale si G6PD)",
     "WHO AWaRe 2023"),
    ("pénicilline G", "B", True,
     "Sûr au T1; antibiotique le plus sûr en grossesse",
     "Sûr; traitement de choix syphilis en grossesse",
     "Sûr; compatible avec allaitement",
     "WHO AWaRe 2023"),
    # ── Anti-tuberculeux ──────────────────────────────────────────────────────
    ("isoniazide", "C", True,
     "Utilisable au T1 si TB active; supplémenter pyridoxine 25mg/j",
     "Sûr avec pyridoxine; surveiller hépatotoxicité",
     "Sûr; compatible avec allaitement avec pyridoxine",
     "OMS TB 2023"),
    ("rifampicine", "C", True,
     "Utilisable au T1 si TB active; risque hémorragie néonatale (vit K)",
     "Sûr; administrer vitamine K au nouveau-né",
     "Administrer vitamine K1 au nouveau-né; surveiller ictère",
     "OMS TB 2023"),
    ("pyrazinamide", "C", True,
     "Données limitées T1; inclus dans schéma OMS si TB active",
     "Utilisable dans schéma standard TB",
     "Utilisable; surveiller uricémie et hépatotoxicité",
     "OMS TB 2023"),
    ("éthambutol", "B", True,
     "Sûr au T1; pas de tératogénicité démontrée",
     "Sûr; inclus dans schéma standard TB",
     "Sûr; compatible avec allaitement",
     "OMS TB 2023"),
    ("streptomycine", "D", False,
     "Contre-indiqué: risque ototoxicité fœtale irréversible",
     "Contre-indiqué pendant toute la grossesse",
     "Contre-indiqué pendant toute la grossesse",
     "OMS TB 2023"),
    # ── Antifongiques ─────────────────────────────────────────────────────────
    ("fluconazole", "D", True,
     "Contre-indiqué au T1 à dose >150mg (tératogène prouvé)",
     "Dose unique 150mg acceptable pour candidose; éviter doses élevées",
     "Éviter doses élevées; dose unique 150mg acceptable",
     "WHO AWaRe 2023"),
    ("nystatine", "A", True,
     "Sûr au T1; absorption systémique négligeable",
     "Sûr; traitement topique de choix candidose",
     "Sûr; compatible avec allaitement",
     "WHO AWaRe 2023"),
    ("kétoconazole", "C", False,
     "Éviter au T1; risque anti-androgénique sur fœtus masculin",
     "Éviter si alternative disponible; utiliser fluconazole dose unique",
     "Éviter; utiliser nystatine topique en alternative",
     "WHO AWaRe 2023"),
    ("amphotéricine B", "B", True,
     "Utilisable au T1 si infection fongique sévère (bénéfice vital)",
     "Traitement de choix mycoses systémiques sévères en grossesse",
     "Sûr; surveiller fonction rénale et kaliémie",
     "WHO AWaRe 2023"),
    ("griséofulvine", "X", False,
     "Contre-indiqué: tératogène prouvé chez l''animal",
     "Contre-indiqué pendant toute la grossesse",
     "Contre-indiqué; attendre 1 mois après arrêt avant conception",
     "WHO AWaRe 2023"),
    # ── Antiparasitaires ──────────────────────────────────────────────────────
    ("albendazole", "C", True,
     "Contre-indiqué au T1 (tératogène chez l''animal)",
     "Utilisable au T2 pour helminthiases; dose unique préférable",
     "Utilisable; traitement déparasitage OMS recommandé T2-T3",
     "OMS 2023"),
    ("mébendazole", "C", True,
     "Éviter au T1 (tératogène chez l''animal à fortes doses)",
     "Utilisable au T2; déparasitage OMS recommandé",
     "Utilisable; compatible avec allaitement",
     "OMS 2023"),
    ("ivermectine", "C", False,
     "Éviter au T1; données insuffisantes chez l''humain",
     "Éviter si possible; utiliser si onchocercose sévère",
     "Éviter; données insuffisantes sur passage dans lait",
     "OMS 2023"),
    ("praziquantel", "B", True,
     "Données rassurantes T1; OMS recommande traitement si schistosomiase",
     "Sûr; traitement recommandé schistosomiase en grossesse",
     "Sûr; compatible avec allaitement",
     "OMS 2023"),
    ("pentamidine", "C", False,
     "Éviter au T1 sauf trypanosomiase (bénéfice vital)",
     "Utilisable si trypanosomiase; surveiller glycémie et fonction rénale",
     "Surveiller hypoglycémie néonatale si utilisé proche du terme",
     "OMS NTD 2023"),
    ("suramine", "C", False,
     "Données très limitées; utiliser si trypanosomiase T1 (bénéfice vital)",
     "Utilisable si trypanosomiase stade 1",
     "Données insuffisantes; surveiller fonction rénale",
     "OMS NTD 2023"),
    ("diéthylcarbamazine", "C", False,
     "Éviter au T1; risque réaction Mazzotti sévère",
     "Éviter pendant grossesse si possible",
     "Éviter; reporter traitement filariose après accouchement",
     "OMS NTD 2023"),
    # ── Soins de support ──────────────────────────────────────────────────────
    ("paracétamol", "A", True,
     "Sûr au T1; antalgique/antipyrétique de choix en grossesse",
     "Sûr; pas de restriction",
     "Sûr; compatible avec allaitement",
     "OMS 2023"),
    ("ibuprofène", "C", False,
     "Éviter au T1 si possible (risque fausse couche discuté)",
     "Utilisable ponctuellement au T2 si paracétamol insuffisant",
     "Contre-indiqué après 24 SA (fermeture prématurée canal artériel)",
     "OMS 2023"),
    ("sulfate de zinc", "A", True,
     "Sûr au T1; supplément recommandé si carence",
     "Sûr; recommandé en complément traitement diarrhée",
     "Sûr; compatible avec allaitement",
     "OMS 2023"),
    ("SRO", "A", True,
     "Sûr au T1; réhydratation orale sans restriction",
     "Sûr; pas de restriction",
     "Sûr; compatible avec allaitement",
     "OMS 2023"),
    ("fer + acide folique", "A", True,
     "Recommandé dès le T1; prévention anémie et anomalies tube neural",
     "Recommandé; supplément systématique grossesse",
     "Recommandé; compatible avec allaitement",
     "OMS 2023"),
    ("vitamine A", "X", True,
     "Contre-indiqué au T1 à dose >10000 UI/j (tératogène)",
     "Contre-indiqué à forte dose pendant grossesse",
     "Dose unique 200000 UI post-partum recommandée",
     "OMS 2023"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# UPGRADE / DOWNGRADE
# ═══════════════════════════════════════════════════════════════════════════════

def upgrade() -> None:
    # ── AMR expansion (40 entries) ────────────────────────────────────────────
    for drug, pathogen, region, res, source, year, conf in AMR_EXPANSION:
        drug_esc = drug.replace("'", "''")
        pathogen_esc = pathogen.replace("'", "''")
        source_esc = source.replace("'", "''")
        op.execute(
            f"""
            INSERT INTO amr_data (drug, pathogen, region, resistance_pct, data_source, year, confidence)
            VALUES ('{drug_esc}', '{pathogen_esc}', '{region}', {res}, '{source_esc}', {year}, '{conf}')
            ON CONFLICT DO NOTHING
            """
        )

    # ── DDI interactions (32 entries) ─────────────────────────────────────────
    for drug_a, drug_b, severity, mechanism, effect, mgmt in DDI_DATA:
        da = drug_a.replace("'", "''")
        db = drug_b.replace("'", "''")
        mech = mechanism.replace("'", "''")
        eff = effect.replace("'", "''")
        mg = mgmt.replace("'", "''")
        op.execute(
            f"""
            INSERT INTO ddi_interactions (drug_a, drug_b, severity, mechanism, clinical_effect, management)
            VALUES ('{da}', '{db}', '{severity}', '{mech}', '{eff}', '{mg}')
            """
        )

    # ── Drug safety (45 entries) ──────────────────────────────────────────────
    for drug, cat, lact, t1, t2, t3, source in DRUG_SAFETY_DATA:
        drug_esc = drug.replace("'", "''")
        t1_esc = t1.replace("'", "''")
        t2_esc = t2.replace("'", "''")
        t3_esc = t3.replace("'", "''")
        source_esc = source.replace("'", "''")
        lact_val = "true" if lact else "false"
        op.execute(
            f"""
            INSERT INTO drug_safety (drug, pregnancy_category, lactation_safe, t1_notes, t2_notes, t3_notes, source)
            VALUES ('{drug_esc}', '{cat}', {lact_val}, '{t1_esc}', '{t2_esc}', '{t3_esc}', '{source_esc}')
            ON CONFLICT (drug) DO UPDATE SET
                pregnancy_category = EXCLUDED.pregnancy_category,
                lactation_safe     = EXCLUDED.lactation_safe,
                t1_notes           = EXCLUDED.t1_notes,
                t2_notes           = EXCLUDED.t2_notes,
                t3_notes           = EXCLUDED.t3_notes,
                source             = EXCLUDED.source
            """
        )


def downgrade() -> None:
    # Remove drug safety entries
    drugs = [row[0].replace("'", "''") for row in DRUG_SAFETY_DATA]
    drug_list = ", ".join(f"'{d}'" for d in drugs)
    op.execute(f"DELETE FROM drug_safety WHERE drug IN ({drug_list})")

    # Remove DDI entries seeded by this migration
    for drug_a, drug_b, *_ in DDI_DATA:
        da = drug_a.replace("'", "''")
        db = drug_b.replace("'", "''")
        op.execute(f"DELETE FROM ddi_interactions WHERE drug_a = '{da}' AND drug_b = '{db}'")

    # Remove AMR expansion entries
    for drug, pathogen, region, *_ in AMR_EXPANSION:
        d = drug.replace("'", "''")
        p = pathogen.replace("'", "''")
        op.execute(f"DELETE FROM amr_data WHERE drug = '{d}' AND pathogen = '{p}' AND region = '{region}'")
