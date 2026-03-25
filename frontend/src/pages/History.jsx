import React, { useState, useEffect } from 'react'
import { Clock, Filter, Phone, Globe, User, FileText, Image, Loader2 } from 'lucide-react'
import { api } from '../api'

const TYPE_ICONS = { phone: Phone, url: Globe, account: User, content: FileText, image: Image }
const TYPE_LABELS = { phone: '電話', url: '網址', account: '帳號', content: '內容', image: '截圖' }

const RISK_STYLES = {
  safe:     'text-green-400 bg-green-500/10',
  low:      'text-lime-400 bg-lime-500/10',
  medium:   'text-yellow-400 bg-yellow-500/10',
  high:     'text-orange-400 bg-orange-500/10',
  critical: 'text-red-400 bg-red-500/10',
  unknown:  'text-slate-400 bg-slate-500/10',
}
const RISK_LABELS = { safe: '安全', low: '低風險', medium: '中風險', high: '高風險', critical: '危險', unknown: '未知' }

export default function History() {
  const [queries, setQueries] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState('')
  const [filterRisk, setFilterRisk] = useState('')

  const load = () => {
    setLoading(true)
    api.getRecentQueries(100, filterType || null, filterRisk || null)
      .then(setQueries)
      .catch(() => setQueries([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filterType, filterRisk])

  return (
    <div className="space-y-6 fade-in-up">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">歷史紀錄</h2>
          <p className="text-sm text-slate-500 mt-1">所有查詢紀錄一覽</p>
        </div>
        <div className="flex gap-2">
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            className="bg-[var(--bg-card)] border border-white/[0.06] text-sm text-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:border-green-500/40"
          >
            <option value="">所有類型</option>
            <option value="phone">電話</option>
            <option value="url">網址</option>
            <option value="account">帳號</option>
            <option value="content">內容</option>
            <option value="image">截圖</option>
          </select>
          <select
            value={filterRisk}
            onChange={e => setFilterRisk(e.target.value)}
            className="bg-[var(--bg-card)] border border-white/[0.06] text-sm text-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:border-green-500/40"
          >
            <option value="">所有風險</option>
            <option value="safe">安全</option>
            <option value="low">低風險</option>
            <option value="medium">中風險</option>
            <option value="high">高風險</option>
            <option value="critical">危險</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-green-500" />
        </div>
      ) : queries.length === 0 ? (
        <div className="text-center py-16">
          <Clock className="w-10 h-10 text-slate-700 mx-auto mb-3" />
          <p className="text-slate-500">尚無查詢紀錄</p>
        </div>
      ) : (
        <div className="card-glow rounded-2xl bg-[var(--bg-card)] overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-12 gap-2 px-5 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wider border-b border-white/[0.04]">
            <div className="col-span-1">類型</div>
            <div className="col-span-4 lg:col-span-5">查詢內容</div>
            <div className="col-span-2">風險</div>
            <div className="col-span-2">分數</div>
            <div className="col-span-2">來源</div>
            <div className="col-span-1 hidden lg:block">時間</div>
          </div>

          {/* Rows */}
          {queries.map((q, i) => {
            const Icon = TYPE_ICONS[q.query_type] || FileText
            const riskStyle = RISK_STYLES[q.risk_level] || RISK_STYLES.unknown
            return (
              <div
                key={q.id || i}
                className="grid grid-cols-12 gap-2 px-5 py-3 text-sm border-b border-white/[0.02] hover:bg-white/[0.015] transition-colors"
              >
                <div className="col-span-1 flex items-center">
                  <Icon className="w-4 h-4 text-slate-500" />
                </div>
                <div className="col-span-4 lg:col-span-5 text-slate-300 truncate font-mono text-xs">
                  {q.query_input}
                </div>
                <div className="col-span-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${riskStyle}`}>
                    {RISK_LABELS[q.risk_level] || q.risk_level}
                  </span>
                </div>
                <div className="col-span-2 font-mono text-xs text-slate-400">
                  {q.risk_score}
                </div>
                <div className="col-span-2 text-xs text-slate-500">
                  {q.source === 'web_api' ? 'Web' : 'LINE'}
                </div>
                <div className="col-span-1 hidden lg:block text-xs text-slate-600">
                  {q.created_at ? new Date(q.created_at).toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' }) : ''}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
