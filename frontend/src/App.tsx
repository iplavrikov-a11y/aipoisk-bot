import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowDown,
  ArrowUp,
  Bot,
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Cpu,
  CreditCard,
  Database,
  Download,
  FileText,
  HardDrive,
  KeyRound,
  Loader2,
  LogIn,
  MemoryStick,
  Minus,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  Server,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Users,
  XCircle,
} from 'lucide-react'

type View = 'dashboard' | 'analytics' | 'clients' | 'jobs' | 'billing' | 'settings' | 'ai'

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
  is_pending: boolean
  source: 'telegram' | 'web' | string
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
  supplier_target_min: number
  notes: string
  telegram_accounts: TelegramAccount[]
  web_users: WebUser[]
  usage: ClientUsage | null
  recent_usage: UsageEntry[]
  recent_billing: BillingTransaction[]
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
  available: number | null
  reserved: number
  spent: number
  granted: number
  manual_debited: number
  source: string
  low: boolean
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
  is_pending: boolean
  notes: string
}

type WebUser = {
  id: string
  client_id: string
  email: string
  name: string
  is_active: boolean
  is_email_verified: boolean
  created_at: string | null
  last_login_at: string | null
}

type PasswordResetRequest = {
  id: string
  user_id: string
  client_id: string
  client_name: string
  email: string
  status: string
  admin_note: string
  requested_ip: string
  created_at: string | null
  resolved_at: string | null
  resolved_by: string
  last_login_at: string | null
}

type AccountDraft = {
  telegram_id: string
  username: string
  name: string
}

type GrantDraft = {
  package_id: string
  kind: string
  units: string
  note: string
  operation: 'grant' | 'debit'
}

type Job = {
  id: string
  client_id: string
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
  result_files: JobResultFile[]
  has_evidence: boolean
  error: string
  created_at: string
  updated_at: string | null
  completed_at: string | null
}

type JobResultFile = {
  kind: string
  label: string
  filename: string
}

type JobInputFile = {
  id: string
  original_filename: string
  parse_status: string
  extracted_chars: number
  error: string
}

type JobSource = {
  id: string
  kind: string
  label: string
  value: string
  parse_status: string
  extracted_chars: number
  error: string
}

type JobSupplier = {
  id: string
  company_name: string
  site: string
  product_match: string
  contact_email: string
  contact_phone: string
  source_url: string
  verification_status: string
}

type JobDetail = Job & {
  files?: JobInputFile[]
  sources?: JobSource[]
  suppliers?: JobSupplier[]
}

type JobDetailError = {
  detail_error: string
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
  supplier_ai_provider: string
  supplier_ai_model: string
  custom_ai_providers_json: string
  saved_models_json: string
  ai_function_models_json: string
  ai_analysis_fallback_json: string
  ai_supplier_fallback_json: string
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
  bot_telegram: string
  contact_email: string
  contact_telegram: string
  contact_max: string
  contact_max_link: string
  contact_website: string
  payment_instructions: string
  payment_provider: string
  yookassa_shop_id: string
  yookassa_secret_key_set: boolean
  yookassa_secret_key?: string
  yookassa_return_url: string
  supplier_search_ui: SupplierSearchUi
}

type SettingsPatchPayload = Partial<SettingsPayload> & {
  supplier_search_adapter_api_key?: string
  yandex_search_api_key?: string
  google_search_api_key?: string
  yookassa_secret_key?: string
}

type TariffPackage = {
  id: string
  kind: string
  name: string
  units: number
  price_kopeks: number
  price_rub: number
  description: string
  is_active: boolean
  sort_order: number
  created_at: string | null
  updated_at: string | null
}

type BillingTransaction = {
  id: string
  client_id: string
  job_id: string | null
  package_id: string
  kind: string
  kind_label: string
  operation: string
  operation_label: string
  units: number
  note: string
  created_by: string
  created_at: string | null
}

type BotAnalytics = {
  period_days: number
  generated_at: string
  summary: {
    clients_total: number
    active_clients: number
    telegram_accounts: number
    trial_clients: number
    period_jobs: number
    period_active_users: number
    period_active_clients: number
    clients_with_usage: number
    clients_with_grants: number
  }
  funnel: {
    trial_started: number
    trial_used_bot: number
    trial_with_grants: number
    trial_to_grant_percent: number
    usage_to_grant_percent: number
  }
  jobs: {
    by_mode: Array<{ mode: string; label: string; count: number }>
    by_status: Array<{ status: string; label: string; count: number }>
    daily: Array<{ date: string; supplier_search: number; procurement_report: number; analysis_and_suppliers: number; total: number }>
  }
  billing: {
    period: Array<{ kind: string; label: string; granted: number; reserved: number; charged: number; released: number; manual_debited: number }>
    payment_provider: string
    yookassa_ready: boolean
  }
  top_clients: AnalyticsClient[]
  trial_followups: AnalyticsClient[]
}

type AnalyticsClient = {
  client_id: string
  name: string
  telegram_id: string
  username: string
  is_trial: boolean
  is_active: boolean
  jobs_total: number
  supplier_jobs: number
  report_jobs: number
  completed_jobs: number
  failed_jobs: number
  last_job_at: string | null
  supplier_available: number | null
  report_available: number | null
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

type FallbackEntry = {
  provider: string
  modelId: string
}

type AiTestState = {
  status: 'idle' | 'running' | 'success' | 'error'
  message: string
  providerName?: string
  model?: string
}

const apiBase = ''
const ADMIN_JOBS_PAGE_SIZE = 12
const procurementAiRoutingKeys = [
  'procurement_document_analysis',
  'procurement_report_verification',
  'procurement_key_info_extraction',
  'procurement_search_query_generation',
  'procurement_report_official_card_repair',
]
const supplierAiRoutingKeys = [
  'minprom_registry_requirement',
  'minprom_registry_query_generation',
  'supplier_procurement_profile',
  'supplier_query_generation',
  'supplier_tz_context_extraction',
  'supplier_candidate_reranker',
  'supplier_candidate_verifier',
]

const viewCopy: Record<View, { title: string; description: string }> = {
  dashboard: {
    title: 'Сводка',
    description: 'Короткая картина по клиентам, задачам и текущим настройкам сервиса.',
  },
  analytics: {
    title: 'Статистика',
    description: 'Воронка Telegram-бота, активность клиентов, триал для дожима и готовность оплаты.',
  },
  clients: {
    title: 'Клиенты',
    description: 'Клиенты из Telegram и сайта, баланс генераций и ручные корректировки.',
  },
  jobs: {
    title: 'Задачи',
    description: 'Последние запуски бота, статусы обработки и готовые файлы для скачивания.',
  },
  billing: {
    title: 'Тарифы',
    description: 'Пакеты как витрина и произвольные ручные корректировки клиентам.',
  },
  settings: {
    title: 'Настройки',
    description: 'Контакты, ручная оплата, бесплатный период, хранение файлов и поиск поставщиков.',
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
  email_unverified: 'почта не подтверждена',
  account_pending: 'ожидает ID',
  pending: 'в очереди',
  running: 'в работе',
  completed: 'готово',
  partial: 'частично готово',
  needs_review: 'нужна проверка',
  failed: 'ошибка',
  cancelled: 'отменено',
  awaiting_customer_confirmation: 'ожидает клиента',
  customer_declined: 'отклонено',
  confirmation_expired: 'истёк срок',
}

const functionLabels: Record<string, string> = {
  procurement_document_analysis: 'Анализ документации',
  procurement_report_verification: 'Проверка отчёта анализа',
  procurement_key_info_extraction: 'Извлечение условий закупки',
  procurement_search_query_generation: 'Запросы по закупке',
  procurement_report_official_card_repair: 'Сверка карточки закупки',
  supplier_query_generation: 'Запросы поставщиков',
  supplier_candidate_verifier: 'Проверка поставщиков',
}

const modelRoleLabels: Record<string, string> = {
  __primary__: 'Основная',
  __light__: 'Быстрая',
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
  const rawMessage = err instanceof Error ? err.message : String(err || '')
  let message = rawMessage
  try {
    const parsed = JSON.parse(rawMessage)
    if (typeof parsed?.detail === 'string') message = parsed.detail
  } catch {
    message = rawMessage
  }
  if (message.includes('Invalid login or password') || message.includes('401')) {
    return 'Неверный логин или пароль.'
  }
  if (message.includes('Too many login attempts') || message.includes('429')) {
    return 'Слишком много попыток входа. Подождите несколько минут и попробуйте снова.'
  }
  return message || 'Ошибка загрузки'
}

function normalizeTelegramUsername(value: string) {
  return String(value || '').trim().replace(/^@+/, '').toLowerCase()
}

function clientDisplayName(client: Client) {
  if (client.web_users?.[0]?.email) return client.web_users[0].email
  return client.name || (client.username ? `@${client.username}` : '') || client.telegram_id || 'без имени'
}

function accountDisplayName(account?: TelegramAccount) {
  if (!account) return 'этот Telegram-аккаунт'
  return account.name || (account.username ? `@${account.username}` : '') || account.telegram_id || 'этот Telegram-аккаунт'
}

function findLinkedTelegramAccount(clients: Client[], targetClient: Client, draft: AccountDraft) {
  const telegramId = draft.telegram_id.trim()
  const username = normalizeTelegramUsername(draft.username)
  for (const client of clients) {
    if (client.id === targetClient.id) continue
    for (const account of client.telegram_accounts || []) {
      if (telegramId && account.telegram_id === telegramId) return { client, account }
      if (username && normalizeTelegramUsername(account.username) === username) return { client, account }
    }
    if (telegramId && client.telegram_id === telegramId) return { client, account: undefined }
  }
  return null
}

function transferAccountMessage(sourceClient: Client, targetClient: Client, account?: TelegramAccount) {
  return [
    `Telegram-аккаунт ${accountDisplayName(account)} уже привязан к клиенту «${clientDisplayName(sourceClient)}».`,
    `Перенести его к клиенту «${clientDisplayName(targetClient)}»?`,
    'Если это отдельный тестовый клиент с одним аккаунтом, его история и списания будут объединены с выбранным клиентом.',
  ].join('\n\n')
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

function isKnownProviderId(providerId: string) {
  const normalized = String(providerId || '').trim().toLowerCase()
  return ['openrouter', 'open-router', 'openai', 'open-ai', 'gemini', 'google', 'polza'].includes(normalized)
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
  const hasConfiguredProviders = providers.some(provider => String(provider.id || '').trim())
  const orderedIds = hasConfiguredProviders ? [] : ['openrouter', 'open-ai', 'gemini']
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

const MOSCOW_TIME_ZONE = 'Europe/Moscow'

function apiDateValue(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return trimmed
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return `${trimmed}T00:00:00Z`
  }
  if (/(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed)) {
    return trimmed
  }
  return `${trimmed}Z`
}

function formatDate(value: string | null | undefined) {
  if (!value) return '-'
  const date = new Date(apiDateValue(value))
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16)
  return date.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short', timeZone: MOSCOW_TIME_ZONE })
}

export function App() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authenticated, setAuthenticated] = useState(false)
  const [view, setView] = useState<View>('dashboard')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [opsStatus, setOpsStatus] = useState<OpsStatus | null>(null)
  const [settings, setSettings] = useState<SettingsPayload | null>(null)
  const [analytics, setAnalytics] = useState<BotAnalytics | null>(null)
  const [tariffs, setTariffs] = useState<TariffPackage[]>([])
  const [passwordResets, setPasswordResets] = useState<PasswordResetRequest[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const isReady = authenticated
  const canLogin = username.trim().length > 0 && password.length > 0

  async function loadAll(force = false) {
    if (!force && !authenticated) return
    setLoading(true)
    setError('')
    try {
      const [dashboardData, clientsData, jobsData, opsStatusData, settingsData, analyticsData, tariffData, passwordResetData] = await Promise.all([
        api<Dashboard>('/api/dashboard'),
        api<Client[]>('/api/clients'),
        api<Job[]>('/api/jobs?include_internal=true&limit=500'),
        api<OpsStatus>('/api/ops/system-status'),
        api<SettingsPayload>('/api/settings'),
        api<BotAnalytics>('/api/analytics/bot?period_days=30'),
        api<TariffPackage[]>('/api/tariffs'),
        api<PasswordResetRequest[]>('/api/web-password-resets?status=open'),
      ])
      setDashboard(dashboardData)
      setClients(clientsData)
      setJobs(jobsData)
      setOpsStatus(opsStatusData)
      setSettings(settingsData)
      setAnalytics(analyticsData)
      setTariffs(tariffData)
      setPasswordResets(passwordResetData)
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
    setOpsStatus(null)
    setSettings(null)
    setAnalytics(null)
    setTariffs([])
    setPasswordResets([])
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

  useEffect(() => {
    function handleUnhandled(event: PromiseRejectionEvent) {
      setError(formatError(event.reason))
    }
    window.addEventListener('unhandledrejection', handleUnhandled)
    return () => window.removeEventListener('unhandledrejection', handleUnhandled)
  }, [])

  useEffect(() => {
    const activeItem = document.querySelector('.nav-item.active')
    activeItem?.scrollIntoView({ block: 'nearest', inline: 'center' })
  }, [view])

  const nav = [
    { id: 'dashboard' as const, label: 'Сводка', icon: ShieldCheck },
    { id: 'analytics' as const, label: 'Статистика', icon: Database },
    { id: 'clients' as const, label: 'Клиенты', icon: Users },
    { id: 'jobs' as const, label: 'Задачи', icon: FileText },
    { id: 'billing' as const, label: 'Тарифы', icon: CreditCard },
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
        <a className="brand" href="https://tenderlex.ru/" target="_blank" rel="noreferrer">
          <div className="brand-mark"><Search size={18} /></div>
          <div>
            <div className="brand-name">TenderLex</div>
            <div className="brand-sub">tenderlex.ru</div>
          </div>
        </a>
        <nav className="nav">
          {nav.map(item => {
            const Icon = item.icon
            return (
              <button key={item.id} className={view === item.id ? 'nav-item active' : 'nav-item'} onClick={() => { setError(''); setView(item.id) }}>
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
            <button className="login-button" onClick={() => void loadAll()} disabled={loading}>
              {loading ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />}
              Обновить
            </button>
            <button className="secondary" onClick={() => void logout()}>Выйти</button>
          </div>
        </header>

        {error && <div className="alert error"><XCircle size={18} />{error}</div>}
        {isReady && view === 'dashboard' && <DashboardView dashboard={dashboard} settings={settings} opsStatus={opsStatus} />}
        {isReady && view === 'analytics' && <AnalyticsView analytics={analytics} />}
        {isReady && view === 'clients' && <ClientsView clients={clients} tariffs={tariffs} passwordResets={passwordResets} onChange={loadAll} />}
        {isReady && view === 'jobs' && <JobsView jobs={jobs} onChange={loadAll} />}
        {isReady && view === 'billing' && <BillingView tariffs={tariffs} onChange={loadAll} />}
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
          <span>Минимум поставщиков: {settings?.default_supplier_target || 25}</span>
          <span>Логистика: {settings?.logistics_enabled ? 'включена' : 'отключена'}</span>
          <span>Частичные отчёты: {settings?.allow_partial_supplier_reports ? 'разрешены' : 'запрещены'}</span>
          <span>Бесплатный период: {settings?.trial_enabled ? 'включён' : 'выключен'}</span>
        </div>
      </div>
    </section>
  )
}

function AnalyticsView({ analytics }: { analytics: BotAnalytics | null }) {
  if (!analytics) return <div className="empty">Статистика пока не загружена.</div>
  const summary = analytics.summary
  const funnel = analytics.funnel
  const maxDaily = Math.max(1, ...analytics.jobs.daily.map(item => item.total))
  const metrics = [
    { label: 'Клиентов', value: summary.clients_total, note: `${summary.active_clients} активных`, icon: Users },
    { label: 'Telegram', value: summary.telegram_accounts, note: `${summary.period_active_users} активных за ${analytics.period_days} дней`, icon: Bot },
    { label: 'Задач', value: summary.period_jobs, note: `${summary.period_active_clients} клиентов запускали бота`, icon: FileText },
    { label: 'Триал', value: `${funnel.trial_to_grant_percent}%`, note: `${funnel.trial_with_grants}/${funnel.trial_started} дошли до оплаты`, icon: CreditCard },
  ]
  return (
    <section className="stack">
      <div className="content-grid">
        {metrics.map(item => {
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
      </div>

      <div className="analytics-grid">
        <div className="form-panel">
          <h2>Воронка</h2>
          <div className="kv-list">
            <div><span>Триал создан</span><strong>{funnel.trial_started}</strong></div>
            <div><span>Триал пользовался ботом</span><strong>{funnel.trial_used_bot}</strong></div>
            <div><span>Получили начисления</span><strong>{funnel.trial_with_grants}</strong></div>
            <div><span>Конверсия использования</span><strong>{funnel.usage_to_grant_percent}%</strong></div>
          </div>
        </div>
        <div className="form-panel">
          <h2>Задачи по режимам</h2>
          <div className="kv-list">
            {analytics.jobs.by_mode.map(item => <div key={item.mode}><span>{item.label}</span><strong>{item.count}</strong></div>)}
            {!analytics.jobs.by_mode.length && <div className="inline-note">За период задач не было.</div>}
          </div>
        </div>
        <div className="form-panel">
          <h2>Статусы задач</h2>
          <div className="kv-list">
            {analytics.jobs.by_status.map(item => <div key={item.status}><span>{item.label}</span><strong>{item.count}</strong></div>)}
            {!analytics.jobs.by_status.length && <div className="inline-note">Статусов за период нет.</div>}
          </div>
        </div>
        <div className="form-panel">
          <h2>Оплата</h2>
          <div className="kv-list">
            <div><span>Текущий режим</span><strong>{paymentProviderLabel(analytics.billing.payment_provider)}</strong></div>
            <div><span>YooKassa</span><strong>{analytics.billing.yookassa_ready ? 'готова' : 'не готова'}</strong></div>
          </div>
          <div className="billing-mini-list">
            {analytics.billing.period.map(item => (
              <div key={item.kind}>
                <strong>{item.label}</strong>
                <span>начислено {item.granted} · списано {item.charged} · резерв {item.reserved}</span>
              </div>
            ))}
            {!analytics.billing.period.length && <span className="inline-note">Начислений за период нет.</span>}
          </div>
        </div>
      </div>

      <div className="form-panel full-width-panel">
        <h2>Динамика запусков</h2>
        <div className="daily-bars">
          {analytics.jobs.daily.map(item => (
            <div className="daily-bar" key={item.date} title={`${item.date}: ${item.total}`}>
              <span style={{ height: `${Math.max(6, Math.round(item.total * 100 / maxDaily))}%` }} />
              <small>{new Date(apiDateValue(item.date)).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', timeZone: MOSCOW_TIME_ZONE })}</small>
            </div>
          ))}
        </div>
      </div>

      <AnalyticsClientList
        title="Триал для дожима"
        empty="Нет триальных клиентов с использованием без начислений."
        clients={analytics.trial_followups}
      />
      <AnalyticsClientList
        title="Топ клиентов за период"
        empty="За период нет активных клиентов."
        clients={analytics.top_clients}
      />
    </section>
  )
}

function AnalyticsClientList({ title, empty, clients }: { title: string; empty: string; clients: AnalyticsClient[] }) {
  return (
    <div className="form-panel full-width-panel">
      <h2>{title}</h2>
      <div className="analytics-client-list">
        {clients.map(client => (
          <div className="analytics-client-row" key={client.client_id}>
            <div>
              <strong>{client.name}</strong>
              <small>{client.username ? `@${client.username}` : client.telegram_id || 'Telegram не указан'} · последний запуск {formatDate(client.last_job_at)}</small>
            </div>
            <span>{client.jobs_total} задач</span>
            <span>поставщики {client.supplier_jobs}</span>
            <span>анализ {client.report_jobs}</span>
            <span>{analyticsBalance(client)}</span>
          </div>
        ))}
        {!clients.length && <div className="empty inline-empty">{empty}</div>}
      </div>
    </div>
  )
}

function analyticsBalance(client: AnalyticsClient) {
  return `баланс: ${client.supplier_available ?? 'без лимита'} / ${client.report_available ?? 'без лимита'}`
}

function paymentProviderLabel(provider: string) {
  return provider === 'yookassa' ? 'YooKassa' : 'ручная оплата'
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
      {opsStatus.queue.running > 0 && (
        <div style={{ marginTop: 8 }}>
          <button className="icon-button small" onClick={async () => {
            if (!window.confirm('Остановить задачи, зависшие более 45 минут?')) return
            const res = await api<{ cancelled: string[]; count: number }>('/api/jobs/force-stale?max_minutes=45', { method: 'POST' })
            alert(res.count ? `Остановлено задач: ${res.count}` : 'Зависших задач не найдено')
          }} title="Разблокировать зависшие задачи">Разблокировать зависшие</button>
        </div>
      )}
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

function ClientsView({
  clients,
  tariffs,
  passwordResets,
  onChange,
}: {
  clients: Client[]
  tariffs: TariffPackage[]
  passwordResets: PasswordResetRequest[]
  onChange: () => Promise<void>
}) {
  const [form, setForm] = useState({ name: '', telegram_usernames: '', telegram_id: '', notes: '' })
  const [accountForms, setAccountForms] = useState<Record<string, AccountDraft>>({})
  const [accountEditForms, setAccountEditForms] = useState<Record<string, AccountDraft>>({})
  const [grantForms, setGrantForms] = useState<Record<string, GrantDraft>>({})
  const [mergeForms, setMergeForms] = useState<Record<string, string>>({})
  const [expandedClients, setExpandedClients] = useState<Record<string, boolean>>({})
  const [resetNotes, setResetNotes] = useState<Record<string, string>>({})
  const [temporaryPasswords, setTemporaryPasswords] = useState<Record<string, string>>({})
  const activeTariffs = tariffs.filter(item => item.is_active)
  async function createClient() {
    const usernames = parseTelegramUsernames(form.telegram_usernames)
    await api('/api/clients', {
      method: 'POST',
      body: JSON.stringify({ ...form, telegram_usernames: usernames, username: usernames[0] || '' }),
    })
    setForm({ name: '', telegram_usernames: '', telegram_id: '', notes: '' })
    await onChange()
  }
  async function patchClient(client: Client, patch: Partial<Client>) {
    await api(`/api/clients/${client.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
    await onChange()
  }
  function patchClientSupplierTarget(client: Client, input: HTMLInputElement) {
    const value = Math.floor(Number(input.value))
    const nextValue = Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0
    input.value = String(nextValue)
    if (nextValue !== (client.supplier_target_min || 0)) void patchClient(client, { supplier_target_min: nextValue })
  }
  async function deleteClient(client: Client) {
    const label = client.name || client.username || client.telegram_id || 'этого клиента'
    if (!window.confirm(`Полностью удалить клиента «${label}» вместе с задачами, балансом и привязками? Это действие нельзя отменить.`)) return
    await api(`/api/clients/${client.id}`, { method: 'DELETE' })
    await onChange()
  }
  async function mergeClientIntoTarget(target: Client) {
    const sourceId = mergeForms[target.id] || ''
    const source = clients.find(item => item.id === sourceId)
    if (!source) return
    if (!window.confirm(`Объединить клиента «${clientDisplayName(source)}» с клиентом «${clientDisplayName(target)}»?\n\nВсе задачи, баланс, Telegram-аккаунты и web-кабинет исходного клиента будут перенесены к целевому клиенту. Исходный клиент будет удалён.`)) return
    await api(`/api/clients/${target.id}/merge`, {
      method: 'POST',
      body: JSON.stringify({ source_client_id: source.id }),
    })
    setMergeForms({ ...mergeForms, [target.id]: '' })
    await onChange()
  }
  async function createAccount(client: Client) {
    const draft = accountForms[client.id] || { telegram_id: '', username: '', name: '' }
    const payload: AccountDraft & { transfer_existing?: boolean } = { ...draft }
    const linkedAccount = findLinkedTelegramAccount(clients, client, draft)
    if (linkedAccount) {
      if (!window.confirm(transferAccountMessage(linkedAccount.client, client, linkedAccount.account))) return
      payload.transfer_existing = true
    }
    const create = (body: AccountDraft & { transfer_existing?: boolean }) => (
      api(`/api/clients/${client.id}/telegram-accounts`, { method: 'POST', body: JSON.stringify(body) })
    )
    try {
      await create(payload)
    } catch (err) {
      const message = formatError(err)
      if (!payload.transfer_existing && message.includes('Подтвердите перенос')) {
        if (!window.confirm(`${message}\n\nПеренести аккаунт к клиенту «${clientDisplayName(client)}»?`)) return
        await create({ ...payload, transfer_existing: true })
      } else {
        throw err
      }
    }
    setAccountForms({ ...accountForms, [client.id]: { telegram_id: '', username: '', name: '' } })
    await onChange()
  }
  async function patchAccount(client: Client, account: TelegramAccount, patch: Partial<TelegramAccount>) {
    await api(`/api/clients/${client.id}/telegram-accounts/${account.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
    await onChange()
  }
  async function deleteAccount(client: Client, account: TelegramAccount) {
    const label = account.username ? `@${account.username}` : account.telegram_id || account.name || 'этот Telegram-аккаунт'
    if (!window.confirm(`Удалить Telegram-аккаунт «${label}» у клиента «${client.name || 'без имени'}»?`)) return
    await api(`/api/clients/${client.id}/telegram-accounts/${account.id}`, { method: 'DELETE' })
    await onChange()
  }
  function accountDraft(client: Client) {
    return accountForms[client.id] || { telegram_id: '', username: '', name: '' }
  }
  function setAccountDraft(client: Client, patch: Partial<AccountDraft>) {
    const current = accountDraft(client)
    setAccountForms({ ...accountForms, [client.id]: { ...current, ...patch } })
  }
  function accountEditDraft(account: TelegramAccount) {
    return accountEditForms[account.id] || {
      telegram_id: account.telegram_id || '',
      username: account.username ? `@${account.username}` : '',
      name: account.name || '',
    }
  }
  function setAccountEditDraft(account: TelegramAccount, patch: Partial<AccountDraft>) {
    const current = accountEditDraft(account)
    setAccountEditForms({ ...accountEditForms, [account.id]: { ...current, ...patch } })
  }
  async function saveAccount(client: Client, account: TelegramAccount) {
    const draft = accountEditDraft(account)
    await patchAccount(client, account, {
      telegram_id: draft.telegram_id,
      username: draft.username,
      name: draft.name,
    })
  }
  function grantDraft(client: Client) {
    return grantForms[client.id] || { package_id: '', kind: 'supplier_search', units: '1', note: '', operation: 'grant' }
  }
  function setGrantDraft(client: Client, patch: Partial<GrantDraft>) {
    const current = grantDraft(client)
    setGrantForms({ ...grantForms, [client.id]: { ...current, ...patch } })
  }
  function applyGrantTemplate(client: Client, packageId: string) {
    const selected = activeTariffs.find(item => item.id === packageId)
    const current = grantDraft(client)
    setGrantForms({
      ...grantForms,
      [client.id]: selected
        ? { ...current, package_id: packageId, kind: selected.kind, units: String(selected.units), operation: 'grant' }
        : { ...current, package_id: '' },
    })
  }
  function quickGrant(client: Client, kind: string, units: number, operation: 'grant' | 'debit' = 'grant') {
    setGrantForms({
      ...grantForms,
      [client.id]: { package_id: '', kind, units: String(units), note: '', operation },
    })
  }
  async function grantUnits(client: Client) {
    const draft = grantDraft(client)
    const selected = draft.operation === 'grant' ? activeTariffs.find(item => item.id === draft.package_id) : undefined
    const units = Math.floor(Number(draft.units))
    if (!Number.isFinite(units) || units < 1) return
    const packageId = selected && selected.kind === draft.kind && selected.units === units ? selected.id : ''
    if (draft.operation === 'debit') {
      const available = availableBillingUnits(client, draft.kind)
      if (available !== null && units > available) return
      if (!window.confirm(`Списать ${units} ${humanBillingKind(draft.kind).toLowerCase()} у клиента «${clientDisplayName(client)}»?`)) return
    }
    await api(`/api/clients/${client.id}/billing/grants`, {
      method: 'POST',
      body: JSON.stringify({ kind: draft.kind, package_id: packageId, units, note: '', operation: draft.operation }),
    })
    setGrantForms({ ...grantForms, [client.id]: { package_id: '', kind: draft.kind, units: '1', note: '', operation: draft.operation } })
    await onChange()
  }
  async function verifyWebUserEmail(client: Client, user: WebUser) {
    await api(`/api/clients/${client.id}/web-users/${user.id}/verify-email`, { method: 'POST' })
    await onChange()
  }
  async function completePasswordReset(item: PasswordResetRequest) {
    const result = await api<{ temporary_password: string }>(`/api/web-password-resets/${item.id}/complete`, {
      method: 'POST',
      body: JSON.stringify({ note: resetNotes[item.id] || '' }),
    })
    setTemporaryPasswords({ ...temporaryPasswords, [item.id]: result.temporary_password })
  }
  async function ignorePasswordReset(item: PasswordResetRequest) {
    await api(`/api/web-password-resets/${item.id}/ignore`, {
      method: 'POST',
      body: JSON.stringify({ note: resetNotes[item.id] || '' }),
    })
    const nextPasswords = { ...temporaryPasswords }
    delete nextPasswords[item.id]
    setTemporaryPasswords(nextPasswords)
    await onChange()
  }
  function patchClientNote(client: Client, value: string) {
    if (value !== client.notes) void patchClient(client, { notes: value })
  }
  return (
    <section className="stack">
      {passwordResets.length > 0 && (
        <div className="form-panel full-width-panel password-reset-panel">
          <h2>Восстановление доступа</h2>
          <p className="field-help">Клиент оставил заявку на вход в кабинет. Сбросьте пароль и передайте временный пароль клиенту через Telegram или email.</p>
          <div className="password-reset-list">
            {passwordResets.map(item => (
              <article className="password-reset-row" key={item.id}>
                <div>
                  <strong>{item.email}</strong>
                  <small>заявка {formatDate(item.created_at)} · последний вход {formatDate(item.last_login_at)}</small>
                  {temporaryPasswords[item.id] && <code>Временный пароль: {temporaryPasswords[item.id]}</code>}
                </div>
                <input
                  placeholder="Комментарий для истории"
                  value={resetNotes[item.id] || ''}
                  onChange={event => setResetNotes({ ...resetNotes, [item.id]: event.target.value })}
                />
                <div className="password-reset-actions">
                  <button onClick={() => void completePasswordReset(item)}><KeyRound size={15} />Сбросить пароль</button>
                  <button className="ghost small-text" onClick={() => void ignorePasswordReset(item)}>Закрыть</button>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
      <div className="client-create-panel">
        <div className="client-create-head">
          <div>
            <h2>Добавить клиента</h2>
          </div>
        </div>
        <div className="client-create-grid">
          <label className="field">
            Название клиента
            <input placeholder="ООО Ромашка" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="field">
            Telegram-ники
            <input
              placeholder="@manager, @buyer"
              value={form.telegram_usernames}
              onChange={e => setForm({ ...form, telegram_usernames: e.target.value })}
            />
          </label>
          <label className="field">
            Telegram ID вручную
            <input placeholder="Если ID известен" value={form.telegram_id} onChange={e => setForm({ ...form, telegram_id: e.target.value })} />
          </label>
          <button className="client-create-submit" onClick={() => void createClient()} disabled={!form.name.trim() || (!form.telegram_id.trim() && !parseTelegramUsernames(form.telegram_usernames).length)}>
            <Plus size={16} />Добавить
          </button>
        </div>
      </div>
      <div className="client-card-list">
        {clients.map(client => {
          const draft = accountDraft(client)
          const accounts = (client.telegram_accounts || []).filter(account => !isSyntheticWebTelegramAccount(account))
          const webUsers = client.web_users?.length ? client.web_users : []
          const expanded = Boolean(expandedClients[client.id])
          const grant = grantDraft(client)
          const debitAvailable = availableBillingUnits(client, grant.kind)
          const connectedCount = accounts.filter(account => !account.is_pending).length
          const pendingCount = accounts.filter(account => account.is_pending).length
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
                    <p>{clientSummaryLine(client, accounts)}</p>
                  </div>
                </div>
                <div className="client-summary-pills">
                  {webUsers[0]?.email && <span>{webUsers[0].email}</span>}
                  <span>Telegram: {connectedCount}</span>
                  {pendingCount > 0 && <span>Ожидают ID: {pendingCount}</span>}
                  <span>Поставщики: {client.usage ? usageSummaryText(client.usage.supplier_search) : 'нет данных'}</span>
                  <span>Анализ: {client.usage ? usageSummaryText(client.usage.procurement_report) : 'нет данных'}</span>
                </div>
                <div className="client-state">
                  {!client.is_active && <StatusBadge status="disabled" />}
                  <button className="danger small-text" onClick={() => void deleteClient(client)}>
                    <Trash2 size={14} />Удалить
                  </button>
                </div>
              </div>

              {expanded && <div className="client-card-grid">
                <div className="client-section client-telegram-section">
                  <div className="section-head">
                    <h3>Telegram-аккаунты</h3>
                    <span>{accounts.length || 'нет'}</span>
                  </div>
                  <div className="account-edit-list">
                    {accounts.map(account => {
                      const edit = accountEditDraft(account)
                      return (
                        <div className="account-edit-row" key={account.id}>
                          <label className="mini-field">
                            <span>Ник</span>
                            <input value={edit.username} placeholder="@manager" onChange={e => setAccountEditDraft(account, { username: e.target.value })} />
                          </label>
                          <label className="mini-field">
                            <span>Telegram ID</span>
                            <input value={edit.telegram_id} placeholder={account.is_pending ? 'Введите ID' : 'ID'} onChange={e => setAccountEditDraft(account, { telegram_id: e.target.value })} />
                          </label>
                          <label className="mini-field">
                            <span>Имя</span>
                            <input value={edit.name} placeholder="Имя менеджера" onChange={e => setAccountEditDraft(account, { name: e.target.value })} />
                          </label>
                          <div className="account-edit-actions">
                            {account.is_pending && <StatusBadge status="account_pending" />}
                            {!account.is_pending && !account.is_active && <StatusBadge status="disabled" />}
                            <button className="small-text" onClick={() => void saveAccount(client, account)}>
                              <Save size={14} />Сохранить
                            </button>
                            <button
                              className="icon-button small danger"
                              title="Удалить Telegram-аккаунт"
                              onClick={() => void deleteAccount(client, account)}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      )
                    })}
                    {!accounts.length && <div className="inline-note">Аккаунты пока не добавлены.</div>}
                    <div className="account-add">
                      <input placeholder="@username" value={draft.username} onChange={e => setAccountDraft(client, { username: e.target.value })} />
                      <input placeholder="ID вручную" value={draft.telegram_id} onChange={e => setAccountDraft(client, { telegram_id: e.target.value })} />
                      <input placeholder="Имя" value={draft.name} onChange={e => setAccountDraft(client, { name: e.target.value })} />
                      <button className="icon-button small" title="Добавить Telegram-аккаунт" onClick={() => void createAccount(client)} disabled={!draft.telegram_id.trim() && !draft.username.trim()}><Plus size={16} /></button>
                    </div>
                  </div>
                </div>

                <div className="client-section client-balance-section">
                  <div className="section-head">
                    <h3>Баланс</h3>
                  </div>
                  {client.usage && (
                    <div className="balance-compact-list">
                      <BalanceLine counter={client.usage.supplier_search} />
                      <BalanceLine counter={client.usage.procurement_report} />
                    </div>
                  )}
                  <div className="manual-grant-panel">
                    <label className="mini-field">
                      <span>Действие</span>
                      <select value={grant.operation} onChange={e => setGrantDraft(client, { operation: e.target.value as 'grant' | 'debit', package_id: '' })}>
                        <option value="grant">Начислить</option>
                        <option value="debit">Списать</option>
                      </select>
                    </label>
                    <label className="mini-field">
                      <span>Тип</span>
                      <select value={grant.kind} onChange={e => setGrantDraft(client, { kind: e.target.value, package_id: '' })}>
                        <option value="supplier_search">Поставщики</option>
                        <option value="procurement_report">Анализ документации</option>
                      </select>
                    </label>
                    <label className="mini-field">
                      <span>Кол-во</span>
                      <input type="number" min={1} step={1} value={grant.units} onChange={e => setGrantDraft(client, { units: e.target.value, package_id: '' })} />
                    </label>
                    <div className="quick-grants">
                      <button className="ghost small-text" onClick={() => quickGrant(client, grant.kind, 1, grant.operation)}>{grant.operation === 'debit' ? '-1' : '+1'}</button>
                      <button className="ghost small-text" onClick={() => quickGrant(client, grant.kind, 10, grant.operation)}>{grant.operation === 'debit' ? '-10' : '+10'}</button>
                      <button className="ghost small-text" onClick={() => quickGrant(client, grant.kind, 50, grant.operation)}>{grant.operation === 'debit' ? '-50' : '+50'}</button>
                    </div>
                    {grant.operation === 'grant' && (
                      <label className="mini-field grant-package-field">
                        <span>Пакет</span>
                        <select value={grant.package_id} onChange={e => applyGrantTemplate(client, e.target.value)}>
                          <option value="">Вручную</option>
                          {activeTariffs.map(item => <option key={item.id} value={item.id}>{tariffOptionLabel(item)}</option>)}
                        </select>
                      </label>
                    )}
                    {grant.operation === 'debit' && debitAvailable !== null && (
                      <div className="inline-note grant-available-note">Доступно для списания: {debitAvailable}</div>
                    )}
                    <button
                      className={grant.operation === 'debit' ? 'danger' : undefined}
                      onClick={() => void grantUnits(client)}
                      disabled={!Number.isFinite(Number(grant.units)) || Number(grant.units) < 1 || (grant.operation === 'debit' && debitAvailable !== null && Number(grant.units) > debitAvailable)}
                    >
                      {grant.operation === 'debit' ? <Minus size={16} /> : <Plus size={16} />}
                      {grant.operation === 'debit' ? 'Списать' : 'Начислить'}
                    </button>
                  </div>
                </div>

                <div className="client-section client-settings-section">
                  <h3>Настройки</h3>
                  <label className="mini-field">
                    <span>Мин. поставщиков</span>
                    <input
                      className="supplier-target-input"
                      type="number"
                      min={0}
                      max={100}
                      step={1}
                      defaultValue={client.supplier_target_min || 0}
                      onBlur={e => patchClientSupplierTarget(client, e.currentTarget)}
                    />
                  </label>
                  <details className="merge-client-details">
                    <summary>Объединение</summary>
                    <div className="merge-client-panel">
                      <label className="mini-field">
                        <span>Кого присоединить</span>
                        <select
                          value={mergeForms[client.id] || ''}
                          onChange={event => setMergeForms({ ...mergeForms, [client.id]: event.target.value })}
                        >
                          <option value="">Выберите клиента</option>
                          {clients.filter(item => item.id !== client.id).map(item => (
                            <option key={item.id} value={item.id}>{clientDisplayName(item)}</option>
                          ))}
                        </select>
                      </label>
                      <button
                        className="small-text"
                        onClick={() => void mergeClientIntoTarget(client)}
                        disabled={!mergeForms[client.id]}
                      >
                        <Users size={14} />Объединить
                      </button>
                    </div>
                  </details>
                </div>

                <details className="client-section billing-history-details">
                  <summary>
                    <span>История баланса</span>
                    <small>{client.recent_billing?.length || 0} операций</small>
                  </summary>
                  <div className="usage-history">
                    {client.recent_billing?.map(item => (
                      <div className="usage-history-row" key={item.id}>
                        <div>
                          <strong>{item.operation_label}: {item.kind_label}</strong>
                          <small>{formatDate(item.created_at)} · {item.note || item.created_by}</small>
                        </div>
                        <span>{item.units}</span>
                      </div>
                    ))}
                    {!client.recent_billing?.length && <div className="inline-note">Операций по балансу пока нет.</div>}
                  </div>
                </details>
              </div>}
            </article>
          )
        })}
      </div>
    </section>
  )
}

function parseTelegramUsernames(value: string) {
  const seen = new Set<string>()
  return value
    .split(/[\s,;]+/)
    .map(item => normalizeTelegramUsername(item))
    .filter(item => {
      if (!item || seen.has(item)) return false
      seen.add(item)
      return true
    })
}

function isSyntheticWebTelegramAccount(account: TelegramAccount) {
  return String(account.telegram_id || '').startsWith('web:')
}

function clientSummaryLine(client: Client, accounts: TelegramAccount[]) {
  if (client.web_users?.[0]?.email) {
    return client.web_users[0].email
  }
  const usernames = accounts.filter(account => account.username).map(account => `@${account.username}`).slice(0, 3)
  const connected = accounts.filter(account => !account.is_pending)
  const pending = accounts.filter(account => account.is_pending)
  if (usernames.length) {
    const more = accounts.length > usernames.length ? ` +${accounts.length - usernames.length}` : ''
    return `${usernames.join(', ')}${more} · подключено ${connected.length}, ожидает ${pending.length}`
  }
  if (client.telegram_id) return `Telegram ID: ${client.telegram_id}`
  return 'Telegram-аккаунты ожидают подключения'
}

function usageSummaryText(counter: UsageCounter) {
  return `${counter.available ?? 'без лимита'} доступно`
}

function availableBillingUnits(client: Client, kind: string) {
  const counter = kind === 'procurement_report' ? client.usage?.procurement_report : client.usage?.supplier_search
  return counter?.available ?? null
}

function BalanceLine({ counter }: { counter: UsageCounter }) {
  return (
    <div className={counter.low ? 'balance-line warning' : 'balance-line'}>
      <div>
        <strong>{counter.label}</strong>
        <small>начислено {counter.granted} · списано {counter.spent} · коррекция {counter.manual_debited || 0} · резерв {counter.reserved}</small>
      </div>
      <span>{counter.available ?? 'без лимита'}</span>
    </div>
  )
}

function tariffOptionLabel(item: TariffPackage) {
  return `${humanBillingKind(item.kind)} · ${item.name} · ${item.units} ед. · ${formatPrice(item.price_kopeks)}`
}

function humanBillingKind(kind: string) {
  return kind === 'procurement_report' ? 'Анализ документации' : 'Поставщики'
}

function formatPrice(priceKopeks: number) {
  if (!priceKopeks) return 'цена не указана'
  return `${new Intl.NumberFormat('ru-RU').format(priceKopeks / 100)} ₽`
}

function kopeksToRubles(priceKopeks: number) {
  return Math.round(Number(priceKopeks || 0)) / 100
}

function rublesToKopeks(rubles: number) {
  return Math.max(0, Math.round(Number(rubles || 0) * 100))
}

function fallbackDownloadName(job: Job, extension: string) {
  const base = String(job.human_title || job.title || humanMode(job.mode) || 'TenderLex')
    .replace(/[\\/:*?"<>|]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 90)
  return `${base || 'TenderLex'}.${extension}`
}

function JobsView({ jobs, onChange }: { jobs: Job[]; onChange: () => Promise<void> }) {
  const [expandedJobs, setExpandedJobs] = useState<Record<string, boolean>>({})
  const [jobDetails, setJobDetails] = useState<Record<string, JobDetail | JobDetailError>>({})
  const [page, setPage] = useState(1)
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
  const pageCount = Math.max(1, Math.ceil(filteredJobs.length / ADMIN_JOBS_PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const pageStart = (currentPage - 1) * ADMIN_JOBS_PAGE_SIZE
  const visibleJobs = filteredJobs.slice(pageStart, pageStart + ADMIN_JOBS_PAGE_SIZE)
  const hiddenInternalCount = showInternalJobs ? 0 : jobs.filter(job => job.is_internal).length
  const statusOptions = Array.from(new Set(jobs.map(job => job.status).filter(Boolean)))
  const modeOptions = Array.from(new Set(jobs.map(job => job.mode).filter(Boolean)))
  const shownFrom = filteredJobs.length ? pageStart + 1 : 0
  const shownTo = Math.min(filteredJobs.length, pageStart + visibleJobs.length)

  useEffect(() => {
    setPage(1)
  }, [showInternalJobs, statusFilter, modeFilter, normalizedQuery])

  async function retry(job: Job) {
    await api(`/api/jobs/${job.id}/retry`, { method: 'POST' })
    await onChange()
  }
  async function cancelJob(job: Job) {
    if (!window.confirm('Отменить задачу?')) return
    await api(`/api/jobs/${job.id}/cancel`, { method: 'POST' })
    await onChange()
  }
  async function toggleJobDetails(job: Job) {
    const nextExpanded = !expandedJobs[job.id]
    setExpandedJobs({ ...expandedJobs, [job.id]: nextExpanded })
    if (!nextExpanded || jobDetails[job.id]) return
    try {
      const payload = await api<JobDetail>(`/api/jobs/${job.id}`)
      setJobDetails(current => ({ ...current, [job.id]: payload }))
    } catch (err) {
      setJobDetails(current => ({ ...current, [job.id]: { detail_error: formatError(err) } }))
    }
  }
  async function download(job: Job, file?: JobResultFile) {
    const suffix = file ? `/${encodeURIComponent(file.kind)}` : ''
    const response = await fetch(`/api/jobs/${job.id}/download${suffix}`, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(await response.text())
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const disposition = response.headers.get('content-disposition') || ''
    const encodedName = disposition.match(/filename\*=utf-8''([^;]+)/i)?.[1]
    const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
    const fallbackExt = file?.filename.split('.').pop() || (job.mode === 'analysis_and_suppliers' ? 'zip' : job.mode === 'procurement_report' ? 'docx' : 'xlsx')
    link.href = url
    link.download = encodedName ? decodeURIComponent(encodedName) : plainName || file?.filename || fallbackDownloadName(job, fallbackExt)
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  async function downloadInputFile(job: Job, file: JobInputFile) {
    const response = await fetch(`/api/jobs/${job.id}/input-files/${file.id}/download`, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(await response.text())
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const disposition = response.headers.get('content-disposition') || ''
    const encodedName = disposition.match(/filename\*=utf-8''([^;]+)/i)?.[1]
    const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
    link.href = url
    link.download = encodedName ? decodeURIComponent(encodedName) : plainName || file.original_filename || 'input-file'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  return (
    <section className="stack">
      <div className="list-toolbar">
        <strong>Задачи: {shownFrom}-{shownTo} из {filteredJobs.length}</strong>
        {filteredJobs.length > ADMIN_JOBS_PAGE_SIZE && (
          <div className="list-pagination toolbar-pagination">
            <button className="ghost small-text" onClick={() => setPage(value => Math.max(1, value - 1))} disabled={currentPage <= 1}>Назад</button>
            <span>Страница {currentPage} из {pageCount}</span>
            <button className="ghost small-text" onClick={() => setPage(value => Math.min(pageCount, value + 1))} disabled={currentPage >= pageCount}>Вперёд</button>
          </div>
        )}
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
        {hiddenInternalCount > 0 && (
          <label>
            <input type="checkbox" checked={showInternalJobs} onChange={e => setShowInternalJobs(e.target.checked)} />
            Показать служебные проверки ({hiddenInternalCount})
          </label>
        )}
      </div>
      <div className="job-list">
        {visibleJobs.map(job => {
          const expanded = Boolean(expandedJobs[job.id])
          const details = jobDetails[job.id]
          return (
          <article className={job.is_internal ? 'job-card service' : 'job-card'} key={job.id}>
            <div className="job-main">
              <button
                className="client-expand-button"
                title={expanded ? 'Свернуть задачу' : 'Открыть задачу'}
                aria-expanded={expanded}
                onClick={() => void toggleJobDetails(job)}
              >
                {expanded ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
              </button>
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
            {job.result_files?.length > 0 && (
              <div className="job-output-list">
                {job.result_files.map(file => (
                  <button
                    key={`${job.id}-${file.kind}`}
                    className="ghost small-text"
                    onClick={() => void download(job, file)}
                    title={file.filename}
                  >
                    <Download size={14} />{file.label}
                  </button>
                ))}
              </div>
            )}
            {expanded && (
              <JobDetailsPanel
                job={job}
                details={details}
                onDownloadInput={downloadInputFile}
              />
            )}
            <div className="row-actions">
              {job.has_result && !job.result_files?.length && <button className="icon-button small" onClick={() => void download(job)} title="Скачать архив"><Download size={15} /></button>}
              {(job.status === 'running' || job.status === 'pending') && <button className="icon-button small" onClick={() => void cancelJob(job)} title="Отменить"><XCircle size={15} /></button>}
              <button className="icon-button small" onClick={() => void retry(job)} title="Перезапустить"><Play size={15} /></button>
            </div>
          </article>
          )
        })}
        {!visibleJobs.length && <div className="empty inline-empty">Нет пользовательских задач для показа.</div>}
      </div>
      {filteredJobs.length > ADMIN_JOBS_PAGE_SIZE && (
        <div className="list-pagination">
          <button className="ghost small-text" onClick={() => setPage(value => Math.max(1, value - 1))} disabled={currentPage <= 1}>Назад</button>
          <span>Страница {currentPage} из {pageCount}</span>
          <button className="ghost small-text" onClick={() => setPage(value => Math.min(pageCount, value + 1))} disabled={currentPage >= pageCount}>Вперёд</button>
        </div>
      )}
    </section>
  )
}

function JobDetailsPanel({ job, details, onDownloadInput }: { job: Job; details?: JobDetail | JobDetailError; onDownloadInput: (job: Job, file: JobInputFile) => Promise<void> }) {
  if (!details) {
    return <div className="job-detail-panel"><div className="inline-note">Загружаю детали задачи...</div></div>
  }
  if ('detail_error' in details) {
    return <div className="job-detail-panel"><div className="alert error compact">{details.detail_error}</div></div>
  }
  const files = details.files || []
  const sources = details.sources || []
  return (
    <div className="job-detail-panel">
      {(files.length > 0 || sources.length > 0) && (
        <div className="job-detail-section">
          <strong>Что загрузил клиент</strong>
          {files.map(file => (
            <button className="ghost small-text input-file-download" key={file.id} onClick={() => void onDownloadInput(job, file)}>
              <Download size={14} />{file.original_filename}
            </button>
          ))}
          {sources.map(source => (
            <span key={source.id}>{source.label || 'Ссылка'}: {source.value}</span>
          ))}
        </div>
      )}
      {!files.length && !sources.length && <div className="inline-note">Входные файлы не найдены.</div>}
      {job.error && <div className="job-detail-error">{job.error}</div>}
    </div>
  )
}

function BillingView({ tariffs, onChange }: { tariffs: TariffPackage[]; onChange: () => Promise<void> }) {
  const [newTariff, setNewTariff] = useState({ kind: 'supplier_search', name: '', units: 10, price_kopeks: 0, sort_order: 100, is_active: true })
  async function createTariff() {
    await api('/api/tariffs', { method: 'POST', body: JSON.stringify(newTariff) })
    setNewTariff({ kind: 'supplier_search', name: '', units: 10, price_kopeks: 0, sort_order: 100, is_active: true })
    await onChange()
  }
  async function patchTariff(item: TariffPackage, patch: Partial<TariffPackage>) {
    await api(`/api/tariffs/${item.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
    await onChange()
  }
  async function deleteTariff(item: TariffPackage) {
    await api(`/api/tariffs/${item.id}`, { method: 'DELETE' })
    await onChange()
  }
  const supplierTariffs = tariffs.filter(item => item.kind === 'supplier_search')
  const reportTariffs = tariffs.filter(item => item.kind === 'procurement_report')
  return (
    <section className="stack">
      <div className="form-panel full-width-panel">
        <h2>Новый пакет</h2>
        <div className="tariff-form-grid">
          <label className="field">
            <span>Тип</span>
            <select value={newTariff.kind} onChange={e => setNewTariff({ ...newTariff, kind: e.target.value })}>
              <option value="supplier_search">Поставщики</option>
              <option value="procurement_report">Анализ документации</option>
            </select>
          </label>
          <TextField label="Название" value={newTariff.name} onChange={value => setNewTariff({ ...newTariff, name: value })} />
          <NumberField label="Генераций" value={newTariff.units} onChange={value => setNewTariff({ ...newTariff, units: value })} />
          <NumberField label="Цена, ₽" value={kopeksToRubles(newTariff.price_kopeks)} onChange={value => setNewTariff({ ...newTariff, price_kopeks: rublesToKopeks(value) })} />
          <label className="switch-row"><input type="checkbox" checked={newTariff.is_active} onChange={e => setNewTariff({ ...newTariff, is_active: e.target.checked })} />Показывать клиентам</label>
        </div>
        <p className="field-help">Включённые пакеты сразу видны на сайте, в кабинете и в Telegram.</p>
        <button onClick={() => void createTariff()} disabled={!newTariff.name.trim()}><Plus size={16} />Добавить пакет</button>
      </div>

      <TariffGroup title="Поставщики" tariffs={supplierTariffs} onPatch={patchTariff} onDelete={deleteTariff} />
      <TariffGroup title="Анализ документации" tariffs={reportTariffs} onPatch={patchTariff} onDelete={deleteTariff} />
    </section>
  )
}

function TariffGroup({ title, tariffs, onPatch, onDelete }: { title: string; tariffs: TariffPackage[]; onPatch: (item: TariffPackage, patch: Partial<TariffPackage>) => Promise<void>; onDelete: (item: TariffPackage) => Promise<void> }) {
  return (
    <div className="form-panel full-width-panel">
      <div className="panel-heading">
        <h2>{title}</h2>
        <span className="sync-note">Сайт + кабинет + Telegram</span>
      </div>
      <div className="tariff-list">
        {tariffs.map(item => (
          <article className={item.is_active ? 'tariff-row' : 'tariff-row muted'} key={item.id}>
            <label className="mini-field"><span>Название</span><input defaultValue={item.name} aria-label="Название пакета" onBlur={e => void onPatch(item, { name: e.currentTarget.value })} /></label>
            <label className="mini-field"><span>Генераций</span><input type="number" min={1} defaultValue={item.units} aria-label="Генераций" onBlur={e => void onPatch(item, { units: Number(e.currentTarget.value) })} /></label>
            <label className="mini-field"><span>Цена, ₽</span><input type="number" min={0} step={1} defaultValue={kopeksToRubles(item.price_kopeks)} aria-label="Цена в рублях" onBlur={e => void onPatch(item, { price_kopeks: rublesToKopeks(Number(e.currentTarget.value)) })} /></label>
            <label className="switch-row tariff-active"><input type="checkbox" checked={item.is_active} onChange={e => void onPatch(item, { is_active: e.target.checked })} /> Показывать клиентам</label>
            <button className="icon-button small" title="Удалить пакет" onClick={() => void onDelete(item)}><Trash2 size={15} /></button>
          </article>
        ))}
        {!tariffs.length && <div className="empty inline-empty">Пакеты ещё не добавлены.</div>}
      </div>
    </div>
  )
}

function SettingsView({ settings, onChange }: { settings: SettingsPayload; onChange: () => Promise<void> }) {
  const [draft, setDraft] = useState(settings)
  const [adapterKey, setAdapterKey] = useState('')
  const [yandexKey, setYandexKey] = useState('')
  const [googleKey, setGoogleKey] = useState('')
  const [yookassaSecret, setYookassaSecret] = useState('')
  const searchUi = draft.supplier_search_ui
  useEffect(() => setDraft(settings), [settings])
  useEffect(() => {
    void api<{ supplier_search_adapter_api_key?: string; yandex_search_api_key?: string; google_search_api_key?: string; yookassa_secret_key?: string }>('/api/settings/keys')
      .then(data => {
        setAdapterKey(data.supplier_search_adapter_api_key || '')
        setYandexKey(data.yandex_search_api_key || '')
        setGoogleKey(data.google_search_api_key || '')
        setYookassaSecret(data.yookassa_secret_key || '')
      })
      .catch(() => {
        setAdapterKey('')
        setYandexKey('')
        setGoogleKey('')
        setYookassaSecret('')
      })
  }, [])
  async function save() {
    const payload: SettingsPatchPayload = {
      ...draft,
      supplier_search_adapter_api_key: adapterKey,
      yandex_search_api_key: yandexKey,
      google_search_api_key: googleKey,
      supplier_search_provider_order: draft.supplier_search_provider_order || 'yandex,google,tavily,ddgs',
    }
    if (yookassaSecret.trim() || !settings.yookassa_secret_key_set) {
      payload.yookassa_secret_key = yookassaSecret
    }
    await api('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    await onChange()
  }
  return (
    <section className="settings-grid">
      <div className="form-panel full">
        <h2>Контакты и ручная оплата</h2>
        <div className="settings-grid compact-grid">
          <TextField label="Telegram-бот для работы" value={draft.bot_telegram} onChange={value => setDraft({ ...draft, bot_telegram: value })} />
          <TextField label="Telegram для связи и оплаты" value={draft.contact_telegram} onChange={value => setDraft({ ...draft, contact_telegram: value })} />
          <TextField label="Email" value={draft.contact_email} onChange={value => setDraft({ ...draft, contact_email: value })} />
          <TextField label="MAX телефон для показа" value={draft.contact_max} onChange={value => setDraft({ ...draft, contact_max: value })} />
          <TextField label="MAX ссылка из приложения" value={draft.contact_max_link} onChange={value => setDraft({ ...draft, contact_max_link: value })} />
          <TextField label="Сайт" value={draft.contact_website} onChange={value => setDraft({ ...draft, contact_website: value })} />
        </div>
        <p className="field-help">Приоритетная связь для клиентов — Telegram. Для рабочей кнопки MAX вставьте ссылку, скопированную в приложении MAX через профиль, QR или приглашение; телефон используется только как текст рядом с контактом.</p>
        <TextArea className="payment-textarea" label="Инструкция ручной оплаты" value={draft.payment_instructions} onChange={value => setDraft({ ...draft, payment_instructions: value })} />
      </div>
      <div className="form-panel full">
        <h2>YooKassa</h2>
        <div className="settings-grid compact-grid">
          <label className="field">
            <span>Режим оплаты</span>
            <select value={draft.payment_provider} onChange={e => setDraft({ ...draft, payment_provider: e.target.value })}>
              <option value="manual">Ручная оплата</option>
              <option value="yookassa">YooKassa</option>
            </select>
          </label>
          <TextField label="Shop ID" value={draft.yookassa_shop_id} onChange={value => setDraft({ ...draft, yookassa_shop_id: value })} />
          <TextField label="Return URL" value={draft.yookassa_return_url} onChange={value => setDraft({ ...draft, yookassa_return_url: value })} />
          <SecretField label="Secret key" value={yookassaSecret} onChange={setYookassaSecret} />
        </div>
        <p className="field-help">Пока YooKassa не подключена, клиентам показываются ручная инструкция, Telegram, MAX, email и сайт. Реквизиты не подставляются автоматически.</p>
      </div>
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
  const [supplierProvider, setSupplierProvider] = useState(settings.supplier_ai_provider || settings.light_provider)
  const [supplierModel, setSupplierModel] = useState(settings.supplier_ai_model || settings.light_model)
  const [analysisFallback, setAnalysisFallback] = useState<FallbackEntry[]>(() => parseJson(settings.ai_analysis_fallback_json, []))
  const [supplierFallback, setSupplierFallback] = useState<FallbackEntry[]>(() => parseJson(settings.ai_supplier_fallback_json, []))
  const [testResults, setTestResults] = useState<Record<string, AiTestState>>({})
  const [saveStatus, setSaveStatus] = useState<Record<string, string>>({})

  useEffect(() => {
    const parsedModels = parseJson<SavedModel[]>(settings.saved_models_json, [])
    setProviders(ensureModelProviders(parseJson(settings.custom_ai_providers_json, []), parsedModels))
    setSavedModels(parsedModels)
    setFunctionModels(parseJson(settings.ai_function_models_json, {}))
    setPrimaryProvider(settings.primary_provider)
    setPrimaryModel(settings.primary_model)
    setLightProvider(settings.light_provider)
    setLightModel(settings.light_model)
    setSupplierProvider(settings.supplier_ai_provider || settings.light_provider)
    setSupplierModel(settings.supplier_ai_model || settings.light_model)
    setAnalysisFallback(parseJson(settings.ai_analysis_fallback_json, []))
    setSupplierFallback(parseJson(settings.ai_supplier_fallback_json, []))
  }, [settings])

  const modelOptions = useMemo(
    () => savedModels.filter(model => model.provider && model.modelId).map(model => `${model.provider}:${model.modelId}`),
    [savedModels],
  )
  const providersById = useMemo(() => new Map(providers.map(provider => [provider.id, provider])), [providers])
  function providerDisplayName(providerId: string) {
    const provider = providersById.get(providerId)
    return isKnownProviderId(providerId)
      ? canonicalProviderName(providerId)
      : (provider?.name || providerId || 'Custom provider')
  }
  function modelOptionLabel(raw: string) {
    const [providerId, ...rest] = raw.split(':')
    const modelId = rest.join(':')
    const providerName = providerDisplayName(providerId)
    return `${providerName} · ${modelId || raw}`
  }
  function providerOptionLabel(provider: CustomProvider) {
    return providerDisplayName(provider.id)
  }
  function selectedModelSummary(providerId: string, modelId: string) {
    if (!providerId || !modelId) return 'Модель не выбрана'
    return modelOptionLabel(`${providerId}:${modelId}`)
  }
  function currentModelValue(role: string) {
    if (role === '__light__') return lightProvider && lightModel ? `${lightProvider}:${lightModel}` : ''
    return primaryProvider && primaryModel ? `${primaryProvider}:${primaryModel}` : ''
  }
  function functionRoleValue(raw: string | undefined) {
    const value = String(raw || '').trim()
    if (value === '__light__') return '__light__'
    if (value === '__primary__' || !value) return '__primary__'
    if (value === currentModelValue('__light__')) return '__light__'
    return '__primary__'
  }
  function explicitFunctionModels() {
    const result: Record<string, string> = {}
    for (const key of procurementAiRoutingKeys) {
      result[key] = functionRoleValue(functionModels[key])
    }
    for (const key of supplierAiRoutingKeys) {
      result[key] = '__supplier_search__'
    }
    return result
  }
  function clearSaveStatus(section: string) {
    setSaveStatus(current => {
      if (!current[section]) return current
      const next = { ...current }
      delete next[section]
      return next
    })
  }
  function clearSaveStatuses(...sections: string[]) {
    setSaveStatus(current => {
      let changed = false
      const next = { ...current }
      for (const section of sections) {
        if (next[section]) {
          delete next[section]
          changed = true
        }
      }
      return changed ? next : current
    })
  }
  function normalizedSavedModels() {
    return savedModels
      .map(model => ({
        ...model,
        id: model.id || crypto.randomUUID(),
        name: '',
        provider: String(model.provider || '').trim(),
        modelId: String(model.modelId || '').trim(),
      }))
      .filter(model => model.provider && model.modelId)
  }
  function updateFunctionModel(key: string, role: string) {
    setFunctionModels(current => {
      return { ...current, [key]: role === '__light__' ? '__light__' : '__primary__' }
    })
    clearSaveStatus('functions')
  }

  function addProvider() {
    let index = providers.length + 1
    let id = `custom-provider-${index}`
    while (providers.some(provider => provider.id === id)) {
      index += 1
      id = `custom-provider-${index}`
    }
    setProviders([...providers, { id, name: 'Custom provider', baseUrl: '', apiKey: '', model: '' }])
    clearSaveStatus('providers')
  }
  function addModel() {
    const lastModel = savedModels[savedModels.length - 1]
    if (lastModel && !lastModel.modelId.trim()) return
    setSavedModels([...savedModels, { id: crypto.randomUUID(), name: '', provider: providers[0]?.id || '', modelId: '' }])
    clearSaveStatus('models')
  }
  function moveProvider(index: number, delta: number) {
    setProviders(moveArrayItem(providers, index, delta))
    clearSaveStatus('providers')
  }
  function moveModel(index: number, delta: number) {
    setSavedModels(moveArrayItem(savedModels, index, delta))
    clearSaveStatus('models')
  }
  function isPaidFallbackEntry(provider: string, model: string) {
    const pid = String(provider || '').trim().toLowerCase()
    if (pid === 'polza') return true
    if (pid === 'openrouter' && !String(model || '').includes(':free')) return true
    return false
  }
  function normalizedFallbackList(list: FallbackEntry[]) {
    return list
      .map(entry => ({ provider: String(entry.provider || '').trim(), modelId: String(entry.modelId || '').trim() }))
      .filter(entry => entry.provider && entry.modelId)
  }
  function addFallbackItem(list: FallbackEntry[], setList: (next: FallbackEntry[]) => void, section: string) {
    const last = list[list.length - 1]
    if (last && !last.modelId.trim()) return
    setList([...list, { provider: providers[0]?.id || '', modelId: '' }])
    clearSaveStatus(section)
  }
  function moveFallbackItem(list: FallbackEntry[], setList: (next: FallbackEntry[]) => void, index: number, delta: number, section: string) {
    setList(moveArrayItem(list, index, delta))
    clearSaveStatus(section)
  }
  function updateFallbackItem(list: FallbackEntry[], setList: (next: FallbackEntry[]) => void, index: number, value: string, section: string) {
    const [provider, ...rest] = value.split(':')
    setList(list.map((item, itemIndex) => (itemIndex === index ? { provider: (provider || '').trim(), modelId: rest.join(':').trim() } : item)))
    clearSaveStatus(section)
  }
  function removeFallbackItem(list: FallbackEntry[], setList: (next: FallbackEntry[]) => void, index: number, section: string) {
    setList(list.filter((_, itemIndex) => itemIndex !== index))
    clearSaveStatus(section)
  }
  function renderFallbackEditor(list: FallbackEntry[], setList: (next: FallbackEntry[]) => void, section: string) {
    return (
      <div className="advanced-section">
        <button className="ghost ai-add-button" onClick={() => addFallbackItem(list, setList, section)}><Plus size={16} />Добавить модель</button>
        <p className="field-help">Пробуются по порядку, если основная модель недоступна. В конце автоматически добавляются оставшиеся бесплатные модели. Выберите из списка «Доступные модели».</p>
        {list.length > 0 && (
          <div className="model-row-head"><span>Модель</span><span></span><span></span></div>
        )}
        {list.map((entry, index) => (
          <div className="model-row" key={`${entry.provider}:${entry.modelId}-${index}`}>
            <select
              value={entry.provider && entry.modelId ? `${entry.provider}:${entry.modelId}` : ''}
              onChange={event => updateFallbackItem(list, setList, index, event.target.value, section)}
            >
              <option value="">Выберите модель</option>
              {modelOptions.map(option => <option key={option} value={option}>{modelOptionLabel(option)}</option>)}
            </select>
            <span className="row-cell-badge">
              {isPaidFallbackEntry(entry.provider, entry.modelId) ? <span className="badge-paid" title="Платная модель — используется по вашему выбору">платная</span> : null}
            </span>
            <RowActions
              index={index}
              count={list.length}
              onMoveUp={() => moveFallbackItem(list, setList, index, -1, section)}
              onMoveDown={() => moveFallbackItem(list, setList, index, 1, section)}
              onRemove={() => removeFallbackItem(list, setList, index, section)}
              removeTitle="Удалить из фолбэка"
            />
          </div>
        ))}
        {list.length === 0 && (
          <p className="field-help">Список пуст — после основной модели автоматически идут оставшиеся бесплатные модели.</p>
        )}
      </div>
    )
  }
  function removeProvider(index: number) {
    const provider = providers[index]
    if (!provider) return
    const relatedModels = savedModels.filter(model => model.provider === provider.id)
    const message = relatedModels.length
      ? `Удалить провайдера «${providerOptionLabel(provider)}» и ${relatedModels.length} связанных моделей?`
      : `Удалить провайдера «${providerOptionLabel(provider)}»?`
    if (!window.confirm(message)) return
    setProviders(providers.filter((_, itemIndex) => itemIndex !== index))
    setSavedModels(savedModels.filter(model => model.provider !== provider.id))
    if (primaryProvider === provider.id) {
      setPrimaryProvider('')
      setPrimaryModel('')
    }
    if (lightProvider === provider.id) {
      setLightProvider('')
      setLightModel('')
    }
    if (supplierProvider === provider.id) {
      setSupplierProvider('')
      setSupplierModel('')
    }
    clearSaveStatuses('providers', 'models', 'global', 'supplier')
  }
  function removeModel(index: number) {
    const model = savedModels[index]
    if (!model) return
    setSavedModels(savedModels.filter((_, itemIndex) => itemIndex !== index))
    if (primaryProvider === model.provider && primaryModel === model.modelId) {
      setPrimaryProvider('')
      setPrimaryModel('')
    }
    if (lightProvider === model.provider && lightModel === model.modelId) {
      setLightProvider('')
      setLightModel('')
    }
    if (supplierProvider === model.provider && supplierModel === model.modelId) {
      setSupplierProvider('')
      setSupplierModel('')
    }
    clearSaveStatuses('models', 'global', 'supplier')
  }
  async function saveSection(section: string, payload: Partial<SettingsPayload>) {
    await api('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    setSaveStatus(current => ({ ...current, [section]: 'Сохранено' }))
    await onChange()
  }
  async function saveFunctionModelSettings() {
    await saveSection('functions', { ai_function_models_json: stringify(explicitFunctionModels()) })
  }
  async function saveGlobalModelSettings() {
    await saveSection('global', {
      primary_provider: primaryProvider,
      primary_model: primaryModel,
      light_provider: lightProvider,
      light_model: lightModel,
      ai_function_models_json: stringify(explicitFunctionModels()),
      ai_analysis_fallback_json: stringify(normalizedFallbackList(analysisFallback)),
    })
  }
  async function saveSupplierModelSettings() {
    await saveSection('supplier', {
      supplier_ai_provider: supplierProvider,
      supplier_ai_model: supplierModel,
      ai_function_models_json: stringify(explicitFunctionModels()),
      ai_supplier_fallback_json: stringify(normalizedFallbackList(supplierFallback)),
    })
  }
  async function saveProviderSettings() {
    const normalizedProviders = providers.filter(provider => provider.id.trim()).map(normalizeProvider)
    const providerIds = new Set(normalizedProviders.map(provider => provider.id))
    const nextModels = normalizedSavedModels().filter(model => providerIds.has(model.provider))
    const modelValues = new Set(nextModels.map(model => `${model.provider}:${model.modelId}`))
    const primaryValue = primaryProvider && primaryModel ? `${primaryProvider}:${primaryModel}` : ''
    const lightValue = lightProvider && lightModel ? `${lightProvider}:${lightModel}` : ''
    const supplierValue = supplierProvider && supplierModel ? `${supplierProvider}:${supplierModel}` : ''
    await saveSection('providers', {
      custom_ai_providers_json: stringify(normalizedProviders),
      saved_models_json: stringify(nextModels),
      primary_provider: primaryValue && modelValues.has(primaryValue) ? primaryProvider : '',
      primary_model: primaryValue && modelValues.has(primaryValue) ? primaryModel : '',
      light_provider: lightValue && modelValues.has(lightValue) ? lightProvider : '',
      light_model: lightValue && modelValues.has(lightValue) ? lightModel : '',
      supplier_ai_provider: supplierValue && modelValues.has(supplierValue) ? supplierProvider : '',
      supplier_ai_model: supplierValue && modelValues.has(supplierValue) ? supplierModel : '',
      ai_function_models_json: stringify(explicitFunctionModels()),
    })
  }
  async function saveModelListSettings() {
    const normalizedModels = normalizedSavedModels()
    const modelValues = new Set(normalizedModels.map(model => `${model.provider}:${model.modelId}`))
    const primaryValue = primaryProvider && primaryModel ? `${primaryProvider}:${primaryModel}` : ''
    const lightValue = lightProvider && lightModel ? `${lightProvider}:${lightModel}` : ''
    const supplierValue = supplierProvider && supplierModel ? `${supplierProvider}:${supplierModel}` : ''
    await saveSection('models', {
      saved_models_json: stringify(normalizedModels),
      primary_provider: !primaryValue || modelValues.has(primaryValue) ? primaryProvider : '',
      primary_model: !primaryValue || modelValues.has(primaryValue) ? primaryModel : '',
      light_provider: !lightValue || modelValues.has(lightValue) ? lightProvider : '',
      light_model: !lightValue || modelValues.has(lightValue) ? lightModel : '',
      supplier_ai_provider: !supplierValue || modelValues.has(supplierValue) ? supplierProvider : '',
      supplier_ai_model: !supplierValue || modelValues.has(supplierValue) ? supplierModel : '',
      ai_function_models_json: stringify(explicitFunctionModels()),
    })
  }
  async function testAi(slot: string, provider: string, model: string) {
    setTestResults(current => ({
      ...current,
      [slot]: {
        status: 'running',
        message: `Проверяю: ${selectedModelSummary(provider, model)}`,
      },
    }))
    try {
      const result = await api<{ response: string; provider_name?: string; model?: string }>('/api/ai/test', {
        method: 'POST',
        body: JSON.stringify({ provider, model }),
      })
      setTestResults(current => ({
        ...current,
        [slot]: {
          status: 'success',
          message: result.response || 'Модель ответила без текста.',
          providerName: result.provider_name || providerDisplayName(provider),
          model: result.model || model,
        },
      }))
    } catch (err) {
      setTestResults(current => ({
        ...current,
        [slot]: {
          status: 'error',
          message: formatError(err),
          providerName: providerDisplayName(provider),
          model,
        },
      }))
    }
  }
  function testButton(slot: string, provider: string, model: string) {
    const running = testResults[slot]?.status === 'running'
    return (
      <button
        className="icon-button small"
        title="Проверить эту модель"
        onClick={() => void testAi(slot, provider, model)}
        disabled={!provider || !model || running}
      >
        {running ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} />}
      </button>
    )
  }
  function renderTestResult(slot: string) {
    const result = testResults[slot]
    if (!result) return null
    return (
      <div className={`test-result ${result.status}`}>
        {result.status === 'success' && <CheckCircle2 size={16} />}
        {result.status === 'error' && <XCircle size={16} />}
        {result.status === 'running' && <Loader2 size={16} className="spin" />}
        <span>
          {result.providerName && result.model && <strong>{result.providerName} · {result.model}</strong>}
          {result.message}
        </span>
      </div>
    )
  }
  function sectionSaveStatus(section: string) {
    return saveStatus[section] ? <span className="save-status">{saveStatus[section]}</span> : null
  }
  return (
    <section className="ai-settings">
      <div className="ai-top-grid">
        <details className="service-panel ai-panel" open>
          <summary>Анализ документации</summary>
          <ModelSelect
            label="Основная модель анализа"
            value={primaryProvider && primaryModel ? `${primaryProvider}:${primaryModel}` : ''}
            options={modelOptions}
            optionLabel={modelOptionLabel}
            action={testButton('primary', primaryProvider, primaryModel)}
            status={renderTestResult('primary')}
            onChange={(provider, model) => {
              setPrimaryProvider(provider)
              setPrimaryModel(model)
              clearSaveStatus('global')
            }}
          />
          <ModelSelect
            label="Быстрая модель анализа"
            value={lightProvider && lightModel ? `${lightProvider}:${lightModel}` : ''}
            options={modelOptions}
            optionLabel={modelOptionLabel}
            action={testButton('light', lightProvider, lightModel)}
            status={renderTestResult('light')}
            onChange={(provider, model) => {
              setLightProvider(provider)
              setLightModel(model)
              clearSaveStatus('global')
            }}
          />
          <div className="fallback-block">
            <p className="field-help"><strong>Резервные модели (фолбэк) для анализа</strong></p>
            {renderFallbackEditor(analysisFallback, setAnalysisFallback, 'global')}
          </div>
          <div className="section-actions">
            <button onClick={() => void saveGlobalModelSettings()}><Save size={16} />Сохранить анализ</button>
            {sectionSaveStatus('global')}
          </div>
        </details>
        <details className="service-panel ai-panel" open>
          <summary>Поиск поставщиков</summary>
          <ModelSelect
            label="Модель поиска поставщиков"
            help="Здесь можно выбрать более дешёвую и быструю модель: она применяется ко всем ИИ-этапам поиска поставщиков."
            value={supplierProvider && supplierModel ? `${supplierProvider}:${supplierModel}` : ''}
            options={modelOptions}
            optionLabel={modelOptionLabel}
            action={testButton('supplier', supplierProvider, supplierModel)}
            status={renderTestResult('supplier')}
            onChange={(provider, model) => {
              setSupplierProvider(provider)
              setSupplierModel(model)
              clearSaveStatus('supplier')
            }}
          />
          <div className="fallback-block">
            <p className="field-help"><strong>Резервные модели (фолбэк) для поиска поставщиков</strong></p>
            {renderFallbackEditor(supplierFallback, setSupplierFallback, 'supplier')}
          </div>
          <div className="section-actions">
            <button onClick={() => void saveSupplierModelSettings()}><Save size={16} />Сохранить поиск</button>
            {sectionSaveStatus('supplier')}
          </div>
        </details>
      </div>
      <details className="service-panel ai-panel">
        <summary>Маршруты анализа документации</summary>
        <p className="field-help">Для отдельных этапов анализа можно выбрать основную или быструю модель. Поиск поставщиков здесь не дробится.</p>
          <div className="function-route-list">
            {procurementAiRoutingKeys.map(key => {
              const value = functionRoleValue(functionModels[key])
              return (
                <label className="function-route-row" key={key}>
                  <span>{functionLabels[key] || key}</span>
                  <select value={value} onChange={event => updateFunctionModel(key, event.target.value)}>
                    <option value="__primary__">{modelRoleLabels.__primary__}</option>
                    <option value="__light__">{modelRoleLabels.__light__}</option>
                  </select>
                </label>
              )
            })}
          </div>
          <div className="section-actions">
            <button onClick={() => void saveFunctionModelSettings()}><Save size={16} />Сохранить маршруты</button>
            {sectionSaveStatus('functions')}
          </div>
      </details>
      <details className="service-panel ai-panel">
        <summary>Провайдеры ИИ</summary>
        <div className="advanced-section">
          <button className="ghost ai-add-button" onClick={addProvider}><Plus size={16} />Добавить провайдера</button>
          <div className="provider-row-head"><span>Код</span><span>Название</span><span>Адрес API</span><span>Ключ API</span><span></span></div>
          {providers.map((provider, index) => (
            <div className="provider-row" key={`${provider.id}-${index}`}>
              <input value={provider.id} placeholder="например openrouter" onChange={e => { updateArray(providers, setProviders, index, { id: e.target.value }); clearSaveStatus('providers') }} />
              <input value={provider.name} placeholder={canonicalProviderName(provider.id)} onChange={e => { updateArray(providers, setProviders, index, { name: e.target.value }); clearSaveStatus('providers') }} />
              <input value={provider.baseUrl} placeholder="https://.../v1" onChange={e => { updateArray(providers, setProviders, index, { baseUrl: e.target.value }); clearSaveStatus('providers') }} />
              <input type="password" value={provider.apiKey} placeholder="Ключ API" onChange={e => { updateArray(providers, setProviders, index, { apiKey: e.target.value }); clearSaveStatus('providers') }} />
              <RowActions
                index={index}
                count={providers.length}
                onMoveUp={() => moveProvider(index, -1)}
                onMoveDown={() => moveProvider(index, 1)}
                onRemove={() => removeProvider(index)}
                removeTitle="Удалить провайдера"
              />
            </div>
          ))}
          <div className="section-actions">
            <button onClick={() => void saveProviderSettings()}><Save size={16} />Сохранить провайдеров</button>
            {sectionSaveStatus('providers')}
          </div>
        </div>
      </details>
      <details className="service-panel ai-panel">
        <summary>Доступные модели</summary>
        <div className="advanced-section">
          <button className="ghost ai-add-button" onClick={addModel}><Plus size={16} />Добавить модель</button>
          <div className="model-row-head"><span>Провайдер</span><span>Модель</span><span></span></div>
          {savedModels.map((model, index) => (
            <div className="model-row" key={model.id}>
              <select value={model.provider} onChange={e => { updateArray(savedModels, setSavedModels, index, { provider: e.target.value }); clearSaveStatus('models') }}>
                <option value="">Провайдер</option>
                {providers.map(provider => <option key={provider.id} value={provider.id}>{providerOptionLabel(provider)}</option>)}
              </select>
              <input value={model.modelId} placeholder="например gpt-5.4" onChange={e => { updateArray(savedModels, setSavedModels, index, { modelId: e.target.value }); clearSaveStatus('models') }} />
              <RowActions
                index={index}
                count={savedModels.length}
                onMoveUp={() => moveModel(index, -1)}
                onMoveDown={() => moveModel(index, 1)}
                onRemove={() => removeModel(index)}
                removeTitle="Удалить модель"
              />
            </div>
          ))}
          <div className="section-actions">
            <button onClick={() => void saveModelListSettings()}><Save size={16} />Сохранить модели</button>
            {sectionSaveStatus('models')}
          </div>
        </div>
      </details>
    </section>
  )
}

function moveArrayItem<T>(items: T[], index: number, delta: number) {
  const nextIndex = index + delta
  if (nextIndex < 0 || nextIndex >= items.length) return items
  const next = [...items]
  const [item] = next.splice(index, 1)
  next.splice(nextIndex, 0, item)
  return next
}

function RowActions({
  index,
  count,
  onMoveUp,
  onMoveDown,
  onRemove,
  removeTitle,
}: {
  index: number
  count: number
  onMoveUp: () => void
  onMoveDown: () => void
  onRemove: () => void
  removeTitle: string
}) {
  return (
    <div className="row-actions">
      <button className="icon-button small" title="Поднять выше" onClick={onMoveUp} disabled={index === 0}><ArrowUp size={14} /></button>
      <button className="icon-button small" title="Опустить ниже" onClick={onMoveDown} disabled={index >= count - 1}><ArrowDown size={14} /></button>
      <button className="icon-button small danger" title={removeTitle} onClick={onRemove}><Trash2 size={14} /></button>
    </div>
  )
}

function updateArray<T>(items: T[], setter: (value: T[]) => void, index: number, patch: Partial<T>) {
  setter(items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
}

function ModelSelect({
  label,
  help = '',
  value,
  options,
  optionLabel = option => option,
  action,
  status,
  onChange,
}: {
  label: string
  help?: string
  value: string
  options: string[]
  optionLabel?: (option: string) => string
  action?: ReactNode
  status?: ReactNode
  onChange: (provider: string, model: string) => void
}) {
  return (
    <div className="field">
      <span>{label}</span>
      <div className="model-select-row">
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
        {action}
      </div>
      {help && <small className="field-help">{help}</small>}
      {status}
    </div>
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

function TextArea({ label, value, onChange, className = '' }: { label: string; value: string; onChange: (value: string) => void; className?: string }) {
  return <label className={className ? `field ${className}` : 'field'}><span>{label}</span><textarea value={value || ''} onChange={e => onChange(e.target.value)} /></label>
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
