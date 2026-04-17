export interface ConsultationRequest {
  symptoms: string[];
  patient_age?: number;
  patient_weight?: number;
  region: string;
  medical_history: string[];
  current_medications: string[];
}

export interface DiagnosticResult {
  diagnostics: Record<string, unknown>[];
  confidence: number;
  reasoning: string;
}

export interface TreatmentRecommendation {
  medication: string;
  dosage: string;
  duration: string;
  availability: string;
  alternatives: string[];
  source: string;
}

export interface ConsultationResponse {
  diagnostic: DiagnosticResult;
  treatments: TreatmentRecommendation[];
  warnings: string[];
  references: string[];
}
