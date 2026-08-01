import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import Help from '../components/Help'

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

export default function PlaylistViewer() {
  const [screens, setScreens] = useState(null)
  const [selectedIds, setSelectedIds] = useState([])
  const [data, setData] = useState(null)
  const [classFilter, setClassFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.screens().then((list) => {
      setScreens(list)
      // Default: pre-select the real DRILLROOM screens if present, else just the first 3.
      const drillroom = list.filter((s) => s.title.toUpperCase().includes('DRILLROOM'))
      setSelectedIds((drillroom.length ? drillroom : list.slice(0, 3)).map((s) => s.id))
    }).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (selectedIds.length === 0) {
      setData(null)
      return
    }
    setLoading(true)
    setError(null)
    api.playlists(selectedIds)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [selectedIds])

  function toggleScreen(id) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const rowsByDay = useMemo(() => {
    if (!data) return null
    const map = Object.fromEntries(DAY_KEYS.map((d) => [d, []]))
    for (const screen of data.screens) {
      for (const row of screen.rows) {
        if (!row.day) continue
        if (classFilter && !row.title.toUpperCase().includes(classFilter.toUpperCase())) continue
        map[row.day].push({ ...row, screen_title: screen.screen_title })
      }
    }
    for (const d of DAY_KEYS) map[d].sort((a, b) => (a.start || '').localeCompare(b.start || ''))
    return map
  }, [data, classFilter])

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-800 mb-1">
        Playlist Viewer
        <Help text="Reads live directly from AbleSign - exactly what's scheduled on each screen right now, organized by day. Use the checkboxes to pick which screens to show, and the search box to filter to one class." />
      </h1>
      <p className="text-sm text-slate-500 mb-4">Read-only - this never changes anything in AbleSign.</p>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}

      <div className="flex flex-wrap items-center gap-4 mb-4">
        <div className="flex flex-wrap gap-2">
          {screens?.map((s) => (
            <label
              key={s.id}
              className={`text-xs px-2.5 py-1.5 rounded-full border cursor-pointer select-none ${
                selectedIds.includes(s.id) ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-300'
              }`}
            >
              <input type="checkbox" className="hidden" checked={selectedIds.includes(s.id)} onChange={() => toggleScreen(s.id)} />
              {s.title}
            </label>
          ))}
        </div>
        <input
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          placeholder="Filter by class name…"
          className="border border-slate-300 rounded-md px-3 py-1.5 text-sm w-56"
        />
      </div>

      {loading && <div className="text-sm text-slate-500">Loading…</div>}

      {rowsByDay && (
        <div className="grid grid-cols-7 gap-3">
          {DAY_NAMES.map((dayName, i) => {
            const key = DAY_KEYS[i]
            const items = rowsByDay[key]
            return (
              <div key={key} className="rounded-lg border border-slate-200 bg-white p-2 min-h-[200px]">
                <div className="text-xs font-semibold text-slate-500 mb-2 text-center">{dayName.slice(0, 3).toUpperCase()}</div>
                <div className="space-y-2">
                  {items.length === 0 && <div className="text-xs text-slate-300 text-center mt-4">—</div>}
                  {items.map((row, idx) => (
                    <div key={idx} className="bg-slate-50 border border-slate-200 rounded-md px-2 py-1.5 text-xs">
                      <div className="font-medium text-slate-800 leading-tight">{row.title}</div>
                      <div className="text-slate-500">{row.start}–{row.end}</div>
                      <div className="text-slate-400">{row.screen_title}</div>
                      {row.period_start && (
                        <div className={row.periodic_ok ? 'text-green-600' : 'text-slate-400 line-through'}>
                          {row.period_start} → {row.period_end}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
