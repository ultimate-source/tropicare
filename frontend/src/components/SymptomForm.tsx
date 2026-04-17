"use client";

import { useState } from "react";
import { ConsultationRequest } from "@/types";

interface Props {
  onSubmit: (request: ConsultationRequest) => void;
  isLoading: boolean;
}

const REGIONS_TOGO = [
  "Lomé",
  "Kara",
  "Sokodé",
  "Atakpamé",
  "Dapaong",
  "Tsévié",
  "Kpalimé",
];

export default function SymptomForm({ onSubmit, isLoading }: Props) {
  const [symptoms, setSymptoms] = useState("");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [region, setRegion] = useState("Lomé");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      symptoms: symptoms.split(",").map((s) => s.trim()).filter(Boolean),
      patient_age: age ? parseInt(age) : undefined,
      patient_weight: weight ? parseFloat(weight) : undefined,
      region,
      medical_history: [],
      current_medications: [],
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="symptoms" className="block text-sm font-medium">
          Symptômes (séparés par des virgules)
        </label>
        <textarea
          id="symptoms"
          value={symptoms}
          onChange={(e) => setSymptoms(e.target.value)}
          className="mt-1 w-full rounded border p-2"
          rows={3}
          placeholder="fièvre, céphalées, frissons..."
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="age" className="block text-sm font-medium">
            Âge (ans)
          </label>
          <input
            id="age"
            type="number"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            placeholder="25"
          />
        </div>
        <div>
          <label htmlFor="weight" className="block text-sm font-medium">
            Poids (kg)
          </label>
          <input
            id="weight"
            type="number"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            placeholder="70"
          />
        </div>
      </div>

      <div>
        <label htmlFor="region" className="block text-sm font-medium">
          Région
        </label>
        <select
          id="region"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="mt-1 w-full rounded border p-2"
        >
          {REGIONS_TOGO.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full rounded bg-green-700 px-4 py-2 text-white hover:bg-green-800 disabled:opacity-50"
      >
        {isLoading ? "Analyse en cours..." : "Analyser"}
      </button>
    </form>
  );
}
