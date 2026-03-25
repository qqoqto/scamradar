import React, { useState, useEffect } from 'react'
import { Shield, Users, FileSearch, AlertOctagon, TrendingUp, Activity } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { api } from '../api'

const RISK_COLORS = {
  safe: '#4ade80',
  low: '#a3e635',
  medium: '#fbbf24',
  high: '#f87171',
  critical: '#ef4444',
  unknown: '#64748b',
}

const RISK_LABELS = {
  safe: '安全',
  low: '低風險',
  medium: '中風險',
  high: '高風險',
  critical: '危險',
  unknown: '未知',
}

function StatCard({ icon: Icon, label, value, sub, color = 'green' }) {
  const colors = {
    green: 'text-green-400 bg-green-500/10',
    red: 'text-red-400 bg-red-500/10',
    yellow: 'text-yellow-400 bg-yellow-500/10',
    blue: 'text-blue-400 bg-blue-500/10',
  }
  return (
    <div className="card-glow rounded-2xl bg-[var(--bg-card)] p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${colors[color]}`}>
          <Icon className="w-4.5 h-4.5" />
        </div>
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <div className="text-3xl font-bold tracking-tight">{value.toLocaleString()}</div>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#1a2540] border border-green-900/30 rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-sm font-bold text-green-400">{payload[0].value} 筆查詢</p>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="relative w-16 h-16">
          <div className="absolute inset-0 rounded-full border-2 border-green-500/20" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-green-400 radar-sweep" />
          <Shield className="absolute inset-0 m-auto w-6 h-6 text-green-500/50" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <AlertOctagon className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <p className="text-slate-400">無法載入數據</p>
        <p className="text-xs text-slate-600 mt-1">{error}</p>
      </div>
    )
  }

  const pieData = stats?.risk_distribution
    ? Object.entries(stats.risk_distribution).map(([key, val]) => ({
        name: RISK_LABELS[key] || key,
        value: val,
        fill: RISK_COLORS[key] || '#64748b',
      }))
    : []

  return (
    <div className="space-y-6 fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">儀表板</h2>
          <p className="text-sm text-slate-500 mt-1">ScamRadar 獵詐雷達 — 即時防護統計</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-green-500">
          <span className="w-2 h-2 rounded-full bg-green-400 pulse-dot" />
          運作中
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={FileSearch} label="總查詢數" value={stats?.total_queries || 0}
                  sub={`今日 ${stats?.queries_today || 0} 筆`} color="green" />
        <StatCard icon={Users} label="使用者" value={stats?.total_users || 0} color="blue" />
        <StatCard icon={AlertOctagon} label="回報數" value={stats?.total_reports || 0} color="yellow" />
        <StatCard icon={Shield} label="黑名單" value={stats?.total_blacklisted || 0} color="red" />
      </div>

      {/* Charts row */}
      <div className="grid lg:grid-cols-3 gap-4">
        {/* Trend chart */}
        <div className="lg:col-span-2 card-glow rounded-2xl bg-[var(--bg-card)] p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-green-500" />
            <h3 className="text-sm font-semibold">近 14 日查詢趨勢</h3>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats?.daily_trend || []}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  tickFormatter={d => d.slice(5)}
                  tick={{ fill: '#475569', fontSize: 11 }}
                  axisLine={{ stroke: '#1e293b' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#475569', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={32}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone" dataKey="count" stroke="#22c55e" strokeWidth={2}
                  fill="url(#g1)" dot={false} activeDot={{ r: 4, fill: '#4ade80' }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Risk pie */}
        <div className="card-glow rounded-2xl bg-[var(--bg-card)] p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-green-500" />
            <h3 className="text-sm font-semibold">風險分佈</h3>
          </div>
          {pieData.length > 0 ? (
            <>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData} dataKey="value" cx="50%" cy="50%"
                      innerRadius={40} outerRadius={65} paddingAngle={3}
                      stroke="none"
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: '#1a2540',
                        border: '1px solid rgba(34,197,94,0.2)',
                        borderRadius: '8px',
                        fontSize: '12px',
                        color: '#e2e8f0',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2 mt-2">
                {pieData.map(d => (
                  <div key={d.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ background: d.fill }} />
                      <span className="text-slate-400">{d.name}</span>
                    </div>
                    <span className="font-mono text-slate-300">{d.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-600 text-center py-8">尚無數據</p>
          )}
        </div>
      </div>

      {/* Query type breakdown */}
      {stats?.top_risk_categories?.length > 0 && (
        <div className="card-glow rounded-2xl bg-[var(--bg-card)] p-5">
          <h3 className="text-sm font-semibold mb-4">查詢類型統計</h3>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {stats.top_risk_categories.map(cat => {
              const typeLabels = { phone: '電話', url: '網址', account: '帳號', content: '內容', image: '截圖' }
              return (
                <div key={cat.category} className="text-center p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <p className="text-2xl font-bold text-green-400">{cat.count}</p>
                  <p className="text-xs text-slate-500 mt-1">{typeLabels[cat.category] || cat.category}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
