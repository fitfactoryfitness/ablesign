import React, { useEffect, useState } from 'react'
import { api } from '../api'
import Help from '../components/Help'
import ConfirmModal from '../components/ConfirmModal'

export default function DeletePlaylist() {
  const [screens, setScreens] = useState(null)
  const [selectedId, setSelectedId] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.screens().then(setScreens).catch((e) => setError(e.message))
  }, [])

  const selectedScreen = screens?.find((s) => String(s.id) === String(selectedId))

  async function confirmDelete() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.deletePlaylist(Number(selectedId))
      setResult(res)
      setConfirmOpen(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-xl font-semibold text-slate-800 mb-1">
        Delete Playlist
        <Help text="Wipes every item off a screen's playlist - a clean slate before pushing new content. This is permanent and cannot be undone from here, so it requires typing DELETE to confirm." />
      </h1>
      <p className="text-sm text-slate-500 mb-4">Permanently clears every item on the chosen screen. Cannot be undone.</p>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {result && (
        <div className="mb-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded-md px-3 py-2">
          Cleared {result.cleared_count} item(s) from "{selectedScreen?.title}".
        </div>
      )}

      <label className="text-sm text-slate-600 block mb-1">Screen</label>
      <select
        value={selectedId}
        onChange={(e) => setSelectedId(e.target.value)}
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-4"
      >
        <option value="">Select a screen…</option>
        {screens?.map((s) => (
          <option key={s.id} value={s.id}>{s.title} (id {s.id})</option>
        ))}
      </select>

      <button
        disabled={!selectedId}
        onClick={() => setConfirmOpen(true)}
        className="px-4 py-2 rounded-md text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Delete Playlist
      </button>

      <ConfirmModal
        open={confirmOpen}
        title={`Delete everything on "${selectedScreen?.title}"?`}
        description="This permanently removes every scheduled item from this screen right now. There is no undo."
        confirmLabel={busy ? 'Deleting…' : 'Delete permanently'}
        danger
        requireText="DELETE"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
