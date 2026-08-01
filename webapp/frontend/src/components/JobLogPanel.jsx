import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api'

// Polls a background job (upload / create-playlist execute) and shows its
// live print() output, exactly like watching the terminal - so nothing
// feels like a black box, even for hours-long runs.
export default function JobLogPanel({ jobId, onDone }) {
  const [job, setJob] = useState(null)
  const logRef = useRef(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    let timer

    async function poll() {
      try {
        const data = await api.jobStatus(jobId)
        if (cancelled) return
        setJob(data)
        if (data.status === 'running') {
          timer = setTimeout(poll, 1500)
        } else if (onDoneRef.current) {
          onDoneRef.current(data)
        }
      } catch (e) {
        if (!cancelled) setJob({ status: 'error', log: String(e.message || e), error: String(e.message || e) })
      }
    }
    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [jobId])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [job?.log])

  if (!jobId) return null

  const statusColor =
    job?.status === 'done' ? 'text-green-600' : job?.status === 'error' ? 'text-red-600' : 'text-amber-600'
  const statusLabel =
    job?.status === 'running' ? 'Running…' : job?.status === 'done' ? 'Done' : job?.status === 'error' ? 'Error' : '…'

  return (
    <div className="mt-4 border border-slate-200 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between bg-slate-100 px-3 py-2">
        <span className="text-sm font-medium">Live log</span>
        <span className={`text-sm font-semibold ${statusColor}`}>{statusLabel}</span>
      </div>
      <pre ref={logRef} className="bg-slate-900 text-slate-100 text-xs p-3 h-64 overflow-y-auto whitespace-pre-wrap">
        {job?.log || 'Starting…'}
      </pre>
    </div>
  )
}
