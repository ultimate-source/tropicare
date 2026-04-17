import { ConsultationRequest, ConsultationResponse } from "@/types";

const API_BASE = "/api";

export async function submitConsultation(
  request: ConsultationRequest
): Promise<ConsultationResponse> {
  const res = await fetch(`${API_BASE}/consult`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    throw new Error(`Erreur API: ${res.status}`);
  }

  return res.json();
}

export async function getAgentsStatus(): Promise<Record<string, string>> {
  const res = await fetch(`${API_BASE}/agents/status`);
  return res.json();
}
