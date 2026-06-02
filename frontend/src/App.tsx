import { useEffect, useMemo, useState } from 'react'
import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  Download,
  FileText,
  KeyRound,
  Loader2,
  LogIn,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  XCircle,
} from 'lucide-react'

type View = 'dashboard' | 'clients' | 'jobs' | 'settings' | 'ai'

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
  access_until: string
  allowed_supplier_search: boolean
  allowed_procurement_report: boolean
  monthly_job_limit: number
  monthly_file_limit: number
  notes: string
}

type Job = {
  id: string
  client_name: string
  telegram_id: string
  mode: string
  status: string
  progress: number
  message: string
  title: string
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
  prompt_settings_json: string
  report_settings_json: string
  document_settings_json: string
  bot_messages_json: string
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

export function App() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authenticated, setAuthenticated] = useState(false)
  const [view, setView] = useState<View>('dashboard')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
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
      const [dashboardData, clientsData, jobsData, settingsData] = await Promise.all([
        api<Dashboard>('/api/dashboard'),
        api<Client[]>('/api/clients'),
        api<Job[]>('/api/jobs'),
        api<SettingsPayload>('/api/settings'),
      ])
      setDashboard(dashboardData)
      setClients(clientsData)
      setJobs(jobsData)
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
    { id: 'settings' as const, label: 'Настройки', icon: SlidersHorizontal },
    { id: 'ai' as const, label: 'AI', icon: BrainCircuit },
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
            <div className="brand-name">AI Poisk</div>
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
            <h1>{nav.find(item => item.id === view)?.label}</h1>
            <p>Ручные доступы, задачи Telegram-бота и гибкая конфигурация без правки кода.</p>
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
        {isReady && view === 'dashboard' && <DashboardView dashboard={dashboard} settings={settings} />}
        {isReady && view === 'clients' && <ClientsView clients={clients} onChange={loadAll} />}
        {isReady && view === 'jobs' && <JobsView jobs={jobs} onChange={loadAll} />}
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

function DashboardView({ dashboard, settings }: { dashboard: Dashboard | null; settings: SettingsPayload | null }) {
  const stats = [
    { label: 'Клиентов', value: dashboard?.clients ?? 0, note: `${dashboard?.active_clients ?? 0} активных`, icon: Users },
    { label: 'Задач', value: dashboard?.jobs ?? 0, note: `${dashboard?.running_jobs ?? 0} в работе`, icon: FileText },
    { label: 'Готово', value: dashboard?.completed_jobs ?? 0, note: `${dashboard?.failed_jobs ?? 0} ошибок`, icon: CheckCircle2 },
    { label: 'Поставщиков', value: dashboard?.suppliers ?? 0, note: 'verified rows', icon: Search },
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
      <div className="wide-panel">
        <h2>Рабочие правила</h2>
        <div className="rule-list">
          <div><Bot size={17} />Telegram-бот принимает файлы только от включённых клиентов.</div>
          <div><Search size={17} />Поставщик попадает в XLSX только после evidence gate.</div>
          <div><Settings size={17} />Тарифов в коде нет: доступы и лимиты задаются вручную.</div>
          <div><KeyRound size={17} />AI-провайдеры настраиваются через OpenAI-compatible endpoint.</div>
        </div>
      </div>
      <div className="wide-panel">
        <h2>Текущая конфигурация</h2>
        <div className="settings-summary">
          <span>Домен: {settings?.public_base_url || 'не задан'}</span>
          <span>Цель поставщиков: {settings?.default_supplier_target || 15}</span>
          <span>Логистика: {settings?.logistics_enabled ? 'включена' : 'отключена'}</span>
          <span>Partial XLSX: {settings?.allow_partial_supplier_reports ? 'разрешён' : 'запрещён'}</span>
        </div>
      </div>
    </section>
  )
}

function ClientsView({ clients, onChange }: { clients: Client[]; onChange: () => Promise<void> }) {
  const [form, setForm] = useState({ telegram_id: '', name: '', username: '', notes: '' })
  async function createClient() {
    await api('/api/clients', { method: 'POST', body: JSON.stringify(form) })
    setForm({ telegram_id: '', name: '', username: '', notes: '' })
    await onChange()
  }
  async function patchClient(client: Client, patch: Partial<Client>) {
    await api(`/api/clients/${client.id}`, { method: 'PATCH', body: JSON.stringify(patch) })
    await onChange()
  }
  function patchString(client: Client, key: keyof Pick<Client, 'access_until' | 'notes'>, value: string) {
    if (value !== client[key]) void patchClient(client, { [key]: value })
  }
  function patchNumber(client: Client, key: keyof Pick<Client, 'monthly_job_limit' | 'monthly_file_limit'>, value: number) {
    if (Number.isFinite(value) && value !== client[key]) void patchClient(client, { [key]: value })
  }
  return (
    <section className="stack">
      <div className="toolbar-panel">
        <input placeholder="Telegram ID" value={form.telegram_id} onChange={e => setForm({ ...form, telegram_id: e.target.value })} />
        <input placeholder="Имя" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
        <input placeholder="Username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} />
        <button onClick={() => void createClient()} disabled={!form.telegram_id.trim()}><Plus size={16} />Добавить</button>
      </div>
      <div className="table-panel">
        <table>
          <thead>
            <tr><th>Клиент</th><th>Telegram</th><th>Доступ</th><th>Функции</th><th>Срок</th><th>Лимиты</th><th>Заметки</th></tr>
          </thead>
          <tbody>
            {clients.map(client => (
              <tr key={client.id}>
                <td><strong>{client.name || 'Без имени'}</strong><small>@{client.username || 'нет'}</small></td>
                <td>{client.telegram_id}</td>
                <td>
                  <div className="access-stack">
                    <StatusBadge status={client.is_active ? 'active' : 'disabled'} />
                    <button className="ghost small-text" onClick={() => void patchClient(client, { is_active: !client.is_active })}>{client.is_active ? 'Отключить' : 'Включить'}</button>
                  </div>
                </td>
                <td>
                  <label><input type="checkbox" checked={client.allowed_supplier_search} onChange={e => void patchClient(client, { allowed_supplier_search: e.target.checked })} /> поставщики</label>
                  <label><input type="checkbox" checked={client.allowed_procurement_report} onChange={e => void patchClient(client, { allowed_procurement_report: e.target.checked })} /> Word</label>
                </td>
                <td>
                  <input
                    className="client-date"
                    type="date"
                    defaultValue={client.access_until || ''}
                    onBlur={e => patchString(client, 'access_until', e.currentTarget.value)}
                  />
                </td>
                <td>
                  <div className="client-limits">
                    <input
                      type="number"
                      min={0}
                      defaultValue={client.monthly_job_limit}
                      aria-label="Лимит задач"
                      onBlur={e => patchNumber(client, 'monthly_job_limit', Number(e.currentTarget.value))}
                    />
                    <input
                      type="number"
                      min={0}
                      defaultValue={client.monthly_file_limit}
                      aria-label="Лимит файлов"
                      onBlur={e => patchNumber(client, 'monthly_file_limit', Number(e.currentTarget.value))}
                    />
                  </div>
                </td>
                <td>
                  <input
                    className="client-note"
                    defaultValue={client.notes || ''}
                    onBlur={e => patchString(client, 'notes', e.currentTarget.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function JobsView({ jobs, onChange }: { jobs: Job[]; onChange: () => Promise<void> }) {
  async function retry(job: Job) {
    await api(`/api/jobs/${job.id}/retry`, { method: 'POST' })
    await onChange()
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
    const fallbackExt = job.mode === 'procurement_report' ? 'docx' : 'xlsx'
    link.href = url
    link.download = encodedName ? decodeURIComponent(encodedName) : plainName || `aipoisk-${job.id.slice(0, 8)}.${fallbackExt}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  return (
    <section className="table-panel">
      <table>
        <thead>
          <tr><th>Задача</th><th>Клиент</th><th>Режим</th><th>Статус</th><th>Прогресс</th><th>Результат</th><th></th></tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <tr key={job.id}>
              <td><strong>{job.title || job.id.slice(0, 8)}</strong><small>{job.id}</small></td>
              <td>{job.client_name || job.telegram_id}</td>
              <td>{job.mode === 'procurement_report' ? 'Word-отчёт' : 'Поставщики'}</td>
              <td><StatusBadge status={job.status} /></td>
              <td><Progress value={job.progress} note={job.message} /></td>
              <td>{job.verified_count}/{job.target_suppliers}</td>
              <td className="row-actions">
                {job.has_result && <button className="icon-button small" onClick={() => void download(job)} title="Скачать"><Download size={15} /></button>}
                <button className="icon-button small" onClick={() => void retry(job)} title="Перезапустить"><Play size={15} /></button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function SettingsView({ settings, onChange }: { settings: SettingsPayload; onChange: () => Promise<void> }) {
  const [draft, setDraft] = useState(settings)
  const [adapterKey, setAdapterKey] = useState('')
  useEffect(() => setDraft(settings), [settings])
  useEffect(() => {
    void api<{ supplier_search_adapter_api_key?: string }>('/api/settings/keys')
      .then(data => setAdapterKey(data.supplier_search_adapter_api_key || ''))
      .catch(() => setAdapterKey(''))
  }, [])
  async function save() {
    await api('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify({
        ...draft,
        supplier_search_adapter_api_key: adapterKey,
      }),
    })
    await onChange()
  }
  return (
    <section className="settings-grid">
      <div className="form-panel">
        <h2>Бот и хранение</h2>
        <TextField label="Публичный URL" value={draft.public_base_url} onChange={value => setDraft({ ...draft, public_base_url: value })} />
        <NumberField label="Хранить файлы, дней" value={draft.storage_retention_days} onChange={value => setDraft({ ...draft, storage_retention_days: value })} />
        <NumberField label="Хранить готовые задачи, дней" value={draft.completed_job_retention_days} onChange={value => setDraft({ ...draft, completed_job_retention_days: value })} />
        <NumberField label="Макс. размер файла, МБ" value={draft.max_upload_mb} onChange={value => setDraft({ ...draft, max_upload_mb: value })} />
        <NumberField label="Макс. файлов в пачке" value={draft.max_files_per_batch} onChange={value => setDraft({ ...draft, max_files_per_batch: value })} />
      </div>
      <div className="form-panel">
        <h2>Отчёты</h2>
        <NumberField label="Цель поставщиков по ТЗ" value={draft.default_supplier_target} onChange={value => setDraft({ ...draft, default_supplier_target: value })} />
        <label className="switch-row"><input type="checkbox" checked={draft.allow_partial_supplier_reports} onChange={e => setDraft({ ...draft, allow_partial_supplier_reports: e.target.checked })} />Разрешить частичные отчёты</label>
        <label className="switch-row"><input type="checkbox" checked={false} disabled onChange={() => undefined} />Логистика/ATI отключена</label>
        <TextArea label="Настройки отчётов JSON" value={draft.report_settings_json} onChange={value => setDraft({ ...draft, report_settings_json: value })} />
        <TextArea label="Настройки документов JSON" value={draft.document_settings_json} onChange={value => setDraft({ ...draft, document_settings_json: value })} />
      </div>
      <div className="form-panel full">
        <h2>Веб-поиск поставщиков</h2>
        <TextField label="Tavily API URL" value={draft.supplier_search_adapter_base_url} onChange={value => setDraft({ ...draft, supplier_search_adapter_base_url: value })} />
        <TextField label="Источник" value={draft.supplier_search_adapter_model} onChange={value => setDraft({ ...draft, supplier_search_adapter_model: value })} />
        <TextField label="Tavily API key" value={adapterKey} onChange={setAdapterKey} />
        <TextArea label="Bot messages JSON" value={draft.bot_messages_json} onChange={value => setDraft({ ...draft, bot_messages_json: value })} />
      </div>
      <div className="savebar"><button onClick={() => void save()}><CheckCircle2 size={16} />Сохранить настройки</button></div>
    </section>
  )
}

function AiView({ settings, onChange }: { settings: SettingsPayload; onChange: () => Promise<void> }) {
  const [providers, setProviders] = useState<CustomProvider[]>(() => parseJson(settings.custom_ai_providers_json, []))
  const [savedModels, setSavedModels] = useState<SavedModel[]>(() => parseJson(settings.saved_models_json, []))
  const [functionModels, setFunctionModels] = useState<Record<string, string>>(() => parseJson(settings.ai_function_models_json, {}))
  const [primaryProvider, setPrimaryProvider] = useState(settings.primary_provider)
  const [primaryModel, setPrimaryModel] = useState(settings.primary_model)
  const [lightProvider, setLightProvider] = useState(settings.light_provider)
  const [lightModel, setLightModel] = useState(settings.light_model)
  const [testResult, setTestResult] = useState('')

  useEffect(() => {
    setProviders(parseJson(settings.custom_ai_providers_json, []))
    setSavedModels(parseJson(settings.saved_models_json, []))
    setFunctionModels(parseJson(settings.ai_function_models_json, {}))
    setPrimaryProvider(settings.primary_provider)
    setPrimaryModel(settings.primary_model)
    setLightProvider(settings.light_provider)
    setLightModel(settings.light_model)
  }, [settings])

  const modelOptions = useMemo(() => savedModels.map(model => `${model.provider}:${model.modelId}`), [savedModels])

  function addProvider() {
    const id = `provider-${providers.length + 1}`
    setProviders([...providers, { id, name: 'CLIProxyAPI', baseUrl: '', apiKey: '', model: '' }])
  }
  function addModel() {
    setSavedModels([...savedModels, { id: crypto.randomUUID(), name: 'Новая модель', provider: providers[0]?.id || '', modelId: '' }])
  }
  async function save() {
    await api('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify({
        primary_provider: primaryProvider,
        primary_model: primaryModel,
        light_provider: lightProvider,
        light_model: lightModel,
        custom_ai_providers_json: stringify(providers),
        saved_models_json: stringify(savedModels),
        ai_function_models_json: stringify(functionModels),
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
      <div className="form-panel">
        <h2>Провайдеры</h2>
        <button onClick={addProvider}><Plus size={16} />Добавить провайдера</button>
        {providers.map((provider, index) => (
          <div className="provider-row" key={provider.id}>
            <input value={provider.id} onChange={e => updateArray(providers, setProviders, index, { id: e.target.value })} />
            <input value={provider.name} onChange={e => updateArray(providers, setProviders, index, { name: e.target.value })} />
            <input value={provider.baseUrl} placeholder="https://.../v1" onChange={e => updateArray(providers, setProviders, index, { baseUrl: e.target.value })} />
            <input type="password" value={provider.apiKey} placeholder="API key" onChange={e => updateArray(providers, setProviders, index, { apiKey: e.target.value })} />
          </div>
        ))}
      </div>
      <div className="form-panel">
        <h2>Сохранённые модели</h2>
        <button onClick={addModel}><Plus size={16} />Добавить модель</button>
        {savedModels.map((model, index) => (
          <div className="model-row" key={model.id}>
            <input value={model.name} onChange={e => updateArray(savedModels, setSavedModels, index, { name: e.target.value })} />
            <select value={model.provider} onChange={e => updateArray(savedModels, setSavedModels, index, { provider: e.target.value })}>
              <option value="">Провайдер</option>
              {providers.map(provider => <option key={provider.id} value={provider.id}>{provider.name || provider.id}</option>)}
            </select>
            <input value={model.modelId} placeholder="model id" onChange={e => updateArray(savedModels, setSavedModels, index, { modelId: e.target.value })} />
          </div>
        ))}
      </div>
      <div className="form-panel">
        <h2>Primary / Light</h2>
        <ModelSelect label="Primary" value={`${primaryProvider}:${primaryModel}`} options={modelOptions} onChange={(provider, model) => { setPrimaryProvider(provider); setPrimaryModel(model) }} />
        <ModelSelect label="Light" value={`${lightProvider}:${lightModel}`} options={modelOptions} onChange={(provider, model) => { setLightProvider(provider); setLightModel(model) }} />
      </div>
      <div className="form-panel">
        <h2>Модели по функциям</h2>
        {aiRoutingKeys.map(key => (
          <ModelSelect
            key={key}
            label={key}
            value={functionModels[key] || ''}
            options={['__primary__', '__light__', ...modelOptions]}
            onChange={(provider, model) => {
              const value = provider.startsWith('__') ? provider : `${provider}:${model}`
              setFunctionModels({ ...functionModels, [key]: value })
            }}
          />
        ))}
      </div>
      <div className="savebar">
        <button onClick={() => void save()}><CheckCircle2 size={16} />Сохранить AI</button>
        <button className="secondary" onClick={() => void testAi()}><BrainCircuit size={16} />Тест</button>
        {testResult && <span>{testResult}</span>}
      </div>
    </section>
  )
}

function updateArray<T>(items: T[], setter: (value: T[]) => void, index: number, patch: Partial<T>) {
  setter(items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
}

function ModelSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (provider: string, model: string) => void }) {
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
        {options.map(option => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  )
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="field"><span>{label}</span><input value={value || ''} onChange={e => onChange(e.target.value)} /></label>
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label className="field"><span>{label}</span><input type="number" value={value || 0} onChange={e => onChange(Number(e.target.value))} /></label>
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="field"><span>{label}</span><textarea value={value || ''} onChange={e => onChange(e.target.value)} /></label>
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status ${status}`}>{status}</span>
}

function Progress({ value, note }: { value: number; note: string }) {
  return (
    <div className="progress-wrap">
      <div className="progress"><span style={{ width: `${value}%` }} /></div>
      <small>{note}</small>
    </div>
  )
}
