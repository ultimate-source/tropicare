"use client";

import { ConsultationResponse } from "@/types";

interface Props {
  result: ConsultationResponse | null;
}

export default function ResultsPanel({ result }: Props) {
  if (!result) return null;

  return (
    <div className="mt-6 space-y-4">
      <section className="rounded border p-4">
        <h2 className="text-lg font-semibold">Diagnostic</h2>
        <p className="mt-2 text-sm">{result.diagnostic.reasoning}</p>
        <p className="mt-1 text-xs text-gray-500">
          Confiance : {(result.diagnostic.confidence * 100).toFixed(0)}%
        </p>
      </section>

      {result.treatments.length > 0 && (
        <section className="rounded border p-4">
          <h2 className="text-lg font-semibold">Traitements recommandés</h2>
          <ul className="mt-2 space-y-2">
            {result.treatments.map((t, i) => (
              <li key={i} className="text-sm">
                <strong>{t.medication}</strong> — {t.dosage} pendant{" "}
                {t.duration}
                <span className="ml-2 text-xs text-gray-500">
                  ({t.source})
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.warnings.length > 0 && (
        <section className="rounded border border-yellow-300 bg-yellow-50 p-4">
          <h2 className="text-lg font-semibold text-yellow-800">Alertes</h2>
          <ul className="mt-2 list-disc pl-4 text-sm text-yellow-700">
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
