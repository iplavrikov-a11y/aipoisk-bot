import { useState, useEffect, useCallback } from 'react'
import {
  Coins,
  RefreshCw,
  Search,
  Check,
  Save,
  Download,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  FileSpreadsheet,
  Users,
  Settings2,
} from 'lucide-react'

type ClientItem = {
  id: string
  name: string
  email: string
  telegram_id: string
  balance_rub: number
  allowed: boolean
  custom_price_rub: number | null
  effective_price_rub: number
  has_override: boolean
}

type JobItem = {
  id: string
  job_number: number | null
  client_id: string | null
  client_name: string
  title: string
  status: string
  progress: number
  message: string
  total_positions: number
  found_positions: number
  charged_rub: number
  created_at: string | null
  completed_at: string | null
  download_url: string | null
}

export function PriceMonitoringView() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [defaultPriceRub, setDefaultPriceRub] = useState<number>(50)
  const [savingSettings, setSavingSettings] = useState(false)
  const [settingsSaved, setSettingsSaved] = useState(false)

  const [clients, setClients] = useState<ClientItem[]>([])
  const [clientSearch, setClientSearch] = useState('')
  const [savingClientId, setSavingClientId] = useState<string | null>(null)
  const [clientEdits, setClientEdits] = useState<Record<string, { allowed: boolean; custom_price_rub: string }>>({})
  const [savedClientId, setSavedClientId] = useState<string | null>(null)

  const [jobs, setJobs] = useState<JobItem[]>([])

  const loadData = useCallback(async () => {
    try {
      setRefreshing(true)
      const [settingsRes, clientsRes, jobsRes] = await Promise.all([
        fetch('/api/price-monitoring/settings', { credentials: 'same-origin' }),
        fetch('/api/price-monitoring/clients', { credentials: 'same-origin' }),
        fetch('/api/price-monitoring/jobs', { credentials: 'same-origin' }),
      ])

      if (settingsRes.ok) {
        const sData = await settingsRes.json()
        setDefaultPriceRub(sData.default_price_rub ?? 50)
      }

      if (clientsRes.ok) {
        const cData = await clientsRes.json()
        const clientList: ClientItem[] = cData.clients || []
        setClients(clientList)
        const initialEdits: Record<string, { allowed: boolean; custom_price_rub: string }> = {}
        clientList.forEach((c) => {
          initialEdits[c.id] = {
            allowed: c.allowed,
            custom_price_rub: c.custom_price_rub !== null ? String(c.custom_price_rub) : '',
          }
        })
        setClientEdits(initialEdits)
      }

      if (jobsRes.ok) {
        const jData = await jobsRes.json()
        setJobs(jData.jobs || [])
      }
    } catch (err) {
      console.error('Failed to load price monitoring data', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const handleSaveSettings = async () => {
    setSavingSettings(true)
    setSettingsSaved(false)
    try {
      const res = await fetch('/api/price-monitoring/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ default_price_rub: defaultPriceRub }),
        credentials: 'same-origin',
      })
      if (res.ok) {
        setSettingsSaved(true)
        setTimeout(() => setSettingsSaved(false), 3000)
        void loadData()
      }
    } catch (err) {
      console.error(err)
    } finally {
      setSavingSettings(false)
    }
  }

  const handleSaveClient = async (clientId: string) => {
    const edit = clientEdits[clientId]
    if (!edit) return
    setSavingClientId(clientId)
    setSavedClientId(null)
    try {
      const customNum = edit.custom_price_rub.trim() === '' ? null : parseFloat(edit.custom_price_rub)
      const res = await fetch(`/api/price-monitoring/clients/${clientId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          allowed: edit.allowed,
          custom_price_rub: customNum,
        }),
        credentials: 'same-origin',
      })
      if (res.ok) {
        setSavedClientId(clientId)
        setTimeout(() => setSavedClientId(null), 2500)
        void loadData()
      }
    } catch (err) {
      console.error(err)
    } finally {
      setSavingClientId(null)
    }
  }

  const filteredClients = clients.filter((c) => {
    if (!clientSearch) return true
    const q = clientSearch.toLowerCase()
    return (
      c.name.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.telegram_id.toLowerCase().includes(q)
    )
  })

  const totalPositionsSum = jobs.reduce((acc, j) => acc + (j.total_positions || 0), 0)
  const totalFoundSum = jobs.reduce((acc, j) => acc + (j.found_positions || 0), 0)
  const totalRevenueRub = jobs.reduce((acc, j) => acc + (j.charged_rub || 0), 0)

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
        <Loader2 className="animate-spin text-slate-400" size={32} />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, margin: '0 0 6px 0', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Coins size={26} color="#059669" />
            Мониторинг цен по номенклатуре
          </h1>
          <p style={{ margin: 0, color: '#64748b', fontSize: '14px' }}>
            Кастомный модуль пакетного поиска цен поставщиков, ИНН и ссылок по Excel-спецификациям. Оплата только за найденные позиции.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={refreshing}
          className="btn btn-secondary"
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          Обновить
        </button>
      </div>

      {/* KPI Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Всего задач</div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '6px' }}>{jobs.length}</div>
          <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>пакетов обработки</div>
        </div>
        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Обработано строк</div>
          <div style={{ fontSize: '24px', fontWeight: 700, marginTop: '6px' }}>{totalPositionsSum}</div>
          <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>товарных позиций</div>
        </div>
        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Найдено с ценой</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#059669', marginTop: '6px' }}>{totalFoundSum}</div>
          <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
            {totalPositionsSum > 0 ? `${Math.round((totalFoundSum / totalPositionsSum) * 100)}% успешности` : '0%'}
          </div>
        </div>
        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Выручка модуля</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#2563eb', marginTop: '6px' }}>
            {totalRevenueRub.toLocaleString('ru-RU')} ₽
          </div>
          <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>списано за найденные цены</div>
        </div>
      </div>

      {/* Global Settings */}
      <div className="card" style={{ padding: '20px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Settings2 size={18} color="#2563eb" />
          Базовые настройки тарификации
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', maxWidth: '600px' }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', fontSize: '13px', color: '#475569', marginBottom: '6px', fontWeight: 500 }}>
              Базовая цена за найденную позицию (₽)
            </label>
            <input
              type="number"
              min="0"
              step="1"
              value={defaultPriceRub}
              onChange={(e) => setDefaultPriceRub(parseFloat(e.target.value) || 0)}
              className="form-input"
              style={{ width: '100%' }}
            />
          </div>
          <div style={{ alignSelf: 'flex-end' }}>
            <button
              onClick={handleSaveSettings}
              disabled={savingSettings}
              className="btn btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '8px', height: '38px' }}
            >
              {savingSettings ? <Loader2 size={16} className="animate-spin" /> : settingsSaved ? <Check size={16} /> : <Save size={16} />}
              {settingsSaved ? 'Сохранено' : 'Сохранить'}
            </button>
          </div>
        </div>
        <p style={{ margin: '12px 0 0 0', fontSize: '12px', color: '#64748b' }}>
          * Если у клиента не задана индивидуальная цена, применяется базовая цена. Списание происходит <b>только</b> за те позиции, по которым найдена хотя бы одна подтвержденная цена со ссылкой.
        </p>
      </div>

      {/* Client Access & Overrides */}
      <div className="card" style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Users size={18} color="#059669" />
            Доступ и индивидуальные цены клиентов
          </h2>
          <div style={{ position: 'relative', width: '280px' }}>
            <Search size={15} style={{ position: 'absolute', left: '10px', top: '10px', color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="Поиск по имени, email, TG..."
              value={clientSearch}
              onChange={(e) => setClientSearch(e.target.value)}
              className="form-input"
              style={{ paddingLeft: '32px', width: '100%', fontSize: '13px' }}
            />
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b', textAlign: 'left' }}>
                <th style={{ padding: '10px 12px' }}>Клиент / Email</th>
                <th style={{ padding: '10px 12px' }}>Баланс</th>
                <th style={{ padding: '10px 12px' }}>Доступ к модулю</th>
                <th style={{ padding: '10px 12px' }}>Цена за позицию (₽)</th>
                <th style={{ padding: '10px 12px', textAlign: 'right' }}>Действие</th>
              </tr>
            </thead>
            <tbody>
              {filteredClients.map((client) => {
                const edit = clientEdits[client.id] || { allowed: client.allowed, custom_price_rub: '' }
                const isSaving = savingClientId === client.id
                const isSaved = savedClientId === client.id

                return (
                  <tr key={client.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '12px' }}>
                      <div style={{ fontWeight: 600, color: '#0f172a' }}>{client.name}</div>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>
                        {client.email || (client.telegram_id ? `TG: ${client.telegram_id}` : client.id.slice(0, 8))}
                      </div>
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={{ fontWeight: 600, color: client.balance_rub > 500 ? '#059669' : '#dc2626' }}>
                        {client.balance_rub.toLocaleString('ru-RU')} ₽
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={edit.allowed}
                          onChange={(e) =>
                            setClientEdits((prev) => ({
                              ...prev,
                              [client.id]: { ...edit, allowed: e.target.checked },
                            }))
                          }
                          style={{ width: '16px', height: '16px', accentColor: '#059669' }}
                        />
                        <span style={{ fontSize: '12px', fontWeight: 500, color: edit.allowed ? '#059669' : '#64748b' }}>
                          {edit.allowed ? 'Включен' : 'Отключен'}
                        </span>
                      </label>
                    </td>
                    <td style={{ padding: '12px' }}>
                      <input
                        type="number"
                        placeholder={`${defaultPriceRub} ₽ (базовая)`}
                        value={edit.custom_price_rub}
                        onChange={(e) =>
                          setClientEdits((prev) => ({
                            ...prev,
                            [client.id]: { ...edit, custom_price_rub: e.target.value },
                          }))
                        }
                        className="form-input"
                        style={{ width: '140px', padding: '6px 10px', fontSize: '13px' }}
                      />
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>
                      <button
                        onClick={() => handleSaveClient(client.id)}
                        disabled={isSaving}
                        className="btn btn-secondary"
                        style={{ padding: '5px 12px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                      >
                        {isSaving ? <Loader2 size={13} className="animate-spin" /> : isSaved ? <Check size={13} color="#059669" /> : <Save size={13} />}
                        {isSaved ? 'Сохранено' : 'Сохранить'}
                      </button>
                    </td>
                  </tr>
                )
              })}
              {filteredClients.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: '24px', textAlign: 'center', color: '#94a3b8' }}>
                    Клиенты не найдены
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Jobs History */}
      <div className="card" style={{ padding: '20px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileSpreadsheet size={18} color="#0284c7" />
          История прогонов мониторинга цен
        </h2>

        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b', textAlign: 'left' }}>
                <th style={{ padding: '10px 12px' }}>№ Задачи</th>
                <th style={{ padding: '10px 12px' }}>Клиент</th>
                <th style={{ padding: '10px 12px' }}>Название / Файл</th>
                <th style={{ padding: '10px 12px' }}>Позиций</th>
                <th style={{ padding: '10px 12px' }}>Найдено</th>
                <th style={{ padding: '10px 12px' }}>Списано (₽)</th>
                <th style={{ padding: '10px 12px' }}>Статус</th>
                <th style={{ padding: '10px 12px', textAlign: 'right' }}>Отчет</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '12px' }}>
                    <span style={{ fontWeight: 600, color: '#334155' }}>#{job.job_number || job.id.slice(0, 6)}</span>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                      {job.created_at ? new Date(job.created_at).toLocaleString('ru-RU') : '—'}
                    </div>
                  </td>
                  <td style={{ padding: '12px', fontWeight: 500 }}>{job.client_name}</td>
                  <td style={{ padding: '12px' }}>
                    <div style={{ fontWeight: 500, color: '#0f172a' }}>{job.title}</div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>{job.message}</div>
                  </td>
                  <td style={{ padding: '12px', fontWeight: 600 }}>{job.total_positions || '—'}</td>
                  <td style={{ padding: '12px', fontWeight: 600, color: job.found_positions > 0 ? '#059669' : '#64748b' }}>
                    {job.found_positions}
                  </td>
                  <td style={{ padding: '12px', fontWeight: 600, color: job.charged_rub > 0 ? '#2563eb' : '#64748b' }}>
                    {job.charged_rub.toLocaleString('ru-RU')} ₽
                  </td>
                  <td style={{ padding: '12px' }}>
                    {job.status === 'completed' ? (
                      <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle2 size={12} /> Готово
                      </span>
                    ) : job.status === 'running' ? (
                      <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <Loader2 size={12} className="animate-spin" /> {job.progress}%
                      </span>
                    ) : job.status === 'failed' ? (
                      <span className="badge badge-error" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <XCircle size={12} /> Ошибка
                      </span>
                    ) : (
                      <span className="badge badge-warning" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={12} /> В очереди
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'right' }}>
                    {job.download_url ? (
                      <a
                        href={job.download_url}
                        className="btn btn-secondary"
                        style={{ padding: '5px 10px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                      >
                        <Download size={13} />
                        Excel
                      </a>
                    ) : (
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: '#94a3b8' }}>
                    Задачи мониторинга цен еще не запускались
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
