import React, { useEffect, useState } from 'react'
import { api } from '../api'
import Help from '../components/Help'

export default function NowOnScreen() {
  const [screens, setScreens] = useState(null)
  const [selectedId, setSelectedId] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.screens().then((list) => {
      setScreens(list)
      const drillroom = list.find((s) => s.title.toUpperCase().includes('DRILLROOM TV1'))
      setSelectedId(String((drillroom || list[0])?.id || ''))
    }).catch((e) => setError(e.message))
  }, [])

  async function refresh(id) {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.playlistNow(id)
      setData(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (selectedId) refresh(Number(selectedId))
  }, [selectedId])

  return (
    <div className="max-w-lg">
      <h1 className="text-xl font-semibold text-slate-800 mb-1">
        Now On Screen
        <Help text="Checks what should be showing on a screen at this exact moment - by day, time, and (if set) periodic date range. Handy to confirm a screen is showing what it should, right now." />
      </h1>
      <p className="text-sm text-slate-500 mb-4">Read-only, based on this computer's clock.</p>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}

      <div className="flex items-center gap-2 mb-4">
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm"
        >
          {screens?.map((s) => (
            <option key={s.id} value={s.id}>{s.title} (id {s.id})</option>
          ))}
        </select>
        <button
          onClick={() => refresh(Number(selectedId))}
          className="px-3 py-2 rounded-md text-sm font-medium bg-white border border-slate-300 hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      {loading && <div className="text-sm text-slate-500">Loading…</div>}

      {data && (
        <div>
          <div className="text-sm text-slate-500 mb-3">Right now: {data.current_day} {data.current_time}</div>
          {data.rows.length === 0 ? (
            <div className="text-sm text-slate-400 border border-dashed border-slate-300 rounded-lg p-6 text-center">
              Nothing scheduled for right now on this screen.
            </div>
          ) : (
            <div className="space-y-2">
              {data.rows.map((row, idx) => (
                <div key={idx} className="bg-white border border-slate-200 rounded-lg px-4 py-3">
                  <div className="font-medium text-slate-800">{row.title}</div>
                  <div className="text-sm text-slate-500">{row.start}–{row.end}</div>
                  {row.period_start && (
                    <div className="text-xs text-green-600 mt-1">active {row.period_start} → {row.period_end}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
