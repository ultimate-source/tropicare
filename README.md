# 🩺 TropiCare

**Système d'aide à la décision clinique propulsé par l'IA pour le diagnostic des maladies tropicales et l'antibiothérapie en Afrique de l'Ouest.**

TropiCare combine un pipeline multi-agents (LLM) avec la génération augmentée par récupération (RAG) pour fournir des recommandations diagnostiques et thérapeutiques fondées sur les preuves, calibrées selon l'épidémiologie du Togo — directives OMS, formulaire CAME, et données locales de résistance antimicrobienne (RAM).

---

## Table des matières

- [Architecture](#architecture)
- [Pile technologique](#pile-technologique)
- [Fonctionnalités](#fonctionnalités)
- [Pipeline multi-agents](#pipeline-multi-agents)
- [Pipeline RAG](#pipeline-rag)
- [Démarrage rapide](#démarrage-rapide)
- [Variables d'environnement](#variables-denvironnement)
- [Commandes Make](#commandes-make)
- [Évaluation et benchmark](#évaluation-et-benchmark)
- [Flux de données](#flux-de-données)
- [Observabilité](#observabilité)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js 16)                        │
│         React 19 · Zustand · Tailwind CSS 4 · NDJSON Stream        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ POST /api/v1/sessions/{id}/turns
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Gateway (FastAPI + Uvicorn)                      │
│            JWT RS256 · Rate Limiting · StreamingResponse            │
└──────────────┬──────────────────────────────────────┬───────────────┘
               │                                      │
               ▼                                      ▼
┌──────────────────────────┐          ┌───────────────────────────────┐
│     Orchestrateur        │          │     Serveur MCP (outils)      │
│  Intake → Diagnostic →   │◄────────►│  symptom_extractor            │
│  Antibiothérapie →       │          │  hybrid_retrieve              │
│  Validation              │          │  formulary_lookup             │
│  (Claude Sonnet 4)       │          │  amr_lookup · ddi_check       │
└──────┬───────────────────┘          │  epid_calendar · safety_class │
       │                              └───────────────────────────────┘
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PostgreSQL 16        Redis 7           Qdrant 1.9.2                │
│  (données + FTS)      (sessions/queue)  (vecteurs 3072-dim)         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Pile technologique

| Couche           | Technologies                                              |
|------------------|-----------------------------------------------------------|
| Frontend         | Next.js 16, React 19, Zustand, Tailwind CSS 4             |
| Backend          | FastAPI, Uvicorn, Claude Sonnet 4, OpenTelemetry           |
| Base de données  | PostgreSQL 16, Redis 7, Qdrant 1.9.2                      |
| Ingestion        | ARQ (file de tâches), OpenAI text-embedding-3-large, Nomic (fallback) |
| Observabilité    | Jaeger (traces), Prometheus + Grafana (métriques)          |
| Infrastructure   | Docker Compose, Alembic (migrations)                       |
| Évaluation       | Harness personnalisé, juges LLM, jeu de benchmark          |

---

## Fonctionnalités

- **Diagnostic différentiel** fondé sur les preuves avec scores de confiance et codes CIM-11
- **Recommandations d'antibiothérapie** adaptées au contexte togolais (formulaire CAME, RAM locale)
- **Détection d'urgences** : méningite, paludisme grave, fièvre hémorragique, choc septique
- **Vérification des interactions médicamenteuses** (DDI) et sécurité grossesse/allaitement
- **Citations structurées** — chaque affirmation clinique est sourcée
- **Streaming temps réel** — les résultats s'affichent progressivement (NDJSON)
- **Contexte épidémiologique** saisonnier par région via l'outil `epid_calendar`
- **Base de connaissances administrable** — upload PDF/DOCX avec ingestion automatique
- **Tableau de bord analytique** pour les administrateurs
- **Journal d'audit** immuable pour la conformité réglementaire

---

## Pipeline multi-agents

Quatre agents spécialisés s'exécutent en séquence pour chaque requête clinique :

### 1. Agent d'accueil (Intake)
Extrait le contexte patient structuré à partir du texte libre : âge, sexe, poids, région, symptômes, signes vitaux, résultats de laboratoire, allergies, médicaments en cours, statut de grossesse. Utilise l'outil MCP `symptom_extractor` pour la reconnaissance d'entités.

### 2. Agent diagnostique (ReAct)
Effectue un raisonnement itératif (jusqu'à 4 cycles Think → Observe → Act) avec récupération hybride sur 3 requêtes simultanées. Produit un diagnostic différentiel classé avec : rang, nom de la maladie, code CIM-11, confiance, preuves, tests confirmatoires, drapeaux rouges. Émet des alertes d'urgence si nécessaire.

### 3. Agent d'antibiothérapie
Appels parallèles aux outils MCP : `formulary_lookup`, `amr_lookup`, `drug_ddi_check`, `safety_classifier`. Filtre les candidats selon : disponibilité CAME, résistance RAM < 30 %, absence de contre-indications, sécurité grossesse. Produit les lignes de traitement (1ère ligne, 2ème ligne, alternatives) avec posologie, voie, fréquence, durée et surveillance.

### 4. Agent de validation
Porte de qualité déterministe (température = 0) vérifiant : présence de citations, cohérence numérique (± 20 %), drapeaux d'urgence, présence du disclaimer, langue, périmètre. Verdict : `PASS` (transmettre) | `WARN` (transmettre avec annotations) | `BLOCK` (rejeter).

---

## Pipeline RAG

### Ingestion (worker ARQ asynchrone)

1. **Parsing** — extraction de sections depuis PDF/DOCX
2. **Chunking** — découpage sémantique : 512 tokens max, 64 tokens de chevauchement, respect des limites de phrases
3. **Métadonnées** — tags maladies, tags médicaments, classification du type de contenu
4. **Embedding** — OpenAI `text-embedding-3-large` (3072 dimensions), fallback Nomic en local
5. **Déduplication** — hash SHA-256 du contenu (16 premiers caractères)
6. **Stockage** — upsert PostgreSQL (`kb_chunks`) + Qdrant (recherche vectorielle)

### Récupération hybride

- **BM25** — recherche plein texte sur PostgreSQL (tokenisation française)
- **Similarité vectorielle** — recherche cosinus sur Qdrant
- Combinaison des résultats, déduplication par `chunk_id`, top 8 par score
- Filtrage par métadonnées (région, tags maladies, type de source)

---

## Démarrage rapide

### Prérequis

- Docker et Docker Compose
- Python 3.12+
- Node.js 20+ et npm
- Clés API : `ANTHROPIC_API_KEY` et `OPENAI_API_KEY`

### Installation en 5 étapes

**1. Cloner et configurer**

```bash
git clone <repo-url> && cd tropicare
cp .env.example .env
# Renseigner ANTHROPIC_API_KEY et OPENAI_API_KEY dans .env
```

**2. Générer la paire de clés JWT (RS256)**

```bash
make keys
```

**3. Démarrer la stack complète** (build des images, migrations, bootstrap Qdrant)

```bash
make up
```

**4. Alimenter la base de connaissances** (placer les PDF dans `data/seed_documents/`)

```bash
make seed
```

**5. Vérifier**

```bash
curl http://localhost:8000/api/v1/health
```

### Accès aux services

| Service    | URL                          | Notes                        |
|------------|------------------------------|------------------------------|
| Frontend   | http://localhost:3000         | Interface clinicien          |
| Gateway    | http://localhost:8000         | API REST                     |
| Grafana    | http://localhost:3001         | admin / tropicare            |
| Jaeger     | http://localhost:16686        | Traces distribuées           |
| Qdrant     | http://localhost:6333         | Dashboard vectoriel          |
| Prometheus | http://localhost:9090         | Métriques                    |

### Créer un utilisateur admin

```bash
make create-admin email=admin@tropicare.health password=motdepasse
```

### Développement frontend (hors Docker)

```bash
cd frontend
npm install
npm run dev
```

---

## Variables d'environnement

| Variable               | Description                                      | Défaut                          |
|------------------------|--------------------------------------------------|---------------------------------|
| `ANTHROPIC_API_KEY`    | Clé API Anthropic (Claude)                       | —                               |
| `OPENAI_API_KEY`       | Clé API OpenAI (embeddings)                      | —                               |
| `DATABASE_URL`         | URL de connexion PostgreSQL                      | `postgresql://tropicare:tropicare@localhost:5432/tropicare` |
| `REDIS_URL`            | URL Redis                                        | `redis://localhost:6379/0`      |
| `QDRANT_URL`           | URL du serveur Qdrant                            | `http://localhost:6333`         |
| `QDRANT_COLLECTION`    | Nom de la collection Qdrant                      | `tropicare_knowledge`           |
| `MCP_URL`              | URL du serveur d'outils MCP                      | `http://localhost:8001`         |
| `MODEL`                | Modèle LLM utilisé                               | `claude-sonnet-4-20250514`      |
| `JWT_PUBLIC_KEY_PATH`  | Chemin vers la clé publique JWT                  | `keys/public.pem`              |
| `JWT_PRIVATE_KEY_PATH` | Chemin vers la clé privée JWT                    | `keys/private.pem`             |
| `CORS_ORIGINS`         | Origines CORS autorisées (JSON array)            | `["http://localhost:3000"]`     |
| `ENABLE_LLM_JUDGES`   | Activer les juges LLM pour l'évaluation (0/1)   | `0`                             |

---

## Commandes Make

```bash
make help             # Afficher toutes les cibles disponibles
make install          # Installer les dépendances Python
make keys             # Générer la paire de clés JWT RS256
make up               # Démarrer la stack complète (Docker Compose)
make down             # Arrêter tous les conteneurs
make logs             # Suivre les logs (make logs svc=gateway)
make ps               # État des conteneurs
make migrate          # Exécuter les migrations Alembic (Docker)
make migrate-local    # Exécuter les migrations en local
make seed             # Alimenter la base de connaissances
make create-admin     # Créer un admin (email=... password=...)
make lint             # Lancer ruff + mypy
make format           # Formater le code (ruff)
make test             # Tests unitaires (pytest)
make test-integration # Tests d'intégration
make eval             # Lancer le pipeline d'évaluation
make benchmark-gen    # Générer les cas de benchmark restants
make benchmark-review # Revue interactive des cas générés
make clean            # Supprimer les artefacts de build
make clean-data       # Supprimer toutes les données locales (volumes Docker)
```

---

## Évaluation et benchmark

### Workflow pour atteindre 200 cas validés

**Étape 1** — Valider les cas seed avec un clinicien partenaire togolais (revue manuelle de `benchmark_v1_seed.json`)

**Étape 2** — Générer les 160 cas restants (~8-12 $ en appels API)

```bash
make benchmark-gen
```

**Étape 3** — Revue interactive par le clinicien

```bash
make benchmark-review
```

**Étape 4** — Lancer l'évaluation

```bash
make eval
```

### Métriques mesurées

**Diagnostic :**
- Précision top-1 / top-3 / top-5 (code CIM-11 ou nom de maladie)
- MRR (Mean Reciprocal Rank)
- Rappel des drapeaux d'urgence
- Taux de citation (citations / affirmations estimées)
- Latence (p50, p95)

**Antibiothérapie :**
- Adhérence 1ère ligne (≥ 1 médicament attendu présent)
- Disponibilité CAME
- Absence de médicaments contre-indiqués
- Présence du disclaimer
- Nombre de citations

**Juges LLM** (échantillon 20 % pour limiter les coûts) :
- Juge qualité des citations : vérifie le sourçage et la cohérence numérique
- Juge hallucination : détecte les médicaments inventés, posologies impossibles, associations aberrantes

---

## Flux de données

```
Le clinicien saisit sa requête
  → Next.js ChatStream (hook useStream ouvre un flux NDJSON)
  → POST /api/v1/sessions/{id}/turns (gateway FastAPI)
  → JWT vérifié → rate-limit appliqué → StreamingResponse créée
  → Orchestrator.handle_turn() commence à émettre des événements :
      ├── IntakeAgent     → MCP : symptom_extractor
      ├── DiagnosticAgent → MCP : hybrid_retrieve (×3) + epid_calendar
      │     └── Boucle ReAct : si "RETRIEVE:" → récupère plus de chunks
      ├── AntibiotherapyAgent → MCP : formulary_lookup + amr_lookup + ddi_check (parallèle)
      └── ValidationAgent → porte PASS / WARN / BLOCK
  → chaque événement streamé en NDJSON : {"type": "...", "data": {...}}\n
  → le worker d'ingestion (ARQ) traite les uploads KB indépendamment
```

Types d'événements streamés : `thinking` → `emergency_flag` → `differential_item` → `treatment_line` → `citation` → `done`

---

## Observabilité

- **Jaeger** (http://localhost:16686) — traces distribuées via OpenTelemetry (OTLP gRPC/HTTP)
- **Prometheus** (http://localhost:9090) — collecte des métriques applicatives
- **Grafana** (http://localhost:3001) — tableaux de bord préconfigurés (identifiants : admin / tropicare)
- **Journal d'audit** — table PostgreSQL immuable, partitionnée par année, pour la conformité réglementaire

---

## Structure du projet

```
tropicare/
├── backend/
│   └── app/
│       ├── agents/          # Agents LLM (intake, diagnostic, antibiothérapie, validation)
│       ├── api/             # Routes FastAPI
│       ├── config/          # Configuration et settings
│       ├── eval/            # Framework d'évaluation et benchmark
│       ├── gateway/         # Point d'entrée API, auth JWT, rate limiting
│       ├── ingestion/       # Pipeline d'ingestion (parsing, chunking, embedding)
│       ├── models/          # Schémas Pydantic
│       ├── orchestrator/    # Orchestration des agents, sessions, audit
│       ├── rag/             # Récupération hybride (BM25 + vectoriel)
│       └── tools/           # Serveur MCP (outils externes)
├── frontend/
│   └── src/
│       ├── app/             # Pages Next.js (App Router)
│       ├── components/      # Composants React (chat, intake, résultats)
│       └── hooks/           # Hooks personnalisés (useStream)
├── alembic/                 # Migrations de base de données
├── docker-compose.yml       # Stack d'infrastructure complète
└── Makefile                 # Commandes de développement
```

---

## Licence

À définir.
