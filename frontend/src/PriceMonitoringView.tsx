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
  Sliders,
  ShieldCheck,
  BarChart2,
  ChevronLeft,
  ChevronRight,
  Layers,
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

export function PriceMonitoringView({ onNavigateToCookies }: { onNavigateToCookies?: () => void } = {}) {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  // System Settings State
  const [defaultPriceRub, setDefaultPriceRub] = useState<number>(50)
  const [maxSuppliers, setMaxSuppliers] = useState<number>(3)
  const [maxPositions, setMaxPositions] = useState<number>(1000)
  const [concurrency, setConcurrency] = useState<number>(4)
  const [clusterRatio, setClusterRatio] = useState<number>(1.4)
  const [filterMarketplaces, setFilterMarketplaces] = useState<boolean>(false)
  const [savingSettings, setSavingSettings] = useState(false)
  const [settingsSaved, setSettingsSaved] = useState(false)

  // Clients State & Tabs & Pagination
  const [clients, setClients] = useState<ClientItem[]>([])
  const [clientSearch, setClientSearch] = useState('')
  const [clientFilterTab, setClientFilterTab] = useState<'all' | 'allowed' | 'custom'>('all')
  const [clientPage, setClientPage] = useState<number>(1)
  const [clientPageSize, setClientPageSize] = useState<number>(10)
  const [savingClientId, setSavingClientId] = useState<string | null>(null)
  const [clientEdits, setClientEdits] = useState<Record<string, { allowed: boolean; custom_price_rub: string }>>({})
  const [savedClientId, setSavedClientId] = useState<string | null>(null)

  // Jobs History State & Pagination
  const [jobs, setJobs] = useState<JobItem[]>([])
  const [jobPage, setJobPage] = useState<number>(1)
  const [jobPageSize, setJobPageSize] = useState<number>(10)

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
        setMaxSuppliers(sData.max_suppliers_per_item ?? sData.max_suppliers ?? 3)
        setMaxPositions(sData.max_positions ?? 1000)
        setConcurrency(sData.concurrency ?? 4)
        setClusterRatio(sData.cluster_ratio ?? 1.4)
        setFilterMarketplaces(sData.filter_marketplaces ?? false)
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
        body: JSON.stringify({
          default_price_rub: defaultPriceRub,
          max_suppliers_per_item: maxSuppliers,
          max_positions: maxPositions,
          concurrency,
          cluster_ratio: clusterRatio,
          filter_marketplaces: filterMarketplaces,
        }),
        credentials: 'same-origin',
      })
      if (res.ok) {
        setSettingsSaved(true)
        setTimeout(() => setSettingsSaved(false), 2500)
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

  // Filter clients by search and tab
  const filteredClients = clients.filter((c) => {
    const edit = clientEdits[c.id]
    const isAllowed = edit ? edit.allowed : c.allowed
    const hasCustom = edit ? edit.custom_price_rub.trim() !== '' : c.has_override

    if (clientFilterTab === 'allowed' && !isAllowed) return false
    if (clientFilterTab === 'custom' && !hasCustom) return false

    if (!clientSearch) return true
    const q = clientSearch.toLowerCase()
    return (
      c.name.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.telegram_id.toLowerCase().includes(q)
    )
  })

  const totalClientPages = Math.max(1, Math.ceil(filteredClients.length / clientPageSize))
  const safeClientPage = Math.min(clientPage, totalClientPages)
  const pagedClients = filteredClients.slice(
    (safeClientPage - 1) * clientPageSize,
    safeClientPage * clientPageSize
  )

  const totalJobPages = Math.max(1, Math.ceil(jobs.length / jobPageSize))
  const safeJobPage = Math.min(jobPage, totalJobPages)
  const pagedJobs = jobs.slice(
    (safeJobPage - 1) * jobPageSize,
    safeJobPage * jobPageSize
  )

  const countAllowed = clients.filter((c) => (clientEdits[c.id] ? clientEdits[c.id].allowed : c.allowed)).length
  const countCustom = clients.filter((c) =>
    clientEdits[c.id] ? clientEdits[c.id].custom_price_rub.trim() !== '' : c.has_override
  ).length

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Compact Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Coins size={22} color="#059669" />
            Мониторинг цен
          </h1>
          <div style={{ fontSize: '13px', color: '#64748b', marginTop: '2px' }}>
            Пакетный поиск цен поставщиков по спецификациям • Консенсусная кластеризация • Чекпоинты
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {onNavigateToCookies && (
            <button
              onClick={onNavigateToCookies}
              className="btn btn-secondary"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '13px' }}
              title="Перейти к управлению сессионными cookies площадок"
            >
              <ShieldCheck size={15} color="#059669" />
              <span>Куки площадок (WAF)</span>
            </button>
          )}
          <button
            onClick={loadData}
            disabled={refreshing}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '13px' }}
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Обновить
          </button>
        </div>
      </div>

      {/* KPI Stats Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        <div className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FileSpreadsheet size={20} color="#475569" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Пакетов</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>{jobs.length}</div>
          </div>
        </div>

        <div className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Layers size={20} color="#2563eb" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Строк в работе</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>{totalPositionsSum.toLocaleString('ru-RU')}</div>
          </div>
        </div>

        <div className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#ecfdf5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <BarChart2 size={20} color="#059669" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Найдено с ценой</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#059669' }}>
              {totalFoundSum.toLocaleString('ru-RU')}
              <span style={{ fontSize: '12px', fontWeight: 500, color: '#64748b', marginLeft: '6px' }}>
                ({totalPositionsSum > 0 ? Math.round((totalFoundSum / totalPositionsSum) * 100) : 0}%)
              </span>
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Coins size={20} color="#d97706" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Выручка модуля</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#b45309' }}>{totalRevenueRub.toLocaleString('ru-RU')} ₽</div>
          </div>
        </div>
      </div>

      {/* Compact Engine & Billing Settings Card */}
      <div className="card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', borderBottom: '1px solid #f1f5f9', paddingBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '15px' }}>
            <Sliders size={18} color="#2563eb" />
            Параметры поиска и тарификации
          </div>
          <button
            onClick={handleSaveSettings}
            disabled={savingSettings}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '5px 14px', fontSize: '13px' }}
          >
            {savingSettings ? <Loader2 size={14} className="animate-spin" /> : settingsSaved ? <Check size={14} /> : <Save size={14} />}
            {settingsSaved ? 'Сохранено' : 'Сохранить настройки'}
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
          {/* Base Price */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
              Базовая цена за позицию (₽)
            </label>
            <input
              type="number"
              min="0"
              step="1"
              value={defaultPriceRub}
              onChange={(e) => setDefaultPriceRub(parseFloat(e.target.value) || 0)}
              className="form-input"
              style={{ width: '100%', padding: '6px 10px', fontSize: '13px' }}
            />
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>Списание только за найденные</span>
          </div>

          {/* Max Suppliers Target */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
              Источников на единицу
            </label>
            <select
              value={maxSuppliers}
              onChange={(e) => setMaxSuppliers(parseInt(e.target.value) || 3)}
              className="form-input"
              style={{ width: '100%', padding: '6px 10px', fontSize: '13px' }}
            >
              <option value={3}>3 источника (стандарт)</option>
              <option value={4}>4 источника</option>
              <option value={5}>5 источников (максимум)</option>
            </select>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>Колонки поставщиков в Excel</span>
          </div>

          {/* Max Positions Limit */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
              Лимит строк в файле
            </label>
            <input
              type="number"
              min="50"
              max="5000"
              step="50"
              value={maxPositions}
              onChange={(e) => setMaxPositions(parseInt(e.target.value) || 1000)}
              className="form-input"
              style={{ width: '100%', padding: '6px 10px', fontSize: '13px' }}
            />
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>Защита от перерасхода баланса</span>
          </div>

          {/* Concurrency */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
              Параллелизм обработки
            </label>
            <select
              value={concurrency}
              onChange={(e) => setConcurrency(parseInt(e.target.value) || 4)}
              className="form-input"
              style={{ width: '100%', padding: '6px 10px', fontSize: '13px' }}
            >
              <option value={2}>2 потока (щадящий)</option>
              <option value={4}>4 потока (рекомендуемый)</option>
              <option value={6}>6 потоков (скоростной)</option>
            </select>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>С учетом лимитов CPU и WAF</span>
          </div>

          {/* Cluster Ratio */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
              Разброс цен (кластер)
            </label>
            <select
              value={clusterRatio}
              onChange={(e) => setClusterRatio(parseFloat(e.target.value) || 1.4)}
              className="form-input"
              style={{ width: '100%', padding: '6px 10px', fontSize: '13px' }}
            >
              <option value={1.3}>до +30% (строгий консенсус)</option>
              <option value={1.4}>до +40% (оптимальный, по умолчанию)</option>
              <option value={1.5}>до +50% (умеренный)</option>
              <option value={1.6}>до +60% (расширенный)</option>
            </select>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>Отсекает выбросы выше порога от мин.</span>
          </div>

          {/* Marketplaces Filter Toggle */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '4px' }}>
              Фильтр маркетплейсов
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', height: '34px' }}>
              <input
                type="checkbox"
                checked={filterMarketplaces}
                onChange={(e) => setFilterMarketplaces(e.target.checked)}
                style={{ width: '16px', height: '16px', accentColor: '#2563eb' }}
              />
              <span style={{ fontSize: '13px', color: '#334155' }}>Исключать Ozon, WB, Avito</span>
            </label>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>По умолчанию выключено (все площадки включены)</span>
          </div>
        </div>
      </div>

      {/* Client Access & Overrides */}
      <div className="card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, fontSize: '15px' }}>
              <Users size={18} color="#059669" />
              Клиенты и персональные цены
            </div>

            {/* Quick Filter Tabs */}
            <div style={{ display: 'flex', gap: '4px', background: '#f1f5f9', padding: '3px', borderRadius: '6px' }}>
              <button
                type="button"
                onClick={() => {
                  setClientFilterTab('all')
                  setClientPage(1)
                }}
                style={{
                  padding: '3px 8px',
                  fontSize: '12px',
                  fontWeight: 500,
                  borderRadius: '4px',
                  border: 'none',
                  cursor: 'pointer',
                  background: clientFilterTab === 'all' ? '#ffffff' : 'transparent',
                  color: clientFilterTab === 'all' ? '#0f172a' : '#64748b',
                  boxShadow: clientFilterTab === 'all' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                }}
              >
                Все ({clients.length})
              </button>
              <button
                type="button"
                onClick={() => {
                  setClientFilterTab('allowed')
                  setClientPage(1)
                }}
                style={{
                  padding: '3px 8px',
                  fontSize: '12px',
                  fontWeight: 500,
                  borderRadius: '4px',
                  border: 'none',
                  cursor: 'pointer',
                  background: clientFilterTab === 'allowed' ? '#ffffff' : 'transparent',
                  color: clientFilterTab === 'allowed' ? '#059669' : '#64748b',
                  boxShadow: clientFilterTab === 'allowed' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                }}
              >
                С доступом ({countAllowed})
              </button>
              <button
                type="button"
                onClick={() => {
                  setClientFilterTab('custom')
                  setClientPage(1)
                }}
                style={{
                  padding: '3px 8px',
                  fontSize: '12px',
                  fontWeight: 500,
                  borderRadius: '4px',
                  border: 'none',
                  cursor: 'pointer',
                  background: clientFilterTab === 'custom' ? '#ffffff' : 'transparent',
                  color: clientFilterTab === 'custom' ? '#2563eb' : '#64748b',
                  boxShadow: clientFilterTab === 'custom' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                }}
              >
                С индив. ценой ({countCustom})
              </button>
            </div>
          </div>

          <div style={{ position: 'relative', width: '240px' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '9px', color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="Поиск клиента..."
              value={clientSearch}
              onChange={(e) => {
                setClientSearch(e.target.value)
                setClientPage(1)
              }}
              className="form-input"
              style={{ paddingLeft: '30px', paddingRight: '10px', paddingTop: '5px', paddingBottom: '5px', width: '100%', fontSize: '13px' }}
            />
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b', textAlign: 'left', background: '#f8fafc' }}>
                <th style={{ padding: '8px 12px' }}>Клиент / Реквизиты</th>
                <th style={{ padding: '8px 12px' }}>Баланс</th>
                <th style={{ padding: '8px 12px' }}>Доступ к модулю</th>
                <th style={{ padding: '8px 12px' }}>Цена за позицию (₽)</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Действие</th>
              </tr>
            </thead>
            <tbody>
              {pagedClients.map((client) => {
                const edit = clientEdits[client.id] || { allowed: client.allowed, custom_price_rub: '' }
                const isSaving = savingClientId === client.id
                const isSaved = savedClientId === client.id

                return (
                  <tr key={client.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ fontWeight: 600, color: '#0f172a' }}>{client.name}</div>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>
                        {client.email || (client.telegram_id ? `TG: ${client.telegram_id}` : client.id.slice(0, 8))}
                      </div>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ fontWeight: 600, color: client.balance_rub > 500 ? '#059669' : '#dc2626' }}>
                        {client.balance_rub.toLocaleString('ru-RU')} ₽
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={edit.allowed}
                          onChange={(e) =>
                            setClientEdits((prev) => ({
                              ...prev,
                              [client.id]: { ...edit, allowed: e.target.checked },
                            }))
                          }
                          style={{ width: '15px', height: '15px', accentColor: '#059669' }}
                        />
                        <span style={{ fontSize: '12px', fontWeight: 500, color: edit.allowed ? '#059669' : '#94a3b8' }}>
                          {edit.allowed ? 'Включен' : 'Отключен'}
                        </span>
                      </label>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <input
                        type="number"
                        placeholder={`${defaultPriceRub} ₽`}
                        value={edit.custom_price_rub}
                        onChange={(e) =>
                          setClientEdits((prev) => ({
                            ...prev,
                            [client.id]: { ...edit, custom_price_rub: e.target.value },
                          }))
                        }
                        className="form-input"
                        style={{ width: '110px', padding: '5px 8px', fontSize: '13px' }}
                      />
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                      <button
                        onClick={() => handleSaveClient(client.id)}
                        disabled={isSaving}
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      >
                        {isSaving ? <Loader2 size={12} className="animate-spin" /> : isSaved ? <Check size={12} color="#059669" /> : <Save size={12} />}
                        {isSaved ? 'Ок' : 'Сохранить'}
                      </button>
                    </td>
                  </tr>
                )
              })}
              {filteredClients.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: '20px', textAlign: 'center', color: '#94a3b8' }}>
                    Клиенты не найдены
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Client Pagination Controls */}
        {filteredClients.length > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #f1f5f9', fontSize: '12px', color: '#64748b' }}>
            <div>
              Показано {(safeClientPage - 1) * clientPageSize + 1}–{Math.min(safeClientPage * clientPageSize, filteredClients.length)} из {filteredClients.length} клиентов
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <select
                value={clientPageSize}
                onChange={(e) => {
                  setClientPageSize(Number(e.target.value))
                  setClientPage(1)
                }}
                className="form-input"
                style={{ padding: '2px 6px', fontSize: '11px', height: '26px' }}
              >
                <option value={5}>5 на стр.</option>
                <option value={10}>10 на стр.</option>
                <option value={20}>20 на стр.</option>
              </select>
              <button
                type="button"
                onClick={() => setClientPage((p) => Math.max(1, p - 1))}
                disabled={safeClientPage <= 1}
                className="btn btn-secondary"
                style={{ padding: '2px 6px', height: '26px', display: 'flex', alignItems: 'center' }}
                title="Предыдущая страница"
              >
                <ChevronLeft size={14} />
              </button>
              <span style={{ fontWeight: 500, fontSize: '11px' }}>
                {safeClientPage} / {totalClientPages}
              </span>
              <button
                type="button"
                onClick={() => setClientPage((p) => Math.min(totalClientPages, p + 1))}
                disabled={safeClientPage >= totalClientPages}
                className="btn btn-secondary"
                style={{ padding: '2px 6px', height: '26px', display: 'flex', alignItems: 'center' }}
                title="Следующая страница"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Jobs History Table */}
      <div className="card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '15px' }}>
            <FileSpreadsheet size={18} color="#0284c7" />
            История запусков ({jobs.length})
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b', textAlign: 'left', background: '#f8fafc' }}>
                <th style={{ padding: '8px 12px' }}>№ Задачи</th>
                <th style={{ padding: '8px 12px' }}>Клиент</th>
                <th style={{ padding: '8px 12px' }}>Спецификация</th>
                <th style={{ padding: '8px 12px' }}>Строк</th>
                <th style={{ padding: '8px 12px' }}>Найдено</th>
                <th style={{ padding: '8px 12px' }}>Списано</th>
                <th style={{ padding: '8px 12px' }}>Статус</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Отчет</th>
              </tr>
            </thead>
            <tbody>
              {pagedJobs.map((job) => (
                <tr key={job.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ fontWeight: 600, color: '#334155' }}>#{job.job_number || job.id.slice(0, 6)}</span>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                      {job.created_at ? new Date(job.created_at).toLocaleString('ru-RU') : '—'}
                    </div>
                  </td>
                  <td style={{ padding: '10px 12px', fontWeight: 500 }}>{job.client_name}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ fontWeight: 500, color: '#0f172a' }}>{job.title}</div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>{job.message}</div>
                  </td>
                  <td style={{ padding: '10px 12px', fontWeight: 600 }}>{job.total_positions || '—'}</td>
                  <td style={{ padding: '10px 12px', fontWeight: 600, color: job.found_positions > 0 ? '#059669' : '#64748b' }}>
                    {job.found_positions}
                  </td>
                  <td style={{ padding: '10px 12px', fontWeight: 600, color: job.charged_rub > 0 ? '#2563eb' : '#64748b' }}>
                    {job.charged_rub.toLocaleString('ru-RU')} ₽
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    {job.status === 'completed' ? (
                      <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
                        <CheckCircle2 size={11} /> Готово
                      </span>
                    ) : job.status === 'running' ? (
                      <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
                        <Loader2 size={11} className="animate-spin" /> {job.progress}%
                      </span>
                    ) : job.status === 'failed' ? (
                      <span className="badge badge-error" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
                        <XCircle size={11} /> Ошибка
                      </span>
                    ) : (
                      <span className="badge badge-warning" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
                        <Clock size={11} /> Очередь
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                    {job.download_url ? (
                      <a
                        href={job.download_url}
                        className="btn btn-secondary"
                        style={{ padding: '4px 8px', fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      >
                        <Download size={12} />
                        Excel
                      </a>
                    ) : (
                      <span style={{ fontSize: '11px', color: '#94a3b8' }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ padding: '20px', textAlign: 'center', color: '#94a3b8' }}>
                    Задачи мониторинга цен еще не запускались
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Jobs Pagination Controls */}
        {jobs.length > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #f1f5f9', fontSize: '12px', color: '#64748b' }}>
            <div>
              Показано {(safeJobPage - 1) * jobPageSize + 1}–{Math.min(safeJobPage * jobPageSize, jobs.length)} из {jobs.length} задач
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <select
                value={jobPageSize}
                onChange={(e) => {
                  setJobPageSize(Number(e.target.value))
                  setJobPage(1)
                }}
                className="form-input"
                style={{ padding: '2px 6px', fontSize: '11px', height: '26px' }}
              >
                <option value={5}>5 на стр.</option>
                <option value={10}>10 на стр.</option>
                <option value={20}>20 на стр.</option>
              </select>
              <button
                type="button"
                onClick={() => setJobPage((p) => Math.max(1, p - 1))}
                disabled={safeJobPage <= 1}
                className="btn btn-secondary"
                style={{ padding: '2px 6px', height: '26px', display: 'flex', alignItems: 'center' }}
                title="Предыдущая страница"
              >
                <ChevronLeft size={14} />
              </button>
              <span style={{ fontWeight: 500, fontSize: '11px' }}>
                {safeJobPage} / {totalJobPages}
              </span>
              <button
                type="button"
                onClick={() => setJobPage((p) => Math.min(totalJobPages, p + 1))}
                disabled={safeJobPage >= totalJobPages}
                className="btn btn-secondary"
                style={{ padding: '2px 6px', height: '26px', display: 'flex', alignItems: 'center' }}
                title="Следующая страница"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}


