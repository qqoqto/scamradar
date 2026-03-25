import React, { useState, useEffect } from 'react'
import { AlertTriangle, Phone, Globe, User, Loader2, Trophy, Flame } from 'lucide-react'
import { api } from '../api'

const TYPE_CONFIG = {
  phone:    { icon: Phone, label: '電話', color: 'text-blue-400' },
  url:      { icon: Globe, label: '網址', color: 'text-purple-400' },
  domain:   { icon: Globe, label: '網域', color: 'text-purple-400' },
  username: { icon: User, label: '帳號', color: 'text-orange-400' },
  line_id:  { icon: User, label: 'LINE', color: 'text-green-400' },
}

function RankBadge({ rank }) {
  if (rank === 1) return <span className="text-lg">🥇</span>
  if (rank === 2) return <span className="text-lg">🥈</span>
  if (rank === 3) return <span className="text-lg">🥉</span>
  return <span className="text-xs text-slate-600 font-mono w-6 text-center">#{rank}</span>
}

export default function Blacklist() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState('')

  useEffect(() => {
    setLoading(true)
    api.getBlacklistTop(50, filterType || null)
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }, [filterType])

  return (
    <div className="space-y-6 fade-in-up">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">黑名單排行榜</h2>
          <p className="text-sm text-slate-500 mt-1">最多被回報的可疑對象</p>
        </div>
        <div className="flex gap-2">
          {[
            { key: '', label: '全部' },
            { key: 'phone', label: '電話' },
            { key: 'url', label: '網址' },
            { key: 'username', label: '帳號' },
            { key: 'domain', label: '網域' },
          ].map(f => (
            <button
              key={f.key}
              onClick={() => setFilterType(f.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                ${filterType === f.key
                  ? 'bg-green-500/10 text-green-400 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.3)]'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]'}`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-green-500" />
        </div>
      ) : entries.length === 0 ? (
        <div className="text-center py-16">
          <AlertTriangle className="w-10 h-10 text-slate-700 mx-auto mb-3" />
          <p className="text-slate-500">黑名單目前為空</p>
          <p className="text-xs text-slate-600 mt-1">透過 LINE Bot 回報可疑對象來建立黑名單</p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry, i) => {
            const cfg = TYPE_CONFIG[entry.target_type] || TYPE_CONFIG.username
            const Icon = cfg.icon
            const scorePct = Math.min(100, entry.risk_score)
            const hue = 120 - (scorePct * 1.2)
            return (
              <div
                key={`${entry.target_value}-${i}`}
                className="card-glow rounded-xl bg-[var(--bg-card)] p-4 flex items-center gap-4"
              >
                {/* Rank */}
                <div className="w-8 flex-shrink-0 flex justify-center">
                  <RankBadge rank={i + 1} />
                </div>

                {/* Type icon */}
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-white/[0.03] flex-shrink-0`}>
                  <Icon className={`w-4.5 h-4.5 ${cfg.color}`} />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-slate-200 truncate">{entry.target_value}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${cfg.color} bg-white/[0.04]`}>
                      {cfg.label}
                    </span>
                  </div>
                  {entry.platform && (
                    <p className="text-xs text-slate-500 mt-0.5">{entry.platform}</p>
                  )}
                </div>

                {/* Report count */}
                <div className="flex items-center gap-1.5 text-sm flex-shrink-0">
                  <Flame className="w-3.5 h-3.5 text-orange-400" />
                  <span className="font-bold text-slate-300">{entry.report_count}</span>
                  <span className="text-xs text-slate-600">回報</span>
                </div>

                {/* Risk score bar */}
                <div className="w-24 flex-shrink-0 hidden sm:block">
                  <div className="flex justify-between text-[10px] mb-1">
                    <span className="text-slate-600">風險</span>
                    <span className="font-mono" style={{ color: `hsl(${hue}, 80%, 55%)` }}>
                      {entry.risk_score}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${scorePct}%`,
                        background: `hsl(${hue}, 80%, 55%)`,
                      }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
