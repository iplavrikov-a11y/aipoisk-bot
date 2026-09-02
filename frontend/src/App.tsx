import { memo, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  X,
  AlertTriangle,
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
  ExternalLink,
  FileText,
  Globe,
  HardDrive,
  KeyRound,
  Loader2,
  LogIn,
  MemoryStick,
  Minus,
  MoreHorizontal,
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
  Upload,
  Users,
  XCircle,
  Mail,
  MessageSquarePlus,
  Send,
  TrendingUp,
  TrendingDown,
  Activity,
  Calendar,
  Crown,
} from 'lucide-react'
import { OutreachView } from './OutreachView'
import { McpApiView } from './McpApiView'

type View = 'dashboard' | 'seo' | 'clients' | 'jobs' | 'billing' | 'settings' | 'ai' | 'outreach' | 'mcp'

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
  created_at?: string | null
  updated_at?: string | null
  onboarding?: {
    last_event: string
    last_channel: string
    last_mode: string
    last_outcome: string
    last_reason_code: string
    last_event_at: string | null
  } | null
}

type ClientUsage = {
  supplier_search: UsageCounter
  procurement_report: UsageCounter
  supplier_search_extra: UsageCounter
  exact_product?: UsageCounter
  money?: {
    balance_kopeks: number
    reserved_kopeks: number
    available_kopeks: number
    balance_rub: number
    reserved_rub: number
    available_rub: number
  }
  effective_prices?: Record<string, { label: string; price_kopeks: number; price_rub: number; enabled: boolean; source: string }>
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
  price_kopeks?: number
  price_rub?: number
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
  created_at?: string | null
  updated_at?: string | null
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
  amount_rub: string
  debit_amount_rub?: string
}

type Job = {
  id: string
  client_id: string
  client_name: string
  telegram_id: string
  created_by_telegram_id: string
  mode: string
  mode_label: string
  supplier_search_policy: string
  supplier_search_run_type: string
  confirmation_kind?: string
  confirmation_outcome?: string
  offer_delivery_outcome?: string
  result_offer?: JobResultOffer | null
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
  has_admin_supplement?: boolean
  admin_comment?: string
  admin_supplement_name?: string
  admin_supplement_at?: string | null
  error: string
  ai_provider?: string
  ai_provider_name?: string
  ai_model?: string
  ai_label?: string
  created_at: string
  updated_at: string | null
  completed_at: string | null
  yandex_requests_count?: number
  yandex_cost_rub?: number
  yandex_cost_label?: string
  input_files?: JobInputFile[]
  sources?: JobSource[]
  parent_job_id?: string
  is_admin_rerun?: boolean
}

type JobResultOffer = {
  kind: string
  registry_verified_count: number
  alternative_verified_count: number
  decision_expires_at?: string | null
  decision_outcome?: string
  delivery_expires_at?: string | null
  delivery_outcome?: string
  active_manifest_version?: number
  charge_amount_kopeks?: number
  charge_units?: number
  can_accept?: boolean
  can_decline?: boolean
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
  onboarding_reminders_enabled: boolean
  onboarding_reminders_rollout_at: string
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
  amount_kopeks: number
  amount_rub: number
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
    period: Array<{
      kind: string
      label: string
      granted: number
      reserved: number
      charged: number
      released: number
      manual_debited: number
      granted_amount_kopeks: number
      reserved_amount_kopeks: number
      charged_amount_kopeks: number
      released_amount_kopeks: number
      manual_debited_amount_kopeks: number
    }>
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
    warning?: boolean
    note: string
    url?: string
  }>
  warnings: string[]
}

type MinpromRegistryStatus = {
  xlsx_exists: boolean
  xlsx_path: string
  xlsx_size_bytes: number
  index_exists: boolean
  index_path: string
  index_size_bytes: number
  sqlite_exists: boolean
  sqlite_path: string
  sqlite_size_bytes: number
  sqlite_ready: boolean
  sqlite_fresh: boolean
  sqlite_entry_count: number
  sqlite_fts_count: number
  sqlite_integrity: string
  sqlite_schema_version?: string
  source_url: string
  filename?: string
  index_count?: number
  sqlite_count?: number
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
    title: 'Сводка и аналитика',
    description: 'Ключевые показатели сервиса, динамика запусков, состояние серверов и активность клиентов.',
  },
  clients: {
    title: 'Клиенты',
    description: 'Клиенты из Telegram и сайта, денежный баланс, цены списания и привязанные аккаунты.',
  },
  jobs: {
    title: 'Задачи',
    description: 'Последние запуски бота, статусы обработки и готовые файлы для скачивания.',
  },
  billing: {
    title: 'Тарифы',
    description: 'Глобальные цены услуг и тарифные пакеты для клиентского кабинета.',
  },
  settings: {
    title: 'Настройки',
    description: 'Контакты, пополнение через менеджера, триал, хранение файлов и источники поиска.',
  },
  ai: {
    title: 'ИИ-модели',
    description: 'Выбор моделей для анализа документации, поиска поставщиков и проверки результатов.',
  },
  seo: {
    title: 'SEO и Трафик сайта',
    description: 'Автоматический фоновый сбор данных Яндекс.Метрики и Вебмастера, поисковые фразы и накопление статистики.',
  },
  outreach: {
    title: 'Лидогенерация и Рассылка',
    description: 'Массовый поиск B2B контактов по нише, отправка email-рассылок через info@tenderlex.ru и входящие ответы.',
  },
  mcp: {
    title: 'MCP & Public API',
    description: 'Управление API-ключами, интеграция с Claude Desktop, Cursor, ChatGPT Codex и прямое подключение внешних систем.',
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
  delivery_expired: 'срок выдачи истёк',
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
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    credentials: 'same-origin',
    headers: isFormData
      ? { ...(init.headers || {}) }
      : {
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

function onboardingStageLabel(eventName: string) {
  return ({
    account_created: 'создан кабинет',
    bot_started: 'открыт бот',
    create_opened: 'открыто создание',
    mode_selected: 'выбран сценарий',
    input_added: 'добавлены материалы',
    launch_attempted: 'попытка запуска',
    launch_blocked: 'запуск остановлен',
    job_created: 'задача создана',
    link_requested: 'запрошена привязка',
    link_succeeded: 'аккаунты связаны',
    link_conflict: 'конфликт привязки',
    onboarding_reminder_sent: 'отправлена подсказка',
  } as Record<string, string>)[eventName] || eventName
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

function registryFallbackOffer(job: Job) {
  const offer = job.result_offer
  const kind = String(offer?.kind || job.confirmation_kind || '')
  if (kind !== 'registry_fallback') return null
  return {
    decision: String(offer?.decision_outcome || job.confirmation_outcome || ''),
    delivery: String(offer?.delivery_outcome || job.offer_delivery_outcome || ''),
    count: Math.max(0, Number(offer?.alternative_verified_count ?? job.verified_count ?? 0)),
  }
}

function registryFallbackStatusLabel(job: Job) {
  const offer = registryFallbackOffer(job)
  if (!offer) return ''
  if (offer.decision === 'accepted') {
    if (offer.delivery === 'delivered') return 'Без реестра: выдано'
    if (offer.delivery === 'expired') return 'Без реестра: срок выдачи истёк'
    return 'Без реестра: ожидает выдачи'
  }
  if (offer.decision === 'declined') return 'Без реестра: клиент отказался'
  if (offer.decision === 'expired') return 'Без реестра: решение не получено'
  return 'Без реестра: ожидает решения'
}

function registryFallbackDecisionLabel(decision: string) {
  return ({
    pending: 'ожидается',
    accepted: 'принято',
    declined: 'отказ',
    expired: 'не получено в срок',
  } as Record<string, string>)[decision || 'pending'] || decision
}

function registryFallbackDeliveryLabel(delivery: string) {
  return ({
    pending: 'ожидает выдачи',
    delivered: 'выдано',
    expired: 'срок выдачи истёк',
  } as Record<string, string>)[delivery] || delivery
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

function supplierSearchPolicyLabel(job: Pick<Job, 'mode' | 'supplier_search_policy'>) {
  if (!['supplier_search', 'analysis_and_suppliers'].includes(job.mode)) return ''
  const labels: Record<string, string> = {
    normal: 'Обычный поиск',
    minprom_registry_only: 'Только реестр (Минпромторг)',
    minprom_registry_priority: 'Реестр в приоритете (Минпромторг)',
  }
  return labels[job.supplier_search_policy || 'normal'] || 'Обычный поиск'
}

function supplierRunTypeLabel(job: Pick<Job, 'mode' | 'supplier_search_run_type'>) {
  if (!['supplier_search', 'analysis_and_suppliers'].includes(job.mode)) return ''
  return job.supplier_search_run_type === 'additional' ? 'Добор поставщиков' : ''
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


function formatJobDuration(job: { created_at?: string | null; completed_at?: string | null; updated_at?: string | null; status?: string }, nowTs: number): string | null {
  if (!job.created_at) return null
  const startTime = new Date(apiDateValue(job.created_at)).getTime()
  if (Number.isNaN(startTime)) return null

  const isRunning = job.status === 'pending' || job.status === 'running' || job.status === 'queued' || job.status === 'in_progress'
  
  let totalSeconds = 0
  if (!isRunning) {
    const endStr = job.completed_at || job.updated_at
    if (!endStr) return null
    const endTime = new Date(apiDateValue(endStr)).getTime()
    if (Number.isNaN(endTime) || endTime < startTime) return null
    totalSeconds = Math.floor((endTime - startTime) / 1000)
  } else {
    totalSeconds = Math.max(0, Math.floor((nowTs - startTime) / 1000))
  }

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60

  if (isRunning) {
    const mm = String(minutes).padStart(2, '0')
    const ss = String(seconds).padStart(2, '0')
    return `${mm}:${ss}`
  }

  if (minutes === 0) {
    return `${seconds} сек`
  }
  if (minutes < 60) {
    return `${minutes} мин ${seconds} сек`
  }
  const hours = Math.floor(minutes / 60)
  const remMin = minutes % 60
  return `${hours} ч ${remMin} мин`
}

function formatDate(value: string | null | undefined) {
  if (!value) return '-'
  const date = new Date(apiDateValue(value))
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16)
  return date.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short', timeZone: MOSCOW_TIME_ZONE })
}

const VALID_VIEWS: readonly View[] = ['dashboard', 'seo', 'clients', 'jobs', 'outreach', 'billing', 'settings', 'ai'] as const

function getInitialView(): View {
  if (typeof window === 'undefined') return 'dashboard'
  const hash = window.location.hash.replace(/^#\/?/, '').trim() as View
  if (VALID_VIEWS.includes(hash)) return hash
  try {
    const saved = localStorage.getItem('aipoisk_admin_view') as View
    if (VALID_VIEWS.includes(saved)) return saved
  } catch {}
  return 'dashboard'
}

export function App() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authenticated, setAuthenticated] = useState(false)
  const [view, setViewState] = useState<View>(getInitialView)
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [opsStatus, setOpsStatus] = useState<OpsStatus | null>(null)
  const [minpromRegistry, setMinpromRegistry] = useState<MinpromRegistryStatus | null>(null)
  const [settings, setSettings] = useState<SettingsPayload | null>(null)
  const [analytics, setAnalytics] = useState<BotAnalytics | null>(null)
  const [tariffs, setTariffs] = useState<TariffPackage[]>([])
  const [passwordResets, setPasswordResets] = useState<PasswordResetRequest[]>([])
  const [seoAnalytics, setSeoAnalytics] = useState<SeoAnalytics | null>(null)
  const [loadingSeo, setLoadingSeo] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showServerModal, setShowServerModal] = useState(false)
  const loadAllRef = useRef<(force?: boolean) => Promise<void>>(() => Promise.resolve())

  function setView(nextView: View) {
    setViewState(nextView)
    try {
      localStorage.setItem('aipoisk_admin_view', nextView)
      if (window.location.hash.replace(/^#\/?/, '') !== nextView) {
        window.history.replaceState(null, '', '#' + nextView)
      }
    } catch {}
  }

  useEffect(() => {
    function handleHashChange() {
      const hash = window.location.hash.replace(/^#\/?/, '').trim() as View
      if (VALID_VIEWS.includes(hash)) {
        setViewState(hash)
        try { localStorage.setItem('aipoisk_admin_view', hash) } catch {}
      }
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  useEffect(() => {
    if (authenticated && window.location.hash.replace(/^#\/?/, '') !== view) {
      try {
        window.history.replaceState(null, '', '#' + view)
      } catch {}
    }
  }, [authenticated, view])

  useEffect(() => {
    if (authenticated && view === 'seo' && !seoAnalytics && !loadingSeo) {
      void loadSeoAnalytics()
    }
  }, [authenticated, view, seoAnalytics, loadingSeo])

  useEffect(() => {
    if (authenticated && view === 'clients') {
      void api<Client[]>('/api/clients')
        .then(data => { if (data) setClients(data) })
        .catch(() => {})
      void api<PasswordResetRequest[]>('/api/web-password-resets?status=open')
        .then(data => { if (data) setPasswordResets(data) })
        .catch(() => {})
    }
  }, [authenticated, view])

  const isReady = authenticated
  const canLogin = username.trim().length > 0 && password.length > 0

  async function loadSeoAnalytics(forceRefresh = false) {
    if (!authenticated) return
    setLoadingSeo(true)
    try {
      const data = await api<SeoAnalytics>(`/api/seo-analytics${forceRefresh ? '?refresh=true' : ''}`)
      setSeoAnalytics(data)
    } catch (err) {
      console.error('Failed to load SEO analytics:', err)
    } finally {
      setLoadingSeo(false)
    }
  }

  async function loadAll(force = false) {
    if (!force && !authenticated) return
    setLoading(true)
    setError('')
    try {
      const [dashboardData, clientsData, opsStatusData, settingsData, tariffData, passwordResetData, analyticsData] = await Promise.all([
        api<Dashboard>('/api/dashboard'),
        api<Client[]>('/api/clients'),
        api<OpsStatus>('/api/ops/system-status'),
        api<SettingsPayload>('/api/settings'),
        api<TariffPackage[]>('/api/tariffs'),
        api<PasswordResetRequest[]>('/api/web-password-resets?status=open'),
        api<BotAnalytics>('/api/analytics/bot?period_days=30').catch(() => null),
      ])
      setDashboard(dashboardData)
      setClients(clientsData)
      setOpsStatus(opsStatusData)
      setSettings(settingsData)
      setTariffs(tariffData)
      setPasswordResets(passwordResetData)
      if (analyticsData) setAnalytics(analyticsData)

      // Fetch background / secondary data without delaying core view rendering
      void api<Job[]>('/api/jobs?include_internal=true&limit=2000')
        .then(jobsData => { if (jobsData) setJobs(jobsData) })
        .catch(() => {})
      void api<MinpromRegistryStatus>('/api/ops/minprom-registry')
        .then(minpromData => { if (minpromData) setMinpromRegistry(minpromData) })
        .catch(() => {})
    } catch (err) {
      setError(formatError(err))
    } finally {
      setLoading(false)
    }
  }
  loadAllRef.current = loadAll

  const stableLoadAll = useCallback(() => loadAllRef.current(), [])

  async function loadAnalytics() {
    if (!authenticated) return
    try {
      const analyticsData = await api<BotAnalytics>('/api/analytics/bot?period_days=30')
      setAnalytics(analyticsData)
    } catch (err) {
      console.error('Failed to load analytics:', err)
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
    setMinpromRegistry(null)
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
    if (!authenticated) return

    let timeoutId: any = null
    let cancelled = false
    let lastClientsPoll = 0

    async function loop() {
      if (cancelled) return

      let hasActive = false
      setJobs(prevJobs => {
        hasActive = prevJobs.some(j => j.status === 'running' || j.status === 'pending')
        return prevJobs
      })

      const delay = document.hidden ? 30000 : hasActive ? 2500 : 6000

      timeoutId = setTimeout(async () => {
        if (cancelled) return
        if (!document.hidden) {
          try {
            const updatedJobs = await api<Job[]>('/api/jobs?include_internal=true&limit=2000')
            if (!cancelled && updatedJobs) {
              setJobs(updatedJobs)
              const nowHasActive = updatedJobs.some(j => j.status === 'running' || j.status === 'pending')
              if (hasActive && !nowHasActive) {
                void api<Dashboard>('/api/dashboard').then(d => {
                  if (!cancelled && d) setDashboard(d)
                }).catch(() => {})
              }
            }

            // Live polling for clients & dashboard
            const now = Date.now()
            const pollInterval = view === 'clients' ? 8000 : 25000
            if (now - lastClientsPoll >= pollInterval) {
              lastClientsPoll = now
              const promises: [Promise<Client[] | null>, Promise<Dashboard | null>, Promise<PasswordResetRequest[] | null>?] = [
                api<Client[]>('/api/clients').catch(() => null),
                api<Dashboard>('/api/dashboard').catch(() => null),
              ]
              if (view === 'clients') {
                promises.push(api<PasswordResetRequest[]>('/api/web-password-resets?status=open').catch(() => null))
              }
              const [cData, dData, pData] = await Promise.all(promises)
              if (!cancelled) {
                if (cData) setClients(cData)
                if (dData) setDashboard(dData)
                if (pData) setPasswordResets(pData)
              }
            }
          } catch {
            // Ignore transient background network glitches
          }
        }
        if (!cancelled) {
          loop()
        }
      }, delay)
    }

    loop()

    function handleVisibilityOrFocus() {
      if (!document.hidden && authenticated) {
        void api<Job[]>('/api/jobs?include_internal=true&limit=2000').then(updatedJobs => {
          if (!cancelled && updatedJobs) setJobs(updatedJobs)
        }).catch(() => {})
        void api<Client[]>('/api/clients').then(cData => {
          if (!cancelled && cData) setClients(cData)
        }).catch(() => {})
        void api<Dashboard>('/api/dashboard').then(dData => {
          if (!cancelled && dData) setDashboard(dData)
        }).catch(() => {})
        if (view === 'clients') {
          void api<PasswordResetRequest[]>('/api/web-password-resets?status=open').then(pData => {
            if (!cancelled && pData) setPasswordResets(pData)
          }).catch(() => {})
        }
      }
    }

    window.addEventListener('focus', handleVisibilityOrFocus)
    document.addEventListener('visibilitychange', handleVisibilityOrFocus)

    return () => {
      cancelled = true
      if (timeoutId) clearTimeout(timeoutId)
      window.removeEventListener('focus', handleVisibilityOrFocus)
      document.removeEventListener('visibilitychange', handleVisibilityOrFocus)
    }
  }, [authenticated, view])

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
    { id: 'seo' as const, label: 'SEO и Трафик', icon: Globe },
    { id: 'clients' as const, label: 'Клиенты', icon: Users },
    { id: 'jobs' as const, label: 'Задачи', icon: FileText },
    { id: 'outreach' as const, label: 'Лиды и Рассылка', icon: Mail },
    { id: 'billing' as const, label: 'Тарифы', icon: CreditCard },
    { id: 'settings' as const, label: 'Настройки', icon: SlidersHorizontal },
    { id: 'ai' as const, label: 'ИИ', icon: BrainCircuit },
    { id: 'mcp' as const, label: 'MCP & API', icon: KeyRound },
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
              <a
                key={item.id}
                href={`#${item.id}`}
                className={view === item.id ? 'nav-item active' : 'nav-item'}
                onClick={(e) => {
                  if (e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
                    e.preventDefault()
                    setError('')
                    setView(item.id)
                  }
                }}
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </a>
            )
          })}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{viewCopy[view]?.title || 'Панель управления'}</h1>
            <p>{viewCopy[view]?.description || ''}</p>
          </div>
          <div className="top-actions">
            {opsStatus && (
              <div className="header-status-badges">
                <span className={`header-badge ${opsStatus.server.cpu_percent >= 80 ? 'warning' : ''}`} title={`CPU: ${opsStatus.server.cpu_percent}%`}>
                  <Cpu size={13} />
                  <span>CPU {opsStatus.server.cpu_percent}%</span>
                </span>
                <span className={`header-badge ${opsStatus.server.ram_percent >= 85 ? 'warning' : ''}`} title={`RAM: ${opsStatus.server.ram_used_gb}/${opsStatus.server.ram_total_gb} ГБ`}>
                  <MemoryStick size={13} />
                  <span>RAM {Math.round(opsStatus.server.ram_percent)}%</span>
                </span>
                <span className={`header-badge ${opsStatus.server.disk_free_gb < 10 ? 'warning' : ''}`} title={`SSD свободно: ${Math.floor(opsStatus.server.disk_free_gb)} ГБ`}>
                  <HardDrive size={13} />
                  <span>SSD {Math.floor(opsStatus.server.disk_free_gb)} ГБ</span>
                </span>
                {(() => {
                  const yandexSvc = opsStatus.services.find(s => s.id === 'yandex')
                  const isWarn = yandexSvc ? (yandexSvc.warning || yandexSvc.status !== 'ok') : false
                  const balanceText = yandexSvc?.balance_label || 'н/д'
                  return (
                    <button
                      type="button"
                      className={`header-badge clickable ${isWarn ? 'warning' : 'balance'}`}
                      onClick={() => setShowServerModal(true)}
                      title="Баланс Яндекс.Поиска (нажмите для подробностей сервера)"
                    >
                      <Search size={13} />
                      <span>Поиск Яндекс: {balanceText}</span>
                    </button>
                  )
                })()}
              </div>
            )}
            <button className="secondary" onClick={() => void logout()}>Выйти</button>
          </div>
        </header>

        {error && <div className="alert error"><XCircle size={18} />{error}</div>}
        {isReady && view === 'dashboard' && (
          <DashboardView
            dashboard={dashboard}
            analytics={analytics}
            settings={settings}
            opsStatus={opsStatus}
            onNavigate={setView}
            onRefresh={loadAll}
          />
        )}
        {isReady && view === 'seo' && <SeoView data={seoAnalytics} loading={loadingSeo} onRefresh={() => void loadSeoAnalytics(true)} />}
        {isReady && view === 'clients' && <ClientsView clients={clients} passwordResets={passwordResets} onChange={loadAll} />}
        {isReady && view === 'jobs' && <JobsView jobs={jobs} onChange={loadAll} />}
        {isReady && view === 'outreach' && <OutreachView />}
        {isReady && view === 'billing' && <BillingView tariffs={tariffs} onChange={loadAll} />}
        {isReady && view === 'settings' && settings && <SettingsView settings={settings} minpromRegistry={minpromRegistry} onChange={loadAll} />}
        {isReady && view === 'ai' && settings && <AiView settings={settings} onChange={stableLoadAll} />}
        {isReady && view === 'mcp' && <McpApiView clients={clients} />}

        {showServerModal && opsStatus && (
          <div className="server-modal-backdrop" onClick={() => setShowServerModal(false)}>
            <div className="server-modal-card" onClick={e => e.stopPropagation()}>
              <div className="server-modal-header">
                <h3>СОСТОЯНИЕ СЕРВЕРА</h3>
                <button className="server-modal-close" onClick={() => setShowServerModal(false)}>
                  <X size={18} />
                </button>
              </div>

              <div className="server-grid-3">
                <div className={`server-grid-item ${opsStatus.server.cpu_percent >= 80 ? 'warning' : ''}`}>
                  <div className="server-grid-item-title"><Cpu size={14} /> CPU</div>
                  <div className="server-grid-item-value">{opsStatus.server.cpu_percent}%</div>
                </div>
                <div className={`server-grid-item ${opsStatus.server.ram_percent >= 85 ? 'warning' : ''}`}>
                  <div className="server-grid-item-title"><MemoryStick size={14} /> RAM</div>
                  <div className="server-grid-item-value">{opsStatus.server.ram_percent}%</div>
                </div>
                <div className={`server-grid-item ${opsStatus.server.disk_free_gb < 10 ? 'warning' : ''}`}>
                  <div className="server-grid-item-title"><HardDrive size={14} /> SSD</div>
                  <div className="server-grid-item-value">{Math.floor(opsStatus.server.disk_free_gb)} GB</div>
                </div>
              </div>

              <div className="server-cache-box">
                <span className="server-cache-title">Кэш и логи</span>
                <button className="secondary small" onClick={async () => {
                  if (!window.confirm('Очистить временные логи и кэш?')) return
                  const res = await api<{ cancelled: string[]; count: number }>('/api/jobs/force-stale?max_minutes=45', { method: 'POST' })
                  alert(res.count ? `Очищено задач: ${res.count}` : 'Кэш и задачи в норме')
                }}>
                  <Trash2 size={13} style={{ marginRight: 4 }} />
                  Очистить
                </button>
              </div>

              <div className="server-api-section-title">API СЕРВИСЫ</div>

              {opsStatus.services.map(svc => {
                const targetUrl = svc.url || (svc.id === 'yandex' ? 'https://console.yandex.cloud/folders/b1gmnp1u8urslual8ht8/dashboard' : undefined)
                const CardTag = targetUrl ? 'a' : 'div'
                const cardProps = targetUrl ? {
                  href: targetUrl,
                  target: '_blank',
                  rel: 'noopener noreferrer',
                  title: `Перейти в ${svc.label} (${svc.detail})`,
                } : {}

                return (
                  <CardTag
                    key={svc.id}
                    className={`server-api-card ${svc.warning ? 'warning' : ''} ${targetUrl ? 'interactive' : ''}`}
                    {...cardProps}
                  >
                    <div className="server-api-card-info">
                      <div className="server-api-card-icon">
                        {svc.id === 'yandex' ? <Search size={16} /> : <Bot size={16} />}
                      </div>
                      <div>
                        <div className="server-api-card-name">
                          <span>{svc.label}</span>
                          {targetUrl && <ExternalLink size={12} className="server-api-card-link-icon" />}
                        </div>
                        <div className="server-api-card-sub">{svc.detail}</div>
                      </div>
                    </div>
                    <div className="server-api-card-val">{svc.balance_label}</div>
                  </CardTag>
                )
              })}
            </div>
          </div>
        )}

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

function DashboardView({
  dashboard,
  analytics,
  settings,
  opsStatus,
  onNavigate,
  onRefresh,
}: {
  dashboard: Dashboard | null
  analytics: BotAnalytics | null
  settings: SettingsPayload | null
  opsStatus: OpsStatus | null
  onNavigate: (view: View) => void
  onRefresh: () => Promise<void>
}) {
  const [resolving, setResolving] = useState(false)
  const summary = analytics?.summary
  const funnel = analytics?.funnel
  const maxDaily = Math.max(1, ...(analytics?.jobs.daily.map(item => item.total) || [1]))

  async function handleResolveAll() {
    if (!window.confirm('Пометить все текущие ошибки как решённые? Они перестанут показываться в сводке и статусе.')) return
    setResolving(true)
    try {
      await api('/api/jobs/resolve-failed', { method: 'POST' })
      await onRefresh()
    } catch (err) {
      alert('Ошибка: ' + formatError(err))
    } finally {
      setResolving(false)
    }
  }

  const stats = [
    {
      label: 'Клиентов',
      value: dashboard?.clients ?? 0,
      note: `${dashboard?.active_clients ?? 0} активных · ${summary?.telegram_accounts ?? 0} TG`,
      icon: Users,
      onClick: () => onNavigate('clients'),
    },
    {
      label: 'Задач',
      value: dashboard?.jobs ?? 0,
      note: `${summary?.period_jobs ?? 0} за 30 дней · ${dashboard?.running_jobs ?? 0} в работе`,
      icon: FileText,
      onClick: () => onNavigate('jobs'),
    },
    {
      label: 'Готово',
      value: dashboard?.completed_jobs ?? 0,
      note: (dashboard?.failed_jobs ?? 0) > 0 ? `${dashboard?.failed_jobs} сбоев (7д)` : 'без сбоев за 7д',
      icon: CheckCircle2,
      warning: (dashboard?.failed_jobs ?? 0) > 0,
      onClick: () => onNavigate('jobs'),
    },
    {
      label: 'Поставщиков',
      value: dashboard?.suppliers ?? 0,
      note: 'проверенных строк в базе',
      icon: Search,
    },
    {
      label: 'Конверсия триала',
      value: `${funnel?.trial_to_grant_percent ?? 0}%`,
      note: `${funnel?.trial_with_grants ?? 0}/${funnel?.trial_started ?? 0} оплатили`,
      icon: CreditCard,
    },
  ]

  const attentionItems = dashboardAttentionItems(dashboard, opsStatus, onNavigate)

  return (
    <section className="dash-container">
      {/* Top 5 KPI Metrics */}
      <div className="dash-kpi-grid">
        {stats.map(item => {
          const Icon = item.icon
          return (
            <div
              className={`dash-kpi-card ${item.onClick ? 'clickable' : ''} ${item.warning ? 'warning' : ''}`}
              key={item.label}
              onClick={item.onClick}
              title={item.onClick ? 'Перейти в раздел' : undefined}
            >
              <div className="dash-kpi-icon">
                <Icon size={20} />
              </div>
              <div className="dash-kpi-content">
                <span className="dash-kpi-label">{item.label}</span>
                <span className="dash-kpi-value">{item.value}</span>
                <span className="dash-kpi-note">{item.note}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Что требует внимания */}
      <DashboardAttentionPanel
        items={attentionItems}
        onResolveAll={handleResolveAll}
        resolving={resolving}
      />

      {/* Динамика запусков (30 дней) */}
      {analytics && analytics.jobs.daily.length > 0 && (
        <div className="dash-chart-card">
          <div className="dash-chart-header">
            <div>
              <h2 style={{ fontSize: 14, margin: 0, fontWeight: 700, color: '#0f172a' }}>Динамика запусков</h2>
              <small style={{ color: '#64748b', fontSize: 11.5 }}>
                За последние {analytics.period_days} дней · всего {summary?.period_jobs ?? 0} запусков
              </small>
            </div>
            <div className="dash-chart-legend">
              <div className="dash-chart-legend-item">
                <span className="dash-chart-legend-dot" style={{ background: '#2563eb' }} />
                <span>Поставщики ({analytics.jobs.by_mode.find(m => m.mode === 'supplier_search')?.count ?? 0})</span>
              </div>
              <div className="dash-chart-legend-item">
                <span className="dash-chart-legend-dot" style={{ background: '#10b981' }} />
                <span>Анализ ТЗ ({analytics.jobs.by_mode.find(m => m.mode === 'procurement_report')?.count ?? 0})</span>
              </div>
              <div className="dash-chart-legend-item">
                <span className="dash-chart-legend-dot" style={{ background: '#8b5cf6' }} />
                <span>Анализ + поиск ({analytics.jobs.by_mode.find(m => m.mode === 'analysis_and_suppliers')?.count ?? 0})</span>
              </div>
            </div>
          </div>
          <div className="dash-chart-bars">
            {analytics.jobs.daily.map(item => {
              const heightPct = Math.max(item.total > 0 ? 10 : 3, Math.round((item.total * 100) / maxDaily))
              return (
                <div
                  className="dash-chart-col"
                  key={item.date}
                  title={`${item.date}: Всего ${item.total} (Поставщики: ${item.supplier_search}, Анализ: ${item.procurement_report}, Комбо: ${item.analysis_and_suppliers})`}
                >
                  <span
                    className={`dash-chart-bar ${item.total > 0 ? 'active' : ''}`}
                    style={{ height: `${heightPct}%` }}
                  />
                  <span className="dash-chart-date">
                    {new Date(apiDateValue(item.date)).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', timeZone: MOSCOW_TIME_ZONE })}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Состояние системы и сервисов */}
      <SystemStatusPanel opsStatus={opsStatus} />

      {/* 2-Column Split: Режимы и Статусы | Воронка и Топ клиентов */}
      {analytics && (
        <div className="dash-split-grid">
          {/* Column 1: Задачи по режимам и статусам */}
          <div className="dash-card">
            <div className="dash-card-section">
              <h3 className="dash-card-title">
                <span>Задачи по режимам</span>
                <span style={{ fontSize: 12, fontWeight: 500, color: '#64748b' }}>за {analytics.period_days}д</span>
              </h3>
              <div className="dash-row-list">
                {analytics.jobs.by_mode.map(item => (
                  <div className="dash-row-item" key={item.mode}>
                    <span>{item.label}</span>
                    <strong>{item.count}</strong>
                  </div>
                ))}
                {!analytics.jobs.by_mode.length && <div className="inline-note">За период задач не было.</div>}
              </div>
            </div>

            <div className="dash-card-section" style={{ borderTop: '1px solid #f1f5f9', paddingTop: 14 }}>
              <h3 className="dash-card-title">Статусы задач</h3>
              <div className="dash-status-grid">
                {analytics.jobs.by_status.map(item => (
                  <div className="dash-status-pill" key={item.status}>
                    <span style={{ color: '#475569' }}>{item.label}</span>
                    <strong>{item.count}</strong>
                  </div>
                ))}
                {!analytics.jobs.by_status.length && <div className="inline-note">Статусов за период нет.</div>}
              </div>
            </div>
          </div>

          {/* Column 2: Воронка триала и Топ клиентов */}
          <div className="dash-card">
            <div className="dash-card-section">
              <h3 className="dash-card-title">
                <span>Воронка триала</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#059669' }}>
                  конверсия {funnel?.trial_to_grant_percent ?? 0}%
                </span>
              </h3>
              <div className="dash-row-list">
                <div className="dash-row-item">
                  <span>Триалов создано</span>
                  <strong>{funnel?.trial_started ?? 0}</strong>
                </div>
                <div className="dash-row-item">
                  <span>Пользовались ботом</span>
                  <strong>{funnel?.trial_used_bot ?? 0}</strong>
                </div>
                <div className="dash-row-item">
                  <span>Оплатили услуги</span>
                  <strong className="dash-highlight">{funnel?.trial_with_grants ?? 0}</strong>
                </div>
                <div className="dash-row-item">
                  <span>Конверсия активных пользователей</span>
                  <strong className="dash-highlight">{funnel?.usage_to_grant_percent ?? 0}%</strong>
                </div>
              </div>
            </div>

            <div className="dash-card-section" style={{ borderTop: '1px solid #f1f5f9', paddingTop: 14 }}>
              <h3 className="dash-card-title">
                <span>Топ активных клиентов</span>
                <span style={{ fontSize: 12, fontWeight: 500, color: '#64748b' }}>за {analytics.period_days}д</span>
              </h3>
              <div className="dash-client-list">
                {(analytics.top_clients || []).slice(0, 5).map(client => (
                  <div
                    className="dash-client-row"
                    key={client.client_id}
                    onClick={() => onNavigate('clients')}
                    title="Открыть клиента в разделе Клиенты"
                  >
                    <div className="dash-client-info">
                      <span className="dash-client-name">{client.name}</span>
                      <span className="dash-client-meta">
                        {client.username ? `@${client.username}` : client.telegram_id || 'ID'} · {client.jobs_total} задач
                      </span>
                    </div>
                    <span className="dash-client-badge">
                      поставщики: {client.supplier_jobs}
                    </span>
                  </div>
                ))}
                {(!analytics.top_clients || !analytics.top_clients.length) && (
                  <div className="inline-note">За период нет активных клиентов.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function dashboardAttentionItems(
  dashboard: Dashboard | null,
  opsStatus: OpsStatus | null,
  onNavigate?: (view: View) => void,
) {
  const items: Array<{ title: string; detail: string; tone: 'critical' | 'warning' | 'ok'; icon: ReactNode; onClick?: () => void }> = []
  const failedJobs = dashboard?.failed_jobs || opsStatus?.queue.failed || 0
  const runningJobs = dashboard?.running_jobs || opsStatus?.queue.running || 0
  const pendingJobs = opsStatus?.queue.pending || 0
  const unconfiguredServices = opsStatus?.services.filter(service => !service.configured) || []

  if (failedJobs > 0) {
    items.push({
      title: 'Ошибки задач',
      detail: `${failedJobs} ${failedJobs === 1 ? 'задача' : failedJobs < 5 ? 'задачи' : 'задач'} за 7 дней требуют внимания`,
      tone: 'warning',
      icon: <AlertTriangle size={18} />,
      onClick: () => onNavigate?.('jobs'),
    })
  }
  if (pendingJobs > 0) {
    items.push({
      title: 'Очередь',
      detail: `${pendingJobs} задач ждут обработки`,
      tone: pendingJobs >= 50 ? 'critical' : 'warning',
      icon: <Server size={18} />,
      onClick: () => onNavigate?.('jobs'),
    })
  }
  if (runningJobs > 0) {
    items.push({
      title: 'В обработке',
      detail: `${runningJobs} задач сейчас выполняются`,
      tone: 'warning',
      icon: <Loader2 size={18} className="animate-spin" />,
      onClick: () => onNavigate?.('jobs'),
    })
  }
  if (opsStatus?.warnings.length) {
    items.push({
      title: 'Сервер',
      detail: opsStatus.warnings[0],
      tone: 'warning',
      icon: <HardDrive size={18} />,
    })
  }
  if (unconfiguredServices.length) {
    items.push({
      title: 'Интеграции',
      detail: `Не настроено: ${unconfiguredServices.map(service => service.label).slice(0, 3).join(', ')}`,
      tone: 'warning',
      icon: <Settings size={18} />,
      onClick: () => onNavigate?.('settings'),
    })
  }
  if (!items.length) {
    items.push({
      title: 'Система работает штатно',
      detail: 'Очередь, сервер и фоновые процессы в норме',
      tone: 'ok',
      icon: <ShieldCheck size={18} style={{ color: '#10b981' }} />,
    })
  }
  return items.slice(0, 4)
}

function DashboardAttentionPanel({
  items,
  onResolveAll,
  resolving,
}: {
  items: Array<{ title: string; detail: string; tone: 'critical' | 'warning' | 'ok'; icon: ReactNode; onClick?: () => void }>
  onResolveAll?: () => void
  resolving?: boolean
}) {
  const hasErrors = items.some(item => item.title === 'Ошибки задач')
  const isOk = items.every(item => item.tone === 'ok')

  return (
    <div className="dash-attention-card">
      <div className="dash-attention-header">
        <div className="dash-attention-title">
          <ShieldCheck size={18} style={{ color: isOk ? '#059669' : '#d97706' }} />
          <span>Что требует внимания</span>
          <span className={items.some(item => item.tone === 'critical') ? 'status failed' : items.some(item => item.tone === 'warning') ? 'status warning' : 'status active'}>
            {items.some(item => item.tone === 'critical') ? 'есть ошибки' : items.some(item => item.tone === 'warning') ? 'проверить' : 'в норме'}
          </span>
        </div>

        <div className="dash-attention-actions">
          {hasErrors && onResolveAll && (
            <button
              type="button"
              className="dash-resolve-btn"
              onClick={onResolveAll}
              disabled={resolving}
              title="Пометить все текущие ошибки как решённые, чтобы они больше не отображались"
            >
              {resolving ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} />}
              <span>{resolving ? 'Сохранение...' : 'Отметить решёнными'}</span>
            </button>
          )}
        </div>
      </div>

      <div className="dash-attention-grid">
        {items.map(item => (
          <div
            className={`dash-attention-item ${item.tone}`}
            key={`${item.title}-${item.detail}`}
            onClick={item.onClick}
            style={item.onClick ? { cursor: 'pointer' } : undefined}
            title={item.onClick ? 'Перейти в раздел' : undefined}
          >
            {item.icon}
            <div>
              <strong style={{ fontSize: 13, display: 'block', color: '#0f172a' }}>{item.title}</strong>
              <span style={{ fontSize: 12, display: 'block', marginTop: 3 }}>{item.detail}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

type RecommendationItem = {
  id: string
  category?: string
  target?: string
  title: string
  current_text: string
  proposed_text: string
  rationale: string
  impact?: string
  status: 'pending' | 'applied' | 'rejected'
  created_at?: string
}

type DailyMetricItem = {
  date: string
  clicks: number
  shows: number
  avg_position?: number
  ctr_percent?: number
  queries_count?: number
  clicks_delta?: number
  shows_delta?: number
  pos_delta?: number
  trend?: 'up' | 'down' | 'stable'
}

type CombinedDailyDynamic = {
  date: string
  total_clicks: number
  total_shows: number
  total_queries: number
  yandex?: DailyMetricItem
  google?: DailyMetricItem
  yandex_pos?: number | null
  google_pos?: number | null
  yandex_trend?: 'up' | 'down' | 'stable'
  google_trend?: 'up' | 'down' | 'stable'
}

type PhraseDynamicItem = {
  text: string
  engine: 'yandex' | 'google'
  current_pos: number
  prev_pos: number
  delta: number
  trend: 'up' | 'down' | 'stable'
}

type TodayEngineProgress = {
  clicks: number
  shows: number
  avg_position: number
  queries_count: number
  clicks_delta: number
  shows_delta: number
  pos_delta: number
  trend: 'up' | 'down' | 'stable'
  data_date?: string
}

type TodayProgress = {
  date: string
  today_site_visits: number
  today_site_users: number
  today_site_pageviews: number
  yandex: TodayEngineProgress
  google: TodayEngineProgress
  combined: {
    clicks: number
    shows: number
    avg_position: number
    queries_count: number
    ranking_status: string
  }
}

type SeoAnalytics = {
  updated_at: string
  collection_status: string
  sample_size_ready: boolean
  sample_visits: number
  sample_target: number
  today_progress?: TodayProgress
  daily_dynamics?: CombinedDailyDynamic[]
  phrase_dynamics?: PhraseDynamicItem[]
  webmaster: {
    sqi: number
    searchable_pages: number
    excluded_pages: number
    top_queries: { text: string; shows: number; clicks: number; avg_position?: number; ctr_percent?: number }[]
    daily_dynamics?: DailyMetricItem[]
    phrase_dynamics?: PhraseDynamicItem[]
    growth_points?: {
      text: string
      shows: number
      clicks: number
      avg_position: number
      wordstat_demand?: number
      top3_potential_clicks?: number
      priority?: 'high' | 'medium' | 'normal'
      demand_source?: string
      potential: string
      action: string
    }[]
  }
  google?: {
    status: string
    site_url: string
    period_days: number
    total_impressions: number
    total_clicks: number
    avg_position: number
    avg_ctr_percent: number
    top_queries: { text: string; shows: number; clicks: number; avg_position?: number; ctr_percent?: number }[]
    daily_dynamics?: DailyMetricItem[]
    phrase_dynamics?: PhraseDynamicItem[]
    growth_points?: {
      text: string
      shows: number
      clicks: number
      avg_position: number
      wordstat_demand?: number
      top3_potential_clicks?: number
      priority?: 'high' | 'medium' | 'normal'
      potential: string
      action: string
    }[]
    sitemaps?: { path: string; last_submitted: string; last_downloaded: string; is_pending: boolean; warnings: number; errors: number }[]
    error?: string
  }
  combined_queries?: {
    text: string
    yandex_pos?: number | null
    yandex_shows: number
    yandex_clicks: number
    google_pos?: number | null
    google_shows: number
    google_clicks: number
    total_shows: number
    total_clicks: number
    in_yandex: boolean
    in_google: boolean
  }[]
  metrika: {
    period_days: number
    visits: number
    users: number
    pageviews: number
    bounce_rate: number
    avg_duration_seconds: number
    sources: { name: string; visits: number; users: number }[]
    top_pages: { path: string; visits: number; users: number; bounce_rate: number; avg_duration_seconds: number }[]
    goals?: { id: number; name: string; type: string; reaches: number }[]
    total_goal_reaches?: number
    total_conversion_rate?: number
  }
  recommendations: RecommendationItem[]
}

function SeoView({ data, loading, onRefresh }: { data: SeoAnalytics | null; loading: boolean; onRefresh: () => void }) {
  const [sendingDigest, setSendingDigest] = useState(false)
  const [digestSuccess, setDigestSuccess] = useState('')
  const [triggeringRecrawl, setTriggeringRecrawl] = useState(false)
  const [recrawlMsg, setRecrawlMsg] = useState('')
  const [querySearch, setQuerySearch] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [searchEngine, setSearchEngine] = useState<'all' | 'yandex' | 'google'>('all')
  const [trendDays, setTrendDays] = useState<7 | 14 | 30>(14)

  async function handleSendDigest() {
    setSendingDigest(true)
    setDigestSuccess('')
    try {
      const res = await api<{ ok: boolean; error?: string }>('/api/seo-analytics/send-digest', { method: 'POST' })
      if (res?.ok) {
        setDigestSuccess('Сводка отправлена вам в Telegram!')
        setTimeout(() => setDigestSuccess(''), 4000)
      } else {
        alert(res?.error || 'Ошибка отправки в Telegram')
      }
    } catch (e) {
      alert('Ошибка отправки в Telegram')
    } finally {
      setSendingDigest(false)
    }
  }

  async function handleTriggerRecrawl() {
    setTriggeringRecrawl(true)
    setRecrawlMsg('')
    try {
      const res = await api<{ ok: boolean; submitted_count?: number; total_urls?: number; quota_remainder?: number; error?: string }>('/api/seo-analytics/recrawl', { method: 'POST' })
      if (res?.ok) {
        setRecrawlMsg(`Отправлено ${res.submitted_count}/${res.total_urls} страниц. Остаток квоты: ${res.quota_remainder}`)
        setTimeout(() => setRecrawlMsg(''), 5000)
      } else {
        alert(res?.error || 'Ошибка отправки в очередь переобхода')
      }
    } catch (e) {
      alert('Ошибка отправки в очередь переобхода')
    } finally {
      setTriggeringRecrawl(false)
    }
  }

  async function handleRecAction(recId: string, action: 'applied' | 'rejected' | 'pending') {
    setActionLoading(recId)
    try {
      const res = await api<{ ok: boolean; error?: string }>(`/api/seo-analytics/recommendations/${recId}/action`, {
        method: 'POST',
        body: JSON.stringify({ action })
      })
      if (res?.ok) {
        onRefresh()
      } else {
        alert(res?.error || 'Ошибка обновления статуса')
      }
    } catch (e) {
      alert('Ошибка обновления статуса')
    } finally {
      setActionLoading(null)
    }
  }

  if (loading && !data) {
    return <div className="empty"><Loader2 className="spin" size={24} /> Загрузка данных Яндекс.Метрики, Вебмастера и Google Search Console...</div>
  }
  if (!data) {
    return (
      <div className="empty">
        <p>Данные аналитики пока не сформированы.</p>
        <button onClick={onRefresh} className="primary" style={{ marginTop: 12 }}>
          <RefreshCw size={14} /> Запросить данные
        </button>
      </div>
    )
  }

  const { webmaster, metrika, google, combined_queries } = data
  const durationMin = Math.floor((metrika.avg_duration_seconds || 0) / 60)
  const durationSec = (metrika.avg_duration_seconds || 0) % 60
  const durationFormatted = `${durationMin} мин ${durationSec} сек`

  const metrics = [
    { label: 'Посетители сайта', value: `${metrika.users || 0} чел.`, note: `за последние ${metrika.period_days || 30} дней`, icon: Users },
    { label: 'Всего визитов', value: metrika.visits || 0, note: `${metrika.pageviews || 0} просмотров страниц`, icon: Globe },
    { label: 'Конверсия в цели', value: `${metrika.total_conversion_rate || 0}%`, note: `${metrika.total_goal_reaches || 0} целевых действий`, icon: CheckCircle2 },
    { label: 'Время на сайте', value: durationFormatted, note: 'средняя длительность визита', icon: ShieldCheck },
    { label: 'Отказы', value: `${metrika.bounce_rate || 0}%`, note: 'ушли в первые 15 секунд', icon: ArrowDown },
  ]

  const yandexGrowthPoints = (webmaster.growth_points || []).map(g => ({ ...g, engine: 'yandex' as const }))
  const googleGrowthPoints = (google?.growth_points || []).map(g => ({ ...g, engine: 'google' as const }))
  
  const displayGrowthPoints = searchEngine === 'yandex'
    ? yandexGrowthPoints
    : searchEngine === 'google'
    ? googleGrowthPoints
    : [...yandexGrowthPoints, ...googleGrowthPoints]

  const goals = metrika.goals || []
  const yandexQueries = webmaster.top_queries || []
  const googleQueries = google?.top_queries || []
  const combinedQueries = combined_queries || []

  const todayProg = data.today_progress
  const dailyDynamicsAll = data.daily_dynamics || []
  const slicedDynamics = dailyDynamicsAll.slice(-trendDays)
  const reversedDynamics = [...slicedDynamics].reverse()
  const phraseDynamicsAll = data.phrase_dynamics || []
  const filteredPhrases = searchEngine === 'all'
    ? phraseDynamicsAll
    : phraseDynamicsAll.filter(p => p.engine === searchEngine)

  const currentClicks = searchEngine === 'all'
    ? (todayProg?.combined.clicks ?? (metrika.visits || 0))
    : searchEngine === 'yandex'
    ? (todayProg?.yandex.clicks ?? 0)
    : (todayProg?.google.clicks ?? (google?.total_clicks || 0))

  const currentClicksDelta = searchEngine === 'all'
    ? ((todayProg?.yandex.clicks_delta || 0) + (todayProg?.google.clicks_delta || 0))
    : searchEngine === 'yandex'
    ? (todayProg?.yandex.clicks_delta || 0)
    : (todayProg?.google.clicks_delta || 0)

  const currentShows = searchEngine === 'all'
    ? (todayProg?.combined.shows ?? ((google?.total_impressions || 0) + 50))
    : searchEngine === 'yandex'
    ? (todayProg?.yandex.shows ?? 50)
    : (todayProg?.google.shows ?? (google?.total_impressions || 0))

  const currentShowsDelta = searchEngine === 'all'
    ? ((todayProg?.yandex.shows_delta || 0) + (todayProg?.google.shows_delta || 0))
    : searchEngine === 'yandex'
    ? (todayProg?.yandex.shows_delta || 0)
    : (todayProg?.google.shows_delta || 0)

  const currentPos = searchEngine === 'all'
    ? (todayProg?.combined.avg_position || 14.0)
    : searchEngine === 'yandex'
    ? (todayProg?.yandex.avg_position || 10.6)
    : (todayProg?.google.avg_position || (google?.avg_position || 0.0))

  const currentPosDelta = searchEngine === 'all'
    ? Math.round((((todayProg?.yandex.pos_delta || 0) + (todayProg?.google.pos_delta || 0)) / 2) * 10) / 10
    : searchEngine === 'yandex'
    ? (todayProg?.yandex.pos_delta || 0)
    : (todayProg?.google.pos_delta || 0)

  const currentQueries = searchEngine === 'all'
    ? (todayProg?.combined.queries_count || combinedQueries.length)
    : searchEngine === 'yandex'
    ? (todayProg?.yandex.queries_count || yandexQueries.length)
    : (todayProg?.google.queries_count || googleQueries.length)

  const maxChartShows = Math.max(...slicedDynamics.map(d => {
    if (searchEngine === 'yandex') return d.yandex?.shows || 0
    if (searchEngine === 'google') return d.google?.shows || 0
    return d.total_shows || 0
  }), 10)

  function formatDynamicsDate(dStr: string) {
    if (!dStr) return '—'
    try {
      const parts = dStr.split('-')
      if (parts.length === 3) {
        const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]))
        const today = new Date()
        if (d.toDateString() === today.toDateString()) return 'Сегодня'
        const yest = new Date(today)
        yest.setDate(today.getDate() - 1)
        if (d.toDateString() === yest.toDateString()) return 'Вчера'
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
      }
      return dStr
    } catch {
      return dStr
    }
  }

  // Filtered queries based on engine and search input
  const rawQueriesToFilter = searchEngine === 'yandex'
    ? yandexQueries.map(q => ({
        text: q.text,
        shows: q.shows,
        clicks: q.clicks,
        yandex_pos: q.avg_position,
        google_pos: null,
        total_shows: q.shows,
        total_clicks: q.clicks,
        in_yandex: true,
        in_google: false
      }))
    : searchEngine === 'google'
    ? googleQueries.map(q => ({
        text: q.text,
        shows: q.shows,
        clicks: q.clicks,
        yandex_pos: null,
        google_pos: q.avg_position,
        total_shows: q.shows,
        total_clicks: q.clicks,
        in_yandex: false,
        in_google: true
      }))
    : combinedQueries

  const filteredQueries = querySearch.trim()
    ? rawQueriesToFilter.filter(q => q.text.toLowerCase().includes(querySearch.toLowerCase().trim()))
    : rawQueriesToFilter

  const recs = data.recommendations || []

  return (
    <section className="stack">
      {/* 1. STATUS BANNER & ACTION BAR */}
      <div className="form-panel full-width-panel" style={{ borderLeft: '4px solid var(--accent)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
              <span className="status-badge" style={{ background: '#e5f4f3', color: '#075b63', fontWeight: 'bold', padding: '3px 8px', borderRadius: 6 }}>
                ● Автоматический сбор активен
              </span>
              <small style={{ color: 'var(--muted)' }}>
                Обновлено: {new Date(data.updated_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </small>
              {digestSuccess && <span style={{ color: '#075b63', fontWeight: 'bold', fontSize: 12 }}>✓ {digestSuccess}</span>}
              {recrawlMsg && <span style={{ color: '#047857', fontWeight: 'bold', fontSize: 12 }}>⚡ {recrawlMsg}</span>}
            </div>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--ink)' }}>
              Сервер самостоятельно опрашивает Яндекс.Метрику, Вебмастер, Wordstat и Google Search Console API в фоновом режиме.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <button className="secondary small-text" onClick={() => void handleTriggerRecrawl()} disabled={triggeringRecrawl} title="Отправить все страницы sitemap в очередь переобхода Яндекса">
              <RefreshCw size={13} className={triggeringRecrawl ? 'spin' : ''} /> {triggeringRecrawl ? 'Отправка...' : '⚡ Переобход (Recrawl)'}
            </button>
            <button className="secondary small-text" onClick={() => void handleSendDigest()} disabled={sendingDigest}>
              <Bot size={14} /> {sendingDigest ? 'Отправка...' : 'Отправить в Telegram'}
            </button>
            <button className="secondary small-text" onClick={onRefresh} disabled={loading}>
              <RefreshCw size={13} className={loading ? 'spin' : ''} /> {loading ? 'Обновление...' : 'Обновить сейчас'}
            </button>
          </div>
        </div>
      </div>

      {/* 2. METRIC CARDS (5 METRICS) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
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

      {/* 2.1 SEARCH ENGINES OVERVIEW CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
        <div style={{ background: '#fff', border: '1px solid #fed7aa', borderLeft: '4px solid #ea580c', borderRadius: 8, padding: '12px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#9a3412' }}>🔴 Яндекс Поиск</span>
            <span className="pill tg" style={{ fontSize: 11 }}>ИКС: {webmaster.sqi || 10}</span>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
            <div>
              <span style={{ fontSize: 11, color: 'var(--muted)', display: 'block' }}>Фраз в ТОПе:</span>
              <strong style={{ fontSize: 16, color: '#0f172a' }}>{yandexQueries.length}</strong>
            </div>
            <div>
              <span style={{ fontSize: 11, color: 'var(--muted)', display: 'block' }}>Точек роста ТОП-3:</span>
              <strong style={{ fontSize: 16, color: '#c2410c' }}>{yandexGrowthPoints.length}</strong>
            </div>
            <div>
              <span style={{ fontSize: 11, color: 'var(--muted)', display: 'block' }}>Страниц в индексе:</span>
              <strong style={{ fontSize: 16, color: '#0f766e' }}>{webmaster.searchable_pages || 32}</strong>
            </div>
          </div>
        </div>

        <div style={{ background: '#fff', border: '1px solid #bfdbfe', borderLeft: '4px solid #2563eb', borderRadius: 8, padding: '12px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#1d4ed8' }}>🔵 Google Search Console</span>
            <span className="pill web" style={{ fontSize: 11 }}>API v1: {google?.status === 'active' ? 'Активен' : 'Подключение'}</span>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
            <div>
              <span style={{ fontSize: 11, color: 'var(--muted)', display: 'block' }}>Показы в Google:</span>
              <strong style={{ fontSize: 16, color: '#0f172a' }}>{google?.total_impressions || 0}</strong>
            </div>
            <div>
              <span style={{ fontSize: 11, color: 'var(--muted)', display: 'block' }}>Клики из Google:</span>
              <strong style={{ fontSize: 16, color: '#047857' }}>{google?.total_clicks || 0}</strong>
            </div>
            <div>
              <span style={{ fontSize: 11, color: 'var(--muted)', display: 'block' }}>Фраз в выдаче:</span>
              <strong style={{ fontSize: 16, color: '#1d4ed8' }}>{googleQueries.length}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* 2.2 SEARCH ENGINE FILTER TAB BAR */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, padding: '10px 14px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>Поисковая система:</span>
          <button
            className={searchEngine === 'all' ? 'primary small-text' : 'secondary small-text'}
            onClick={() => setSearchEngine('all')}
            style={{ borderRadius: 20, padding: '4px 12px' }}
          >
            🌐 Все поисковики ({combinedQueries.length || (yandexQueries.length + googleQueries.length)})
          </button>
          <button
            className={searchEngine === 'yandex' ? 'primary small-text' : 'secondary small-text'}
            onClick={() => setSearchEngine('yandex')}
            style={{ borderRadius: 20, padding: '4px 12px', background: searchEngine === 'yandex' ? '#ea580c' : undefined, borderColor: searchEngine === 'yandex' ? '#ea580c' : undefined, color: searchEngine === 'yandex' ? '#fff' : undefined }}
          >
            🔴 Яндекс ({yandexQueries.length})
          </button>
          <button
            className={searchEngine === 'google' ? 'primary small-text' : 'secondary small-text'}
            onClick={() => setSearchEngine('google')}
            style={{ borderRadius: 20, padding: '4px 12px', background: searchEngine === 'google' ? '#2563eb' : undefined, borderColor: searchEngine === 'google' ? '#2563eb' : undefined, color: searchEngine === 'google' ? '#fff' : undefined }}
          >
            🔵 Google ({googleQueries.length})
          </button>
        </div>
        <small style={{ color: 'var(--muted)' }}>
          {searchEngine === 'all' ? 'Объединенный анализ видимости' : searchEngine === 'yandex' ? 'Поисковые данные Яндекса' : 'Поисковые данные Google'}
        </small>
      </div>

      {/* 2.3 TODAY PROGRESS & KEY INDICATORS */}
      <div className="form-panel full-width-panel" style={{ borderLeft: '4px solid #0f766e', background: 'linear-gradient(135deg, #f0fdfa, #f8fafc)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 8 }}>
          <div>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0, fontSize: 17, color: '#0f766e' }}>
              ⚡ Прогресс на сегодняшний день ({formatDynamicsDate(todayProg?.date || '')})
            </h2>
            <p className="field-help" style={{ margin: '4px 0 0 0' }}>
              Мгновенный срез показателей для {searchEngine === 'all' ? 'всех поисковых систем' : searchEngine === 'yandex' ? 'Яндекс Поиска' : 'Google Search Console'}
            </p>
          </div>
          <span className="pill web" style={{ fontSize: 12, padding: '4px 10px', background: '#e6fffa', color: '#047857', borderColor: '#a7f3d0' }}>
            {todayProg?.combined.ranking_status || '🟢 Позиции стабильны'}
          </span>
        </div>

        <div className="seo-today-grid">
          {/* Card 1: Clicks */}
          <div className="seo-today-card">
            <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>🖱️ Клики из поиска</span>
            <div className="seo-today-val">
              <span>{currentClicks}</span>
              {currentClicksDelta !== 0 && (
                <span className={`seo-delta-badge ${currentClicksDelta > 0 ? 'up' : 'down'}`}>
                  {currentClicksDelta > 0 ? `+${currentClicksDelta}` : currentClicksDelta} к вчера
                </span>
              )}
              {currentClicksDelta === 0 && (
                <span className="seo-delta-badge stable">0 к вчера</span>
              )}
            </div>
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>
              {searchEngine === 'all'
                ? `🔴 Яндекс: ${todayProg?.yandex.clicks || 0} • 🔵 Google: ${todayProg?.google.clicks || 0}`
                : searchEngine === 'yandex' ? 'Яндекс.Метрика + Вебмастер' : 'Google Search Console API'}
            </small>
          </div>

          {/* Card 2: Shows */}
          <div className="seo-today-card">
            <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>👁️ Показы в выдаче</span>
            <div className="seo-today-val">
              <span>{currentShows}</span>
              {currentShowsDelta !== 0 && (
                <span className={`seo-delta-badge ${currentShowsDelta > 0 ? 'up' : 'down'}`}>
                  {currentShowsDelta > 0 ? `+${currentShowsDelta}` : currentShowsDelta} к вчера
                </span>
              )}
              {currentShowsDelta === 0 && (
                <span className="seo-delta-badge stable">0 к вчера</span>
              )}
            </div>
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>
              {searchEngine === 'all'
                ? `🔴 Яндекс: ${todayProg?.yandex.shows || 0} • 🔵 Google: ${todayProg?.google.shows || 0}`
                : 'Показы в результатах поиска'}
            </small>
          </div>

          {/* Card 3: Avg Position */}
          <div className="seo-today-card">
            <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>🎯 Средняя позиция сайта</span>
            <div className="seo-today-val">
              <span>{currentPos}</span>
              {currentPosDelta > 0 && (
                <span className="seo-delta-badge up" title="Позиция стала выше (номер уменьшился)">
                  <TrendingUp size={12} /> ▲ +{currentPosDelta} поз.
                </span>
              )}
              {currentPosDelta < 0 && (
                <span className="seo-delta-badge down" title="Позиция просела">
                  <TrendingDown size={12} /> ▼ -{Math.abs(currentPosDelta)} поз.
                </span>
              )}
              {currentPosDelta === 0 && (
                <span className="seo-delta-badge stable">
                  <Minus size={12} /> ▬ Стабильно
                </span>
              )}
            </div>
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>
              {currentPosDelta > 0
                ? '🟢 Ранжирование улучшается'
                : currentPosDelta < 0
                ? '🔴 Небольшое снижение позиций'
                : '⚪ Результаты стабильны'}
            </small>
          </div>

          {/* Card 4: Queries Count */}
          <div className="seo-today-card">
            <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>🗂️ Фраз в выдаче</span>
            <div className="seo-today-val">
              <span>{currentQueries}</span>
              <span className="pill web" style={{ fontSize: 11 }}>В ТОП-100</span>
            </div>
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>
              {searchEngine === 'all'
                ? `🔴 Яндекс: ${todayProg?.yandex.queries_count || yandexQueries.length} • 🔵 Google: ${todayProg?.google.queries_count || googleQueries.length}`
                : 'Поисковые запросы, по которым сайт ранжируется'}
            </small>
          </div>
        </div>
      </div>

      {/* 2.4 DAILY DYNAMICS & TRENDS (CHART + TIMELINE TABLE) */}
      <div className="form-panel full-width-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 6 }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0, fontSize: 17 }}>
            📈 Динамика ранжирования и показов по дням ({searchEngine === 'all' ? 'Яндекс + Google' : searchEngine === 'yandex' ? 'Яндекс' : 'Google'})
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--muted)', marginRight: 4 }}>Период:</span>
            <button
              className={trendDays === 7 ? 'primary small-text' : 'secondary small-text'}
              onClick={() => setTrendDays(7)}
              style={{ borderRadius: 16, padding: '2px 10px', fontSize: 11 }}
            >
              7 дней
            </button>
            <button
              className={trendDays === 14 ? 'primary small-text' : 'secondary small-text'}
              onClick={() => setTrendDays(14)}
              style={{ borderRadius: 16, padding: '2px 10px', fontSize: 11 }}
            >
              14 дней
            </button>
            <button
              className={trendDays === 30 ? 'primary small-text' : 'secondary small-text'}
              onClick={() => setTrendDays(30)}
              style={{ borderRadius: 16, padding: '2px 10px', fontSize: 11 }}
            >
              30 дней
            </button>
          </div>
        </div>
        <p className="field-help" style={{ marginBottom: 10 }}>
          Посуточный тренд показов, переходов и изменений позиций. Показывает, улучшаются или ухудшаются позиции сайта день за днем.
        </p>

        {/* Visual Bar Trend */}
        {slicedDynamics.length > 0 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', marginBottom: 2 }}>
              <span>📊 График показов и тренда позиций по дням</span>
              <span>Максимум за период: <strong>{maxChartShows}</strong> показов/день</span>
            </div>
            <div className="seo-chart-container">
              {slicedDynamics.map((d, i) => {
                const shows = searchEngine === 'yandex'
                  ? (d.yandex?.shows || 0)
                  : searchEngine === 'google'
                  ? (d.google?.shows || 0)
                  : (d.total_shows || 0)
                const clicks = searchEngine === 'yandex'
                  ? (d.yandex?.clicks || 0)
                  : searchEngine === 'google'
                  ? (d.google?.clicks || 0)
                  : (d.total_clicks || 0)
                const pos = searchEngine === 'yandex'
                  ? (d.yandex_pos || d.yandex?.avg_position)
                  : searchEngine === 'google'
                  ? (d.google_pos || d.google?.avg_position)
                  : (d.yandex_pos && d.google_pos ? Math.round(((d.yandex_pos + d.google_pos)/2)*10)/10 : (d.yandex_pos || d.google_pos))
                const trend = searchEngine === 'yandex'
                  ? (d.yandex?.trend || d.yandex_trend)
                  : searchEngine === 'google'
                  ? (d.google?.trend || d.google_trend)
                  : (d.yandex_trend === 'up' || d.google_trend === 'up' ? 'up' : (d.yandex_trend === 'down' || d.google_trend === 'down' ? 'down' : 'stable'))

                const barHeight = Math.max(8, Math.round((shows / maxChartShows) * 56))
                const barColor = trend === 'up' ? '#059669' : trend === 'down' ? '#dc2626' : (searchEngine === 'google' ? '#2563eb' : searchEngine === 'yandex' ? '#ea580c' : '#0f766e')
                const titleText = `${d.date}: ${shows} показов, ${clicks} кликов, ср. поз: ${pos || '—'}`

                return (
                  <div key={i} className="seo-chart-col" title={titleText}>
                    <div
                      className="seo-chart-bar"
                      style={{
                        height: `${barHeight}px`,
                        backgroundColor: barColor,
                        opacity: shows > 0 ? 1 : 0.25
                      }}
                    />
                    <span className="seo-chart-date">{d.date.slice(5)}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Daily Dynamics Timeline Table */}
        {reversedDynamics.length > 0 ? (
          <div className="seo-table-wrap">
            <table className="seo-table">
              <thead>
                <tr>
                  <th style={{ width: '16%' }}>Дата</th>
                  <th style={{ width: '14%' }}>Клики</th>
                  <th style={{ width: '14%' }}>Показы</th>
                  <th style={{ width: searchEngine === 'all' ? '24%' : '20%' }}>Средняя позиция</th>
                  <th style={{ width: '14%' }}>Фраз в поиске</th>
                  <th style={{ width: searchEngine === 'all' ? '18%' : '22%' }}>Динамика ранжирования</th>
                </tr>
              </thead>
              <tbody>
                {reversedDynamics.map((row, idx) => {
                  const yData: Partial<DailyMetricItem> = row.yandex || {}
                  const gData: Partial<DailyMetricItem> = row.google || {}

                  const clicks = searchEngine === 'yandex'
                    ? (yData.clicks ?? 0)
                    : searchEngine === 'google'
                    ? (gData.clicks ?? 0)
                    : row.total_clicks
                  const clicksDelta = searchEngine === 'yandex'
                    ? yData.clicks_delta
                    : searchEngine === 'google'
                    ? gData.clicks_delta
                    : ((yData.clicks_delta || 0) + (gData.clicks_delta || 0))

                  const shows = searchEngine === 'yandex'
                    ? (yData.shows ?? 0)
                    : searchEngine === 'google'
                    ? (gData.shows ?? 0)
                    : row.total_shows
                  const showsDelta = searchEngine === 'yandex'
                    ? yData.shows_delta
                    : searchEngine === 'google'
                    ? gData.shows_delta
                    : ((yData.shows_delta || 0) + (gData.shows_delta || 0))

                  const yPos = row.yandex_pos || yData.avg_position
                  const gPos = row.google_pos || gData.avg_position
                  const yPosDelta = yData.pos_delta
                  const gPosDelta = gData.pos_delta

                  const queriesCount = searchEngine === 'yandex'
                    ? (yData.queries_count || 0)
                    : searchEngine === 'google'
                    ? (gData.queries_count || 0)
                    : row.total_queries

                  const engineTrend = searchEngine === 'yandex'
                    ? yData.trend
                    : searchEngine === 'google'
                    ? gData.trend
                    : (yData.trend === 'up' || gData.trend === 'up' ? 'up' : (yData.trend === 'down' || gData.trend === 'down' ? 'down' : 'stable'))

                  return (
                    <tr key={idx}>
                      <td>
                        <strong>{formatDynamicsDate(row.date)}</strong>
                        <small style={{ display: 'block', color: 'var(--muted)', fontSize: 11 }}>{row.date}</small>
                      </td>
                      <td>
                        <strong style={{ fontSize: 14 }}>{clicks}</strong>
                        {clicksDelta !== undefined && clicksDelta !== 0 && (
                          <span className={`seo-delta-badge ${clicksDelta > 0 ? 'up' : 'down'}`} style={{ marginLeft: 6 }}>
                            {clicksDelta > 0 ? `+${clicksDelta}` : clicksDelta}
                          </span>
                        )}
                      </td>
                      <td>
                        <strong style={{ fontSize: 14 }}>{shows}</strong>
                        {showsDelta !== undefined && showsDelta !== 0 && (
                          <span className={`seo-delta-badge ${showsDelta > 0 ? 'up' : 'down'}`} style={{ marginLeft: 6 }}>
                            {showsDelta > 0 ? `+${showsDelta}` : showsDelta}
                          </span>
                        )}
                      </td>
                      <td>
                        {searchEngine === 'all' ? (
                          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                            <div>
                              <small style={{ color: '#c2410c', display: 'block', fontSize: 10, fontWeight: 700 }}>ЯНДЕКС</small>
                              {yPos ? (
                                <span className={`seo-pos-badge ${yPos <= 3.5 ? 'top3' : yPos <= 10.5 ? 'growth' : 'other'}`}>
                                  {yPos}
                                </span>
                              ) : <span style={{ color: 'var(--muted)' }}>—</span>}
                            </div>
                            <div>
                              <small style={{ color: '#1d4ed8', display: 'block', fontSize: 10, fontWeight: 700 }}>GOOGLE</small>
                              {gPos ? (
                                <span className={`seo-pos-badge ${gPos <= 3.5 ? 'top3' : gPos <= 15.0 ? 'growth' : 'other'}`}>
                                  {gPos}
                                </span>
                              ) : <span style={{ color: 'var(--muted)' }}>—</span>}
                            </div>
                          </div>
                        ) : searchEngine === 'yandex' ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            {yPos ? (
                              <span className={`seo-pos-badge ${yPos <= 3.5 ? 'top3' : yPos <= 10.5 ? 'growth' : 'other'}`}>
                                {yPos} место
                              </span>
                            ) : <span style={{ color: 'var(--muted)' }}>—</span>}
                            {yPosDelta !== undefined && yPosDelta !== 0 && (
                              <span className={`seo-delta-badge ${yPosDelta > 0 ? 'up' : 'down'}`}>
                                {yPosDelta > 0 ? `▲ +${yPosDelta}` : `▼ ${yPosDelta}`}
                              </span>
                            )}
                          </div>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            {gPos ? (
                              <span className={`seo-pos-badge ${gPos <= 3.5 ? 'top3' : gPos <= 15.0 ? 'growth' : 'other'}`}>
                                {gPos} место
                              </span>
                            ) : <span style={{ color: 'var(--muted)' }}>—</span>}
                            {gPosDelta !== undefined && gPosDelta !== 0 && (
                              <span className={`seo-delta-badge ${gPosDelta > 0 ? 'up' : 'down'}`}>
                                {gPosDelta > 0 ? `▲ +${gPosDelta}` : `▼ ${gPosDelta}`}
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{queriesCount}</span> <small style={{ color: 'var(--muted)' }}>фраз</small>
                      </td>
                      <td>
                        {engineTrend === 'up' ? (
                          <span className="seo-delta-badge up" style={{ padding: '4px 8px' }}>
                            <TrendingUp size={12} /> 🟢 Позиции растут
                          </span>
                        ) : engineTrend === 'down' ? (
                          <span className="seo-delta-badge down" style={{ padding: '4px 8px' }}>
                            <TrendingDown size={12} /> 🔴 Снижение позиций
                          </span>
                        ) : (
                          <span className="seo-delta-badge stable" style={{ padding: '4px 8px' }}>
                            <Minus size={12} /> ⚪ Стабильно
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="inline-note" style={{ padding: '12px 0' }}>
            Накапливается подневная статистика ранжирования.
          </div>
        )}
      </div>

      {/* 2.5 PHRASE MOVEMENTS (WHO ROSE, WHO DROPPED) */}
      {filteredPhrases.length > 0 && (
        <div className="form-panel full-width-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 6 }}>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0, fontSize: 17 }}>
              🎯 Динамика позиций по фразам (Кто вырос, кто просел)
            </h2>
            <span className="pill web" style={{ fontSize: 11 }}>
              {filteredPhrases.length} фраз с изменением позиций
            </span>
          </div>
          <p className="field-help" style={{ marginBottom: 10 }}>
            Конкретные поисковые запросы, изменившие позиции в Яндексе и Google за последние дни.
          </p>

          <div className="seo-table-wrap">
            <table className="seo-table">
              <thead>
                <tr>
                  <th style={{ width: '40%' }}>Поисковая фраза</th>
                  <th style={{ width: '15%' }}>Поисковик</th>
                  <th style={{ width: '15%' }}>Текущая позиция</th>
                  <th style={{ width: '15%' }}>Предыдущая</th>
                  <th style={{ width: '15%' }}>Изменение</th>
                </tr>
              </thead>
              <tbody>
                {filteredPhrases.slice(0, 15).map((p, pIdx) => {
                  const isUp = p.delta > 0
                  return (
                    <tr key={pIdx}>
                      <td>
                        <strong style={{ fontSize: 13, color: '#0f172a' }}>«{p.text}»</strong>
                      </td>
                      <td>
                        {p.engine === 'google' ? (
                          <span className="pill web" style={{ fontSize: 11, background: '#eff6ff', color: '#1d4ed8', borderColor: '#bfdbfe' }}>
                            🔵 Google
                          </span>
                        ) : (
                          <span className="pill tg" style={{ fontSize: 11, background: '#fff7ed', color: '#c2410c', borderColor: '#ffedd5' }}>
                            🔴 Яндекс
                          </span>
                        )}
                      </td>
                      <td>
                        <span className={`seo-pos-badge ${p.current_pos <= 3.5 ? 'top3' : p.current_pos <= 10.5 ? 'growth' : 'other'}`}>
                          {p.current_pos} место
                        </span>
                      </td>
                      <td>
                        <span style={{ color: 'var(--muted)', fontSize: 13 }}>{p.prev_pos} место</span>
                      </td>
                      <td>
                        {isUp ? (
                          <span className="seo-delta-badge up">
                            <TrendingUp size={12} /> ▲ +{p.delta} поз.
                          </span>
                        ) : (
                          <span className="seo-delta-badge down">
                            <TrendingDown size={12} /> ▼ {p.delta} поз.
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3. FULL-WIDTH TABLE: GROWTH POINTS WITH WORDSTAT DEMAND */}
      <div className="form-panel full-width-panel" style={{ background: 'linear-gradient(135deg, #fbfdfc, #f4faf8)', border: '1px solid #b8c8c5' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 6 }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0, fontSize: 17 }}>
            🔥 Точки быстрого роста (Потенциал выхода в ТОП-3)
          </h2>
          <span className="pill tg" style={{ fontSize: 11 }}>
            {searchEngine === 'all' ? 'Яндекс + Google' : searchEngine === 'yandex' ? 'Яндекс (поз. 4–10)' : 'Google (поз. 4–20)'}
          </span>
        </div>
        <p className="field-help" style={{ marginBottom: 12 }}>
          По этим запросам поисковики уже выводят сайт близко к ТОП-3. Дожим в ТОП-3 по этим фразам обеспечит основной приток целевых B2B-клиентов.
        </p>
        
        {displayGrowthPoints.length > 0 ? (
          <div className="seo-table-wrap">
            <table className="seo-table">
              <thead>
                <tr>
                  <th style={{ width: '30%' }}>Поисковая фраза</th>
                  <th style={{ width: '12%' }}>Поисковик</th>
                  <th style={{ width: '11%' }}>Позиция</th>
                  <th style={{ width: '10%' }}>Показы</th>
                  <th style={{ width: '18%' }}>Спрос Вордстат / Рынок</th>
                  <th style={{ width: '14%' }}>Потенциал ТОП-3</th>
                  <th style={{ width: '15%' }}>SEO-Приоритет</th>
                </tr>
              </thead>
              <tbody>
                {displayGrowthPoints.map((g, idx) => {
                  const isHighPriority = g.priority === 'high' || (idx === 0 && (g.wordstat_demand || 0) > 0)
                  const demand = g.wordstat_demand || 0
                  const potentialClicks = g.top3_potential_clicks || Math.round(demand * 0.35)
                  const isGoogle = (g as any).engine === 'google'
                  return (
                    <tr key={idx} className={isHighPriority ? 'priority-row-high' : ''}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          <strong style={{ fontSize: 14, color: '#0f172a' }}>«{g.text}»</strong>
                          {isHighPriority && <span className="wordstat-badge-top">🔥 Приоритет №1</span>}
                        </div>
                      </td>
                      <td>
                        {isGoogle ? (
                          <span className="pill web" style={{ fontSize: 11, background: '#eff6ff', color: '#1d4ed8', borderColor: '#bfdbfe' }}>🔵 Google</span>
                        ) : (
                          <span className="pill tg" style={{ fontSize: 11, background: '#fff7ed', color: '#c2410c', borderColor: '#ffedd5' }}>🔴 Яндекс</span>
                        )}
                      </td>
                      <td>
                        <span className="seo-pos-badge growth">{g.avg_position} место</span>
                      </td>
                      <td>
                        <strong style={{ fontSize: 14 }}>{g.shows}</strong> <small style={{ color: 'var(--muted)' }}>показов</small>
                      </td>
                      <td>
                        <span className="wordstat-demand-val">{demand.toLocaleString('ru-RU')}</span> <small style={{ color: 'var(--muted)' }}>запр./мес</small>
                      </td>
                      <td>
                        <span className="wordstat-potential-val">+{potentialClicks.toLocaleString('ru-RU')}</span> <small style={{ color: 'var(--muted)' }}>кл./мес (35%)</small>
                      </td>
                      <td>
                        {isHighPriority ? (
                          <span className="pill balance" style={{ fontSize: 11, padding: '3px 8px', background: '#fef3c7', color: '#92400e', borderColor: '#fde68a' }}>
                            SEO-дожим в ТОП-3
                          </span>
                        ) : (
                          <span className="pill balance" style={{ fontSize: 11, padding: '3px 8px' }}>
                            Дожать в ТОП-3
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="inline-note" style={{ padding: '12px 0' }}>
            Идет накопление истории позиций. Как только запросы поднимутся в диапазон точек роста, система автоматически сформирует список.
          </div>
        )}
      </div>

      {/* 4. FULL-WIDTH TABLE: ALL SEARCH QUERIES WITH SEARCH FILTER */}
      <div className="form-panel full-width-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 6 }}>
          <h2 style={{ margin: 0, fontSize: 17 }}>
            🔎 Все поисковые фразы и позиции ({searchEngine === 'all' ? 'Яндекс + Google' : searchEngine === 'yandex' ? 'Яндекс' : 'Google'})
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              type="text"
              placeholder="🔍 Поиск по фразам..."
              value={querySearch}
              onChange={e => setQuerySearch(e.target.value)}
              style={{ maxWidth: 220, minHeight: 32, padding: '4px 10px', fontSize: 12, borderRadius: 6 }}
            />
            <span className="pill web" style={{ fontSize: 11 }}>{filteredQueries.length} из {rawQueriesToFilter.length} запросов</span>
          </div>
        </div>
        <p className="field-help" style={{ marginBottom: 12 }}>
          Точные поисковые запросы реальных людей, средняя позиция показа и клики в поисковых системах
        </p>

        {filteredQueries.length > 0 ? (
          <div className="seo-table-wrap">
            <table className="seo-table">
              <thead>
                <tr>
                  <th style={{ width: searchEngine === 'all' ? '38%' : '45%' }}>Поисковый запрос</th>
                  {searchEngine === 'all' ? (
                    <>
                      <th style={{ width: '13%' }}>🔴 Позиция Яндекс</th>
                      <th style={{ width: '13%' }}>🔵 Позиция Google</th>
                      <th style={{ width: '13%' }}>Показы всего</th>
                      <th style={{ width: '10%' }}>Клики</th>
                      <th style={{ width: '13%' }}>Статус</th>
                    </>
                  ) : searchEngine === 'yandex' ? (
                    <>
                      <th style={{ width: '18%' }}>Позиция в Яндексе</th>
                      <th style={{ width: '15%' }}>Показы в Яндексе</th>
                      <th style={{ width: '12%' }}>Клики</th>
                      <th style={{ width: '15%' }}>Статус</th>
                    </>
                  ) : (
                    <>
                      <th style={{ width: '18%' }}>Позиция в Google</th>
                      <th style={{ width: '15%' }}>Показы в Google</th>
                      <th style={{ width: '12%' }}>Клики</th>
                      <th style={{ width: '15%' }}>Статус</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {filteredQueries.map((q, idx) => {
                  const yPos = (q as any).yandex_pos
                  const gPos = (q as any).google_pos
                  const bestPos = yPos && gPos ? Math.min(yPos, gPos) : (yPos || gPos || 0)
                  const isTop3 = bestPos > 0 && bestPos <= 3.5
                  const isGrowth = bestPos > 3.5 && bestPos <= 12.0
                  const totalShows = (q as any).total_shows ?? (q as any).shows ?? 0
                  const totalClicks = (q as any).total_clicks ?? (q as any).clicks ?? 0

                  return (
                    <tr key={idx}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>{q.text}</span>
                          {searchEngine === 'all' && (
                            <div style={{ display: 'flex', gap: 4 }}>
                              {(q as any).in_yandex && <span style={{ fontSize: 10, color: '#ea580c', fontWeight: 'bold' }}>Яндекс</span>}
                              {(q as any).in_google && <span style={{ fontSize: 10, color: '#2563eb', fontWeight: 'bold' }}>Google</span>}
                            </div>
                          )}
                        </div>
                      </td>

                      {searchEngine === 'all' ? (
                        <>
                          <td>
                            {yPos ? (
                              <span className={`seo-pos-badge ${yPos <= 3.5 ? 'top3' : yPos <= 10.5 ? 'growth' : 'other'}`}>
                                {yPos} место
                              </span>
                            ) : (
                              <span style={{ color: 'var(--muted)' }}>—</span>
                            )}
                          </td>
                          <td>
                            {gPos ? (
                              <span className={`seo-pos-badge ${gPos <= 3.5 ? 'top3' : gPos <= 15.0 ? 'growth' : 'other'}`}>
                                {gPos} место
                              </span>
                            ) : (
                              <span style={{ color: 'var(--muted)' }}>—</span>
                            )}
                          </td>
                          <td>
                            <strong style={{ fontSize: 14 }}>{totalShows}</strong>
                          </td>
                          <td>
                            <span style={{ fontSize: 13, color: totalClicks > 0 ? '#047857' : 'var(--muted)' }}>
                              {totalClicks}
                            </span>
                          </td>
                          <td>
                            {isTop3 ? (
                              <span className="pill web" style={{ fontSize: 11 }}>🏆 ТОП-3</span>
                            ) : isGrowth ? (
                              <span className="pill tg" style={{ fontSize: 11 }}>🔥 1-я страница</span>
                            ) : (
                              <span style={{ fontSize: 12, color: 'var(--muted)' }}>Поиск</span>
                            )}
                          </td>
                        </>
                      ) : searchEngine === 'yandex' ? (
                        <>
                          <td>
                            {yPos ? (
                              <span className={`seo-pos-badge ${yPos <= 3.5 ? 'top3' : yPos <= 10.5 ? 'growth' : 'other'}`}>
                                {yPos} место
                              </span>
                            ) : (
                              <span style={{ color: 'var(--muted)' }}>—</span>
                            )}
                          </td>
                          <td>
                            <strong style={{ fontSize: 14 }}>{totalShows}</strong>
                          </td>
                          <td>
                            <span style={{ fontSize: 13, color: totalClicks > 0 ? '#047857' : 'var(--muted)' }}>
                              {totalClicks}
                            </span>
                          </td>
                          <td>
                            {yPos && yPos <= 3.5 ? (
                              <span className="pill web" style={{ fontSize: 11 }}>🏆 ТОП-3</span>
                            ) : yPos && yPos <= 10.5 ? (
                              <span className="pill tg" style={{ fontSize: 11 }}>🔥 1-я страница</span>
                            ) : (
                              <span style={{ fontSize: 12, color: 'var(--muted)' }}>Поиск</span>
                            )}
                          </td>
                        </>
                      ) : (
                        <>
                          <td>
                            {gPos ? (
                              <span className={`seo-pos-badge ${gPos <= 3.5 ? 'top3' : gPos <= 15.0 ? 'growth' : 'other'}`}>
                                {gPos} место
                              </span>
                            ) : (
                              <span style={{ color: 'var(--muted)' }}>—</span>
                            )}
                          </td>
                          <td>
                            <strong style={{ fontSize: 14 }}>{totalShows}</strong>
                          </td>
                          <td>
                            <span style={{ fontSize: 13, color: totalClicks > 0 ? '#047857' : 'var(--muted)' }}>
                              {totalClicks}
                            </span>
                          </td>
                          <td>
                            {gPos && gPos <= 3.5 ? (
                              <span className="pill web" style={{ fontSize: 11 }}>🏆 ТОП-3</span>
                            ) : gPos && gPos <= 15.0 ? (
                              <span className="pill tg" style={{ fontSize: 11 }}>🔥 Точка роста</span>
                            ) : (
                              <span style={{ fontSize: 12, color: 'var(--muted)' }}>Поиск</span>
                            )}
                          </td>
                        </>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="inline-note" style={{ padding: '12px 0' }}>
            {querySearch ? 'По вашему фильтру запросов не найдено.' : 'Поисковых показов пока не зафиксировано.'}
          </div>
        )}
      </div>

      {/* 5. 50/50 GRID: SOURCES + CONVERSION GOALS */}
      <div className="ops-grid">
        <div className="form-panel">
          <h2 style={{ fontSize: 16, marginBottom: 4 }}>Источники переходов на сайт</h2>
          <p className="field-help" style={{ marginBottom: 14 }}>Откуда приходят посетители за последние 30 дней</p>
          
          <div style={{ display: 'grid', gap: 10 }}>
            {(metrika.sources || []).map((s, idx) => {
              let label = s.name
              if (s.name === 'Direct traffic') label = 'Прямые заходы (адрес / закладки)'
              else if (s.name === 'Link traffic') label = 'Переходы по внешним ссылкам'
              else if (s.name === 'Search engine traffic') label = 'Поисковые системы (Яндекс / Google)'
              else if (s.name === 'Social network traffic') label = 'Telegram и соцсети'
              else if (s.name === 'Internal traffic') label = 'Внутренние переходы'

              const totalVisits = metrika.visits || 1
              const percent = Math.round((s.visits / totalVisits) * 100)

              return (
                <div key={idx} style={{ padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>{label}</span>
                    <strong style={{ fontSize: 13 }}>{s.visits} визитов <small style={{ color: 'var(--muted)', fontWeight: 'normal' }}>({percent}%)</small></strong>
                  </div>
                  <div className="seo-progress-bar-bg">
                    <div className="seo-progress-bar-fill" style={{ width: `${percent}%` }} />
                  </div>
                </div>
              )
            })}
            {!(metrika.sources || []).length && <div className="inline-note">Источников пока нет.</div>}
          </div>
        </div>

        <div className="form-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <h2 style={{ fontSize: 16, margin: 0 }}>🎯 Цели и конверсии (Метрика)</h2>
            <span className="pill balance" style={{ fontSize: 11 }}>Конверсия: {metrika.total_conversion_rate || 0}%</span>
          </div>
          <p className="field-help" style={{ marginBottom: 14 }}>Реальные целевые действия посетителей (кнопки, формы, кабинет)</p>
          
          <div style={{ display: 'grid', gap: 10 }}>
            {goals.map((g, idx) => {
              const reaches = g.reaches || 0
              return (
                <div key={idx} style={{ padding: '9px 12px', border: '1px solid #e2e8f0', borderRadius: 8, background: reaches > 0 ? '#f0fdf4' : '#fff', borderColor: reaches > 0 ? '#bbf7d0' : '#e2e8f0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong style={{ fontSize: 13, color: reaches > 0 ? '#166534' : '#0f172a' }}>{g.name}</strong>
                      <small style={{ display: 'block', color: 'var(--muted)', fontSize: 11 }}>Тип: {g.type}</small>
                    </div>
                    <span className={reaches > 0 ? 'pill balance' : 'pill web'} style={{ fontSize: 12 }}>
                      {reaches} {reaches === 1 ? 'действие' : reaches > 1 && reaches < 5 ? 'действия' : 'действий'}
                    </span>
                  </div>
                </div>
              )
            })}
            {!goals.length && <div className="inline-note">Цели загружаются из Яндекс.Метрики.</div>}
          </div>
        </div>
      </div>

      {/* 6. TECHNICAL STATUS (YANDEX & GOOGLE) */}
      <div className="form-panel full-width-panel">
        <h2 style={{ fontSize: 16, marginBottom: 4 }}>Индексация и техническое состояние (Яндекс и Google)</h2>
        <p className="field-help" style={{ marginBottom: 12 }}>Показатели доступности страниц для поисковых роботов Яндекса и Google</p>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          <div style={{ padding: 12, border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff' }}>
            <span style={{ display: 'block', fontSize: 12, color: 'var(--muted)' }}>ИКС сайта (Яндекс)</span>
            <strong style={{ display: 'block', fontSize: 22, color: '#0f766e', marginTop: 4 }}>{webmaster.sqi || 10}</strong>
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>Индекс качества сайта</small>
          </div>
          
          <div style={{ padding: 12, border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff' }}>
            <span style={{ display: 'block', fontSize: 12, color: 'var(--muted)' }}>Яндекс: страниц в поиске</span>
            <strong style={{ display: 'block', fontSize: 22, color: '#0f172a', marginTop: 4 }}>{webmaster.searchable_pages || 32}</strong>
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>Проиндексировано роботом</small>
          </div>
          
          <div style={{ padding: 12, border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff' }}>
            <span style={{ display: 'block', fontSize: 12, color: 'var(--muted)' }}>Google: показы в выдаче</span>
            <strong style={{ display: 'block', fontSize: 22, color: '#2563eb', marginTop: 4 }}>
              {google?.total_impressions || 0}
            </strong>
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>За последние 30 дней</small>
          </div>

          <div style={{ padding: 12, border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff' }}>
            <span style={{ display: 'block', fontSize: 12, color: 'var(--muted)' }}>Статус Google API</span>
            <strong style={{ display: 'block', fontSize: 16, color: google?.status === 'active' ? '#047857' : '#9a3412', marginTop: 6 }}>
              {google?.status === 'active' ? '● Активен' : 'Подключение'}
            </strong>
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>{google?.site_url || 'sc-domain:tenderlex.ru'}</small>
          </div>
        </div>
      </div>

      {/* 7. AI RECOMMENDATIONS & INTERACTIVE APPROVAL SECTION */}
      <div className="form-panel full-width-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 8 }}>
          <h2 style={{ margin: 0, fontSize: 17 }}>🧠 AI-Рекомендации по оптимизации (Согласование владельцем)</h2>
          <span className="pill web">Выборка: {metrika.visits} / {data.sample_target || 300} визитов</span>
        </div>
        
        <p className="field-help" style={{ marginBottom: 14 }}>
          Интеллектуальные рекомендации сформированы на основе реальных поисковых фраз Вебмастера, Google Search Console и поведенческих конверсий Метрики. Вы можете согласовать или отклонить любое предложение.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
          {recs.map(r => {
            const isApplied = r.status === 'applied'
            const isRejected = r.status === 'rejected'
            const isPending = !isApplied && !isRejected
            const isLoading = actionLoading === r.id

            return (
              <div 
                key={r.id} 
                style={{ 
                  background: '#fff', 
                  border: `1px solid ${isApplied ? '#86efac' : isRejected ? '#e2e8f0' : '#cbd5e1'}`, 
                  borderRadius: 10, 
                  padding: 16, 
                  display: 'flex', 
                  flexDirection: 'column', 
                  justifyContent: 'space-between',
                  boxShadow: isApplied ? '0 0 0 2px #dcfce7' : 'none'
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#0f766e', textTransform: 'uppercase' }}>
                      {r.category || 'Оптимизация'}
                    </span>
                    {isApplied ? (
                      <span className="pill balance" style={{ fontSize: 11, background: '#dcfce7', color: '#166534' }}>✅ Согласовано</span>
                    ) : isRejected ? (
                      <span className="pill" style={{ fontSize: 11, background: '#f1f5f9', color: '#64748b' }}>Отклонено</span>
                    ) : (
                      <span className="pill web" style={{ fontSize: 11, background: '#fef3c7', color: '#92400e' }}>Ожидает решения</span>
                    )}
                  </div>

                  <strong style={{ display: 'block', fontSize: 14, color: '#0f172a', marginBottom: 10 }}>{r.title}</strong>
                  
                  <div style={{ background: '#fef2f2', borderLeft: '3px solid #ef4444', padding: '6px 10px', borderRadius: 4, marginBottom: 8, fontSize: 12 }}>
                    <span style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#b91c1c' }}>ТЕКУЩИЙ ВАРИАНТ (ДО):</span>
                    <span style={{ color: '#475569' }}>«{r.current_text}»</span>
                  </div>

                  <div style={{ background: '#f0fdf4', borderLeft: '3px solid #16a34a', padding: '6px 10px', borderRadius: 4, marginBottom: 10, fontSize: 12 }}>
                    <span style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#15803d' }}>ПРЕДЛОЖЕНИЕ ИИ (ПОСЛЕ):</span>
                    <span style={{ color: '#0f172a', fontWeight: 600 }}>«{r.proposed_text}»</span>
                  </div>

                  <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.4, marginBottom: 8 }}>
                    <strong>💡 Обоснование:</strong> {r.rationale}
                  </div>

                  {r.impact && (
                    <div style={{ fontSize: 11, color: '#0f766e', fontWeight: 600, marginBottom: 12 }}>
                      🚀 Ожидаемый эффект: {r.impact}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 6, borderTop: '1px solid #f1f5f9', paddingTop: 10, marginTop: 4 }}>
                  {!isApplied ? (
                    <button 
                      className="primary small-text" 
                      style={{ flex: 1, minHeight: 30 }}
                      disabled={isLoading}
                      onClick={() => void handleRecAction(r.id, 'applied')}
                    >
                      {isLoading ? '...' : '✅ Согласовать'}
                    </button>
                  ) : (
                    <button 
                      className="ghost small-text" 
                      style={{ flex: 1, minHeight: 30 }}
                      disabled={isLoading}
                      onClick={() => void handleRecAction(r.id, 'pending')}
                    >
                      {isLoading ? '...' : '↩️ Отменить'}
                    </button>
                  )}
                  {isPending && (
                    <button 
                      className="ghost small-text" 
                      style={{ minHeight: 30 }}
                      disabled={isLoading}
                      onClick={() => void handleRecAction(r.id, 'rejected')}
                    >
                      Отклонить
                    </button>
                  )}
                </div>
              </div>
            )
          })}
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
        {opsStatus.services.map(service => {
          const targetUrl = service.url || (service.id === 'yandex' ? 'https://console.yandex.cloud/folders/b1gmnp1u8urslual8ht8/dashboard' : undefined)
          const RowTag = targetUrl ? 'a' : 'div'
          const rowProps = targetUrl ? {
            href: targetUrl,
            target: '_blank',
            rel: 'noopener noreferrer',
            title: `Перейти в ${service.label} (${service.detail})`,
          } : {}

          return (
            <RowTag
              key={service.id}
              className={`${service.configured ? 'api-service-row configured' : 'api-service-row'} ${targetUrl ? 'interactive' : ''}`}
              {...rowProps}
            >
              <div>
                <strong>
                  <span>{service.label}</span>
                  {targetUrl && <ExternalLink size={11} className="api-service-row-link-icon" />}
                </strong>
                <small>{service.detail} · {service.note}</small>
              </div>
              <div>
                <span>{service.status_label}</span>
                <small>{service.balance_label}</small>
              </div>
            </RowTag>
          )
        })}
      </div>
    </div>
  )
}

function ClientsView({
  clients,
  passwordResets,
  onChange,
}: {
  clients: Client[]
  passwordResets: PasswordResetRequest[]
  onChange: () => Promise<void>
}) {
  const [form, setForm] = useState({ name: '', telegram_usernames: '', telegram_id: '', notes: '' })
  const [accountForms, setAccountForms] = useState<Record<string, AccountDraft>>({})
  const [accountEditForms, setAccountEditForms] = useState<Record<string, AccountDraft>>({})
  const [grantForms, setGrantForms] = useState<Record<string, GrantDraft>>({})
  const balanceRequestIds = useRef<Record<string, string>>({})
  const balanceRequestsInFlight = useRef<Record<string, boolean>>({})
  const [mergeForms, setMergeForms] = useState<Record<string, string>>({})
  const [expandedClients, setExpandedClients] = useState<Record<string, boolean>>({})
  const [priceForms, setPriceForms] = useState<Record<string, string>>({})
  const [resetNotes, setResetNotes] = useState<Record<string, string>>({})
  const [temporaryPasswords, setTemporaryPasswords] = useState<Record<string, string>>({})
  const [deletingClientId, setDeletingClientId] = useState<string | null>(null)

  // Pagination & Filtering state
  const [searchQuery, setSearchQuery] = useState('')
  const [clientFilter, setClientFilter] = useState<'all' | 'balance' | 'web' | 'tg'>('all')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('tenderlex_admin_clients_page_size')
      if (saved) {
        const parsed = parseInt(saved, 10)
        if (parsed === 25 || parsed === 50 || parsed === 100) return parsed
      }
    } catch {}
    return 25
  })

  function handleClientPageSizeChange(nextSize: number) {
    setPageSize(nextSize)
    setPage(1)
    try {
      localStorage.setItem('tenderlex_admin_clients_page_size', String(nextSize))
    } catch {}
  }

  const webClientsCount = useMemo(
    () => clients.filter(c => c.web_users && c.web_users.length > 0).length,
    [clients]
  )
  const tgClientsCount = useMemo(
    () => clients.filter(c => ((c.telegram_accounts || []).some(a => !isSyntheticWebTelegramAccount(a)) || Boolean(c.telegram_id))).length,
    [clients]
  )
  const balanceClientsCount = useMemo(
    () => clients.filter(c => (c.usage?.money?.available_kopeks || 0) > 0).length,
    [clients]
  )

  const filteredClients = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return clients.filter(client => {
      if (clientFilter === 'web') {
        if (!client.web_users || client.web_users.length === 0) return false
      } else if (clientFilter === 'tg') {
        const realAccounts = (client.telegram_accounts || []).filter(a => !isSyntheticWebTelegramAccount(a))
        if (!realAccounts.length && !client.telegram_id) return false
      } else if (clientFilter === 'balance') {
        if (!client.usage?.money || client.usage.money.available_kopeks <= 0) return false
      }

      if (!q) return true
      const name = (client.name || '').toLowerCase()
      const username = (client.username || '').toLowerCase()
      const tgId = String(client.telegram_id || '').toLowerCase()
      const notes = (client.notes || '').toLowerCase()
      const tgAccounts = (client.telegram_accounts || []).some(a =>
        (a.username || '').toLowerCase().includes(q) ||
        String(a.telegram_id || '').toLowerCase().includes(q) ||
        (a.name || '').toLowerCase().includes(q)
      )
      const webUsers = (client.web_users || []).some(u =>
        (u.email || '').toLowerCase().includes(q) ||
        (u.name || '').toLowerCase().includes(q)
      )
      return name.includes(q) || username.includes(q) || tgId.includes(q) || notes.includes(q) || tgAccounts || webUsers
    })
  }, [clients, searchQuery, clientFilter])

  const pageCount = Math.max(1, Math.ceil(filteredClients.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const shownFrom = filteredClients.length ? (currentPage - 1) * pageSize + 1 : 0
  const shownTo = Math.min(currentPage * pageSize, filteredClients.length)
  const pagedClients = filteredClients.slice((currentPage - 1) * pageSize, currentPage * pageSize)

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
  async function deleteClient(client: Client, event?: React.MouseEvent) {
    const label = client.name || client.username || client.telegram_id || 'этого клиента'
    if (!window.confirm(`Полностью удалить клиента «${label}» вместе с задачами, балансом и привязками? Это действие нельзя отменить.`)) return
    
    if (event?.currentTarget) {
      const detailsEl = (event.currentTarget as HTMLElement).closest('details') as HTMLDetailsElement | null
      if (detailsEl) detailsEl.open = false
    }

    setDeletingClientId(client.id)
    try {
      await api(`/api/clients/${client.id}`, { method: 'DELETE' })
      await onChange()
    } catch (err) {
      alert(`Ошибка при удалении клиента: ${formatError(err)}`)
    } finally {
      setDeletingClientId(null)
    }
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
    return grantForms[client.id] || { amount_rub: '' }
  }
  function setGrantDraft(client: Client, patch: Partial<GrantDraft>) {
    const current = grantDraft(client)
    setGrantForms({ ...grantForms, [client.id]: { ...current, ...patch } })
  }
  function priceDraftKey(client: Client, kind: string) {
    return `${client.id}:${kind}`
  }
  function priceDraftValue(client: Client, kind: string, fallbackKopeks: number) {
    return priceForms[priceDraftKey(client, kind)] ?? String(kopeksToRubles(fallbackKopeks))
  }
  function setPriceDraftValue(client: Client, kind: string, value: string) {
    setPriceForms({ ...priceForms, [priceDraftKey(client, kind)]: value })
  }
  async function topUpClientBalance(client: Client) {
    const draft = grantDraft(client)
    const amountRub = Number(String(draft.amount_rub || 0).replace(',', '.'))
    const amountKopeks = Number.isFinite(amountRub) && amountRub > 0 ? rublesToKopeks(amountRub) : 0
    if (amountKopeks <= 0) return
    const requestSlot = `${client.id}:grant`
    if (balanceRequestsInFlight.current[requestSlot]) return
    const idempotencyKey = balanceRequestIds.current[requestSlot] || crypto.randomUUID()
    balanceRequestIds.current[requestSlot] = idempotencyKey
    balanceRequestsInFlight.current[requestSlot] = true
    try {
      await api(`/api/clients/${client.id}/billing/grants`, {
        method: 'POST',
        body: JSON.stringify({
          kind: 'money',
          package_id: '',
          units: 1,
          amount_kopeks: amountKopeks,
          note: 'Ручное пополнение баланса',
          operation: 'grant',
          idempotency_key: idempotencyKey,
        }),
      })
      delete balanceRequestIds.current[requestSlot]
      setGrantForms({ ...grantForms, [client.id]: { ...draft, amount_rub: '' } })
      await onChange()
    } finally {
      delete balanceRequestsInFlight.current[requestSlot]
    }
  }
  async function debitClientBalance(client: Client) {
    const draft = grantDraft(client)
    const amountRub = Number(String(draft.debit_amount_rub || 0).replace(',', '.'))
    const amountKopeks = Number.isFinite(amountRub) && amountRub > 0 ? rublesToKopeks(amountRub) : 0
    if (amountKopeks <= 0) return
    const requestSlot = `${client.id}:debit`
    if (balanceRequestsInFlight.current[requestSlot]) return
    const idempotencyKey = balanceRequestIds.current[requestSlot] || crypto.randomUUID()
    balanceRequestIds.current[requestSlot] = idempotencyKey
    balanceRequestsInFlight.current[requestSlot] = true
    try {
      await api(`/api/clients/${client.id}/billing/grants`, {
        method: 'POST',
        body: JSON.stringify({
          kind: 'money',
          package_id: '',
          units: 1,
          amount_kopeks: amountKopeks,
          note: 'Ручное списание с баланса',
          operation: 'debit',
          idempotency_key: idempotencyKey,
        }),
      })
      delete balanceRequestIds.current[requestSlot]
      setGrantForms({ ...grantForms, [client.id]: { ...draft, debit_amount_rub: '' } })
      await onChange()
    } finally {
      delete balanceRequestsInFlight.current[requestSlot]
    }
  }
  async function saveClientTariffOverride(client: Client, kind: string, fallbackKopeks: number) {
    const key = priceDraftKey(client, kind)
    const valueRub = Number(priceForms[key] ?? kopeksToRubles(fallbackKopeks))
    if (!Number.isFinite(valueRub) || valueRub < 0) return
    await api(`/api/clients/${client.id}/tariff-overrides/${kind}`, {
      method: 'PATCH',
      body: JSON.stringify({ kind, price_kopeks: rublesToKopeks(valueRub), is_enabled: valueRub > 0, note: '' }),
    })
    const nextForms = { ...priceForms }
    delete nextForms[key]
    setPriceForms(nextForms)
    await onChange()
  }
  async function verifyWebUserEmail(client: Client, user: WebUser) {
    await api(`/api/clients/${client.id}/web-users/${user.id}/verify-email`, { method: 'POST' })
    await onChange()
  }
  async function deleteWebUser(client: Client, user: WebUser) {
    const label = user.email || user.name || 'этот web-кабинет'
    if (!window.confirm(`Удалить web-кабинет «${label}» у клиента «${clientDisplayName(client)}»?\n\nКлиент, баланс, задачи и Telegram-аккаунты останутся. Пользователь больше не сможет входить на сайт с этим email.`)) return
    await api(`/api/clients/${client.id}/web-users/${user.id}`, { method: 'DELETE' })
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
      <div className="list-toolbar">
        <div className="list-toolbar-row">
          <div className="list-toolbar-meta">
            <strong>Клиенты: {shownFrom}-{shownTo} из {filteredClients.length}</strong>
            {clients.length > filteredClients.length && (
              <span className="inline-note">Всего в базе: {clients.length}</span>
            )}
          </div>
          {filteredClients.length > pageSize && (
            <div className="list-pagination toolbar-pagination">
              <button
                className="ghost small-text"
                onClick={() => setPage(v => Math.max(1, v - 1))}
                disabled={currentPage <= 1}
              >
                Назад
              </button>
              <span>Страница {currentPage} из {pageCount}</span>
              <button
                className="ghost small-text"
                onClick={() => setPage(v => Math.min(pageCount, v + 1))}
                disabled={currentPage >= pageCount}
              >
                Вперёд
              </button>
            </div>
          )}
        </div>
        <div className="list-toolbar-filters">
          <input
            className="toolbar-search"
            placeholder="Найти клиента по имени, email, Telegram нику или ID..."
            value={searchQuery}
            onChange={e => {
              setSearchQuery(e.target.value)
              setPage(1)
            }}
          />
          <div style={{ display: 'inline-flex', background: '#f1f5f9', borderRadius: 8, padding: 2, gap: 2, flexWrap: 'wrap' }}>
            <button
              type="button"
              className={`ghost small-text ${clientFilter === 'all' ? 'active' : ''}`}
              style={{
                background: clientFilter === 'all' ? '#0f766e' : 'transparent',
                color: clientFilter === 'all' ? '#fff' : '#334155',
                borderRadius: 6,
                padding: '4px 10px',
                fontWeight: 600,
                fontSize: 12,
              }}
              onClick={() => {
                setClientFilter('all')
                setPage(1)
              }}
            >
              Все ({clients.length})
            </button>
            <button
              type="button"
              className={`ghost small-text ${clientFilter === 'web' ? 'active' : ''}`}
              style={{
                background: clientFilter === 'web' ? '#0f766e' : 'transparent',
                color: clientFilter === 'web' ? '#fff' : '#334155',
                borderRadius: 6,
                padding: '4px 10px',
                fontWeight: 600,
                fontSize: 12,
              }}
              onClick={() => {
                setClientFilter('web')
                setPage(1)
              }}
            >
              Web ({webClientsCount})
            </button>
            <button
              type="button"
              className={`ghost small-text ${clientFilter === 'tg' ? 'active' : ''}`}
              style={{
                background: clientFilter === 'tg' ? '#0f766e' : 'transparent',
                color: clientFilter === 'tg' ? '#fff' : '#334155',
                borderRadius: 6,
                padding: '4px 10px',
                fontWeight: 600,
                fontSize: 12,
              }}
              onClick={() => {
                setClientFilter('tg')
                setPage(1)
              }}
            >
              Telegram ({tgClientsCount})
            </button>
            <button
              type="button"
              className={`ghost small-text ${clientFilter === 'balance' ? 'active' : ''}`}
              style={{
                background: clientFilter === 'balance' ? '#0f766e' : 'transparent',
                color: clientFilter === 'balance' ? '#fff' : '#334155',
                borderRadius: 6,
                padding: '4px 10px',
                fontWeight: 600,
                fontSize: 12,
              }}
              onClick={() => {
                setClientFilter('balance')
                setPage(1)
              }}
            >
              С балансом ({balanceClientsCount})
            </button>
          </div>
          <select
            value={pageSize}
            onChange={e => handleClientPageSizeChange(Number(e.target.value))}
            style={{ width: 'auto', minWidth: 100, fontSize: 12 }}
            title="Количество клиентов на странице"
          >
            <option value={25}>По 25</option>
            <option value={50}>По 50</option>
            <option value={100}>По 100</option>
          </select>
        </div>
      </div>
      {filteredClients.length === 0 ? (
        <div className="form-panel full-width-panel" style={{ textAlign: 'center', padding: '36px 16px', color: '#64748b' }}>
          <p style={{ margin: 0, fontWeight: 600 }}>Ничего не найдено</p>
          <p style={{ margin: '4px 0 0', fontSize: 12 }}>Попробуйте изменить поисковый запрос или фильтр</p>
        </div>
      ) : (
        <div className="client-card-list">
          {pagedClients.map(client => {
          const draft = accountDraft(client)
          const accounts = (client.telegram_accounts || []).filter(account => !isSyntheticWebTelegramAccount(account))
          const webUsers = client.web_users?.length ? client.web_users : []
          const expanded = Boolean(expandedClients[client.id])
          const grant = grantDraft(client)
          const grantAmountRub = Number(String(grant.amount_rub || 0).replace(',', '.'))
          const grantAmountValid = Number.isFinite(grantAmountRub) && grantAmountRub > 0
          const debitAmountRub = Number(String(grant.debit_amount_rub || 0).replace(',', '.'))
          const debitAmountValid = Number.isFinite(debitAmountRub) && debitAmountRub > 0
          const connectedCount = accounts.filter(account => !account.is_pending).length
          const pendingCount = accounts.filter(account => account.is_pending).length
          return (
            <article className={`client-card compact ${expanded ? 'expanded' : ''}`} key={client.id}>
              <div className="client-card-head compact">
                <div className="client-title-row compact">
                  <button
                    className="client-expand-button compact"
                    title={expanded ? 'Свернуть карточку клиента' : 'Открыть карточку клиента'}
                    aria-expanded={expanded}
                    onClick={() => setExpandedClients({ ...expandedClients, [client.id]: !expanded })}
                  >
                    {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </button>
                  <div className="client-name-wrap">
                    <div className="client-name-line">
                      <h2>{client.name || 'Без имени'}</h2>
                      {!client.is_active && <StatusBadge status="disabled" />}
                    </div>
                    <p>{clientSummaryLine(client, accounts)}</p>
                    <div className="client-meta-line">
                      {client.created_at && (
                        <small className="client-registered-date">
                          Регистрация: {formatDate(client.created_at)}
                        </small>
                      )}
                      {client.onboarding?.last_event && (
                        <small> · Шаг: {onboardingStageLabel(client.onboarding.last_event)} · {formatDate(client.onboarding.last_event_at)}</small>
                      )}
                    </div>
                  </div>
                </div>
                <div className="client-summary-pills compact">
                  {webUsers.length > 0 && <span className="pill web">Web: {webUsers.length}</span>}
                  <span className="pill tg">TG: {connectedCount}</span>
                  {pendingCount > 0 && <span className="pill pending">Ожидают: {pendingCount}</span>}
                  {client.usage?.money && <span className="pill balance">{formatMoney(client.usage.money.available_kopeks)}</span>}
                </div>
                <div className="client-state">
                  <details className="client-actions-menu compact">
                    <summary title="Действия клиента" aria-label="Действия клиента">
                      <MoreHorizontal size={15} />
                    </summary>
                    <div className="client-actions-popover">
                      <button
                        className="danger small-text"
                        onClick={(e) => void deleteClient(client, e)}
                        disabled={deletingClientId === client.id}
                      >
                        <Trash2 size={13} />
                        {deletingClientId === client.id ? 'Удаление...' : 'Удалить клиента'}
                      </button>
                    </div>
                  </details>
                </div>
              </div>

              {expanded && <div className="client-card-grid">
                <div className="client-section client-telegram-section">
                  <div className="section-head">
                    <h3>Доступы</h3>
                    <span>{webUsers.length ? `Web: ${webUsers.length} · Telegram: ${accounts.length}` : accounts.length || 'нет'}</span>
                  </div>
                  <div className="access-subsection">
                    <div className="subsection-label">Web-доступ</div>
                    {webUsers.length > 0 ? (
                      <div className="web-user-list">
                        {webUsers.map(user => (
                          <div className="web-user-row" key={user.id}>
                            <div>
                              <strong>{user.email}</strong>
                              <small>
                                {[
                                  user.name || 'web-кабинет',
                                  user.created_at ? `рег. ${formatDate(user.created_at)}` : '',
                                  user.is_email_verified ? 'email подтверждён' : 'email не подтверждён',
                                  user.last_login_at ? `вход ${formatDate(user.last_login_at)}` : 'входа ещё не было',
                                ].filter(Boolean).join(' · ')}
                              </small>
                            </div>
                            <div className="web-user-actions">
                              {!user.is_active && <StatusBadge status="disabled" />}
                              {!user.is_email_verified && (
                                <button className="small-text" onClick={() => void verifyWebUserEmail(client, user)}>
                                  <CheckCircle2 size={14} />Подтвердить
                                </button>
                              )}
                              <button
                                className="icon-button small danger"
                                title="Удалить web-кабинет"
                                onClick={() => void deleteWebUser(client, user)}
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="inline-note">Web-кабинет не привязан.</div>
                    )}
                  </div>
                  <div className="access-subsection">
                    <div className="subsection-label">Telegram-аккаунты</div>
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
                            {account.created_at && (
                              <div className="account-meta-line">
                                <small>Зарегистрирован / привязан: {formatDate(account.created_at)}</small>
                              </div>
                            )}
                          </div>
                        )
                      })}
                      {!accounts.length && <div className="inline-note">Аккаунты пока не добавлены.</div>}
                      <details className="compact-form-details account-add-details">
                        <summary>Добавить Telegram</summary>
                        <div className="account-add">
                          <input placeholder="@username" value={draft.username} onChange={e => setAccountDraft(client, { username: e.target.value })} />
                          <input placeholder="ID вручную" value={draft.telegram_id} onChange={e => setAccountDraft(client, { telegram_id: e.target.value })} />
                          <input placeholder="Имя" value={draft.name} onChange={e => setAccountDraft(client, { name: e.target.value })} />
                          <button className="icon-button small" title="Добавить Telegram-аккаунт" onClick={() => void createAccount(client)} disabled={!draft.telegram_id.trim() && !draft.username.trim()}><Plus size={16} /></button>
                        </div>
                      </details>
                    </div>
                  </div>
                </div>

                <div className="client-section client-balance-section">
                  <div className="section-head">
                    <h3>Финансы</h3>
                  </div>
                  {client.usage && (
                    <div className="balance-compact-list">
                      {client.usage.money && (
                        <div className="balance-line">
                          <div>
                            <strong>Баланс</strong>
                            {client.usage.money.reserved_kopeks > 0 && (
                              <small title="Средства удержаны под задачи в работе">В обработке {formatMoney(client.usage.money.reserved_kopeks)}</small>
                            )}
                          </div>
                          <span>{formatMoney(client.usage.money.available_kopeks)}</span>
                        </div>
                      )}
                    </div>
                  )}
                  <div className="subsection-label">Операции с балансом</div>
                  <div className="balance-adjust-panel">
                    <div className="balance-adjust-row">
                      <label className="mini-field">
                        <span>Пополнить баланс, ₽</span>
                        <input
                          type="number"
                          min={0}
                          step={1}
                          placeholder="Сумма"
                          value={grant.amount_rub}
                          onChange={e => setGrantDraft(client, { amount_rub: e.currentTarget.value })}
                          onKeyDown={e => {
                            if (e.key === 'Enter' && grantAmountValid) void topUpClientBalance(client)
                          }}
                        />
                      </label>
                      <button onClick={() => void topUpClientBalance(client)} disabled={!grantAmountValid}>
                        <Plus size={16} />Пополнить
                      </button>
                    </div>
                    <div className="balance-adjust-row">
                      <label className="mini-field">
                        <span>Списать с баланса, ₽</span>
                        <input
                          type="number"
                          min={0}
                          step={1}
                          placeholder="Сумма"
                          value={grant.debit_amount_rub || ''}
                          onChange={e => setGrantDraft(client, { debit_amount_rub: e.currentTarget.value })}
                          onKeyDown={e => {
                            if (e.key === 'Enter' && debitAmountValid) void debitClientBalance(client)
                          }}
                        />
                      </label>
                      <button className="danger" onClick={() => void debitClientBalance(client)} disabled={!debitAmountValid}>
                        <Minus size={16} />Списать
                      </button>
                    </div>
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
                          <span>{item.amount_kopeks ? formatPrice(item.amount_kopeks) : item.units}</span>
                        </div>
                      ))}
                      {!client.recent_billing?.length && <div className="inline-note">Операций по балансу пока нет.</div>}
                    </div>
                  </details>
                </div>

                <div className="client-section client-settings-section">
                  <h3>Настройки клиента</h3>
                  <label className="mini-field">
                    <span>Поставщиков в выдаче</span>
                    <input
                      className="supplier-target-input"
                      type="number"
                      min={0}
                      max={100}
                      step={1}
                      placeholder="по умолчанию"
                      defaultValue={client.supplier_target_min || ''}
                      onBlur={e => patchClientSupplierTarget(client, e.currentTarget)}
                    />
                  </label>
                  {client.usage?.effective_prices && (
                    <details className="compact-form-details price-settings-details">
                      <summary>Индивидуальные цены</summary>
                      <div className="price-settings-panel">
                        {(['supplier_search', 'procurement_report', 'supplier_search_extra', 'exact_product'] as const).map(kind => {
                          const price = client.usage?.effective_prices?.[kind]
                          const fallbackKopeks = price?.price_kopeks || 0
                          return (
                            <label className="mini-field" key={kind}>
                              <span>{priceBillingLabel(kind)}, ₽</span>
                              <div className="price-override-row">
                                <input
                                  type="number"
                                  min={0}
                                  step={1}
                                  value={priceDraftValue(client, kind, fallbackKopeks)}
                                  onChange={e => setPriceDraftValue(client, kind, e.currentTarget.value)}
                                  onKeyDown={e => {
                                    if (e.key === 'Enter') void saveClientTariffOverride(client, kind, fallbackKopeks)
                                  }}
                                />
                                <button className="icon-button small" type="button" title="Сохранить цену" onClick={() => void saveClientTariffOverride(client, kind, fallbackKopeks)}>
                                  <Save size={14} />
                                </button>
                              </div>
                            </label>
                          )
                        })}
                      </div>
                    </details>
                  )}
                </div>

                <details className="client-section client-merge-section merge-client-details danger-zone-details">
                  <summary>Объединение клиентов</summary>
                  <div className="merge-client-panel">
                    <p className="field-help">Перенесёт задачи, баланс, Telegram-аккаунты и web-кабинет выбранного клиента в эту карточку.</p>
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
              </div>}
            </article>
          )
        })}
      </div>
      )}
      {filteredClients.length > pageSize && (
        <div className="list-pagination" style={{ marginTop: 8, marginBottom: 12 }}>
          <button
            className="ghost small-text"
            onClick={() => {
              setPage(v => Math.max(1, v - 1))
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
            disabled={currentPage <= 1}
          >
            Назад
          </button>
          <span>Страница {currentPage} из {pageCount}</span>
          <button
            className="ghost small-text"
            onClick={() => {
              setPage(v => Math.min(pageCount, v + 1))
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
            disabled={currentPage >= pageCount}
          >
            Вперёд
          </button>
        </div>
      )}
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
  const realAccounts = accounts.filter(account => !isSyntheticWebTelegramAccount(account))
  const connected = realAccounts.filter(account => !account.is_pending)
  const pending = realAccounts.filter(account => account.is_pending)
  const accountLabels = realAccounts
    .map(account => {
      if (account.username) return `@${account.username}`
      if (account.name && account.telegram_id) return `${account.name} (ID: ${account.telegram_id})`
      if (account.name) return account.name
      if (account.telegram_id) return `Telegram ID: ${account.telegram_id}`
      return ''
    })
    .filter(Boolean)
    .slice(0, 3)

  if (accountLabels.length) {
    const more = realAccounts.length > accountLabels.length ? ` +${realAccounts.length - accountLabels.length}` : ''
    return `${accountLabels.join(', ')}${more} · подключено ${connected.length}, ожидает ${pending.length}`
  }
  if (client.telegram_id) {
    return client.name ? `${client.name} (ID: ${client.telegram_id})` : `Telegram ID: ${client.telegram_id}`
  }
  return 'Telegram-аккаунты ожидают подключения'
}

function humanBillingKind(kind: string) {
  if (kind === 'supplier_search_extra') return 'Добор поставщиков'
  if (kind === 'exact_product') return 'Точный товар и аналоги'
  return kind === 'procurement_report' ? 'Анализ документации' : 'Поставщики'
}

function priceBillingLabel(kind: string) {
  if (kind === 'supplier_search_extra') return 'Добор'
  if (kind === 'exact_product') return 'Точный товар'
  return kind === 'procurement_report' ? 'Анализ' : 'Поиск'
}

function formatPrice(priceKopeks: number) {
  if (!priceKopeks) return 'цена не указана'
  return `${new Intl.NumberFormat('ru-RU').format(priceKopeks / 100)} ₽`
}

function formatMoney(amountKopeks: number) {
  return `${new Intl.NumberFormat('ru-RU').format(Number(amountKopeks || 0) / 100)} ₽`
}

function formatBytes(value: number) {
  const bytes = Number(value || 0)
  if (bytes <= 0) return '0 Б'
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} ГБ`
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${bytes} Б`
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
  const [nowTs, setNowTs] = useState(() => Date.now())
  const [showServerModal, setShowServerModal] = useState(false)
  const [supplementModalJob, setSupplementModalJob] = useState<Job | null>(null)
  useEffect(() => {
    const timer = setInterval(() => setNowTs(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  const [expandedJobs, setExpandedJobs] = useState<Record<string, boolean>>({})
  const [jobDetails, setJobDetails] = useState<Record<string, JobDetail | JobDetailError>>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('tenderlex_admin_jobs_page_size')
      if (saved) {
        const parsed = parseInt(saved, 10)
        if (parsed === 12 || parsed === 25 || parsed === 50 || parsed === 100) return parsed
      }
    } catch {}
    return 12
  })

  function handleJobPageSizeChange(nextSize: number) {
    setPageSize(nextSize)
    setPage(1)
    try {
      localStorage.setItem('tenderlex_admin_jobs_page_size', String(nextSize))
    } catch {}
  }

  const [showInternalJobs, setShowInternalJobs] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [modeFilter, setModeFilter] = useState('')
  const [policyFilter, setPolicyFilter] = useState('')
  const [query, setQuery] = useState('')
  const normalizedQuery = query.trim().toLowerCase()
  const filteredJobs = useMemo(() => jobs
    .filter(job => showInternalJobs || !job.is_internal)
    .filter(job => !statusFilter || job.status === statusFilter)
    .filter(job => !modeFilter || job.mode === modeFilter)
    .filter(job => !policyFilter || (job.supplier_search_policy || 'normal') === policyFilter)
    .filter(job => {
      if (!normalizedQuery) return true
      const inputNames = (job.input_files || []).map(f => f.original_filename)
      const resultNames = (job.result_files || []).map(f => f.filename)
      return [
        job.human_title,
        job.title,
        job.client_name,
        (job as any).client_email,
        (job as any).client_username,
        job.telegram_id,
        job.created_by_telegram_id,
        job.message,
        ...inputNames,
        ...resultNames,
      ].some(value => String(value || '').toLowerCase().includes(normalizedQuery))
    }), [jobs, showInternalJobs, statusFilter, modeFilter, policyFilter, normalizedQuery])
  const pageCount = Math.max(1, Math.ceil(filteredJobs.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const pageStart = (currentPage - 1) * pageSize
  const visibleJobs = filteredJobs.slice(pageStart, pageStart + pageSize)
  const hiddenInternalCount = useMemo(() => showInternalJobs ? 0 : jobs.filter(job => job.is_internal).length, [jobs, showInternalJobs])
  const statusOptions = useMemo(() => [
    { id: 'pending', label: 'В очереди' },
    { id: 'running', label: 'В работе' },
    { id: 'completed', label: 'Готово' },
    { id: 'partial', label: 'Частично готово' },
    { id: 'awaiting_customer_confirmation', label: 'Ожидает клиента' },
    { id: 'failed', label: 'Ошибка' },
    { id: 'cancelled', label: 'Отменено' },
  ], [])
  const modeOptions = useMemo(() => [
    { id: 'supplier_search', label: 'Поиск поставщиков' },
    { id: 'exact_product', label: 'Подбор товара и аналогов' },
    { id: 'procurement_report', label: 'Анализ документации' },
    { id: 'analysis_and_suppliers', label: 'Анализ + поиск' },
  ], [])
  const policyOptions = useMemo(() => [
    { id: 'normal', label: 'Обычный поиск' },
    { id: 'minprom_registry_only', label: 'Только реестр (Минпромторг)' },
    { id: 'minprom_registry_priority', label: 'Реестр в приоритете (Минпромторг)' },
  ], [])
  const shownFrom = filteredJobs.length ? pageStart + 1 : 0
  const shownTo = Math.min(filteredJobs.length, pageStart + visibleJobs.length)
  const registryFallbackJobsCount = useMemo(() => filteredJobs.filter(job => Boolean(registryFallbackOffer(job))).length, [filteredJobs])
  const hasActiveFilters = Boolean(statusFilter || modeFilter || policyFilter || query.trim())

  function resetFilters() {
    setStatusFilter('')
    setModeFilter('')
    setPolicyFilter('')
    setQuery('')
    setPage(1)
  }

  useEffect(() => {
    setPage(1)
  }, [showInternalJobs, statusFilter, modeFilter, policyFilter, normalizedQuery])

  async function adminRerun(job: Job) {
    try {
      await api(`/api/jobs/${job.id}/admin-rerun`, { method: 'POST' })
      await onChange()
    } catch (err: any) {
      alert(err.message || 'Ошибка перезапуска задачи')
    }
  }
  async function resolveJob(job: Job) {
    await api(`/api/jobs/${job.id}/resolve`, { method: 'POST' })
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
    const totalYandexCost = filteredJobs.reduce((sum, j) => sum + (j.yandex_cost_rub || 0), 0)
  return (
    <section className="stack">
      <div className="list-toolbar">
        <div className="list-toolbar-row">
          <div className="list-toolbar-meta">
            <strong>Задачи: {shownFrom}-{shownTo} из {filteredJobs.length}</strong>
            {registryFallbackJobsCount > 0 && <span className="inline-note">Без реестра: {registryFallbackJobsCount}</span>}
            {totalYandexCost > 0 && <span className="inline-note yandex-total">Яндекс API: {totalYandexCost.toFixed(2)} ₽</span>}
          </div>
          {filteredJobs.length > pageSize && (
            <div className="list-pagination toolbar-pagination">
              <button className="ghost small-text" onClick={() => setPage(value => Math.max(1, value - 1))} disabled={currentPage <= 1}>Назад</button>
              <span>Страница {currentPage} из {pageCount}</span>
              <button className="ghost small-text" onClick={() => setPage(value => Math.min(pageCount, value + 1))} disabled={currentPage >= pageCount}>Вперёд</button>
            </div>
          )}
        </div>
        <div className="list-toolbar-filters">
          <input
            className="toolbar-search"
            placeholder="Найти задачу, клиента или Telegram ID"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <select value={modeFilter} onChange={e => setModeFilter(e.target.value)}>
            <option value="">Все типы</option>
            {modeOptions.map(opt => <option key={opt.id} value={opt.id}>{opt.label}</option>)}
          </select>
          <select value={policyFilter} onChange={e => setPolicyFilter(e.target.value)}>
            <option value="">Все режимы</option>
            {policyOptions.map(opt => <option key={opt.id} value={opt.id}>{opt.label}</option>)}
          </select>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">Все статусы</option>
            {statusOptions.map(opt => <option key={opt.id} value={opt.id}>{opt.label}</option>)}
          </select>
          <select
            value={pageSize}
            onChange={e => handleJobPageSizeChange(Number(e.target.value))}
            style={{ width: 'auto', minWidth: 90, fontSize: 12 }}
            title="Количество задач на странице"
          >
            <option value={12}>По 12</option>
            <option value={25}>По 25</option>
            <option value={50}>По 50</option>
            <option value={100}>По 100</option>
          </select>
          {hasActiveFilters && (
            <button className="ghost small-text" onClick={resetFilters} title="Сбросить фильтры" style={{ height: '34px', padding: '0 10px' }}>
              Сброс
            </button>
          )}
          {hiddenInternalCount > 0 && (
            <label className="toolbar-checkbox">
              <input type="checkbox" checked={showInternalJobs} onChange={e => setShowInternalJobs(e.target.checked)} />
              Показать служебные ({hiddenInternalCount})
            </label>
          )}
        </div>
      </div>
      <div className="job-list">
        {visibleJobs.map(job => {
          const supplierPolicyLabel = supplierSearchPolicyLabel(job)
          const supplierRunLabel = supplierRunTypeLabel(job)
          const fallbackOffer = registryFallbackOffer(job)
          const fallbackStatusLabel = registryFallbackStatusLabel(job)
          const isFinished = job.status === 'completed' || job.status === 'partial' || job.status === 'failed' || job.status === 'cancelled'
          const showProgress = !isFinished || (job.status === 'running' || job.status === 'pending')
          const hasResult = job.has_result || (job.result_files && job.result_files.length > 0)
          const inputFiles = job.input_files || []
          const inputSources = job.sources || []
          const hasInput = inputFiles.length > 0 || inputSources.length > 0 || job.file_count > 0

          return (
          <article className={`job-card compact mode-${job.mode} status-${job.status} ${job.is_internal ? 'service' : ''}`} key={job.id}>
            <div className="job-card-top">
              <div className="job-title-group">
                <div className="job-title-row">
                  <h2 title={job.title}>{job.human_title || humanMode(job.mode)}</h2>
                  <StatusBadge status={job.status} />
                </div>
                <p className="job-subline">
                  {formatDate(job.created_at)}
                  {formatJobDuration(job, nowTs) ? ` · ${formatJobDuration(job, nowTs)}` : ''}
                  {' · '}{job.client_name || 'клиент не указан'}
                  {(job as any).client_email ? ` (${(job as any).client_email})` : ''}
                  {' · '}менеджер {job.created_by_telegram_id || job.telegram_id || 'не указан'}
                </p>
              </div>
              <div className="job-card-top-right">
                <JobTimeline job={job} hasInput={hasInput} />
                <div className="job-card-actions">
                  {hasResult && !job.result_files?.length && (
                    <button className="icon-button small" onClick={() => void download(job)} title="Скачать архив"><Download size={13} /></button>
                  )}
                  {(job.status === 'running' || job.status === 'pending') && (
                    <button className="icon-button small danger" onClick={() => void cancelJob(job)} title="Отменить"><XCircle size={13} /></button>
                  )}
                  {job.status === 'failed' && (
                    <button className="icon-button small" style={{ color: '#059669', borderColor: '#a7f3d0', background: '#ecfdf5' }} onClick={() => void resolveJob(job)} title="Отметить решённым (устранено)"><CheckCircle2 size={13} /></button>
                  )}
                  <button
                    className={`icon-button small ${job.has_admin_supplement ? 'accent-active' : ''}`}
                    style={job.has_admin_supplement ? { color: '#0d9488', borderColor: '#99f6e4', background: '#f0fdfa' } : undefined}
                    onClick={() => setSupplementModalJob(job)}
                    title={job.has_admin_supplement ? 'Редактировать дополнение эксперта' : 'Дополнить отчет / отправить клиенту'}
                  >
                    <MessageSquarePlus size={13} />
                  </button>
                  <button
                    className="icon-button small"
                    onClick={() => void adminRerun(job)}
                    title="Экспертный перезапуск администратора (создает новую доработанную задачу без затирания исходного отчета клиента)"
                  >
                    <Play size={13} />
                  </button>
                </div>
              </div>
            </div>

            <div className="job-card-meta-line">
              <div className="job-meta-badges">
                {(job.is_admin_rerun || (job.title && job.title.startsWith('[Админ]')) || Boolean(job.parent_job_id)) && (
                  <span
                    className="badge-pill"
                    style={{ background: '#fef3c7', color: '#92400e', borderColor: '#fcd34d', fontWeight: 700 }}
                    title="Задача создана администратором для экспертной доработки"
                  >
                    <Crown size={12} className="pill-icon" />
                    Админ-доработка
                  </span>
                )}
                <span className={`badge-pill mode mode-${job.mode}`}>{job.mode_label || humanMode(job.mode)}</span>
                {supplierPolicyLabel && <span className={`badge-pill supplier-policy ${job.supplier_search_policy || 'normal'}`}>{supplierPolicyLabel}</span>}
                {supplierRunLabel && <span className="badge-pill supplier-policy additional">{supplierRunLabel}</span>}
                {fallbackStatusLabel && <span className="badge-pill supplier-policy registry-fallback">{fallbackStatusLabel}</span>}
                {job.has_admin_supplement && (
                  <span className="badge-pill" style={{ background: '#ccfbf1', color: '#0f766e', borderColor: '#99f6e4', fontWeight: 600 }} title={job.admin_comment || 'Дополнено администратором'}>
                    ✨ Дополнено{job.admin_supplement_name ? `: ${job.admin_supplement_name}` : ''}
                  </span>
                )}
                {fallbackOffer && <span className="badge-pill">Вне реестра: {fallbackOffer.count}</span>}
                {fallbackOffer && <span className="badge-pill">Решение: {registryFallbackDecisionLabel(fallbackOffer.decision)}</span>}
                {fallbackOffer?.delivery && <span className="badge-pill">Выдача: {registryFallbackDeliveryLabel(fallbackOffer.delivery)}</span>}
                {(job.ai_model || job.ai_provider_name || job.ai_provider) && (
                  <span
                    className="badge-pill ai-model"
                    title={`ИИ: ${job.ai_provider_name || job.ai_provider || 'Провайдер не указан'} · Модель: ${job.ai_model || 'не указана'}`}
                  >
                    <BrainCircuit size={12} className="pill-icon" />
                    <span className="pill-label">{job.ai_label || [job.ai_provider_name || job.ai_provider, job.ai_model].filter(Boolean).join(' · ')}</span>
                  </span>
                )}
                <span className="badge-pill count">
                  {job.mode === 'procurement_report'
                    ? 'Анализ ТЗ'
                    : job.mode === 'exact_product'
                    ? `Товаров: ${job.verified_count || 1}`
                    : `Поставщиков: ${supplierCountLabel(job)}`}
                </span>
                {Boolean(job.yandex_cost_rub && job.yandex_cost_rub > 0) ? (
                  <span className="badge-pill yandex-cost" title={`Запросов Yandex Search API: ${job.yandex_requests_count || 0}`}>
                    🔍 {job.yandex_requests_count ? `${job.yandex_requests_count} запр. · ` : ''}{(job.yandex_cost_rub || 0).toFixed(2)} ₽
                  </span>
                ) : job.mode === 'exact_product' ? (
                  <span className="badge-pill yandex-cost" title="Подбор товара выполнен без платных запросов к Яндекс Поиску">
                    ⚡ Без Яндекс API (0.00 ₽)
                  </span>
                ) : null}
              </div>
              <div className="job-inline-downloads">
                {inputFiles.map(file => (
                  <button
                    key={`in-${job.id}-${file.id}`}
                    className="download-pill input-file"
                    onClick={() => void downloadInputFile(job, file)}
                    title={`Входной файл клиента: ${file.original_filename}`}
                  >
                    <FileText size={12} className="pill-icon" />
                    <span className="pill-filename">{file.original_filename}</span>
                  </button>
                ))}
                {inputSources.map(source => (
                  <span key={`src-${job.id}-${source.id}`} className="download-pill input-source" title={source.value}>
                    <Globe size={11} className="pill-icon" />
                    <span className="pill-label">{source.label || 'Ссылка'}: {source.value}</span>
                  </span>
                ))}
                {job.result_files && job.result_files.length > 0 && job.result_files.map(file => (
                  <button
                    key={`${job.id}-${file.kind}`}
                    className="download-pill result-file"
                    onClick={() => void download(job, file)}
                    title={file.filename}
                  >
                    <Download size={12} className="pill-icon" />
                    <span className="pill-label">{file.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {showProgress && (
              <div className="job-progress-compact">
                <Progress value={job.progress} note={job.message || humanStatus(job.status)} />
              </div>
            )}

            {job.status === 'failed' && Boolean(job.error) && !showProgress && (
              <div className="alert error compact">{job.error}</div>
            )}
          </article>
          )
        })}
        {!visibleJobs.length && <div className="empty inline-empty">Нет пользовательских задач для показа.</div>}
      </div>
      {filteredJobs.length > pageSize && (
        <div className="list-pagination">
          <button className="ghost small-text" onClick={() => setPage(value => Math.max(1, value - 1))} disabled={currentPage <= 1}>Назад</button>
          <span>Страница {currentPage} из {pageCount}</span>
          <button className="ghost small-text" onClick={() => setPage(value => Math.min(pageCount, value + 1))} disabled={currentPage >= pageCount}>Вперёд</button>
        </div>
      )}
      {supplementModalJob && (
        <AdminSupplementModal
          job={supplementModalJob}
          onClose={() => setSupplementModalJob(null)}
          onSuccess={onChange}
        />
      )}
    </section>
  )
}

function generateDefaultComment(job: Job): string {
  const title = job.human_title || job.title || 'задаче'
  if (job.mode === 'supplier_search' || job.mode === 'analysis_and_suppliers') {
    return `Наши специалисты вручную проверили и расширили выборку поставщиков по задаче «${title}». В прикрепленном файле — дополненная база с прямыми контактами производителей и отделами продаж.`
  }
  if (job.mode === 'exact_product') {
    return `Эксперты TenderLex провели расширенный подбор товара и аналогов по позиции «${title}». В отчете сформирован перечень производителей и эквивалентов с подтвержденными параметрами.`
  }
  if (job.mode === 'procurement_report') {
    return `Специалисты TenderLex дополнительно проанализировали документацию закупки «${title}». В отчете выделены ключевые требования, риски и рекомендации.`
  }
  return `Специалисты TenderLex вручную проверили и дополнили результаты по вашей задаче «${title}». Обновленный отчет прикреплен к задаче.`
}

function defaultAdminComment(job: Job): string {
  if (job.admin_comment) return job.admin_comment
  return generateDefaultComment(job)
}

type SupplementCandidate = {
  kind: string
  composite_id: string
  label: string
  filename: string
  job_id: string
  is_admin_rerun: boolean
  created_at?: string | null
}

function AdminSupplementModal({
  job,
  onClose,
  onSuccess,
}: {
  job: Job
  onClose: () => void
  onSuccess: () => Promise<void>
}) {
  const [comment, setComment] = useState(() => defaultAdminComment(job))
  const [candidates, setCandidates] = useState<SupplementCandidate[]>([])
  const [loadingCandidates, setLoadingCandidates] = useState(true)
  const [sourceMode, setSourceMode] = useState<'job_file' | 'upload'>('job_file')
  const [selectedJobFileKinds, setSelectedJobFileKinds] = useState<string[]>([])
  const [files, setFiles] = useState<File[]>([])
  const [notifyTelegram, setNotifyTelegram] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    async function loadCandidates() {
      try {
        const token = localStorage.getItem('tenderlex_admin_token') || sessionStorage.getItem('tenderlex_admin_token') || ''
        const res = await fetch(`/api/jobs/${job.id}/supplement-candidates`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (res.ok) {
          const data = await res.json()
          if (active && data.candidates && Array.isArray(data.candidates)) {
            const list: SupplementCandidate[] = data.candidates
            setCandidates(list)
            if (list.length > 0) {
              const rerunIds = list.filter(c => c.is_admin_rerun).map(c => c.composite_id)
              if (rerunIds.length > 0) {
                setSelectedJobFileKinds(rerunIds)
              } else {
                setSelectedJobFileKinds(list.map(c => c.composite_id))
              }
              setSourceMode('job_file')
            } else {
              setSourceMode('upload')
            }
          }
        }
      } catch (err) {
        console.error('Failed to load supplement candidates:', err)
      } finally {
        if (active) setLoadingCandidates(false)
      }
    }
    loadCandidates()
    return () => {
      active = false
    }
  }, [job.id])

  function toggleJobFileKind(compositeId: string) {
    setSelectedJobFileKinds(prev =>
      prev.includes(compositeId) ? prev.filter(k => k !== compositeId) : [...prev, compositeId]
    )
  }

  function selectAllJobFiles() {
    setSelectedJobFileKinds(candidates.map(f => f.composite_id))
  }

  function unselectAllJobFiles() {
    setSelectedJobFileKinds([])
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!comment.trim() && files.length === 0 && selectedJobFileKinds.length === 0 && !job.has_admin_supplement) {
      setError('Укажите комментарий или выберите хотя бы один файл.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('source_mode', sourceMode)
      if (sourceMode === 'upload') {
        files.forEach(f => formData.append('files', f))
        if (files[0]) formData.append('file', files[0])
      } else if (sourceMode === 'job_file' && selectedJobFileKinds.length > 0) {
        formData.append('file_kinds', selectedJobFileKinds.join(','))
        formData.append('file_kind', selectedJobFileKinds[0])
      }
      formData.append('comment', comment.trim())
      formData.append('notify_telegram', String(notifyTelegram))

      const token = localStorage.getItem('tenderlex_admin_token') || sessionStorage.getItem('tenderlex_admin_token') || ''
      const res = await fetch(`/api/jobs/${job.id}/admin-supplement`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText || 'Ошибка отправки')
      }
      await onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message || 'Не удалось отправить дополнение')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="server-modal-backdrop" onClick={onClose}>
      <div className="server-modal-card" style={{ maxWidth: 620 }} onClick={e => e.stopPropagation()}>
        <div className="server-modal-header">
          <h3>ДОПОЛНИТЬ ОТЧЕТ ЭКСПЕРТОМ</h3>
          <button className="server-modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 12 }}>
          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 12px', fontSize: 13 }}>
            <div style={{ fontWeight: 600, color: '#1e293b', marginBottom: 2 }}>{job.human_title || job.title}</div>
            <div style={{ color: '#64748b', fontSize: 12 }}>
              Клиент: {job.client_name || 'Не указан'} {job.created_by_telegram_id ? `· TG ID: ${job.created_by_telegram_id}` : ''}
            </div>
            {job.admin_supplement_name && (
              <div style={{ marginTop: 6, fontSize: 12, color: '#0f766e', fontWeight: 600 }}>
                ✨ Текущий прикрепленный отчет: {job.admin_supplement_name}
              </div>
            )}
          </div>

          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#334155', marginBottom: 8 }}>
              Источник файлов отчета:
            </label>

            {(candidates.length > 0 || loadingCandidates) && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600, color: '#1e293b', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="source_mode"
                    checked={sourceMode === 'job_file'}
                    onChange={() => setSourceMode('job_file')}
                  />
                  <span>Использовать файлы из задачи (исходные или после Play / перезапуска)</span>
                </label>

                {sourceMode === 'job_file' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginLeft: 24, padding: '12px', background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                    {loadingCandidates ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#64748b', padding: '12px 0' }}>
                        <Loader2 size={16} className="spin" />
                        <span>Поиск файлов задачи и экспертных перезапусков...</span>
                      </div>
                    ) : candidates.length === 0 ? (
                      <div style={{ fontSize: 13, color: '#64748b' }}>Нет готовых файлов в задаче. Загрузите файл с компьютера.</div>
                    ) : (
                      <>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: 12, color: '#64748b' }}>Выберите файлы для отправки клиенту:</span>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button
                              type="button"
                              className="ghost small-text"
                              style={{ fontSize: 11, padding: '2px 6px', height: 'auto', color: '#0d9488' }}
                              onClick={selectAllJobFiles}
                            >
                              Выбрать все
                            </button>
                            <button
                              type="button"
                              className="ghost small-text"
                              style={{ fontSize: 11, padding: '2px 6px', height: 'auto', color: '#64748b' }}
                              onClick={unselectAllJobFiles}
                            >
                              Снять все
                            </button>
                          </div>
                        </div>
                        {candidates.map(cand => {
                          const isChecked = selectedJobFileKinds.includes(cand.composite_id)
                          return (
                            <div
                              key={cand.composite_id}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                gap: 10,
                                padding: '8px 12px',
                                border: `1px solid ${isChecked ? '#0d9488' : '#cbd5e1'}`,
                                borderRadius: 6,
                                background: isChecked ? '#f0fdfa' : '#fff',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', flex: 1, minWidth: 0 }}>
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => toggleJobFileKind(cand.composite_id)}
                                />
                                <FileText size={18} color={isChecked ? '#0d9488' : '#64748b'} style={{ flexShrink: 0 }} />
                                <div style={{ fontSize: 13, minWidth: 0 }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                                    <strong style={{ color: isChecked ? '#0f766e' : '#1e293b' }}>{cand.label}</strong>
                                    {cand.is_admin_rerun && (
                                      <span style={{ fontSize: 10, background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>
                                        👑 Доработка
                                      </span>
                                    )}
                                  </div>
                                  <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>{cand.filename}</div>
                                </div>
                              </label>

                              <button
                                type="button"
                                className="ghost small-text"
                                style={{
                                  flexShrink: 0,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 4,
                                  padding: '4px 10px',
                                  fontSize: 12,
                                  fontWeight: 600,
                                  color: '#0d9488',
                                  border: '1px solid #99f6e4',
                                  background: '#fff',
                                  borderRadius: 6,
                                  cursor: 'pointer',
                                }}
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  window.open(`/api/jobs/${cand.job_id}/download/${cand.kind}`, '_blank')
                                }}
                                title="Скачать и открыть файл для проверки"
                              >
                                <Download size={13} />
                                <span>Открыть</span>
                              </button>
                            </div>
                          )
                        })}
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600, color: '#1e293b', cursor: 'pointer' }}>
                <input
                  type="radio"
                  name="source_mode"
                  checked={sourceMode === 'upload'}
                  onChange={() => setSourceMode('upload')}
                />
                <span>Загрузить отредактированные файлы с компьютера</span>
              </label>

              {sourceMode === 'upload' && (
                <div style={{ marginLeft: 24, marginTop: 4 }}>
                  <input
                    type="file"
                    multiple
                    accept=".xlsx,.xls,.docx,.doc,.pdf,.zip"
                    onChange={e => {
                      if (e.target.files) {
                        setFiles(Array.from(e.target.files))
                      }
                    }}
                    style={{ fontSize: 13, width: '100%', padding: '8px', border: '1px solid #cbd5e1', borderRadius: 6, background: '#fff' }}
                  />
                  {files.length > 0 && (
                    <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {files.map((f, i) => (
                        <span key={i} style={{ fontSize: 12, background: '#f0fdfa', border: '1px solid #99f6e4', color: '#0f766e', padding: '2px 8px', borderRadius: 4 }}>
                          📎 {f.name}
                        </span>
                      ))}
                    </div>
                  )}
                  <small style={{ display: 'block', color: '#64748b', marginTop: 4, fontSize: 11 }}>
                    Можно выбрать несколько файлов (XLSX, DOCX, ZIP, PDF).
                  </small>
                </div>
              )}
            </div>
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: '#334155' }}>
                Комментарий клиенту
              </label>
              <button
                type="button"
                className="ghost small-text"
                style={{ fontSize: 11, padding: '2px 8px', height: 'auto', color: '#0d9488', border: '1px solid #99f6e4', background: '#f0fdfa', borderRadius: 4, cursor: 'pointer' }}
                onClick={() => setComment(generateDefaultComment(job))}
              >
                Восстановить автотекст
              </button>
            </div>
            <textarea
              rows={4}
              value={comment}
              onChange={e => setComment(e.target.value)}
              placeholder="Укажите комментарий эксперта..."
              style={{ width: '100%', padding: '10px', fontSize: 13, border: '1px solid #cbd5e1', borderRadius: 6, resize: 'vertical' }}
            />
            <small style={{ display: 'block', color: '#64748b', marginTop: 4, fontSize: 11 }}>
              Этот комментарий будет отображаться в личном кабинете на карточке задачи и отправлен в сообщении Telegram.
            </small>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#334155', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={notifyTelegram}
              onChange={e => setNotifyTelegram(e.target.checked)}
            />
            <span>Отправить уведомление и файл в Telegram бот клиенту</span>
          </label>

          {error && (
            <div style={{ color: '#dc2626', background: '#fef2f2', border: '1px solid #fecaca', padding: '8px 12px', borderRadius: 6, fontSize: 13 }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
            <button type="button" className="ghost" onClick={onClose} disabled={loading}>
              Отмена
            </button>
            <button type="submit" className="primary" disabled={loading} style={{ background: '#0d9488', borderColor: '#0d9488' }}>
              {loading ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
              <span>{loading ? 'Отправка...' : 'Отправить клиенту'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function JobTimeline({ job, hasInput }: { job: Job; hasInput: boolean }) {
  const failed = job.status === 'failed' || Boolean(job.error)
  const completed = job.status === 'completed' || job.has_result || (job.result_files?.length || 0) > 0
  const steps = [
    { label: 'Создана', state: 'done' },
    { label: 'Входные', state: hasInput ? 'done' : job.status === 'pending' ? 'current' : 'waiting' },
    { label: 'ИИ', state: failed ? 'error' : completed || job.progress >= 70 ? 'done' : job.status === 'running' ? 'current' : 'waiting' },
    { label: 'Результат', state: failed ? 'error' : completed ? 'done' : job.status === 'running' || job.status === 'pending' ? 'current' : 'waiting' },
  ]
  return (
    <div className="job-timeline" aria-label="Этапы обработки задачи">
      {steps.map(step => (
        <div className={`job-timeline-step ${step.state}`} key={step.label} title={`Этап: ${step.label} (${step.state})`}>
          <span className="timeline-dot" />
          <span className="timeline-text">{step.label}</span>
        </div>
      ))}
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
  const extraSupplierTariffs = tariffs.filter(item => item.kind === 'supplier_search_extra')
  const exactProductTariffs = tariffs.filter(item => item.kind === 'exact_product')
  return (
    <section className="stack">
      <div className="form-panel full-width-panel">
        <h2>Новый пакет</h2>
        <div className="tariff-form-grid">
          <label className="field">
            <span>Тип</span>
            <select value={newTariff.kind} onChange={e => setNewTariff({ ...newTariff, kind: e.target.value })}>
              <option value="supplier_search">Поставщики</option>
              <option value="exact_product">Точный товар и аналоги</option>
              <option value="procurement_report">Анализ документации</option>
              <option value="supplier_search_extra">Добор поставщиков</option>
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

      <TariffGroup title="Точный товар и аналоги" tariffs={exactProductTariffs} onPatch={patchTariff} onDelete={deleteTariff} />
      <TariffGroup title="Поставщики" tariffs={supplierTariffs} onPatch={patchTariff} onDelete={deleteTariff} />
      <TariffGroup title="Анализ документации" tariffs={reportTariffs} onPatch={patchTariff} onDelete={deleteTariff} />
      <TariffGroup title="Добор поставщиков" tariffs={extraSupplierTariffs} onPatch={patchTariff} onDelete={deleteTariff} />
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

function SettingsView({
  settings,
  minpromRegistry,
  onChange,
}: {
  settings: SettingsPayload
  minpromRegistry: MinpromRegistryStatus | null
  onChange: () => Promise<void>
}) {
  const [draft, setDraft] = useState(settings)
  const [adapterKey, setAdapterKey] = useState('')
  const [yandexKey, setYandexKey] = useState('')
  const [googleKey, setGoogleKey] = useState('')
  const [registryFile, setRegistryFile] = useState<File | null>(null)
  const [registryUploadBusy, setRegistryUploadBusy] = useState(false)
  const [registryUploadMessage, setRegistryUploadMessage] = useState('')
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
    const payload: SettingsPatchPayload = {
      ...draft,
      supplier_search_adapter_api_key: adapterKey,
      yandex_search_api_key: yandexKey,
      google_search_api_key: googleKey,
      supplier_search_provider_order: draft.supplier_search_provider_order || 'yandex',
    }
    await api('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    await onChange()
  }
  async function uploadMinpromRegistry() {
    if (!registryFile) return
    setRegistryUploadBusy(true)
    setRegistryUploadMessage('')
    try {
      const form = new FormData()
      form.append('file', registryFile)
      const status = await api<MinpromRegistryStatus>('/api/ops/minprom-registry/upload', {
        method: 'POST',
        body: form,
      })
      setRegistryUploadMessage(`Загружено: ${new Intl.NumberFormat('ru-RU').format(status.sqlite_entry_count || status.sqlite_count || 0)} записей.`)
      setRegistryFile(null)
      await onChange()
    } catch (err) {
      setRegistryUploadMessage(formatError(err))
    } finally {
      setRegistryUploadBusy(false)
    }
  }
  return (
    <section className="settings-grid">
      <div className="form-panel full">
        <h2>Контакты и пополнение</h2>
        <div className="settings-grid compact-grid">
          <TextField label="Telegram-бот для работы" value={draft.bot_telegram} onChange={value => setDraft({ ...draft, bot_telegram: value })} />
          <TextField label="Telegram для связи и оплаты" value={draft.contact_telegram} onChange={value => setDraft({ ...draft, contact_telegram: value })} />
          <TextField label="Email" value={draft.contact_email} onChange={value => setDraft({ ...draft, contact_email: value })} />
          <TextField label="MAX телефон для показа" value={draft.contact_max} onChange={value => setDraft({ ...draft, contact_max: value })} />
          <TextField label="MAX ссылка из приложения" value={draft.contact_max_link} onChange={value => setDraft({ ...draft, contact_max_link: value })} />
          <TextField label="Сайт" value={draft.contact_website} onChange={value => setDraft({ ...draft, contact_website: value })} />
        </div>
        <p className="field-help">Telegram — основной контакт. MAX-кнопка работает только по ссылке.</p>
        <TextArea className="payment-textarea" label="Инструкция для пополнения" value={draft.payment_instructions} onChange={value => setDraft({ ...draft, payment_instructions: value })} />
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
        <p className="field-help">В бесплатном периоде недоступна массовая обработка нескольких ТЗ. Комбинированный сценарий использует один поиск и один анализ.</p>
        <label className="switch-row"><input type="checkbox" checked={draft.onboarding_reminders_enabled} onChange={e => setDraft({ ...draft, onboarding_reminders_enabled: e.target.checked, onboarding_reminders_rollout_at: e.target.checked && !draft.onboarding_reminders_rollout_at ? new Date().toISOString() : draft.onboarding_reminders_rollout_at })} />Одна подсказка новым пользователям без запусков через 24 часа</label>
        <p className="field-help">Работает только для пользователей, открывших бота после даты включения; повторные сообщения исключены.</p>
      </div>
      <div className="form-panel">
        <h2>Отчёты</h2>
        <NumberField label="Поставщиков в выдаче" value={draft.default_supplier_target} onChange={value => setDraft({ ...draft, default_supplier_target: value })} />
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
        <p className="field-help">Поиск выполняется в реальном времени через Яндекс XML Search API.</p>
        <div className={minpromRegistry?.sqlite_ready ? 'registry-panel ready' : 'registry-panel warning'}>
          <div className="registry-heading">
            <div>
              <h3>Реестр Минпромторга</h3>
              <p>{minpromRegistry?.sqlite_ready ? 'Единая база ГИСП подключена из сервиса EmailAgent.' : 'Централизованный индекс ГИСП формируется в EmailAgent.'}</p>
            </div>
            <span className={minpromRegistry?.sqlite_ready ? 'status active' : 'status warning'}>
              {minpromRegistry?.sqlite_ready ? 'готов' : 'не готов'}
            </span>
          </div>
          <div className="registry-metrics">
            <div><span>Записей</span><strong>{new Intl.NumberFormat('ru-RU').format(minpromRegistry?.sqlite_entry_count || 0)}</strong></div>
            <div><span>XLSX</span><strong>{formatBytes(minpromRegistry?.xlsx_size_bytes || 0)}</strong></div>
            <div><span>JSONL</span><strong>{formatBytes(minpromRegistry?.index_size_bytes || 0)}</strong></div>
            <div><span>SQLite</span><strong>{formatBytes(minpromRegistry?.sqlite_size_bytes || 0)}</strong></div>
          </div>
        </div>
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
              <h3>Google Поиск (Резерв)</h3>
              <TextField label="ID поисковой системы Google" value={draft.google_search_cse_id} onChange={value => setDraft({ ...draft, google_search_cse_id: value })} />
              <SecretField label="Ключ API Google Custom Search" value={googleKey} onChange={setGoogleKey} />
            </div>
            <div className="provider-config auxiliary">
              <h3>Порядок источников</h3>
              <TextField label="Порядок поиска" value={draft.supplier_search_provider_order} onChange={value => setDraft({ ...draft, supplier_search_provider_order: value })} />
              <p className="field-help">Основной порядок: yandex.</p>
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

const AiView = memo(function AiView({ settings, onChange }: { settings: SettingsPayload; onChange: () => Promise<void> }) {
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
  function fallbackTestSlot(section: string, index: number) {
    return `fallback-${section}-${index}`
  }
  function savedModelTestSlot(model: SavedModel, index: number) {
    return `saved-model-${model.id || index}`
  }
  function renderFallbackEditor(list: FallbackEntry[], setList: (next: FallbackEntry[]) => void, section: string) {
    return (
      <div className="advanced-section">
        <button className="ghost ai-add-button" onClick={() => addFallbackItem(list, setList, section)}><Plus size={16} />Добавить модель</button>
        <p className="field-help">Пробуются по порядку, если основная модель недоступна. В конце автоматически добавляются оставшиеся бесплатные модели. Выберите из списка «Доступные модели».</p>
        {list.length > 0 && (
          <div className="model-row-head"><span>Модель</span><span></span><span></span><span></span></div>
        )}
        {list.map((entry, index) => {
          const slot = fallbackTestSlot(section, index)
          return (
            <div className="model-row-wrap" key={`${entry.provider}:${entry.modelId}-${index}`}>
              <div className="model-row">
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
                {testButton(slot, entry.provider, entry.modelId)}
                <RowActions
                  index={index}
                  count={list.length}
                  onMoveUp={() => moveFallbackItem(list, setList, index, -1, section)}
                  onMoveDown={() => moveFallbackItem(list, setList, index, 1, section)}
                  onRemove={() => removeFallbackItem(list, setList, index, section)}
                  removeTitle="Удалить из фолбэка"
                />
              </div>
              {renderTestResult(slot)}
            </div>
          )
        })}
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
        type="button"
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
          <div className="model-row-head"><span>Провайдер</span><span>Модель</span><span></span><span></span></div>
          {savedModels.map((model, index) => {
            const slot = savedModelTestSlot(model, index)
            return (
              <div className="model-row-wrap" key={model.id}>
                <div className="model-row">
                  <select value={model.provider} onChange={e => { updateArray(savedModels, setSavedModels, index, { provider: e.target.value }); clearSaveStatus('models') }}>
                    <option value="">Провайдер</option>
                    {providers.map(provider => <option key={provider.id} value={provider.id}>{providerOptionLabel(provider)}</option>)}
                  </select>
                  <input value={model.modelId} placeholder="например gpt-5.4" onChange={e => { updateArray(savedModels, setSavedModels, index, { modelId: e.target.value }); clearSaveStatus('models') }} />
                  {testButton(slot, model.provider, model.modelId)}
                  <RowActions
                    index={index}
                    count={savedModels.length}
                    onMoveUp={() => moveModel(index, -1)}
                    onMoveDown={() => moveModel(index, 1)}
                    onRemove={() => removeModel(index)}
                    removeTitle="Удалить модель"
                  />
                </div>
                {renderTestResult(slot)}
              </div>
            )
          })}
          <div className="section-actions">
            <button onClick={() => void saveModelListSettings()}><Save size={16} />Сохранить модели</button>
            {sectionSaveStatus('models')}
          </div>
        </div>
      </details>
    </section>
  )
})

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
