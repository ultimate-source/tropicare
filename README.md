# TropiCare RAG

Système multi-agents sensible au contexte pour le raisonnement diagnostique et les recommandations d'antibiothérapie calibrées selon l'épidémiologie du Togo.

## Architecture

- **Frontend** : Next.js (React)
- **Backend** : Python (FastAPI) avec système multi-agents RAG

## Fonctionnalités

- Raisonnement diagnostique fondé sur les preuves
- Recommandations d'antibiothérapie adaptées au contexte togolais
- Prise en compte de la disponibilité locale des médicaments
- Données de résistance antimicrobienne locales
- Conformité aux directives OMS et PNLP

## Démarrage rapide

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Le frontend sera accessible sur `http://localhost:3000` et l'API sur `http://localhost:8000`.
