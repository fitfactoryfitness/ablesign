import React, { useState } from 'react'

// Used everywhere in the app before any mutating action fires. Two modes:
// - requireText set: destructive action, must type the exact word to enable Confirm.
// - requireText unset: simple Cancel/Confirm, still an explicit click required.
export default function ConfirmModal({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  danger = false,
  requireText,
  onConfirm,
  onCancel,
  children,
}) {
  const [typed, setTyped] = useState('')

  if (!open) return null

  const canConfirm = requireText ? typed.trim().toUpperCase() === requireText.toUpperCase() : true

  function handleCancel() {
    setTyped('')
    onCancel()
  }

  function handleConfirm() {
    setTyped('')
    onConfirm()
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
        <h2 className={`text-lg font-semibold mb-2 ${danger ? 'text-red-700' : 'text-slate-800'}`}>{title}</h2>
        {description && <p className="text-sm text-slate-600 mb-4 whitespace-pre-line">{description}</p>}
        {children}
        {requireText && (
          <div className="mt-4">
            <label className="text-sm text-slate-600 block mb-1">
              Type <span className="font-mono font-semibold text-red-700">{requireText}</span> to confirm
            </label>
            <input
              autoFocus
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
              placeholder={requireText}
            />
          </div>
        )}
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={handleCancel}
            className="px-4 py-2 rounded-md text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!canConfirm}
            className={`px-4 py-2 rounded-md text-sm font-medium text-white disabled:opacity-40 disabled:cursor-not-allowed ${
              danger ? 'bg-red-600 hover:bg-red-700' : 'bg-indigo-600 hover:bg-indigo-700'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
