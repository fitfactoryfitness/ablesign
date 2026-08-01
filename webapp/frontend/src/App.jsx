import React, { useState } from 'react'
import ScheduleEditor from './pages/ScheduleEditor'
import PlaylistViewer from './pages/PlaylistViewer'
import DeletePlaylist from './pages/DeletePlaylist'
import UploadContent from './pages/UploadContent'
import NowOnScreen from './pages/NowOnScreen'
import CreatePlaylist from './pages/CreatePlaylist'

const TABS = [
  { key: 'schedule', label: 'Weekly Schedule', Component: ScheduleEditor },
  { key: 'viewer', label: 'Playlist Viewer', Component: PlaylistViewer },
  { key: 'now', label: 'Now On Screen', Component: NowOnScreen },
  { key: 'upload', label: 'Upload Content', Component: UploadContent },
  { key: 'create', label: 'Create Playlist', Component: CreatePlaylist },
  { key: 'delete', label: 'Delete Playlist', Component: DeletePlaylist },
]

export default function App() {
  const [active, setActive] = useState('schedule')
  const Active = TABS.find((t) => t.key === active).Component

  return (
    <div className="min-h-screen flex">
      <nav className="w-56 shrink-0 bg-white border-r border-slate-200 p-4">
        <div className="text-lg font-bold text-indigo-700 mb-1">AbleSign</div>
        <div className="text-xs text-slate-400 mb-6">Control Panel</div>
        <div className="space-y-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setActive(t.key)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm font-medium ${
                active === t.key ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>
      <main className="flex-1 p-6 overflow-y-auto">
        <Active />
      </main>
    </div>
  )
}
