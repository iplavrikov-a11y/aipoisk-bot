import { SeoTrafficView } from './SeoTrafficView'
import { Component, memo, useCallback, useEffect, useMemo, useRef, useState, type ErrorInfo, type ReactNode } from 'react'
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
  FileCheck,
  FileText,
  FolderArchive,
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
  RotateCw,
  Save,
  Search,
  Server,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
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
  Coins,
  MapPin,
} from 'lucide-react'
import { OutreachView } from './OutreachView'
import { McpApiView } from './McpApiView'
import { PriceMonitoringView } from './PriceMonitoringView'
import { CookiesView } from './CookiesView'

type View = 'dashboard' | 'seo' | 'clients' | 'jobs' | 'billing' | 'settings' | 'ai' | 'outreach' | 'mcp' | 'price_monitoring' | 'cookies'

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
  client_number?: number | null
  telegram_id: string
  is_pending: boolean
  source: 'telegram' | 'web' | string
  name: string
  username: string
  is_active: boolean
  is_trial: boolean
  allowed_supplier_search: boolean
  allowed_procurement_report: boolean
  allowed_exact_product?: boolean
  monthly_job_limit: number
  monthly_supplier_search_limit: number
  monthly_procurement_report_limit: number
  monthly_file_limit: number
  supplier_target_min: number
  notes: string
  jobs_count?: number
  has_custom_tariffs?: boolean
  telegram_accounts: TelegramAccount[]
  web_users: WebUser[]
  usage: ClientUsage | null
  recent_usage: UsageEntry[]
  recent_billing: BillingTransaction[]
  has_api_key?: boolean
  api_keys?: Array<{
    id: string
    key_prefix: string
    name: string
    is_active: boolean
    allowed_supplier_search: boolean
    allowed_exact_product: boolean
    allowed_procurement_report: boolean
    spent_supplier_search: number
    spent_exact_product: number
    spent_procurement_report: number
    total_spent: number
    last_used_at?: string | null
    created_at?: string | null
  }>
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

type AdminSyncCheckResponse = {
  version_key: string
  clients_count: number
  jobs_count: number
  latest_client?: {
    id: string
    client_number?: number | null
    name: string
    source: string
    contact: string
    created_at: string
  } | null
}

type AdminToast = {
  id: string
  title: string
  message: string
  type?: 'client' | 'job' | 'info'
  clientId?: string
  createdAt: number
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
  has_custom_tariffs?: boolean
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

type ExactSelection = {
  mode?: string
  pricing_mode?: string
  revision: string
  max_positions: number
  price_kopeks: number
  selected_ids: string[]
  confirmed: boolean
  items: Array<{ id: string; position_no: number; name: string; name_in_tz?: string }>
}

type MultiItemSelection = Pick<ExactSelection, 'items' | 'selected_ids' | 'confirmed'> & { mode?: string; revision?: string }

type Job = {
  id: string
  job_number?: number | null
  client_id: string
  client_number?: number | null
  client_name: string
  client_email?: string
  client_username?: string
  created_by_label?: string
  telegram_id: string
  created_by_telegram_id: string
  mode: string
  mode_label: string
  supplier_search_policy: string
  supplier_search_run_type: string
  multi_item_mode?: string
  delivery_city?: string
  geo_radius_km?: number | null
  geo_scope?: string
  confirmation_expires_at?: string | null
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
  position_selection?: ExactSelection | null
  multi_item_selection?: MultiItemSelection | null
  exact_product_selection?: ExactSelection | null
  admin_rerun?: JobAdminRerunInfo | null
  admin_reruns?: JobAdminRerunInfo[]
}

type JobAdminRerunInfo = {
  mode?: string
  confirmation_kind?: string
  multi_item_mode?: string
  position_selection?: ExactSelection | null
  multi_item_selection?: MultiItemSelection | null
  exact_product_selection?: ExactSelection | null
  id: string
  job_number?: number | null
  status: string
  progress: number
  message: string
  verified_count?: number
  files: JobResultFile[]
  yandex_requests_count?: number
  yandex_cost_rub?: number
  created_at?: string | null
  completed_at?: string | null
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
  created_at?: string | null
}

type JobInputFile = {
  id: string
  original_filename: string
  parse_status: string
  extracted_chars: number
  error: string
  created_at?: string | null
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
  geo_radius_search_enabled_global?: boolean
  geo_radius_surcharge_pct?: number
  trial_enabled: boolean
  trial_balance_rub?: number
  trial_supplier_search_limit?: number
  trial_procurement_report_limit?: number
  trial_file_limit?: number
  onboarding_reminders_enabled: boolean
  onboarding_reminders_rollout_at: string
  reengagement_reminders_enabled: boolean
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
  bonus_kopeks?: number
  bonus_rub?: number
  credit_kopeks?: number
  credit_rub?: number
  badge?: string
  description: string
  is_active: boolean
  sort_order: number
  created_at: string | null
  updated_at: string | null
}

function calculateBonusRub(amountRub: number): number {
  if (!Number.isFinite(amountRub) || amountRub <= 0) return 0
  if (amountRub >= 25000) return Math.round(amountRub * 0.5)
  if (amountRub >= 10000) return 4000
  if (amountRub >= 5000) return 1500
  if (amountRub >= 3000) return 500
  return 0
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
    daily: Array<{ date: string; supplier_search: number; exact_product?: number; procurement_report: number; analysis_and_suppliers: number; total: number }>
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
  source_url: string
  filename?: string
  index_count?: number
  sqlite_count?: number
  updated_at?: string
  updated_at_label?: string
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
    description: 'Автоматическая аналитика Метрики, Яндекс.Вебмастера и Google Search Console. Улучшения выполняем с агентом.',
  },
  outreach: {
    title: 'Лидогенерация и Рассылка',
    description: 'Массовый поиск B2B контактов по нише, отправка email-рассылок через info@tenderlex.ru и входящие ответы.',
  },
  mcp: {
    title: 'MCP & Public API',
    description: 'Управление API-ключами, интеграция с Claude Desktop, Cursor, ChatGPT Codex и прямое подключение внешних систем.',
  },
  price_monitoring: {
    title: 'Мониторинг цен',
    description: 'Закрытый модуль мониторинга цен поставщиков по спецификациям: настройки тарификации, доступ клиентов и история запусков.',
  },
  cookies: {
    title: 'Куки площадок (WAF)',
    description: 'Управление сессионными cookies для прямого сбора цен с Ozon, Wildberries, Яндекс Маркета, ВсеИнструменты и B2B каталогов.',
  },
}

const modeLabels: Record<string, string> = {
  supplier_search: 'Поиск поставщиков',
  procurement_report: 'Анализ документации',
  analysis_and_suppliers: 'Анализ + поставщики',
  exact_product: 'Подбор товара и аналогов',
  price_monitoring: 'Мониторинг цен',
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
  awaiting_exact_selection: 'ожидает выбора товаров',
  awaiting_position_selection: 'ожидает выбора позиций',
  settling: 'сохраняется результат',
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

function playNotificationChime() {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(587.33, ctx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15)
    gain.gain.setValueAtTime(0.12, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.35)
  } catch {}
}

function useTimeAgo(timestamp?: number) {
  const [text, setText] = useState('только что')
  useEffect(() => {
    if (!timestamp) return
    function update() {
      const sec = Math.max(0, Math.floor((Date.now() - (timestamp || Date.now())) / 1000))
      if (sec < 5) setText('только что')
      else if (sec < 60) setText(`${sec} сек назад`)
      else setText(`${Math.floor(sec / 60)} мин назад`)
    }
    update()
    const timer = setInterval(update, 3000)
    return () => clearInterval(timer)
  }, [timestamp])
  return text
}

function ToastContainer({
  toasts,
  onDismiss,
  onSelectClient,
}: {
  toasts: AdminToast[]
  onDismiss: (id: string) => void
  onSelectClient?: (clientId: string) => void
}) {
  if (!toasts.length) return null
  return (
    <div className="admin-toast-container" role="region" aria-live="polite" aria-label="Уведомления">
      {toasts.map(toast => (
        <div key={toast.id} className={`admin-toast-card ${toast.type || 'client'}`}>
          <div className="admin-toast-icon">
            {toast.type === 'job' ? <Sparkles size={16} /> : <Users size={16} />}
          </div>
          <div className="admin-toast-body">
            <div className="admin-toast-title">{toast.title}</div>
            <div className="admin-toast-msg">{toast.message}</div>
            {toast.clientId && onSelectClient && (
              <div className="admin-toast-actions">
                <button
                  type="button"
                  className="admin-toast-view-btn"
                  onClick={() => {
                    onSelectClient(toast.clientId!)
                    onDismiss(toast.id)
                  }}
                >
                  Показать клиента →
                </button>
              </div>
            )}
          </div>
          <button
            type="button"
            className="admin-toast-close"
            onClick={() => onDismiss(toast.id)}
            aria-label="Закрыть"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}

const VALID_VIEWS: readonly View[] = ['dashboard', 'seo', 'clients', 'jobs', 'outreach', 'billing', 'settings', 'ai', 'mcp', 'price_monitoring', 'cookies'] as const

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

interface ErrorBoundaryProps {
  children: ReactNode
  sectionName?: string
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class AdminErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('AdminErrorBoundary caught error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, margin: '20px auto', maxWidth: 640, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, color: '#991b1b' }}>
          <h3 style={{ margin: '0 0 8px 0', fontSize: 16 }}>Ошибка отображения раздела {this.props.sectionName ? `«${this.props.sectionName}»` : ''}</h3>
          <p style={{ margin: '0 0 12px 0', fontSize: 13, color: '#7f1d1d' }}>
            {this.state.error?.message || 'Произошла непредвиденная ошибка при отображении данных.'}
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="ghost small-text"
              style={{ background: '#fff', border: '1px solid #fca5a5', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}
              onClick={() => {
                this.setState({ hasError: false, error: null })
              }}
            >
              Попробовать снова
            </button>
            <button
              type="button"
              className="ghost small-text"
              style={{ background: '#0f766e', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}
              onClick={() => {
                window.location.reload()
              }}
            >
              Перезагрузить страницу
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export function App() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authenticated, setAuthenticated] = useState(false)
  const [view, setViewState] = useState<View>(getInitialView)
  const viewRef = useRef(view)
  viewRef.current = view
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [jobsLoading, setJobsLoading] = useState(false)
  const [opsStatus, setOpsStatus] = useState<OpsStatus | null>(null)
  const [minpromRegistry, setMinpromRegistry] = useState<MinpromRegistryStatus | null>(null)
  const [settings, setSettings] = useState<SettingsPayload | null>(null)
  const [analytics, setAnalytics] = useState<BotAnalytics | null>(null)
  const [tariffs, setTariffs] = useState<TariffPackage[]>([])
  const [passwordResets, setPasswordResets] = useState<PasswordResetRequest[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showServerModal, setShowServerModal] = useState(false)
  const [selectedClientForJobs, setSelectedClientForJobs] = useState<string>('')
  const loadAllRef = useRef<(force?: boolean) => Promise<void>>(() => Promise.resolve())

  function handleNavigateToClientJobs(clientId: string) {
    setSelectedClientForJobs(clientId)
    setView('jobs')
  }

  const [toasts, setToasts] = useState<AdminToast[]>([])
  const [isClientsSyncing, setIsClientsSyncing] = useState(false)
  const [lastClientsSyncAt, setLastClientsSyncAt] = useState<number>(() => Date.now())
  const [recentNewClientIds, setRecentNewClientIds] = useState<Set<string>>(() => new Set())
  const [selectedClientIdForView, setSelectedClientIdForView] = useState<string>('')
  const lastSyncVersionKeyRef = useRef<string>('')
  const prevClientsCountRef = useRef<number>(-1)

  const addToast = useCallback((toast: Omit<AdminToast, 'id' | 'createdAt'>) => {
    const id = Math.random().toString(36).slice(2, 9)
    const newToast: AdminToast = { ...toast, id, createdAt: Date.now() }
    setToasts(prev => [newToast, ...prev].slice(0, 5))
    playNotificationChime()
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 8000)
  }, [])

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  function handleSelectClient(clientId: string) {
    setSelectedClientIdForView(clientId)
    setView('clients')
  }

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
      void api<Job[]>('/api/jobs?include_internal=true&limit=100')
        .then(jobsData => { if (jobsData && viewRef.current !== 'jobs') setJobs(jobsData) })
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
    let fullJobsRequest: Promise<Job[]> | null = null
    let resumeRefreshing = false

    async function refreshFullJobHistory() {
      if (!fullJobsRequest) {
        fullJobsRequest = api<Job[]>('/api/jobs?include_internal=true&limit=2000')
          .then(updatedJobs => {
            if (!cancelled && updatedJobs) setJobs(updatedJobs)
            return updatedJobs
          })
          .finally(() => {
            fullJobsRequest = null
            if (!cancelled) setJobsLoading(false)
          })
      }
      return fullJobsRequest
    }

    // The Jobs view needs the complete history for its client-side filters and
    // pagination. Two-stage loading: stage 1 loads top 25 instantly (<100ms),
    // stage 2 loads the full history in background without blocking.
    if (view === 'jobs') {
      if (jobs.length === 0) {
        setJobsLoading(true)
        void api<Job[]>('/api/jobs?include_internal=true&limit=25')
          .then(quickJobs => {
            if (!cancelled && quickJobs && quickJobs.length > 0) {
              setJobs(prev => (prev.length > quickJobs.length ? prev : quickJobs))
            }
          })
          .catch(() => {})
          .finally(() => {
            if (!cancelled && jobs.length === 0) setJobsLoading(false)
          })
      }
      void refreshFullJobHistory().catch(() => {})
    }

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
            if (view === 'jobs') {
              // Lightweight poll: only fetch latest 50 to update active tasks and recent completions instantly
              const quickJobs = await api<Job[]>('/api/jobs?include_internal=true&limit=50')
              if (!cancelled && quickJobs) {
                setJobs(prevJobs => {
                  if (prevJobs.length === 0) return quickJobs
                  const map = new Map(prevJobs.map(j => [j.id, j]))
                  for (const qj of quickJobs) {
                    map.set(qj.id, qj)
                  }
                  return Array.from(map.values()).sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
                })
                const nowHasActive = quickJobs.some(j => j.status === 'running' || j.status === 'pending')
                if (hasActive && !nowHasActive) {
                  void api<Dashboard>('/api/dashboard').then(d => {
                    if (!cancelled && d) setDashboard(d)
                  }).catch(() => {})
                }
              }
            }

            // Live polling for dashboard & password resets
            const now = Date.now()
            const pollInterval = view === 'clients' ? 15000 : 30000
            if (now - lastClientsPoll >= pollInterval) {
              lastClientsPoll = now
              const promises: [Promise<Dashboard | null>, Promise<PasswordResetRequest[] | null>?] = [
                api<Dashboard>('/api/dashboard').catch(() => null),
              ]
              if (view === 'clients') {
                promises.push(api<PasswordResetRequest[]>('/api/web-password-resets?status=open').catch(() => null))
              }
              const [dData, pData] = await Promise.all(promises)
              if (!cancelled) {
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
      if (document.hidden || !authenticated || cancelled || resumeRefreshing) return
      resumeRefreshing = true
      void Promise.all([
        view === 'jobs' ? refreshFullJobHistory().catch(() => {}) : Promise.resolve(),
        api<Dashboard>('/api/dashboard').then(dData => {
          if (!cancelled && dData) setDashboard(dData)
        }).catch(() => {}),
        view === 'clients' ? api<PasswordResetRequest[]>('/api/web-password-resets?status=open').then(pData => {
          if (!cancelled && pData) setPasswordResets(pData)
        }).catch(() => {}) : Promise.resolve(),
      ]).finally(() => { resumeRefreshing = false })
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

  const handleManualClientsSync = useCallback(async () => {
    setIsClientsSyncing(true)
    try {
      const [cData, syncData, dData] = await Promise.all([
        api<Client[]>('/api/clients').catch(() => null),
        api<AdminSyncCheckResponse>('/api/clients/sync-check').catch(() => null),
        api<Dashboard>('/api/dashboard').catch(() => null),
      ])
      if (cData) setClients(cData)
      if (syncData) {
        lastSyncVersionKeyRef.current = syncData.version_key
        prevClientsCountRef.current = syncData.clients_count
      }
      if (dData) setDashboard(dData)
      setLastClientsSyncAt(Date.now())
    } catch {
    } finally {
      setIsClientsSyncing(false)
    }
  }, [])

  useEffect(() => {
    if (!authenticated) return

    let cancelled = false
    let timerId: any = null
    let syncInFlight = false

    async function checkSync() {
      if (cancelled || document.hidden || syncInFlight) return
      syncInFlight = true
      try {
        const syncData = await api<AdminSyncCheckResponse>('/api/clients/sync-check')
        if (!cancelled && syncData) {
          setLastClientsSyncAt(Date.now())
          const isFirstCheck = lastSyncVersionKeyRef.current === ''
          const versionChanged = syncData.version_key !== lastSyncVersionKeyRef.current
          const prevCount = prevClientsCountRef.current
          lastSyncVersionKeyRef.current = syncData.version_key

          if (isFirstCheck) {
            prevClientsCountRef.current = syncData.clients_count
          } else if (versionChanged) {
            prevClientsCountRef.current = syncData.clients_count

            // If a new client was registered
            if (prevCount >= 0 && syncData.clients_count > prevCount && syncData.latest_client) {
              const lc = syncData.latest_client
              const clientLabel = lc.client_number ? `#${lc.client_number} ${lc.name}` : lc.name
              addToast({
                type: 'client',
                title: 'Новый клиент в системе',
                message: `${clientLabel} (${lc.contact || 'контакт не указан'} · ${lc.source === 'web' ? 'Web' : 'Telegram'})`,
                clientId: lc.id,
              })
              setRecentNewClientIds(prev => new Set([...prev, lc.id]))
            }

            // Background reload clients and dashboard
            setIsClientsSyncing(true)
            const [cData, dData] = await Promise.all([
              api<Client[]>('/api/clients').catch(() => null),
              api<Dashboard>('/api/dashboard').catch(() => null),
            ])
            if (!cancelled) {
              if (cData) setClients(cData)
              if (dData) setDashboard(dData)
            }
            setIsClientsSyncing(false)
          }
        }
      } catch {
        // Ignore network glitches
      } finally {
        syncInFlight = false
      }
    }

    const intervalMs = view === 'clients' ? 3500 : 12000
    timerId = setInterval(() => {
      void checkSync()
    }, intervalMs)

    function handleFocusOrVisible() {
      if (!document.hidden && authenticated) {
        void checkSync()
      }
    }

    window.addEventListener('focus', handleFocusOrVisible)
    document.addEventListener('visibilitychange', handleFocusOrVisible)

    return () => {
      cancelled = true
      if (timerId) clearInterval(timerId)
      window.removeEventListener('focus', handleFocusOrVisible)
      document.removeEventListener('visibilitychange', handleFocusOrVisible)
    }
  }, [authenticated, view, addToast])

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
    { id: 'price_monitoring' as const, label: 'Мониторинг цен', icon: Coins },
    { id: 'cookies' as const, label: 'Куки площадок', icon: ShieldCheck },
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
        {isReady && view === 'seo' && <SeoTrafficView />}
        {isReady && view === 'clients' && (
          <AdminErrorBoundary sectionName="Клиенты">
            <ClientsView
              clients={clients}
              passwordResets={passwordResets}
              onChange={loadAll}
              onNavigateToClientJobs={handleNavigateToClientJobs}
              onNavigateToMcp={() => setView('mcp')}
              isSyncing={isClientsSyncing}
              lastSyncAt={lastClientsSyncAt}
              onManualSync={handleManualClientsSync}
              recentNewClientIds={recentNewClientIds}
              selectedClientIdFromParent={selectedClientIdForView}
              onClearSelectedClientFromParent={() => setSelectedClientIdForView('')}
            />
          </AdminErrorBoundary>
        )}
        {isReady && view === 'jobs' && (
          <AdminErrorBoundary sectionName="Задачи">
            <JobsView
              jobs={jobs}
              clients={clients}
              selectedClientId={selectedClientForJobs}
              onClearSelectedClient={() => setSelectedClientForJobs('')}
              onChange={async jobId => {
                if (jobId) {
                  const updated = await api<Job>(`/api/jobs/${jobId}`)
                  setJobs(current => current.map(job => job.id === jobId ? updated : job))
                }
                await loadAll()
              }}
              loading={jobsLoading}
            />
          </AdminErrorBoundary>
        )}
        {isReady && view === 'outreach' && <OutreachView />}
        {isReady && view === 'billing' && <BillingView tariffs={tariffs} settings={settings} onChange={loadAll} />}
        {isReady && view === 'settings' && settings && <SettingsView settings={settings} minpromRegistry={minpromRegistry} onChange={loadAll} />}
        {isReady && view === 'ai' && settings && <AiView settings={settings} onChange={stableLoadAll} onSettingsUpdated={setSettings} />}
        {isReady && view === 'mcp' && <McpApiView clients={clients} />}
        {isReady && view === 'price_monitoring' && <PriceMonitoringView onNavigateToCookies={() => setView('cookies')} />}
        {isReady && view === 'cookies' && <CookiesView onNavigateToMonitoring={() => setView('price_monitoring')} />}

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
                  <div className="server-grid-item-value">{Math.floor(opsStatus.server.disk_free_gb)} ГБ</div>
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

        <ToastContainer
          toasts={toasts}
          onDismiss={dismissToast}
          onSelectClient={handleSelectClient}
        />
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
                <span>Поиск поставщиков ({analytics.jobs.by_mode.find(m => m.mode === 'supplier_search')?.count ?? 0})</span>
              </div>
              <div className="dash-chart-legend-item">
                <span className="dash-chart-legend-dot" style={{ background: '#f59e0b' }} />
                <span>Подбор аналогов ({analytics.jobs.by_mode.find(m => m.mode === 'exact_product')?.count ?? 0})</span>
              </div>
              <div className="dash-chart-legend-item">
                <span className="dash-chart-legend-dot" style={{ background: '#10b981' }} />
                <span>Анализ документации ({analytics.jobs.by_mode.find(m => m.mode === 'procurement_report')?.count ?? 0})</span>
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
                  title={`${item.date}: Всего ${item.total} (Поставщики: ${item.supplier_search}, Подбор аналогов: ${item.exact_product ?? 0}, Анализ: ${item.procurement_report}, Комбо: ${item.analysis_and_suppliers})`}
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
  onNavigateToClientJobs,
  onNavigateToMcp,
  isSyncing,
  lastSyncAt,
  onManualSync,
  recentNewClientIds,
  selectedClientIdFromParent,
  onClearSelectedClientFromParent,
}: {
  clients: Client[]
  passwordResets: PasswordResetRequest[]
  onChange: () => Promise<void>
  onNavigateToClientJobs?: (clientId: string) => void
  onNavigateToMcp?: () => void
  isSyncing?: boolean
  lastSyncAt?: number
  onManualSync?: () => void
  recentNewClientIds?: Set<string>
  selectedClientIdFromParent?: string
  onClearSelectedClientFromParent?: () => void
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
  const [selectedClientId, setSelectedClientId] = useState(selectedClientIdFromParent || '')
  const lastSyncText = useTimeAgo(lastSyncAt)

  useEffect(() => {
    if (selectedClientIdFromParent) {
      setSelectedClientId(selectedClientIdFromParent)
      setPage(1)
    }
  }, [selectedClientIdFromParent])
  const [clientFilter, setClientFilter] = useState<'all' | 'balance' | 'web' | 'tg' | 'api'>('all')
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

  const recentClients = useMemo(() => clients.slice(0, 20), [clients])
  const otherClients = useMemo(() => (clients.length > 20 ? clients.slice(20) : []), [clients])

  function formatClientOptionLabel(c: Client): string {
    const num = c.client_number ? `#${c.client_number} ` : ''
    const name = c.name || 'Без имени'
    const email = c.web_users?.[0]?.email
    const tg = c.username ? `@${c.username}` : (c.telegram_accounts?.[0]?.username ? `@${c.telegram_accounts[0].username}` : '')
    const contact = email ? ` (${email})` : (tg ? ` (${tg})` : '')
    const tasks = c.jobs_count ?? 0
    const tasksStr = ` · ${tasks} ${tasks === 1 ? 'зад.' : 'зад.'}`
    return `${num}${name}${contact}${tasksStr}`
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
  const apiClientsCount = useMemo(
    () => clients.filter(c => c.has_api_key || (c.api_keys && c.api_keys.length > 0) || c.source === 'api').length,
    [clients]
  )

  const filteredClients = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return clients.filter(client => {
      if (selectedClientId && client.id !== selectedClientId) {
        return false
      }
      if (clientFilter === 'web') {
        if (!client.web_users || client.web_users.length === 0) return false
      } else if (clientFilter === 'tg') {
        const realAccounts = (client.telegram_accounts || []).filter(a => !isSyntheticWebTelegramAccount(a))
        if (!realAccounts.length && !client.telegram_id) return false
      } else if (clientFilter === 'balance') {
        if (!client.usage?.money || client.usage.money.available_kopeks <= 0) return false
      } else if (clientFilter === 'api') {
        if (!client.has_api_key && (!client.api_keys || client.api_keys.length === 0) && client.source !== 'api') return false
      }

      if (!q) return true
      const name = (client.name || '').toLowerCase()
      const username = (client.username || '').toLowerCase()
      const tgId = String(client.telegram_id || '').toLowerCase()
      const notes = (client.notes || '').toLowerCase()
      const clientNumberStr = client.client_number ? String(client.client_number) : ''
      const clientNumberHash = client.client_number ? `#${client.client_number}` : ''
      const tgAccounts = (client.telegram_accounts || []).some(a =>
        (a.username || '').toLowerCase().includes(q) ||
        String(a.telegram_id || '').toLowerCase().includes(q) ||
        (a.name || '').toLowerCase().includes(q)
      )
      const webUsers = (client.web_users || []).some(u =>
        (u.email || '').toLowerCase().includes(q) ||
        (u.name || '').toLowerCase().includes(q)
      )
      return (
        name.includes(q) ||
        username.includes(q) ||
        tgId.includes(q) ||
        notes.includes(q) ||
        clientNumberStr === q ||
        clientNumberHash.includes(q) ||
        tgAccounts ||
        webUsers
      )
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
    const hasCustomPrices = Boolean(
      client.has_custom_tariffs ||
      client.usage?.has_custom_tariffs ||
      (client.usage?.effective_prices &&
        Object.values(client.usage.effective_prices).some(p => p?.source === 'client_override'))
    )
    const bonusRub = hasCustomPrices ? 0 : calculateBonusRub(amountRub)
    const bonusKopeks = rublesToKopeks(bonusRub)
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
          bonus_kopeks: bonusKopeks,
          note: '',
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
          <div className="list-toolbar-sync">
            <span className="live-status-pill" title="Автоматическая синхронизация каждые 3-4 секунды без перезагрузки страницы">
              <span className={`live-dot ${isSyncing ? 'syncing' : ''}`} />
              Live
            </span>
            <span className="live-time-label">
              {lastSyncText}
            </span>
            {onManualSync && (
              <button
                type="button"
                className="sync-manual-btn"
                onClick={onManualSync}
                disabled={isSyncing}
                title="Принудительно обновить список клиентов прямо сейчас"
              >
                <RefreshCw size={12} className={isSyncing ? 'spin-icon' : ''} />
                {isSyncing ? 'Синхронизация...' : 'Обновить'}
              </button>
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
          <select
            value={selectedClientId}
            onChange={e => {
              setSelectedClientId(e.target.value)
              if (e.target.value) setSearchQuery('')
              setPage(1)
            }}
            style={{
              maxWidth: 320,
              fontSize: 13,
              fontWeight: selectedClientId ? 600 : 400,
              borderColor: selectedClientId ? '#0f766e' : undefined,
              background: selectedClientId ? '#f0fdf4' : undefined,
            }}
            title="Быстрый выбор клиента (последние 20)"
          >
            <option value="">Выбрать клиента (последние 20)...</option>
            <optgroup label="Последние 20 клиентов">
              {recentClients.map(c => (
                <option key={c.id} value={c.id}>
                  {formatClientOptionLabel(c)}
                </option>
              ))}
            </optgroup>
            {otherClients.length > 0 && (
              <optgroup label="Остальные клиенты">
                {otherClients.map(c => (
                  <option key={c.id} value={c.id}>
                    {formatClientOptionLabel(c)}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
          {selectedClientId && (
            <button
              type="button"
              className="ghost small-text"
              style={{ color: '#ef4444', fontSize: 12, padding: '4px 8px' }}
              onClick={() => {
                setSelectedClientId('')
                if (onClearSelectedClientFromParent) onClearSelectedClientFromParent()
                setPage(1)
              }}
              title="Сбросить выбранного клиента"
            >
              ✕ Сброс
            </button>
          )}
          <input
            className="toolbar-search"
            placeholder="Поиск по имени, email, Telegram нику или ID..."
            value={searchQuery}
            onChange={e => {
              setSearchQuery(e.target.value)
              if (e.target.value) setSelectedClientId('')
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
            <button
              type="button"
              className={`ghost small-text ${clientFilter === 'api' ? 'active' : ''}`}
              style={{
                background: clientFilter === 'api' ? '#7e22ce' : 'transparent',
                color: clientFilter === 'api' ? '#fff' : '#7e22ce',
                border: '1px solid #d8b4fe',
                borderRadius: 6,
                padding: '4px 10px',
                fontWeight: 600,
                fontSize: 12,
              }}
              onClick={() => {
                setClientFilter('api')
                setPage(1)
              }}
            >
              🔑 API ({apiClientsCount})
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
          const isNewClient = Boolean(
            (recentNewClientIds && recentNewClientIds.has(client.id)) ||
            (client.created_at && (Date.now() - new Date(client.created_at).getTime()) < 3 * 3600 * 1000)
          )
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
            <article className={`client-card compact ${expanded ? 'expanded' : ''} ${isNewClient ? 'is-new-client' : ''}`} key={client.id}>
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
                      {client.client_number ? (
                        <span className="client-number-badge" title={`Клиент #${client.client_number}`}>
                          #{client.client_number}
                        </span>
                      ) : null}
                      <h2>{client.name || 'Без имени'}</h2>
                      {isNewClient && (
                        <span className="badge-new-client" title="Зарегистрирован недавно">
                          Новый
                        </span>
                      )}
                      {(client.has_api_key || (client.api_keys && client.api_keys.length > 0)) && (
                        <span
                          className="badge-api-client"
                          style={{
                            background: '#ede9fe',
                            color: '#6d28d9',
                            border: '1px solid #c4b5fd',
                            borderRadius: 4,
                            padding: '1px 6px',
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                            cursor: onNavigateToMcp ? 'pointer' : 'default',
                          }}
                          title="Подключен API-доступ (TenderLex API / CRM). Нажмите для перехода в MCP & API"
                          onClick={(e) => {
                            if (onNavigateToMcp) {
                              e.stopPropagation()
                              onNavigateToMcp()
                            }
                          }}
                        >
                          🔑 API
                        </span>
                      )}
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
                  <span
                    className={`pill jobs ${(client.jobs_count || 0) > 0 ? '' : 'zero'}`}
                    title={(client.jobs_count || 0) > 0 ? 'Перейти к задачам клиента' : 'У клиента пока нет задач'}
                    onClick={(e) => {
                      if ((client.jobs_count || 0) > 0 && onNavigateToClientJobs) {
                        e.stopPropagation()
                        onNavigateToClientJobs(client.id)
                      }
                    }}
                  >
                    Задач: {client.jobs_count ?? 0}
                  </span>
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
                      {onNavigateToClientJobs && (
                        <button
                          className="small-text"
                          onClick={(e) => {
                            e.stopPropagation()
                            onNavigateToClientJobs(client.id)
                          }}
                        >
                          <FileText size={13} />
                          Задачи клиента ({client.jobs_count ?? 0})
                        </button>
                      )}
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
                    <span>
                      {[
                        webUsers.length ? `Web: ${webUsers.length}` : '',
                        accounts.length ? `Telegram: ${accounts.length}` : '',
                        client.api_keys && client.api_keys.length ? `API: ${client.api_keys.length}` : '',
                      ].filter(Boolean).join(' · ') || 'нет'}
                    </span>
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
                  <div className="access-subsection">
                    <div className="subsection-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>API-доступ (CRM / Интеграции)</span>
                      {onNavigateToMcp && (
                        <button
                          type="button"
                          className="small-text"
                          style={{ background: 'none', border: 'none', color: '#6366f1', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}
                          onClick={onNavigateToMcp}
                        >
                          Управление в MCP & API →
                        </button>
                      )}
                    </div>
                    {client.api_keys && client.api_keys.length > 0 ? (
                      <div className="account-edit-list">
                        {client.api_keys.map(k => (
                          <div className="account-edit-row" key={k.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px', background: '#f8fafc', borderRadius: 6, marginBottom: 4 }}>
                            <div>
                              <strong style={{ fontFamily: 'monospace', fontSize: '0.84rem' }}>{k.key_prefix}...</strong>
                              <span style={{ marginLeft: 8, fontSize: '0.82rem', color: '#475569' }}>{k.name || 'API Key'}</span>
                              <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: 2 }}>
                                Всего вызовов: <strong>{k.total_spent || 0}</strong> · Списание с единого баланса клиента
                              </div>
                            </div>
                            <div className="account-edit-actions">
                              {!k.is_active ? <StatusBadge status="disabled" /> : <StatusBadge status="active" />}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="inline-note" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span>API-ключ пока не привязан.</span>
                        {onNavigateToMcp && (
                          <button
                            type="button"
                            className="small-text"
                            style={{ background: 'none', border: 'none', color: '#6366f1', cursor: 'pointer' }}
                            onClick={onNavigateToMcp}
                          >
                            + Создать ключ
                          </button>
                        )}
                      </div>
                    )}
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
                    {(() => {
                      const hasCustomPrices = Boolean(
                        client.has_custom_tariffs ||
                        client.usage?.has_custom_tariffs ||
                        (client.usage?.effective_prices &&
                          Object.values(client.usage.effective_prices).some(p => p?.source === 'client_override'))
                      )
                      const quickChips = hasCustomPrices
                        ? [
                            { label: '1 000 ₽', val: '1000' },
                            { label: '3 000 ₽', val: '3000' },
                            { label: '5 000 ₽', val: '5000' },
                            { label: '10 000 ₽', val: '10000' },
                            { label: '25 000 ₽', val: '25000' },
                          ]
                        : [
                            { label: '1 000 ₽', val: '1000' },
                            { label: '3 000 ₽ (+500)', val: '3000' },
                            { label: '5 000 ₽ (+1.5k)', val: '5000' },
                            { label: '10 000 ₽ (+4k)', val: '10000' },
                            { label: '25 000 ₽ (+12.5k)', val: '25000' },
                          ]

                      return (
                        <>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                            {quickChips.map(p => (
                              <button
                                key={p.val}
                                type="button"
                                className="ghost small-text"
                                style={{
                                  padding: '2px 8px',
                                  fontSize: 11,
                                  background: grant.amount_rub === p.val ? '#0f766e' : '#f1f5f9',
                                  color: grant.amount_rub === p.val ? '#fff' : '#0f766e',
                                  fontWeight: 600,
                                  borderRadius: 6,
                                }}
                                onClick={() => setGrantDraft(client, { amount_rub: p.val })}
                              >
                                {p.label}
                              </button>
                            ))}
                          </div>
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
                              {(() => {
                                const amt = Number(String(grant.amount_rub || 0).replace(',', '.'))
                                if (hasCustomPrices) {
                                  if (amt > 0) {
                                    return (
                                      <small style={{ color: '#64748b', fontWeight: 600, display: 'block', marginTop: 2 }}>
                                        Индивидуальный тариф: к зачислению ровно {amt.toLocaleString('ru-RU')} ₽ (без бонуса)
                                      </small>
                                    )
                                  }
                                  return null
                                }
                                const bonus = calculateBonusRub(amt)
                                if (bonus > 0) {
                                  return (
                                    <small style={{ color: '#0f766e', fontWeight: 600, display: 'block', marginTop: 2 }}>
                                      Итого: {(amt + bonus).toLocaleString('ru-RU')} ₽ (оплата {amt} ₽ + бонус {bonus.toLocaleString('ru-RU')} ₽)
                                    </small>
                                  )
                                }
                                return null
                              })()}
                            </label>
                            <button onClick={() => void topUpClientBalance(client)} disabled={!grantAmountValid}>
                              <Plus size={16} />Пополнить
                            </button>
                          </div>
                        </>
                      )
                    })()}
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
                        {(['supplier_search', 'exact_product', 'procurement_report', 'supplier_search_extra', 'price_monitoring'] as const).map(kind => {
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
  if (kind === 'exact_product') return 'Подбор товара и аналогов'
  if (kind === 'price_monitoring') return 'Мониторинг цен'
  return kind === 'procurement_report' ? 'Анализ документации' : 'Поиск поставщиков'
}

function priceBillingLabel(kind: string) {
  if (kind === 'supplier_search_extra') return 'Добор'
  if (kind === 'exact_product') return 'Подбор товара'
  if (kind === 'price_monitoring') return 'Мониторинг цен'
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

function getPrimaryReport(job: Job): { file: JobResultFile; isAdmin: boolean; jobId: string; label: string } | null {
  // 1. If admin rerun completed and has files, admin result is top priority
  if (job.admin_rerun && job.admin_rerun.status === 'completed' && job.admin_rerun.files && job.admin_rerun.files.length > 0) {
    const files = job.admin_rerun.files
    const target = job.mode === 'exact_product'
      ? (files.find(f => f.kind === 'docx' || f.kind === 'word' || f.filename?.endsWith('.docx')) || files[0])
      : (files.find(f => f.kind === 'excel' || f.kind === 'xlsx' || f.kind === 'suppliers' || f.filename?.endsWith('.xlsx')) || files[0])
    if (target) {
      const isXlsx = target.filename?.endsWith('.xlsx') || target.kind === 'excel' || target.kind === 'xlsx'
      const isDocx = target.filename?.endsWith('.docx') || target.kind === 'docx' || target.kind === 'word'
      const ext = isXlsx ? 'Excel' : isDocx ? 'Word' : ''
      return {
        file: target,
        isAdmin: true,
        jobId: job.admin_rerun.id,
        label: `Админ-отчёт${ext ? ` (${ext})` : ''}`,
      }
    }
  }

  // 2. Client result files
  if (job.result_files && job.result_files.length > 0) {
    const files = job.result_files
    const target = job.mode === 'exact_product'
      ? (files.find(f => f.kind === 'docx' || f.kind === 'word' || f.filename?.endsWith('.docx')) || files[0])
      : (files.find(f => f.kind === 'excel' || f.kind === 'xlsx' || f.kind === 'suppliers' || f.filename?.endsWith('.xlsx')) || files[0])
    if (target) {
      const isXlsx = target.filename?.endsWith('.xlsx') || target.kind === 'excel' || target.kind === 'xlsx'
      const isDocx = target.filename?.endsWith('.docx') || target.kind === 'docx' || target.kind === 'word'
      const ext = isXlsx ? 'Excel' : isDocx ? 'Word' : ''
      return {
        file: target,
        isAdmin: false,
        jobId: job.id,
        label: `Отчёт${ext ? ` (${ext})` : ''}`,
      }
    }
  }

  return null
}

const selectionWaitingStatuses = ['awaiting_exact_selection', 'awaiting_position_selection']
const activeExpertStatuses = ['pending', 'running', 'settling', ...selectionWaitingStatuses, 'awaiting_customer_confirmation']

function jobSelection(job?: Pick<Job, 'position_selection' | 'exact_product_selection' | 'multi_item_selection'> | null): ExactSelection | null {
  if (!job) return null
  const ps = job.position_selection
  if (ps && Array.isArray(ps.items) && ps.items.length > 0) {
    return {
      ...ps,
      items: ps.items,
      selected_ids: Array.isArray(ps.selected_ids) ? ps.selected_ids : [],
    }
  }
  const eps = job.exact_product_selection
  if (eps && Array.isArray(eps.items) && eps.items.length > 0) {
    return {
      ...eps,
      items: eps.items,
      selected_ids: Array.isArray(eps.selected_ids) ? eps.selected_ids : [],
    }
  }
  const strategy = job.multi_item_selection
  if (!strategy || !Array.isArray(strategy.items) || strategy.items.length === 0) return null
  const items = strategy.items.map((row, index) => ({
    ...row,
    id: String(row.id || `item-${index}`),
    position_no: row.position_no || index + 1,
    name: row.name || row.name_in_tz || `Позиция ${index + 1}`,
  }))
  return {
    ...strategy,
    items,
    selected_ids: Array.isArray(strategy.selected_ids) ? strategy.selected_ids : [],
    mode: 'supplier_search',
    revision: strategy.revision || '',
    max_positions: items.length,
    price_kopeks: 0,
  }
}

function needsAdminSelection(job: Pick<Job, 'status' | 'confirmation_kind' | 'position_selection' | 'exact_product_selection' | 'multi_item_selection'>) {
  return selectionWaitingStatuses.includes(job.status) ||
    (job.status === 'awaiting_customer_confirmation' && job.confirmation_kind === 'multi_item_strategy') ||
    Boolean(jobSelection(job)?.items?.length && !jobSelection(job)?.confirmed)
}

function expertScope(job: Job) {
  const selection = jobSelection(job)
  const rows = selection?.confirmed ? `Подтверждённые позиции: ${selection.selected_ids?.length || 0}. ` : ''
  const geoScopeLabel = job.geo_scope === 'cis' ? 'РФ и СНГ (ЕАЭС)' : job.geo_scope === 'world' ? 'Весь мир' : 'Только РФ'
  const geography = job.delivery_city
    ? `География: ${job.delivery_city}${job.geo_radius_km ? `, радиус ${job.geo_radius_km} км` : ''} (${geoScopeLabel}). `
    : (job.geo_scope && job.geo_scope !== 'ru' ? `География: ${geoScopeLabel}. ` : '')
  const strategy = ['supplier_search', 'analysis_and_suppliers'].includes(job.mode)
    ? `Стратегия: ${job.multi_item_mode === 'per_item' ? 'попозиционный поиск' : 'сбалансированный поиск'}. ` : ''
  return `${humanMode(job.mode)}. ${rows}${strategy}${geography}`
}

function JobsView({
  jobs,
  clients = [],
  selectedClientId = '',
  onClearSelectedClient,
  onChange,
  loading = false,
}: {
  jobs: Job[]
  clients?: Client[]
  selectedClientId?: string
  onClearSelectedClient?: () => void
  onChange: (jobId?: string) => Promise<void>
  loading?: boolean
}) {
  const [nowTs, setNowTs] = useState(() => Date.now())
  const [showServerModal, setShowServerModal] = useState(false)
  const [supplementModalJob, setSupplementModalJob] = useState<Job | null>(null)
  const [activeFilesDropdownJobId, setActiveFilesDropdownJobId] = useState<string | null>(null)

  useEffect(() => {
    if (!activeFilesDropdownJobId) return
    const handleClickOutside = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.files-dropdown-wrapper')) {
        setActiveFilesDropdownJobId(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [activeFilesDropdownJobId])

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
        if (parsed === 10 || parsed === 12 || parsed === 25 || parsed === 50 || parsed === 100) return parsed
      }
    } catch {}
    return 25
  })

  function handleJobPageSizeChange(nextSize: number) {
    setPageSize(nextSize)
    setPage(1)
    try {
      localStorage.setItem('tenderlex_admin_jobs_page_size', String(nextSize))
    } catch {}
  }

  const [showInternalJobs, setShowInternalJobs] = useState(false)
  const [clientFilter, setClientFilter] = useState(selectedClientId || '')
  const [statusFilter, setStatusFilter] = useState('')
  const [modeFilter, setModeFilter] = useState('')
  const [policyFilter, setPolicyFilter] = useState('')
  const [query, setQuery] = useState('')
  const normalizedQuery = query.trim().toLowerCase()

  useEffect(() => {
    if (selectedClientId) {
      setClientFilter(selectedClientId)
      setPage(1)
    }
  }, [selectedClientId])

  const recentClientOptions = useMemo(() => {
    const jobCounts: Record<string, number> = {}
    for (const j of jobs) {
      if (j.client_id) {
        jobCounts[j.client_id] = (jobCounts[j.client_id] || 0) + 1
      }
    }
    return clients.slice(0, 20).map(c => {
      const email = c.web_users?.[0]?.email || ''
      const count = jobCounts[c.id] || c.jobs_count || 0
      const numPrefix = c.client_number ? `#${c.client_number} ` : ''
      const contactPart = email ? ` (${email})` : (c.username ? ` (@${c.username})` : '')
      const countPart = count > 0 ? ` · ${count} ${count === 1 ? 'зад.' : 'зад.'}` : ' · 0 зад.'
      return {
        id: c.id,
        label: `${numPrefix}${c.name || 'Без имени'}${contactPart}${countPart}`,
      }
    })
  }, [clients, jobs])

  const otherClientOptions = useMemo(() => {
    if (clients.length <= 20) return []
    const jobCounts: Record<string, number> = {}
    for (const j of jobs) {
      if (j.client_id) {
        jobCounts[j.client_id] = (jobCounts[j.client_id] || 0) + 1
      }
    }
    return clients.slice(20).map(c => {
      const email = c.web_users?.[0]?.email || ''
      const count = jobCounts[c.id] || c.jobs_count || 0
      const numPrefix = c.client_number ? `#${c.client_number} ` : ''
      const contactPart = email ? ` (${email})` : (c.username ? ` (@${c.username})` : '')
      const countPart = count > 0 ? ` · ${count} ${count === 1 ? 'зад.' : 'зад.'}` : ' · 0 зад.'
      return {
        id: c.id,
        label: `${numPrefix}${c.name || 'Без имени'}${contactPart}${countPart}`,
      }
    })
  }, [clients, jobs])

  const filteredJobs = useMemo(() => jobs
    .filter(job => showInternalJobs || (!job.is_internal && (!job.is_admin_rerun || !job.parent_job_id)))
    .filter(job => !clientFilter || job.client_id === clientFilter)
    .filter(job => !statusFilter || job.status === statusFilter)
    .filter(job => !modeFilter || job.mode === modeFilter)
    .filter(job => !policyFilter || (job.supplier_search_policy || 'normal') === policyFilter)
    .filter(job => {
      if (!normalizedQuery) return true
      const inputNames = (job.input_files || []).map(f => f.original_filename)
      const resultNames = (job.result_files || []).map(f => f.filename)
      const rerunNumber = job.admin_rerun?.job_number
      return [
        job.job_number ? `#${job.job_number}` : '',
        job.job_number ? String(job.job_number) : '',
        job.client_number ? `#${job.client_number}` : '',
        job.client_number ? String(job.client_number) : '',
        rerunNumber ? `#${rerunNumber}` : '',
        rerunNumber ? String(rerunNumber) : '',
        job.admin_rerun?.id,
        job.human_title,
        job.title,
        job.client_name,
        job.client_email,
        job.client_username,
        job.created_by_label,
        job.telegram_id,
        job.created_by_telegram_id,
        job.message,
        ...inputNames,
        ...resultNames,
      ].some(value => String(value || '').toLowerCase().includes(normalizedQuery))
    }), [jobs, showInternalJobs, clientFilter, statusFilter, modeFilter, policyFilter, normalizedQuery])
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
    { id: 'awaiting_exact_selection', label: 'Ожидает выбора товаров' },
    { id: 'awaiting_position_selection', label: 'Ожидает выбора позиций' },
    { id: 'confirmation_expired', label: 'Срок выбора истёк' },
    { id: 'failed', label: 'Ошибка' },
    { id: 'cancelled', label: 'Отменено' },
  ], [])
  const modeOptions = useMemo(() => [
    { id: 'supplier_search', label: 'Поиск поставщиков' },
    { id: 'exact_product', label: 'Подбор товара и аналогов' },
    { id: 'price_monitoring', label: 'Мониторинг цен' },
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
  const hasActiveFilters = Boolean(statusFilter || modeFilter || policyFilter || clientFilter || query.trim())

  function resetFilters() {
    setStatusFilter('')
    setModeFilter('')
    setPolicyFilter('')
    setClientFilter('')
    setQuery('')
    setPage(1)
    if (onClearSelectedClient) {
      onClearSelectedClient()
    }
  }

  useEffect(() => {
    setPage(1)
  }, [showInternalJobs, clientFilter, statusFilter, modeFilter, policyFilter, normalizedQuery])

  async function adminRerun(job: Job) {
    if (needsAdminSelection(job) || (job.admin_rerun && activeExpertStatuses.includes(job.admin_rerun.status))) return
    if (!window.confirm(
      `Создать новый экспертный поиск по задаче #${job.job_number || job.id}?\n\n${expertScope(job)}\nСостав позиций и условия сохраняются. Баланс клиента не списывается. Результат не отправляется автоматически — используйте «Дополнить отчёт».`
    )) return
    try {
      await api(`/api/jobs/${job.id}/admin-rerun`, { method: 'POST' })
      await onChange(job.id)
    } catch (err: any) {
      alert(err.message || 'Ошибка перезапуска задачи')
    }
  }
  async function resolveJob(job: Job) {
    await api(`/api/jobs/${job.id}/resolve`, { method: 'POST' })
    await onChange(job.id)
  }
  async function cancelJob(job: Job) {
    if (!window.confirm('Отменить задачу?')) return
    await api(`/api/jobs/${job.id}/cancel`, { method: 'POST' })
    await onChange(job.id)
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
            <strong>
              {loading && filteredJobs.length === 0
                ? 'Задачи: загрузка...'
                : `Задачи: ${shownFrom}-${shownTo} из ${filteredJobs.length}`}
            </strong>
            {loading && (
              <span className="inline-note" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <Loader2 size={12} className="animate-spin" />
                <span>обновление...</span>
              </span>
            )}
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
          <select
            value={clientFilter}
            onChange={e => {
              setClientFilter(e.target.value)
              if (e.target.value) setQuery('')
              setPage(1)
              if (!e.target.value && onClearSelectedClient) {
                onClearSelectedClient()
              }
            }}
            style={{
              maxWidth: 320,
              fontSize: 13,
              fontWeight: clientFilter ? 600 : 400,
              borderColor: clientFilter ? '#0f766e' : undefined,
              background: clientFilter ? '#f0fdf4' : undefined,
            }}
            title="Выбрать клиента (последние 20)"
          >
            <option value="">Выбрать клиента (последние 20)...</option>
            <optgroup label="Последние 20 клиентов">
              {recentClientOptions.map(opt => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </optgroup>
            {otherClientOptions.length > 0 && (
              <optgroup label="Остальные клиенты">
                {otherClientOptions.map(opt => (
                  <option key={opt.id} value={opt.id}>
                    {opt.label}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
          {clientFilter && (
            <button
              type="button"
              className="ghost small-text"
              style={{ color: '#ef4444', fontSize: 12, padding: '4px 8px' }}
              onClick={() => {
                setClientFilter('')
                setPage(1)
                if (onClearSelectedClient) onClearSelectedClient()
              }}
              title="Сбросить фильтр по клиенту"
            >
              ✕ Сброс
            </button>
          )}
          <input
            className="toolbar-search"
            autoComplete="off"
            placeholder="Поиск по названию задачи, файлу или #номеру..."
            value={query}
            onChange={e => {
              setQuery(e.target.value)
              if (e.target.value) {
                setClientFilter('')
                if (onClearSelectedClient) onClearSelectedClient()
              }
              setPage(1)
            }}
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
            <option value={10}>По 10</option>
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
          const selection = jobSelection(job)
          const awaitingSelection = selectionWaitingStatuses.includes(job.status) || (job.status === 'awaiting_customer_confirmation' && job.confirmation_kind === 'multi_item_strategy')
          const expiredSelection = job.status === 'confirmation_expired' && Boolean(selection && !selection.confirmed)
          const reruns = job.admin_reruns?.length ? job.admin_reruns : job.admin_rerun ? [job.admin_rerun] : []
          const expertActive = reruns.some(rerun => activeExpertStatuses.includes(rerun.status))
          const isFinished = job.status === 'completed' || job.status === 'partial' || job.status === 'failed' || job.status === 'cancelled'
          const showProgress = !isFinished || (job.status === 'running' || job.status === 'pending')
          const hasResult = job.has_result || (job.result_files && job.result_files.length > 0)
          const inputFiles = job.input_files || []
          const inputSources = job.sources || []
          const hasInput = inputFiles.length > 0 || inputSources.length > 0 || job.file_count > 0
          const primaryReport = getPrimaryReport(job)
          const isLegacyArchive = !primaryReport && hasResult
          const completedAdminReruns = (job.admin_reruns && job.admin_reruns.length > 0
            ? job.admin_reruns.filter(r => r.status === 'completed' && r.files && r.files.length > 0)
            : (job.admin_rerun && job.admin_rerun.status === 'completed' && job.admin_rerun.files ? [job.admin_rerun] : [])
          )
          const allAdminFilesCount = completedAdminReruns.reduce((acc, r) => acc + (r.files ? r.files.length : 0), 0)
          const clientResultFiles = job.result_files || []
          const totalFileCount = inputFiles.length + inputSources.length + clientResultFiles.length + allAdminFilesCount
          const isFilesDropdownOpen = activeFilesDropdownJobId === job.id

          return (
          <article
            className={`job-card compact mode-${job.mode} status-${job.status} ${job.is_internal ? 'service' : ''}`}
            key={job.id}
            style={{ zIndex: isFilesDropdownOpen ? 50 : undefined, position: 'relative' }}
          >
            <div className="job-card-top">
              <div className="job-title-group">
                <div className="job-title-row">
                  {job.job_number ? (
                    <span className="job-number-badge" title={`Номер задачи #${job.job_number}`}>
                      #{job.job_number}
                    </span>
                  ) : null}
                  <h2 title={job.title}>{job.human_title || humanMode(job.mode)}</h2>
                  <StatusBadge status={job.status} />
                </div>
                <p className="job-subline">
                  {formatDate(job.created_at)}
                  {formatJobDuration(job, nowTs) ? ` · ${formatJobDuration(job, nowTs)}` : ''}
                  {' · '}
                  <span
                    className="job-client-link"
                    title="Показать только задачи этого клиента"
                    onClick={() => {
                      if (job.client_id) {
                        setClientFilter(job.client_id)
                        setPage(1)
                      }
                    }}
                    style={{ cursor: job.client_id ? 'pointer' : 'default' }}
                  >
                    {job.client_number ? `#${job.client_number} ` : ''}
                    {job.client_name || 'клиент не указан'}
                    {job.client_email ? ` (${job.client_email})` : ''}
                  </span>
                  {' · '}
                  {job.created_by_label?.startsWith('API:') ? (
                    <span style={{ background: '#ede9fe', color: '#6d28d9', border: '1px solid #c4b5fd', borderRadius: 4, padding: '1px 6px', fontSize: '0.72rem', fontWeight: 600 }}>
                      🔑 {job.created_by_label}
                    </span>
                  ) : (
                    job.created_by_label || (
                      String(job.created_by_telegram_id || '').startsWith('web:')
                        ? (job.client_email ? `Веб: ${job.client_email}` : 'Веб-кабинет')
                        : (job.created_by_telegram_id || job.telegram_id || 'автор не указан')
                    )
                  )}
                </p>
              </div>
              <div className="job-card-top-right">
                {job.status !== 'completed' && <JobTimeline job={job} hasInput={hasInput} />}
                {(job.status === 'running' || job.status === 'pending') && (
                  <button className="icon-button small danger" onClick={() => void cancelJob(job)} title="Отменить"><XCircle size={13} /></button>
                )}
                {job.status === 'failed' && (
                  <button className="icon-button small" style={{ color: '#059669', borderColor: '#a7f3d0', background: '#ecfdf5' }} onClick={() => void resolveJob(job)} title="Отметить решённым (устранено)"><CheckCircle2 size={13} /></button>
                )}
              </div>
            </div>

            <div className="job-card-meta-line">
              <div className="job-meta-bar">
                {(job.is_admin_rerun || (job.title && job.title.startsWith('[Админ]')) || Boolean(job.parent_job_id)) && (
                  <span
                    className="meta-tag admin-task"
                    title="Задача создана администратором для экспертной доработки"
                  >
                    <Crown size={11} />
                    Админ-доработка
                  </span>
                )}
                <span className={`job-module-badge mode-${job.mode}`}>
                  {job.mode_label || humanMode(job.mode)}
                </span>

                <div className="job-meta-details">
                  {supplierPolicyLabel && (
                    <span className={`meta-item policy ${job.supplier_search_policy || 'normal'}`}>
                      {supplierPolicyLabel}
                    </span>
                  )}

                  {supplierRunLabel && (
                    <>
                      <span className="meta-sep">·</span>
                      <span className="meta-item">{supplierRunLabel}</span>
                    </>
                  )}

                  {(job.mode === 'supplier_search' || job.mode === 'analysis_and_suppliers') && (
                    <>
                      <span className="meta-sep">·</span>
                      <span
                        className="meta-item"
                        title={job.multi_item_mode === 'per_item' ? 'Глубокий независимый поиск под каждую позицию спецификации' : 'Единая квота распределяется по всем позициям со вкладками в Excel'}
                      >
                        {awaitingSelection ? 'Стратегия ещё не подтверждена' : job.multi_item_mode === 'per_item' ? '🔍 Попозиционный' : '⚖️ Сбалансированный'}
                      </span>
                    </>
                  )}

                  {fallbackStatusLabel && (
                    <>
                      <span className="meta-sep">·</span>
                      <span className="meta-item fallback">{fallbackStatusLabel}</span>
                    </>
                  )}

                  <span className="meta-sep">·</span>
                  <span className="meta-item count">
                    {awaitingSelection ? 'Ожидает выбора позиций'
                      : expiredSelection ? 'Срок выбора истёк · поиск не запущен'
                      : !hasResult && ['pending', 'running', 'settling'].includes(job.status) ? 'Поиск ещё выполняется'
                      : job.mode === 'procurement_report'
                      ? 'Анализ ТЗ'
                      : job.mode === 'exact_product'
                      ? `${job.verified_count || 0} тов.`
                      : job.mode === 'price_monitoring'
                      ? `${job.verified_count || 0} поз.`
                      : `${supplierCountLabel(job)} пост.`}
                  </span>

                  {selection && Boolean(selection.items?.length) && (
                    <span className="meta-item">
                      Распознано: {selection.items?.length || 0} · Подтверждено: {selection.confirmed ? (selection.selected_ids?.length || 0) : 0}
                    </span>
                  )}
                  {awaitingSelection && job.confirmation_expires_at && <span className="meta-item">Подтвердить до: {formatDate(job.confirmation_expires_at)}</span>}
                  {job.delivery_city && <span className="meta-item">📍 {job.delivery_city}{job.geo_radius_km ? ` · ${job.geo_radius_km} км` : ''}</span>}
                  {job.geo_scope && job.geo_scope !== 'ru' && (
                    <span className="meta-item" style={{ color: '#4f46e5', fontWeight: 600 }}>
                      {job.geo_scope === 'cis' ? 'СНГ' : 'Весь мир'}
                    </span>
                  )}

                  {Boolean(job.yandex_cost_rub && job.yandex_cost_rub > 0) ? (
                    <>
                      <span className="meta-sep">·</span>
                      <span className="meta-item cost" title={`Запросов Yandex Search API: ${job.yandex_requests_count || 0}`}>
                        🔍 {job.yandex_requests_count ? `${job.yandex_requests_count} запр. · ` : ''}{(job.yandex_cost_rub || 0).toFixed(2)} ₽
                      </span>
                    </>
                  ) : job.mode === 'exact_product' ? (
                    <>
                      <span className="meta-sep">·</span>
                      <span className="meta-item cost-free" title="Подбор товара выполнен без платных запросов к Яндекс Поиску">
                        ⚡ 0.00 ₽
                      </span>
                    </>
                  ) : job.mode === 'procurement_report' ? (
                    <>
                      <span className="meta-sep">·</span>
                      <span className="meta-item cost-free" title="Анализ документации выполняется нейросетью без платных запросов к Яндекс Поиску">
                        ⚡ 0.00 ₽ (ИИ)
                      </span>
                    </>
                  ) : null}

                  {job.has_admin_supplement && (
                    <>
                      <span className="meta-sep">·</span>
                      <span className="meta-tag supplement" title={job.admin_comment || 'Дополнено администратором'}>
                        ✨ Дополнено{job.admin_supplement_name ? `: ${job.admin_supplement_name}` : ''}
                      </span>
                    </>
                  )}

                  {job.admin_rerun && job.admin_rerun.status === 'completed' && (
                    <>
                      <span className="meta-sep">·</span>
                      <span className="meta-tag admin-result" title="Есть экспертный результат администратора">
                        <Crown size={11} /> Админ: {job.admin_rerun.verified_count || 0} пост.{job.admin_rerun.yandex_cost_rub ? ` (${job.admin_rerun.yandex_cost_rub.toFixed(2)} ₽)` : ''}
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div className="job-actions-strip">
                {/* 1. Primary Download Button */}
                {primaryReport ? (
                  <button
                    type="button"
                    className={`btn-primary-download ${primaryReport.isAdmin ? 'is-admin' : ''}`}
                    onClick={() => void download({ id: primaryReport.jobId } as Job, primaryReport.file)}
                    title={`Скачать итоговый отчёт: ${primaryReport.file.filename}`}
                  >
                    <Download size={13} />
                    <span>{primaryReport.label}</span>
                  </button>
                ) : isLegacyArchive ? (
                  <button
                    type="button"
                    className="btn-primary-download"
                    onClick={() => void download(job)}
                    title="Скачать архив результатов"
                  >
                    <Download size={13} />
                    <span>Скачать архив</span>
                  </button>
                ) : null}

                {/* 2. Files Dropdown (when multiple files exist) */}
                {totalFileCount > 1 ? (
                  <div className="files-dropdown-wrapper">
                    <button
                      type="button"
                      className={`btn-files-dropdown ${isFilesDropdownOpen ? 'active' : ''}`}
                      onClick={e => {
                        e.stopPropagation()
                        setActiveFilesDropdownJobId(isFilesDropdownOpen ? null : job.id)
                      }}
                      title="Все файлы задачи: исходное ТЗ, отчеты, админ-версии"
                    >
                      <FolderArchive size={13} />
                      <span>Файлы ({totalFileCount})</span>
                      <ChevronDown size={11} className={`dropdown-chevron ${isFilesDropdownOpen ? 'open' : ''}`} />
                    </button>

                    {isFilesDropdownOpen && (
                      <div className="files-dropdown-popover" onClick={e => e.stopPropagation()}>
                        <div className="dropdown-popover-header">
                          <span>Файлы задачи #{job.job_number || job.id.slice(0, 8)}</span>
                          <button
                            type="button"
                            className="dropdown-close-btn"
                            onClick={() => setActiveFilesDropdownJobId(null)}
                            title="Закрыть"
                          >
                            <X size={12} />
                          </button>
                        </div>

                        <div className="dropdown-popover-body">
                          {/* Admin Reruns (all expert results) */}
                          {completedAdminReruns.map((rerun, rIdx) => {
                            const files = rerun.files || []
                            if (files.length === 0) return null
                            const isLatest = rIdx === 0 && completedAdminReruns.length > 1
                            const dateLabel = rerun.completed_at || rerun.created_at
                            return (
                              <div key={`rerun-${rerun.id}`} className="dropdown-popover-section admin-section">
                                <div className="dropdown-section-title">
                                  <div className="dropdown-title-left">
                                    <Crown size={12} />
                                    <span>
                                      Экспертный итог {rerun.job_number ? `#${rerun.job_number} ` : ''}
                                      ({rerun.verified_count || 0} {job.mode === 'exact_product' ? 'тов.' : 'пост.'})
                                      {isLatest ? ' · Свежий' : ''}
                                    </span>
                                  </div>
                                  {dateLabel && (
                                    <span className="dropdown-section-time">{formatDate(dateLabel)}</span>
                                  )}
                                </div>
                                {files.map(file => (
                                  <button
                                    key={`admin-${rerun.id}-${file.kind}`}
                                    type="button"
                                    className="dropdown-file-item admin-item"
                                    onClick={() => {
                                      void download({ id: rerun.id } as Job, file)
                                      setActiveFilesDropdownJobId(null)
                                    }}
                                    title={file.filename}
                                  >
                                    <div className="dropdown-file-info">
                                      <span className="file-kind-badge admin">
                                        {file.filename?.endsWith('.docx') || file.kind === 'docx' ? 'DOCX' : 'XLSX'}
                                      </span>
                                      <span className="file-name">{file.label} (Админ)</span>
                                    </div>
                                    <div className="dropdown-file-meta">
                                      {(file.created_at || dateLabel) && (
                                        <span className="dropdown-file-time">
                                          {formatDate(file.created_at || dateLabel)}
                                        </span>
                                      )}
                                      <Download size={12} className="download-icon" />
                                    </div>
                                  </button>
                                ))}
                              </div>
                            )
                          })}

                          {/* Client Result Files */}
                          {clientResultFiles.length > 0 && (
                            <div className="dropdown-popover-section">
                              <div className="dropdown-section-title">
                                <div className="dropdown-title-left">
                                  <FileCheck size={12} />
                                  <span>{completedAdminReruns.length > 0 ? 'Исходные отчеты клиента' : 'Итоговые отчеты'}</span>
                                </div>
                                {(job.completed_at || job.created_at) && (
                                  <span className="dropdown-section-time">{formatDate(job.completed_at || job.created_at)}</span>
                                )}
                              </div>
                              {clientResultFiles.map(file => (
                                <button
                                  key={`client-${file.kind}`}
                                  type="button"
                                  className="dropdown-file-item"
                                  onClick={() => {
                                    void download(job, file)
                                    setActiveFilesDropdownJobId(null)
                                  }}
                                  title={file.filename}
                                >
                                  <div className="dropdown-file-info">
                                    <span className="file-kind-badge">
                                      {file.filename?.endsWith('.docx') || file.kind === 'docx' ? 'DOCX' : 'XLSX'}
                                    </span>
                                    <span className="file-name">{file.label}</span>
                                  </div>
                                  <div className="dropdown-file-meta">
                                    {(file.created_at || job.completed_at || job.created_at) && (
                                      <span className="dropdown-file-time">
                                        {formatDate(file.created_at || job.completed_at || job.created_at)}
                                      </span>
                                    )}
                                    <Download size={12} className="download-icon" />
                                  </div>
                                </button>
                              ))}
                            </div>
                          )}

                          {/* Input Files */}
                          {inputFiles.length > 0 && (
                            <div className="dropdown-popover-section">
                              <div className="dropdown-section-title">
                                <div className="dropdown-title-left">
                                  <FileText size={12} />
                                  <span>Входные материалы клиента</span>
                                </div>
                                {job.created_at && (
                                  <span className="dropdown-section-time">{formatDate(job.created_at)}</span>
                                )}
                              </div>
                              {inputFiles.map(file => (
                                <button
                                  key={`in-${file.id}`}
                                  type="button"
                                  className="dropdown-file-item input-item"
                                  onClick={() => {
                                    void downloadInputFile(job, file)
                                    setActiveFilesDropdownJobId(null)
                                  }}
                                  title={`Скачать входной файл: ${file.original_filename}`}
                                >
                                  <div className="dropdown-file-info">
                                    <span className="file-kind-badge input">ТЗ</span>
                                    <span className="file-name" title={file.original_filename}>{file.original_filename}</span>
                                  </div>
                                  <div className="dropdown-file-meta">
                                    {(file.created_at || job.created_at) && (
                                      <span className="dropdown-file-time">
                                        {formatDate(file.created_at || job.created_at)}
                                      </span>
                                    )}
                                    <Download size={12} className="download-icon" />
                                  </div>
                                </button>
                              ))}
                            </div>
                          )}

                          {/* Web Sources */}
                          {inputSources.length > 0 && (
                            <div className="dropdown-popover-section">
                              <div className="dropdown-section-title">
                                <Globe size={12} />
                                <span>Ссылки</span>
                              </div>
                              {inputSources.map(source => (
                                <div key={`src-${source.id}`} className="dropdown-source-item" title={source.value}>
                                  <Globe size={11} className="source-icon" />
                                  <span className="source-label">{source.label || 'Ссылка'}:</span>
                                  <a href={source.value} target="_blank" rel="noreferrer" className="source-link" onClick={e => e.stopPropagation()}>
                                    {source.value}
                                  </a>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ) : totalFileCount === 1 && !primaryReport && inputFiles.length === 1 ? (
                  <button
                    type="button"
                    className="btn-files-dropdown"
                    onClick={() => void downloadInputFile(job, inputFiles[0])}
                    title={`Входной файл клиента: ${inputFiles[0].original_filename}`}
                  >
                    <FileText size={12} />
                    <span className="pill-filename" title={inputFiles[0].original_filename}>{inputFiles[0].original_filename}</span>
                  </button>
                ) : null}

                {/* Supplement button */}
                <button
                  type="button"
                  className={`icon-button small ${job.has_admin_supplement ? 'accent-active' : ''}`}
                  style={job.has_admin_supplement ? { color: '#0d9488', borderColor: '#99f6e4', background: '#f0fdfa' } : undefined}
                  onClick={() => setSupplementModalJob(job)}
                  title={job.has_admin_supplement ? 'Редактировать дополнение эксперта' : 'Дополнить отчет / отправить клиенту'}
                >
                  <MessageSquarePlus size={13} />
                </button>

                {/* Admin Rerun button */}
                <button
                  type="button"
                  className={`icon-button small ${job.admin_rerun?.status === 'completed' ? 'has-rerun' : ''}`}
                  style={job.admin_rerun?.status === 'completed' ? { color: '#047857', borderColor: '#a7f3d0', background: '#ecfdf5' } : undefined}
                  disabled={needsAdminSelection(job) || expertActive}
                  onClick={() => void adminRerun(job)}
                  title={expertActive ? 'Экспертная задача уже активна; продолжите её в карточке'
                    : needsAdminSelection(job) ? 'Сначала подтвердите позиции в карточке задачи'
                    : 'Новый экспертный поиск без списания с клиента'}
                >
                  {job.admin_rerun?.status === 'pending' || job.admin_rerun?.status === 'running' ? (
                    <Loader2 size={13} className="spin" />
                  ) : job.admin_rerun?.status === 'completed' ? (
                    <RotateCw size={13} />
                  ) : (
                    <Play size={13} />
                  )}
                </button>
              </div>
            </div>

            {(awaitingSelection || expiredSelection) && selection && Boolean(selection.items?.length) && !expertActive && (
              <AdminExactSelection key={`${job.id}:${selection.revision}`} jobId={job.id} selection={selection}
                mode={job.mode} multiItemMode={job.multi_item_mode} reissue={expiredSelection}
                geography={job.delivery_city ? `${job.delivery_city}${job.geo_radius_km ? `, радиус ${job.geo_radius_km} км` : ''}` : ''} onChange={() => onChange(job.id)} />
            )}
            {job.admin_rerun && (selectionWaitingStatuses.includes(job.admin_rerun.status) ||
              (job.admin_rerun.status === 'awaiting_customer_confirmation' && job.admin_rerun.confirmation_kind === 'multi_item_strategy')) &&
              Boolean(jobSelection(job.admin_rerun)?.items?.length) && (
              <AdminExactSelection key={`${job.admin_rerun.id}:${jobSelection(job.admin_rerun)!.revision}`} jobId={job.admin_rerun.id}
                selection={jobSelection(job.admin_rerun)!} mode={job.admin_rerun.mode || job.mode} multiItemMode={job.admin_rerun.multi_item_mode}
                internal onChange={() => onChange(job.id)} />
            )}

            {reruns.length > 0 && <details style={{ marginTop: 8, fontSize: 12 }}>
              <summary>Экспертные поиски: {reruns.length} · последний: {humanStatus(reruns[0].status)}</summary>
              {reruns.slice(0, 5).map(rerun => <div key={rerun.id} style={{ marginTop: 4 }}>
                #{rerun.job_number || rerun.id} · {humanStatus(rerun.status)} · {rerun.message || 'Нет описания'}
              </div>)}
              {reruns.length > 5 && <div>Ещё: {reruns.length - 5}. Готовые файлы доступны в списке отчётов.</div>}
            </details>}

            {job.admin_rerun && (job.admin_rerun.status === 'pending' || job.admin_rerun.status === 'running') && (
              <div className="job-progress-compact" style={{ marginTop: 6, padding: '6px 10px', background: '#f0fdf4', borderRadius: 6, border: '1px solid #bbf7d0' }}>
                <div style={{ fontSize: 12, color: '#166534', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <Loader2 size={13} className="spin" />
                  <span>
                    Идет экспертный админ-перерасчет {job.admin_rerun.job_number ? `(#${job.admin_rerun.job_number}) ` : ''}
                    ({job.admin_rerun.progress}%): {job.admin_rerun.message || humanStatus(job.admin_rerun.status)}
                  </span>
                </div>
                <Progress value={job.admin_rerun.progress} note={job.admin_rerun.message || humanStatus(job.admin_rerun.status)} />
              </div>
            )}

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
        {loading && !visibleJobs.length ? (
          <div className="empty inline-empty" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '40px 0' }}>
            <Loader2 size={18} className="animate-spin" style={{ color: '#0f766e' }} />
            <span>Загрузка задач...</span>
          </div>
        ) : !visibleJobs.length ? (
          <div className="empty inline-empty">Нет пользовательских задач для показа.</div>
        ) : null}
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
          onSuccess={() => onChange(supplementModalJob.id)}
        />
      )}
    </section>
  )
}

function AdminExactSelection({ jobId, selection, mode, multiItemMode, reissue = false, internal = false, geography = '', onChange }: {
  jobId: string; selection: ExactSelection; mode?: string; multiItemMode?: string; reissue?: boolean; internal?: boolean; geography?: string; onChange: () => Promise<void>
}) {
  const [selected, setSelected] = useState<string[]>(selection.selected_ids || [])
  const [strategy, setStrategy] = useState(multiItemMode || 'balanced')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const maximum = selection.max_positions || (selection.pricing_mode === 'per_position' ? (selection.items?.length || 100) : 5)
  const monitoring = mode === 'price_monitoring' || selection.pricing_mode === 'per_found_position'
  const supplier = ['supplier_search', 'analysis_and_suppliers'].includes(mode || selection.mode || '')
  const balanced = supplier && strategy === 'balanced'
  const effectiveIds = selected
  const noCharge = reissue || internal
  const billing = noCharge ? 'Экспертная задача без списания с клиента. Результат не отправляется автоматически.'
    : supplier ? 'Продолжение исходной задачи по тарифу клиента. Попозиционный режим может потребовать дополнительный резерв за позиции.'
    : monitoring ? `За найденную позицию: ${formatMoney(selection.price_kopeks)}. Максимальный резерв: ${formatMoney(selection.price_kopeks * selected.length)}.`
    : selection.pricing_mode === 'per_position' ? `За выбранную позицию: ${formatMoney(selection.price_kopeks)}. Итого: ${formatMoney(selection.price_kopeks * selected.length)}.`
    : `Стоимость исходной задачи: ${formatMoney(selection.price_kopeks)} за выбор до ${maximum} товаров.`
  async function confirm() {
    if (!effectiveIds.length || effectiveIds.length > maximum || busy) return
    if (!window.confirm(`${reissue ? 'Создать новую экспертную задачу' : 'Подтвердить продолжение задачи'}?\n\nПозиций: ${effectiveIds.length}. ${supplier ? `Стратегия: ${balanced ? 'сбалансированная' : 'попозиционная'}. ` : ''}${geography ? `География: ${geography}. ` : ''}\n${billing}\n\n${selection.items.filter(row => effectiveIds.includes(row.id)).map(row => `${row.position_no}. ${row.name}`).join('\n')}`)) return
    setBusy(true)
    setError('')
    try {
      if (supplier && !reissue) {
        const query = new URLSearchParams({ multi_item_mode: strategy, revision: selection.revision })
        selected.forEach(id => query.append('selected_item_ids', id))
        await api(`/api/jobs/${jobId}/choose-strategy?${query}`, { method: 'POST' })
      } else {
        await api(`/api/jobs/${jobId}/${reissue ? 'admin-rerun' : monitoring ? 'position-selection' : 'exact-selection'}${supplier ? `?multi_item_mode=${strategy}` : ''}`, {
          method: 'POST', body: JSON.stringify({ revision: selection.revision, selected_item_ids: effectiveIds }),
        })
      }
      await onChange()
    } catch (err) {
      setError(formatError(err))
    } finally {
      setBusy(false)
    }
  }
  return <section aria-label={supplier ? 'Выбор позиций и стратегии поставщиков' : monitoring ? 'Выбор позиций для мониторинга' : 'Выбор товаров для подбора'} style={{ border: '1px solid #a7c9bd', borderRadius: 10, padding: 14, marginTop: 12, minWidth: 0 }}>
    <strong>{reissue ? 'Срок подтверждения истёк. Выберите позиции для новой экспертной задачи' : supplier ? 'Подтвердите позиции и стратегию поиска поставщиков' : monitoring ? 'Выберите позиции для мониторинга цен' : selection.pricing_mode === 'per_position' ? 'Выберите позиции для подбора модели и аналогов' : `Выберите до ${maximum} товаров для подбора`}</strong>
    <p>Выбрано: {effectiveIds.length} из {maximum}. {billing}</p>
    {supplier && <label style={{ display: 'block', marginBottom: 10 }}>Стратегия поиска поставщиков{' '}
      <select aria-label="Стратегия поиска поставщиков" value={strategy} disabled={busy} onChange={event => setStrategy(event.target.value)}>
        <option value="balanced">Сбалансированный — единая квота по отмеченным позициям</option>
        <option value="per_item">Попозиционный — независимый поиск по отмеченным позициям</option>
      </select>
    </label>}
    <div style={{ maxHeight: 280, overflowY: 'auto', display: 'grid', gap: 10, marginBottom: 12 }}>
      {selection.items.map(row => <label key={row.id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', overflowWrap: 'anywhere' }}>
        <input type="checkbox" checked={effectiveIds.includes(row.id)} disabled={busy || (!selected.includes(row.id) && selected.length >= maximum)}
          onChange={() => setSelected(current => current.includes(row.id) ? current.filter(id => id !== row.id) : [...current, row.id])} />
        <span>{row.position_no}. {row.name}</span>
      </label>)}
    </div>
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={busy || !effectiveIds.length || effectiveIds.length > maximum} onClick={() => void confirm()}>
      {busy ? 'Подтверждаем…' : reissue ? 'Создать экспертный поиск с выбранными позициями' : supplier ? 'Подтвердить позиции и стратегию' : monitoring ? 'Подтвердить позиции для мониторинга' : 'Подтвердить выбор товаров'}
    </button>
  </section>
}

function cleanItemNameForComment(rawTitle: string): string {
  let text = (rawTitle || '').trim()
  text = text.replace(/\[\s*админ\s*\]/gi, '').trim()
  text = text.replace(/^(?:точный\s+товар\s+и\s+аналоги|подбор\s+товар(?:а|ов)(?:\s+и\s+аналогов)?|анализ\s+(?:закупки|документации|\+\s*поиск)|тз|техническое\s+задание)\s*[-:—–]\s*/gi, '').trim()
  text = text.replace(/\.(?:docx?|xlsx?|pdf|zip|rar|7z|rtf|txt)$/gi, '').trim()
  text = text.replace(/^[:\s"'«»]+|[:\s"'«»]+$/g, '').trim()
  return text || 'позиции'
}

function generateDefaultComment(job: Job): string {
  const rawTitle = job.human_title || job.title || ''
  const item = cleanItemNameForComment(rawTitle)
  if (job.mode === 'exact_product') {
    return `Эксперты TenderLex провели расширенный подбор товаров и аналогов позиции «${item}».`
  }
  if (job.mode === 'supplier_search' || job.mode === 'analysis_and_suppliers') {
    return `Эксперты TenderLex провели дополнительный поиск поставщиков и производителей по позиции «${item}».`
  }
  if (job.mode === 'procurement_report') {
    return `Эксперты TenderLex подготовили дополнительный анализ документации по закупке «${item}».`
  }
  return `Эксперты TenderLex провели расширенную доработку по позиции «${item}».`
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
      <div className="server-modal-card supplement-modal" style={{ maxWidth: 640 }} onClick={e => e.stopPropagation()}>
        <div className="server-modal-header">
          <h3>ДОПОЛНИТЬ ОТЧЁТ: КОММЕНТАРИЙ И ФАЙЛЫ</h3>
          <button className="server-modal-close" onClick={onClose} title="Закрыть">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="supplement-modal-form">
          <div className="supplement-modal-scroll-body">
            <p style={{ fontSize: 12, margin: 0 }}>Прикрепите комментарий и готовые файлы к задаче клиента. Новый поиск не запускается. Доставка в Telegram зависит от отметки ниже.</p>
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, padding: '8px 10px', fontSize: 12 }}>
              <div style={{ fontWeight: 600, color: '#1e293b', marginBottom: 2 }}>
                {job.job_number ? `[#${job.job_number}] ` : ''}{job.human_title || job.title}
              </div>
              <div style={{ color: '#64748b', fontSize: 11 }}>
                Клиент: {job.client_name || 'Не указан'} {job.created_by_telegram_id ? `· TG ID: ${job.created_by_telegram_id}` : ''}
              </div>
              {job.admin_supplement_name && (
                <div style={{ marginTop: 4, fontSize: 11, color: '#0f766e', fontWeight: 600 }}>
                  ✨ Текущий прикрепленный отчет: {job.admin_supplement_name}
                </div>
              )}
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                Источник файлов отчета:
              </label>

              {(candidates.length > 0 || loadingCandidates) && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600, color: '#1e293b', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="source_mode"
                      checked={sourceMode === 'job_file'}
                      onChange={() => setSourceMode('job_file')}
                    />
                    <span>Использовать файлы из задачи (исходные или после Play / перезапуска)</span>
                  </label>

                  {sourceMode === 'job_file' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginLeft: 20, padding: '8px 10px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                      {loadingCandidates ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#64748b', padding: '8px 0' }}>
                          <Loader2 size={14} className="spin" />
                          <span>Поиск файлов задачи и экспертных перезапусков...</span>
                        </div>
                      ) : candidates.length === 0 ? (
                        <div style={{ fontSize: 12, color: '#64748b' }}>Нет готовых файлов в задаче. Загрузите файл с компьютера.</div>
                      ) : (
                        <>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                            <span style={{ fontSize: 11, color: '#64748b' }}>Выберите файлы для отправки клиенту ({selectedJobFileKinds.length}/{candidates.length}):</span>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button
                                type="button"
                                className="ghost small-text"
                                style={{ fontSize: 10.5, padding: '1px 6px', height: 'auto', color: '#0d9488' }}
                                onClick={selectAllJobFiles}
                              >
                                Выбрать все
                              </button>
                              <button
                                type="button"
                                className="ghost small-text"
                                style={{ fontSize: 10.5, padding: '1px 6px', height: 'auto', color: '#64748b' }}
                                onClick={unselectAllJobFiles}
                              >
                                Снять все
                              </button>
                            </div>
                          </div>

                          <div className="supplement-candidates-list">
                            {candidates.map(cand => {
                              const isChecked = selectedJobFileKinds.includes(cand.composite_id)
                              return (
                                <div
                                  key={cand.composite_id}
                                  className={`supplement-candidate-card ${isChecked ? 'is-checked' : ''}`}
                                >
                                  <label className="candidate-label">
                                    <input
                                      type="checkbox"
                                      checked={isChecked}
                                      onChange={() => toggleJobFileKind(cand.composite_id)}
                                    />
                                    <FileText size={15} color={isChecked ? '#0d9488' : '#64748b'} style={{ flexShrink: 0 }} />
                                    <div className="candidate-details">
                                      <div className="candidate-header-row">
                                        <strong className="candidate-name">{cand.label}</strong>
                                        {cand.is_admin_rerun && (
                                          <span className="candidate-badge">
                                            👑 Доработка
                                          </span>
                                        )}
                                        {cand.created_at && (
                                          <span className="candidate-time">
                                            · {formatDate(cand.created_at)}
                                          </span>
                                        )}
                                      </div>
                                      <div className="candidate-file-name" title={cand.filename}>{cand.filename}</div>
                                    </div>
                                  </label>

                                  <button
                                    type="button"
                                    className="candidate-preview-btn"
                                    onClick={(e) => {
                                      e.preventDefault()
                                      e.stopPropagation()
                                      window.open(`/api/jobs/${cand.job_id}/download/${cand.kind}`, '_blank')
                                    }}
                                    title="Скачать и открыть файл для проверки"
                                  >
                                    <Download size={11} />
                                    <span>Открыть</span>
                                  </button>
                                </div>
                              )
                            })}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600, color: '#1e293b', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="source_mode"
                    checked={sourceMode === 'upload'}
                    onChange={() => setSourceMode('upload')}
                  />
                  <span>Загрузить отредактированные файлы с компьютера</span>
                </label>

                {sourceMode === 'upload' && (
                  <div style={{ marginLeft: 20, marginTop: 2 }}>
                    <input
                      type="file"
                      multiple
                      accept=".xlsx,.xls,.docx,.doc,.pdf,.zip"
                      onChange={e => {
                        if (e.target.files) {
                          setFiles(Array.from(e.target.files))
                        }
                      }}
                      style={{ fontSize: 12, width: '100%', padding: '6px', border: '1px solid #cbd5e1', borderRadius: 6, background: '#fff' }}
                    />
                    {files.length > 0 && (
                      <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {files.map((f, i) => (
                          <span key={i} style={{ fontSize: 11, background: '#f0fdfa', border: '1px solid #99f6e4', color: '#0f766e', padding: '1px 6px', borderRadius: 4 }}>
                            📎 {f.name}
                          </span>
                        ))}
                      </div>
                    )}
                    <small style={{ display: 'block', color: '#64748b', marginTop: 2, fontSize: 10.5 }}>
                      Можно выбрать несколько файлов (XLSX, DOCX, ZIP, PDF).
                    </small>
                  </div>
                )}
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <label style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>
                  Комментарий клиенту:
                </label>
                <button
                  type="button"
                  className="ghost small-text"
                  style={{ fontSize: 10.5, padding: '1px 6px', height: 'auto', color: '#0d9488', border: '1px solid #99f6e4', background: '#f0fdfa', borderRadius: 4, cursor: 'pointer' }}
                  onClick={() => setComment(generateDefaultComment(job))}
                >
                  Восстановить автотекст
                </button>
              </div>
              <textarea
                rows={3}
                value={comment}
                onChange={e => setComment(e.target.value)}
                placeholder="Укажите комментарий эксперта..."
                style={{ width: '100%', padding: '8px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 6, resize: 'vertical' }}
              />
              <small style={{ display: 'block', color: '#64748b', marginTop: 2, fontSize: 10.5 }}>
                Комментарий отобразится в личном кабинете на карточке задачи и в Telegram-боте.
              </small>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#334155', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={notifyTelegram}
                onChange={e => setNotifyTelegram(e.target.checked)}
              />
              <span>Отправить уведомление и файл в Telegram бот клиенту</span>
            </label>

            {error && (
              <div style={{ color: '#dc2626', background: '#fef2f2', border: '1px solid #fecaca', padding: '6px 10px', borderRadius: 6, fontSize: 12 }}>
                {error}
              </div>
            )}
          </div>

          <div className="supplement-modal-footer">
            <button type="button" className="ghost" onClick={onClose} disabled={loading} style={{ fontSize: 12, padding: '6px 14px' }}>
              Отмена
            </button>
            <button type="submit" className="primary" disabled={loading} style={{ background: '#0d9488', borderColor: '#0d9488', fontSize: 12, padding: '6px 16px' }}>
              {loading ? <Loader2 size={13} className="spin" /> : <Send size={13} />}
              <span>{loading ? 'Сохранение...' : notifyTelegram ? 'Сохранить и отправить в Telegram' : 'Сохранить дополнение в кабинете'}</span>
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

function BillingView({
  tariffs,
  settings,
  onChange,
}: {
  tariffs: TariffPackage[]
  settings: SettingsPayload | null
  onChange: () => Promise<void>
}) {
  const [showAddForm, setShowAddForm] = useState(false)
  const [showAllServices, setShowAllServices] = useState(false)
  const [geoEnabled, setGeoEnabled] = useState(settings?.geo_radius_search_enabled_global ?? true)
  const [geoSurcharge, setGeoSurcharge] = useState(settings?.geo_radius_surcharge_pct ?? 30)
  const [geoSaving, setGeoSaving] = useState(false)
  const [geoSaved, setGeoSaved] = useState(false)

  useEffect(() => {
    if (settings) {
      setGeoEnabled(settings.geo_radius_search_enabled_global ?? true)
      setGeoSurcharge(settings.geo_radius_surcharge_pct ?? 30)
    }
  }, [settings])

  async function saveGeoSettings() {
    setGeoSaving(true)
    try {
      await api('/api/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          geo_radius_search_enabled_global: geoEnabled,
          geo_radius_surcharge_pct: Number(geoSurcharge),
        }),
      })
      await onChange()
      setGeoSaved(true)
      setTimeout(() => setGeoSaved(false), 2500)
    } finally {
      setGeoSaving(false)
    }
  }

  const [newTariff, setNewTariff] = useState({
    kind: 'deposit',
    name: '',
    units: 10,
    price_kopeks: 0,
    bonus_kopeks: 0,
    badge: '',
    sort_order: 100,
    is_active: true,
  })
  const [billingError, setBillingError] = useState('')

  async function createTariff() {
    setBillingError('')
    try {
      await api('/api/tariffs', { method: 'POST', body: JSON.stringify(newTariff) })
      setNewTariff({ kind: 'deposit', name: '', units: 10, price_kopeks: 0, bonus_kopeks: 0, badge: '', sort_order: 100, is_active: true })
      setShowAddForm(false)
      await onChange()
    } catch (err) {
      setBillingError(formatError(err))
    }
  }

  async function patchTariff(item: TariffPackage, patch: Partial<TariffPackage>) {
    setBillingError('')
    try {
      await api(`/api/tariffs/${item.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
      await onChange()
    } catch (err) {
      setBillingError(formatError(err))
    }
  }

  async function deleteTariff(item: TariffPackage) {
    if (!window.confirm(`Удалить тариф "${item.name}"?`)) return
    setBillingError('')
    try {
      await api(`/api/tariffs/${item.id}`, { method: 'DELETE' })
      await onChange()
    } catch (err) {
      setBillingError(formatError(err))
    }
  }

  const depositTariffs = tariffs.filter(item => item.kind === 'deposit')
  const baseServiceOrder = ['supplier_search', 'exact_product', 'procurement_report', 'supplier_search_extra']
  const allServiceTariffs = tariffs
    .filter(item => item.kind !== 'deposit')
    .sort((a, b) => {
      const orderA = baseServiceOrder.indexOf(a.kind)
      const orderB = baseServiceOrder.indexOf(b.kind)
      if (orderA !== orderB) return orderA - orderB
      return (a.sort_order ?? 0) - (b.sort_order ?? 0)
    })

  // Filter to core 1-unit services unless expanded
  const displayedServiceTariffs = showAllServices
    ? allServiceTariffs
    : allServiceTariffs.filter(t => t.units === 1)

  const basePriceExample = 99
  const surchargeExample = Math.round(basePriceExample * (1 + (geoSurcharge || 0) / 100))

  return (
    <section className="stack" style={{ gap: 14 }}>
      {/* 1. Header with Title & Add button */}
      <div className="tariff-header-bar">
        <div>
          <h2>Тарифы и ценообразование</h2>
          <span className="sync-note">
            Синхронизировано: Сайт (tenderlex.ru) + Web-кабинет + Telegram-бот
          </span>
        </div>
        <button
          className={showAddForm ? 'button-secondary' : 'button-primary'}
          onClick={() => setShowAddForm(!showAddForm)}
        >
          {showAddForm ? <X size={14} /> : <Plus size={14} />}
          {showAddForm ? 'Скрыть форму' : 'Добавить пакет'}
        </button>
      </div>

      {billingError && (
        <div className="alert error" style={{ margin: 0, padding: '8px 12px', fontSize: 13, borderRadius: 8 }}>
          {billingError}
        </div>
      )}

      {/* 2. Sleek 1-line logistics filter strip (replaces bulky banner) */}
      <div className="tariff-subnav-strip">
        <div className="tariff-subnav-left">
          <span className="tariff-subnav-title">
            <MapPin size={15} />
            Поиск в радиусе города:
          </span>
          <label className="tariff-inline-switch">
            <input
              type="checkbox"
              checked={geoEnabled}
              onChange={e => setGeoEnabled(e.target.checked)}
            />
            <span>Доступен всем</span>
          </label>
          <div className="tariff-inline-rate">
            <span>Доплата:</span>
            <input
              type="number"
              min={0}
              max={500}
              step={5}
              value={geoSurcharge}
              onChange={e => setGeoSurcharge(Number(e.target.value))}
            />
            <span>%</span>
            <span className="tariff-rate-example">
              (пример: 99 ₽ → <strong>{surchargeExample} ₽</strong>)
            </span>
          </div>
        </div>
        <button
          className="tariff-subnav-save-btn"
          onClick={() => void saveGeoSettings()}
          disabled={geoSaving}
        >
          {geoSaved ? <CheckCircle2 size={13} /> : <Save size={13} />}
          {geoSaved ? 'Сохранено' : geoSaving ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>

      {/* 3. Collapsible Add Form */}
      {showAddForm && (
        <div className="tariff-collapsible-panel">
          <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: '#0f172a' }}>
            Новый тарифный пакет
          </h3>
          <div className="tariff-form-grid">
            <label className="field">
              <span>Тип</span>
              <select value={newTariff.kind} onChange={e => setNewTariff({ ...newTariff, kind: e.target.value })}>
                <option value="deposit">Пакет пополнения баланса (с бонусом)</option>
                <option value="supplier_search">Поиск поставщиков (базовый)</option>
                <option value="exact_product">Подбор товара и аналогов (базовый)</option>
                <option value="procurement_report">Анализ документации (базовый)</option>
                <option value="supplier_search_extra">Добор поставщиков (базовый)</option>
              </select>
            </label>
            <TextField label="Название" value={newTariff.name} onChange={value => setNewTariff({ ...newTariff, name: value })} />
            <NumberField label="Оплата, ₽" value={kopeksToRubles(newTariff.price_kopeks)} onChange={value => setNewTariff({ ...newTariff, price_kopeks: rublesToKopeks(value) })} />
            {newTariff.kind === 'deposit' ? (
              <>
                <NumberField label="Бонус, ₽" value={kopeksToRubles(newTariff.bonus_kopeks)} onChange={value => setNewTariff({ ...newTariff, bonus_kopeks: rublesToKopeks(value) })} />
                <TextField label="Бейдж" value={newTariff.badge} onChange={value => setNewTariff({ ...newTariff, badge: value })} />
              </>
            ) : null}
            <NumberField label="Генераций / Задач" value={newTariff.units} onChange={value => setNewTariff({ ...newTariff, units: value })} />
            <label className="switch-row">
              <input type="checkbox" checked={newTariff.is_active} onChange={e => setNewTariff({ ...newTariff, is_active: e.target.checked })} />
              Показывать клиентам
            </label>
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
            <button onClick={() => void createTariff()} disabled={!newTariff.name.trim()}>
              <Plus size={14} /> Сохранить тариф
            </button>
            <button className="button-secondary" onClick={() => setShowAddForm(false)}>
              Отмена
            </button>
          </div>
        </div>
      )}

      {/* 4. Deposit Packages Table: Noise-Free with Effective Cost per Task */}
      <div className="tariff-panel-card">
        <div className="tariff-panel-header">
          <div>
            <h2>Пакеты пополнения единого баланса</h2>
            <span className="sync-note">Пополнение баланса со скидкой / бонусом и пересчетом стоимости 1 задачи</span>
          </div>
          <span style={{ fontSize: 12, color: '#64748b' }}>Пакетов: {depositTariffs.length}</span>
        </div>

        <div className="tariff-clean-table-container">
          <table className="tariff-clean-table">
            <thead>
              <tr>
                <th style={{ width: '20%' }}>Пакет / Название</th>
                <th style={{ width: '11%', textAlign: 'right' }}>Оплата, ₽</th>
                <th style={{ width: '11%', textAlign: 'right' }}>Бонус, ₽</th>
                <th style={{ width: '16%' }}>Итого на баланс</th>
                <th style={{ width: '14%' }}>Цена 1 задачи</th>
                <th style={{ width: '8%', textAlign: 'center' }}>Задач</th>
                <th style={{ width: '10%', textAlign: 'center' }}>Бейдж</th>
                <th style={{ width: '6%', textAlign: 'center' }}>Активен</th>
                <th style={{ width: '4%', textAlign: 'center' }}></th>
              </tr>
            </thead>
            <tbody>
              {depositTariffs.map(item => {
                const payRub = kopeksToRubles(item.price_kopeks)
                const bonusRub = kopeksToRubles(item.bonus_kopeks || 0)
                const totalRub = payRub + bonusRub
                const costPerTask = item.units > 0 ? payRub / item.units : 0
                // Discount relative to 100 ₽ base rate
                const discountPct = costPerTask > 0 && costPerTask < 100
                  ? Math.round(((100 - costPerTask) / 100) * 100)
                  : 0

                return (
                  <tr key={item.id} className={item.is_active ? '' : 'muted-row'}>
                    <td>
                      <input
                        className="t-input text"
                        style={{ fontWeight: 600 }}
                        defaultValue={item.name}
                        placeholder="Название"
                        onBlur={e => {
                          const val = e.currentTarget.value.trim()
                          if (val && val !== item.name) void patchTariff(item, { name: val })
                        }}
                      />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <input
                        className="t-input number"
                        type="number"
                        min={0}
                        step={100}
                        defaultValue={payRub}
                        onBlur={e => {
                          const val = Number(e.currentTarget.value)
                          if (!isNaN(val) && val !== payRub) void patchTariff(item, { price_kopeks: rublesToKopeks(val) })
                        }}
                      />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <input
                        className="t-input number"
                        type="number"
                        min={0}
                        step={100}
                        defaultValue={bonusRub}
                        onBlur={e => {
                          const val = Number(e.currentTarget.value)
                          if (!isNaN(val) && val !== bonusRub) void patchTariff(item, { bonus_kopeks: rublesToKopeks(val) })
                        }}
                      />
                    </td>
                    <td>
                      <div className="balance-credit-wrap">
                        <span className="balance-credit-total">{totalRub.toLocaleString('ru-RU')} ₽</span>
                        {bonusRub > 0 && (
                          <span className="balance-credit-bonus">(+{bonusRub.toLocaleString('ru-RU')} ₽)</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="task-cost-wrap">
                        <span className="task-cost-price">
                          {costPerTask > 0 ? `${costPerTask.toFixed(costPerTask % 1 === 0 ? 0 : 1)} ₽` : '—'}
                        </span>
                        {discountPct > 0 ? (
                          <span className="task-cost-badge">-{discountPct}%</span>
                        ) : costPerTask === 100 ? (
                          <span className="task-cost-badge base">база</span>
                        ) : null}
                      </div>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <input
                        className="t-input number-center"
                        type="number"
                        min={1}
                        defaultValue={item.units}
                        onBlur={e => {
                          const val = Number(e.currentTarget.value)
                          if (!isNaN(val) && val > 0 && val !== item.units) void patchTariff(item, { units: val })
                        }}
                      />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <input
                        className="t-input badge-text"
                        defaultValue={item.badge || ''}
                        placeholder="—"
                        onBlur={e => {
                          const val = e.currentTarget.value.trim()
                          if (val !== (item.badge || '')) void patchTariff(item, { badge: val })
                        }}
                      />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={item.is_active}
                        title="Показывать клиентам"
                        onChange={e => void patchTariff(item, { is_active: e.target.checked })}
                      />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        className="icon-button small"
                        title="Удалить пакет"
                        style={{ color: '#ef4444' }}
                        onClick={() => void deleteTariff(item)}
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Service Base Prices Table: Clean & Compact with Segmented Toggle */}
      <div className="tariff-panel-card">
        <div className="tariff-panel-header">
          <div>
            <h2>Базовые цены разовых услуг</h2>
            <span className="sync-note">
              Порядок: (1) Поиск поставщиков → (2) Подбор товара и аналогов → (3) Анализ документации
            </span>
          </div>
          <div className="tariff-segmented-control">
            <button
              className={`tariff-seg-btn ${!showAllServices ? 'active' : ''}`}
              onClick={() => setShowAllServices(false)}
            >
              4 основные услуги (1 задача)
            </button>
            <button
              className={`tariff-seg-btn ${showAllServices ? 'active' : ''}`}
              onClick={() => setShowAllServices(true)}
            >
              Все пакетные варианты ({allServiceTariffs.length})
            </button>
          </div>
        </div>

        <div className="tariff-clean-table-container">
          <table className="tariff-clean-table">
            <thead>
              <tr>
                <th style={{ width: '25%' }}>Модуль / Сценарий</th>
                <th style={{ width: '28%' }}>Тариф / Описание</th>
                <th style={{ width: '8%', textAlign: 'center' }}>Задач</th>
                <th style={{ width: '12%', textAlign: 'right' }}>Разовая цена, ₽</th>
                <th style={{ width: '15%' }}>Цена 1 задачи</th>
                <th style={{ width: '7%', textAlign: 'center' }}>Активен</th>
                <th style={{ width: '5%', textAlign: 'center' }}></th>
              </tr>
            </thead>
            <tbody>
              {displayedServiceTariffs.map(item => {
                const getModuleInfo = (kind: string) => {
                  switch (kind) {
                    case 'supplier_search':
                      return { label: '1. Поиск поставщиков', cls: 'supplier_search' }
                    case 'exact_product':
                      return { label: '2. Подбор товара и аналогов', cls: 'exact_product' }
                    case 'procurement_report':
                      return { label: '3. Анализ документации', cls: 'procurement_report' }
                    case 'supplier_search_extra':
                      return { label: '4. Добор поставщиков', cls: 'supplier_search_extra' }
                    default:
                      return { label: kind, cls: 'supplier_search_extra' }
                  }
                }
                const mod = getModuleInfo(item.kind)
                const payRub = kopeksToRubles(item.price_kopeks)
                const costPerTask = item.units > 0 ? payRub / item.units : 0
                const baseUnitRate = item.kind === 'supplier_search_extra' ? 49 : 99
                const bulkDiscountPct = item.units > 1 && costPerTask < baseUnitRate
                  ? Math.round(((baseUnitRate - costPerTask) / baseUnitRate) * 100)
                  : 0

                return (
                  <tr key={item.id} className={item.is_active ? '' : 'muted-row'}>
                    <td>
                      <span className={`module-pill-tag ${mod.cls}`}>{mod.label}</span>
                    </td>
                    <td>
                      <input
                        className="t-input text"
                        defaultValue={item.name}
                        onBlur={e => {
                          const val = e.currentTarget.value.trim()
                          if (val && val !== item.name) void patchTariff(item, { name: val })
                        }}
                      />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <input
                        className="t-input number-center"
                        type="number"
                        min={1}
                        defaultValue={item.units}
                        onBlur={e => {
                          const val = Number(e.currentTarget.value)
                          if (!isNaN(val) && val > 0 && val !== item.units) void patchTariff(item, { units: val })
                        }}
                      />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <input
                        className="t-input number"
                        type="number"
                        min={0}
                        step={10}
                        style={{ fontWeight: 600 }}
                        defaultValue={payRub}
                        onBlur={e => {
                          const val = Number(e.currentTarget.value)
                          if (!isNaN(val) && val !== payRub) void patchTariff(item, { price_kopeks: rublesToKopeks(val) })
                        }}
                      />
                    </td>
                    <td>
                      <div className="task-cost-wrap">
                        <span className="task-cost-price">
                          {costPerTask > 0 ? `${costPerTask.toFixed(costPerTask % 1 === 0 ? 0 : 1)} ₽` : '—'}
                        </span>
                        {bulkDiscountPct > 0 ? (
                          <span className="task-cost-badge">-{bulkDiscountPct}%</span>
                        ) : (
                          <span className="task-cost-badge base">база</span>
                        )}
                      </div>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={item.is_active}
                        title="Показывать клиентам"
                        onChange={e => void patchTariff(item, { is_active: e.target.checked })}
                      />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        className="icon-button small"
                        title="Удалить тариф"
                        style={{ color: '#ef4444' }}
                        onClick={() => void deleteTariff(item)}
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
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
        <label className="switch-row"><input type="checkbox" checked={draft.trial_enabled} onChange={e => setDraft({ ...draft, trial_enabled: e.target.checked })} />Включить бесплатный период для новых пользователей (Telegram и Web)</label>
        <NumberField label="Стартовый баланс триала, ₽" value={draft.trial_balance_rub ?? 495} onChange={value => setDraft({ ...draft, trial_balance_rub: value })} />
        <p className="field-help">Сумма в рублях, которая начисляется на баланс новым пользователям при регистрации. Пользователь может свободно расходовать этот баланс на любые сценарии: поиск поставщиков, подбор товара и аналогов или анализ документации по действующим тарифам.</p>
        <label className="switch-row"><input type="checkbox" checked={draft.onboarding_reminders_enabled} onChange={e => setDraft({ ...draft, onboarding_reminders_enabled: e.target.checked, reengagement_reminders_enabled: e.target.checked, onboarding_reminders_rollout_at: e.target.checked && !draft.onboarding_reminders_rollout_at ? new Date().toISOString() : draft.onboarding_reminders_rollout_at })} />Автонапоминания (цепочка подсказок + возврат остывших)</label>
        <p className="field-help">Единая автоматическая цепочка: подсказка через 1–5 дней без запусков → последнее напоминание через 14+ дней молчания → подсказка про возможности после 1–3 задач → предложение тарифов после исчерпания баланса → возврат остывших (одно сообщение тем, кто делал задачи и пропал на 10+ дней). Каждое сообщение строго один раз, с кнопкой отписки. Только рабочие часы 9:00–20:00 МСК.</p>
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
              <p>
                {minpromRegistry?.sqlite_ready ? 'Единая база ГИСП подключена из сервиса EmailAgent.' : 'Централизованный индекс ГИСП формируется в EmailAgent.'}
                {minpromRegistry?.updated_at_label && ` База от ${minpromRegistry.updated_at_label}.`}
              </p>
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
          <p className="field-help" style={{ marginTop: 10, marginBottom: 0 }}>
            Единый реестр ГИСП управляется и обновляется в сервисе EmailAgent. В TenderLex используется общая актуальная база.
          </p>
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
        </details>
      </div>
      <div className="savebar"><button onClick={() => void save()}><CheckCircle2 size={16} />Сохранить настройки</button></div>
    </section>
  )
}

const AiView = memo(function AiView({
  settings,
  onChange,
  onSettingsUpdated,
}: {
  settings: SettingsPayload
  onChange?: () => Promise<void>
  onSettingsUpdated?: (settings: SettingsPayload) => void
}) {
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
  const [savingSection, setSavingSection] = useState<string | null>(null)

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
    setSavingSection(section)
    try {
      const res = await api<{ success: boolean; settings: SettingsPayload }>('/api/settings', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
      setSaveStatus(current => ({ ...current, [section]: 'Сохранено' }))
      if (res?.settings && onSettingsUpdated) {
        onSettingsUpdated(res.settings)
      } else if (onChange) {
        await onChange()
      }
    } catch (err) {
      setSaveStatus(current => ({ ...current, [section]: `Ошибка: ${formatError(err)}` }))
    } finally {
      setSavingSection(null)
    }
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
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 12000)
    try {
      const result = await api<{ response: string; provider_name?: string; model?: string }>('/api/ai/test', {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({ provider, model }),
      })
      clearTimeout(timeoutId)
      setTestResults(current => ({
        ...current,
        [slot]: {
          status: 'success',
          message: result.response || 'Модель ответила без текста.',
          providerName: result.provider_name || providerDisplayName(provider),
          model: result.model || model,
        },
      }))
    } catch (err: unknown) {
      clearTimeout(timeoutId)
      const isTimeout =
        err instanceof Error && (err.name === 'AbortError' || err.message.toLowerCase().includes('aborted'))
      setTestResults(current => ({
        ...current,
        [slot]: {
          status: 'error',
          message: isTimeout ? 'Превышен лимит времени проверки модели (12 сек)' : formatError(err),
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
            <button onClick={() => void saveGlobalModelSettings()} disabled={savingSection !== null}>
              {savingSection === 'global' ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              {savingSection === 'global' ? 'Сохранение...' : 'Сохранить анализ'}
            </button>
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
            <button onClick={() => void saveSupplierModelSettings()} disabled={savingSection !== null}>
              {savingSection === 'supplier' ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              {savingSection === 'supplier' ? 'Сохранение...' : 'Сохранить поиск'}
            </button>
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
            <button onClick={() => void saveFunctionModelSettings()} disabled={savingSection !== null}>
              {savingSection === 'functions' ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              {savingSection === 'functions' ? 'Сохранение...' : 'Сохранить маршруты'}
            </button>
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
            <button onClick={() => void saveProviderSettings()} disabled={savingSection !== null}>
              {savingSection === 'providers' ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              {savingSection === 'providers' ? 'Сохранение...' : 'Сохранить провайдеров'}
            </button>
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
            <button onClick={() => void saveModelListSettings()} disabled={savingSection !== null}>
              {savingSection === 'models' ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              {savingSection === 'models' ? 'Сохранение...' : 'Сохранить модели'}
            </button>
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
