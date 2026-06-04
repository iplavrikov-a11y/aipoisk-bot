import { useEffect, useMemo, useState } from 'react'
import {
  Bot,
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Cpu,
  Database,
  Download,
  FileText,
  HardDrive,
  KeyRound,
  Loader2,
  LogIn,
  MemoryStick,
  Play,
  Plus,
  RefreshCw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  XCircle,
} from 'lucide-react'

type View = 'dashboard' | 'clients' | 'jobs' | 'quality' | 'settings' | 'ai'

type Dashboard = {
  clients: number
  active_clients: number
  jobs: number
  running_jobs: number
  completed_jobs: number
  failed_jobs: number
  suppliers: number
}

type Client = {
  id: string
  telegram_id: string
  name: string
  username: string
  is_active: boolean
  is_trial: boolean
  access_until: string
  allowed_supplier_search: boolean
  allowed_procurement_report: boolean
  monthly_job_limit: number
  monthly_supplier_search_limit: number
  monthly_procurement_report_limit: number
  monthly_file_limit: number
  notes: string
  telegram_accounts: TelegramAccount[]
  usage: ClientUsage | null
  recent_usage: UsageEntry[]
}

type ClientUsage = {
  supplier_search: UsageCounter
  procurement_report: UsageCounter
}

type UsageCounter = {
  label: string
  used: number
  limit: number
  remaining: number | null
  unlimited: boolean
  percent: number
}

type UsageEntry = {
  id: string
  mode: string
  mode_label: string
  human_title: string
  created_by_telegram_id: string
  supplier_units: number
  procurement_report_units: number
  status: string
  created_at: string | null
}

type TelegramAccount = {
  id: string
  client_id: string
  telegram_id: string
  username: string
  name: string
  is_active: boolean
  notes: string
}

type Job = {
  id: string
  client_name: string
  telegram_id: string
  created_by_telegram_id: string
  mode: string
  mode_label: string
  status: string
  progress: number
  message: string
  title: string
  human_title: string
  is_internal: boolean
  supplier_units: number
  procurement_report_units: number
  target_suppliers: number
  verified_count: number
  file_count: number
  has_result: boolean
  error: string
  created_at: string
}

type SettingsPayload = {
  public_base_url: string
  storage_retention_days: number
  completed_job_retention_days: number
  failed_job_retention_days: number
  max_upload_mb: number
  max_files_per_batch: number
  default_supplier_target: number
  allow_partial_supplier_reports: boolean
  logistics_enabled: boolean
  trial_enabled: boolean
  trial_supplier_search_limit: number
  trial_procurement_report_limit: number
  trial_file_limit: number
  primary_provider: string
  primary_model: string
  light_provider: string
  light_model: string
  custom_ai_providers_json: string
  saved_models_json: string
  ai_function_models_json: string
  supplier_search_adapter_base_url: string
  supplier_search_adapter_api_key_set: boolean
  supplier_search_adapter_model: string
  supplier_search_provider_order: string
  yandex_search_folder_id: string
  yandex_search_api_key_set: boolean
  google_search_api_key_set: boolean
  google_search_cse_id: string
  prompt_settings_json: string
  report_settings_json: string
  document_settings_json: string
  bot_messages_json: string
  supplier_search_ui: SupplierSearchUi
}

type SupplierSearchUi = {
  active_provider: string
  active_label: string
  active_note: string
  has_active_source: boolean
  provider_order: string[]
  technical_sources: Array<{
    id: string
    label: string
    configured: boolean
    active: boolean
    status_label: string
  }>
}

type SupplierQualitySnapshot = {
  window_size: number
  status_counts: Record<string, number>
  average_verified_count: number
  average_duration_seconds: number
  underfilled_terminal_jobs: number
  ai_required_failures: number
  provider_status_counts: Record<string, Record<string, number>>
  alerts: Array<{ severity: string; code: string; message: string }>
  recent_failures: Array<{
    id: string
    title: string
    error: string
    ai_required: boolean
    stage: string
    created_at: string | null
  }>
}

type OpsStatus = {
  status: string
  updated_at: string
  server: {
    disk_total_gb: number
    disk_used_gb: number
    disk_free_gb: number
    disk_percent: number
    cpu_percent: number
    ram_total_gb: number
    ram_used_gb: number
    ram_percent: number
    storage_free_gb: number
    storage_used_gb: number
    storage_percent: number
  }
  queue: {
    pending: number
    running: number
    failed: number
    completed: number
  }
  services: Array<{
    id: string
    label: string
    detail: string
    configured: boolean
    status: string
    status_label: string
    balance_label: string
    note: string
  }>
  warnings: string[]
}

type CustomProvider = {
  id: string
  name: string
  baseUrl: string
  apiKey: string
  model?: string
  primaryModel?: string
  lightModel?: string
}

type SavedModel = {
  id: string
  name: string
  provider: string
  modelId: string
}

const apiBase = ''
const aiRoutingKeys = [
  'procurement_document_analysis',
  'procurement_report_verification',
  'procurement_key_info_extraction',
  'procurement_search_query_generation',
  'supplier_query_generation',
  'supplier_candidate_verifier',
]

const viewCopy: Record<View, { title: string; description: string }> = {
  dashboard: {
    title: 'Сводка',
    description: 'Короткая картина по клиентам, задачам и текущим настройкам сервиса.',
  },
  clients: {
    title: 'Клиенты',
    description: 'Клиенты, менеджеры в Telegram, доступы и два коммерческих лимита: поставщики и анализ.',
  },
  jobs: {
    title: 'Задачи',
    description: 'Последние запуски бота, статусы обработки и готовые файлы для скачивания.',
  },
  quality: {
    title: 'Контроль отчётов',
    description: 'Понятный мониторинг: где отчёты не собрались, где мало поставщиков и какие источники поиска сработали.',
  },
  settings: {
    title: 'Настройки',
    description: 'Бесплатный период, хранение файлов и поиск поставщиков.',
  },
  ai: {
    title: 'ИИ-модели',
    description: 'Выбор моделей для анализа документации, поиска поставщиков и проверки результатов.',
  },
}

const modeLabels: Record<string, string> = {
  supplier_search: 'Поиск поставщиков',
  procurement_report: 'Анализ документации',
  analysis_and_suppliers: 'Анализ + поставщики',
}

const statusLabels: Record<string, string> = {
  active: 'включён',
  disabled: 'выключен',
  trial: 'бесплатный период',
  pending: 'в очереди',
  running: 'в работе',
  completed: 'готово',
  partial: 'частично готово',
  needs_review: 'нужна проверка',
  failed: 'ошибка',
}

const providerLabels: Record<string, string> = {
  yandex: 'Яндекс Поиск',
  google: 'Google Поиск',
  tavily: 'Tavily',
  ddgs: 'DuckDuckGo',
}

const providerStatusLabels: Record<string, string> = {
  ok: 'успешно',
  empty: 'пусто',
  failed: 'ошибка',
  skipped: 'пропущено',
}

const supplierProviderPriority = ['yandex', 'google', 'tavily', 'ddgs']

const alertTitles: Record<string, string> = {
  ai_required_failures: 'ИИ-проверка сорвалась',
  underfilled_reports: 'Мало поставщиков в отчёте',
  slow_supplier_jobs: 'Долгая обработка',
  search_provider_no_ok: 'Источник поиска не дал результатов',
  supplier_failure_rate: 'Много ошибок по отчётам',
}

const functionLabels: Record<string, string> = {
  procurement_document_analysis: 'Анализ документации',
  procurement_report_verification: 'Проверка отчёта анализа',
  procurement_key_info_extraction: 'Извлечение условий закупки',
  procurement_search_query_generation: 'Запросы по закупке',
  supplier_query_generation: 'Запросы для поиска поставщиков',
  supplier_candidate_verifier: 'Проверка поставщиков',
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json() as Promise<T>
}

function formatError(err: unknown) {
  const message = err instanceof Error ? err.message : String(err || '')
  if (message.includes('Invalid login or password') || message.includes('401')) {
    return 'Неверный логин или пароль.'
  }
  if (message.includes('Too many login attempts') || message.includes('429')) {
    return 'Слишком много попыток входа. Подождите несколько минут и попробуйте снова.'
  }
  return message || 'Ошибка загрузки'
}

function supplierCountLabel(job: Job) {
  return `${job.verified_count}`
}

function parseJson<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value || '') as T
  } catch {
    return fallback
  }
}

function stringify(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function canonicalProviderName(providerId: string) {
  const normalized = String(providerId || '').trim().toLowerCase()
  const names: Record<string, string> = {
    openrouter: 'OpenRouter',
    'open-router': 'OpenRouter',
    openai: 'OpenAI',
    'open-ai': 'OpenAI',
    gemini: 'Gemini',
    google: 'Gemini',
    polza: 'Polza',
  }
  return names[normalized] || providerId || 'Custom provider'
}

function defaultProviderBaseUrl(providerId: string) {
  const normalized = String(providerId || '').trim().toLowerCase()
  const urls: Record<string, string> = {
    openrouter: 'https://openrouter.ai/api/v1',
    'open-router': 'https://openrouter.ai/api/v1',
    polza: 'https://api.polza.ai/v1',
  }
  return urls[normalized] || ''
}

function normalizeProviderBaseUrl(providerId: string, baseUrl: string) {
  const normalizedProviderId = String(providerId || '').trim().toLowerCase()
  const raw = String(baseUrl || '').trim()
  const fallback = defaultProviderBaseUrl(normalizedProviderId)
  if (!fallback) return raw
  if (!raw || !/^https?:\/\//i.test(raw)) return fallback
  try {
    const parsed = new URL(raw)
    const host = parsed.hostname.toLowerCase()
    if (host.includes('lexelence')) return fallback
    if (normalizedProviderId === 'openrouter' && host === 'openrouter.ai' && parsed.pathname.replace(/\/$/, '') !== '/api/v1') {
      return fallback
    }
  } catch {
    return fallback
  }
  return raw
}

function normalizeProvider(provider: CustomProvider): CustomProvider {
  const id = String(provider.id || '').trim()
  const canonicalName = canonicalProviderName(id)
  const isKnownProvider = canonicalName !== (id || 'Custom provider')
  return {
    ...provider,
    id,
    name: isKnownProvider ? canonicalName : String(provider.name || canonicalName).trim(),
    baseUrl: normalizeProviderBaseUrl(id, provider.baseUrl || ''),
    apiKey: provider.apiKey || '',
  }
}

function ensureModelProviders(providers: CustomProvider[], models: SavedModel[]) {
  const orderedIds = ['openrouter', 'open-ai', 'gemini']
  for (const model of models) {
    const providerId = String(model.provider || '').trim()
    if (providerId && !orderedIds.includes(providerId)) orderedIds.push(providerId)
  }

  const result = new Map<string, CustomProvider>()
  for (const provider of providers) {
    const normalized = normalizeProvider(provider)
    if (normalized.id) result.set(normalized.id, normalized)
  }
  for (const id of orderedIds) {
    if (!result.has(id)) {
      result.set(id, { id, name: canonicalProviderName(id), baseUrl: defaultProviderBaseUrl(id), apiKey: '', model: '' })
    }
  }
  return [
    ...orderedIds.map(id => result.get(id)).filter((provider): provider is CustomProvider => Boolean(provider)),
    ...Array.from(result.values()).filter(provider => !orderedIds.includes(provider.id)),
  ]
}

function humanStatus(status: string) {
  return statusLabels[status] || status || 'неизвестно'
}

function humanMode(mode: string) {
  return modeLabels[mode] || mode || 'Задача'
}

function humanProvider(provider: string) {
  return providerLabels[provider] || provider || 'Источник'
}

function humanProviderStatus(status: string) {
  return providerStatusLabels[status] || status || 'статус'
}

function humanStage(stage: string) {
  return humanMode(stage)
}

function humanAlertTitle(code: string) {
  return alertTitles[code] || code
}

function humanAlertMessage(alert: { code: string; message: string }) {
  const message = alert.message || ''
  if (alert.code === 'ai_required_failures') {
    const count = message.match(/\d+/)?.[0] || ''
    return `ИИ не смог надёжно проверить ${count || 'несколько'} отчёта. Такие задачи нужно посмотреть вручную.`
  }
  if (alert.code === 'underfilled_reports') {
    const count = message.match(/\d+/)?.[0] || ''
    return `${count || 'Есть'} отчёта с меньшим количеством поставщиков, чем планировалось.`
  }
  if (alert.code === 'slow_supplier_jobs') {
    const seconds = message.match(/[\d.]+/)?.[0]
    return `Средняя обработка поиска поставщиков занимает ${seconds ? `${Math.round(Number(seconds) / 60)} мин` : 'слишком долго'}.`
  }
  if (alert.code === 'search_provider_no_ok') {
    const provider = Object.keys(providerLabels).find(item => message.toLowerCase().includes(item))
    return `${provider ? humanProvider(provider) : 'Один из источников'} не дал успешных результатов в текущем окне.`
  }
  return message
}

function friendlyError(error: string) {
  const lowered = String(error || '').toLowerCase()
  if (!lowered) return 'Причина не записана.'
  if (lowered.includes('candidate reranking') || lowered.includes('reranker')) {
    return 'ИИ не смог надёжно отобрать подходящие сайты поставщиков.'
  }
  if (lowered.includes('supplier query generation')) {
    return 'ИИ не смог подготовить поисковые запросы для поставщиков.'
  }
  if (lowered.includes('ai provider') || lowered.includes('timeout') || lowered.includes('timed out')) {
    return 'В момент обработки был недоступен ИИ-провайдер.'
  }
  if (lowered.includes('did not keep any candidates')) {
    return 'После проверки не осталось подходящих поставщиков.'
  }
  return error
}

function providerStatusSummary(counts: Record<string, number>) {
  return Object.entries(counts)
    .map(([status, count]) => `${humanProviderStatus(status)}: ${count}`)
    .join(', ')
}

function sortSupplierProviders<T>(entries: Array<[string, T]>) {
  return entries.sort(([left], [right]) => providerPriority(left) - providerPriority(right) || left.localeCompare(right))
}

function providerPriority(provider: string) {
  const index = supplierProviderPriority.indexOf(provider)
  return index >= 0 ? index : supplierProviderPriority.length
}

function formatDuration(seconds: number) {
  const safeSeconds = Math.max(0, Math.round(seconds || 0))
  const minutes = Math.round(safeSeconds / 60)
  return minutes >= 1 ? `${minutes} мин` : `${safeSeconds} сек`
}

function formatDate(value: string | null | undefined) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16)
  return date.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}

export function App() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authenticated, setAuthenticated] = useState(false)
  const [view, setView] = useState<View>('dashboard')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [quality, setQuality] = useState<SupplierQualitySnapshot | null>(null)
  const [opsStatus, setOpsStatus] = useState<OpsStatus | null>(null)
  const [settings, setSettings] = useState<SettingsPayload | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const isReady = authenticated
  const canLogin = username.trim().length > 0 && password.length > 0

  async function loadAll(force = false) {
    if (!force && !authenticated) return
    setLoading(true)
    setError('')
    try {
      const [dashboardData, clientsData, jobsData, qualityData, opsStatusData, settingsData] = await Promise.all([
        api<Dashboard>('/api/dashboard'),
        api<Client[]>('/api/clients'),
        api<Job[]>('/api/jobs?include_internal=true'),
        api<SupplierQualitySnapshot>('/api/ops/supplier-quality'),
        api<OpsStatus>('/api/ops/system-status'),
        api<SettingsPayload>('/api/settings'),
      ])
      setDashboard(dashboardData)
      setClients(clientsData)
      setJobs(jobsData)
      setQuality(qualityData)
      setOpsStatus(opsStatusData)
      setSettings(settingsData)
    } catch (err) {
      setError(formatError(err))
    } finally {
      setLoading(false)
    }
  }

  async function login() {
    setLoading(true)
    setError('')
    try {
      await api<{ ok: boolean; username: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      localStorage.removeItem('aipoisk_admin_token')
      setPassword('')
      setAuthenticated(true)
      await loadAll(true)
    } catch (err) {
      setAuthenticated(false)
      setError(formatError(err))
    } finally {
      setLoading(false)
    }
  }

  async function logout() {
    await api('/api/auth/logout', { method: 'POST' }).catch(() => undefined)
    setAuthenticated(false)
    setDashboard(null)
    setClients([])
    setJobs([])
    setQuality(null)
    setOpsStatus(null)
    setSettings(null)
    setUsername('')
    setPassword('')
  }

  useEffect(() => {
    void api<{ ok: boolean }>('/api/auth/session')
      .then(result => {
        if (!result.ok) return
        setAuthenticated(true)
        return loadAll(true)
      })
      .catch(() => setAuthenticated(false))
  }, [])

  const nav = [
    { id: 'dashboard' as const, label: 'Сводка', icon: ShieldCheck },
    { id: 'clients' as const, label: 'Клиенты', icon: Users },
    { id: 'jobs' as const, label: 'Задачи', icon: FileText },
    { id: 'quality' as const, label: 'Контроль', icon: CheckCircle2 },
    { id: 'settings' as const, label: 'Настройки', icon: SlidersHorizontal },
    { id: 'ai' as const, label: 'ИИ', icon: BrainCircuit },
  ]

  if (!authenticated) {
    return (
      <AuthScreen
        username={username}
        password={password}
        loading={loading}
        canLogin={canLogin}
        error={error}
        onUsername={setUsername}
        onPassword={setPassword}
        onSubmit={login}
      />
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Search size={18} /></div>
          <div>
            <div className="brand-name">AI Поиск</div>
            <div className="brand-sub">aipoisk.lexelence.ru</div>
          </div>
        </div>
        <nav className="nav">
          {nav.map(item => {
            const Icon = item.icon
            return (
              <button key={item.id} className={view === item.id ? 'nav-item active' : 'nav-item'} onClick={() => setView(item.id)}>
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{viewCopy[view].title}</h1>
            <p>{viewCopy[view].description}</p>
          </div>
          <div className="top-actions">
            <span className="session-label">Вход выполнен</span>
            <button className="login-button" onClick={() => void loadAll()} disabled={loading}>
              {loading ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />}
              Обновить
            </button>
            <button className="secondary" onClick={() => void logout()}>Выйти</button>
          </div>
        </header>

        {error && <div className="alert error"><XCircle size={18} />{error}</div>}
        {isReady && view === 'dashboard' && <DashboardView dashboard={dashboard} settings={settings} opsStatus={opsStatus} />}
        {isReady && view === 'clients' && <ClientsView clients={clients} onChange={loadAll} />}
        {isReady && view === 'jobs' && <JobsView jobs={jobs} onChange={loadAll} />}
        {isReady && view === 'quality' && <QualityView quality={quality} />}
        {isReady && view === 'settings' && settings && <SettingsView settings={settings} onChange={loadAll} />}
        {isReady && view === 'ai' && settings && <AiView settings={settings} onChange={loadAll} />}
      </main>
    </div>
  )
}

function AuthScreen({
  username,
  password,
  loading,
  canLogin,
  error,
  onUsername,
  onPassword,
  onSubmit,
}: {
  username: string
  password: string
  loading: boolean
  canLogin: boolean
  error: string
  onUsername: (value: string) => void
  onPassword: (value: string) => void
  onSubmit: () => Promise<void>
}) {
  return (
    <main className="auth-shell">
      <form className="login-card" onSubmit={event => { event.preventDefault(); void onSubmit() }}>
        <div className="login-mark"><Search size={22} /></div>
        <h1>Вход</h1>
        <p>Введите логин и пароль</p>
        {error && <div className="alert error compact"><XCircle size={18} />{error}</div>}
        <label className="field">
          <span>Логин</span>
          <input
            aria-label="Логин"
            placeholder="Логин"
            autoComplete="username"
            value={username}
            onChange={event => onUsername(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Пароль</span>
          <input
            type="password"
            aria-label="Пароль"
            placeholder="Пароль"
            autoComplete="current-password"
            value={password}
            onChange={event => onPassword(event.target.value)}
          />
        </label>
        <button className="login-button full-width" type="submit" disabled={!canLogin || loading}>
          {loading ? <Loader2 className="spin" size={18} /> : <LogIn size={18} />}
          Войти
        </button>
      </form>
    </main>
  )
}

function DashboardView({ dashboard, settings, opsStatus }: { dashboard: Dashboard | null; settings: SettingsPayload | null; opsStatus: OpsStatus | null }) {
  const stats = [
    { label: 'Клиентов', value: dashboard?.clients ?? 0, note: `${dashboard?.active_clients ?? 0} активных`, icon: Users },
    { label: 'Задач', value: dashboard?.jobs ?? 0, note: `${dashboard?.running_jobs ?? 0} в работе`, icon: FileText },
    { label: 'Готово', value: dashboard?.completed_jobs ?? 0, note: `${dashboard?.failed_jobs ?? 0} ошибок`, icon: CheckCircle2 },
    { label: 'Поставщиков', value: dashboard?.suppliers ?? 0, note: 'проверенных строк', icon: Search },
  ]
  return (
    <section className="content-grid">
      {stats.map(item => {
        const Icon = item.icon
        return (
          <div className="metric" key={item.label}>
            <Icon size={20} />
            <div>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.note}</small>
            </div>
          </div>
        )
      })}
      <SystemStatusPanel opsStatus={opsStatus} />
      <div className="wide-panel">
        <h2>Рабочие правила</h2>
        <div className="rule-list">
          <div><Bot size={17} />В боте работают только включённые клиенты и их менеджеры.</div>
          <div><Search size={17} />В отчёт попадают только поставщики, проверенные ИИ.</div>
          <div><Settings size={17} />Лимиты задаются вручную: отдельно поиск поставщиков и анализ документации.</div>
          <div><KeyRound size={17} />Модели ИИ выбираются в разделе «ИИ-модели».</div>
        </div>
      </div>
      <div className="wide-panel">
        <h2>Текущая конфигурация</h2>
        <div className="settings-summary">
          <span>Домен: {settings?.public_base_url || 'не задан'}</span>
          <span>Минимум поставщиков: {settings?.default_supplier_target || 15}</span>
          <span>Логистика: {settings?.logistics_enabled ? 'включена' : 'отключена'}</span>
          <span>Частичные отчёты: {settings?.allow_partial_supplier_reports ? 'разрешены' : 'запрещены'}</span>
          <span>Бесплатный период: {settings?.trial_enabled ? 'включён' : 'выключен'}</span>
        </div>
      </div>
    </section>
  )
}

function SystemStatusPanel({ opsStatus }: { opsStatus: OpsStatus | null }) {
  if (!opsStatus) {
    return <div className="form-panel full-width-panel"><h2>Состояние системы</h2><div className="empty inline-empty">Данные состояния пока не загружены.</div></div>
  }
  const serverMetrics = [
    { label: 'CPU', value: `${opsStatus.server.cpu_percent}%`, note: 'нагрузка процессора', icon: Cpu, warning: opsStatus.server.cpu_percent >= 85 },
    { label: 'RAM', value: `${opsStatus.server.ram_percent}%`, note: `${opsStatus.server.ram_used_gb}/${opsStatus.server.ram_total_gb} ГБ`, icon: MemoryStick, warning: opsStatus.server.ram_percent >= 85 },
    { label: 'SSD', value: `${Math.floor(opsStatus.server.disk_free_gb)} ГБ`, note: `свободно, занято ${opsStatus.server.disk_percent}%`, icon: HardDrive, warning: opsStatus.server.disk_free_gb < 10 },
    { label: 'Хранилище', value: `${opsStatus.server.storage_percent}%`, note: `${opsStatus.server.storage_used_gb} ГБ занято`, icon: Database, warning: opsStatus.server.storage_percent >= 90 },
    { label: 'Очередь', value: `${opsStatus.queue.pending}`, note: `${opsStatus.queue.running} в работе`, icon: Server, warning: opsStatus.queue.pending >= 50 },
  ]
  return (
    <div className="form-panel full-width-panel system-status-panel">
      <div className="panel-heading">
        <h2>Состояние системы и сервисов</h2>
        <span className={opsStatus.status === 'warning' ? 'status warning' : 'status active'}>
          {opsStatus.status === 'warning' ? 'требует внимания' : 'в норме'}
        </span>
      </div>
      <div className="system-metrics-grid">
        {serverMetrics.map(item => {
          const Icon = item.icon
          return (
            <div className={item.warning ? 'system-metric warning' : 'system-metric'} key={item.label}>
              <Icon size={17} />
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.note}</small>
            </div>
          )
        })}
      </div>
      {opsStatus.warnings.length > 0 && (
        <div className="warning-list">
          {opsStatus.warnings.map(item => <div key={item}>{item}</div>)}
        </div>
      )}
      <div className="api-service-list">
        {opsStatus.services.map(service => (
          <div className={service.configured ? 'api-service-row configured' : 'api-service-row'} key={service.id}>
            <div>
              <strong>{service.label}</strong>
              <small>{service.detail} · {service.note}</small>
            </div>
            <div>
              <span>{service.status_label}</span>
              <small>{service.balance_label}</small>
            </div>
          </div>
        ))}
      </div>
      <p className="field-help">Балансы не подставляются фиктивно: здесь показан факт подключения сервисов и состояние сервера. Реальные суммы можно добавить только через подтверждённые billing API.</p>
    </div>
  )
}

function ClientsView({ clients, onChange }: { clients: Client[]; onChange: () => Promise<void> }) {
  const [form, setForm] = useState({ telegram_id: '', name: '', username: '', notes: '' })
  const [accountForms, setAccountForms] = useState<Record<string, { telegram_id: string; username: string; name: string }>>({})
  const [expandedClients, setExpandedClients] = useState<Record<string, boolean>>({})
  async function createClient() {
    await api('/api/clients', { method: 'POST', body: JSON.stringify(form) })
    setForm({ telegram_id: '', name: '', username: '', notes: '' })
    await onChange()
  }
  async function patchClient(client: Client, patch: Partial<Client>) {
    await api(`/api/clients/${client.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
    await onChange()
  }
  async function createAccount(client: Client) {
    const draft = accountForms[client.id] || { telegram_id: '', username: '', name: '' }
    await api(`/api/clients/${client.id}/telegram-accounts`, { method: 'POST', body: JSON.stringify(draft) })
    setAccountForms({ ...accountForms, [client.id]: { telegram_id: '', username: '', name: '' } })
    await onChange()
  }
  async function patchAccount(client: Client, account: TelegramAccount, patch: Partial<TelegramAccount>) {
    await api(`/api/clients/${client.id}/telegram-accounts/${account.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
    await onChange()
  }
  function accountDraft(client: Client) {
    return accountForms[client.id] || { telegram_id: '', username: '', name: '' }
  }
  function setAccountDraft(client: Client, patch: Partial<{ telegram_id: string; username: string; name: string }>) {
    const current = accountDraft(client)
    setAccountForms({ ...accountForms, [client.id]: { ...current, ...patch } })
  }
  function patchString(client: Client, key: keyof Pick<Client, 'access_until' | 'notes'>, value: string) {
    if (value !== client[key]) void patchClient(client, { [key]: value })
  }
  function patchNumber(client: Client, key: keyof Pick<Client, 'monthly_supplier_search_limit' | 'monthly_procurement_report_limit'>, value: number) {
    if (Number.isFinite(value) && value !== client[key]) void patchClient(client, { [key]: value })
  }
  return (
    <section className="stack">
      <div className="toolbar-panel">
        <input placeholder="ID первого менеджера" value={form.telegram_id} onChange={e => setForm({ ...form, telegram_id: e.target.value })} />
        <input placeholder="Название клиента" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
        <input placeholder="Ник в Telegram" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} />
        <button onClick={() => void createClient()} disabled={!form.telegram_id.trim()}><Plus size={16} />Добавить клиента</button>
      </div>
      <div className="client-card-list">
        {clients.map(client => {
          const draft = accountDraft(client)
          const accounts = client.telegram_accounts?.length ? client.telegram_accounts : []
          const expanded = Boolean(expandedClients[client.id])
          const primaryAccount = accounts[0]
          return (
            <article className="client-card" key={client.id}>
              <div className="client-card-head">
                <div className="client-title-row">
                  <button
                    className="client-expand-button"
                    title={expanded ? 'Свернуть карточку клиента' : 'Открыть карточку клиента'}
                    aria-expanded={expanded}
                    onClick={() => setExpandedClients({ ...expandedClients, [client.id]: !expanded })}
                  >
                    {expanded ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
                  </button>
                  <div>
                    <h2>{client.name || 'Без имени'}</h2>
                    <p>{clientSummaryLine(client, accounts, primaryAccount)}</p>
                  </div>
                </div>
                <div className="client-summary-pills">
                  <span>Менеджеры: {accounts.length || (client.telegram_id ? 1 : 0)}</span>
                  <span>Поставщики: {client.usage ? usageSummaryText(client.usage.supplier_search) : 'нет данных'}</span>
                  <span>Анализ: {client.usage ? usageSummaryText(client.usage.procurement_report) : 'нет данных'}</span>
                </div>
                <div className="client-state">
                  <StatusBadge status={client.is_active ? 'active' : 'disabled'} />
                  {client.is_trial && <StatusBadge status="trial" />}
                  <button className="ghost small-text" onClick={() => void patchClient(client, { is_active: !client.is_active })}>
                    {client.is_active ? 'Отключить' : 'Включить'}
                  </button>
                </div>
              </div>

              {expanded && <div className="client-card-grid">
                <div className="client-section">
                  <h3>Аккаунты менеджеров</h3>
                  <div className="account-list">
                    {accounts.map(account => (
                      <div className="account-row" key={account.id}>
                        <div>
                          <strong>{account.telegram_id}</strong>
                          <small>{account.username ? `@${account.username}` : account.name || 'имя не указано'}</small>
                        </div>
                        <button
                          className="ghost small-text"
                          onClick={() => void patchAccount(client, account, { is_active: !account.is_active })}
                        >
                          {account.is_active ? 'Отключить' : 'Включить'}
                        </button>
                      </div>
                    ))}
                    {!accounts.length && <div className="inline-note">Аккаунты пока не добавлены.</div>}
                    <div className="account-add">
                      <input placeholder="ID менеджера" value={draft.telegram_id} onChange={e => setAccountDraft(client, { telegram_id: e.target.value })} />
                      <input placeholder="Ник в Telegram" value={draft.username} onChange={e => setAccountDraft(client, { username: e.target.value })} />
                      <input placeholder="Имя" value={draft.name} onChange={e => setAccountDraft(client, { name: e.target.value })} />
                      <button className="icon-button small" title="Добавить Telegram-аккаунт" onClick={() => void createAccount(client)} disabled={!draft.telegram_id.trim()}><Plus size={16} /></button>
                    </div>
                  </div>
                </div>

                <div className="client-section">
                  <h3>Функции</h3>
                  <label><input type="checkbox" checked={client.allowed_supplier_search} onChange={e => void patchClient(client, { allowed_supplier_search: e.target.checked })} /> Поиск поставщиков</label>
                  <label><input type="checkbox" checked={client.allowed_procurement_report} onChange={e => void patchClient(client, { allowed_procurement_report: e.target.checked })} /> Анализ документации</label>
                  <label><input type="checkbox" checked={client.is_trial} onChange={e => void patchClient(client, { is_trial: e.target.checked })} /> Бесплатный период</label>
                </div>

                <div className="client-section">
                  <h3>Срок доступа</h3>
                  <input
                    className="client-date"
                    type="text"
                    placeholder="гггг-мм-дд"
                    defaultValue={client.access_until || ''}
                    onBlur={e => patchString(client, 'access_until', e.currentTarget.value)}
                  />
                </div>

                <div className="client-section client-limits-section">
                  <h3>Общие лимиты клиента</h3>
                  <div className="client-limits">
                    <label className="mini-field">
                      <span>Отчёты по поставщикам</span>
                      <input
                        type="number"
                        min={0}
                        defaultValue={client.monthly_supplier_search_limit}
                        aria-label="Лимит отчётов по поиску поставщиков"
                        onBlur={e => patchNumber(client, 'monthly_supplier_search_limit', Number(e.currentTarget.value))}
                      />
                    </label>
                    <label className="mini-field">
                      <span>Анализы документации</span>
                      <input
                        type="number"
                        min={0}
                        defaultValue={client.monthly_procurement_report_limit}
                        aria-label="Лимит отчётов анализа документации"
                        onBlur={e => patchNumber(client, 'monthly_procurement_report_limit', Number(e.currentTarget.value))}
                      />
                    </label>
                  </div>
                  <p className="field-help">Лимит общий для всех Telegram-аккаунтов этого клиента.</p>
                  {client.usage && (
                    <div className="usage-grid">
                      <UsageMeter counter={client.usage.supplier_search} />
                      <UsageMeter counter={client.usage.procurement_report} />
                    </div>
                  )}
                </div>

                <div className="client-section recent-usage-section">
                  <h3>Последние списания</h3>
                  <div className="usage-history">
                    {client.recent_usage?.map(item => (
                      <div className="usage-history-row" key={item.id}>
                        <div>
                          <strong>{item.human_title}</strong>
                          <small>{formatDate(item.created_at)} · менеджер {item.created_by_telegram_id || 'не указан'}</small>
                        </div>
                        <span>{usageEntryLabel(item)}</span>
                      </div>
                    ))}
                    {!client.recent_usage?.length && <div className="inline-note">Списаний в этом месяце пока нет.</div>}
                  </div>
                </div>

                <div className="client-section client-notes">
                  <h3>Заметки</h3>
                  <input
                    className="client-note"
                    placeholder="Комментарий для себя"
                    defaultValue={client.notes || ''}
                    onBlur={e => patchString(client, 'notes', e.currentTarget.value)}
                  />
                </div>
              </div>}
            </article>
          )
        })}
      </div>
    </section>
  )
}

function clientSummaryLine(client: Client, accounts: TelegramAccount[], primaryAccount?: TelegramAccount) {
  const username = client.username ? `@${client.username}` : ''
  const primary = primaryAccount?.telegram_id || client.telegram_id || ''
  const accountLabel = primary ? `первый Telegram ID: ${primary}` : 'Telegram ID не указан'
  return [username, accountLabel].filter(Boolean).join(' · ')
}

function usageSummaryText(counter: UsageCounter) {
  const limit = counter.unlimited ? 'без лимита' : counter.limit
  return `${counter.used}/${limit}`
}

function UsageMeter({ counter }: { counter: UsageCounter }) {
  return (
    <div className="usage-meter">
      <div className="usage-meter-head">
        <strong>{counter.label}</strong>
        <span>{counter.used} из {counter.unlimited ? 'без лимита' : counter.limit}</span>
      </div>
      <div className="usage-bar"><span style={{ width: `${counter.percent}%` }} /></div>
      <small>{counter.unlimited ? 'Ограничение не задано' : `Осталось: ${counter.remaining}`}</small>
    </div>
  )
}

function usageEntryLabel(item: UsageEntry) {
  const parts = []
  if (item.supplier_units) parts.push(`поставщики: ${item.supplier_units}`)
  if (item.procurement_report_units) parts.push(`анализ: ${item.procurement_report_units}`)
  return parts.join(' · ') || item.mode_label
}

function JobsView({ jobs, onChange }: { jobs: Job[]; onChange: () => Promise<void> }) {
  const [evidence, setEvidence] = useState<{ job: Job; payload: unknown } | null>(null)
  const [showInternalJobs, setShowInternalJobs] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [modeFilter, setModeFilter] = useState('')
  const [query, setQuery] = useState('')
  const normalizedQuery = query.trim().toLowerCase()
  const filteredJobs = jobs
    .filter(job => showInternalJobs || !job.is_internal)
    .filter(job => !statusFilter || job.status === statusFilter)
    .filter(job => !modeFilter || job.mode === modeFilter)
    .filter(job => {
      if (!normalizedQuery) return true
      return [
        job.human_title,
        job.client_name,
        job.telegram_id,
        job.created_by_telegram_id,
        job.message,
      ].some(value => String(value || '').toLowerCase().includes(normalizedQuery))
    })
  const visibleJobs = filteredJobs.slice(0, 30)
  const hiddenInternalCount = showInternalJobs ? 0 : jobs.filter(job => job.is_internal).length
  const hiddenByLimitCount = Math.max(0, filteredJobs.length - visibleJobs.length)
  const statusOptions = Array.from(new Set(jobs.map(job => job.status).filter(Boolean)))
  const modeOptions = Array.from(new Set(jobs.map(job => job.mode).filter(Boolean)))

  async function retry(job: Job) {
    await api(`/api/jobs/${job.id}/retry`, { method: 'POST' })
    await onChange()
  }
  async function showEvidence(job: Job) {
    const payload = await api<unknown>(`/api/jobs/${job.id}/evidence`)
    setEvidence({ job, payload })
  }
  async function download(job: Job) {
    const response = await fetch(`/api/jobs/${job.id}/download`, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(await response.text())
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const disposition = response.headers.get('content-disposition') || ''
    const encodedName = disposition.match(/filename\*=utf-8''([^;]+)/i)?.[1]
    const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
    const fallbackExt = job.mode === 'analysis_and_suppliers' ? 'zip' : job.mode === 'procurement_report' ? 'docx' : 'xlsx'
    link.href = url
    link.download = encodedName ? decodeURIComponent(encodedName) : plainName || `aipoisk-${job.id.slice(0, 8)}.${fallbackExt}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  return (
    <section className="stack">
      <div className="list-toolbar">
        <strong>Показано задач: {visibleJobs.length}</strong>
        <input
          className="toolbar-search"
          placeholder="Найти задачу, клиента или Telegram ID"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">Все статусы</option>
          {statusOptions.map(status => <option key={status} value={status}>{humanStatus(status)}</option>)}
        </select>
        <select value={modeFilter} onChange={e => setModeFilter(e.target.value)}>
          <option value="">Все режимы</option>
          {modeOptions.map(mode => <option key={mode} value={mode}>{humanMode(mode)}</option>)}
        </select>
        {hiddenByLimitCount > 0 && <span>Ещё {hiddenByLimitCount} старых задач скрыто, чтобы список не превращался в простыню.</span>}
        {hiddenInternalCount > 0 && (
          <label>
            <input type="checkbox" checked={showInternalJobs} onChange={e => setShowInternalJobs(e.target.checked)} />
            Показать служебные проверки ({hiddenInternalCount})
          </label>
        )}
      </div>
      <div className="job-list">
        {visibleJobs.map(job => (
          <article className={job.is_internal ? 'job-card service' : 'job-card'} key={job.id}>
            <div className="job-main">
              <div>
                <h2>{job.human_title || humanMode(job.mode)}</h2>
                <p>{formatDate(job.created_at)} · {job.client_name || 'клиент не указан'} · менеджер {job.created_by_telegram_id || job.telegram_id || 'не указан'}</p>
              </div>
              <StatusBadge status={job.status} />
            </div>
            <div className="job-meta">
              <span>{job.mode_label || humanMode(job.mode)}</span>
              <span>{job.mode === 'procurement_report' ? 'Анализ документации' : `Поставщиков: ${supplierCountLabel(job)}`}</span>
            </div>
            <Progress value={job.progress} note={job.message || humanStatus(job.status)} />
            <div className="row-actions">
              {job.has_result && <button className="icon-button small" onClick={() => void download(job)} title="Скачать"><Download size={15} /></button>}
              <button className="icon-button small" onClick={() => void showEvidence(job)} title="Данные проверки"><FileText size={15} /></button>
              <button className="icon-button small" onClick={() => void retry(job)} title="Перезапустить"><Play size={15} /></button>
            </div>
          </article>
        ))}
        {!visibleJobs.length && <div className="empty inline-empty">Нет пользовательских задач для показа.</div>}
      </div>
      {evidence && (
        <div className="wide-panel full-width-panel">
          <div className="panel-heading">
            <h2>Данные проверки: {evidence.job.human_title || humanMode(evidence.job.mode)}</h2>
            <button className="ghost small-text" onClick={() => setEvidence(null)}>Закрыть</button>
          </div>
          <pre className="json-view">{stringify(evidence.payload)}</pre>
        </div>
      )}
    </section>
  )
}

function QualityView({ quality }: { quality: SupplierQualitySnapshot | null }) {
  if (!quality) return <div className="empty">Пока нет данных контроля отчётов.</div>
  const statusEntries = Object.entries(quality.status_counts)
  const providerEntries = sortSupplierProviders(Object.entries(quality.provider_status_counts))
  const visibleFailures = quality.recent_failures
  return (
    <section className="stack">
      <div className="content-grid">
        <div className="metric">
          <Search size={20} />
          <div><span>Поисковых отчётов</span><strong>{quality.window_size}</strong><small>последние задачи</small></div>
        </div>
        <div className="metric">
          <CheckCircle2 size={20} />
          <div><span>Среднее поставщиков</span><strong>{quality.average_verified_count}</strong><small>в одном отчёте</small></div>
        </div>
        <div className="metric">
          <RefreshCw size={20} />
          <div><span>Средняя длительность</span><strong>{formatDuration(quality.average_duration_seconds)}</strong><small>по готовым задачам</small></div>
        </div>
        <div className="metric">
          <XCircle size={20} />
          <div><span>Срывов ИИ-проверки</span><strong>{quality.ai_required_failures}</strong><small>{quality.underfilled_terminal_jobs} недоборов</small></div>
        </div>
      </div>
      <div className="ops-grid">
        <div className="form-panel full-width-panel">
          <h2>Что требует внимания</h2>
          {quality.alerts.length ? (
            <div className="alert-list">
              {quality.alerts.map(alert => (
                <div className={`alert-row ${alert.severity}`} key={alert.code}>
                  <strong>{humanAlertTitle(alert.code)}</strong>
                  <span>{humanAlertMessage(alert)}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty inline-empty">Активных сигналов нет.</div>
          )}
        </div>
        <div className="form-panel">
          <h2>Статусы задач</h2>
          <div className="kv-list">
            {statusEntries.map(([status, count]) => <div key={status}><StatusBadge status={status} /><strong>{count}</strong></div>)}
          </div>
        </div>
        <div className="form-panel">
          <h2>Источники поиска</h2>
          <div className="kv-list">
            {providerEntries.map(([provider, counts]) => (
              <div key={provider}>
                <span>{humanProvider(provider)}</span>
                <strong>{providerStatusSummary(counts)}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="form-panel full-width-panel">
        <h2>Задачи для ручной проверки</h2>
        <div className="failure-list">
          {visibleFailures.map(item => (
            <article className="failure-card" key={item.id}>
              <div>
                <strong>{item.title || humanStage(item.stage || '')}</strong>
                <small>{formatDate(item.created_at)} · {humanStage(item.stage || '')}</small>
              </div>
              <span>{item.ai_required ? 'Нужна ИИ-проверка' : 'Проверить вручную'}</span>
              <p>{friendlyError(item.error)}</p>
            </article>
          ))}
          {!visibleFailures.length && <div className="empty inline-empty">Нет пользовательских задач с ошибками.</div>}
        </div>
      </div>
    </section>
  )
}

function SettingsView({ settings, onChange }: { settings: SettingsPayload; onChange: () => Promise<void> }) {
  const [draft, setDraft] = useState(settings)
  const [adapterKey, setAdapterKey] = useState('')
  const [yandexKey, setYandexKey] = useState('')
  const [googleKey, setGoogleKey] = useState('')
  const searchUi = draft.supplier_search_ui
  useEffect(() => setDraft(settings), [settings])
  useEffect(() => {
    void api<{ supplier_search_adapter_api_key?: string; yandex_search_api_key?: string; google_search_api_key?: string }>('/api/settings/keys')
      .then(data => {
        setAdapterKey(data.supplier_search_adapter_api_key || '')
        setYandexKey(data.yandex_search_api_key || '')
        setGoogleKey(data.google_search_api_key || '')
      })
      .catch(() => {
        setAdapterKey('')
        setYandexKey('')
        setGoogleKey('')
      })
  }, [])
  async function save() {
    await api('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify({
        ...draft,
        supplier_search_adapter_api_key: adapterKey,
        yandex_search_api_key: yandexKey,
        google_search_api_key: googleKey,
        supplier_search_provider_order: draft.supplier_search_provider_order || 'yandex,google,tavily,ddgs',
      }),
    })
    await onChange()
  }
  return (
    <section className="settings-grid">
      <div className="form-panel">
        <h2>Бот и хранение</h2>
        <TextField label="Адрес сайта" value={draft.public_base_url} onChange={value => setDraft({ ...draft, public_base_url: value })} />
        <NumberField label="Хранить файлы, дней" value={draft.storage_retention_days} onChange={value => setDraft({ ...draft, storage_retention_days: value })} />
        <NumberField label="Хранить готовые задачи, дней" value={draft.completed_job_retention_days} onChange={value => setDraft({ ...draft, completed_job_retention_days: value })} />
        <NumberField label="Макс. размер файла, МБ" value={draft.max_upload_mb} onChange={value => setDraft({ ...draft, max_upload_mb: value })} />
        <NumberField label="Макс. файлов в комплекте" value={draft.max_files_per_batch} onChange={value => setDraft({ ...draft, max_files_per_batch: value })} />
      </div>
      <div className="form-panel">
        <h2>Бесплатный доступ</h2>
        <label className="switch-row"><input type="checkbox" checked={draft.trial_enabled} onChange={e => setDraft({ ...draft, trial_enabled: e.target.checked })} />Включить бесплатный период для новых Telegram-аккаунтов</label>
        <NumberField label="Бесплатных отчётов по поставщикам" value={draft.trial_supplier_search_limit} onChange={value => setDraft({ ...draft, trial_supplier_search_limit: value })} />
        <NumberField label="Бесплатных анализов документации" value={draft.trial_procurement_report_limit} onChange={value => setDraft({ ...draft, trial_procurement_report_limit: value })} />
        <p className="field-help">В бесплатном периоде недоступны массовая обработка ТЗ и режим «Анализ + поставщики».</p>
      </div>
      <div className="form-panel">
        <h2>Отчёты</h2>
        <NumberField label="Мин. поставщиков по ТЗ" value={draft.default_supplier_target} onChange={value => setDraft({ ...draft, default_supplier_target: value })} />
        <label className="switch-row"><input type="checkbox" checked={draft.allow_partial_supplier_reports} onChange={e => setDraft({ ...draft, allow_partial_supplier_reports: e.target.checked })} />Разрешить частичные отчёты</label>
      </div>
      <div className="form-panel full">
        <h2>Поиск поставщиков</h2>
        <div className="source-summary">
          {searchUi?.has_active_source ? (
            <div className="source-primary">
              <Search size={18} />
              <div>
                <strong>{searchUi.active_label}</strong>
                <span>{searchUi.active_note}</span>
              </div>
            </div>
          ) : (
            <div className="source-primary muted">
              <XCircle size={18} />
              <div>
                <strong>Основной поиск не настроен</strong>
                <span>{searchUi?.active_note || 'Добавьте ключи Яндекса или Google в расширенных параметрах.'}</span>
              </div>
            </div>
          )}
        </div>
        <p className="field-help">Приоритет поиска: Яндекс, Google, затем вспомогательные источники. Tavily используется только как дополнительный резерв.</p>
        <details className="service-panel">
          <summary>Расширенные параметры источников</summary>
          <div className="search-source-grid">
            {searchUi?.technical_sources.map(source => (
              <div className={source.active ? 'source-status active' : 'source-status'} key={source.id}>
                <strong>{source.label}</strong>
                <span>{source.status_label}</span>
              </div>
            ))}
          </div>
          <div className="provider-config-grid">
            <div className="provider-config primary">
              <h3>Яндекс Поиск</h3>
              <TextField label="ID каталога Яндекс Cloud" value={draft.yandex_search_folder_id} onChange={value => setDraft({ ...draft, yandex_search_folder_id: value })} />
              <SecretField label="Ключ API Яндекс Search" value={yandexKey} onChange={setYandexKey} />
            </div>
            <div className="provider-config primary">
              <h3>Google Поиск</h3>
              <TextField label="ID поисковой системы Google" value={draft.google_search_cse_id} onChange={value => setDraft({ ...draft, google_search_cse_id: value })} />
              <SecretField label="Ключ API Google Custom Search" value={googleKey} onChange={setGoogleKey} />
            </div>
            <div className="provider-config auxiliary">
              <h3>Дополнительный Tavily</h3>
              <TextField label="Адрес Tavily API" value={draft.supplier_search_adapter_base_url} onChange={value => setDraft({ ...draft, supplier_search_adapter_base_url: value })} />
              <TextField label="Метка Tavily" value={draft.supplier_search_adapter_model} onChange={value => setDraft({ ...draft, supplier_search_adapter_model: value })} />
              <SecretField label="Ключ Tavily API" value={adapterKey} onChange={setAdapterKey} />
            </div>
            <div className="provider-config auxiliary">
              <h3>Порядок источников</h3>
              <TextField label="Порядок поиска" value={draft.supplier_search_provider_order} onChange={value => setDraft({ ...draft, supplier_search_provider_order: value })} />
              <p className="field-help">Обычный порядок: yandex,google,tavily,ddgs.</p>
            </div>
          </div>
        </details>
      </div>
      <div className="form-panel full">
        <details className="service-panel">
          <summary>Расширенные настройки отчётов и сообщений</summary>
          <TextArea label="Отчёты" value={draft.report_settings_json} onChange={value => setDraft({ ...draft, report_settings_json: value })} />
          <TextArea label="Документы" value={draft.document_settings_json} onChange={value => setDraft({ ...draft, document_settings_json: value })} />
          <TextArea label="Сообщения бота" value={draft.bot_messages_json} onChange={value => setDraft({ ...draft, bot_messages_json: value })} />
        </details>
      </div>
      <div className="savebar"><button onClick={() => void save()}><CheckCircle2 size={16} />Сохранить настройки</button></div>
    </section>
  )
}

function AiView({ settings, onChange }: { settings: SettingsPayload; onChange: () => Promise<void> }) {
  const [savedModels, setSavedModels] = useState<SavedModel[]>(() => parseJson(settings.saved_models_json, []))
  const [providers, setProviders] = useState<CustomProvider[]>(() => ensureModelProviders(parseJson(settings.custom_ai_providers_json, []), parseJson(settings.saved_models_json, [])))
  const [functionModels, setFunctionModels] = useState<Record<string, string>>(() => parseJson(settings.ai_function_models_json, {}))
  const [primaryProvider, setPrimaryProvider] = useState(settings.primary_provider)
  const [primaryModel, setPrimaryModel] = useState(settings.primary_model)
  const [lightProvider, setLightProvider] = useState(settings.light_provider)
  const [lightModel, setLightModel] = useState(settings.light_model)
  const [testResult, setTestResult] = useState('')

  useEffect(() => {
    const parsedModels = parseJson<SavedModel[]>(settings.saved_models_json, [])
    setProviders(ensureModelProviders(parseJson(settings.custom_ai_providers_json, []), parsedModels))
    setSavedModels(parsedModels)
    setFunctionModels(parseJson(settings.ai_function_models_json, {}))
    setPrimaryProvider(settings.primary_provider)
    setPrimaryModel(settings.primary_model)
    setLightProvider(settings.light_provider)
    setLightModel(settings.light_model)
  }, [settings])

  const modelOptions = useMemo(
    () => savedModels.filter(model => model.provider && model.modelId).map(model => `${model.provider}:${model.modelId}`),
    [savedModels],
  )
  function modelOptionLabel(raw: string) {
    const [providerId, ...rest] = raw.split(':')
    const modelId = rest.join(':')
    const saved = savedModels.find(item => item.provider === providerId && item.modelId === modelId)
    if (saved) return saved.modelId || raw
    return modelId || raw
  }
  function providerOptionLabel(provider: CustomProvider) {
    return provider.id
  }
  function resolvedModelValue(raw: string | undefined) {
    const value = String(raw || '').trim()
    if (value === '__primary__' || !value) return primaryProvider && primaryModel ? `${primaryProvider}:${primaryModel}` : ''
    if (value === '__light__') return lightProvider && lightModel ? `${lightProvider}:${lightModel}` : ''
    return value
  }
  function explicitFunctionModels() {
    const result: Record<string, string> = {}
    for (const key of aiRoutingKeys) {
      const value = resolvedModelValue(functionModels[key])
      if (value) result[key] = value
    }
    return result
  }

  function addProvider() {
    const id = `custom-provider-${providers.length + 1}`
    setProviders([...providers, { id, name: 'Custom provider', baseUrl: '', apiKey: '', model: '' }])
  }
  function addModel() {
    setSavedModels([...savedModels, { id: crypto.randomUUID(), name: '', provider: providers[0]?.id || '', modelId: '' }])
  }
  async function save() {
    const normalizedProviders = ensureModelProviders(providers, savedModels)
    await api('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify({
        primary_provider: primaryProvider,
        primary_model: primaryModel,
        light_provider: lightProvider,
        light_model: lightModel,
        custom_ai_providers_json: stringify(normalizedProviders),
        saved_models_json: stringify(savedModels),
        ai_function_models_json: stringify(explicitFunctionModels()),
      }),
    })
    await onChange()
  }
  async function testAi() {
    const result = await api<{ response: string }>('/api/ai/test', {
      method: 'POST',
      body: JSON.stringify({ provider: lightProvider || primaryProvider, model: lightModel || primaryModel }),
    })
    setTestResult(result.response)
  }
  return (
    <section className="stack">
      <div className="form-panel full-width-panel">
        <h2>Модели для функций бота</h2>
        <p className="field-help">В селекторах отображается только modelId.</p>
        {aiRoutingKeys.map(key => (
          <ModelSelect
            key={key}
            label={functionLabels[key] || key}
            value={resolvedModelValue(functionModels[key])}
            options={modelOptions}
            optionLabel={modelOptionLabel}
            onChange={(provider, model) => {
              setFunctionModels({ ...functionModels, [key]: `${provider}:${model}` })
            }}
          />
        ))}
      </div>
      <div className="form-panel">
        <h2>primary_model / light_model</h2>
        <ModelSelect label="primary_model" value={primaryProvider && primaryModel ? `${primaryProvider}:${primaryModel}` : ''} options={modelOptions} optionLabel={modelOptionLabel} onChange={(provider, model) => { setPrimaryProvider(provider); setPrimaryModel(model) }} />
        <ModelSelect label="light_model" value={lightProvider && lightModel ? `${lightProvider}:${lightModel}` : ''} options={modelOptions} optionLabel={modelOptionLabel} onChange={(provider, model) => { setLightProvider(provider); setLightModel(model) }} />
      </div>
      <div className="form-panel">
        <h2>Проверка</h2>
        <p className="field-help">Запрос проверки: light_model, иначе primary_model.</p>
        <button className="secondary" onClick={() => void testAi()}><BrainCircuit size={16} />Проверить модель</button>
        {testResult && <span className="test-result">{testResult}</span>}
      </div>
      <div className="form-panel full-width-panel">
        <details className="service-panel">
          <summary>Провайдеры и modelId</summary>
          <div className="advanced-section">
            <h3>AI providers</h3>
            <button onClick={addProvider}><Plus size={16} />Добавить provider</button>
            <div className="provider-row-head"><span>provider id</span><span>provider name</span><span>Base URL</span><span>API key</span></div>
            {providers.map((provider, index) => (
              <div className="provider-row" key={provider.id}>
                <input value={provider.id} placeholder="например openrouter" onChange={e => updateArray(providers, setProviders, index, { id: e.target.value })} />
                <input value={provider.name} placeholder={canonicalProviderName(provider.id)} onChange={e => updateArray(providers, setProviders, index, { name: e.target.value })} />
                <input value={provider.baseUrl} placeholder="https://.../v1" onChange={e => updateArray(providers, setProviders, index, { baseUrl: e.target.value })} />
                <input type="password" value={provider.apiKey} placeholder="API key" onChange={e => updateArray(providers, setProviders, index, { apiKey: e.target.value })} />
              </div>
            ))}
          </div>
          <div className="advanced-section">
            <h3>Models</h3>
            <button onClick={addModel}><Plus size={16} />Добавить modelId</button>
            <div className="model-row-head"><span>Комментарий</span><span>provider id</span><span>modelId</span></div>
            {savedModels.map((model, index) => (
              <div className="model-row" key={model.id}>
                <input value={model.name} placeholder="необязательно" onChange={e => updateArray(savedModels, setSavedModels, index, { name: e.target.value })} />
                <select value={model.provider} onChange={e => updateArray(savedModels, setSavedModels, index, { provider: e.target.value })}>
                  <option value="">provider id</option>
                  {providers.map(provider => <option key={provider.id} value={provider.id}>{providerOptionLabel(provider)}</option>)}
                </select>
                <input value={model.modelId} placeholder="например gemini-3.1-flash-lite" onChange={e => updateArray(savedModels, setSavedModels, index, { modelId: e.target.value })} />
              </div>
            ))}
          </div>
        </details>
      </div>
      <div className="savebar">
        <button onClick={() => void save()}><CheckCircle2 size={16} />Сохранить ИИ</button>
      </div>
    </section>
  )
}

function updateArray<T>(items: T[], setter: (value: T[]) => void, index: number, patch: Partial<T>) {
  setter(items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
}

function ModelSelect({
  label,
  value,
  options,
  optionLabel = option => option,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  optionLabel?: (option: string) => string
  onChange: (provider: string, model: string) => void
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={event => {
        const raw = event.target.value
        if (raw.startsWith('__')) {
          onChange(raw, '')
          return
        }
        const [provider, ...rest] = raw.split(':')
        onChange(provider || '', rest.join(':') || '')
      }}>
        <option value="">Не выбрано</option>
        {options.map(option => <option key={option} value={option}>{optionLabel(option)}</option>)}
      </select>
    </label>
  )
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="field"><span>{label}</span><input value={value || ''} onChange={e => onChange(e.target.value)} /></label>
}

function SecretField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="field"><span>{label}</span><input type="password" value={value || ''} onChange={e => onChange(e.target.value)} /></label>
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label className="field"><span>{label}</span><input type="number" value={value || 0} onChange={e => onChange(Number(e.target.value))} /></label>
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="field"><span>{label}</span><textarea value={value || ''} onChange={e => onChange(e.target.value)} /></label>
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status ${status}`}>{humanStatus(status)}</span>
}

function Progress({ value, note }: { value: number; note: string }) {
  return (
    <div className="progress-wrap">
      <div className="progress"><span style={{ width: `${value}%` }} /></div>
      <small>{note}</small>
    </div>
  )
}
