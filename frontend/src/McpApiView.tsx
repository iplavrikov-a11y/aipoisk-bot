import { useState, useEffect } from 'react'
import {
  KeyRound,
  Copy,
  Check,
  RefreshCw,
  Plus,
  Shield,
  Zap,
  Terminal,
  Code2,
  Trash2,
  Edit2,
  Power,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  FileText,
  Search,
  ExternalLink,
} from 'lucide-react'

type Client = {
  id: string
  name: string
  username?: string
  telegram_id?: string
}

type ApiKeyItem = {
  id: string
  key_prefix: string
  name: string
  client_id?: string | null
  client_name?: string | null
  is_admin: boolean
  is_active: boolean
  allowed_supplier_search: boolean
  allowed_exact_product: boolean
  allowed_procurement_report: boolean
  quota_supplier_search: number
  quota_exact_product: number
  quota_procurement_report: number
  spent_supplier_search: number
  spent_exact_product: number
  spent_procurement_report: number
  rate_limit_per_minute: number
  notes: string
  created_at: string
  expires_at?: string | null
  last_used_at?: string | null
}

export function McpApiView({ clients }: { clients: Client[] }) {
  const [keys, setKeys] = useState<ApiKeyItem[]>([])
  const [masterKeyInfo, setMasterKeyInfo] = useState<{ item: ApiKeyItem | null; raw_api_key: string | null }>({
    item: null,
    raw_api_key: null,
  })
  const [loading, setLoading] = useState(true)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [activeConfigTab, setActiveConfigTab] = useState<'claude' | 'cursor' | 'codex' | 'python'>('claude')

  // Modals & form state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showRawKeyModal, setShowRawKeyModal] = useState<{ token: string; name: string } | null>(null)
  const [editingKey, setEditingKey] = useState<ApiKeyItem | null>(null)

  const [createForm, setCreateForm] = useState({
    name: '',
    client_id: '',
    allowed_supplier_search: true,
    allowed_exact_product: true,
    allowed_procurement_report: true,
    quota_supplier_search: 20,
    quota_exact_product: 10,
    quota_procurement_report: 10,
    rate_limit_per_minute: 30,
    notes: '',
    expires_days: '',
  })

  // Live tester state
  const [testerTool, setTesterTool] = useState<'supplier_search' | 'exact_product' | 'procurement_report'>('supplier_search')
  const [testerQuery, setTesterQuery] = useState('')
  const [testingRunning, setTestingRunning] = useState(false)
  const [testerResult, setTesterResult] = useState<any>(null)
  const [testerError, setTesterError] = useState<string | null>(null)

  useEffect(() => {
    void loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [keysData, masterData] = await Promise.all([
        fetchApi<ApiKeyItem[]>('/api/admin/api-keys'),
        fetchApi<{ ok: boolean; raw_api_key: string | null; item: ApiKeyItem }>('/api/admin/api-keys/master'),
      ])
      setKeys(keysData || [])
      if (masterData?.item) {
        setMasterKeyInfo({
          item: masterData.item,
          raw_api_key: masterData.raw_api_key,
        })
      }
    } catch (err) {
      console.error('Failed to load MCP API keys:', err)
    } finally {
      setLoading(false)
    }
  }

  async function fetchApi<T>(path: string, options: RequestInit = {}): Promise<T> {
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    })
    if (!res.ok) {
      const errText = await res.text()
      throw new Error(errText || `HTTP ${res.status}`)
    }
    return res.json() as Promise<T>
  }

  function handleCopy(text: string, identifier: string) {
    void navigator.clipboard.writeText(text)
    setCopiedKey(identifier)
    setTimeout(() => setCopiedKey(null), 2500)
  }

  async function handleCreateKey(e: React.FormEvent) {
    e.preventDefault()
    try {
      const payload = {
        name: createForm.name.trim(),
        client_id: createForm.client_id || null,
        is_admin: false,
        allowed_supplier_search: createForm.allowed_supplier_search,
        allowed_exact_product: createForm.allowed_exact_product,
        allowed_procurement_report: createForm.allowed_procurement_report,
        quota_supplier_search: Number(createForm.quota_supplier_search) || 0,
        quota_exact_product: Number(createForm.quota_exact_product) || 0,
        quota_procurement_report: Number(createForm.quota_procurement_report) || 0,
        rate_limit_per_minute: Number(createForm.rate_limit_per_minute) || 30,
        notes: createForm.notes.trim(),
        expires_days: createForm.expires_days ? Number(createForm.expires_days) : null,
      }

      const res = await fetchApi<{ ok: boolean; raw_api_key: string; item: ApiKeyItem }>('/api/admin/api-keys', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      setShowCreateModal(false)
      setCreateForm({
        name: '',
        client_id: '',
        allowed_supplier_search: true,
        allowed_exact_product: true,
        allowed_procurement_report: true,
        quota_supplier_search: 20,
        quota_exact_product: 10,
        quota_procurement_report: 10,
        rate_limit_per_minute: 30,
        notes: '',
        expires_days: '',
      })
      await loadData()
      setShowRawKeyModal({ token: res.raw_api_key, name: res.item.name })
    } catch (err: any) {
      alert(`Ошибка создания ключа: ${err.message}`)
    }
  }

  async function handleRegenerateKey(keyItem: ApiKeyItem) {
    if (!window.confirm(`Перегенерировать токен для «${keyItem.name}»?\nСтарый ключ немедленно перестанет работать!`)) {
      return
    }
    try {
      const res = await fetchApi<{ ok: boolean; raw_api_key: string; item: ApiKeyItem }>(
        `/api/admin/api-keys/${keyItem.id}/regenerate`,
        { method: 'POST' }
      )
      await loadData()
      setShowRawKeyModal({ token: res.raw_api_key, name: keyItem.name })
    } catch (err: any) {
      alert(`Ошибка перегенерации: ${err.message}`)
    }
  }

  async function handleToggleActive(keyItem: ApiKeyItem) {
    try {
      await fetchApi(`/api/admin/api-keys/${keyItem.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !keyItem.is_active }),
      })
      await loadData()
    } catch (err: any) {
      alert(`Ошибка: ${err.message}`)
    }
  }

  async function handleDeleteKey(keyItem: ApiKeyItem) {
    if (!window.confirm(`Удалить API-ключ «${keyItem.name}»? Это действие необратимо.`)) {
      return
    }
    try {
      await fetchApi(`/api/admin/api-keys/${keyItem.id}`, { method: 'DELETE' })
      await loadData()
    } catch (err: any) {
      alert(`Ошибка удаления: ${err.message}`)
    }
  }

  async function handleUpdateKey(e: React.FormEvent) {
    e.preventDefault()
    if (!editingKey) return
    try {
      await fetchApi(`/api/admin/api-keys/${editingKey.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editingKey.name,
          allowed_supplier_search: editingKey.allowed_supplier_search,
          allowed_exact_product: editingKey.allowed_exact_product,
          allowed_procurement_report: editingKey.allowed_procurement_report,
          quota_supplier_search: Number(editingKey.quota_supplier_search),
          quota_exact_product: Number(editingKey.quota_exact_product),
          quota_procurement_report: Number(editingKey.quota_procurement_report),
          rate_limit_per_minute: Number(editingKey.rate_limit_per_minute),
          notes: editingKey.notes,
        }),
      })
      setEditingKey(null)
      await loadData()
    } catch (err: any) {
      alert(`Ошибка обновления: ${err.message}`)
    }
  }

  async function runLiveTest() {
    if (!testerQuery.trim()) {
      alert('Пожалуйста, введите текст запроса или технического задания')
      return
    }
    setTestingRunning(true)
    setTesterResult(null)
    setTesterError(null)

    try {
      const res = await fetchApi<any>('/api/admin/api-keys/test', {
        method: 'POST',
        body: JSON.stringify({ tool: testerTool, query: testerQuery.trim() }),
      })
      setTesterResult(res)
    } catch (err: any) {
      setTesterError(err.message || 'Ошибка выполнения инструмента')
    } finally {
      setTestingRunning(false)
    }
  }

  const effectiveMasterToken = masterKeyInfo.raw_api_key || 'tl_admin_YOUR_MASTER_TOKEN_HERE'

  const claudeConfigJson = JSON.stringify(
    {
      mcpServers: {
        tenderlex: {
          command: 'python3',
          args: ['/root/projects/aipoisk-bot/scripts/tenderlex_mcp.py'],
          env: {
            TENDERLEX_API_KEY: effectiveMasterToken,
            TENDERLEX_API_URL: 'https://tenderlex.ru',
          },
        },
      },
    },
    null,
    2
  )

  const cursorConfigJson = JSON.stringify(
    {
      mcpServers: {
        tenderlex: {
          command: 'python3',
          args: ['/root/projects/aipoisk-bot/scripts/tenderlex_mcp.py'],
          env: {
            TENDERLEX_API_KEY: effectiveMasterToken,
            TENDERLEX_API_URL: 'https://tenderlex.ru',
          },
        },
      },
    },
    null,
    2
  )

  const codexInstructions = `### Интеграция TenderLex MCP с ChatGPT / Codex:
1. Запустите локальный MCP-сервер или используйте прямое обращение к REST API.
2. Базовый URL: https://tenderlex.ru/api/v1/mcp
3. Передавайте заголовок: Authorization: Bearer ${effectiveMasterToken}

Доступные функции:
- POST /api/v1/mcp/suppliers/search (Поиск поставщиков)
- POST /api/v1/mcp/products/exact-analogs (Подбор точного товара и аналогов Форма 2)
- POST /api/v1/mcp/procurements/analyze (Анализ документации 44-ФЗ / 223-ФЗ)
- GET /api/v1/mcp/balance (Проверка баланса и квот)`

  const pythonSnippet = `import requests

API_KEY = "${effectiveMasterToken}"
API_URL = "https://tenderlex.ru/api/v1/mcp"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. Поиск поставщиков
resp = requests.post(f"{API_URL}/suppliers/search", headers=headers, json={
    "specification": "Поставка насосов центробежных К 80-50-200",
    "target_count": 5,
    "include_quote_request": True
})
print("Поставщики:", resp.json())

# 2. Подбор товара и аналогов (Форма 2)
resp_exact = requests.post(f"{API_URL}/products/exact-analogs", headers=headers, json={
    "specification": "Светильник светодиодный 40 Вт, световой поток не менее 4500 лм, IP65",
    "procurement_title": "Поставка офисных светильников"
})
print("Точный товар и аналоги:", resp_exact.json())`

  return (
    <div className="mcp-container">
      {/* 1. MASTER ADMIN KEY SECTION */}
      <div className="mcp-card master-card">
        <div className="mcp-card-header">
          <div className="mcp-card-title-wrap">
            <div className="mcp-icon-badge master">
              <Shield size={20} />
            </div>
            <div>
              <h2>Личный Master API-ключ Администратора</h2>
              <p>Главный мастер-ключ с полным безлимитным доступом ко всем модулям TenderLex для Claude, Cursor и ваших личных агентов.</p>
            </div>
          </div>
          {masterKeyInfo.item && (
            <button
              type="button"
              className="ghost small-text"
              style={{ color: '#0f766e', borderColor: '#0f766e' }}
              onClick={() => handleRegenerateKey(masterKeyInfo.item!)}
            >
              <RefreshCw size={14} style={{ marginRight: 6 }} />
              Сгенерировать новый ключ
            </button>
          )}
        </div>

        <div className="mcp-token-box">
          <div className="mcp-token-display">
            <span className="token-label">Токен:</span>
            <code className="token-code">
              {masterKeyInfo.raw_api_key ? masterKeyInfo.raw_api_key : masterKeyInfo.item?.key_prefix || 'tl_admin_...'}
            </code>
          </div>
          <div className="mcp-token-actions">
            <button
              type="button"
              className="primary small-text"
              onClick={() =>
                handleCopy(
                  masterKeyInfo.raw_api_key || masterKeyInfo.item?.key_prefix || '',
                  'master_token'
                )
              }
            >
              {copiedKey === 'master_token' ? (
                <>
                  <Check size={14} /> Скопировано!
                </>
              ) : (
                <>
                  <Copy size={14} /> Скопировать
                </>
              )}
            </button>
          </div>
        </div>

        {masterKeyInfo.item && (
          <div className="master-meta-row">
            <span>
              ⚡ Лимит запросов: <strong>{masterKeyInfo.item.rate_limit_per_minute} req/min</strong>
            </span>
            <span>
              🔒 Права: <strong>Безлимит на все модули</strong>
            </span>
            <span>
              🕒 Последнее использование: <strong>{masterKeyInfo.item.last_used_at ? new Date(masterKeyInfo.item.last_used_at).toLocaleString('ru-RU') : 'Никогда'}</strong>
            </span>
          </div>
        )}
      </div>

      {/* 2. CONFIG & MCP INTEGRATION SNIPPETS */}
      <div className="mcp-card">
        <div className="mcp-card-header">
          <div className="mcp-card-title-wrap">
            <div className="mcp-icon-badge config">
              <Code2 size={20} />
            </div>
            <div>
              <h2>Подключение к AI-агентам и IDE (MCP / API)</h2>
              <p>Готовые файлы конфигурации для мгновенного добавления TenderLex в ваш Claude Desktop, Cursor или Python-код.</p>
            </div>
          </div>
        </div>

        <div className="config-tabs-nav">
          <button
            type="button"
            className={`config-tab-btn ${activeConfigTab === 'claude' ? 'active' : ''}`}
            onClick={() => setActiveConfigTab('claude')}
          >
            🍏 Claude Desktop
          </button>
          <button
            type="button"
            className={`config-tab-btn ${activeConfigTab === 'cursor' ? 'active' : ''}`}
            onClick={() => setActiveConfigTab('cursor')}
          >
            ⚡ Cursor / VS Code
          </button>
          <button
            type="button"
            className={`config-tab-btn ${activeConfigTab === 'codex' ? 'active' : ''}`}
            onClick={() => setActiveConfigTab('codex')}
          >
            🤖 ChatGPT Codex
          </button>
          <button
            type="button"
            className={`config-tab-btn ${activeConfigTab === 'python' ? 'active' : ''}`}
            onClick={() => setActiveConfigTab('python')}
          >
            🐍 Python / cURL
          </button>
        </div>

        <div className="config-snippet-body">
          {activeConfigTab === 'claude' && (
            <div>
              <p className="config-desc">
                Вставьте этот блок в ваш файл <code>~/Library/Application Support/Claude/claude_desktop_config.json</code> (macOS) или <code>%APPDATA%\Claude\claude_desktop_config.json</code> (Windows):
              </p>
              <div className="snippet-code-wrap">
                <pre>{claudeConfigJson}</pre>
                <button
                  type="button"
                  className="snippet-copy-btn"
                  onClick={() => handleCopy(claudeConfigJson, 'claude_cfg')}
                >
                  {copiedKey === 'claude_cfg' ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            </div>
          )}

          {activeConfigTab === 'cursor' && (
            <div>
              <p className="config-desc">
                Вставьте этот блок в ваш файл <code>.cursor/mcp.json</code> в корне проекта:
              </p>
              <div className="snippet-code-wrap">
                <pre>{cursorConfigJson}</pre>
                <button
                  type="button"
                  className="snippet-copy-btn"
                  onClick={() => handleCopy(cursorConfigJson, 'cursor_cfg')}
                >
                  {copiedKey === 'cursor_cfg' ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            </div>
          )}

          {activeConfigTab === 'codex' && (
            <div>
              <p className="config-desc">Параметры для добавления TenderLex в качестве Custom Action или вызова через REST API:</p>
              <div className="snippet-code-wrap">
                <pre>{codexInstructions}</pre>
                <button
                  type="button"
                  className="snippet-copy-btn"
                  onClick={() => handleCopy(codexInstructions, 'codex_cfg')}
                >
                  {copiedKey === 'codex_cfg' ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            </div>
          )}

          {activeConfigTab === 'python' && (
            <div>
              <p className="config-desc">Пример прямого вызова API TenderLex на Python:</p>
              <div className="snippet-code-wrap">
                <pre>{pythonSnippet}</pre>
                <button
                  type="button"
                  className="snippet-copy-btn"
                  onClick={() => handleCopy(pythonSnippet, 'python_cfg')}
                >
                  {copiedKey === 'python_cfg' ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. CLIENT API KEYS MANAGEMENT TABLE */}
      <div className="mcp-card">
        <div className="mcp-card-header">
          <div className="mcp-card-title-wrap">
            <div className="mcp-icon-badge client">
              <KeyRound size={20} />
            </div>
            <div>
              <h2>Клиентские и партнерские API-ключи ({keys.filter(k => !k.is_admin).length})</h2>
              <p>Создание, продажа и управление доступом к API TenderLex для внешних клиентов, интеграторов и партнеров.</p>
            </div>
          </div>
          <button
            type="button"
            className="primary"
            onClick={() => setShowCreateModal(true)}
          >
            <Plus size={16} style={{ marginRight: 6 }} />
            Создать API-ключ
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)' }}>
            <Loader2 size={24} className="spin" style={{ margin: '0 auto 8px' }} />
            Загрузка списка ключей...
          </div>
        ) : keys.filter(k => !k.is_admin).length === 0 ? (
          <div className="mcp-empty-state">
            <KeyRound size={36} />
            <p>У вас пока нет созданных клиентских ключей.</p>
            <button
              type="button"
              className="primary small-text"
              onClick={() => setShowCreateModal(true)}
            >
              + Создать первый клиентский ключ
            </button>
          </div>
        ) : (
          <div className="mcp-table-responsive">
            <table className="mcp-table">
              <thead>
                <tr>
                  <th>Название & Клиент</th>
                  <th>Префикс ключа</th>
                  <th>Разрешенные модули & Остатки квот</th>
                  <th>Статус</th>
                  <th>Использован</th>
                  <th style={{ textAlign: 'right' }}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {keys
                  .filter(k => !k.is_admin)
                  .map(k => (
                    <tr key={k.id} className={!k.is_active ? 'row-disabled' : ''}>
                      <td>
                        <strong style={{ fontSize: 14, color: '#0f172a' }}>{k.name}</strong>
                        {k.client_name && (
                          <div style={{ fontSize: 12, color: '#0f766e', marginTop: 2 }}>
                            👤 Клиент: {k.client_name}
                          </div>
                        )}
                        {k.notes && <div style={{ fontSize: 11, color: '#64748b' }}>{k.notes}</div>}
                      </td>
                      <td>
                        <code style={{ background: '#f1f5f9', padding: '3px 8px', borderRadius: 4, fontSize: 12 }}>
                          {k.key_prefix}
                        </code>
                      </td>
                      <td>
                        <div className="quota-tags-list">
                          {k.allowed_supplier_search && (
                            <span className="quota-tag suppliers" title="Поиск поставщиков">
                              🔍 Поиск: <strong>{k.spent_supplier_search} / {k.quota_supplier_search}</strong>
                            </span>
                          )}
                          {k.allowed_exact_product && (
                            <span className="quota-tag exact" title="Подбор товара и аналогов">
                              🔬 Аналоги: <strong>{k.spent_exact_product} / {k.quota_exact_product}</strong>
                            </span>
                          )}
                          {k.allowed_procurement_report && (
                            <span className="quota-tag audit" title="Анализ документации">
                              📑 Анализ: <strong>{k.spent_procurement_report} / {k.quota_procurement_report}</strong>
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        {k.is_active ? (
                          <span className="pill balance" style={{ fontSize: 11 }}>Активен</span>
                        ) : (
                          <span className="pill warning" style={{ fontSize: 11 }}>Заблокирован</span>
                        )}
                      </td>
                      <td>
                        <small style={{ color: '#64748b' }}>
                          {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('ru-RU') : 'Никогда'}
                        </small>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: 6 }}>
                          <button
                            type="button"
                            className="icon-button small"
                            title="Перегенерировать токен"
                            onClick={() => handleRegenerateKey(k)}
                          >
                            <RefreshCw size={14} />
                          </button>
                          <button
                            type="button"
                            className="icon-button small"
                            title="Редактировать квоты"
                            onClick={() => setEditingKey(k)}
                          >
                            <Edit2 size={14} />
                          </button>
                          <button
                            type="button"
                            className={`icon-button small ${k.is_active ? 'warning' : ''}`}
                            title={k.is_active ? 'Заблокировать' : 'Активировать'}
                            onClick={() => handleToggleActive(k)}
                          >
                            <Power size={14} />
                          </button>
                          <button
                            type="button"
                            className="icon-button small danger"
                            title="Удалить"
                            onClick={() => handleDeleteKey(k)}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 4. INTERACTIVE LIVE TESTER CONSOLE */}
      <div className="mcp-card">
        <div className="mcp-card-header">
          <div className="mcp-card-title-wrap">
            <div className="mcp-icon-badge tester">
              <Terminal size={20} />
            </div>
            <div>
              <h2>Тестирование инструментов MCP и API (Live Console)</h2>
              <p>Мгновенная проверка работы модулей TenderLex в реальном времени прямо из панели управления.</p>
            </div>
          </div>
        </div>

        <div className="tester-grid">
          <div>
            <label className="field" style={{ marginBottom: 12 }}>
              <span>Выберите инструмент для проверки:</span>
              <select
                value={testerTool}
                onChange={e => setTesterTool(e.target.value as any)}
                style={{ height: 38 }}
              >
                <option value="supplier_search">🔍 Поиск поставщиков (supplier_search)</option>
                <option value="exact_product">🔬 Подбор товара и аналогов Форма 2 (exact_product)</option>
                <option value="procurement_report">📑 Анализ документации и контракта (procurement_report)</option>
              </select>
            </label>

            <label className="field">
              <span>Текст технического задания / спецификации:</span>
              <textarea
                rows={6}
                placeholder="Вставьте фрагмент ТЗ, наименование оборудования или проект контракта..."
                value={testerQuery}
                onChange={e => setTesterQuery(e.target.value)}
              />
            </label>

            <div style={{ marginTop: 14 }}>
              <button
                type="button"
                className="primary"
                disabled={testingRunning || !testerQuery.trim()}
                onClick={() => void runLiveTest()}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                {testingRunning ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
                {testingRunning ? 'Выполняю поиск и аудит...' : 'Запустить тест'}
              </button>
            </div>
          </div>

          <div className="tester-output-box">
            <div className="tester-output-header">
              <span>Результат выполнения (JSON Output):</span>
              {testerResult && (
                <span className="pill balance" style={{ fontSize: 11 }}>
                  Время: {testerResult.duration_seconds} сек
                </span>
              )}
            </div>
            {testingRunning ? (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--muted)' }}>
                <Loader2 size={28} className="spin" style={{ margin: '0 auto 12px', color: '#0f766e' }} />
                Идет выполнение через реальный пайплайн TenderLex...
              </div>
            ) : testerError ? (
              <div className="alert error" style={{ margin: 12 }}>
                <XCircle size={18} />
                {testerError}
              </div>
            ) : testerResult ? (
              <pre className="tester-json">{JSON.stringify(testerResult, null, 2)}</pre>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13, textAlign: 'center', padding: '60px 20px' }}>
                Введите данные слева и нажмите «Запустить тест», чтобы увидеть живой ответ сервиса.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* CREATE KEY MODAL */}
      {showCreateModal && (
        <div className="server-modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="server-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 540 }}>
            <div className="server-modal-header">
              <h3>Создание нового API-ключа</h3>
              <button className="server-modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateKey} style={{ display: 'grid', gap: 14 }}>
              <label className="field">
                <span>Название ключа / Партнер *</span>
                <input
                  required
                  placeholder="например: ООО ПромСнаб / Интеграция"
                  value={createForm.name}
                  onChange={e => setCreateForm({ ...createForm, name: e.target.value })}
                />
              </label>

              <label className="field">
                <span>Привязать к существующему клиенту (опционально):</span>
                <select
                  value={createForm.client_id}
                  onChange={e => setCreateForm({ ...createForm, client_id: e.target.value })}
                >
                  <option value="">-- Без привязки --</option>
                  {clients.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.username ? `(@${c.username})` : ''}
                    </option>
                  ))}
                </select>
              </label>

              <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}>
                <strong style={{ display: 'block', fontSize: 13, marginBottom: 8, color: '#0f172a' }}>
                  Разрешенные модули и лимиты (квоты):
                </strong>

                <div style={{ display: 'grid', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={createForm.allowed_supplier_search}
                        onChange={e => setCreateForm({ ...createForm, allowed_supplier_search: e.target.checked })}
                      />
                      🔍 Поиск поставщиков
                    </label>
                    <input
                      type="number"
                      placeholder="Квота"
                      style={{ width: 90, height: 32, padding: '2px 8px' }}
                      value={createForm.quota_supplier_search}
                      onChange={e => setCreateForm({ ...createForm, quota_supplier_search: Number(e.target.value) })}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={createForm.allowed_exact_product}
                        onChange={e => setCreateForm({ ...createForm, allowed_exact_product: e.target.checked })}
                      />
                      🔬 Подбор аналогов (Форма 2)
                    </label>
                    <input
                      type="number"
                      placeholder="Квота"
                      style={{ width: 90, height: 32, padding: '2px 8px' }}
                      value={createForm.quota_exact_product}
                      onChange={e => setCreateForm({ ...createForm, quota_exact_product: Number(e.target.value) })}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={createForm.allowed_procurement_report}
                        onChange={e => setCreateForm({ ...createForm, allowed_procurement_report: e.target.checked })}
                      />
                      📑 Анализ документации
                    </label>
                    <input
                      type="number"
                      placeholder="Квота"
                      style={{ width: 90, height: 32, padding: '2px 8px' }}
                      value={createForm.quota_procurement_report}
                      onChange={e => setCreateForm({ ...createForm, quota_procurement_report: Number(e.target.value) })}
                    />
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <label className="field">
                  <span>Лимит в минуту (Rate limit):</span>
                  <input
                    type="number"
                    value={createForm.rate_limit_per_minute}
                    onChange={e => setCreateForm({ ...createForm, rate_limit_per_minute: Number(e.target.value) })}
                  />
                </label>
                <label className="field">
                  <span>Срок действия (дней):</span>
                  <input
                    type="number"
                    placeholder="Бессрочно"
                    value={createForm.expires_days}
                    onChange={e => setCreateForm({ ...createForm, expires_days: e.target.value })}
                  />
                </label>
              </div>

              <label className="field">
                <span>Заметки / Примечания:</span>
                <input
                  placeholder="Дополнительная информация"
                  value={createForm.notes}
                  onChange={e => setCreateForm({ ...createForm, notes: e.target.value })}
                />
              </label>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
                <button type="button" className="ghost" onClick={() => setShowCreateModal(false)}>
                  Отмена
                </button>
                <button type="submit" className="primary">
                  Создать и получить ключ
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT KEY MODAL */}
      {editingKey && (
        <div className="server-modal-backdrop" onClick={() => setEditingKey(null)}>
          <div className="server-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 540 }}>
            <div className="server-modal-header">
              <h3>Редактирование API-ключа: {editingKey.name}</h3>
              <button className="server-modal-close" onClick={() => setEditingKey(null)}>✕</button>
            </div>
            <form onSubmit={handleUpdateKey} style={{ display: 'grid', gap: 14 }}>
              <label className="field">
                <span>Название ключа *</span>
                <input
                  required
                  value={editingKey.name}
                  onChange={e => setEditingKey({ ...editingKey, name: e.target.value })}
                />
              </label>

              <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}>
                <strong style={{ display: 'block', fontSize: 13, marginBottom: 8, color: '#0f172a' }}>
                  Квоты и разрешения:
                </strong>

                <div style={{ display: 'grid', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                      <input
                        type="checkbox"
                        checked={editingKey.allowed_supplier_search}
                        onChange={e => setEditingKey({ ...editingKey, allowed_supplier_search: e.target.checked })}
                      />
                      🔍 Поиск поставщиков (потрачено: {editingKey.spent_supplier_search})
                    </label>
                    <input
                      type="number"
                      style={{ width: 90, height: 32, padding: '2px 8px' }}
                      value={editingKey.quota_supplier_search}
                      onChange={e => setEditingKey({ ...editingKey, quota_supplier_search: Number(e.target.value) })}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                      <input
                        type="checkbox"
                        checked={editingKey.allowed_exact_product}
                        onChange={e => setEditingKey({ ...editingKey, allowed_exact_product: e.target.checked })}
                      />
                      🔬 Подбор аналогов (потрачено: {editingKey.spent_exact_product})
                    </label>
                    <input
                      type="number"
                      style={{ width: 90, height: 32, padding: '2px 8px' }}
                      value={editingKey.quota_exact_product}
                      onChange={e => setEditingKey({ ...editingKey, quota_exact_product: Number(e.target.value) })}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                      <input
                        type="checkbox"
                        checked={editingKey.allowed_procurement_report}
                        onChange={e => setEditingKey({ ...editingKey, allowed_procurement_report: e.target.checked })}
                      />
                      📑 Анализ документации (потрачено: {editingKey.spent_procurement_report})
                    </label>
                    <input
                      type="number"
                      style={{ width: 90, height: 32, padding: '2px 8px' }}
                      value={editingKey.quota_procurement_report}
                      onChange={e => setEditingKey({ ...editingKey, quota_procurement_report: Number(e.target.value) })}
                    />
                  </div>
                </div>
              </div>

              <label className="field">
                <span>Лимит запросов в минуту (Rate limit):</span>
                <input
                  type="number"
                  value={editingKey.rate_limit_per_minute}
                  onChange={e => setEditingKey({ ...editingKey, rate_limit_per_minute: Number(e.target.value) })}
                />
              </label>

              <label className="field">
                <span>Заметки:</span>
                <input
                  value={editingKey.notes}
                  onChange={e => setEditingKey({ ...editingKey, notes: e.target.value })}
                />
              </label>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
                <button type="button" className="ghost" onClick={() => setEditingKey(null)}>
                  Отмена
                </button>
                <button type="submit" className="primary">
                  Сохранить изменения
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RAW SECRET KEY REVEAL MODAL */}
      {showRawKeyModal && (
        <div className="server-modal-backdrop" onClick={() => setShowRawKeyModal(null)}>
          <div className="server-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 560 }}>
            <div className="server-modal-header">
              <h3 style={{ color: '#047857', display: 'flex', alignItems: 'center', gap: 8 }}>
                <CheckCircle2 size={20} />
                API-ключ успешно создан!
              </h3>
              <button className="server-modal-close" onClick={() => setShowRawKeyModal(null)}>✕</button>
            </div>
            <div style={{ padding: '4px 0' }}>
              <p style={{ fontSize: 13, color: '#334155', marginBottom: 12 }}>
                Скопируйте и сохраните этот ключ прямо сейчас. В целях безопасности открытый ключ больше <strong>никогда не будет показан</strong>.
              </p>

              <div className="mcp-token-box" style={{ margin: '14px 0' }}>
                <code className="token-code" style={{ wordBreak: 'break-all', fontSize: 13 }}>
                  {showRawKeyModal.token}
                </code>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18 }}>
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    handleCopy(showRawKeyModal.token, 'new_raw_key')
                  }}
                >
                  {copiedKey === 'new_raw_key' ? <Check size={16} /> : <Copy size={16} />}
                  {copiedKey === 'new_raw_key' ? 'Скопировано!' : 'Скопировать ключ'}
                </button>
                <button type="button" className="ghost" onClick={() => setShowRawKeyModal(null)}>
                  Закрыть
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
