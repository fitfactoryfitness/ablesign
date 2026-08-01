import React, { useEffect, useState } from 'react'
import { api } from '../api'
import Help from '../components/Help'
import ConfirmModal from '../components/ConfirmModal'

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

let nextLocalId = -1 // negative ids = new rows not yet saved, never collide with server ids (>=0)

function blankRow() {
  return { id: nextLocalId--, class: 'NEW CLASS', day: 'Monday', start: '09:00', end: '10:00' }
}

export default function ScheduleEditor() {
  const [rows, setRows] = useState(null)
  const [savedRows, setSavedRows] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [dragOverDay, setDragOverDay] = useState(null)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setError(null)
    try {
      const data = await api.getSchedule()
      setRows(data.rows)
      setSavedRows(data.rows)
    } catch (e) {
      setError(e.message)
    }
  }

  if (error) return <div className="text-red-600 text-sm">Failed to load schedule: {error}</div>
  if (!rows) return <div className="text-slate-500 text-sm">Loading schedule…</div>

  const dirty = JSON.stringify(rows) !== JSON.stringify(savedRows)
  const editingRow = rows.find((r) => r.id === editingId) || null

  function updateRow(id, patch) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  function duplicateRow(id) {
    const row = rows.find((r) => r.id === id)
    if (!row) return
    const copy = { ...row, id: nextLocalId-- }
    setRows((prev) => [...prev, copy])
  }

  function deleteRow(id) {
    setRows((prev) => prev.filter((r) => r.id !== id))
    if (editingId === id) setEditingId(null)
  }

  function addRow() {
    const row = blankRow()
    setRows((prev) => [...prev, row])
    setEditingId(row.id)
  }

  function onDropDay(day) {
    setDragOverDay(null)
    const id = Number(window.__draggedRowId)
    if (Number.isNaN(id)) return
    updateRow(id, { day })
  }

  function diffSummary() {
    const savedById = new Map(savedRows.map((r) => [r.id, r]))
    const currentById = new Map(rows.map((r) => [r.id, r]))
    const added = rows.filter((r) => !savedById.has(r.id))
    const removed = savedRows.filter((r) => !currentById.has(r.id))
    const modified = rows.filter((r) => {
      const prev = savedById.get(r.id)
      return prev && (prev.class !== r.class || prev.day !== r.day || prev.start !== r.start || prev.end !== r.end)
    })
    return { added, removed, modified }
  }

  async function confirmSave() {
    setSaving(true)
    setError(null)
    try {
      const payload = rows.map(({ class: cls, day, start, end }) => ({ class: cls, day, start, end }))
      await api.saveSchedule(payload)
      await load()
      setConfirmOpen(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const { added, removed, modified } = dirty ? diffSummary() : { added: [], removed: [], modified: [] }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">
            Weekly Schedule
            <Help text="This is schedule.csv, the source of truth for Create Playlist. Drag a class to a different day, click a class to edit its time, or use the icons to duplicate/delete. Nothing is saved to disk until you click 'Update the schedule' and confirm." />
          </h1>
          <p className="text-sm text-slate-500 mt-1">Drag a class card to move it to a different day. Click a card to edit its time.</p>
        </div>
        <button
          onClick={addRow}
          className="px-3 py-2 rounded-md text-sm font-medium bg-white border border-slate-300 hover:bg-slate-50"
        >
          + Add class
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}

      <div className="grid grid-cols-7 gap-3">
        {DAY_NAMES.map((day) => {
          const dayRows = rows
            .filter((r) => r.day === day)
            .sort((a, b) => a.start.localeCompare(b.start))
          return (
            <div
              key={day}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOverDay(day)
              }}
              onDragLeave={() => setDragOverDay((d) => (d === day ? null : d))}
              onDrop={(e) => {
                e.preventDefault()
                onDropDay(day)
              }}
              className={`rounded-lg border p-2 min-h-[200px] transition-colors ${
                dragOverDay === day ? 'bg-indigo-50 border-indigo-300' : 'bg-white border-slate-200'
              }`}
            >
              <div className="text-xs font-semibold text-slate-500 mb-2 text-center">{day.slice(0, 3).toUpperCase()}</div>
              <div className="space-y-2">
                {dayRows.map((row) => (
                  <div
                    key={row.id}
                    draggable
                    onDragStart={() => {
                      window.__draggedRowId = row.id
                    }}
                    onClick={() => setEditingId(row.id)}
                    className="group bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-md px-2 py-1.5 text-xs cursor-grab active:cursor-grabbing"
                  >
                    <div className="font-medium text-indigo-900 leading-tight">{row.class}</div>
                    <div className="text-indigo-600">{row.start}–{row.end}</div>
                    <div className="hidden group-hover:flex gap-2 mt-1 text-[11px]">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          duplicateRow(row.id)
                        }}
                        className="text-slate-500 hover:text-indigo-700"
                      >
                        Duplicate
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteRow(row.id)
                        }}
                        className="text-slate-500 hover:text-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {editingRow && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-40 p-4" onClick={() => setEditingId(null)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-sm w-full p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Edit class</h3>
            <label className="text-xs text-slate-500">Class name</label>
            <input
              value={editingRow.class}
              onChange={(e) => updateRow(editingRow.id, { class: e.target.value })}
              className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm mb-3 mt-1"
            />
            <label className="text-xs text-slate-500">Day</label>
            <select
              value={editingRow.day}
              onChange={(e) => updateRow(editingRow.id, { day: e.target.value })}
              className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm mb-3 mt-1"
            >
              {DAY_NAMES.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
            <div className="flex gap-2 mb-4">
              <div className="flex-1">
                <label className="text-xs text-slate-500">Start</label>
                <input
                  type="time"
                  value={editingRow.start}
                  onChange={(e) => updateRow(editingRow.id, { start: e.target.value })}
                  className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-slate-500">End</label>
                <input
                  type="time"
                  value={editingRow.end}
                  onChange={(e) => updateRow(editingRow.id, { end: e.target.value })}
                  className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-sm mt-1"
                />
              </div>
            </div>
            <div className="flex justify-between">
              <button onClick={() => deleteRow(editingRow.id)} className="text-sm text-red-600 hover:underline">
                Delete this class
              </button>
              <button onClick={() => setEditingId(null)} className="px-3 py-1.5 rounded-md text-sm bg-slate-100 hover:bg-slate-200">
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {dirty && (
        <div className="fixed bottom-6 right-6 z-30">
          <button
            onClick={() => setConfirmOpen(true)}
            className="px-5 py-3 rounded-full shadow-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold"
          >
            Update the schedule ({added.length + removed.length + modified.length} change{added.length + removed.length + modified.length === 1 ? '' : 's'})
          </button>
        </div>
      )}

      <ConfirmModal
        open={confirmOpen}
        title="Save changes to the schedule?"
        description="This overwrites schedule.csv on disk (a backup of the previous version is kept automatically). It does NOT touch AbleSign - you still need to run Create Playlist afterwards to push these changes live."
        confirmLabel={saving ? 'Saving…' : 'Save schedule'}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmSave}
      >
        <div className="text-sm space-y-2 max-h-56 overflow-y-auto border border-slate-200 rounded-md p-3 bg-slate-50">
          {added.length > 0 && (
            <div>
              <div className="font-semibold text-green-700">Added ({added.length})</div>
              {added.map((r) => (
                <div key={r.id} className="text-slate-600">+ {r.class} — {r.day} {r.start}-{r.end}</div>
              ))}
            </div>
          )}
          {removed.length > 0 && (
            <div>
              <div className="font-semibold text-red-700">Removed ({removed.length})</div>
              {removed.map((r) => (
                <div key={r.id} className="text-slate-600">− {r.class} — {r.day} {r.start}-{r.end}</div>
              ))}
            </div>
          )}
          {modified.length > 0 && (
            <div>
              <div className="font-semibold text-amber-700">Changed ({modified.length})</div>
              {modified.map((r) => (
                <div key={r.id} className="text-slate-600">~ {r.class} — {r.day} {r.start}-{r.end}</div>
              ))}
            </div>
          )}
        </div>
      </ConfirmModal>
    </div>
  )
}
