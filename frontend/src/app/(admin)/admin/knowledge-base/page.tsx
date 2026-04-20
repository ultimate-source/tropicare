// ─────────────────────────────────────────────────────────────────────────────
// app/(admin)/admin/knowledge-base/page.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useEffect, useRef, useState } from "react"
import { api, type KBDocument } from "@/lib/api"
import { cn } from "@/lib/utils"
import { SkeletonTableRows } from "@/components/LoadingSkeleton"

const SOURCE_TYPES = ["guideline", "formulary", "amr_data", "epidemiology"]

export default function KnowledgeBasePage() {
  const [docs,      setDocs]      = useState<KBDocument[]>([])
  const [loading,   setLoading]   = useState(true)
  const [uploading, setUploading] = useState(false)
  const [progress,  setProgress]  = useState<string | null>(null)
  const [error,     setError]     = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // Form state
  const [title,   setTitle]   = useState("")
  const [srcType, setSrcType] = useState("guideline")
  const [version, setVersion] = useState("")

  async function loadDocs() {
    try {
      const data = await api.admin.listDocuments()
      setDocs(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadDocs() }, []) // eslint-disable-line react-hooks/set-state-in-effect

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file || !title) return

    setUploading(true)
    setProgress(`Envoi de ${file.name}…`)
    setError(null)

    try {
      const fd = new FormData()
      fd.append("file",        file)
      fd.append("title",       title)
      fd.append("source_type", srcType)
      fd.append("version",     version)

      const result = await api.admin.uploadDocument(fd)
      setProgress(`Ingestion en cours… (id: ${result.document_id.slice(0, 8)})`)
      setTitle(""); setVersion("")
      if (fileRef.current) fileRef.current.value = ""

      // Poll until chunk_count > 0
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        await loadDocs()
        const doc = (await api.admin.listDocuments()).find(d => d.id === result.document_id)
        if ((doc?.chunk_count ?? 0) > 0 || attempts > 20) {
          clearInterval(poll)
          setProgress(null)
          setUploading(false)
        }
      }, 3000)

    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur d'upload")
      setUploading(false)
      setProgress(null)
    }
  }

  async function handleSupersede(docId: string) {
    const replacement = window.prompt("ID du document de remplacement :")
    if (!replacement) return
    try {
      await api.admin.supersede(docId, replacement)
      await loadDocs()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur")
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <header>
        <h1 className="text-lg font-semibold text-gray-900">Base de connaissances</h1>
      </header>

      {/* Upload form */}
      <form onSubmit={handleUpload}
        className="rounded-xl border bg-white p-5 space-y-4 shadow-sm">
        <h2 className="text-sm font-medium text-gray-700">Ajouter un document</h2>

        {error    && <p className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</p>}
        {progress && <p className="text-sm text-blue-600 bg-blue-50 rounded p-2">{progress}</p>}

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label htmlFor="kb-title" className="block text-xs font-medium text-gray-600 mb-1">Titre</label>
            <input id="kb-title" value={title} onChange={e => setTitle(e.target.value)} required
              placeholder="PNLP Togo — Directives paludisme 2023"
              aria-label="Titre du document"
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label htmlFor="kb-type" className="block text-xs font-medium text-gray-600 mb-1">Type</label>
            <select id="kb-type" value={srcType} onChange={e => setSrcType(e.target.value)}
              aria-label="Type de document"
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              {SOURCE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="kb-version" className="block text-xs font-medium text-gray-600 mb-1">Version</label>
            <input id="kb-version" value={version} onChange={e => setVersion(e.target.value)}
              placeholder="2023"
              aria-label="Version du document"
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="col-span-2">
            <label htmlFor="kb-file" className="block text-xs font-medium text-gray-600 mb-1">Fichier (PDF / DOCX / JSON)</label>
            <input id="kb-file" ref={fileRef} type="file" accept=".pdf,.docx,.doc,.json" required
              aria-label="Sélectionner un fichier à téléverser"
              className="w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-blue-700 hover:file:bg-blue-100" />
          </div>
        </div>
        <button type="submit" disabled={uploading}
          aria-label="Téléverser et indexer le document"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
          {uploading ? "Traitement…" : "Téléverser et indexer"}
        </button>
      </form>

      {/* Document list */}
      <div className="rounded-xl border bg-white overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              {["Titre", "Type", "Version", "Chunks", "Indexé le", ""].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading && (
              <SkeletonTableRows cols={6} rows={3} />
            )}
            {!loading && docs.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-xs">Aucun document indexé</td></tr>
            )}
            {docs.map(doc => (
              <tr key={doc.id} className={cn("hover:bg-gray-50", doc.superseded && "opacity-40")}>
                <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate">{doc.title}</td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                    {doc.source_type}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">{doc.version || "—"}</td>
                <td className="px-4 py-3 text-gray-700 tabular-nums">
                  {doc.chunk_count > 0
                    ? doc.chunk_count
                    : <span className="text-amber-500 text-xs">en cours…</span>}
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs">
                  {new Date(doc.ingested_at).toLocaleDateString("fr-FR")}
                </td>
                <td className="px-4 py-3">
                  {!doc.superseded && (
                    <button onClick={() => handleSupersede(doc.id)}
                      aria-label={`Remplacer le document ${doc.title}`}
                      className="text-xs text-red-500 hover:text-red-700 hover:underline">
                      Remplacer
                    </button>
                  )}
                  {doc.superseded && (
                    <span className="text-xs text-gray-400 italic">Remplacé</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
