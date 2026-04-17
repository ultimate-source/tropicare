"use client";

import { useState } from "react";
import SymptomForm from "@/components/SymptomForm";
import ResultsPanel from "@/components/ResultsPanel";
import { submitConsultation } from "@/lib/api";
import { ConsultationRequest, ConsultationResponse } from "@/types";

export default function Home() {
  const [result, setResult] = useState<ConsultationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (request: ConsultationRequest) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await submitConsultation(request);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-2 text-3xl font-bold text-green-800">
        TropiCare RAG
      </h1>
      <p className="mb-8 text-sm text-gray-600">
        Diagnostic et antibiothérapie adaptés au contexte togolais
        — OMS / PNLP
      </p>

      <SymptomForm onSubmit={handleSubmit} isLoading={isLoading} />

      {error && (
        <p className="mt-4 text-sm text-red-600">{error}</p>
      )}

      <ResultsPanel result={result} />
    </main>
  );
}
