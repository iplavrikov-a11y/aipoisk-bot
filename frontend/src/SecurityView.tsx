import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Ban, CheckCircle2, Clock, RefreshCw, ShieldAlert, ShieldCheck, Unlock } from 'lucide-react'

type SecurityOverview = {
  summary: {
    security_events_24h: number
    security_events_7d: number
    reg_blocked_7d: number
    active_blocks: number
  }
  work_hours: {
    enabled: boolean
    is_open: boolean
    start: string
    end: string
    tz_offset: number
    quiet_night: boolean
    local_time: string
    notice: string
  }
  settings: {
    support_work_hours_enabled: boolean
    support_work_hours_start: string
    support_work_hours_end: string
    support_timezone_offset: number
    support_quiet_night_notifications: boolean
    support_ai_antispam_enabled: boolean
    support_ai_auto_reply_enabled: boolean
    registration_block_disposable_email: boolean
  }
  registration_attempts: Array<{
    id: string
    email: string
    ip_address: string
    status: string
    user_agent: string
    flags: string[]
    created_at?: string | null
  }>
  security_events: Array<{
    id: string
    event_type: string
    severity: string
    ip_address: string
    actor_key: string
    user_agent: string
    payload_preview: string
    reason: string
    action_taken: string
    is_ip_blocked: boolean
    created_at?: string | null
  }>
  blocked_actors: Array<{
    id: string
    actor_type: string
    actor_value: string
    dialog_key: string
    reason: string
    blocked_by: string
    created_at?: string | null
  }>
}

function fmtDate(raw?: string | null) {
  if (!raw) return '—'
  try {
    return new Date(raw).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return raw
  }
}

export function SecurityView() {
  const [data, setData] = useState<SecurityOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [subTab, setSubTab] = useState<'registrations' | 'events' | 'blocks'>('registrations')

  const [workEnabled, setWorkEnabled] = useState(true)
  const [workStart, setWorkStart] = useState('09:00')
  const [workEnd, setWorkEnd] = useState('20:00')
  const [quietNight, setQuietNight] = useState(true)
  const [aiAntispam, setAiAntispam] = useState(true)
  const [aiAutoReply, setAiAutoReply] = useState(true)
  const [blockDisposable, setBlockDisposable] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/admin/security/overview?limit=80', { credentials: 'include' })
      if (!res.ok) throw new Error(`Ошибка загрузки (${res.status})`)
      const json: SecurityOverview = await res.json()
      setData(json)
      setWorkEnabled(json.settings.support_work_hours_enabled)
      setWorkStart(json.settings.support_work_hours_start)
      setWorkEnd(json.settings.support_work_hours_end)
      setQuietNight(json.settings.support_quiet_night_notifications)
      setAiAntispam(json.settings.support_ai_antispam_enabled)
      setAiAutoReply(json.settings.support_ai_auto_reply_enabled)
      setBlockDisposable(json.settings.registration_block_disposable_email)
    } catch (e: any) {
      setError(e?.message || 'Не удалось загрузить журнал безопасности')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function saveSettings() {
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const res = await fetch('/api/admin/security/settings', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          support_work_hours_enabled: workEnabled,
          support_work_hours_start: workStart,
          support_work_hours_end: workEnd,
          support_quiet_night_notifications: quietNight,
          support_ai_antispam_enabled: aiAntispam,
          support_ai_auto_reply_enabled: aiAutoReply,
          registration_block_disposable_email: blockDisposable,
        }),
      })
      if (!res.ok) throw new Error('Не удалось сохранить настройки')
      setNotice('Настройки защиты и режима работы сохранены.')
      await load()
    } catch (e: any) {
      setError(e?.message || 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  async function blockIp(ip: string, reason: string) {
    if (!ip || ip === '127.0.0.1' || ip === 'unknown') return
    try {
      const res = await fetch('/api/admin/security/block', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actor_type: 'ip', actor_value: ip, reason }),
      })
      if (!res.ok) throw new Error('Не удалось заблокировать IP')
      setNotice(`IP ${ip} заблокирован.`)
      await load()
    } catch (e: any) {
      setError(e?.message || 'Ошибка блокировки')
    }
  }

  async function unblockActor(id: string) {
    try {
      const res = await fetch('/api/admin/security/unblock', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      })
      if (!res.ok) throw new Error('Не удалось разблокировать')
      setNotice('Блокировка снята.')
      await load()
    } catch (e: any) {
      setError(e?.message || 'Ошибка разблокировки')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ShieldCheck size={20} color="#0f766e" />
          <strong>Защита от спама, атак и ночной режим поддержки</strong>
        </div>
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
          <RefreshCw size={14} /> Обновить
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <div className="card" style={{ padding: '14px' }}>
            <div style={{ fontSize: '12px', color: '#64748b' }}>Инцидентов за 24ч</div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#0f172a' }}>{data.summary.security_events_24h}</div>
          </div>
          <div className="card" style={{ padding: '14px' }}>
            <div style={{ fontSize: '12px', color: '#64748b' }}>Инцидентов за 7 дней</div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#0f172a' }}>{data.summary.security_events_7d}</div>
          </div>
          <div className="card" style={{ padding: '14px' }}>
            <div style={{ fontSize: '12px', color: '#64748b' }}>Отбито регистраций (7д)</div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#b45309' }}>{data.summary.reg_blocked_7d}</div>
          </div>
          <div className="card" style={{ padding: '14px' }}>
            <div style={{ fontSize: '12px', color: '#64748b' }}>Активных блокировок</div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#be123c' }}>{data.summary.active_blocks}</div>
          </div>
          <div className="card" style={{ padding: '14px' }}>
            <div style={{ fontSize: '12px', color: '#64748b' }}>Режим поддержки ({data.work_hours.local_time} МСК)</div>
            <div style={{ fontSize: '15px', fontWeight: 600, marginTop: '4px', color: data.work_hours.is_open ? '#047857' : '#0369a1' }}>
              {data.work_hours.is_open ? 'Рабочие часы' : 'Ночной / тихий режим'}
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
          <Clock size={16} /> Режим работы, Telegram и AI-фильтр
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <input type="checkbox" checked={workEnabled} onChange={e => setWorkEnabled(e.target.checked)} />
            Включить расписание работы поддержки (МСК)
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <span>С:</span>
            <input type="text" value={workStart} onChange={e => setWorkStart(e.target.value)} style={{ width: '76px' }} />
            <span>До:</span>
            <input type="text" value={workEnd} onChange={e => setWorkEnd(e.target.value)} style={{ width: '76px' }} />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <input type="checkbox" checked={quietNight} onChange={e => setQuietNight(e.target.checked)} />
            Не будить ЛС админа в Telegram в нерабочее время
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <input type="checkbox" checked={aiAntispam} onChange={e => setAiAntispam(e.target.checked)} />
            AI-антиспам фильтр входящих сообщений чата
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <input type="checkbox" checked={aiAutoReply} onChange={e => setAiAutoReply(e.target.checked)} />
            AI-помощник первой линии (ответы по тарифам и услугам)
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <input type="checkbox" checked={blockDisposable} onChange={e => setBlockDisposable(e.target.checked)} />
            Блокировать одноразовые и тестовые email при регистрации
          </label>
        </div>
        <div>
          <button type="button" className="btn btn-primary" onClick={saveSettings} disabled={saving}>
            <CheckCircle2 size={14} /> {saving ? 'Сохранение...' : 'Сохранить настройки защиты'}
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button
          type="button"
          className={`btn ${subTab === 'registrations' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setSubTab('registrations')}
        >
          Попытки регистрации ({data?.registration_attempts.length || 0})
        </button>
        <button
          type="button"
          className={`btn ${subTab === 'events' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setSubTab('events')}
        >
          <ShieldAlert size={14} /> Журнал атак и спама ({data?.security_events.length || 0})
        </button>
        <button
          type="button"
          className={`btn ${subTab === 'blocks' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setSubTab('blocks')}
        >
          <Ban size={14} /> Блокировки ({data?.blocked_actors.length || 0})
        </button>
      </div>

      {data && subTab === 'registrations' && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Email</th>
                <th>IP</th>
                <th>Статус</th>
                <th>Флаги</th>
                <th>User-Agent</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.registration_attempts.map(row => (
                <tr key={row.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: '12px' }}>{fmtDate(row.created_at)}</td>
                  <td style={{ fontWeight: 500 }}>{row.email}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{row.ip_address}</td>
                  <td>
                    <span className={`badge ${row.status === 'created' ? 'badge-success' : 'badge-warning'}`}>
                      {row.status}
                    </span>
                  </td>
                  <td style={{ fontSize: '11px' }}>
                    {row.flags.length > 0 ? (
                      <span style={{ color: '#b91c1c', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <AlertTriangle size={12} /> {row.flags.join(', ')}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td style={{ fontSize: '11px', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {row.user_agent || '—'}
                  </td>
                  <td>
                    {row.ip_address && row.ip_address !== '127.0.0.1' && !row.flags.includes('ip_blocked') && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '4px 8px', fontSize: '11px' }}
                        onClick={() => blockIp(row.ip_address, `Подозрительная регистрация: ${row.email}`)}
                      >
                        Бан IP
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && subTab === 'events' && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тип</th>
                <th>Уровень</th>
                <th>IP / Актор</th>
                <th>Причина</th>
                <th>Фрагмент</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.security_events.map(ev => (
                <tr key={ev.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: '12px' }}>{fmtDate(ev.created_at)}</td>
                  <td><code>{ev.event_type}</code></td>
                  <td>{ev.severity}</td>
                  <td style={{ fontSize: '12px' }}>
                    <div style={{ fontFamily: 'monospace' }}>{ev.ip_address || '—'}</div>
                    <div style={{ color: '#64748b' }}>{ev.actor_key || '—'}</div>
                  </td>
                  <td style={{ fontSize: '12px' }}>{ev.reason}</td>
                  <td style={{ fontSize: '11px', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {ev.payload_preview || '—'}
                  </td>
                  <td>
                    {ev.ip_address && ev.ip_address !== '127.0.0.1' && !ev.is_ip_blocked && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '4px 8px', fontSize: '11px' }}
                        onClick={() => blockIp(ev.ip_address, ev.reason || ev.event_type)}
                      >
                        Бан IP
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && subTab === 'blocks' && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тип</th>
                <th>Значение</th>
                <th>Причина</th>
                <th>Кем</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.blocked_actors.map(b => (
                <tr key={b.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: '12px' }}>{fmtDate(b.created_at)}</td>
                  <td><code>{b.actor_type}</code></td>
                  <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{b.actor_value}</td>
                  <td style={{ fontSize: '12px' }}>{b.reason || '—'}</td>
                  <td style={{ fontSize: '12px' }}>{b.blocked_by}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ padding: '4px 8px', fontSize: '11px' }}
                      onClick={() => unblockActor(b.id)}
                    >
                      <Unlock size={12} /> Снять бан
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
