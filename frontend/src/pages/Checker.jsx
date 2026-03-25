import React, { useState } from 'react'
import { Search, Phone, Globe, User, FileText, Loader2, ShieldCheck, ShieldAlert, ShieldX, ChevronDown } from 'lucide-react'
import { api } from '../api'

const MODES = [
  { key: 'phone', icon: Phone, label: '電話號碼', placeholder: '輸入電話號碼，例如 0912345678 或 +886912345678', apiCall: api.checkPhone },
  { key: 'url', icon: Globe, label: '網址連結', placeholder: '輸入可疑網址，例如 https://example.com', apiCall: api.checkUrl },
  { key: 'username', icon: User, label: '社群帳號', placeholder: '輸入社群帳號名稱（IG / FB / LINE / X），例如 @scammer123', apiCall: api.checkUsername },
  { key: 'content', icon: FileText, label: '訊息內容', placeholder: '貼上可疑訊息內容...', apiCall: api.checkContent },
]

const RISK_CONFIG = {
  safe:     { icon: ShieldCheck, color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20', label: '安全' },
  low:      { icon: ShieldCheck, color: 'text-lime-400',  bg: 'bg-lime-500/10',  border: 'border-lime-500/20',  label: '低風險' },
  medium:   { icon: ShieldAlert, color: 'text-yellow-400',bg: 'bg-yellow-500/10',border: 'border-yellow-500/20',label: '中風險' },
  high:     { icon: ShieldAlert, color: 'text-orange-400',bg: 'bg-orange-500/10',border: 'border-orange-500/20',label: '高風險' },
  critical: { icon: ShieldX,     color: 'text-red-400',   bg: 'bg-red-500/10',   border: 'border-red-500/20',   label: '危險' },
}

function RiskMeter({ score }) {
  const pct = Math.min(100, Math.max(0, score))
  const hue = 120 - (pct * 1.2) // green(120) -> red(0)
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs">
        <span className="text-slate-500">風險分數</span>
        <span className="font-mono font-bold" style={{ color: `hsl(${hue}, 80%, 55%)` }}>{score}/100</span>
      </div>
      <div className="h-2 rounded-full bg-white/5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000 ease-out"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, #4ade80 0%, hsl(${hue}, 80%, 55%) 100%)`,
          }}
        />
      </div>
    </div>
  )
}

const PLATFORMS = [
  { key: '', label: '自動偵測', desc: '嘗試所有平台' },
  { key: 'ig', label: 'Instagram', desc: 'IG 帳號' },
  { key: 'threads', label: 'Threads', desc: 'Threads 帳號' },
  { key: 'fb', label: 'Facebook', desc: 'FB 粉專/帳號' },
  { key: 'x', label: 'X (Twitter)', desc: '推特帳號' },
]

export default function Checker() {
  const [mode, setMode] = useState('phone')
  const [input, setInput] = useState('')
  const [platform, setPlatform] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const current = MODES.find(m => m.key === mode)

  const handleCheck = async () => {
    if (!input.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      let query = input.trim()
      // For username mode, prepend platform hint if selected
      if (mode === 'username' && platform) {
        query = `${platform}:${query.replace(/^@/, '')}`
      }
      const res = await current.apiCall(query)
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const riskCfg = result ? (RISK_CONFIG[result.risk_level] || RISK_CONFIG.safe) : null
  const RiskIcon = riskCfg?.icon

  return (
    <div className="space-y-6 fade-in-up max-w-3xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">查詢工具</h2>
        <p className="text-sm text-slate-500 mt-1">輸入可疑的電話、網址、帳號或訊息來檢測詐騙風險</p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-2 flex-wrap">
        {MODES.map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            onClick={() => { setMode(key); setResult(null); setError(null); setInput(''); setPlatform('') }}
            className={`
              flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all
              ${mode === key
                ? 'bg-green-500/10 text-green-400 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.3)]'
                : 'bg-white/[0.02] text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'}
            `}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="card-glow rounded-2xl bg-[var(--bg-card)] p-5">
        {/* Platform selector — only for username mode */}
        {mode === 'username' && (
          <div className="mb-4">
            <p className="text-xs text-slate-500 mb-2">選擇社群平台</p>
            <div className="flex gap-2 flex-wrap">
              {PLATFORMS.map(p => (
                <button
                  key={p.key}
                  onClick={() => setPlatform(p.key)}
                  className={`px-3 py-2 rounded-lg text-xs font-medium transition-all
                    ${platform === p.key
                      ? 'bg-green-500/15 text-green-400 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.3)]'
                      : 'bg-white/[0.03] text-slate-400 hover:text-slate-200 hover:bg-white/[0.05]'}`}
                >
                  <span className="block">{p.label}</span>
                  <span className="block text-[10px] text-slate-600 mt-0.5">{p.desc}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {mode === 'content' ? (
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={current.placeholder}
            rows={5}
            className="w-full bg-transparent border border-white/[0.06] rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-green-500/40 resize-none"
          />
        ) : (
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={current.placeholder}
            onKeyDown={e => e.key === 'Enter' && handleCheck()}
            className="w-full bg-transparent border border-white/[0.06] rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-green-500/40"
          />
        )}
        <button
          onClick={handleCheck}
          disabled={loading || !input.trim()}
          className="mt-4 w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold
                     bg-green-600 hover:bg-green-500 disabled:bg-green-900/30 disabled:text-green-700
                     text-white transition-all duration-200"
        >
          {loading ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> 分析中...</>
          ) : (
            <><Search className="w-4 h-4" /> 開始檢測</>
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className={`card-glow rounded-2xl bg-[var(--bg-card)] p-6 border ${riskCfg.border} fade-in-up`}>
          {/* Risk header */}
          <div className="flex items-center gap-4 mb-5">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${riskCfg.bg}`}>
              <RiskIcon className={`w-7 h-7 ${riskCfg.color}`} />
            </div>
            <div>
              <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${riskCfg.bg} ${riskCfg.color}`}>
                {riskCfg.label}
              </span>
              <p className="text-sm text-slate-400 mt-1.5">{result.summary}</p>
            </div>
          </div>

          {/* Risk meter */}
          <RiskMeter score={result.risk_score} />

          {/* Flags */}
          {result.flags && result.flags.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {result.flags.map((flag, i) => (
                <span key={i} className="text-xs px-2.5 py-1 rounded-lg bg-red-500/10 text-red-300 border border-red-500/10">
                  {flag}
                </span>
              ))}
            </div>
          )}

          {/* Action suggestion */}
          {result.action && (
            <div className="mt-4 p-3 rounded-xl bg-green-500/5 border border-green-500/10">
              <p className="text-xs font-semibold text-green-500 mb-1">建議行動</p>
              <p className="text-sm text-slate-300">{result.action}</p>
            </div>
          )}

          {/* Details */}
          {result.details && Object.keys(result.details).length > 0 && (
            <div className="mt-5 pt-5 border-t border-white/[0.05]">
              <h4 className="text-xs font-semibold text-slate-400 mb-3">詳細分析</h4>
              <div className="space-y-2">
                {Object.entries(result.details).map(([key, val]) => (
                  <div key={key} className="flex justify-between text-sm py-1.5 border-b border-white/[0.03] last:border-0">
                    <span className="text-slate-500">{key}</span>
                    <span className="text-slate-300 font-mono text-xs">
                      {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timestamp */}
          <p className="text-[11px] text-slate-600 mt-4">
            分析時間: {new Date(result.timestamp).toLocaleString('zh-TW')}
            {result.cached && ' (快取結果)'}
          </p>
        </div>
      )}
    </div>
  )
}
