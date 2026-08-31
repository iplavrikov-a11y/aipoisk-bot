import { useState, useEffect } from 'react'
import {
  KeyRound,
  Copy,
  Check,
  RefreshCw,
  Plus,
  Shield,
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
  Terminal,
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
  const [showTokenText, setShowTokenText] = useState(false)

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
  const [testerPolicy, setTesterPolicy] = useState<'normal' | 'minprom_registry_priority' | 'minprom_registry_only'>('normal')
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
        body: JSON.stringify({
          tool: testerTool,
          query: testerQuery.trim(),
          search_policy: testerTool === 'supplier_search' ? testerPolicy : 'normal',
        }),
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

  const codexInstructions = `### Интеграция TenderLex с ChatGPT / Codex:
Base URL: https://tenderlex.ru/api/v1/mcp
Headers: Authorization: Bearer ${effectiveMasterToken}

Эндпоинты:
- POST /api/v1/mcp/suppliers/search (Поиск поставщиков)
  Параметры:
  - specification: текст ТЗ или номенклатура
  - target_count: количество (от 1 до 50)
  - city: город/регион поставки (опционально)
  - search_policy: 'normal' (рынок РФ) | 'minprom_registry_priority' (приоритет реестра Минпромторга / ГИСП) | 'minprom_registry_only' (строго только реестр Минпромторга РФ)
- POST /api/v1/mcp/products/exact-analogs (Подбор товара и эквивалентных аналогов по Форме 2)
- POST /api/v1/mcp/procurements/analyze (Экспресс-аудит проекта контракта и рисков 44-ФЗ/223-ФЗ)
- GET /api/v1/mcp/balance (Остатки квот)`

  const pythonSnippet = `import requests

API_KEY = "${effectiveMasterToken}"
API_URL = "https://tenderlex.ru/api/v1/mcp"
headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Поиск поставщиков (режимы: 'normal', 'minprom_registry_priority', 'minprom_registry_only')
resp = requests.post(f"{API_URL}/suppliers/search", headers=headers, json={
    "specification": "Насос центробежный К 80-50-200",
    "target_count": 5,
    "search_policy": "minprom_registry_priority"  # или 'minprom_registry_only' / 'normal'
})
print(resp.json())`

  return (
    <div className="mcp-compact-root">
      {/* 1. TOP ROW: 2 COMPACT CARDS (MASTER KEY & CONFIG SNIPPET) */}
      <div className="mcp-top-grid">
        {/* Left: Master Key Card */}
        <div className="mcp-compact-card master">
          <div className="mcp-card-title-row">
            <div className="mcp-card-title-left">
              <span className="mcp-icon-tag master"><Shield size={16} /></span>
              <div>
                <h3>Master API-ключ Администратора</h3>
                <small>Полный безлимитный доступ ко всем модулям TenderLex</small>
              </div>
            </div>
            {masterKeyInfo.item && (
              <button
                type="button"
                className="mcp-mini-action-btn"
                title="Сгенерировать новый мастер-ключ"
                onClick={() => handleRegenerateKey(masterKeyInfo.item!)}
              >
                <RefreshCw size={13} />
                <span>Обновить</span>
              </button>
            )}
          </div>

          <div className="mcp-token-strip">
            <div className="mcp-token-value-wrap">
              <span className="mcp-token-prefix-label">TOKEN:</span>
              <code className="mcp-token-text">
                {showTokenText && masterKeyInfo.raw_api_key
                  ? masterKeyInfo.raw_api_key
                  : masterKeyInfo.item?.key_prefix || 'tl_admin_...'}
              </code>
            </div>
            <div className="mcp-token-btn-group">
              {masterKeyInfo.raw_api_key && (
                <button
                  type="button"
                  className="mcp-token-icon-btn"
                  title={showTokenText ? 'Скрыть токен' : 'Показать токен'}
                  onClick={() => setShowTokenText(!showTokenText)}
                >
                  {showTokenText ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              )}
              <button
                type="button"
                className="mcp-copy-btn"
                onClick={() =>
                  handleCopy(
                    masterKeyInfo.raw_api_key || masterKeyInfo.item?.key_prefix || '',
                    'master_token'
                  )
                }
              >
                {copiedKey === 'master_token' ? (
                  <>
                    <Check size={13} /> <span>Скопировано</span>
                  </>
                ) : (
                  <>
                    <Copy size={13} /> <span>Копировать</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {masterKeyInfo.item && (
            <div className="mcp-compact-meta-row">
              <span className="mcp-meta-pill">⚡ <strong>{masterKeyInfo.item.rate_limit_per_minute}</strong> req/min</span>
              <span className="mcp-meta-pill emerald">🔒 <strong>Безлимитный доступ</strong></span>
              <span className="mcp-meta-pill muted">
                🕒 {masterKeyInfo.item.last_used_at ? new Date(masterKeyInfo.item.last_used_at).toLocaleDateString('ru-RU') : 'Не использовался'}
              </span>
            </div>
          )}
        </div>

        {/* Right: Quick Connect Tabs */}
        <div className="mcp-compact-card">
          <div className="mcp-card-title-row">
            <div className="mcp-card-title-left">
              <span className="mcp-icon-tag config"><Code2 size={16} /></span>
              <div>
                <h3>Подключение к AI-ассистентам (MCP)</h3>
                <small>Конфигурации для Claude Desktop, Cursor, ChatGPT Codex</small>
              </div>
            </div>
          </div>

          <div className="mcp-tabs-pill-row">
            <button
              type="button"
              className={`mcp-tab-pill ${activeConfigTab === 'claude' ? 'active' : ''}`}
              onClick={() => setActiveConfigTab('claude')}
            >
              🍏 Claude Desktop
            </button>
            <button
              type="button"
              className={`mcp-tab-pill ${activeConfigTab === 'cursor' ? 'active' : ''}`}
              onClick={() => setActiveConfigTab('cursor')}
            >
              ⚡ Cursor
            </button>
            <button
              type="button"
              className={`mcp-tab-pill ${activeConfigTab === 'codex' ? 'active' : ''}`}
              onClick={() => setActiveConfigTab('codex')}
            >
              🤖 ChatGPT
            </button>
            <button
              type="button"
              className={`mcp-tab-pill ${activeConfigTab === 'python' ? 'active' : ''}`}
              onClick={() => setActiveConfigTab('python')}
            >
              🐍 Python
            </button>
          </div>

          <div className="mcp-compact-code-wrap">
            <pre className="mcp-compact-pre">
              {activeConfigTab === 'claude' && claudeConfigJson}
              {activeConfigTab === 'cursor' && cursorConfigJson}
              {activeConfigTab === 'codex' && codexInstructions}
              {activeConfigTab === 'python' && pythonSnippet}
            </pre>
            <button
              type="button"
              className="mcp-code-copy-btn"
              title="Скопировать конфигурацию"
              onClick={() => {
                const text =
                  activeConfigTab === 'claude'
                    ? claudeConfigJson
                    : activeConfigTab === 'cursor'
                    ? cursorConfigJson
                    : activeConfigTab === 'codex'
                    ? codexInstructions
                    : pythonSnippet
                handleCopy(text, 'snippet_cfg')
              }}
            >
              {copiedKey === 'snippet_cfg' ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
        </div>
      </div>

      {/* 2. CLIENT API KEYS TABLE */}
      <div className="mcp-compact-card">
        <div className="mcp-card-title-row">
          <div className="mcp-card-title-left">
            <span className="mcp-icon-tag client"><KeyRound size={16} /></span>
            <div>
              <h3>Клиентские API-ключи ({keys.filter(k => !k.is_admin).length})</h3>
              <small>Управление доступом и квотами для внешних интеграторов и клиентов</small>
            </div>
          </div>
          <button
            type="button"
            className="primary small-text"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            onClick={() => setShowCreateModal(true)}
          >
            <Plus size={15} />
            <span>Создать API-ключ</span>
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '30px 0', color: '#64748b' }}>
            <Loader2 size={20} className="spin" style={{ margin: '0 auto 6px' }} />
            Загрузка ключей...
          </div>
        ) : keys.filter(k => !k.is_admin).length === 0 ? (
          <div className="mcp-empty-state-compact">
            <p>Клиентских ключей пока нет. Создайте ключ для подключения партнера или внешней ERP.</p>
          </div>
        ) : (
          <div className="mcp-table-wrap">
            <table className="mcp-compact-table">
              <thead>
                <tr>
                  <th>Название & Клиент</th>
                  <th>Префикс ключа</th>
                  <th>Модули & Квоты (Использовано / Лимит)</th>
                  <th>Статус</th>
                  <th>Использован</th>
                  <th style={{ textAlign: 'right' }}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {keys
                  .filter(k => !k.is_admin)
                  .map(k => (
                    <tr key={k.id} className={!k.is_active ? 'row-inactive' : ''}>
                      <td>
                        <strong className="key-name-cell">{k.name}</strong>
                        {k.client_name && (
                          <div className="key-client-sub">👤 {k.client_name}</div>
                        )}
                        {k.notes && <div className="key-note-sub">{k.notes}</div>}
                      </td>
                      <td>
                        <code className="key-prefix-badge">{k.key_prefix}</code>
                      </td>
                      <td>
                        <div className="mcp-quota-pills">
                          {k.allowed_supplier_search && (
                            <span className="mcp-quota-badge search">
                              🔍 Поиск: <strong>{k.spent_supplier_search}/{k.quota_supplier_search}</strong>
                            </span>
                          )}
                          {k.allowed_exact_product && (
                            <span className="mcp-quota-badge exact">
                              🔬 Аналоги: <strong>{k.spent_exact_product}/{k.quota_exact_product}</strong>
                            </span>
                          )}
                          {k.allowed_procurement_report && (
                            <span className="mcp-quota-badge audit">
                              📑 Анализ: <strong>{k.spent_procurement_report}/{k.quota_procurement_report}</strong>
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        {k.is_active ? (
                          <span className="mcp-status-pill active">Активен</span>
                        ) : (
                          <span className="mcp-status-pill disabled">Отключен</span>
                        )}
                      </td>
                      <td>
                        <small style={{ color: '#64748b', fontSize: 12 }}>
                          {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('ru-RU') : 'Никогда'}
                        </small>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="mcp-actions-row">
                          <button
                            type="button"
                            className="icon-button small"
                            title="Перегенерировать токен"
                            onClick={() => handleRegenerateKey(k)}
                          >
                            <RefreshCw size={13} />
                          </button>
                          <button
                            type="button"
                            className="icon-button small"
                            title="Редактировать квоты"
                            onClick={() => setEditingKey(k)}
                          >
                            <Edit2 size={13} />
                          </button>
                          <button
                            type="button"
                            className={`icon-button small ${k.is_active ? 'warning' : ''}`}
                            title={k.is_active ? 'Заблокировать' : 'Активировать'}
                            onClick={() => handleToggleActive(k)}
                          >
                            <Power size={13} />
                          </button>
                          <button
                            type="button"
                            className="icon-button small danger"
                            title="Удалить"
                            onClick={() => handleDeleteKey(k)}
                          >
                            <Trash2 size={13} />
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

      {/* 3. LIVE TESTER CONSOLE (COMPACT 2-COLUMN) */}
      <div className="mcp-compact-card">
        <div className="mcp-card-title-row">
          <div className="mcp-card-title-left">
            <span className="mcp-icon-tag tester"><Terminal size={16} /></span>
            <div>
              <h3>Тестирование инструментов API (Live Console)</h3>
              <small>Живая проверка эндпоинтов в реальном времени</small>
            </div>
          </div>
        </div>

        <div className="mcp-tester-split">
          <div className="mcp-tester-form">
            <div className="mcp-field-wrap">
              <span className="mcp-label">Инструмент:</span>
              <select
                value={testerTool}
                onChange={e => setTesterTool(e.target.value as any)}
                className="mcp-select"
              >
                <option value="supplier_search">🔍 Поиск поставщиков (supplier_search)</option>
                <option value="exact_product">🔬 Подбор товара и аналогов (exact_product)</option>
                <option value="procurement_report">📑 Анализ документации и контракта (procurement_report)</option>
              </select>
            </div>

            {testerTool === 'supplier_search' && (
              <div className="mcp-field-wrap">
                <span className="mcp-label">Режим поиска поставщиков:</span>
                <select
                  value={testerPolicy}
                  onChange={e => setTesterPolicy(e.target.value as any)}
                  className="mcp-select"
                >
                  <option value="normal">🌐 Обычный поиск по рынку РФ (заводы, дилеры, оптовики)</option>
                  <option value="minprom_registry_priority">⭐ Приоритет Реестра Минпромторга (ГИСП) + добор</option>
                  <option value="minprom_registry_only">🏛️ Строго только Реестр Минпромторга РФ (нацрежим)</option>
                </select>
              </div>
            )}

            <div className="mcp-field-wrap">
              <span className="mcp-label">Текст ТЗ / спецификации:</span>
              <textarea
                rows={4}
                className="mcp-textarea"
                placeholder="Вставьте фрагмент ТЗ, наименование оборудования или проект контракта..."
                value={testerQuery}
                onChange={e => setTesterQuery(e.target.value)}
              />
            </div>

            <button
              type="button"
              className="primary small-text"
              disabled={testingRunning || !testerQuery.trim()}
              onClick={() => void runLiveTest()}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 4 }}
            >
              {testingRunning ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
              <span>{testingRunning ? 'Выполняю запрос...' : 'Запустить тест'}</span>
            </button>
          </div>

          <div className="mcp-tester-output-card">
            <div className="mcp-tester-out-head">
              <span>Ответ API (JSON Output)</span>
              {testerResult && (
                <span className="mcp-timing-badge">
                  ⏱️ {testerResult.duration_seconds} сек
                </span>
              )}
            </div>

            <div className="mcp-tester-out-body">
              {testingRunning ? (
                <div className="mcp-tester-loading">
                  <Loader2 size={22} className="spin" style={{ color: '#0f766e', marginBottom: 8 }} />
                  <div>Запрос выполняется через реальный пайплайн...</div>
                </div>
              ) : testerError ? (
                <div className="mcp-tester-err">
                  <XCircle size={16} />
                  <span>{testerError}</span>
                </div>
              ) : testerResult ? (
                <pre className="mcp-tester-json">{JSON.stringify(testerResult, null, 2)}</pre>
              ) : (
                <div className="mcp-tester-placeholder">
                  Введите данные слева и нажмите «Запустить тест» для просмотра ответа.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* CREATE KEY MODAL (COMPACT & FIXED CHECKBOXES) */}
      {showCreateModal && (
        <div className="server-modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="server-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 500 }}>
            <div className="server-modal-header">
              <h3 style={{ fontSize: 16 }}>Создание нового API-ключа</h3>
              <button className="server-modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateKey} className="mcp-modal-form">
              <label className="mcp-form-label">
                <span>Название ключа / Партнер *</span>
                <input
                  required
                  placeholder="например: ООО ПромСнаб / Интеграция"
                  value={createForm.name}
                  onChange={e => setCreateForm({ ...createForm, name: e.target.value })}
                />
              </label>

              <label className="mcp-form-label">
                <span>Привязать к клиенту:</span>
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

              {/* MODULE QUOTAS BOX */}
              <div className="mcp-modal-quotas-box">
                <span className="mcp-modal-quotas-title">Разрешенные модули и квоты (лимиты):</span>

                <div className="mcp-quota-row">
                  <label className="mcp-checkbox-label">
                    <input
                      type="checkbox"
                      checked={createForm.allowed_supplier_search}
                      onChange={e => setCreateForm({ ...createForm, allowed_supplier_search: e.target.checked })}
                    />
                    <span>🔍 Поиск поставщиков</span>
                  </label>
                  <div className="mcp-quota-input-wrap">
                    <input
                      type="number"
                      min={0}
                      className="mcp-quota-input"
                      value={createForm.quota_supplier_search}
                      onChange={e => setCreateForm({ ...createForm, quota_supplier_search: Number(e.target.value) })}
                    />
                    <small>запросов</small>
                  </div>
                </div>

                <div className="mcp-quota-row">
                  <label className="mcp-checkbox-label">
                    <input
                      type="checkbox"
                      checked={createForm.allowed_exact_product}
                      onChange={e => setCreateForm({ ...createForm, allowed_exact_product: e.target.checked })}
                    />
                    <span>🔬 Подбор товара и аналогов</span>
                  </label>
                  <div className="mcp-quota-input-wrap">
                    <input
                      type="number"
                      min={0}
                      className="mcp-quota-input"
                      value={createForm.quota_exact_product}
                      onChange={e => setCreateForm({ ...createForm, quota_exact_product: Number(e.target.value) })}
                    />
                    <small>запросов</small>
                  </div>
                </div>

                <div className="mcp-quota-row">
                  <label className="mcp-checkbox-label">
                    <input
                      type="checkbox"
                      checked={createForm.allowed_procurement_report}
                      onChange={e => setCreateForm({ ...createForm, allowed_procurement_report: e.target.checked })}
                    />
                    <span>📑 Анализ документации</span>
                  </label>
                  <div className="mcp-quota-input-wrap">
                    <input
                      type="number"
                      min={0}
                      className="mcp-quota-input"
                      value={createForm.quota_procurement_report}
                      onChange={e => setCreateForm({ ...createForm, quota_procurement_report: Number(e.target.value) })}
                    />
                    <small>запросов</small>
                  </div>
                </div>
              </div>

              <div className="mcp-modal-2col">
                <label className="mcp-form-label">
                  <span>Лимит в минуту (Rate limit):</span>
                  <input
                    type="number"
                    min={1}
                    max={300}
                    value={createForm.rate_limit_per_minute}
                    onChange={e => setCreateForm({ ...createForm, rate_limit_per_minute: Number(e.target.value) })}
                  />
                </label>
                <label className="mcp-form-label">
                  <span>Срок действия (дней):</span>
                  <input
                    type="number"
                    placeholder="Бессрочно"
                    value={createForm.expires_days}
                    onChange={e => setCreateForm({ ...createForm, expires_days: e.target.value })}
                  />
                </label>
              </div>

              <label className="mcp-form-label">
                <span>Заметки / Примечания:</span>
                <input
                  placeholder="Дополнительная информация"
                  value={createForm.notes}
                  onChange={e => setCreateForm({ ...createForm, notes: e.target.value })}
                />
              </label>

              <div className="mcp-modal-actions">
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
          <div className="server-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 500 }}>
            <div className="server-modal-header">
              <h3 style={{ fontSize: 16 }}>Редактирование: {editingKey.name}</h3>
              <button className="server-modal-close" onClick={() => setEditingKey(null)}>✕</button>
            </div>
            <form onSubmit={handleUpdateKey} className="mcp-modal-form">
              <label className="mcp-form-label">
                <span>Название ключа *</span>
                <input
                  required
                  value={editingKey.name}
                  onChange={e => setEditingKey({ ...editingKey, name: e.target.value })}
                />
              </label>

              <div className="mcp-modal-quotas-box">
                <span className="mcp-modal-quotas-title">Квоты и разрешения:</span>

                <div className="mcp-quota-row">
                  <label className="mcp-checkbox-label">
                    <input
                      type="checkbox"
                      checked={editingKey.allowed_supplier_search}
                      onChange={e => setEditingKey({ ...editingKey, allowed_supplier_search: e.target.checked })}
                    />
                    <span>🔍 Поиск (расход: {editingKey.spent_supplier_search})</span>
                  </label>
                  <div className="mcp-quota-input-wrap">
                    <input
                      type="number"
                      min={0}
                      className="mcp-quota-input"
                      value={editingKey.quota_supplier_search}
                      onChange={e => setEditingKey({ ...editingKey, quota_supplier_search: Number(e.target.value) })}
                    />
                    <small>запросов</small>
                  </div>
                </div>

                <div className="mcp-quota-row">
                  <label className="mcp-checkbox-label">
                    <input
                      type="checkbox"
                      checked={editingKey.allowed_exact_product}
                      onChange={e => setEditingKey({ ...editingKey, allowed_exact_product: e.target.checked })}
                    />
                    <span>🔬 Аналоги (расход: {editingKey.spent_exact_product})</span>
                  </label>
                  <div className="mcp-quota-input-wrap">
                    <input
                      type="number"
                      min={0}
                      className="mcp-quota-input"
                      value={editingKey.quota_exact_product}
                      onChange={e => setEditingKey({ ...editingKey, quota_exact_product: Number(e.target.value) })}
                    />
                    <small>запросов</small>
                  </div>
                </div>

                <div className="mcp-quota-row">
                  <label className="mcp-checkbox-label">
                    <input
                      type="checkbox"
                      checked={editingKey.allowed_procurement_report}
                      onChange={e => setEditingKey({ ...editingKey, allowed_procurement_report: e.target.checked })}
                    />
                    <span>📑 Анализ (расход: {editingKey.spent_procurement_report})</span>
                  </label>
                  <div className="mcp-quota-input-wrap">
                    <input
                      type="number"
                      min={0}
                      className="mcp-quota-input"
                      value={editingKey.quota_procurement_report}
                      onChange={e => setEditingKey({ ...editingKey, quota_procurement_report: Number(e.target.value) })}
                    />
                    <small>запросов</small>
                  </div>
                </div>
              </div>

              <label className="mcp-form-label">
                <span>Лимит в минуту (Rate limit):</span>
                <input
                  type="number"
                  min={1}
                  max={300}
                  value={editingKey.rate_limit_per_minute}
                  onChange={e => setEditingKey({ ...editingKey, rate_limit_per_minute: Number(e.target.value) })}
                />
              </label>

              <label className="mcp-form-label">
                <span>Заметки:</span>
                <input
                  value={editingKey.notes}
                  onChange={e => setEditingKey({ ...editingKey, notes: e.target.value })}
                />
              </label>

              <div className="mcp-modal-actions">
                <button type="button" className="ghost" onClick={() => setEditingKey(null)}>
                  Отмена
                </button>
                <button type="submit" className="primary">
                  Сохранить
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RAW SECRET KEY REVEAL MODAL */}
      {showRawKeyModal && (
        <div className="server-modal-backdrop" onClick={() => setShowRawKeyModal(null)}>
          <div className="server-modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="server-modal-header">
              <h3 style={{ color: '#047857', display: 'flex', alignItems: 'center', gap: 8, fontSize: 16 }}>
                <CheckCircle2 size={18} />
                Ключ успешно сгенерирован!
              </h3>
              <button className="server-modal-close" onClick={() => setShowRawKeyModal(null)}>✕</button>
            </div>
            <div style={{ padding: '4px 0' }}>
              <p style={{ fontSize: 13, color: '#475569', margin: '0 0 12px 0', lineHeight: 1.4 }}>
                Скопируйте и сохраните этот ключ прямо сейчас. В целях безопасности открытый ключ больше <strong>никогда не будет показан</strong>.
              </p>

              <div className="mcp-token-strip" style={{ margin: '12px 0' }}>
                <code className="mcp-token-text" style={{ wordBreak: 'break-all', fontSize: 13 }}>
                  {showRawKeyModal.token}
                </code>
              </div>

              <div className="mcp-modal-actions" style={{ marginTop: 16 }}>
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    handleCopy(showRawKeyModal.token, 'new_raw_key')
                  }}
                >
                  {copiedKey === 'new_raw_key' ? <Check size={15} /> : <Copy size={15} />}
                  <span>{copiedKey === 'new_raw_key' ? 'Скопировано!' : 'Скопировать ключ'}</span>
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
