import React, { useEffect, useState } from 'react'
import { api } from '../api'
import Help from '../components/Help'
import ConfirmModal from '../components/ConfirmModal'
import JobLogPanel from '../components/JobLogPanel'

export default function UploadContent() {
  const [months, setMonths] = useState(null)
  const [selectedMonth, setSelectedMonth] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [jobKind, setJobKind] = useState(null) // 'preview' | 'real'
  const [error, setError] = useState(null)

  useEffect(() => {
    api.driveMonths().then((list) => {
      setMonths(list)
      const aug = list.find((m) => m.name.toLowerCase().includes('august'))
      setSelectedMonth((aug || list[0])?.name || '')
    }).catch((e) => setError(e.message))
  }, [])

  async function startPreview() {
    setError(null)
    try {
      const res = await api.startUpload(selectedMonth, true)
      setJobKind('preview')
      setJobId(res.job_id)
    } catch (e) {
      setError(e.message)
    }
  }

  async function startReal() {
    setError(null)
    try {
      const res = await api.startUpload(selectedMonth, false)
      setJobKind('real')
      setJobId(res.job_id)
      setConfirmOpen(false)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold text-slate-800 mb-1">
        Upload Content
        <Help text="Pulls the slides for a month from Google Drive and uploads them into AbleSign under GROUP FITNESS/<month>. This does NOT schedule anything on a screen - that's the Create Playlist page, once uploading is done." />
      </h1>
      <p className="text-sm text-slate-500 mb-4">Mirrors one month's slides from Drive into AbleSign. Doesn't touch any screen's playlist.</p>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}

      <label className="text-sm text-slate-600 block mb-1">Month folder</label>
      <select
        value={selectedMonth}
        onChange={(e) => setSelectedMonth(e.target.value)}
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-4"
      >
        {months?.map((m) => (
          <option key={m.drive_id} value={m.name}>{m.name}</option>
        ))}
      </select>

      <div className="flex gap-2">
        <button
          disabled={!selectedMonth}
          onClick={startPreview}
          className="px-4 py-2 rounded-md text-sm font-medium bg-white border border-slate-300 hover:bg-slate-50 disabled:opacity-40"
        >
          Preview (dry run)
        </button>
        <button
          disabled={!selectedMonth}
          onClick={() => setConfirmOpen(true)}
          className="px-4 py-2 rounded-md text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40"
        >
          Upload for real
        </button>
      </div>

      {jobId && (
        <div>
          <div className="text-xs text-slate-400 mt-4">{jobKind === 'preview' ? 'Preview run - nothing was uploaded to AbleSign.' : 'Real run - uploading to AbleSign now.'}</div>
          <JobLogPanel jobId={jobId} />
        </div>
      )}

      <ConfirmModal
        open={confirmOpen}
        title={`Upload "${selectedMonth}" to AbleSign?`}
        description="This uploads every TV1/TV3/TV5-tagged slide found in this month's Drive folder into AbleSign, creating folders as needed. It does not schedule anything on any screen."
        confirmLabel="Upload"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={startReal}
      />
    </div>
  )
}
