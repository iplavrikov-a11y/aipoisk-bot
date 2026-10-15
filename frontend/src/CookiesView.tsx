import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  ShieldCheck,
  RefreshCw,
  Search,
  Check,
  Save,
  Trash2,
  Edit3,
  Zap,
  Globe,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Plus,
  HelpCircle,
  ExternalLink,
  Lock,
  Layers,
  Sparkles,
  ArrowRight,
  X,
} from 'lucide-react'

export type CookieCatalogItem = {
  domain: string
  name: string
  category: string
  description: string
  test_url: string
  waf_type: string
  has_cookie: boolean
  cookie_length: number
  cookie_preview: string
  cookie_value: string
}

type TestResult = {
  status_code: number
  status_text: string
  accessible: boolean
  response_size: number
  duration_ms: number
  title: string
  has_cookie_applied: boolean
}

export function CookiesView({ onNavigateToMonitoring }: { onNavigateToMonitoring?: () => void }) {
  const [catalog, setCatalog] = useState<CookieCatalogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

  // Edit / Add Modal State
  const [modalOpen, setModalOpen] = useState(false)
  const [modalDomain, setModalDomain] = useState('')
  const [modalName, setModalName] = useState('')
  const [modalCookieInput, setModalCookieInput] = useState('')
  const [modalSaving, setModalSaving] = useState(false)
  const [modalTesting, setModalTesting] = useState(false)
  const [modalTestResult, setModalTestResult] = useState<TestResult | null>(null)
  const [modalError, setModalError] = useState<string | null>(null)

  // Quick Inline Testing State per domain: { [domain]: { testing: boolean, result?: TestResult } }
  const [testStates, setTestStates] = useState<Record<string, { testing: boolean; result?: TestResult }>>({})
  const [deleteConfirmDomain, setDeleteConfirmDomain] = useState<string | null>(null)

  const loadCookies = useCallback(async () => {
    try {
      setRefreshing(true)
      const res = await fetch('/api/cookies', { credentials: 'same-origin' })
      if (res.ok) {
        const data = await res.json()
        setCatalog(data.catalog || [])
      }
    } catch (err) {
      console.error('Failed to load cookies catalog', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadCookies()
  }, [loadCookies])

  // Categories list with counts
  const categories = useMemo(() => {
    const map = new Map<string, number>()
    catalog.forEach((item) => {
      const cat = item.category || 'Другое'
      map.set(cat, (map.get(cat) || 0) + 1)
    })
    return Array.from(map.entries()).map(([name, count]) => ({ name, count }))
  }, [catalog])

  const totalWithCookies = catalog.filter((c) => c.has_cookie).length
  const totalDomains = catalog.length

  // Filtered catalog
  const filteredCatalog = useMemo(() => {
    return catalog.filter((item) => {
      if (categoryFilter === 'active' && !item.has_cookie) return false
      if (categoryFilter === 'missing' && item.has_cookie) return false
      if (categoryFilter !== 'all' && categoryFilter !== 'active' && categoryFilter !== 'missing' && item.category !== categoryFilter) {
        return false
      }
      if (!search.trim()) return true
      const q = search.toLowerCase()
      return (
        item.domain.toLowerCase().includes(q) ||
        item.name.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.waf_type.toLowerCase().includes(q)
      )
    })
  }, [catalog, categoryFilter, search])

  // Open Edit Modal for a specific domain
  const handleOpenEdit = (item: CookieCatalogItem) => {
    setModalDomain(item.domain)
    setModalName(item.name)
    setModalCookieInput(item.cookie_value || '')
    setModalTestResult(null)
    setModalError(null)
    setModalOpen(true)
  }

  // Open Add Custom Domain Modal
  const handleOpenAddCustom = () => {
    setModalDomain('')
    setModalName('')
    setModalCookieInput('')
    setModalTestResult(null)
    setModalError(null)
    setModalOpen(true)
  }

  // Save Cookie in Modal
  const handleSaveModal = async () => {
    if (!modalDomain.trim()) {
      setModalError('Укажите домен сайта (например, ozon.ru)')
      return
    }
    setModalSaving(true)
    setModalError(null)
    try {
      const res = await fetch(`/api/cookies/${encodeURIComponent(modalDomain.trim().toLowerCase())}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cookie: modalCookieInput }),
        credentials: 'same-origin',
      })
      if (res.ok) {
        setModalOpen(false)
        void loadCookies()
      } else {
        const errData = await res.json().catch(() => ({}))
        setModalError(errData.detail || 'Не удалось сохранить куки')
      }
    } catch (err: any) {
      setModalError(String(err))
    } finally {
      setModalSaving(false)
    }
  }

  // Test Cookie in Modal without saving
  const handleTestModalCookie = async () => {
    if (!modalDomain.trim()) {
      setModalError('Сначала укажите домен сайта для проверки')
      return
    }
    setModalTesting(true)
    setModalTestResult(null)
    setModalError(null)
    try {
      const res = await fetch(`/api/cookies/${encodeURIComponent(modalDomain.trim().toLowerCase())}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cookie: modalCookieInput }),
        credentials: 'same-origin',
      })
      if (res.ok) {
        const result: TestResult = await res.json()
        setModalTestResult(result)
      } else {
        setModalError('Ошибка запуска теста на сервере')
      }
    } catch (err: any) {
      setModalError(String(err))
    } finally {
      setModalTesting(false)
    }
  }

  // Quick inline domain test
  const handleQuickTest = async (domain: string) => {
    setTestStates((prev) => ({
      ...prev,
      [domain]: { testing: true, result: prev[domain]?.result },
    }))
    try {
      const res = await fetch(`/api/cookies/${encodeURIComponent(domain)}/test`, {
        method: 'POST',
        credentials: 'same-origin',
      })
      if (res.ok) {
        const result: TestResult = await res.json()
        setTestStates((prev) => ({
          ...prev,
          [domain]: { testing: false, result },
        }))
      } else {
        setTestStates((prev) => ({
          ...prev,
          [domain]: {
            testing: false,
            result: {
              status_code: 500,
              status_text: 'Ошибка сервера при тесте',
              accessible: false,
              response_size: 0,
              duration_ms: 0,
              title: '',
              has_cookie_applied: false,
            },
          },
        }))
      }
    } catch (err) {
      setTestStates((prev) => ({
        ...prev,
        [domain]: {
          testing: false,
          result: {
            status_code: 500,
            status_text: 'Ошибка соединения',
            accessible: false,
            response_size: 0,
            duration_ms: 0,
            title: '',
            has_cookie_applied: false,
          },
        },
      }))
    }
  }

  // Delete Cookie
  const handleDeleteCookie = async (domain: string) => {
    try {
      const res = await fetch(`/api/cookies/${encodeURIComponent(domain)}`, {
        method: 'DELETE',
        credentials: 'same-origin',
      })
      if (res.ok) {
        setDeleteConfirmDomain(null)
        void loadCookies()
      }
    } catch (err) {
      console.error(err)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
        <Loader2 className="animate-spin text-slate-400" size={32} />
      </div>
    )
  }

  return (
    <div className="cookies-container">
      {/* Top Action Bar */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        {onNavigateToMonitoring && (
          <button
            type="button"
            onClick={onNavigateToMonitoring}
            className="cookies-btn-secondary"
            style={{ fontSize: '12.5px', padding: '0 12px', minHeight: '34px' }}
          >
            <span>В мониторинг цен</span>
            <ArrowRight size={14} />
          </button>
        )}
        <button
          type="button"
          onClick={loadCookies}
          disabled={refreshing}
          className="cookies-btn-secondary"
          style={{ fontSize: '12.5px', padding: '0 12px', minHeight: '34px' }}
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          <span>Обновить</span>
        </button>
        <button
          type="button"
          onClick={handleOpenAddCustom}
          className="cookies-btn-primary"
          style={{ fontSize: '12.5px', padding: '0 14px', minHeight: '34px' }}
        >
          <Plus size={15} />
          <span>Добавить сайт</span>
        </button>
      </div>

      {/* KPI Stats Strip */}
      <div className="cookies-kpi-grid">
        <div className="cookies-kpi-card">
          <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#ecfdf5', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <CheckCircle2 size={20} color="#059669" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Активных cookies</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#059669', marginTop: '1px' }}>
              {totalWithCookies}{' '}
              <span style={{ fontSize: '12px', fontWeight: 500, color: '#64748b' }}>из {totalDomains} сайтов</span>
            </div>
          </div>
        </div>

        <div className="cookies-kpi-card">
          <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Layers size={20} color="#2563eb" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Маркетплейсы</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#1e293b', marginTop: '1px' }}>
              {catalog.filter((c) => c.category === 'Маркетплейсы' && c.has_cookie).length}{' '}
              <span style={{ fontSize: '12px', fontWeight: 500, color: '#64748b' }}>
                из {catalog.filter((c) => c.category === 'Маркетплейсы').length}
              </span>
            </div>
          </div>
        </div>

        <div className="cookies-kpi-card">
          <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Lock size={20} color="#d97706" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Защита WAF</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#b45309', marginTop: '2px' }}>
              Cloudflare, Qrator, WBAAS
            </div>
          </div>
        </div>

        <div className="cookies-kpi-card">
          <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Sparkles size={20} color="#475569" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Форматы ввода</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginTop: '2px' }}>
              JSON, DevTools, Raw
            </div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="cookies-filter-strip">
        <div className="cookies-filter-pills">
          <button
            type="button"
            onClick={() => setCategoryFilter('all')}
            className={`cookies-pill-btn ${categoryFilter === 'all' ? 'active' : ''}`}
          >
            Все ({totalDomains})
          </button>
          <button
            type="button"
            onClick={() => setCategoryFilter('active')}
            className={`cookies-pill-btn ${categoryFilter === 'active' ? 'active-green' : ''}`}
          >
            ✓ Активны ({totalWithCookies})
          </button>
          <button
            type="button"
            onClick={() => setCategoryFilter('missing')}
            className={`cookies-pill-btn ${categoryFilter === 'missing' ? 'active' : ''}`}
          >
            Без кук ({totalDomains - totalWithCookies})
          </button>
          {categories.map((c) => (
            <button
              key={c.name}
              type="button"
              onClick={() => setCategoryFilter(c.name)}
              className={`cookies-pill-btn ${categoryFilter === c.name ? 'active' : ''}`}
            >
              {c.name} ({c.count})
            </button>
          ))}
        </div>

        <div style={{ position: 'relative', width: '260px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: '#94a3b8' }} />
          <input
            type="text"
            placeholder="Поиск по домену..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="cookies-input-text"
            style={{ paddingLeft: '32px', minHeight: '34px', fontSize: '12.5px' }}
          />
        </div>
      </div>

      {/* Catalog Cards Grid */}
      <div className="cookies-grid">
        {filteredCatalog.map((item) => {
          const testState = testStates[item.domain]
          const isTesting = Boolean(testState?.testing)
          const testRes = testState?.result
          const isDeleting = deleteConfirmDomain === item.domain

          return (
            <div
              key={item.domain}
              className={`cookies-card ${item.has_cookie ? 'has-cookie' : ''}`}
            >
              <div>
                {/* Top Row: Title, Domain, Status */}
                <div className="cookies-card-header">
                  <div>
                    <div className="cookies-card-title">
                      <Globe size={15} color={item.has_cookie ? '#059669' : '#64748b'} />
                      <span>{item.name}</span>
                    </div>
                    <div className="cookies-card-domain">
                      {item.domain}
                    </div>
                  </div>
                  <div>
                    {item.has_cookie ? (
                      <span className="cookies-badge-active">
                        <Check size={12} />
                        Активны ({item.cookie_length} зн.)
                      </span>
                    ) : (
                      <span
                        className="cookies-badge-snippet"
                        title="Цены с этого домена собираются через сниппеты Яндекса"
                      >
                        Сниппеты Яндекса
                      </span>
                    )}
                  </div>
                </div>

                {/* Description */}
                <div className="cookies-card-desc">
                  {item.description}
                </div>

                {/* Tags */}
                <div className="cookies-card-tags">
                  <span className="cookies-tag">
                    Категория: <strong>{item.category}</strong>
                  </span>
                  <span className="cookies-tag">
                    WAF: {item.waf_type}
                  </span>
                </div>

                {/* Quick Test Result Display */}
                {testRes && (
                  <div className={`cookies-test-result ${testRes.accessible ? 'success' : 'fail'}`}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: 600 }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        {testRes.accessible ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                        {testRes.status_text}
                      </span>
                      <span style={{ color: '#64748b' }}>{testRes.duration_ms} мс</span>
                    </div>
                    {testRes.title && (
                      <div style={{ marginTop: '3px', color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        «{testRes.title}»
                      </div>
                    )}
                    {testRes.response_size > 0 && (
                      <div style={{ color: '#64748b', marginTop: '2px' }}>
                        Размер: {(testRes.response_size / 1024).toFixed(1)} КБ {testRes.has_cookie_applied ? '• с куками' : '• без кук'}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Bottom Actions Row */}
              <div className="cookies-card-actions">
                <button
                  type="button"
                  onClick={() => handleQuickTest(item.domain)}
                  disabled={isTesting}
                  className="cookies-card-btn"
                  title="Отправить проверочный HTTP GET-запрос с сервера с текущими cookies"
                >
                  {isTesting ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} color="#2563eb" />}
                  <span>{isTesting ? 'Проверка...' : 'Тест соединения'}</span>
                </button>

                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    type="button"
                    onClick={() => handleOpenEdit(item)}
                    className="cookies-card-btn"
                  >
                    <Edit3 size={13} />
                    <span>{item.has_cookie ? 'Изменить' : 'Вставить куки'}</span>
                  </button>

                  {item.has_cookie && (
                    <>
                      {isDeleting ? (
                        <div style={{ display: 'flex', gap: '4px' }}>
                          <button
                            type="button"
                            onClick={() => handleDeleteCookie(item.domain)}
                            style={{
                              background: '#dc2626',
                              color: '#fff',
                              border: 'none',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              cursor: 'pointer',
                              fontWeight: 600,
                            }}
                          >
                            Да, удалить
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteConfirmDomain(null)}
                            style={{
                              background: '#e2e8f0',
                              color: '#334155',
                              border: 'none',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              cursor: 'pointer',
                            }}
                          >
                            Отмена
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setDeleteConfirmDomain(item.domain)}
                          style={{
                            background: 'transparent',
                            color: '#94a3b8',
                            border: '1px solid #e2e8f0',
                            padding: '4px 8px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                          }}
                          title="Очистить куки для этого сайта"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Edit / Add Modal */}
      {modalOpen && (
        <div
          className="cookies-modal-backdrop"
          onClick={() => setModalOpen(false)}
        >
          <div
            className="cookies-modal-card"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cookies-modal-header">
              <div>
                <h3 className="cookies-modal-title">
                  {modalName ? `${modalName} (${modalDomain})` : 'Добавить сайт и cookies'}
                </h3>
                <div className="cookies-modal-sub">
                  Вставьте сессионные куки в любом формате: текст, JSON-массив из расширений или таблица DevTools
                </div>
              </div>
              <button
                type="button"
                className="cookies-modal-close-btn"
                onClick={() => setModalOpen(false)}
                title="Закрыть"
              >
                <X size={18} />
              </button>
            </div>

            {modalError && (
              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', borderRadius: '6px', padding: '10px 12px', fontSize: '12px', marginBottom: '14px' }}>
                {modalError}
              </div>
            )}

            {/* Domain input if adding custom */}
            <div style={{ marginBottom: '14px' }}>
              <label className="cookies-field-label">
                Домен сайта (без https:// и www) *
              </label>
              <input
                type="text"
                value={modalDomain}
                onChange={(e) => setModalDomain(e.target.value.toLowerCase().trim())}
                placeholder="например: ozon.ru или petrovich.ru"
                className="cookies-input-text"
              />
            </div>

            {/* Cookies Textarea */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
                <label className="cookies-field-label" style={{ marginBottom: 0 }}>
                  Содержимое Cookies (raw-строка, JSON или таблица из DevTools) *
                </label>
                {modalCookieInput && (
                  <span style={{ fontSize: '11px', color: '#64748b' }}>
                    Длина: {modalCookieInput.length} символов
                  </span>
                )}
              </div>
              <textarea
                rows={7}
                value={modalCookieInput}
                onChange={(e) => setModalCookieInput(e.target.value)}
                placeholder={'Примеры поддерживаемых форматов:\n1. Строка: "name=val; name2=val2; __Secure-access-token=..."\n2. JSON из Cookie-Editor: [{"name": "..", "value": ".."}]\n3. Таблица из вкладки DevTools Application -> Storage -> Cookies'}
                className="cookies-textarea"
              />
            </div>

            {/* Test result inside modal */}
            {modalTestResult && (
              <div
                className={`cookies-test-result ${modalTestResult.accessible ? 'success' : 'fail'}`}
                style={{ marginBottom: '14px', padding: '10px 12px', fontSize: '12px' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: 600 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {modalTestResult.accessible ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
                    {modalTestResult.status_text}
                  </span>
                  <span style={{ color: '#64748b' }}>Время: {modalTestResult.duration_ms} мс</span>
                </div>
                {modalTestResult.title && (
                  <div style={{ color: '#334155', marginTop: '4px' }}>
                    Заголовок страницы: «<strong>{modalTestResult.title}</strong>»
                  </div>
                )}
                <div style={{ color: '#64748b', fontSize: '11px', marginTop: '2px' }}>
                  Размер ответа: {(modalTestResult.response_size / 1024).toFixed(1)} КБ (HTTP {modalTestResult.status_code})
                </div>
              </div>
            )}

            {/* Quick helper tip */}
            <div className="cookies-helper-box">
              <div style={{ fontWeight: 600, color: '#1e293b', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <HelpCircle size={13} color="#2563eb" />
                <span>Как быстро скопировать cookies:</span>
              </div>
              <div>• <strong>DevTools:</strong> на странице сайта нажать <code>F12</code> → вкладка <strong>Application</strong> → слева <strong>Cookies</strong> → выделить все строки (<code>Ctrl+A</code>) и вставить сюда.</div>
              <div style={{ marginTop: '2px' }}>• <strong>Расширение Cookie-Editor:</strong> нажать значок расширения на вкладке сайта → <strong>Export</strong> → <strong>JSON</strong> → вставить сюда.</div>
            </div>

            {/* Modal Actions Footer */}
            <div className="cookies-modal-footer">
              <button
                type="button"
                onClick={handleTestModalCookie}
                disabled={modalTesting || !modalCookieInput.trim()}
                className="cookies-btn-test-action"
              >
                {modalTesting ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} color="#2563eb" />}
                <span>{modalTesting ? 'Проверяю...' : 'Проверить без сохранения'}</span>
              </button>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="cookies-btn-secondary"
                >
                  Отмена
                </button>
                <button
                  type="button"
                  onClick={handleSaveModal}
                  disabled={modalSaving}
                  className="cookies-btn-primary"
                >
                  {modalSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  <span>{modalSaving ? 'Сохранение...' : 'Сохранить и применить'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
