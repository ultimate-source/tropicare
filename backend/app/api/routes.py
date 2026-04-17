from fastapi import APIRouter, HTTPException
from app.models.schemas import ConsultationRequest, ConsultationResponse
from app.agents.orchestrator import AgentOrchestrator

router = APIRouter()
orchestrator = AgentOrchestrator()


@router.post("/consult", response_model=ConsultationResponse)
async def consult(request: ConsultationRequest):
    """Point d'entrée principal pour une consultation diagnostique."""
    try:
        result = await orchestrator.process(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/status")
async def agents_status():
    """Vérifie le statut des agents."""
    return orchestrator.get_status()
