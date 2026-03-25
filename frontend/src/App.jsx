import React from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Shield, Search, Clock, AlertTriangle, Menu, X } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Checker from './pages/Checker'
import History from './pages/History'
import Blacklist from './pages/Blacklist'

const NAV_ITEMS = [
  { to: '/', icon: Shield, label: '總覽' },
  { to: '/check', icon: Search, label: '查詢工具' },
  { to: '/history', icon: Clock, label: '歷史紀錄' },
  { to: '/blacklist', icon: AlertTriangle, label: '黑名單' },
]

function Sidebar({ mobileOpen, setMobileOpen }) {
  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside className={`
        fixed top-0 left-0 h-full w-64 z-50
        bg-[#0d1526] border-r border-green-900/20
        flex flex-col
        transition-transform duration-300 ease-in-out
        lg:translate-x-0
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="px-6 py-6 flex items-center gap-3">
          <div className="relative w-10 h-10">
            <div className="absolute inset-0 rounded-full bg-green-500/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-green-400" />
            </div>
            <div className="absolute inset-0 rounded-full border border-green-500/30 radar-sweep"
                 style={{ borderTopColor: 'transparent', borderLeftColor: 'transparent' }} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-green-400 tracking-tight">ScamRadar</h1>
            <p className="text-[10px] text-slate-500 tracking-widest uppercase">獵詐雷達</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `
                flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium
                transition-all duration-200
                ${isActive
                  ? 'bg-green-500/10 text-green-400 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.2)]'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]'}
              `}
            >
              <Icon className="w-4.5 h-4.5" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-green-900/10">
          <p className="text-[11px] text-slate-600">
            LINE Bot: <span className="text-green-600 font-mono">@693zkvby</span>
          </p>
          <p className="text-[11px] text-slate-600 mt-1">v2.0 — Phase 2</p>
        </div>
      </aside>
    </>
  )
}

export default function App() {
  const [mobileOpen, setMobileOpen] = React.useState(false)

  return (
    <BrowserRouter>
      <div className="min-h-screen">
        <Sidebar mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} />

        {/* Mobile header */}
        <div className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-[#0d1526]/90 backdrop-blur-md border-b border-green-900/20 z-30 flex items-center px-4">
          <button onClick={() => setMobileOpen(true)} className="p-2 text-slate-400 hover:text-green-400">
            <Menu className="w-5 h-5" />
          </button>
          <span className="ml-3 text-sm font-bold text-green-400">ScamRadar</span>
        </div>

        {/* Main content */}
        <main className="lg:ml-64 pt-14 lg:pt-0 min-h-screen">
          <div className="p-4 lg:p-8 max-w-7xl mx-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/check" element={<Checker />} />
              <Route path="/history" element={<History />} />
              <Route path="/blacklist" element={<Blacklist />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
