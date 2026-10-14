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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={22} color="#059669" />
            Куки площадок и защита от WAF
          </h1>
          <div style={{ fontSize: '13px', color: '#64748b', marginTop: '2px' }}>
            Управление сессионными cookies для прямого сбора цен с маркетплейсов и каталогов поставщиков
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {onNavigateToMonitoring && (
            <button
              onClick={onNavigateToMonitoring}
              className="btn btn-secondary"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '13px' }}
            >
              <span>В мониторинг цен</span>
              <ArrowRight size={14} />
            </button>
          )}
          <button
            onClick={loadCookies}
            disabled={refreshing}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '13px' }}
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Обновить
          </button>
          <button
            onClick={handleOpenAddCustom}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 14px', fontSize: '13px' }}
          >
            <Plus size={15} />
            Добавить сайт
          </button>
        </div>
      </div>

      {/* KPI Stats Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
        <div className="card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: '#ecfdf5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CheckCircle2 size={22} color="#059669" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Активных cookies</div>
            <div style={{ fontSize: '22px', fontWeight: 700, color: '#059669' }}>
              {totalWithCookies}{' '}
              <span style={{ fontSize: '13px', fontWeight: 500, color: '#64748b' }}>из {totalDomains} сайтов</span>
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Layers size={22} color="#2563eb" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Маркетплейсы</div>
            <div style={{ fontSize: '22px', fontWeight: 700, color: '#1e293b' }}>
              {catalog.filter((c) => c.category === 'Маркетплейсы' && c.has_cookie).length}{' '}
              <span style={{ fontSize: '13px', fontWeight: 500, color: '#64748b' }}>
                из {catalog.filter((c) => c.category === 'Маркетплейсы').length}
              </span>
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Lock size={22} color="#d97706" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Защита от WAF</div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: '#b45309', marginTop: '4px' }}>
              Cloudflare, Qrator, WBAAS
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Sparkles size={22} color="#475569" />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Форматы ввода</div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#334155', marginTop: '2px' }}>
              JSON, DevTools, Text
            </div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card" style={{ padding: '12px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            type="button"
            onClick={() => setCategoryFilter('all')}
            style={{
              padding: '5px 10px',
              fontSize: '12px',
              fontWeight: 500,
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              background: categoryFilter === 'all' ? '#0f172a' : '#f1f5f9',
              color: categoryFilter === 'all' ? '#ffffff' : '#475569',
            }}
          >
            Все ({totalDomains})
          </button>
          <button
            type="button"
            onClick={() => setCategoryFilter('active')}
            style={{
              padding: '5px 10px',
              fontSize: '12px',
              fontWeight: 500,
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              background: categoryFilter === 'active' ? '#059669' : '#ecfdf5',
              color: categoryFilter === 'active' ? '#ffffff' : '#059669',
            }}
          >
            ✓ Активны с куками ({totalWithCookies})
          </button>
          <button
            type="button"
            onClick={() => setCategoryFilter('missing')}
            style={{
              padding: '5px 10px',
              fontSize: '12px',
              fontWeight: 500,
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              background: categoryFilter === 'missing' ? '#475569' : '#f1f5f9',
              color: categoryFilter === 'missing' ? '#ffffff' : '#64748b',
            }}
          >
            Без кук ({totalDomains - totalWithCookies})
          </button>
          {categories.map((c) => (
            <button
              key={c.name}
              type="button"
              onClick={() => setCategoryFilter(c.name)}
              style={{
                padding: '5px 10px',
                fontSize: '12px',
                fontWeight: 500,
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                background: categoryFilter === c.name ? '#2563eb' : '#f1f5f9',
                color: categoryFilter === c.name ? '#ffffff' : '#475569',
              }}
            >
              {c.name} ({c.count})
            </button>
          ))}
        </div>

        <div style={{ position: 'relative', width: '260px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '9px', color: '#94a3b8' }} />
          <input
            type="text"
            placeholder="Поиск по домену или названию..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="form-input"
            style={{ paddingLeft: '30px', paddingRight: '10px', paddingTop: '5px', paddingBottom: '5px', width: '100%', fontSize: '13px' }}
          />
        </div>
      </div>

      {/* Catalog Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '14px' }}>
        {filteredCatalog.map((item) => {
          const testState = testStates[item.domain]
          const isTesting = Boolean(testState?.testing)
          const testRes = testState?.result
          const isDeleting = deleteConfirmDomain === item.domain

          return (
            <div
              key={item.domain}
              className="card"
              style={{
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                border: item.has_cookie ? '1px solid #bbf7d0' : '1px solid #e2e8f0',
                background: item.has_cookie ? '#fcfdfd' : '#ffffff',
                boxShadow: item.has_cookie ? '0 1px 3px rgba(5, 150, 105, 0.08)' : '0 1px 3px rgba(0, 0, 0, 0.04)',
                position: 'relative',
              }}
            >
              <div>
                {/* Top Row: Title, Domain, Status */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', marginBottom: '8px' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '15px', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Globe size={16} color={item.has_cookie ? '#059669' : '#64748b'} />
                      {item.name}
                    </div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '1px' }}>
                      <code>{item.domain}</code>
                    </div>
                  </div>
                  <div>
                    {item.has_cookie ? (
                      <span
                        style={{
                          background: '#dcfce7',
                          color: '#15803d',
                          border: '1px solid #bbf7d0',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <Check size={12} />
                        Активны ({item.cookie_length} зн.)
                      </span>
                    ) : (
                      <span
                        style={{
                          background: '#f1f5f9',
                          color: '#64748b',
                          border: '1px solid #e2e8f0',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 500,
                        }}
                        title="Цены с этого домена собираются через сниппеты Яндекса"
                      >
                        Сниппеты Яндекса
                      </span>
                    )}
                  </div>
                </div>

                {/* Description & WAF info */}
                <div style={{ fontSize: '12px', color: '#475569', marginBottom: '10px', lineHeight: 1.4 }}>
                  {item.description}
                </div>

                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px' }}>
                  <span style={{ fontSize: '11px', background: '#f8fafc', border: '1px solid #e2e8f0', color: '#475569', padding: '2px 6px', borderRadius: '4px' }}>
                    Категория: <strong>{item.category}</strong>
                  </span>
                  <span style={{ fontSize: '11px', background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b', padding: '2px 6px', borderRadius: '4px' }}>
                    WAF: {item.waf_type}
                  </span>
                </div>

                {/* Quick Test Result Display */}
                {testRes && (
                  <div
                    style={{
                      background: testRes.accessible ? '#ecfdf5' : '#fef2f2',
                      border: `1px solid ${testRes.accessible ? '#a7f3d0' : '#fecaca'}`,
                      borderRadius: '6px',
                      padding: '8px 10px',
                      marginBottom: '12px',
                      fontSize: '11px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: 600 }}>
                      <span style={{ color: testRes.accessible ? '#065f46' : '#991b1b', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        {testRes.accessible ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
                        {testRes.status_text}
                      </span>
                      <span style={{ color: '#64748b' }}>{testRes.duration_ms} мс</span>
                    </div>
                    {testRes.title && (
                      <div style={{ color: '#475569', marginTop: '3px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                        Заголовок: «{testRes.title}»
                      </div>
                    )}
                    {testRes.response_size > 0 && (
                      <div style={{ color: '#64748b', marginTop: '2px' }}>
                        Размер ответа: {(testRes.response_size / 1024).toFixed(1)} КБ {testRes.has_cookie_applied ? '• с куками' : '• без кук'}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Bottom Actions Row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #f1f5f9', paddingTop: '10px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => handleQuickTest(item.domain)}
                  disabled={isTesting}
                  className="btn btn-secondary"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 10px',
                    fontSize: '12px',
                  }}
                  title="Отправить проверочный HTTP GET-запрос с сервера с текущими cookies"
                >
                  {isTesting ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} color="#2563eb" />}
                  {isTesting ? 'Проверка...' : 'Тест соединения'}
                </button>

                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    type="button"
                    onClick={() => handleOpenEdit(item)}
                    className="btn btn-secondary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '4px 10px',
                      fontSize: '12px',
                    }}
                  >
                    <Edit3 size={13} />
                    {item.has_cookie ? 'Изменить' : 'Вставить куки'}
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
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setModalOpen(false)}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: '680px',
              padding: '24px',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700, color: '#0f172a' }}>
                  {modalName ? `${modalName} (${modalDomain})` : 'Добавить сайт и cookies'}
                </h3>
                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                  Вставьте сессионные куки в любом формате: текст, JSON-массив из расширений или таблица DevTools
                </div>
              </div>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '18px', color: '#94a3b8' }}
              >
                ✕
              </button>
            </div>

            {modalError && (
              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', borderRadius: '6px', padding: '10px 12px', fontSize: '12px', marginBottom: '14px' }}>
                {modalError}
              </div>
            )}

            {/* Domain input if adding custom */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                Домен сайта (без https:// и www) *
              </label>
              <input
                type="text"
                value={modalDomain}
                onChange={(e) => setModalDomain(e.target.value.toLowerCase().trim())}
                placeholder="например: ozon.ru или petrovich.ru"
                className="form-input"
                style={{ width: '100%', padding: '7px 10px', fontSize: '13px' }}
              />
            </div>

            {/* Cookies Textarea */}
            <div style={{ marginBottom: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155' }}>
                  Содержимое Cookies (raw-строка, JSON или таблица из DevTools) *
                </label>
                {modalCookieInput && (
                  <span style={{ fontSize: '11px', color: '#64748b' }}>
                    Длина: {modalCookieInput.length} символов
                  </span>
                )}
              </div>
              <textarea
                rows={8}
                value={modalCookieInput}
                onChange={(e) => setModalCookieInput(e.target.value)}
                placeholder={'Примеры поддерживаемых форматов:\n1. Строка: "name=val; name2=val2; __Secure-access-token=..."\n2. JSON из Cookie-Editor: [{"name": "..", "value": ".."}]\n3. Таблица из вкладки DevTools Application -> Storage -> Cookies'}
                className="form-input"
                style={{ width: '100%', padding: '10px', fontSize: '12px', fontFamily: 'monospace', lineHeight: 1.4 }}
              />
            </div>

            {/* Test result inside modal */}
            {modalTestResult && (
              <div
                style={{
                  background: modalTestResult.accessible ? '#ecfdf5' : '#fef2f2',
                  border: `1px solid ${modalTestResult.accessible ? '#a7f3d0' : '#fecaca'}`,
                  borderRadius: '6px',
                  padding: '10px 12px',
                  marginBottom: '14px',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: 700 }}>
                  <span style={{ color: modalTestResult.accessible ? '#065f46' : '#991b1b', display: 'flex', alignItems: 'center', gap: '6px' }}>
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
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '10px 14px', fontSize: '11px', color: '#475569', marginBottom: '16px', lineHeight: 1.4 }}>
              <div style={{ fontWeight: 600, color: '#1e293b', marginBottom: '3px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <HelpCircle size={13} color="#2563eb" />
                Как быстро скопировать cookies:
              </div>
              • <strong>DevTools:</strong> на странице сайта нажать <code>F12</code> → вкладка <strong>Application</strong> → слева <strong>Cookies</strong> → выделить все строки (<code>Ctrl+A</code>) и вставить сюда.<br />
              • <strong>Расширение Cookie-Editor:</strong> нажать значок расширения на вкладке сайта → <strong>Export</strong> → <strong>JSON</strong> → вставить сюда.
            </div>

            {/* Modal Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #e2e8f0', paddingTop: '14px' }}>
              <button
                type="button"
                onClick={handleTestModalCookie}
                disabled={modalTesting || !modalCookieInput.trim()}
                className="btn btn-secondary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
              >
                {modalTesting ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} color="#2563eb" />}
                {modalTesting ? 'Проверяю...' : 'Проверить без сохранения'}
              </button>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="btn btn-secondary"
                  style={{ fontSize: '13px' }}
                >
                  Отмена
                </button>
                <button
                  type="button"
                  onClick={handleSaveModal}
                  disabled={modalSaving}
                  className="btn btn-primary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}
                >
                  {modalSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  {modalSaving ? 'Сохранение...' : 'Сохранить и применить'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
