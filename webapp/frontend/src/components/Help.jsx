import React from 'react'

// The "?" bubble with an explanation on hover, used next to anything that
// might not be obvious at a glance.
export default function Help({ text }) {
  return (
    <span className="help-dot group relative">
      ?
      <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:block w-64 bg-slate-800 text-white text-xs rounded-md px-3 py-2 shadow-lg z-50 font-normal normal-case">
        {text}
      </span>
    </span>
  )
}
