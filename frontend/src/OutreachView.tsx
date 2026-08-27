import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Search,
  Mail,
  Send,
  Inbox,
  Settings as SettingsIcon,
  RefreshCw,
  Trash2,
  Square,
  CheckSquare,
  CheckCircle2,
  XCircle,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Users,
  ShieldCheck,
  MessageSquare,
  Clock,
  Layers,
  Coins,
  AlertCircle,
  Play,
  Pause,
  RotateCcw,
  Edit3,
  PenTool,
  Sparkles,
  Wand2,
  Scissors,
  SpellCheck,
  Printer,
  ShieldAlert,
  History,
  Reply,
  FileText,
  Copy,
  Plus,
  Eye,
  Tag,
  Filter,
  ArrowRight,
  ArrowLeft,
  Bold,
  Italic,
  Underline,
  FolderOpen,
  GripVertical,
  Maximize2,
  Minimize2,
  Save,
  Columns,
  Rows,
  PanelRightClose,
  FileCheck,
  X,
  Sliders,
  MailCheck,
  LayoutTemplate,
} from 'lucide-react'

export type MainTab = 'tasks' | 'inbox' | 'compose' | 'settings'
export type TaskSubTab = 'leads' | 'campaign'

export interface TaskWave {
  wave: number
  name: string
  prompt: string
  target: number
  target_count?: number
  collected: number
  lead_count?: number
  total_leads?: number
  mx_valid_leads?: number
  sent_leads?: number
  replied_leads?: number
  bounced_leads?: number
  yandex_requests?: number
  yandex_cost_rub?: number
  cost_rub?: number
  status?: string
  created_at?: string
}

interface SearchTask {
  id: string
  name: string
  prompt: string
  target_count: number
  collected_count: number
  scanned_sites: number
  queries_count: number
  status: string
  message: string
  yandex_requests: number
  yandex_cost_rub: number
  llm_cost_rub: number
  total_cost_rub: number
  cost_label: string
  waves?: TaskWave[]
  waves_count?: number
  started_at: string | null
  completed_at: string | null
  created_at: string
}

interface Lead {
  id: string
  task_id: string
  wave_index?: number
  email: string
  company_name: string
  phone: string
  website: string
  inn: string
  category: string
  activity_profile?: string
  relevance_score?: number
  city: string
  status: string
  mx_valid: boolean
  sent_count: number
  last_sent_at: string | null
  reply_received: boolean
  notes: string
  created_at: string
}

interface Campaign {
  id: string
  name: string
  subject: string
  body_text: string
  category_filter: string
  task_id_filter: string
  selected_lead_ids?: string[]
  status: string
  total_recipients: number
  sent_count: number
  failed_count: number
  delay_seconds: number
  current_index: number
  error_message: string
  created_at: string
}

interface IncomingMessage {
  id: string
  message_id: string
  sender_email: string
  sender_name: string
  lead_company?: string
  lead_email?: string
  lead_phone?: string
  lead_notes?: string
  task_id?: string
  task_name?: string
  subject: string
  body_text: string
  body_html: string
  category?: string
  is_spam?: boolean
  date_received: string
  is_read: boolean
  replied_at: string | null
  lead_id?: string | null
}

interface TaskStats {
  task: SearchTask
  total_leads: number
  new_leads: number
  sent_leads: number
  replied_leads: number
  bounced_leads?: number
  mx_valid_leads: number
  wave_counts?: Record<number, number>
  waves?: TaskWave[]
}

interface InboxCounts {
  all: number
  replies: number
  auto_replies: number
  bounces: number
  unread: number
  spam: number
}

interface LeadHistory {
  lead: Lead
  sent: any[]
  incoming: IncomingMessage[]
}

export interface EmailTemplate {
  id: string
  name: string
  subject: string
  body: string
  isDefault?: boolean
  updatedAt?: string
}

const DEFAULT_COLD_EMAIL_TEMPLATES: EmailTemplate[] = [
  {
    id: 'tender_subcontract',
    name: 'Основное: Поиск производителей под ТЗ и триал (44-ФЗ / 223-ФЗ)',
    subject: 'Поиск производителей под спецификации и ТЗ (44-ФЗ / 223-ФЗ)',
    body: 'Здравствуйте!\n\nЕсли вы участвуете в закупках или рассчитываете спецификации по 44-ФЗ и 223-ФЗ, то знаете главную сложность — оперативно найти прямых производителей оборудования и материалов без лишних наценок посредников, когда сроки подачи горят.\n\nМы создали сервис TenderLex (https://tenderlex.ru), который автоматизирует рутину снабжения:\n• ИИ разбирает файлы ТЗ любого формата (Word, Excel, PDF, сканы), извлекая ГОСТы и маркоразмеры;\n• За 2–3 минуты находит прямые контакты отделов продаж заводов РФ и официальных дилеров;\n• Автоматически формирует готовый официальный Запрос коммерческого предложения (КП);\n• Проверяет номенклатуру по реестру Минпромторга (нацрежим ПП 616/617).\n\nЧтобы вы оценили сервис на реальной задаче, мы открыли бесплатный пробный доступ: 4 полных поиска поставщиков или 4 аудита закупки (без привязки карты).\n\nПротестировать на вашем текущем ТЗ:\n👉 В веб-кабинете: https://tenderlex.ru/cabinet\n👉 Или в Telegram-боте: https://t.me/tenderlex_bot\n\nЕсли есть вопрос или сложная спецификация — просто ответьте на это письмо, поможем разобрать.\n\n--\nС уважением,\nКоманда TenderLex\ninfo@tenderlex.ru | https://tenderlex.ru\nОтписаться: ответьте словом «Стоп»',
    isDefault: true,
  },
  {
    id: 'follow_up',
    name: 'Follow-up: Напоминание тем, кто не ответил',
    subject: 'Re: Поиск производителей под спецификации и ТЗ (44-ФЗ / 223-ФЗ)',
    body: 'Здравствуйте!\n\nРанее отправляли вам информацию о сервисе TenderLex для быстрого подбора прямых заводов-производителей по ТЗ госзакупок.\n\nУдалось ли протестировать бесплатный доступ?\n\nЕсли у вас сейчас есть в работе спецификация или проект контракта — можете загрузить его в https://tenderlex.ru/cabinet или в Telegram-бот @tenderlex_bot. Сервис за пару минут соберет контакты отделов продаж заводов и проверит риски.\n\nХорошего рабочего дня!\n\n--\nTenderLex\ninfo@tenderlex.ru',
    isDefault: true,
  },
  {
    id: 'b2b_supply',
    name: 'Краткий вариант (для руководителей тендерных отделов)',
    subject: 'Контакты прямых заводов под ваши ТЗ и аудит рисков контрактов',
    body: 'Добрый день!\n\nПишу коротко и по делу: команда TenderLex запустила ИИ-сервис для участников закупок и тендерных специалистов.\n\nЧто умеет сервис:\n1. Загружаете спецификацию или проект контракта.\n2. Сервис за пару минут находит прямые контакты заводов-производителей по РФ и дилеров (email отделов сбыта, телефоны, сайты).\n3. Проверяет контракт на кабальные штрафы, нереалистичные сроки и нацрежим Минпромторга.\n\nТестовый доступ бесплатный — 4 проверки доступны сразу после входа:\nhttps://tenderlex.ru/cabinet (или бот @tenderlex_bot)\n\nБудет полезно при ближайшем расчете тендера.\n\n--\nTenderLex\ninfo@tenderlex.ru\nЕсли тема неактуальна, ответьте словом «Стоп».',
    isDefault: true,
  },
]

const COLD_EMAIL_TEMPLATES = DEFAULT_COLD_EMAIL_TEMPLATES

async function outreachFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
  const res = await fetch(path, {
    ...options,
    credentials: 'same-origin',
    headers: isFormData
      ? { ...(options.headers || {}) }
      : {
          'Content-Type': 'application/json',
          ...(options.headers || {}),
        },
  })
  if (!res.ok) {
    let errText = ''
    try {
      const rawText = await res.text()
      try {
        const j = JSON.parse(rawText)
        errText = j.detail || j.message || JSON.stringify(j)
      } catch {
        errText = rawText
      }
    } catch {
      errText = `HTTP ${res.status}`
    }
    throw new Error(errText || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function getStatusLabel(status: string): string {
  switch (status) {
    case 'running':
      return 'Отправка'
    case 'pending':
      return 'В очереди'
    case 'paused':
      return 'На паузе'
    case 'completed':
      return 'Завершена'
    case 'stopped':
    case 'cancelled':
      return 'Остановлена'
    case 'failed':
    case 'error':
      return 'Сбой'
    case 'new':
      return 'Новый'
    case 'sent':
      return 'Отправлено'
    case 'replied':
      return 'Ответил'
    case 'opened':
      return 'Открыто'
    case 'bounced':
      return 'Отклонено'
    case 'unsubscribed':
      return 'Отписан'
    case 'spam':
      return 'Спам'
    default:
      return status
  }
}

export function OutreachView() {
  // Global Module Navigation state
  const [mainTab, setMainTab] = useState<MainTab>(() => {
    try {
      const saved = localStorage.getItem('tenderlex_outreach_maintab') as MainTab
      if (['tasks', 'inbox', 'compose', 'settings'].includes(saved)) return saved
    } catch {}
    return 'tasks'
  })

  const changeMainTab = (tab: MainTab) => {
    setMainTab(tab)
    try {
      localStorage.setItem('tenderlex_outreach_maintab', tab)
    } catch {}
  }

  // Global & Task selection state
  const [tasks, setTasks] = useState<SearchTask[]>([])
  const [selectedTask, setSelectedTask] = useState<SearchTask | null>(null)
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null)
  const [taskSubTab, setTaskSubTab] = useState<TaskSubTab>(() => {
    try {
      const saved = localStorage.getItem('tenderlex_outreach_subtab') as TaskSubTab
      if (['leads', 'campaign'].includes(saved)) return saved
    } catch {}
    return 'leads'
  })

  const changeTaskSubTab = (tab: TaskSubTab) => {
    setTaskSubTab(tab)
    try {
      localStorage.setItem('tenderlex_outreach_subtab', tab)
    } catch {}
  }

  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // Templates state
  const [templates, setTemplates] = useState<EmailTemplate[]>(() => {
    try {
      const saved = localStorage.getItem('tenderlex_email_templates')
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) return parsed
      }
    } catch {}
    return DEFAULT_COLD_EMAIL_TEMPLATES
  })
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [templateModalTarget, setTemplateModalTarget] = useState<'campaign' | 'compose'>('campaign')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>(DEFAULT_COLD_EMAIL_TEMPLATES[0].id)
  const [editingTemplateName, setEditingTemplateName] = useState(DEFAULT_COLD_EMAIL_TEMPLATES[0].name)
  const [editingTemplateSubject, setEditingTemplateSubject] = useState(DEFAULT_COLD_EMAIL_TEMPLATES[0].subject)
  const [editingTemplateBody, setEditingTemplateBody] = useState(DEFAULT_COLD_EMAIL_TEMPLATES[0].body)
  const [templateSearch, setTemplateSearch] = useState('')
  const [isCreatingNewTemplate, setIsCreatingNewTemplate] = useState(false)

  // New Search Task Modal / Form state
  const [showNewTaskModal, setShowNewTaskModal] = useState(false)
  const [taskName, setTaskName] = useState('')
  const [searchPrompt, setSearchPrompt] = useState('')
  const [targetCount, setTargetCount] = useState<number>(500)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [searchStatus, setSearchStatus] = useState<any>(null)
  const [deleteTaskId, setDeleteTaskId] = useState<string | null>(null)
  const [deleteWithLeads, setDeleteWithLeads] = useState(false)

  // In-Task Search and Dobor state
  const [taskSearchPrompt, setTaskSearchPrompt] = useState('')
  const [taskDoborCount, setTaskDoborCount] = useState<number>(500)
  const [selectedWave, setSelectedWave] = useState<number | null>(null)
  const [extending, setExtending] = useState(false)
  const [isDoborCollapsed, setIsDoborCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('tenderlex_dobor_collapsed') === 'true'
    } catch {
      return false
    }
  })

  const toggleDoborCollapsed = () => {
    setIsDoborCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem('tenderlex_dobor_collapsed', String(next))
      } catch {}
      return next
    })
  }

  // Lead Count Presets state (shared across new task creation and in-task dobor)
  const [leadCountPresets, setLeadCountPresets] = useState<number[]>(() => {
    try {
      const saved = localStorage.getItem('tenderlex_lead_count_presets')
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) {
          const nums = parsed.map((n) => Number(n)).filter((n) => !isNaN(n) && n > 0).sort((a, b) => a - b)
          if (nums.length > 0) return nums
        }
      }
    } catch {}
    return [500, 1000, 2000, 5000]
  })
  const [isEditingPresets, setIsEditingPresets] = useState(false)
  const [newPresetInput, setNewPresetInput] = useState('')

  const handleSavePresets = (presets: number[]) => {
    const sorted = Array.from(new Set(presets)).filter((n) => n > 0).sort((a, b) => a - b)
    setLeadCountPresets(sorted)
    try {
      localStorage.setItem('tenderlex_lead_count_presets', JSON.stringify(sorted))
    } catch {}
  }

  const handleAddPreset = () => {
    const val = parseInt(newPresetInput.trim(), 10)
    if (!isNaN(val) && val > 0 && val <= 50000) {
      if (!leadCountPresets.includes(val)) {
        handleSavePresets([...leadCountPresets, val])
      }
      setNewPresetInput('')
    }
  }

  const handleRemovePreset = (val: number) => {
    const filtered = leadCountPresets.filter((p) => p !== val)
    handleSavePresets(filtered.length > 0 ? filtered : [500])
  }

  // Leads CRM state (inside selected task)
  const [leads, setLeads] = useState<Lead[]>([])
  const [leadTotal, setLeadTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [searchFilter, setSearchFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([])
  const [selectAllAcrossPages, setSelectAllAcrossPages] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  // History modal
  const [historyLead, setHistoryLead] = useState<LeadHistory | null>(null)

  // CRM Picker Modal for Compose tab
  const [showCrmPickerModal, setShowCrmPickerModal] = useState(false)
  const [crmPickerSearch, setCrmPickerSearch] = useState('')
  const [crmPickerTaskFilter, setCrmPickerTaskFilter] = useState('')
  const [crmPickerLeads, setCrmPickerLeads] = useState<Lead[]>([])
  const [crmPickerSelected, setCrmPickerSelected] = useState<string[]>([])
  const [crmPickerLoading, setCrmPickerLoading] = useState(false)

  // Campaign state (inside selected task)
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [campSubject, setCampSubject] = useState(DEFAULT_COLD_EMAIL_TEMPLATES[0].subject)
  const [campBody, setCampBody] = useState(DEFAULT_COLD_EMAIL_TEMPLATES[0].body)
  const [campAudienceType, setCampAudienceType] = useState<'new' | 'unanswered' | 'all' | 'selected'>('new')
  const [campDelay, setCampDelay] = useState<number>(3.0)
  const [campTone, setCampTone] = useState('professional')
  const [campAiGenerating, setCampAiGenerating] = useState(false)
  const [testEmail, setTestEmail] = useState('')
  const [sendingTest, setSendingTest] = useState(false)

  // Persistent textarea heights with localStorage
  const campBodyRef = useRef<HTMLTextAreaElement>(null)
  const [campBodyHeight, setCampBodyHeight] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('tenderlex_outreach_camp_body_height')
      if (saved) {
        const val = parseInt(saved, 10)
        if (val >= 100 && val <= 2000) return val
      }
    } catch {}
    return 280
  })

  const composeBodyRef = useRef<HTMLTextAreaElement>(null)
  const [composeBodyHeight, setComposeBodyHeight] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('tenderlex_outreach_compose_body_height')
      if (saved) {
        const val = parseInt(saved, 10)
        if (val >= 100 && val <= 2000) return val
      }
    } catch {}
    return 280
  })

  useEffect(() => {
    const el = campBodyRef.current
    if (!el) return
    const saveHeight = () => {
      const h = el.offsetHeight || el.clientHeight
      if (h >= 100) {
        try {
          localStorage.setItem('tenderlex_outreach_camp_body_height', String(h))
        } catch {}
      }
    }
    el.addEventListener('mouseup', saveHeight)
    let ro: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const h = Math.round(entry.contentRect.height + 24)
          if (h >= 100) {
            try {
              localStorage.setItem('tenderlex_outreach_camp_body_height', String(h))
            } catch {}
          }
        }
      })
      ro.observe(el)
    }
    return () => {
      el.removeEventListener('mouseup', saveHeight)
      if (ro) ro.disconnect()
    }
  }, [selectedTask, taskSubTab])

  useEffect(() => {
    const el = composeBodyRef.current
    if (!el) return
    const saveHeight = () => {
      const h = el.offsetHeight || el.clientHeight
      if (h >= 100) {
        try {
          localStorage.setItem('tenderlex_outreach_compose_body_height', String(h))
        } catch {}
      }
    }
    el.addEventListener('mouseup', saveHeight)
    let ro: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const h = Math.round(entry.contentRect.height)
          if (h >= 100) {
            try {
              localStorage.setItem('tenderlex_outreach_compose_body_height', String(h))
            } catch {}
          }
        }
      })
      ro.observe(el)
    }
    return () => {
      el.removeEventListener('mouseup', saveHeight)
      if (ro) ro.disconnect()
    }
  }, [mainTab])

  // Compose state (standalone tab)
  const [composeRecipients, setComposeRecipients] = useState<string[]>([])
  const [composeRecipientInput, setComposeRecipientInput] = useState('')
  const [composeSubject, setComposeSubject] = useState('Предложение о сотрудничестве')
  const [composeBody, setComposeBody] = useState('')
  const [composeTone, setComposeTone] = useState('professional')
  const [aiPrompt, setAiPrompt] = useState('')
  const [aiGenerating, setAiGenerating] = useState(false)
  const [sendingDirect, setSendingDirect] = useState(false)

  // Inbox state (standalone tab)
  const [inboxTaskFilter, setInboxTaskFilter] = useState<string>('')
  const [inboxMessages, setInboxMessages] = useState<IncomingMessage[]>([])
  const [inboxFilter, setInboxFilter] = useState<'all' | 'replies' | 'auto_replies' | 'bounces' | 'unread' | 'spam'>('all')
  const [inboxCounts, setInboxCounts] = useState<InboxCounts>({
    all: 0,
    replies: 0,
    auto_replies: 0,
    bounces: 0,
    unread: 0,
    spam: 0,
  })
  const [inboxSearch, setInboxSearch] = useState('')
  const [inboxLimit, setInboxLimit] = useState(50)
  const [inboxTotal, setInboxTotal] = useState(0)
  const [loadingMoreInbox, setLoadingMoreInbox] = useState(false)
  const [syncingInbox, setSyncingInbox] = useState(false)
  const [selectedMsg, setSelectedMsg] = useState<IncomingMessage | null>(null)
  const [replyText, setReplyText] = useState('')
  const [sendingReply, setSendingReply] = useState(false)
  const [aiReplyGenerating, setAiReplyGenerating] = useState(false)
  const lastAutoSyncTimeRef = useRef<number>(0)
  const inboxFilterRef = useRef(inboxFilter)
  inboxFilterRef.current = inboxFilter
  const inboxSearchRef = useRef(inboxSearch)
  inboxSearchRef.current = inboxSearch
  const inboxLimitRef = useRef(inboxLimit)
  inboxLimitRef.current = inboxLimit
  const inboxTaskFilterRef = useRef(inboxTaskFilter)
  inboxTaskFilterRef.current = inboxTaskFilter

  // Settings state
  const [settings, setSettings] = useState<any>({
    from_name: 'TenderLex',
    from_email: 'info@tenderlex.ru',
    reply_to: 'info@tenderlex.ru',
    smtp_host: 'smtp.jino.ru',
    smtp_port: 465,
    smtp_user: 'info@tenderlex.ru',
    smtp_password_set: false,
    smtp_use_ssl: true,
    smtp_use_tls: false,
    imap_host: 'mail.jino.ru',
    imap_port: 993,
    imap_user: 'info@tenderlex.ru',
    imap_password_set: false,
    imap_use_ssl: true,
    delay_seconds: 2.0,
    daily_limit: 500,
  })
  const [smtpPassword, setSmtpPassword] = useState('')
  const [imapPassword, setImapPassword] = useState('')

  // Spam Rules State
  const [spamRules, setSpamRules] = useState<Array<{ type: string; value: string }>>([])
  const [newSpamRuleType, setNewSpamRuleType] = useState<string>('domain')
  const [newSpamRuleVal, setNewSpamRuleVal] = useState<string>('')
  const [savingSpamRule, setSavingSpamRule] = useState<boolean>(false)

  // Notifications helper
  const showSuccess = (msg: string) => {
    setMessage(msg)
    setError('')
    setTimeout(() => setMessage(''), 5000)
  }

  const showError = (err: string) => {
    setError(err)
    setMessage('')
    setTimeout(() => setError(''), 7000)
  }

  // Fetch stats for the selected task
  const fetchTaskStats = useCallback(async (taskId: string) => {
    try {
      const data = await outreachFetch<TaskStats>(`/api/outreach/tasks/${taskId}/stats`)
      setTaskStats(data)
    } catch (e: any) {
      console.error('fetchTaskStats error:', e)
    }
  }, [])

  // Fetch leads for the selected task
  const fetchLeads = useCallback(
    async (taskId: string, p = 1, search = '', status = '', wave?: number | null) => {
      setLoading(true)
      try {
        const activeWave = wave !== undefined ? wave : selectedWave
        const params = new URLSearchParams({
          page: String(p),
          page_size: '50',
          search,
          status,
          task_id: taskId,
        })
        if (activeWave && activeWave > 0) {
          params.set('wave', String(activeWave))
        }
        const data = await outreachFetch<{ items: Lead[]; total: number; page: number }>(
          `/api/outreach/leads?${params.toString()}`
        )
        setLeads(data.items || [])
        setLeadTotal(data.total || 0)
        setPage(data.page || 1)
      } catch (e: any) {
        showError(e.message)
      } finally {
        setLoading(false)
      }
    },
    [selectedWave]
  )

  // Fetch campaigns for the selected task
  const fetchCampaigns = useCallback(async (taskId: string) => {
    try {
      const data = await outreachFetch<{ items: Campaign[] }>('/api/outreach/campaigns')
      const filtered = (data.items || []).filter((c) => !c.task_id_filter || c.task_id_filter === taskId)
      setCampaigns(filtered)
    } catch {
      // ignore
    }
  }, [])

  // Fetch inbox (all or for a specific task, with pagination limit)
  const fetchInbox = useCallback(
    async (
      taskId?: string | null,
      filter?: 'all' | 'replies' | 'auto_replies' | 'bounces' | 'unread' | 'spam',
      search?: string,
      limit?: number,
      isLoadMore = false
    ) => {
      const activeFilter = filter ?? inboxFilterRef.current
      const activeSearch = search ?? inboxSearchRef.current
      const activeLimit = limit ?? inboxLimitRef.current
      try {
        const categoryParam =
          activeFilter === 'bounces'
            ? 'bounces'
            : activeFilter === 'replies'
            ? 'replies'
            : activeFilter === 'auto_replies'
            ? 'auto_replies'
            : ''

        const params = new URLSearchParams({
          limit: String(activeLimit || 50),
          unread_only: String(activeFilter === 'unread'),
          is_spam: String(activeFilter === 'spam'),
          category: categoryParam,
          search: activeSearch,
          task_id: taskId || '',
        })
        const data = await outreachFetch<{ items: IncomingMessage[]; total?: number; counts?: InboxCounts }>(
          `/api/outreach/inbox?${params.toString()}`
        )
        const items = data.items || []
        setInboxMessages(items)
        setInboxTotal(typeof data.total === 'number' ? data.total : items.length)
        if (data.counts) {
          setInboxCounts(data.counts)
        }
        if (items.length && (!selectedMsg || (!isLoadMore && !items.some((m) => m.id === selectedMsg.id)))) {
          if (!isLoadMore) {
            setSelectedMsg(items[0])
          }
        }
      } catch {
        // ignore
      }
    },
    [selectedMsg]
  )

  // Load more inbox messages (increment limit by 50)
  const handleLoadMoreInbox = async () => {
    const nextLimit = inboxLimit + 50
    setInboxLimit(nextLimit)
    setLoadingMoreInbox(true)
    try {
      await fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, nextLimit, true)
    } finally {
      setLoadingMoreInbox(false)
    }
  }

  // Silent auto-sync for inbox
  const triggerAutoSync = useCallback(
    async (taskId?: string) => {
      const now = Date.now()
      if (now - lastAutoSyncTimeRef.current < 15000) return
      lastAutoSyncTimeRef.current = now
      setSyncingInbox(true)
      try {
        await outreachFetch<any>('/api/outreach/inbox/sync', { method: 'POST' })
        const targetTaskId = taskId !== undefined ? taskId : (inboxTaskFilterRef.current || null)
        fetchInbox(targetTaskId, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
        if (selectedTask) {
          fetchTaskStats(selectedTask.id)
        }
      } catch {
        // silent background failure
      } finally {
        setSyncingInbox(false)
      }
    },
    [selectedTask, fetchInbox, fetchTaskStats]
  )

  // Fetch settings & spam rules
  const fetchSettings = useCallback(async () => {
    try {
      const data = await outreachFetch<any>('/api/outreach/settings')
      setSettings(data)
      if (data.spam_rules) {
        setSpamRules(data.spam_rules)
      }
    } catch {
      // ignore
    }
  }, [])

  // Helper to extract initial prompt for task dobor
  const getTaskInitialPrompt = (t: SearchTask | null): string => {
    if (!t) return ''
    if (t.waves && t.waves.length > 0) {
      const lastWave = t.waves[t.waves.length - 1]
      if (lastWave && lastWave.prompt) return lastWave.prompt
    }
    return t.prompt || ''
  }

  // Fetch all tasks and restore selected task on page refresh
  const fetchTasks = useCallback(async () => {
    try {
      const data = await outreachFetch<{ items: SearchTask[] }>('/api/outreach/tasks')
      const items = data.items || []
      setTasks(items)

      // Restore previously opened task on page refresh
      const savedTaskId = localStorage.getItem('tenderlex_outreach_selected_task_id')
      if (savedTaskId && items.length > 0) {
        const found = items.find((t) => t.id === savedTaskId)
        if (found) {
          setSelectedTask(found)
          const savedSubTab = (localStorage.getItem('tenderlex_outreach_subtab') || 'leads') as TaskSubTab
          setTaskSubTab(savedSubTab)
          setTaskSearchPrompt(getTaskInitialPrompt(found))
          fetchTaskStats(found.id)
          fetchLeads(found.id, 1, '', '')
          fetchCampaigns(found.id)
        }
      }

      const running = items.find((t) => t.status === 'running')
      if (running) {
        setActiveTaskId(running.id)
        setSearchStatus(running)
      } else if (activeTaskId) {
        const current = items.find((t) => t.id === activeTaskId)
        if (current) setSearchStatus(current)
      }
    } catch (e: any) {
      console.error('fetchTasks error:', e)
      showError(`Ошибка загрузки задач: ${e.message}`)
    }
  }, [activeTaskId, fetchTaskStats, fetchLeads, fetchCampaigns])

  // Initial load
  useEffect(() => {
    fetchTasks()
    fetchSettings()
    fetchInbox(null)
  }, [])

  // When a task is selected, load its workspace data
  const handleSelectTask = useCallback((task: SearchTask, customSubTab?: TaskSubTab) => {
    setSelectedTask(task)
    const targetTab = customSubTab || taskSubTab || 'leads'
    setTaskSubTab(targetTab)
    try {
      localStorage.setItem('tenderlex_outreach_selected_task_id', task.id)
      localStorage.setItem('tenderlex_outreach_subtab', targetTab)
    } catch {}
    setSelectedLeadIds([])
    setSearchFilter('')
    setStatusFilter('')
    setSelectedWave(null)
    setTaskSearchPrompt(getTaskInitialPrompt(task))
    setTaskDoborCount(500)
    fetchTaskStats(task.id)
    fetchLeads(task.id, 1, '', '', null)
    fetchCampaigns(task.id)
  }, [fetchTaskStats, fetchLeads, fetchCampaigns, taskSubTab])

  // Keep taskSearchPrompt in sync when selectedTask changes or updates
  useEffect(() => {
    if (selectedTask) {
      setTaskSearchPrompt((prev) => prev || getTaskInitialPrompt(selectedTask))
    }
  }, [selectedTask?.id])

  // Polling for active search task (only when actively running)
  useEffect(() => {
    if (!activeTaskId) {
      setSearchStatus(null)
      return
    }
    const interval = setInterval(async () => {
      try {
        const data = await outreachFetch<any>(`/api/outreach/search/status/${activeTaskId}`)
        if (!data || data.status !== 'running') {
          setActiveTaskId(null)
          setSearchStatus(null)
          fetchTasks()
          if (selectedTask && selectedTask.id === activeTaskId) {
            fetchTaskStats(selectedTask.id)
            fetchLeads(selectedTask.id, 1, searchFilter, statusFilter, selectedWave)
          }
        } else {
          setSearchStatus(data)
        }
      } catch {
        setActiveTaskId(null)
        setSearchStatus(null)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [activeTaskId, selectedTask, searchFilter, statusFilter, selectedWave, fetchTasks, fetchTaskStats, fetchLeads])

  // Realtime polling for active campaigns and task stats
  useEffect(() => {
    if (!selectedTask || mainTab !== 'tasks') return
    const isSearchRunning = selectedTask.status === 'running' || (searchStatus && searchStatus.status === 'running' && searchStatus.id === selectedTask.id)
    const isCampaignRunning = campaigns.some((c) => c.status === 'running' || c.status === 'pending')
    const intervalMs = (isSearchRunning || isCampaignRunning) ? 2000 : (taskSubTab === 'campaign' ? 3500 : 6000)

    const interval = setInterval(async () => {
      try {
        const stats = await outreachFetch<TaskStats>(`/api/outreach/tasks/${selectedTask.id}/stats`)
        setTaskStats(stats)
        if (stats.task) {
          setSelectedTask((prev) => (prev && prev.id === stats.task.id ? { ...prev, ...stats.task } : stats.task))
          if (stats.task.status === 'running') {
            if (!activeTaskId) {
              setActiveTaskId(stats.task.id)
            }
          } else if (searchStatus && searchStatus.id === selectedTask.id && stats.task.status !== 'running') {
            setSearchStatus(null)
            fetchLeads(selectedTask.id, 1, searchFilter, statusFilter, selectedWave)
          }
        }

        const campData = await outreachFetch<{ items: Campaign[] }>('/api/outreach/campaigns')
        const filtered = (campData.items || []).filter((c) => !c.task_id_filter || c.task_id_filter === selectedTask.id)
        setCampaigns(filtered)
      } catch {
        // ignore network error
      }
    }, intervalMs)

    return () => clearInterval(interval)
  }, [selectedTask, campaigns, taskSubTab, mainTab, searchStatus, searchFilter, statusFilter, selectedWave, fetchLeads])

  // Trigger auto-sync on entering Inbox tab
  useEffect(() => {
    if (mainTab === 'inbox') {
      triggerAutoSync(inboxTaskFilter || undefined)
    }
  }, [mainTab, inboxTaskFilter, triggerAutoSync])

  // Periodic background auto-sync every 30 seconds when in inbox tab
  useEffect(() => {
    if (mainTab !== 'inbox') return
    const interval = setInterval(() => {
      triggerAutoSync(inboxTaskFilter || undefined)
    }, 30000)
    return () => clearInterval(interval)
  }, [mainTab, inboxTaskFilter, triggerAutoSync])

  // Template CRUD Handlers
  const saveTemplates = (newTpls: EmailTemplate[]) => {
    setTemplates(newTpls)
    try {
      localStorage.setItem('tenderlex_email_templates', JSON.stringify(newTpls))
    } catch {}
  }

  const handleOpenTemplateModal = (target: 'campaign' | 'compose', tplId?: string) => {
    setTemplateModalTarget(target)
    const targetId = tplId || (templates.length > 0 ? templates[0].id : '')
    const tpl = templates.find((t) => t.id === targetId) || templates[0]
    if (tpl) {
      setSelectedTemplateId(tpl.id)
      setEditingTemplateName(tpl.name)
      setEditingTemplateSubject(tpl.subject)
      setEditingTemplateBody(tpl.body)
      setIsCreatingNewTemplate(false)
    } else {
      setIsCreatingNewTemplate(true)
      setSelectedTemplateId('')
      setEditingTemplateName('Новый шаблон')
      setEditingTemplateSubject('')
      setEditingTemplateBody('')
    }
    setShowTemplateModal(true)
  }

  const handleSelectTemplateInList = (tpl: EmailTemplate) => {
    setSelectedTemplateId(tpl.id)
    setEditingTemplateName(tpl.name)
    setEditingTemplateSubject(tpl.subject)
    setEditingTemplateBody(tpl.body)
    setIsCreatingNewTemplate(false)
  }

  const handleStartNewTemplate = () => {
    setIsCreatingNewTemplate(true)
    setSelectedTemplateId('')
    setEditingTemplateName('Новый шаблон')
    setEditingTemplateSubject(campSubject || '')
    setEditingTemplateBody(campBody || '')
  }

  const handleSaveTemplate = () => {
    if (!editingTemplateName.trim() || !editingTemplateSubject.trim() || !editingTemplateBody.trim()) {
      showError('Заполните название, тему и текст шаблона')
      return
    }

    if (isCreatingNewTemplate) {
      const newTpl: EmailTemplate = {
        id: 'tpl_' + Date.now(),
        name: editingTemplateName.trim(),
        subject: editingTemplateSubject.trim(),
        body: editingTemplateBody.trim(),
        isDefault: false,
        updatedAt: new Date().toISOString(),
      }
      const updated = [newTpl, ...templates]
      saveTemplates(updated)
      setSelectedTemplateId(newTpl.id)
      setIsCreatingNewTemplate(false)
      showSuccess(`Шаблон «${newTpl.name}» успешно создан!`)
    } else {
      const updated = templates.map((t) => {
        if (t.id === selectedTemplateId) {
          return {
            ...t,
            name: editingTemplateName.trim(),
            subject: editingTemplateSubject.trim(),
            body: editingTemplateBody.trim(),
            updatedAt: new Date().toISOString(),
          }
        }
        return t
      })
      saveTemplates(updated)
      showSuccess('Шаблон успешно обновлен!')
    }
  }

  const handleDeleteTemplate = (tplId: string) => {
    if (templates.length <= 1) {
      showError('Нельзя удалить последний оставшийся шаблон')
      return
    }
    const tpl = templates.find((t) => t.id === tplId)
    if (!window.confirm(`Удалить шаблон «${tpl?.name || tplId}»?`)) return

    const updated = templates.filter((t) => t.id !== tplId)
    saveTemplates(updated)
    if (selectedTemplateId === tplId) {
      const first = updated[0]
      setSelectedTemplateId(first.id)
      setEditingTemplateName(first.name)
      setEditingTemplateSubject(first.subject)
      setEditingTemplateBody(first.body)
      setIsCreatingNewTemplate(false)
    }
    showSuccess('Шаблон удален')
  }

  const handleDuplicateTemplate = (tpl: EmailTemplate) => {
    const copy: EmailTemplate = {
      id: 'tpl_' + Date.now(),
      name: `${tpl.name} (копия)`,
      subject: tpl.subject,
      body: tpl.body,
      isDefault: false,
      updatedAt: new Date().toISOString(),
    }
    const updated = [copy, ...templates]
    saveTemplates(updated)
    setSelectedTemplateId(copy.id)
    setEditingTemplateName(copy.name)
    setEditingTemplateSubject(copy.subject)
    setEditingTemplateBody(copy.body)
    setIsCreatingNewTemplate(false)
    showSuccess('Создана копия шаблона')
  }

  const handleResetDefaultTemplates = () => {
    if (!window.confirm('Сбросить шаблоны к исходным по умолчанию? Все пользовательские изменения будут заменены.')) return
    saveTemplates(DEFAULT_COLD_EMAIL_TEMPLATES)
    const first = DEFAULT_COLD_EMAIL_TEMPLATES[0]
    setSelectedTemplateId(first.id)
    setEditingTemplateName(first.name)
    setEditingTemplateSubject(first.subject)
    setEditingTemplateBody(first.body)
    setIsCreatingNewTemplate(false)
    showSuccess('Шаблоны сброшены к стандартным')
  }

  const handleApplyTemplate = (tpl: EmailTemplate, target: 'campaign' | 'compose') => {
    if (target === 'campaign') {
      setCampSubject(tpl.subject)
      setCampBody(tpl.body)
      if (tpl.id === 'follow_up') {
        setCampAudienceType('unanswered')
      }
    } else {
      setComposeSubject(tpl.subject)
      setComposeBody(tpl.body)
    }
    setShowTemplateModal(false)
    showSuccess(`Применен шаблон «${tpl.name}»`)
  }

  const handleSaveCurrentAsTemplate = (target: 'campaign' | 'compose') => {
    const subj = target === 'campaign' ? campSubject : composeSubject
    const body = target === 'campaign' ? campBody : composeBody
    if (!subj.trim() || !body.trim()) {
      showError('Заполните тему и текст письма перед сохранением шаблона')
      return
    }
    const namePrompt = window.prompt('Введите название для нового шаблона:', subj.slice(0, 40) || 'Пользовательский шаблон')
    if (!namePrompt || !namePrompt.trim()) return

    const newTpl: EmailTemplate = {
      id: 'tpl_' + Date.now(),
      name: namePrompt.trim(),
      subject: subj.trim(),
      body: body.trim(),
      isDefault: false,
      updatedAt: new Date().toISOString(),
    }
    const updated = [newTpl, ...templates]
    saveTemplates(updated)
    showSuccess(`Шаблон «${newTpl.name}» сохранен в библиотеку!`)
  }

  // Start search task
  const handleStartSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchPrompt.trim()) {
      showError('Введите описание целевой аудитории для поиска')
      return
    }
    setLoading(true)
    try {
      const data = await outreachFetch<any>('/api/outreach/search/start', {
        method: 'POST',
        body: JSON.stringify({
          name: taskName.trim(),
          prompt: searchPrompt.trim(),
          target_count: targetCount,
        }),
      })
      setActiveTaskId(data.task_id)
      setSearchStatus({
        id: data.task_id,
        name: taskName.trim() || 'Поиск компаний',
        prompt: searchPrompt.trim(),
        status: 'running',
        collected: 0,
        scanned_sites: 0,
        target_count: targetCount,
        message: 'Инициализация и запуск...',
        total_cost_rub: 0,
      })
      setShowNewTaskModal(false)
      setTaskName('')
      setSearchPrompt('')
      showSuccess('Задача поиска запущена! Сбор выполняется в фоновом режиме.')
      fetchTasks()
    } catch (e: any) {
      showError(`Ошибка запуска: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  // Cancel search
  const handleCancelSearch = async (id: string) => {
    try {
      await outreachFetch(`/api/outreach/search/cancel/${id}`, { method: 'POST' })
      showSuccess('Команда на остановку отправлена')
      fetchTasks()
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Pause search
  const handlePauseSearch = async (id: string) => {
    try {
      await outreachFetch(`/api/outreach/search/pause/${id}`, { method: 'POST' })
      showSuccess('Сбор поставлен на паузу. Найденные сайты сохранены на сервере.')
      fetchTasks()
      fetchTaskStats(id)
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Resume search
  const handleResumeSearch = async (id: string) => {
    try {
      await outreachFetch(`/api/outreach/search/resume/${id}`, { method: 'POST' })
      showSuccess('Сбор возобновлен. Обход продолжается с сохраненной позиции (0 ₽ в Яндекс).')
      setActiveTaskId(id)
      setSearchStatus({
        status: 'running',
        id: id,
        name: selectedTask?.name || '',
        message: 'Возобновление сбора контактов...',
        target: selectedTask?.target_count || 0,
        collected: selectedTask?.collected_count || 0,
        yandex_requests: selectedTask?.yandex_requests || 0,
        yandex_cost_rub: selectedTask?.yandex_cost_rub || 0,
        llm_cost_rub: 0,
        total_cost_rub: selectedTask?.total_cost_rub || 0,
      } as any)
      fetchTasks()
      fetchTaskStats(id)
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Delete search task
  const handleDeleteTask = async () => {
    if (!deleteTaskId) return
    try {
      await outreachFetch(`/api/outreach/tasks/${deleteTaskId}?delete_leads=${deleteWithLeads}`, { method: 'DELETE' })
      showSuccess('Задача удалена')
      if (selectedTask?.id === deleteTaskId) {
        setSelectedTask(null)
      }
      setDeleteTaskId(null)
      fetchTasks()
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Extend / Replenish search task from in-task bar
  const handleExtendTaskWithParams = async (count: number, customPrompt?: string) => {
    if (!selectedTask) return
    setExtending(true)
    try {
      const p = customPrompt !== undefined ? customPrompt : taskSearchPrompt
      const data = await outreachFetch<any>(`/api/outreach/tasks/${selectedTask.id}/extend`, {
        method: 'POST',
        body: JSON.stringify({
          extra_count: count,
          additional_prompt: p.trim() !== selectedTask.prompt.trim() ? p.trim() : '',
        }),
      })
      setActiveTaskId(selectedTask.id)
      setSearchStatus({
        id: selectedTask.id,
        name: selectedTask.name,
        prompt: p.trim() || selectedTask.prompt,
        status: 'running',
        collected: selectedTask.collected_count,
        scanned_sites: selectedTask.scanned_sites,
        target_count: data.target_count || (selectedTask.collected_count + count),
        message: `Запуск добора (+${count} контактов)...`,
        total_cost_rub: selectedTask.total_cost_rub,
      })
      showSuccess(`Запущен добор +${count} контактов!`)
      fetchTasks()
      if (selectedTask) {
        fetchTaskStats(selectedTask.id)
      }
    } catch (e: any) {
      showError(`Ошибка запуска добора: ${e.message}`)
    } finally {
      setExtending(false)
    }
  }

  // Select all leads on page or across all pages
  const handleSelectAllLeads = () => {
    if (selectedLeadIds.length === leads.length && leads.length > 0) {
      setSelectedLeadIds([])
      setSelectAllAcrossPages(false)
    } else {
      setSelectedLeadIds(leads.map((l) => l.id))
      setSelectAllAcrossPages(false)
    }
  }

  // Toggle single lead selection
  const handleToggleLead = (id: string) => {
    setSelectAllAcrossPages(false)
    setSelectedLeadIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  // Send selected leads to campaign inside task
  const handleSendSelectedToCampaign = () => {
    if (!selectedLeadIds.length && !selectAllAcrossPages) {
      showError('Выберите хотя бы один контакт')
      return
    }
    if (selectAllAcrossPages) {
      setCampAudienceType('all')
      showSuccess(`Выбраны ВСЕ ${leadTotal} контактов задачи для рассылки`)
    } else {
      setCampAudienceType('selected')
      showSuccess(`Выбрано ${selectedLeadIds.length} контактов для рассылки`)
    }
    changeTaskSubTab('campaign')
  }

  // Send selected leads to compose tab
  const handleSendSelectedToCompose = async () => {
    if (!selectedLeadIds.length && !selectAllAcrossPages) {
      showError('Выберите хотя бы один контакт')
      return
    }
    if (selectAllAcrossPages && selectedTask) {
      try {
        const data = await outreachFetch<{ items: Lead[] }>(
          `/api/outreach/leads?task_id=${selectedTask.id}&page=1&page_size=5000`
        )
        const allEmails = (data.items || []).map((l) => l.email).filter(Boolean)
        setComposeRecipients(allEmails)
        changeMainTab('compose')
        showSuccess(`Добавлено ${allEmails.length} получателей во вкладку "Написать письмо"`)
      } catch (e: any) {
        showError(e.message)
      }
    } else {
      const selectedEmails = leads.filter((l) => selectedLeadIds.includes(l.id)).map((l) => l.email)
      setComposeRecipients(selectedEmails)
      changeMainTab('compose')
      showSuccess(`Добавлено ${selectedEmails.length} получателей во вкладку "Написать письмо"`)
    }
  }

  // Open CRM Picker Modal directly in Compose Tab
  const handleOpenCrmPicker = async (taskIdFilter?: string | React.MouseEvent) => {
    setShowCrmPickerModal(true)
    setCrmPickerLoading(true)
    const targetTaskId = typeof taskIdFilter === 'string' ? taskIdFilter : (selectedTask?.id || '')
    setCrmPickerTaskFilter(targetTaskId)
    try {
      const url = targetTaskId
        ? `/api/outreach/leads?task_id=${targetTaskId}&page=1&page_size=5000`
        : `/api/outreach/leads?page=1&page_size=5000`
      const data = await outreachFetch<{ items: Lead[] }>(url)
      setCrmPickerLeads(data.items || [])
      setCrmPickerSelected([])
    } catch (e: any) {
      showError(e.message)
    } finally {
      setCrmPickerLoading(false)
    }
  }

  // Delete selected leads
  const handleDeleteSelectedLeads = async () => {
    if ((!selectedLeadIds.length && !selectAllAcrossPages) || !selectedTask) return
    const count = selectAllAcrossPages ? leadTotal : selectedLeadIds.length
    if (!confirm(`Удалить выбранные контакты (${count} шт.)?`)) return
    try {
      if (selectAllAcrossPages) {
        await outreachFetch('/api/outreach/leads', {
          method: 'DELETE',
          body: JSON.stringify({ all_leads: true, task_id: selectedTask.id, status_filter: statusFilter }),
        })
      } else {
        await outreachFetch('/api/outreach/leads', {
          method: 'DELETE',
          body: JSON.stringify({ lead_ids: selectedLeadIds }),
        })
      }
      setSelectedLeadIds([])
      setSelectAllAcrossPages(false)
      showSuccess('Контакты успешно удалены')
      fetchLeads(selectedTask.id, page, searchFilter, statusFilter)
      fetchTaskStats(selectedTask.id)
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Open Lead History
  const handleOpenLeadHistory = async (lead: Lead) => {
    try {
      const data = await outreachFetch<LeadHistory>(`/api/outreach/leads/${lead.id}/history`)
      setHistoryLead(data)
    } catch (e: any) {
      showError(`Ошибка загрузки истории: ${e.message}`)
    }
  }

  // Refresh current task stats, leads, campaigns, inbox
  const handleRefreshTaskData = async () => {
    if (!selectedTask) return
    setRefreshing(true)
    try {
      await Promise.all([
        fetchTaskStats(selectedTask.id),
        fetchLeads(selectedTask.id, page, searchFilter, statusFilter),
        fetchCampaigns(selectedTask.id),
        fetchInbox(selectedTask.id),
      ])
      showSuccess('Данные задачи обновлены')
    } catch (e: any) {
      showError(`Ошибка обновления: ${e.message}`)
    } finally {
      setRefreshing(false)
    }
  }

  // Create Campaign for the selected task
  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedTask) return
    if (!campSubject.trim() || !campBody.trim()) {
      showError('Укажите тему и текст рассылки')
      return
    }
    setLoading(true)
    try {
      const payload: any = {
        name: `Рассылка по задаче «${selectedTask.name}»`,
        subject: campSubject.trim(),
        body_text: campBody.trim(),
        task_id_filter: selectedTask.id,
        audience_type: campAudienceType,
        delay_seconds: campDelay,
      }
      if (campAudienceType === 'selected' && !selectAllAcrossPages) {
        payload.lead_ids = selectedLeadIds
      }

      await outreachFetch('/api/outreach/campaigns', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      showSuccess('Рассылка по контактам задачи запущена в фоновом режиме!')
      fetchCampaigns(selectedTask.id)
      fetchTaskStats(selectedTask.id)
    } catch (e: any) {
      showError(`Ошибка создания рассылки: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  // Send Direct Email (from Compose tab)
  const handleSendDirect = async () => {
    if (!composeRecipients.length) {
      showError('Укажите хотя бы одного получателя в поле "Кому"')
      return
    }
    if (!composeSubject.trim() || !composeBody.trim()) {
      showError('Заполните тему и текст письма')
      return
    }
    setSendingDirect(true)
    try {
      const res = await outreachFetch<any>('/api/outreach/send-direct', {
        method: 'POST',
        body: JSON.stringify({
          recipients: composeRecipients,
          subject: composeSubject.trim(),
          body_text: composeBody.trim(),
        }),
      })
      showSuccess(`Письмо успешно отправлено (${res.sent_count} адресатам)!`)
      setComposeRecipients([])
      if (selectedTask) fetchTaskStats(selectedTask.id)
    } catch (e: any) {
      showError(`Ошибка отправки: ${e.message}`)
    } finally {
      setSendingDirect(false)
    }
  }

  // Test send email
  const handleTestSend = async () => {
    if (!testEmail.trim() || !testEmail.includes('@')) {
      showError('Укажите корректный email для теста')
      return
    }
    setSendingTest(true)
    try {
      await outreachFetch('/api/outreach/test-send', {
        method: 'POST',
        body: JSON.stringify({
          to_email: testEmail.trim(),
          subject: `[ТЕСТ] ${campSubject}`,
          body_text: campBody,
        }),
      })
      showSuccess(`Тестовое письмо отправлено на ${testEmail}`)
    } catch (e: any) {
      showError(`Ошибка теста: ${e.message}`)
    } finally {
      setSendingTest(false)
    }
  }

  // AI Assistant for Email & Campaign
  const handleAiAction = async (action: string, target: 'compose' | 'campaign' = 'compose', customPrompt = '') => {
    if (target === 'campaign') {
      setCampAiGenerating(true)
    } else {
      setAiGenerating(true)
    }
    try {
      const currentBody = target === 'campaign' ? campBody : composeBody
      const currentTone = target === 'campaign' ? campTone : composeTone
      const targetCompany = target === 'compose' ? (composeRecipients[0] || selectedTask?.name || '') : (selectedTask?.name || '')

      const data = await outreachFetch<any>('/api/outreach/ai/generate', {
        method: 'POST',
        body: JSON.stringify({
          action,
          prompt: customPrompt || aiPrompt || selectedTask?.prompt || '',
          context: currentBody,
          tone: currentTone,
          company_name: targetCompany,
        }),
      })

      if (action === 'cold_email') {
        if (target === 'campaign') {
          if (data.subject) setCampSubject(data.subject)
          if (data.body_text) setCampBody(data.body_text)
        } else {
          if (data.subject) setComposeSubject(data.subject)
          if (data.body_text) setComposeBody(data.body_text)
        }
        showSuccess('AI успешно сгенерировал тему и текст письма!')
      } else if (action === 'improve' || action === 'shorten' || action === 'grammar') {
        if (target === 'campaign') {
          if (data.body_text) setCampBody(data.body_text)
        } else {
          if (data.body_text) setComposeBody(data.body_text)
        }
        showSuccess('Текст обновлен с помощью AI!')
      } else if (action === 'subject') {
        if (data.subjects?.length) {
          if (target === 'campaign') {
            setCampSubject(data.subjects[0])
          } else {
            setComposeSubject(data.subjects[0])
          }
          showSuccess(`AI предложил тему: "${data.subjects[0]}"`)
        }
      }
    } catch (e: any) {
      showError(`Ошибка AI: ${e.message}`)
    } finally {
      if (target === 'campaign') {
        setCampAiGenerating(false)
      } else {
        setAiGenerating(false)
      }
    }
  }

  // Sync Inbox
  const handleSyncInbox = async () => {
    setSyncingInbox(true)
    try {
      const res = await outreachFetch<any>('/api/outreach/inbox/sync', { method: 'POST' })
      showSuccess(`Синхронизация завершена (новых писем: ${res.new_messages || res.synced || 0})`)
      fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
      if (selectedTask) {
        fetchTaskStats(selectedTask.id)
      }
    } catch (e: any) {
      showError(`Ошибка синхронизации: ${e.message}`)
    } finally {
      setSyncingInbox(false)
    }
  }

  // Reply to Inbox message
  const handleSendReply = async () => {
    if (!selectedMsg) return
    if (!replyText.trim()) {
      showError('Введите текст ответа')
      return
    }
    setSendingReply(true)
    try {
      await outreachFetch('/api/outreach/inbox/reply', {
        method: 'POST',
        body: JSON.stringify({
          message_id: selectedMsg.id,
          reply_body: replyText.trim(),
        }),
      })
      showSuccess(`Ответ отправлен на ${selectedMsg.sender_email}!`)
      setReplyText('')
      fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
      if (selectedTask) {
        fetchTaskStats(selectedTask.id)
      }
    } catch (e: any) {
      showError(`Ошибка отправки ответа: ${e.message}`)
    } finally {
      setSendingReply(false)
    }
  }

  // AI Generate Reply for Inbox
  const handleAiReply = async (type: string) => {
    if (!selectedMsg) return
    setAiReplyGenerating(true)
    try {
      const prompts: Record<string, string> = {
        agree: 'Напиши согласие на сотрудничество/встречу, предложи удобное время в будни.',
        request_quote: 'Вежливо поблагодари за отклик и запроси коммерческое предложение, прайс-лист и условия поставки.',
        decline: 'Вежливо поблагодари и напиши мягкий отказ, предложив оставаться на связи на будущее.',
      }
      const data = await outreachFetch<any>('/api/outreach/ai/generate', {
        method: 'POST',
        body: JSON.stringify({
          action: 'reply',
          prompt: prompts[type] || prompts.agree,
          incoming_message: selectedMsg.body_text,
          tone: 'professional',
        }),
      })
      if (data.reply_body) {
        setReplyText(data.reply_body)
        showSuccess('AI сгенерировал текст ответа!')
      }
    } catch (e: any) {
      showError(`Ошибка AI: ${e.message}`)
    } finally {
      setAiReplyGenerating(false)
    }
  }

  // Toggle Spam on Inbox message
  const handleToggleSpam = async (msg: IncomingMessage) => {
    try {
      const res = await outreachFetch<any>(`/api/outreach/inbox/${msg.id}/spam`, { method: 'POST' })
      if (res.is_spam) {
        const extra = res.auto_blocked_rule
          ? ` Домен @${res.auto_blocked_rule.value} добавлен в чёрный список (${res.affected_count} писем перенесено в спам).`
          : ''
        showSuccess(`Письмо перемещено в Спам.${extra}`)
      } else {
        showSuccess('Письмо возвращено из Спама')
      }
      fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
      fetchSettings()
      if (selectedTask) {
        fetchTaskStats(selectedTask.id)
      }
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Block Sender / Spammer Permanently
  const handleBlockSender = async (msg: IncomingMessage) => {
    const sender = msg.sender_email || msg.sender_name || 'этого отправителя'
    if (!confirm(`Заблокировать все письма от ${sender} и навсегда внести в чёрный список?`)) return
    try {
      const res = await outreachFetch<any>(`/api/outreach/inbox/${msg.id}/block-sender`, { method: 'POST' })
      showSuccess(`Спамщик заблокирован! Удалено писем: ${res.deleted_count || 1}. Правило добавлено в чёрный список.`)
      setSelectedMsg(null)
      fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
      fetchSettings()
      if (selectedTask) {
        fetchTaskStats(selectedTask.id)
      }
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Mark all messages in current category/inbox as read
  const handleMarkAllRead = async (customCategory?: string) => {
    try {
      const activeFilter = customCategory || inboxFilter
      const params = new URLSearchParams()
      if (activeFilter === 'bounces') {
        params.set('category', 'bounces')
      } else if (activeFilter === 'spam') {
        params.set('category', 'spam')
        params.set('is_spam', 'true')
      } else if (activeFilter === 'replies') {
        params.set('category', 'replies')
      } else if (activeFilter === 'auto_replies') {
        params.set('category', 'auto_replies')
      }
      if (inboxTaskFilter) {
        params.set('task_id', inboxTaskFilter)
      }
      const res = await outreachFetch<any>(`/api/outreach/inbox/mark-all-read?${params.toString()}`, {
        method: 'POST',
      })
      showSuccess(`Отмечено прочитанными: ${res.updated_count || 0} писем`)
      fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
    } catch (e: any) {
      showError(`Ошибка: ${e.message}`)
    }
  }

  // Purge all spam messages
  const handlePurgeSpam = async () => {
    if (!confirm(`Вы действительно хотите навсегда удалить все (${inboxCounts.spam}) спам-писем?`)) return
    try {
      const res = await outreachFetch<any>('/api/outreach/inbox/purge-spam', { method: 'POST' })
      showSuccess(`Удалено ${res.deleted_count || 0} спам-писем`)
      if (selectedMsg?.is_spam) setSelectedMsg(null)
      fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Add Custom Spam Rule
  const handleAddSpamRule = async () => {
    const val = newSpamRuleVal.trim().toLowerCase()
    if (!val) return
    setSavingSpamRule(true)
    try {
      const data = await outreachFetch<{ rules: Array<{ type: string; value: string }> }>('/api/outreach/spam-rules', {
        method: 'POST',
        body: JSON.stringify({ type: newSpamRuleType, value: val }),
      })
      setSpamRules(data.rules || [])
      setNewSpamRuleVal('')
      showSuccess(`Правило блокировки «${val}» добавлено и применено!`)
      fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
    } catch (e: any) {
      showError(e.message)
    } finally {
      setSavingSpamRule(false)
    }
  }

  // Delete Custom Spam Rule
  const handleDeleteSpamRule = async (idx: number) => {
    try {
      const data = await outreachFetch<{ rules: Array<{ type: string; value: string }> }>(`/api/outreach/spam-rules/${idx}`, {
        method: 'DELETE',
      })
      setSpamRules(data.rules || [])
      showSuccess('Правило блокировки удалено')
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Delete Inbox message
  const handleDeleteInboxMsg = async (id: string) => {
    if (!confirm('Удалить это письмо?')) return
    try {
      await outreachFetch(`/api/outreach/inbox/${id}`, { method: 'DELETE' })
      showSuccess('Письмо удалено')
      if (selectedMsg?.id === id) setSelectedMsg(null)
      fetchInbox(inboxTaskFilter || null, inboxFilterRef.current, inboxSearchRef.current, inboxLimitRef.current)
      if (selectedTask) {
        fetchTaskStats(selectedTask.id)
      }
    } catch (e: any) {
      showError(e.message)
    }
  }

  // Save Settings
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const payload: any = { ...settings }
      if (smtpPassword) payload.smtp_password = smtpPassword
      if (imapPassword) payload.imap_password = imapPassword
      await outreachFetch('/api/outreach/settings', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
      showSuccess('Настройки почты успешно сохранены!')
      setSmtpPassword('')
      setImapPassword('')
      fetchSettings()
    } catch (e: any) {
      showError(`Ошибка сохранения: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  // Consistent pleasant avatar color palette
  const getAvatarColor = (str: string) => {
    const colors = [
      '#f59e0b', // amber
      '#3b82f6', // blue
      '#10b981', // emerald
      '#ec4899', // pink
      '#8b5cf6', // violet
      '#06b6d4', // cyan
      '#6366f1', // indigo
      '#14b8a6', // teal
      '#f43f5e', // rose
      '#d97706', // dark amber
    ]
    let hash = 0
    const text = str || '?'
    for (let i = 0; i < text.length; i++) hash = text.charCodeAt(i) + ((hash << 5) - hash)
    return colors[Math.abs(hash) % colors.length]
  }

  // Toggle individual message read / unread status with optimistic update
  const handleToggleRead = async (e: React.MouseEvent, msg: IncomingMessage) => {
    e.stopPropagation()
    const targetId = msg.id
    const nextIsRead = !msg.is_read

    setInboxMessages((prev) =>
      inboxFilterRef.current === 'unread' && nextIsRead
        ? prev.filter((m) => m.id !== targetId)
        : prev.map((m) => (m.id === targetId ? { ...m, is_read: nextIsRead } : m))
    )
    if (inboxFilterRef.current === 'unread' && nextIsRead) {
      setInboxTotal((prev) => Math.max(0, prev - 1))
    }
    setInboxCounts((prev) => ({
      ...prev,
      unread: nextIsRead ? Math.max(0, prev.unread - 1) : prev.unread + 1,
    }))
    if (selectedMsg?.id === targetId) {
      setSelectedMsg((prev) => (prev ? { ...prev, is_read: nextIsRead } : null))
    }

    try {
      await outreachFetch(`/api/outreach/inbox/${targetId}/${nextIsRead ? 'read' : 'unread'}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_read: nextIsRead }),
      })
    } catch {
      // Revert optimistic state on error
      setInboxMessages((prev) =>
        prev.map((m) => (m.id === targetId ? { ...m, is_read: !nextIsRead } : m))
      )
      setInboxCounts((prev) => ({
        ...prev,
        unread: nextIsRead ? prev.unread + 1 : Math.max(0, prev.unread - 1),
      }))
      if (selectedMsg?.id === targetId) {
        setSelectedMsg((prev) => (prev ? { ...prev, is_read: !nextIsRead } : null))
      }
    }
  }

  // Format date helper
  const formatDate = (iso: string | null) => {
    if (!iso) return '—'
    try {
      const d = new Date(iso)
      return d.toLocaleString('ru-RU', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return iso
    }
  }

  return (
    <div className="outreach-container">
      {/* Global Alerts */}
      {message && (
        <div className="outreach-alert success">
          <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
          <span>{message}</span>
        </div>
      )}
      {error && (
        <div className="outreach-alert error">
          <AlertCircle size={18} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}

      {/* Global Module Navigation Tabs */}
      <div className="outreach-tabs" style={{ marginBottom: 16 }}>
        <button
          type="button"
          onClick={() => changeMainTab('tasks')}
          className={`outreach-tab-btn ${mainTab === 'tasks' ? 'active' : ''}`}
        >
          <FolderOpen size={16} />
          <span>Задачи поиска ({tasks.length})</span>
        </button>

        <button
          type="button"
          onClick={() => {
            changeMainTab('inbox')
            fetchInbox(inboxTaskFilter || null, inboxFilter, inboxSearch, inboxLimit)
          }}
          className={`outreach-tab-btn ${mainTab === 'inbox' ? 'active' : ''}`}
        >
          <Inbox size={16} />
          <span>Входящие ответы</span>
          {inboxCounts.unread > 0 && (
            <span className="outreach-tab-badge">{inboxCounts.unread}</span>
          )}
        </button>

        <button
          type="button"
          onClick={() => changeMainTab('compose')}
          className={`outreach-tab-btn ${mainTab === 'compose' ? 'active' : ''}`}
        >
          <PenTool size={16} />
          <span>Написать письмо</span>
          {composeRecipients.length > 0 && (
            <span className="outreach-tab-badge">{composeRecipients.length}</span>
          )}
        </button>

        <button
          type="button"
          onClick={() => changeMainTab('settings')}
          className={`outreach-tab-btn ${mainTab === 'settings' ? 'active' : ''}`}
        >
          <SettingsIcon size={16} />
          <span>Настройки почты</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: SEARCH TASKS & CAMPAIGNS (PROJECTS REGISTRY / TASK WORKSPACE)      */}
      {/* ========================================================================= */}
      {mainTab === 'tasks' && (
        <>
          {/* LEVEL 1: NO TASK SELECTED (MAIN DASHBOARD: LIST OF SEARCH PROJECTS) */}
          {!selectedTask && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

          {/* New Task Creation Modal / Collapsible Form */}
          {showNewTaskModal && (
            <div className="outreach-panel" style={{ border: '2px solid #0f766e', background: '#fafdfc' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h2 className="outreach-panel-title">Запуск новой задачи поиска целевых компаний</h2>
                  <p className="outreach-panel-desc">
                    Поиск прямых участников тендеров, поставщиков, дилеров и торговых домов с автофильтрацией финансовых посредников.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowNewTaskModal(false)}
                  className="outreach-btn outreach-btn-ghost"
                >
                  ✕ Закрыть
                </button>
              </div>

              <form onSubmit={handleStartSearch} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                    Название задачи / проекта:
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Например: Поставщики оборудования и исполнители госконтрактов 44-ФЗ"
                    value={taskName}
                    onChange={(e) => setTaskName(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                    Описание целевой аудитории (товары, ниша, деятельность):
                  </label>
                  <textarea
                    rows={3}
                    required
                    style={{ minHeight: 70 }}
                    placeholder="Например: компании занимающиеся участием в тендерах, поставщики промышленного оборудования, торговые дома и снабжение по 44-ФЗ и 223-ФЗ"
                    value={searchPrompt}
                    onChange={(e) => setSearchPrompt(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                    Количество контактов:
                  </label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
                    <input
                      type="number"
                      min={1}
                      max={50000}
                      style={{ width: 95, fontWeight: 700, textAlign: 'center' }}
                      value={targetCount}
                      onChange={(e) => setTargetCount(Math.max(1, Math.min(50000, parseInt(e.target.value) || 1)))}
                      title="Точное число контактов"
                    />
                    <span style={{ fontSize: 11.5, color: '#94a3b8' }}>или шаблоны:</span>
                    {leadCountPresets.map((cnt) => (
                      <div
                        key={cnt}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          borderRadius: 6,
                          border: targetCount === cnt ? '1.5px solid #059669' : '1px solid #cbd5e1',
                          background: targetCount === cnt ? '#ecfdf5' : '#fff',
                          transition: 'all 0.15s',
                          padding: isEditingPresets ? '2px 4px 2px 6px' : 0,
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => setTargetCount(cnt)}
                          style={{
                            padding: isEditingPresets ? '3px 4px' : '5px 9px',
                            background: 'transparent',
                            border: 'none',
                            fontSize: 12,
                            fontWeight: 700,
                            color: targetCount === cnt ? '#065f46' : '#334155',
                            cursor: 'pointer',
                          }}
                        >
                          +{cnt.toLocaleString('ru-RU')}
                        </button>
                        {isEditingPresets && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleRemovePreset(cnt)
                            }}
                            style={{
                              background: '#fee2e2',
                              border: 'none',
                              borderRadius: 4,
                              width: 17,
                              height: 17,
                              padding: 0,
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#dc2626',
                              cursor: 'pointer',
                              marginLeft: 2,
                            }}
                            title={`Удалить шаблон +${cnt}`}
                          >
                            <X size={10} strokeWidth={2.5} />
                          </button>
                        )}
                      </div>
                    ))}

                    {isEditingPresets ? (
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#f8fafc', border: '1px dashed #94a3b8', borderRadius: 6, padding: '2px 6px' }}>
                        <input
                          type="number"
                          min="1"
                          max="50000"
                          placeholder="+число"
                          value={newPresetInput}
                          onChange={(e) => setNewPresetInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              handleAddPreset()
                            }
                          }}
                          style={{
                            width: 65,
                            padding: '3px 4px',
                            fontSize: 11,
                            fontWeight: 600,
                            border: '1px solid #cbd5e1',
                            borderRadius: 4,
                            textAlign: 'center',
                          }}
                        />
                        <button
                          type="button"
                          onClick={handleAddPreset}
                          style={{
                            background: '#059669',
                            color: '#fff',
                            border: 'none',
                            borderRadius: 4,
                            padding: '3px 6px',
                            fontSize: 11,
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                          title="Добавить шаблон"
                        >
                          <Plus size={11} strokeWidth={2.5} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setIsEditingPresets(false)}
                          style={{
                            background: '#e2e8f0',
                            color: '#334155',
                            border: 'none',
                            borderRadius: 4,
                            padding: '3px 6px',
                            fontSize: 11,
                            cursor: 'pointer',
                          }}
                          title="Готово"
                        >
                          <CheckCircle2 size={11} />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setIsEditingPresets(true)}
                        style={{
                          background: '#f8fafc',
                          border: '1px dashed #cbd5e1',
                          borderRadius: 6,
                          padding: '4px 6px',
                          fontSize: 11,
                          color: '#64748b',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 3,
                        }}
                        title="Настроить шаблоны (+добавить / удалить)"
                      >
                        <Edit3 size={11} />
                        <span style={{ fontSize: 10 }}>настроить</span>
                      </button>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="submit"
                    disabled={loading}
                    className="outreach-btn outreach-btn-primary"
                    style={{ padding: '8px 18px', fontSize: 13 }}
                  >
                    <Play size={15} />
                    <span>Запустить сбор контактов</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowNewTaskModal(false)}
                    className="outreach-btn outreach-btn-secondary"
                  >
                    Отмена
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Task Projects List */}
          <div className="outreach-panel">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h2 className="outreach-panel-title" style={{ fontSize: 18 }}>
                  Задачи поиска контактов и кампании
                </h2>
                <p className="outreach-panel-desc">
                  Выберите конкретную задачу, чтобы открыть ее контакты, настроить рассылку и работать со входящими ответами.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  type="button"
                  onClick={fetchTasks}
                  className="outreach-btn outreach-btn-secondary"
                >
                  <RefreshCw size={13} />
                  <span>Обновить</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowNewTaskModal(true)}
                  className="outreach-btn outreach-btn-primary"
                  style={{ padding: '8px 16px' }}
                >
                  <Plus size={15} />
                  <span>+ Запустить новый поиск</span>
                </button>
              </div>
            </div>

            {tasks.length === 0 ? (
              <div style={{ padding: '40px 0', textAlign: 'center', color: '#94a3b8' }}>
                <Search size={36} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
                <h3 style={{ margin: '0 0 6px', fontSize: 15, fontWeight: 700, color: '#334155' }}>
                  Нет запущенных задач
                </h3>
                <p style={{ margin: '0 0 16px', fontSize: 12 }}>
                  Запустите первую задачу поиска компаний, чтобы начать работу с контактами и рассылками.
                </p>
                <button
                  type="button"
                  onClick={() => setShowNewTaskModal(true)}
                  className="outreach-btn outreach-btn-primary"
                >
                  <Plus size={14} />
                  <span>Создать задачу поиска</span>
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                {tasks.map((task) => (
                  <div
                    key={task.id}
                    className="outreach-task-row"
                    style={{
                      background: '#fff',
                      border: '1px solid #e2e8f0',
                      borderRadius: 10,
                      padding: '14px 18px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 16,
                      boxShadow: '0 1px 3px rgba(15, 23, 42, 0.04)',
                      transition: 'all 0.15s ease',
                      flexWrap: 'wrap',
                    }}
                  >
                    {/* Left: Title, Badges, Query Prompt */}
                    <div style={{ flex: 1, minWidth: 280 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 4 }}>
                        <h3
                          onClick={() => handleSelectTask(task)}
                          style={{
                            margin: 0,
                            fontSize: 14.5,
                            fontWeight: 700,
                            color: '#0f172a',
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = '#0d9488')}
                          onMouseLeave={(e) => (e.currentTarget.style.color = '#0f172a')}
                        >
                          {task.name}
                        </h3>

                        {task.status === 'completed' && (
                          <span className="outreach-badge completed" style={{ fontSize: 11, padding: '2px 8px' }}>
                            <CheckCircle2 size={12} /> Готово
                          </span>
                        )}
                        {task.status === 'running' && (
                          <span className="outreach-badge running" style={{ fontSize: 11, padding: '2px 8px' }}>
                            <RefreshCw size={12} className="animate-spin" /> В процессе
                          </span>
                        )}
                        {task.status === 'cancelled' && (
                          <span className="outreach-badge cancelled" style={{ fontSize: 11, padding: '2px 8px' }}>
                            Остановлена
                          </span>
                        )}

                        <span style={{ fontSize: 11, color: '#94a3b8' }}>
                          {formatDate(task.created_at)}
                        </span>
                      </div>

                      {task.prompt && (
                        <p style={{ margin: '0 0 8px 0', fontSize: 12, color: '#64748b', lineHeight: 1.4 }}>
                          {task.prompt}
                        </p>
                      )}

                      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                        <div style={{ background: '#f1f5f9', padding: '3px 8px', borderRadius: 6, fontSize: 11, color: '#334155', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Users size={12} style={{ color: '#0f766e' }} />
                          <span>Лидов собрано:</span>
                          <strong style={{ color: '#0f172a' }}>{task.collected_count}</strong>
                          <span style={{ color: '#64748b' }}>/ {task.target_count}</span>
                        </div>

                        <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '3px 8px', borderRadius: 6, fontSize: 11, color: '#047857', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Coins size={12} style={{ color: '#059669' }} />
                          <span>Себестоимость: {task.cost_label || `${(task.total_cost_rub || 0).toFixed(2)} ₽`}</span>
                        </div>

                        {task.yandex_requests ? (
                          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', padding: '3px 8px', borderRadius: 6, fontSize: 11, color: '#64748b' }}>
                            Яндекс: <strong>{task.yandex_requests}</strong> зап. ({(task.yandex_cost_rub || 0).toFixed(2)} ₽)
                          </div>
                        ) : null}
                      </div>
                    </div>

                    {/* Right: Actions */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                      <button
                        type="button"
                        onClick={() => handleSelectTask(task)}
                        className="outreach-btn outreach-btn-primary"
                        style={{ padding: '7px 16px', fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 6 }}
                      >
                        <FolderOpen size={14} />
                        <span>Открыть задачу ({task.collected_count}) →</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setDeleteTaskId(task.id)}
                        className="outreach-btn outreach-btn-danger"
                        style={{ padding: '7px 10px' }}
                        title="Удалить задачу"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* LEVEL 2: INSIDE A SELECTED TASK (TASK WORKSPACE)                          */}
      {/* ========================================================================= */}
      {selectedTask && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Top Breadcrumb & Task Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
              <button
                type="button"
                onClick={() => {
                  setSelectedTask(null)
                  try {
                    localStorage.removeItem('tenderlex_outreach_selected_task_id')
                  } catch {}
                  fetchTasks()
                }}
                className="outreach-btn outreach-btn-secondary"
                style={{ padding: '5px 10px', fontSize: 12, flexShrink: 0 }}
              >
                <ArrowLeft size={14} />
                <span>Все задачи</span>
              </button>

              <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {selectedTask.name}
              </h2>

              <span
                style={{
                  padding: '2px 8px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  background: '#ecfdf5',
                  border: '1px solid #a7f3d0',
                  color: '#047857',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  flexShrink: 0,
                }}
                title={`Расход: Яндекс ${((searchStatus && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) ? searchStatus.yandex_cost_rub : null) ?? taskStats?.task?.yandex_cost_rub ?? selectedTask.yandex_cost_rub ?? 0).toFixed(2)} ₽ (${(searchStatus && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) ? searchStatus.yandex_requests : null) ?? taskStats?.task?.yandex_requests ?? selectedTask.yandex_requests ?? 0} зап.)`}
              >
                <Coins size={12} style={{ color: '#d97706' }} />
                <span>
                  {((searchStatus && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) ? searchStatus.yandex_cost_rub : null) ?? taskStats?.task?.yandex_cost_rub ?? selectedTask.yandex_cost_rub ?? 0).toFixed(2)} ₽
                </span>
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              <button
                type="button"
                disabled={refreshing}
                onClick={handleRefreshTaskData}
                className="outreach-btn outreach-btn-secondary"
                style={{ padding: '6px 12px', fontSize: 12.5, flexShrink: 0 }}
                title="Обновить данные задачи"
              >
                <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
                <span>{refreshing ? 'Обновление...' : 'Обновить'}</span>
              </button>
            </div>
          </div>

          {/* 1. In-Task Search and Dobor Module (Placed TOP above Iterations, Collapsible) */}
          <div
            className="outreach-panel"
            style={{
              padding: isDoborCollapsed ? '10px 16px' : '14px 16px',
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              borderRadius: 10,
              boxShadow: '0 2px 6px rgba(0,0,0,0.03)',
              transition: 'all 0.2s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: isDoborCollapsed ? 0 : 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13.5, fontWeight: 700, color: '#0f172a' }}>
                <Sparkles size={16} style={{ color: '#059669' }} />
                <span>Поиск и добор контактов в задачу</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#475569', background: '#f1f5f9', border: '1px solid #e2e8f0', padding: '1px 8px', borderRadius: 6 }}>
                  в базе: {taskStats?.total_leads ?? selectedTask.collected_count} лидов ({taskStats?.waves?.length || 1} {taskStats?.waves?.length === 1 ? 'итерация' : 'итерации'})
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                <span style={{ fontSize: 11.5, color: '#059669', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}>
                  🛡️ Автоматическое исключение уже собранных компаний
                </span>
                <button
                  type="button"
                  onClick={toggleDoborCollapsed}
                  className="dobor-collapse-btn"
                  title={isDoborCollapsed ? 'Развернуть блок поиска и добора' : 'Свернуть блок поиска и добора'}
                >
                  {isDoborCollapsed ? <ChevronDown size={16} strokeWidth={2.5} /> : <ChevronUp size={16} strokeWidth={2.5} />}
                </button>
              </div>
            </div>

            {!isDoborCollapsed && (
              <>
                {/* Resizable Search Prompt Textarea */}
                <div style={{ marginBottom: 10 }}>
                  <textarea
                    rows={3}
                    value={taskSearchPrompt !== '' ? taskSearchPrompt : getTaskInitialPrompt(selectedTask)}
                    onChange={(e) => setTaskSearchPrompt(e.target.value)}
                    placeholder="Промпт поиска, критерии компаний, продукция, ниша, география..."
                    style={{
                      width: '100%',
                      fontSize: 13,
                      lineHeight: 1.5,
                      padding: '9px 12px',
                      borderRadius: 8,
                      border: '1px solid #cbd5e1',
                      background: '#f8fafc',
                      resize: 'vertical',
                      minHeight: 72,
                    }}
                  />
                </div>

                {/* Controls Row: Presets, Number Input, Action Button */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Сколько добрать:</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                      {leadCountPresets.map((val) => (
                        <div
                          key={val}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            borderRadius: 6,
                            border: taskDoborCount === val ? '1.5px solid #059669' : '1px solid #cbd5e1',
                            background: taskDoborCount === val ? '#ecfdf5' : '#fff',
                            transition: 'all 0.15s',
                            padding: isEditingPresets ? '2px 4px 2px 6px' : 0,
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setTaskDoborCount(val)}
                            style={{
                              padding: isEditingPresets ? '3px 4px' : '6px 10px',
                              background: 'transparent',
                              border: 'none',
                              fontSize: 12,
                              fontWeight: 700,
                              color: taskDoborCount === val ? '#065f46' : '#334155',
                              cursor: 'pointer',
                            }}
                          >
                            +{val.toLocaleString('ru-RU')}
                          </button>
                          {isEditingPresets && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleRemovePreset(val)
                              }}
                              style={{
                                background: '#fee2e2',
                                border: 'none',
                                borderRadius: 4,
                                width: 17,
                                height: 17,
                                padding: 0,
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: '#dc2626',
                                cursor: 'pointer',
                                marginLeft: 2,
                              }}
                              title={`Удалить шаблон +${val}`}
                            >
                              <X size={10} strokeWidth={2.5} />
                            </button>
                          )}
                        </div>
                      ))}

                      {isEditingPresets ? (
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#f8fafc', border: '1px dashed #94a3b8', borderRadius: 6, padding: '2px 6px' }}>
                          <input
                            type="number"
                            min="1"
                            max="50000"
                            placeholder="+число"
                            value={newPresetInput}
                            onChange={(e) => setNewPresetInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault()
                                handleAddPreset()
                              }
                            }}
                            style={{
                              width: 65,
                              padding: '3px 4px',
                              fontSize: 11,
                              fontWeight: 600,
                              border: '1px solid #cbd5e1',
                              borderRadius: 4,
                              textAlign: 'center',
                            }}
                          />
                          <button
                            type="button"
                            onClick={handleAddPreset}
                            style={{
                              background: '#059669',
                              color: '#fff',
                              border: 'none',
                              borderRadius: 4,
                              padding: '3px 6px',
                              fontSize: 11,
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                            title="Добавить шаблон"
                          >
                            <Plus size={11} strokeWidth={2.5} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setIsEditingPresets(false)}
                            style={{
                              background: '#e2e8f0',
                              color: '#334155',
                              border: 'none',
                              borderRadius: 4,
                              padding: '3px 6px',
                              fontSize: 11,
                              cursor: 'pointer',
                            }}
                            title="Готово"
                          >
                            <CheckCircle2 size={11} />
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setIsEditingPresets(true)}
                          style={{
                            background: '#f8fafc',
                            border: '1px dashed #cbd5e1',
                            borderRadius: 6,
                            padding: '4px 6px',
                            fontSize: 11,
                            color: '#64748b',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                          }}
                          title="Редактировать шаблоны (+добавить / удалить)"
                        >
                          <Edit3 size={11} />
                          <span style={{ fontSize: 10 }}>настроить</span>
                        </button>
                      )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ fontSize: 11.5, color: '#94a3b8' }}>или:</span>
                      <input
                        type="number"
                        min="1"
                        max="20000"
                        value={taskDoborCount}
                        onChange={(e) => setTaskDoborCount(Math.max(1, parseInt(e.target.value) || 1))}
                        style={{
                          width: 80,
                          fontSize: 12.5,
                          fontWeight: 600,
                          padding: '5px 8px',
                          borderRadius: 6,
                          border: '1px solid #cbd5e1',
                          textAlign: 'center',
                        }}
                        title="Точное число контактов"
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {(selectedTask.status === 'paused' || (selectedTask.status === 'cancelled' && (selectedTask.collected_count || 0) < selectedTask.target_count)) && (
                      <button
                        type="button"
                        onClick={() => handleResumeSearch(selectedTask.id)}
                        className="outreach-btn"
                        style={{
                          padding: '8px 18px',
                          fontSize: 13,
                          fontWeight: 700,
                          background: '#10b981',
                          color: '#fff',
                          border: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          flexShrink: 0,
                          borderRadius: 8,
                          boxShadow: '0 2px 6px rgba(16, 185, 129, 0.25)',
                          cursor: 'pointer',
                        }}
                        title="Продолжить сбор сохраненных кандидатов без запросов в Яндекс"
                      >
                        <Play size={14} />
                        <span>Продолжить сбор</span>
                      </button>
                    )}

                    <button
                      type="button"
                      disabled={extending || selectedTask.status === 'running' || (activeTaskId === selectedTask.id && searchStatus?.status === 'running')}
                      onClick={async () => {
                        await handleExtendTaskWithParams(taskDoborCount, taskSearchPrompt)
                      }}
                      className="outreach-btn outreach-btn-primary"
                      style={{
                        padding: '8px 18px',
                        fontSize: 13,
                        fontWeight: 700,
                        background: '#059669',
                        borderColor: '#059669',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        flexShrink: 0,
                        boxShadow: '0 2px 6px rgba(5, 150, 105, 0.25)',
                      }}
                    >
                      {extending ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                      <span>🚀 Запустить добор (+{taskDoborCount})</span>
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* 2. Wave / Search Iterations Selector Bar */}
          {((taskStats?.waves && taskStats.waves.length > 1) || (selectedTask.waves && selectedTask.waves.length > 1)) && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 10,
                padding: '8px 14px',
                flexWrap: 'wrap',
                boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 700, color: '#334155', marginRight: 4 }}>
                <Layers size={15} style={{ color: '#059669' }} />
                <span>Итерации поиска:</span>
              </div>

              {/* All Waves Pill */}
              <button
                type="button"
                onClick={() => {
                  setSelectedWave(null)
                  fetchLeads(selectedTask.id, 1, searchFilter, statusFilter, null)
                }}
                style={{
                  padding: '5px 12px',
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 700,
                  border: selectedWave === null ? '1.5px solid #059669' : '1px solid #e2e8f0',
                  background: selectedWave === null ? '#ecfdf5' : '#f8fafc',
                  color: selectedWave === null ? '#065f46' : '#475569',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  transition: 'all 0.15s',
                }}
              >
                <span>✨ Все итерации</span>
                <span style={{ fontSize: 11, background: selectedWave === null ? '#a7f3d0' : '#e2e8f0', color: selectedWave === null ? '#064e3b' : '#64748b', padding: '1px 6px', borderRadius: 6 }}>
                  {taskStats?.total_leads ?? selectedTask.collected_count} лидов
                </span>
              </button>

              {/* Individual Waves Pills */}
              {(taskStats?.waves || selectedTask.waves || []).map((w) => {
                const isSelected = selectedWave === w.wave
                const isRunning = Boolean(
                  (searchStatus && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) && searchStatus.status === 'running' && searchStatus.wave_index === w.wave)
                )
                const isPaused = !isRunning && Boolean(
                  w.status === 'paused' ||
                  ((searchStatus && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) && searchStatus.status === 'paused' && searchStatus.wave_index === w.wave) ||
                   (selectedTask.status === 'paused' && w.wave === (taskStats?.waves?.length || selectedTask.waves?.length || 1)))
                )
                const liveCollected = isRunning && searchStatus?.wave_collected !== undefined ? searchStatus.wave_collected : (w.lead_count ?? w.collected ?? 0)
                const liveCost = isRunning && searchStatus?.wave_cost_rub !== undefined
                  ? `${Number(searchStatus.wave_cost_rub).toFixed(2)} ₽`
                  : w.cost_rub !== undefined && w.cost_rub !== null
                  ? `${Number(w.cost_rub).toFixed(2)} ₽`
                  : null
                return (
                  <button
                    key={w.wave}
                    type="button"
                    onClick={() => {
                      setSelectedWave(w.wave)
                      fetchLeads(selectedTask.id, 1, searchFilter, statusFilter, w.wave)
                    }}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 8,
                      fontSize: 12,
                      fontWeight: 700,
                      border: isSelected ? '1.5px solid #059669' : '1px solid #e2e8f0',
                      background: isSelected ? '#ecfdf5' : '#f8fafc',
                      color: isSelected ? '#065f46' : '#475569',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      transition: 'all 0.15s',
                    }}
                  >
                    <span>{w.wave === 1 ? '🎯 Основной поиск' : `⚡ ${w.name || `Добор #${w.wave - 1}`}`}</span>
                    <span style={{ fontSize: 11, background: isSelected ? '#a7f3d0' : '#e2e8f0', color: isSelected ? '#064e3b' : '#64748b', padding: '1px 6px', borderRadius: 6 }}>
                      {liveCollected} лидов
                    </span>
                    {liveCost && (
                      <span style={{ fontSize: 11, color: isSelected ? '#047857' : '#94a3b8', fontWeight: 600 }}>
                        {liveCost}
                      </span>
                    )}
                    {isRunning && <span className="animate-pulse" style={{ color: '#059669', fontSize: 10 }}>● в процессе</span>}
                    {isPaused && <span style={{ color: '#d97706', fontSize: 10, fontWeight: 700 }}>● на паузе</span>}
                  </button>
                )
              })}
            </div>
          )}

          {/* 3. Task-Specific 5 Metrics Cards (Dynamic per selected wave, compact layout) */}
          {(() => {
            const activeWaveObj = selectedWave !== null
              ? (taskStats?.waves || selectedTask.waves || []).find((w) => w.wave === selectedWave)
              : null

            const isWaveRunning = Boolean(
              activeWaveObj &&
              searchStatus &&
              (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) &&
              searchStatus.status === 'running' &&
              searchStatus.wave_index === activeWaveObj.wave
            )

            const displayLeadsCount = activeWaveObj
              ? (isWaveRunning && searchStatus?.wave_collected !== undefined
                  ? searchStatus.wave_collected
                  : (activeWaveObj.lead_count ?? activeWaveObj.collected ?? 0))
              : (taskStats?.total_leads ?? selectedTask.collected_count ?? 0)

            const displayTargetCount = activeWaveObj
              ? (isWaveRunning && searchStatus?.wave_target
                  ? searchStatus.wave_target
                  : (activeWaveObj.target ?? activeWaveObj.target_count ?? 0))
              : selectedTask.target_count

            const displayMxCount = activeWaveObj
              ? (activeWaveObj.mx_valid_leads ?? (displayLeadsCount ? Math.round(displayLeadsCount * 0.93) : 0))
              : (taskStats?.mx_valid_leads ?? (selectedTask.collected_count ? Math.round(selectedTask.collected_count * 0.93) : 0))

            const displaySentCount = activeWaveObj
              ? (activeWaveObj.sent_leads ?? 0)
              : (taskStats?.sent_leads ?? 0)

            const displayRepliedCount = activeWaveObj
              ? (activeWaveObj.replied_leads ?? 0)
              : (taskStats?.replied_leads ?? inboxMessages.length)

            const allWaves = taskStats?.waves || selectedTask.waves || []
            const wavesCostSum = allWaves.reduce((sum, w) => {
              const isRunning = Boolean(
                searchStatus &&
                (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) &&
                searchStatus.status === 'running' &&
                searchStatus.wave_index === w.wave
              )
              const wCost = isRunning && searchStatus?.wave_cost_rub !== undefined
                ? Number(searchStatus.wave_cost_rub)
                : (w.cost_rub !== undefined && w.cost_rub !== null
                    ? Number(w.cost_rub)
                    : Number(w.yandex_cost_rub || 0))
              return sum + (isNaN(wCost) ? 0 : wCost)
            }, 0)

            const totalYandexCost = wavesCostSum > 0
              ? wavesCostSum
              : Number(
                  (searchStatus && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) ? searchStatus.yandex_cost_rub : null) ??
                  taskStats?.task?.yandex_cost_rub ??
                  selectedTask.yandex_cost_rub ??
                  0
                )

            const wavesRequestsSum = allWaves.reduce((sum, w) => {
              const isRunning = Boolean(
                searchStatus &&
                (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) &&
                searchStatus.status === 'running' &&
                searchStatus.wave_index === w.wave
              )
              const wReq = isRunning && searchStatus?.wave_yandex_requests !== undefined
                ? Number(searchStatus.wave_yandex_requests)
                : (w.yandex_requests !== undefined && w.yandex_requests !== null
                    ? Number(w.yandex_requests)
                    : Math.round(Number(w.cost_rub || w.yandex_cost_rub || 0) / 0.04))
              return sum + (isNaN(wReq) ? 0 : wReq)
            }, 0)

            const totalYandexRequests = wavesRequestsSum > 0
              ? wavesRequestsSum
              : Number(
                  (searchStatus && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id) ? searchStatus.yandex_requests : null) ??
                  taskStats?.task?.yandex_requests ??
                  selectedTask.yandex_requests ??
                  0
                )

            const displayCost = activeWaveObj
              ? (isWaveRunning && searchStatus?.wave_cost_rub !== undefined
                  ? `${Number(searchStatus.wave_cost_rub).toFixed(2)} ₽`
                  : activeWaveObj.cost_rub !== undefined && activeWaveObj.cost_rub !== null
                  ? `${Number(activeWaveObj.cost_rub).toFixed(2)} ₽`
                  : `${Number(activeWaveObj.yandex_cost_rub || 0).toFixed(2)} ₽`)
              : `${totalYandexCost.toFixed(2)} ₽`

            const displayCostSub = activeWaveObj
              ? (isWaveRunning && searchStatus?.wave_yandex_requests !== undefined
                  ? `Яндекс: ${searchStatus.wave_yandex_requests} зап.`
                  : `Яндекс: ${activeWaveObj.yandex_requests ?? Math.round((Number(activeWaveObj.cost_rub || activeWaveObj.yandex_cost_rub || 0)) / 0.04)} зап.`)
              : `Яндекс: ${totalYandexRequests.toLocaleString('ru-RU')} зап.`

            const waveCardTitle = activeWaveObj
              ? `Расход Яндекс (${activeWaveObj.wave === 1 ? 'основной поиск' : `добор #${activeWaveObj.wave - 1}`})`
              : (searchStatus && searchStatus.status === 'running'
                  ? 'Расход Яндекс (все итерации • идет сбор)'
                  : 'Расход Яндекс (все итерации)')

            return (
              <div className="outreach-metrics-grid">
                <div className="outreach-metric-card">
                  <div className="outreach-metric-header">
                    <div className="outreach-metric-icon blue">
                      <Users size={16} />
                    </div>
                    <div className="outreach-metric-info">
                      <span className="outreach-metric-label">
                        {activeWaveObj ? `Лидов (${activeWaveObj.name || `Поиск #${activeWaveObj.wave}`})` : 'Лидов в задаче'}
                      </span>
                      <strong className="outreach-metric-value">{displayLeadsCount}</strong>
                    </div>
                  </div>
                  <span className="outreach-metric-sub">Цель: {displayTargetCount} контактов</span>
                </div>

                <div className="outreach-metric-card">
                  <div className="outreach-metric-header">
                    <div className="outreach-metric-icon green">
                      <ShieldCheck size={16} />
                    </div>
                    <div className="outreach-metric-info">
                      <span className="outreach-metric-label">MX проверен</span>
                      <strong className="outreach-metric-value" style={{ color: '#059669' }}>
                        {displayMxCount}
                      </strong>
                    </div>
                  </div>
                  <span className="outreach-metric-sub">Валидные почтовые домены</span>
                </div>

                <div className="outreach-metric-card">
                  <div className="outreach-metric-header">
                    <div className="outreach-metric-icon indigo">
                      <Send size={16} />
                    </div>
                    <div className="outreach-metric-info">
                      <span className="outreach-metric-label">Отправлено писем</span>
                      <strong className="outreach-metric-value">{displaySentCount}</strong>
                    </div>
                  </div>
                  <span className="outreach-metric-sub">По контактам выборки</span>
                </div>

                <div className="outreach-metric-card">
                  <div className="outreach-metric-header">
                    <div className="outreach-metric-icon amber">
                      <MessageSquare size={16} />
                    </div>
                    <div className="outreach-metric-info">
                      <span className="outreach-metric-label">Получено ответов</span>
                      <strong className="outreach-metric-value" style={{ color: '#d97706' }}>
                        {displayRepliedCount}
                      </strong>
                    </div>
                  </div>
                  <span className="outreach-metric-sub">Входящие ответы</span>
                </div>

                <div className="outreach-metric-card">
                  <div className="outreach-metric-header">
                    <div className="outreach-metric-icon amber" style={{ background: '#fef3c7', color: '#d97706' }}>
                      <Coins size={16} />
                    </div>
                    <div className="outreach-metric-info">
                      <span className="outreach-metric-label">
                        {waveCardTitle}
                      </span>
                      <strong className="outreach-metric-value" style={{ color: '#059669' }}>
                        {displayCost}
                      </strong>
                    </div>
                  </div>
                  <span className="outreach-metric-sub">
                    {displayCostSub}
                  </span>
                </div>
              </div>
            )
          })()}

          {/* Live Search Status Banner inside Workspace */}
          {((searchStatus && searchStatus.status === 'running' && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id)) || selectedTask.status === 'running') && (() => {
            const activeWaveForBanner = (taskStats?.waves || selectedTask.waves || []).find(
              (w) => w.status === 'running' || (searchStatus?.status === 'running' && searchStatus?.wave_index === w.wave)
            ) || (taskStats?.waves || selectedTask.waves || [])[(taskStats?.waves || selectedTask.waves || []).length - 1]

            const isBannerExtend = searchStatus?.is_extend ?? (activeWaveForBanner ? activeWaveForBanner.wave > 1 : (selectedTask.waves?.length ? selectedTask.waves.length > 1 : false))
            const bannerWaveIdx = searchStatus?.wave_index ?? (activeWaveForBanner ? activeWaveForBanner.wave : (selectedTask.waves?.length || 1))
            const bannerWaveTarget = searchStatus?.wave_target ?? (activeWaveForBanner?.target || 500)
            const bannerWaveCollected = searchStatus?.wave_collected ?? (activeWaveForBanner?.collected || 0)
            const bannerWaveCost = searchStatus?.wave_cost_rub ?? (activeWaveForBanner?.cost_rub ?? 0)

            return (
            <div
              style={{
                background: 'linear-gradient(135deg, #064e3b 0%, #047857 100%)',
                color: '#fff',
                borderRadius: 10,
                padding: '12px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                boxShadow: '0 4px 12px rgba(4, 120, 87, 0.2)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 0 }}>
                <RefreshCw size={20} className="animate-spin" style={{ color: '#6ee7b7', flexShrink: 0 }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13.5, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span>
                      {isBannerExtend
                        ? `Идет добор контактов (Добор #${bannerWaveIdx - 1})`
                        : 'Идет поиск и сбор контактов'}
                    </span>
                    <span style={{ fontSize: 11, background: 'rgba(255,255,255,0.2)', padding: '1px 6px', borderRadius: 4 }}>
                      Цель: +{bannerWaveTarget} контактов
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: '#d1fae5', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {searchStatus?.message || selectedTask.message || 'Сбор и проверка новых компаний...'}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
                <div style={{ textAlign: 'right', fontSize: 12, color: '#ecfdf5' }}>
                  <div>
                    Собрано в {isBannerExtend ? 'доборе' : 'поиске'}: <strong>{bannerWaveCollected}</strong> лидов
                  </div>
                  <div style={{ fontSize: 11, color: '#a7f3d0' }}>
                    Расход Яндекс: {Number(bannerWaveCost).toFixed(2)} ₽
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => handlePauseSearch(selectedTask.id)}
                    className="outreach-btn"
                    style={{
                      background: '#f59e0b',
                      color: '#fff',
                      border: 'none',
                      padding: '6px 12px',
                      fontSize: 12,
                      borderRadius: 6,
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                    title="Поставить на паузу (найденные сайты сохранятся на диске)"
                  >
                    <Pause size={13} />
                    <span>Пауза</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCancelSearch(selectedTask.id)}
                    className="outreach-btn"
                    style={{
                      background: 'rgba(239, 68, 68, 0.9)',
                      color: '#fff',
                      border: 'none',
                      padding: '6px 12px',
                      fontSize: 12,
                      borderRadius: 6,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Остановить
                  </button>
                </div>
              </div>
            </div>
            )
          })()}

          {/* Live Paused / Resumable Status Banner */}
          {!((searchStatus && searchStatus.status === 'running' && (searchStatus.id === selectedTask.id || activeTaskId === selectedTask.id)) || selectedTask.status === 'running') &&
            (selectedTask.status === 'paused' || selectedTask.status === 'cancelling' || (selectedTask.status === 'cancelled' && (selectedTask.collected_count || 0) < selectedTask.target_count)) &&
            (() => {
              const allWaves = taskStats?.waves || selectedTask.waves || []
              const activeWaveObj = selectedWave !== null ? allWaves.find((w) => w.wave === selectedWave) : allWaves[allWaves.length - 1]
              const isSpecificWave = selectedWave !== null && activeWaveObj
              const waveCollected = activeWaveObj ? (activeWaveObj.lead_count ?? activeWaveObj.collected ?? 0) : (selectedTask.collected_count || 0)
              const waveTarget = activeWaveObj ? (activeWaveObj.target ?? activeWaveObj.target_count ?? 100) : (selectedTask.target_count || 0)
              const badgeText = isSpecificWave
                ? (activeWaveObj.wave === 1 ? `Собрано: ${waveCollected} из ${waveTarget}` : `Собрано в доборе #${activeWaveObj.wave - 1}: ${waveCollected} из ${waveTarget}`)
                : `Собрано: ${selectedTask.collected_count || 0} из ${selectedTask.target_count || 0}`

              return (
                <div
                  style={{
                    background: 'linear-gradient(135deg, #78350f 0%, #b45309 100%)',
                    color: '#fff',
                    borderRadius: 10,
                    padding: '12px 18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 16,
                    boxShadow: '0 4px 12px rgba(180, 83, 9, 0.2)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 0 }}>
                    <span style={{ fontSize: 22 }}>⏸️</span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 13.5, display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>Сбор контактов приостановлен</span>
                        <span style={{ fontSize: 11, background: 'rgba(255,255,255,0.2)', padding: '1px 6px', borderRadius: 4 }}>
                          {badgeText}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: '#fef3c7', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {selectedTask.message || 'Сбор можно продолжить в один клик.'}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                    <button
                      type="button"
                      onClick={() => handleResumeSearch(selectedTask.id)}
                      className="outreach-btn"
                      style={{
                        background: '#10b981',
                        color: '#fff',
                        border: 'none',
                        padding: '8px 18px',
                        fontSize: 13,
                        borderRadius: 6,
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        boxShadow: '0 2px 6px rgba(16, 185, 129, 0.3)',
                      }}
                      title="Возобновить сбор контактов"
                    >
                      <Play size={14} />
                      <span>Продолжить сбор</span>
                    </button>
                  </div>
                </div>
              )
            })()}

          {/* Sub-Navigation Tabs inside Selected Task */}
          <div className="outreach-tabs">
            <button
              type="button"
              onClick={() => changeTaskSubTab('leads')}
              className={`outreach-tab-btn ${taskSubTab === 'leads' ? 'active' : ''}`}
            >
              <Users size={16} />
              <span>База контактов ({taskStats?.total_leads ?? selectedTask.collected_count})</span>
            </button>

            <button
              type="button"
              onClick={() => changeTaskSubTab('campaign')}
              className={`outreach-tab-btn ${taskSubTab === 'campaign' ? 'active' : ''}`}
            >
              <Send size={16} />
              <span>Email-рассылка</span>
            </button>
          </div>

          {/* SUBTAB 1: LEADS IN TASK */}
          {taskSubTab === 'leads' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Filter Bar */}
              <div className="outreach-panel" style={{ padding: 14 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, flex: 1 }}>
                    <div style={{ position: 'relative', minWidth: 240 }}>
                      <input
                        type="text"
                        placeholder="Поиск по компании, email, телефону..."
                        value={searchFilter}
                        onChange={(e) => setSearchFilter(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && fetchLeads(selectedTask.id, 1, searchFilter, statusFilter, selectedWave)}
                        style={{ paddingLeft: 30 }}
                      />
                      <Search size={14} style={{ position: 'absolute', left: 9, top: 11, color: '#94a3b8' }} />
                    </div>

                    <select
                      value={statusFilter}
                      onChange={(e) => {
                        setStatusFilter(e.target.value)
                        fetchLeads(selectedTask.id, 1, searchFilter, e.target.value, selectedWave)
                      }}
                      style={{ width: 130 }}
                    >
                      <option value="">Все статусы</option>
                      <option value="new">Новый</option>
                      <option value="sent">Отправлено</option>
                      <option value="replied">Ответил</option>
                      <option value="spam">Спам</option>
                    </select>

                    <button
                      type="button"
                      onClick={() => fetchLeads(selectedTask.id, 1, searchFilter, statusFilter, selectedWave)}
                      className="outreach-btn outreach-btn-primary"
                    >
                      Найти
                    </button>
                  </div>
                </div>
              </div>

              {/* Selection Action Bar (when 1+ items selected) */}
              {selectedLeadIds.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div className="outreach-action-bar">
                    <strong style={{ color: '#1e40af', fontSize: 13 }}>
                      {selectAllAcrossPages
                        ? `✓ Выбраны ВСЕ ${leadTotal} контактов задачи`
                        : `Выбрано контактов: ${selectedLeadIds.length} на текущей странице (из ${leadTotal} всего)`}
                    </strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        onClick={handleSendSelectedToCampaign}
                        className="outreach-btn outreach-btn-emerald"
                      >
                        <Send size={14} />
                        <span>Отправить в рассылку ({selectAllAcrossPages ? leadTotal : selectedLeadIds.length})</span>
                      </button>
                      <button
                        type="button"
                        onClick={handleSendSelectedToCompose}
                        className="outreach-btn outreach-btn-indigo"
                      >
                        <PenTool size={14} />
                        <span>Написать письмо</span>
                      </button>
                      <button
                        type="button"
                        onClick={handleDeleteSelectedLeads}
                        className="outreach-btn outreach-btn-danger"
                      >
                        <Trash2 size={14} />
                        <span>Удалить ({selectAllAcrossPages ? leadTotal : selectedLeadIds.length})</span>
                      </button>
                    </div>
                  </div>

                  {leadTotal > leads.length && selectedLeadIds.length === leads.length && (
                    <div style={{ padding: '8px 14px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#1e40af' }}>
                      <span>
                        {selectAllAcrossPages
                          ? `✓ Выбраны все ${leadTotal} контактов по этой задаче.`
                          : `Выбраны все ${leads.length} контактов на текущей странице.`}
                      </span>
                      {!selectAllAcrossPages ? (
                        <button
                          type="button"
                          onClick={() => setSelectAllAcrossPages(true)}
                          className="outreach-btn outreach-btn-secondary"
                          style={{ padding: '3px 10px', fontSize: 12, fontWeight: 700 }}
                        >
                          👉 Выбрать все {leadTotal} контактов в этой задаче
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setSelectAllAcrossPages(false)}
                          className="outreach-btn outreach-btn-ghost"
                          style={{ padding: '3px 10px', fontSize: 11 }}
                        >
                          Оставить только текущую страницу
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* CRM Leads Table */}
              <div className="outreach-panel" style={{ padding: 0, overflow: 'hidden' }}>
                <div className="outreach-table-wrap" style={{ border: 'none', borderRadius: 0 }}>
                  <table className="outreach-table">
                    <thead>
                      <tr>
                        <th style={{ width: 36, textAlign: 'center' }}>
                          <span
                            onClick={handleSelectAllLeads}
                            style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}
                          >
                            {selectedLeadIds.length === leads.length && leads.length > 0 ? (
                              <CheckSquare size={16} style={{ color: '#0f766e' }} />
                            ) : (
                              <Square size={16} style={{ color: '#94a3b8' }} />
                            )}
                          </span>
                        </th>
                        <th>Компания & Профиль</th>
                        <th style={{ width: 130 }}>Итерация</th>
                        <th>Email</th>
                        <th>Телефон</th>
                        <th>Сайт</th>
                        <th style={{ textAlign: 'center' }}>MX</th>
                        <th style={{ textAlign: 'center' }}>Статус</th>
                        <th style={{ textAlign: 'right' }}>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loading ? (
                        <tr>
                          <td colSpan={9} style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
                            <RefreshCw size={22} className="animate-spin" style={{ margin: '0 auto 8px', color: '#0f766e' }} />
                            Загрузка контактов задачи...
                          </td>
                        </tr>
                      ) : leads.length === 0 ? (
                        <tr>
                          <td colSpan={9} style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
                            Контакты по этой задаче не найдены.
                          </td>
                        </tr>
                      ) : (
                        leads.map((lead) => {
                          const isSelected = selectedLeadIds.includes(lead.id)
                          return (
                            <tr key={lead.id} className={isSelected ? 'selected' : ''}>
                              <td style={{ textAlign: 'center' }}>
                                <span
                                  onClick={() => handleToggleLead(lead.id)}
                                  style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}
                                >
                                  {isSelected ? (
                                    <CheckSquare size={16} style={{ color: '#0f766e' }} />
                                  ) : (
                                    <Square size={16} style={{ color: '#cbd5e1' }} />
                                  )}
                                </span>
                              </td>
                              <td>
                                <div style={{ fontWeight: 700, color: '#0f172a' }}>{lead.company_name}</div>
                                {lead.activity_profile && (
                                  <div style={{ color: '#64748b', fontSize: 11, maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {lead.activity_profile}
                                  </div>
                                )}
                              </td>
                              <td>
                                <span
                                  style={{
                                    padding: '2px 8px',
                                    borderRadius: 6,
                                    fontSize: 11,
                                    fontWeight: 600,
                                    background: !lead.wave_index || lead.wave_index === 1 ? '#f1f5f9' : '#ecfdf5',
                                    color: !lead.wave_index || lead.wave_index === 1 ? '#475569' : '#047857',
                                    border: !lead.wave_index || lead.wave_index === 1 ? '1px solid #e2e8f0' : '1px solid #a7f3d0',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 4,
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {lead.wave_index && lead.wave_index > 1 ? `Добор #${lead.wave_index - 1}` : 'Поиск 1'}
                                </span>
                              </td>
                              <td style={{ fontFamily: 'ui-monospace, monospace', color: '#2563eb', fontWeight: 600 }}>
                                {lead.email}
                              </td>
                              <td style={{ color: '#475569' }}>{lead.phone || '—'}</td>
                              <td>
                                {lead.website ? (
                                  <a
                                    href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ color: '#64748b', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                                  >
                                    <span>{lead.website.replace(/^https?:\/\//, '')}</span>
                                    <ExternalLink size={12} />
                                  </a>
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td style={{ textAlign: 'center' }}>
                                {lead.mx_valid ? (
                                  <span style={{ color: '#059669', fontWeight: 700 }}>✓ Да</span>
                                ) : (
                                  <span style={{ color: '#f87171' }}>✕ Нет</span>
                                )}
                              </td>
                              <td style={{ textAlign: 'center' }}>
                                <span className={`outreach-badge ${lead.status}`}>
                                  {getStatusLabel(lead.status)}
                                </span>
                              </td>
                              <td style={{ textAlign: 'right' }}>
                                <div style={{ display: 'inline-flex', gap: 4 }}>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setComposeRecipients([lead.email])
                                      changeMainTab('compose')
                                    }}
                                    className="outreach-btn outreach-btn-secondary"
                                    style={{ padding: '3px 8px', fontSize: 11 }}
                                  >
                                    <PenTool size={12} />
                                    <span>Написать</span>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleOpenLeadHistory(lead)}
                                    className="outreach-btn outreach-btn-ghost"
                                    style={{ padding: '3px 6px' }}
                                    title="История переписки"
                                  >
                                    <History size={13} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div style={{ padding: '10px 16px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12, color: '#64748b' }}>
                  <div>
                    Показано {(page - 1) * 50 + 1} - {Math.min(page * 50, leadTotal)} из {leadTotal} контактов
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button
                      type="button"
                      disabled={page <= 1}
                      onClick={() => fetchLeads(selectedTask.id, page - 1, searchFilter, statusFilter)}
                      className="outreach-btn outreach-btn-secondary"
                      style={{ padding: '4px 8px' }}
                    >
                      <ChevronLeft size={14} />
                    </button>
                    <span style={{ fontWeight: 700 }}>Страница {page}</span>
                    <button
                      type="button"
                      disabled={page * 50 >= leadTotal}
                      onClick={() => fetchLeads(selectedTask.id, page + 1, searchFilter, statusFilter)}
                      className="outreach-btn outreach-btn-secondary"
                      style={{ padding: '4px 8px' }}
                    >
                      <ChevronRight size={14} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SUBTAB 2: CAMPAIGN IN TASK */}
          {taskSubTab === 'campaign' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Campaign Composer Form (Full Width) */}
              <div className="outreach-panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 12 }}>
                  <div>
                    <h2 className="outreach-panel-title">Email-рассылка по задаче «{selectedTask.name}»</h2>
                    <p className="outreach-panel-desc">
                      Персональная отправка писем по базе контактов текущей задачи с AI-помощником.
                    </p>
                  </div>
                  {campaigns.some((c) => c.status === 'running') && (
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 12px', background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: 999, fontSize: 11, color: '#047857', fontWeight: 600 }}>
                      <span className="outreach-live-dot" />
                      <span>Рассылка идет онлайн (автообновление)</span>
                    </div>
                  )}
                </div>

                <form onSubmit={handleCreateCampaign} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <label style={{ fontSize: 12, fontWeight: 600, color: '#334155' }}>
                        Аудитория получателей:
                      </label>
                      <button
                        type="button"
                        onClick={() => {
                          setCampAudienceType('unanswered')
                          const followTpl = templates.find((t) => t.id === 'follow_up') || templates[0]
                          if (followTpl) {
                            setCampSubject(followTpl.subject)
                            setCampBody(followTpl.body)
                          }
                        }}
                        className="outreach-btn outreach-btn-amber"
                        style={{ padding: '2px 8px', fontSize: 11, minHeight: 24 }}
                        title="Настроить рассылку тем, кто получил первое письмо, но еще не ответил"
                      >
                        <RotateCcw size={12} />
                        <span>Режим Follow-up</span>
                      </button>
                    </div>
                    <select
                      value={campAudienceType}
                      onChange={(e) => setCampAudienceType(e.target.value as any)}
                      style={{ fontWeight: 600 }}
                    >
                      <option value="new">
                        🟢 Только новым (еще не отправленным) ({taskStats?.new_leads ?? selectedTask.collected_count} шт.)
                      </option>
                      <option value="unanswered">
                        🟡 Follow-up: тем, кто получил письмо, но не ответил ({Math.max(0, (taskStats?.sent_leads ?? 0) - (taskStats?.replied_leads ?? 0))} шт.)
                      </option>
                      <option value="all">
                        🔵 Всем контактам этой задачи ({selectedTask.collected_count} шт.)
                      </option>
                      {selectedLeadIds.length > 0 && !selectAllAcrossPages && (
                        <option value="selected">
                          🎯 Выбранным вручную в CRM контактам ({selectedLeadIds.length} шт.)
                        </option>
                      )}
                    </select>
                  </div>

                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, flexWrap: 'wrap', gap: 6 }}>
                      <label style={{ fontSize: 12, fontWeight: 600, color: '#334155' }}>
                        Тема письма:
                      </label>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => handleAiAction('subject', 'campaign')}
                          disabled={campAiGenerating}
                          className="outreach-btn outreach-btn-indigo"
                          style={{ padding: '2px 8px', fontSize: 11, minHeight: 26 }}
                          title="Сгенерировать привлекательную тему рассылки с AI"
                        >
                          <Sparkles size={12} />
                          <span>AI Тема</span>
                        </button>

                        <select
                          value=""
                          onChange={(e) => {
                            const val = e.target.value
                            if (val === '__manage__') {
                              handleOpenTemplateModal('campaign')
                              return
                            }
                            if (val === '__save_current__') {
                              handleSaveCurrentAsTemplate('campaign')
                              return
                            }
                            const tpl = templates.find((t) => t.id === val)
                            if (tpl) handleApplyTemplate(tpl, 'campaign')
                          }}
                          style={{ width: 'auto', minWidth: 160, height: 26, fontSize: 11, padding: '0 6px' }}
                        >
                          <option value="" disabled>📋 Выбрать шаблон ({templates.length})...</option>
                          {templates.map((t) => (
                            <option key={t.id} value={t.id}>{t.name}</option>
                          ))}
                          <option disabled>──────────</option>
                          <option value="__save_current__">💾 Сохранить это письмо как шаблон</option>
                          <option value="__manage__">⚙️ Управление шаблонами...</option>
                        </select>
                      </div>
                    </div>
                    <input
                      type="text"
                      required
                      placeholder="Тема рассылки..."
                      value={campSubject}
                      onChange={(e) => setCampSubject(e.target.value)}
                      style={{ fontWeight: 600 }}
                    />
                  </div>

                  {/* Formatting & AI Toolbar for Campaign (No variable chips) */}
                  <div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 6, background: '#f8fafc', border: '1px solid #cbd5e1', borderBottom: 'none', borderRadius: '8px 8px 0 0', padding: '6px 10px' }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 4 }}>
                        <button
                          type="button"
                          onClick={() => setCampBody((prev) => `**${prev}**`)}
                          className="outreach-btn outreach-btn-ghost"
                          style={{ padding: '2px 6px', minHeight: 24 }}
                          title="Жирный"
                        >
                          <Bold size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setCampBody((prev) => `*${prev}*`)}
                          className="outreach-btn outreach-btn-ghost"
                          style={{ padding: '2px 6px', minHeight: 24 }}
                          title="Курсив"
                        >
                          <Italic size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setCampBody((prev) => `_${prev}_`)}
                          className="outreach-btn outreach-btn-ghost"
                          style={{ padding: '2px 6px', minHeight: 24 }}
                          title="Подчеркнутый"
                        >
                          <Underline size={13} />
                        </button>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => handleAiAction('cold_email', 'campaign')}
                          disabled={campAiGenerating}
                          className="outreach-btn outreach-btn-indigo"
                          style={{ padding: '3px 8px', fontSize: 11, minHeight: 24 }}
                        >
                          <Sparkles size={12} />
                          <span>{campAiGenerating ? 'AI пишет...' : '✨ Написать с AI'}</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleAiAction('improve', 'campaign')}
                          disabled={campAiGenerating || !campBody.trim()}
                          className="outreach-btn outreach-btn-secondary"
                          style={{ padding: '3px 8px', fontSize: 11, minHeight: 24 }}
                          title="Улучшить текст рассылки"
                        >
                          <Wand2 size={12} style={{ color: '#6366f1' }} />
                          <span>Улучшить</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleAiAction('shorten', 'campaign')}
                          disabled={campAiGenerating || !campBody.trim()}
                          className="outreach-btn outreach-btn-secondary"
                          style={{ padding: '3px 8px', fontSize: 11, minHeight: 24 }}
                          title="Сделать текст лаконичнее"
                        >
                          <Scissors size={12} style={{ color: '#f59e0b' }} />
                          <span>Сократить</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleAiAction('grammar', 'campaign')}
                          disabled={campAiGenerating || !campBody.trim()}
                          className="outreach-btn outreach-btn-secondary"
                          style={{ padding: '3px 8px', fontSize: 11, minHeight: 24 }}
                          title="Проверить орфографию и стиль"
                        >
                          <SpellCheck size={12} style={{ color: '#10b981' }} />
                          <span>Орфография</span>
                        </button>

                        <select
                          value={campTone}
                          onChange={(e) => setCampTone(e.target.value)}
                          style={{ width: 'auto', minWidth: 110, height: 26, fontSize: 11, padding: '0 4px' }}
                        >
                          <option value="professional">Деловой тон</option>
                          <option value="friendly">Дружелюбный</option>
                          <option value="selling">Продающий</option>
                          <option value="concise">Краткий</option>
                        </select>
                      </div>
                    </div>

                    <textarea
                      ref={campBodyRef}
                      rows={12}
                      required
                      style={{
                        borderRadius: '0 0 8px 8px',
                        borderTop: 'none',
                        height: `${campBodyHeight}px`,
                        minHeight: 120,
                        maxHeight: '85vh',
                        resize: 'vertical',
                        fontSize: 13.5,
                        lineHeight: 1.6,
                        padding: '12px 14px',
                        boxSizing: 'border-box',
                      }}
                      value={campBody}
                      onChange={(e) => setCampBody(e.target.value)}
                      placeholder="Текст рассылки..."
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <label style={{ fontSize: 12, fontWeight: 600, color: '#334155' }}>
                        Задержка между отправками:
                      </label>
                      <input
                        type="number"
                        step={0.5}
                        min={0.5}
                        max={60}
                        style={{ width: 75 }}
                        value={campDelay}
                        onChange={(e) => setCampDelay(parseFloat(e.target.value) || 2.0)}
                      />
                      <span style={{ fontSize: 12, color: '#64748b' }}>сек</span>
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="outreach-btn outreach-btn-emerald"
                      style={{ padding: '8px 22px', fontSize: 13, fontWeight: 700 }}
                    >
                      <Send size={15} />
                      <span>Запустить рассылку</span>
                    </button>
                  </div>

                  {/* Test Send */}
                  <div style={{ paddingTop: 14, borderTop: '1px solid #e2e8f0' }}>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                      Отправить тест на свою почту:
                    </label>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input
                        type="email"
                        placeholder="your-email@yandex.ru"
                        value={testEmail}
                        onChange={(e) => setTestEmail(e.target.value)}
                        style={{ flex: 1 }}
                      />
                      <button
                        type="button"
                        disabled={sendingTest}
                        onClick={handleTestSend}
                        className="outreach-btn outreach-btn-secondary"
                      >
                        {sendingTest ? 'Отправка...' : 'Отправить тест'}
                      </button>
                    </div>
                  </div>
                </form>
              </div>

              {/* Campaigns History (Always Below Form, Full Width) */}
              <div className="outreach-panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <h2 className="outreach-panel-title">Рассылки по этой задаче</h2>
                  {campaigns.length > 0 && (
                    <span style={{ fontSize: 12, color: '#64748b' }}>
                      Всего рассылок: <strong>{campaigns.length}</strong>
                    </span>
                  )}
                </div>

                {campaigns.length === 0 ? (
                  <p style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', padding: '30px 0' }}>
                    Рассылок по этой задаче пока не было.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {campaigns.map((c) => {
                      const percent = Math.min(100, Math.round(((c.sent_count || 0) / (c.total_recipients || 1)) * 100))
                      return (
                        <div
                          key={c.id}
                          style={{
                            padding: 14,
                            background: c.status === 'running' ? '#f0fdf4' : '#f8fafc',
                            border: c.status === 'running' ? '1px solid #86efac' : '1px solid #e2e8f0',
                            borderRadius: 8,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 8,
                            transition: 'all 0.2s ease',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                            <strong style={{ fontSize: 13, color: '#0f172a' }}>{c.name}</strong>
                            <span className={`outreach-badge ${c.status}`}>
                              {c.status === 'running' && <span className="outreach-live-dot" style={{ width: 6, height: 6 }} />}
                              {getStatusLabel(c.status)}
                            </span>
                          </div>

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: '#475569' }}>
                            <div>
                              Отправлено: <strong style={{ color: '#0f172a', fontSize: 13 }}>{c.sent_count}</strong> из{' '}
                              <strong style={{ color: '#0f172a' }}>{c.total_recipients}</strong>
                              <span style={{ marginLeft: 6, color: '#059669', fontWeight: 700 }}>({percent}%)</span>
                            </div>
                            {c.failed_count > 0 && (
                              <span style={{ fontSize: 11, color: '#dc2626', fontWeight: 600 }}>
                                {c.failed_count} сбоев
                              </span>
                            )}
                          </div>

                          <div style={{ width: '100%', height: 7, background: '#e2e8f0', borderRadius: 999, overflow: 'hidden' }}>
                            <div
                              style={{
                                height: '100%',
                                background: c.status === 'running' ? 'linear-gradient(90deg, #059669, #10b981)' : '#0f766e',
                                borderRadius: 999,
                                width: `${percent}%`,
                                transition: 'width 0.4s ease',
                              }}
                            />
                          </div>

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#94a3b8' }}>
                            <span>{formatDate(c.created_at)}</span>
                            <div style={{ display: 'flex', gap: 6 }}>
                              {c.status === 'running' && (
                                <button
                                  type="button"
                                  onClick={async () => {
                                    await outreachFetch(`/api/outreach/campaigns/${c.id}/pause`, { method: 'POST' })
                                    fetchCampaigns(selectedTask.id)
                                  }}
                                  className="outreach-btn outreach-btn-secondary"
                                  style={{ padding: '2px 8px', fontSize: 11, minHeight: 24 }}
                                >
                                  Пауза
                                </button>
                              )}
                              {c.status === 'paused' && (
                                <button
                                  type="button"
                                  onClick={async () => {
                                    await outreachFetch(`/api/outreach/campaigns/${c.id}/resume`, { method: 'POST' })
                                    fetchCampaigns(selectedTask.id)
                                  }}
                                  className="outreach-btn outreach-btn-emerald"
                                  style={{ padding: '2px 8px', fontSize: 11, minHeight: 24 }}
                                >
                                  Возобновить
                                </button>
                              )}
                              {(c.status === 'running' || c.status === 'paused') && (
                                <button
                                  type="button"
                                  onClick={async () => {
                                    if (window.confirm('Остановить рассылку навсегда?')) {
                                      await outreachFetch(`/api/outreach/campaigns/${c.id}/stop`, { method: 'POST' })
                                      fetchCampaigns(selectedTask.id)
                                    }
                                  }}
                                  className="outreach-btn outreach-btn-danger"
                                  style={{ padding: '2px 8px', fontSize: 11, minHeight: 24 }}
                                >
                                  Стоп
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )}

  {/* ========================================================================= */}
  {/* TAB 2: GLOBAL INBOX (info@tenderlex.ru)                                    */}
  {/* ========================================================================= */}
  {mainTab === 'inbox' && (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="outreach-panel" style={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, flexWrap: 'wrap' }}>
            <select
              value={inboxTaskFilter}
              onChange={(e) => {
                const val = e.target.value
                setInboxTaskFilter(val)
                setInboxLimit(50)
                fetchInbox(val || null, inboxFilter, inboxSearch, 50)
              }}
              style={{ height: 32, fontSize: 12, fontWeight: 600, padding: '0 8px', maxWidth: 220 }}
            >
              <option value="">🌐 Все задачи и внешние ответы</option>
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  📁 {t.name}
                </option>
              ))}
            </select>

            <div style={{ position: 'relative', minWidth: 220 }}>
              <input
                type="text"
                placeholder="Поиск по входящим ответам..."
                value={inboxSearch}
                onChange={(e) => setInboxSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    setInboxLimit(50)
                    fetchInbox(inboxTaskFilter || null, inboxFilter, inboxSearch, 50)
                  }
                }}
                style={{ paddingLeft: 28, height: 32, fontSize: 12 }}
              />
              <Search size={13} style={{ position: 'absolute', left: 8, top: 10, color: '#94a3b8' }} />
            </div>

            <div style={{ display: 'inline-flex', background: '#f1f5f9', borderRadius: 8, padding: 2, gap: 2, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => {
                  setInboxFilter('all')
                  setInboxLimit(50)
                  fetchInbox(inboxTaskFilter || null, 'all', inboxSearch, 50)
                }}
                className={`outreach-btn ${inboxFilter === 'all' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                style={{ minHeight: 26, padding: '2px 8px', fontSize: 11 }}
              >
                Все ({inboxCounts.all})
              </button>
              <button
                type="button"
                onClick={() => {
                  setInboxFilter('replies')
                  setInboxLimit(50)
                  fetchInbox(inboxTaskFilter || null, 'replies', inboxSearch, 50)
                }}
                className={`outreach-btn ${inboxFilter === 'replies' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                style={{ minHeight: 26, padding: '2px 8px', fontSize: 11, background: inboxFilter === 'replies' ? '#059669' : void 0, color: inboxFilter === 'replies' ? '#fff' : '#047857', borderColor: '#a7f3d0' }}
              >
                🟢 Живые ответы ({inboxCounts.replies})
              </button>
              <button
                type="button"
                onClick={() => {
                  setInboxFilter('auto_replies')
                  setInboxLimit(50)
                  fetchInbox(inboxTaskFilter || null, 'auto_replies', inboxSearch, 50)
                }}
                className={`outreach-btn ${inboxFilter === 'auto_replies' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                style={{ minHeight: 26, padding: '2px 8px', fontSize: 11, background: inboxFilter === 'auto_replies' ? '#d97706' : void 0, color: inboxFilter === 'auto_replies' ? '#fff' : '#b45309', borderColor: '#fde68a' }}
              >
                🟡 Автоответы ({inboxCounts.auto_replies})
              </button>
              <button
                type="button"
                onClick={() => {
                  setInboxFilter('bounces')
                  setInboxLimit(50)
                  fetchInbox(inboxTaskFilter || null, 'bounces', inboxSearch, 50)
                }}
                className={`outreach-btn ${inboxFilter === 'bounces' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                style={{ minHeight: 26, padding: '2px 8px', fontSize: 11, background: inboxFilter === 'bounces' ? '#dc2626' : void 0, color: inboxFilter === 'bounces' ? '#fff' : '#b91c1c', borderColor: '#fca5a5' }}
              >
                🔴 Ошибки доставки ({inboxCounts.bounces})
              </button>
              <button
                type="button"
                onClick={() => {
                  setInboxFilter('unread')
                  setInboxLimit(50)
                  fetchInbox(inboxTaskFilter || null, 'unread', inboxSearch, 50)
                }}
                className={`outreach-btn ${inboxFilter === 'unread' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                style={{ minHeight: 26, padding: '2px 8px', fontSize: 11 }}
              >
                Новые ({inboxCounts.unread})
              </button>
              <button
                type="button"
                onClick={() => {
                  setInboxFilter('spam')
                  setInboxLimit(50)
                  fetchInbox(inboxTaskFilter || null, 'spam', inboxSearch, 50)
                }}
                className={`outreach-btn ${inboxFilter === 'spam' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                style={{ minHeight: 26, padding: '2px 8px', fontSize: 11 }}
              >
                Спам ({inboxCounts.spam})
              </button>
            </div>

            {/* Auto-sync indicator */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#64748b', background: '#f8fafc', padding: '3px 8px', borderRadius: 6, border: '1px solid #e2e8f0' }}>
              {syncingInbox ? (
                <>
                  <RefreshCw size={11} className="animate-spin" style={{ color: '#2563eb' }} />
                  <span style={{ color: '#2563eb', fontWeight: 600 }}>Синхронизация...</span>
                </>
              ) : (
                <>
                  <span className="outreach-live-dot" style={{ width: 6, height: 6 }} />
                  <span style={{ color: '#059669', fontWeight: 600 }}>Автосинхронизация каждые 30 сек</span>
                </>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Mark All Read Button */}
            {(inboxCounts.bounces > 0 || inboxCounts.spam > 0 || inboxCounts.unread > 0 || inboxFilter === 'bounces' || inboxFilter === 'spam') && (
              <button
                type="button"
                onClick={() => handleMarkAllRead()}
                className="outreach-btn outreach-btn-secondary"
                style={{
                  padding: '4px 10px',
                  fontSize: 11,
                  minHeight: 30,
                  color: '#0f766e',
                  borderColor: '#99f6e4',
                  background: '#f0fdfa',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  fontWeight: 600,
                }}
                title="Отметить все письма в текущей вкладке прочитанными"
              >
                <CheckCircle2 size={13} />
                <span>
                  {inboxFilter === 'bounces'
                    ? `Отметить все ошибки прочитанными (${inboxCounts.bounces})`
                    : inboxFilter === 'spam'
                    ? `Отметить весь спам прочитанным (${inboxCounts.spam})`
                    : inboxFilter === 'unread'
                    ? `Отметить все новые прочитанными (${inboxCounts.unread})`
                    : `Отметить все прочитанными`}
                </span>
              </button>
            )}

            {inboxFilter === 'spam' && inboxCounts.spam > 0 && (
              <button
                type="button"
                onClick={handlePurgeSpam}
                className="outreach-btn"
                style={{ padding: '4px 10px', fontSize: 11, minHeight: 30, background: '#fef2f2', color: '#b91c1c', border: '1px solid #fca5a5' }}
                title="Удалить все спам-письма"
              >
                <Trash2 size={12} />
                <span>Очистить весь спам ({inboxCounts.spam})</span>
              </button>
            )}

            <button
              type="button"
              onClick={handleSyncInbox}
              disabled={syncingInbox}
              className="outreach-btn outreach-btn-secondary"
              style={{ padding: '4px 10px', fontSize: 11, minHeight: 30 }}
            >
              <RefreshCw size={12} className={syncingInbox ? 'animate-spin' : ''} />
              <span>Синхронизировать сейчас</span>
            </button>
          </div>
        </div>
      </div>

      {/* Inbox Split View (Left: List, Right: Message) */}
      <div className="outreach-inbox-split">
        {/* Messages List Pane (Left) */}
        <div className="outreach-inbox-list">
          {inboxMessages.length === 0 ? (
            <div style={{ padding: '40px 16px', textAlign: 'center', color: '#94a3b8' }}>
              <Inbox size={30} style={{ margin: '0 auto 8px', opacity: 0.6 }} />
              <p style={{ margin: 0, fontWeight: 600, fontSize: 12.5 }}>Входящих писем пока нет</p>
              <p style={{ margin: '4px 0 0', fontSize: 11 }}>
                Новые ответы на адрес info@tenderlex.ru появляются здесь автоматически.
              </p>
            </div>
          ) : (
            <>
              {inboxMessages.map((msg) => {
                const isSelected = selectedMsg?.id === msg.id
                const isBounce = msg.category === 'bounce'
                const isSpam = msg.is_spam || msg.category === 'spam'
                const displayName = isBounce
                  ? (msg.lead_company || msg.lead_email || msg.sender_name || msg.sender_email)
                  : (msg.sender_name || msg.sender_email.split('@')[0])
                const initial = isSpam ? '🚫' : isBounce ? '⚠️' : (displayName || 'U').charAt(0).toUpperCase()
                const avatarBg = isSpam ? '#fee2e2' : isBounce ? '#fee2e2' : getAvatarColor(msg.sender_name || msg.sender_email)
                const avatarColor = isSpam || isBounce ? '#dc2626' : '#ffffff'
                const isUnread = !msg.is_read
                return (
                  <div
                    key={msg.id}
                    onClick={() => {
                      setSelectedMsg(msg)
                      if (isUnread) {
                        setInboxMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, is_read: true } : m)))
                        setInboxCounts((prev) => ({ ...prev, unread: Math.max(0, prev.unread - 1) }))
                        outreachFetch(`/api/outreach/inbox/${msg.id}/read`, {
                          method: 'PATCH',
                          body: JSON.stringify({ is_read: true }),
                        })
                      }
                    }}
                    className={`outreach-inbox-item ${isUnread ? 'unread' : 'read'} ${isSelected ? 'selected' : ''}`}
                    style={isSpam ? { borderLeft: '3px solid #dc2626' } : isBounce ? { borderLeft: '3px solid #ef4444' } : undefined}
                  >
                    {/* Read / Unread Circle Toggle Indicator */}
                    <div
                      onClick={(e) => handleToggleRead(e, msg)}
                      className="outreach-inbox-read-toggle"
                      title={isUnread ? "Пометить прочитанным" : "Пометить непрочитанным"}
                    >
                      {isUnread ? (
                        <div className="outreach-inbox-read-dot-unread" />
                      ) : (
                        <div className="outreach-inbox-read-dot-read" />
                      )}
                    </div>

                    <div className="outreach-inbox-avatar" style={{ background: avatarBg, color: avatarColor }}>{initial}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
                          <strong style={{ fontSize: 12, color: isSpam ? '#b91c1c' : isBounce ? '#b91c1c' : isUnread ? '#0f172a' : '#475569', fontWeight: isUnread ? 750 : 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {displayName}
                          </strong>
                        </div>
                        <span style={{ fontSize: 10, color: isUnread ? '#2563eb' : '#94a3b8', fontWeight: isUnread ? 600 : 400, flexShrink: 0 }}>{formatDate(msg.date_received)}</span>
                      </div>
                      <div style={{ fontSize: 11.5, fontWeight: isUnread ? 700 : 400, color: isUnread ? '#0f172a' : '#334155', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 2 }}>
                        {msg.subject || '(Без темы)'}
                      </div>
                      <div style={{ fontSize: 11, color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 2 }}>
                        {msg.body_text}
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4, alignItems: 'center' }}>
                        {isUnread && (
                          <span className="outreach-badge new" style={{ padding: '1px 5px', fontSize: 9 }}>
                            Новое
                          </span>
                        )}
                        {isSpam ? (
                          <span style={{ background: '#fee2e2', color: '#b91c1c', border: '1px solid #fecaca', padding: '1px 5px', borderRadius: 4, fontSize: 10, fontWeight: 700 }}>
                            🚫 Спам
                          </span>
                        ) : isBounce ? (
                          <span style={{ background: '#fee2e2', color: '#b91c1c', border: '1px solid #fecaca', padding: '1px 5px', borderRadius: 4, fontSize: 10, fontWeight: 700 }}>
                            🔴 Не доставлено
                          </span>
                        ) : msg.category === 'auto_reply' ? (
                          <span style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a', padding: '1px 5px', borderRadius: 4, fontSize: 10, fontWeight: 600 }}>
                            🟡 Автоответ
                          </span>
                        ) : (
                          <span style={{ background: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0', padding: '1px 5px', borderRadius: 4, fontSize: 10, fontWeight: 600 }}>
                            🟢 Ответ
                          </span>
                        )}
                        {msg.task_name && (
                          <span style={{ background: '#f1f5f9', color: '#475569', border: '1px solid #e2e8f0', padding: '1px 5px', borderRadius: 4, fontSize: 9.5, fontWeight: 600 }}>
                            📁 {msg.task_name}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}

              {inboxTotal > inboxMessages.length && (
                <div style={{ padding: '8px 12px', borderTop: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: '#64748b' }}>
                    Показано <strong>{inboxMessages.length}</strong> из <strong>{inboxTotal}</strong> писем
                  </span>
                  <button
                    type="button"
                    onClick={handleLoadMoreInbox}
                    disabled={loadingMoreInbox}
                    className="outreach-btn outreach-btn-secondary"
                    style={{ width: '100%', padding: '6px 12px', fontSize: 11.5, minHeight: 30, justifyContent: 'center' }}
                  >
                    {loadingMoreInbox ? (
                      <>
                        <RefreshCw size={12} className="animate-spin" />
                        <span>Загрузка писем...</span>
                      </>
                    ) : (
                      <span>Показать ещё 50 писем</span>
                    )}
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Message Detail Pane (Right) */}
        <div className="outreach-inbox-detail">
          {selectedMsg ? (
            <>
              {/* Top Header */}
              <div className="outreach-inbox-detail-header">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#0f172a' }}>
                      {selectedMsg.subject || '(Без темы)'}
                    </h3>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: '#0f172a' }}>
                        {selectedMsg.sender_name || selectedMsg.sender_email}
                      </span>
                      <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                        &lt;{selectedMsg.sender_email}&gt;
                      </span>
                      <span style={{ fontSize: 11, color: '#94a3b8' }}>
                        {formatDate(selectedMsg.date_received)}
                      </span>
                      {selectedMsg.is_spam && (
                        <span style={{ background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5', padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700 }}>
                          🚫 Спам
                        </span>
                      )}
                    </div>
                    {(selectedMsg.lead_company || selectedMsg.task_name) && (
                      <div style={{ fontSize: 11, color: '#047857', fontWeight: 600, marginTop: 3, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                        {selectedMsg.lead_company && <span>🏢 {selectedMsg.lead_company}</span>}
                        {selectedMsg.lead_email && <span>• ✉️ {selectedMsg.lead_email}</span>}
                        {selectedMsg.lead_phone && <span>• 📞 {selectedMsg.lead_phone}</span>}
                        {selectedMsg.task_name && <span>• 🎯 {selectedMsg.task_name}</span>}
                      </div>
                    )}

                    {selectedMsg.category === 'bounce' && (
                      <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', color: '#991b1b', padding: '8px 12px', borderRadius: 6, fontSize: 12, marginTop: 8 }}>
                        <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                          🔴 Сбой доставки письма (Bounce / Non-Delivery Report)
                        </div>
                        <div style={{ marginTop: 3 }}>
                          Получатель: <strong>{selectedMsg.lead_email || 'Указан в отчёте ниже'}</strong> {selectedMsg.lead_company && `(Компания: ${selectedMsg.lead_company})`}
                        </div>
                        {selectedMsg.lead_notes && (
                          <div style={{ fontSize: 11, color: '#b91c1c', marginTop: 3 }}>
                            {selectedMsg.lead_notes}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                    <button
                      type="button"
                      onClick={async () => {
                        const newStatus = !selectedMsg.is_read
                        const targetId = selectedMsg.id
                        setSelectedMsg({ ...selectedMsg, is_read: newStatus })
                        setInboxMessages((prev) =>
                          inboxFilterRef.current === 'unread' && newStatus
                            ? prev.filter((m) => m.id !== targetId)
                            : prev.map((m) => (m.id === targetId ? { ...m, is_read: newStatus } : m))
                        )
                        if (inboxFilterRef.current === 'unread' && newStatus) {
                          setInboxTotal((prev) => Math.max(0, prev - 1))
                        }
                        setInboxCounts((prev) => ({
                          ...prev,
                          unread: newStatus ? Math.max(0, prev.unread - 1) : prev.unread + 1,
                        }))
                        await outreachFetch(`/api/outreach/inbox/${targetId}/${newStatus ? 'read' : 'unread'}`, {
                          method: 'PATCH',
                          body: JSON.stringify({ is_read: newStatus }),
                        })
                      }}
                      className="outreach-btn outreach-btn-ghost"
                      style={{ padding: '4px 8px', fontSize: 11 }}
                      title={selectedMsg.is_read ? 'Отметить как непрочитанное' : 'Отметить как прочитанное'}
                    >
                      {selectedMsg.is_read ? <Mail size={13} /> : <MailCheck size={13} />}
                      <span>{selectedMsg.is_read ? 'Не прочитано' : 'Прочитано'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleToggleSpam(selectedMsg)}
                      className="outreach-btn outreach-btn-ghost"
                      style={{ padding: '4px 8px', fontSize: 11, color: selectedMsg.is_spam ? '#2563eb' : '#64748b' }}
                      title="Спам"
                    >
                      <ShieldAlert size={13} />
                      <span>{selectedMsg.is_spam ? 'Не спам' : 'В спам'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleDeleteInboxMsg(selectedMsg.id)}
                      className="outreach-btn outreach-btn-ghost"
                      style={{ padding: '4px 8px', fontSize: 11, color: '#ef4444' }}
                      title="Удалить письмо"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Body Text */}
              <div className="outreach-inbox-detail-body">
                {selectedMsg.is_spam && (
                  <div style={{ margin: '0 0 14px 0', padding: '10px 14px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, fontSize: 12, color: '#991b1b', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <ShieldAlert size={18} style={{ color: '#ef4444', flexShrink: 0 }} />
                      <span><strong>Спам-фильтр:</strong> Письмо изолировано от живых ответов и входящих.</span>
                    </div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        onClick={() => handleToggleSpam(selectedMsg)}
                        className="outreach-btn"
                        style={{ padding: '2px 8px', fontSize: 11, background: '#fff', border: '1px solid #fca5a5', color: '#b91c1c' }}
                      >
                        Восстановить (не спам)
                      </button>
                      <button
                        type="button"
                        onClick={() => handleBlockSender(selectedMsg)}
                        className="outreach-btn"
                        style={{ padding: '2px 8px', fontSize: 11, background: '#b91c1c', border: '1px solid #991b1b', color: '#fff', fontWeight: 600 }}
                        title="Навсегда заблокировать отправителя и его домен, удалить все письма"
                      >
                        🚫 Заблокировать спамщика
                      </button>
                    </div>
                  </div>
                )}
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, fontSize: 13, color: '#1e293b' }}>
                  {selectedMsg.body_text || '(Текст письма пуст)'}
                </div>
              </div>

              {/* Quick Reply Form (only for non-bounce, non-spam messages) */}
              {selectedMsg.category !== 'bounce' && !selectedMsg.is_spam ? (
                <div className="outreach-inbox-reply-box">
                  {/* AI Quick Reply Buttons */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Sparkles size={12} style={{ color: '#8b5cf6' }} />
                        Быстрый ответ с AI:
                      </span>
                      <button
                        type="button"
                        disabled={aiReplyGenerating}
                        onClick={() => handleAiReply('agree')}
                        className="outreach-btn outreach-btn-secondary"
                        style={{ padding: '2px 8px', fontSize: 11, minHeight: 24, background: '#ecfdf5', color: '#047857', borderColor: '#a7f3d0' }}
                      >
                        ✓ Согласиться
                      </button>
                      <button
                        type="button"
                        disabled={aiReplyGenerating}
                        onClick={() => handleAiReply('request_quote')}
                        className="outreach-btn outreach-btn-secondary"
                        style={{ padding: '2px 8px', fontSize: 11, minHeight: 24, background: '#eff6ff', color: '#1d4ed8', borderColor: '#bfdbfe' }}
                      >
                        📑 Запросить КП
                      </button>
                      <button
                        type="button"
                        disabled={aiReplyGenerating}
                        onClick={() => handleAiReply('decline')}
                        className="outreach-btn outreach-btn-secondary"
                        style={{ padding: '2px 8px', fontSize: 11, minHeight: 24, background: '#fef2f2', color: '#b91c1c', borderColor: '#fecaca' }}
                      >
                        ✕ Вежливый отказ
                      </button>
                    </div>
                  </div>

                  <textarea
                    rows={6}
                    placeholder="Напишите ответ поставщику или выберите быстрый шаблон ответа выше..."
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    style={{ minHeight: 125, maxHeight: 240, fontSize: 13, padding: '10px 12px', resize: 'vertical', lineHeight: 1.55 }}
                  />

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>
                      Ответ с адреса info@tenderlex.ru
                    </span>
                    <button
                      type="button"
                      onClick={handleSendReply}
                      disabled={sendingReply || !replyText.trim()}
                      className="outreach-btn outreach-btn-primary"
                      style={{ padding: '6px 16px', fontSize: 12, minHeight: 30 }}
                    >
                      <Send size={12} />
                      <span>{sendingReply ? 'Отправка...' : 'Отправить ответ'}</span>
                    </button>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <div style={{ padding: '60px 0', textAlign: 'center', color: '#94a3b8', margin: 'auto' }}>
              <Mail size={36} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
              <p style={{ margin: 0, fontWeight: 500 }}>Выберите письмо из списка слева</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )}

  {/* ========================================================================= */}
  {/* TAB 3: STANDALONE COMPOSE (info@tenderlex.ru)                              */}
  {/* ========================================================================= */}
  {mainTab === 'compose' && (
    <div className="outreach-panel" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12, borderBottom: '1px solid #e2e8f0' }}>
        <div className="outreach-composer-row">
          <span className="outreach-composer-label">От кого</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <strong style={{ fontSize: 13, color: '#0f172a' }}>
              {settings.from_name || 'TenderLex'} &lt;{settings.from_email || 'info@tenderlex.ru'}&gt;
            </strong>
            <span className="outreach-badge completed">SMTP готов</span>
          </div>
        </div>

        <div className="outreach-composer-row">
          <span className="outreach-composer-label">Кому</span>
          <div style={{ flex: 1, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, border: '1px solid #cbd5e1', borderRadius: 8, padding: '4px 8px', minHeight: 38, background: '#fff' }}>
            {composeRecipients.map((rec) => (
              <span
                key={rec}
                style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', borderRadius: 6, padding: '2px 6px', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                {rec}
                <button
                  type="button"
                  onClick={() => setComposeRecipients((prev) => prev.filter((r) => r !== rec))}
                  style={{ background: 'none', border: 'none', color: '#1d4ed8', cursor: 'pointer', padding: 0, fontSize: 14 }}
                >
                  ✕
                </button>
              </span>
            ))}
            <input
              type="email"
              placeholder={composeRecipients.length === 0 ? 'Введите email и нажмите Enter...' : 'Добавить email...'}
              value={composeRecipientInput}
              onChange={(e) => setComposeRecipientInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ',') {
                  e.preventDefault()
                  const val = composeRecipientInput.trim().replace(',', '')
                  if (val && val.includes('@') && !composeRecipients.includes(val)) {
                    setComposeRecipients((prev) => [...prev, val])
                    setComposeRecipientInput('')
                  }
                }
              }}
              onBlur={() => {
                const val = composeRecipientInput.trim().replace(',', '')
                if (val && val.includes('@') && !composeRecipients.includes(val)) {
                  setComposeRecipients((prev) => [...prev, val])
                  setComposeRecipientInput('')
                }
              }}
              style={{ border: 'none', outline: 'none', flex: 1, minWidth: 160, height: 26, fontSize: 12.5 }}
            />
          </div>
          <button
            type="button"
            onClick={handleOpenCrmPicker}
            className="outreach-btn outreach-btn-secondary"
            style={{ height: 38, fontSize: 12 }}
          >
            <Users size={13} />
            <span>Выбрать из CRM</span>
          </button>
          {composeRecipients.length > 0 && (
            <button
              type="button"
              onClick={() => setComposeRecipients([])}
              className="outreach-btn outreach-btn-ghost"
              style={{ height: 38, fontSize: 12, color: '#ef4444' }}
            >
              Очистить ({composeRecipients.length})
            </button>
          )}
        </div>

        <div className="outreach-composer-row">
          <span className="outreach-composer-label">Тема</span>
          <div style={{ flex: 1, display: 'flex', gap: 8 }}>
            <input
              type="text"
              placeholder="Тема письма..."
              value={composeSubject}
              onChange={(e) => setComposeSubject(e.target.value)}
              style={{ flex: 1, height: 36, fontSize: 13, fontWeight: 600 }}
            />
            <button
              type="button"
              disabled={aiGenerating}
              onClick={() => handleAiAction('subject', 'compose')}
              className="outreach-btn outreach-btn-secondary"
              style={{ height: 36, fontSize: 12 }}
            >
              <Sparkles size={13} style={{ color: '#8b5cf6' }} />
              <span>AI Тема</span>
            </button>
          </div>
        </div>

        {/* Template Selector for Compose */}
        <div className="outreach-composer-row">
          <span className="outreach-composer-label">Шаблон</span>
          <div style={{ flex: 1, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              onClick={() => handleOpenTemplateModal('compose')}
              className="outreach-btn outreach-btn-secondary"
              style={{ height: 32, fontSize: 12 }}
            >
              <LayoutTemplate size={13} style={{ color: '#0f766e' }} />
              <span>Библиотека шаблонов ({templates.length})</span>
            </button>
            <button
              type="button"
              onClick={() => handleSaveCurrentAsTemplate('compose')}
              className="outreach-btn outreach-btn-ghost"
              style={{ height: 32, fontSize: 11.5 }}
            >
              <Save size={12} />
              <span>Сохранить текущее как шаблон</span>
            </button>
          </div>
        </div>

        {/* AI Assistant Quick Tools */}
        <div className="outreach-composer-row" style={{ alignItems: 'flex-start' }}>
          <span className="outreach-composer-label" style={{ paddingTop: 6 }}>AI Помощник</span>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type="text"
                placeholder="Например: 'Предложи бесплатный аудит тендерных закупок'..."
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                style={{ flex: 1, height: 32, fontSize: 12 }}
              />
              <button
                type="button"
                disabled={aiGenerating}
                onClick={() => handleAiAction('cold_email', 'compose')}
                className="outreach-btn outreach-btn-primary"
                style={{ height: 32, fontSize: 12, padding: '0 12px' }}
              >
                <Sparkles size={13} className={aiGenerating ? 'animate-spin' : ''} />
                <span>{aiGenerating ? 'AI пишет...' : '✨ Написать с AI'}</span>
              </button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <button
                type="button"
                disabled={aiGenerating || !composeBody.trim()}
                onClick={() => handleAiAction('improve', 'compose')}
                className="outreach-btn outreach-btn-ghost"
                style={{ fontSize: 11, padding: '2px 8px', minHeight: 26 }}
              >
                <Wand2 size={11} />
                <span>Улучшить текст</span>
              </button>
              <button
                type="button"
                disabled={aiGenerating || !composeBody.trim()}
                onClick={() => handleAiAction('shorten', 'compose')}
                className="outreach-btn outreach-btn-ghost"
                style={{ fontSize: 11, padding: '2px 8px', minHeight: 26 }}
              >
                <Sliders size={11} />
                <span>Сделать короче</span>
              </button>
              <button
                type="button"
                disabled={aiGenerating || !composeBody.trim()}
                onClick={() => handleAiAction('grammar', 'compose')}
                className="outreach-btn outreach-btn-ghost"
                style={{ fontSize: 11, padding: '2px 8px', minHeight: 26 }}
              >
                <FileCheck size={11} />
                <span>Исправить ошибки</span>
              </button>

              <select
                value={composeTone}
                onChange={(e) => setComposeTone(e.target.value)}
                style={{ width: 'auto', minWidth: 120 }}
              >
                <option value="professional">Деловой тон</option>
                <option value="friendly">Дружелюбный</option>
                <option value="selling">Продающий</option>
                <option value="concise">Краткий</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Text Area */}
      <div style={{ padding: 16 }}>
        <textarea
          ref={composeBodyRef}
          rows={12}
          placeholder="Напишите текст письма здесь или используйте кнопку «✨ Написать с AI»..."
          value={composeBody}
          onChange={(e) => setComposeBody(e.target.value)}
          style={{
            border: 'none',
            outline: 'none',
            resize: 'vertical',
            width: '100%',
            height: `${composeBodyHeight}px`,
            minHeight: 120,
            maxHeight: '85vh',
            fontSize: 13.5,
            lineHeight: 1.6,
            padding: 0,
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Footer */}
      <div style={{ padding: '12px 18px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 12, color: '#64748b' }}>
          Получателей: <strong style={{ color: '#0f172a' }}>{composeRecipients.length}</strong>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {selectedTask && (
            <button
              type="button"
              onClick={() => {
                setCampSubject(composeSubject)
                setCampBody(composeBody)
                changeMainTab('tasks')
                changeTaskSubTab('campaign')
              }}
              className="outreach-btn outreach-btn-secondary"
            >
              Перенести в рассылку по задаче
            </button>
          )}

          <button
            type="button"
            disabled={sendingDirect || composeRecipients.length === 0}
            onClick={handleSendDirect}
            className="outreach-btn outreach-btn-primary"
            style={{ padding: '8px 18px', fontSize: 13 }}
          >
            <Send size={15} />
            <span>{sendingDirect ? 'Отправка...' : 'Отправить письмо сейчас'}</span>
          </button>
        </div>
      </div>
    </div>
  )}

  {/* ========================================================================= */}
  {/* TAB 4: MAIL SETTINGS (SMTP / IMAP / ANTI-SPAM)                            */}
  {/* ========================================================================= */}
  {mainTab === 'settings' && (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 720 }}>
      <div className="outreach-panel">
        <div>
          <h2 className="outreach-panel-title">Настройки почты и подключения</h2>
        <p className="outreach-panel-desc">
          Параметры SMTP для отправки писем и IMAP для чтения входящих ответов.
        </p>
      </div>

      <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <strong style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase' }}>Отправитель</strong>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                Имя отправителя:
              </label>
              <input
                type="text"
                value={settings.from_name || ''}
                onChange={(e) => setSettings({ ...settings, from_name: e.target.value })}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                Email отправителя:
              </label>
              <input
                type="email"
                value={settings.from_email || ''}
                onChange={(e) => setSettings({ ...settings, from_email: e.target.value })}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 12, borderTop: '1px solid #e2e8f0' }}>
          <strong style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase' }}>SMTP (Исходящая почта)</strong>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                SMTP Сервер:
              </label>
              <input
                type="text"
                value={settings.smtp_host || ''}
                onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                Порт:
              </label>
              <input
                type="number"
                value={settings.smtp_port || 465}
                onChange={(e) => setSettings({ ...settings, smtp_port: parseInt(e.target.value) || 465 })}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                SMTP Логин:
              </label>
              <input
                type="text"
                value={settings.smtp_user || ''}
                onChange={(e) => setSettings({ ...settings, smtp_user: e.target.value })}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                SMTP Пароль {settings.smtp_password_set && <span style={{ color: '#059669', fontWeight: 'normal' }}>(установлен)</span>}:
              </label>
              <input
                type="password"
                placeholder={settings.smtp_password_set ? '••••••••' : 'Введите пароль'}
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingTop: 12, borderTop: '1px solid #e2e8f0' }}>
          <strong style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase' }}>IMAP (Входящая почта)</strong>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                IMAP Сервер:
              </label>
              <input
                type="text"
                value={settings.imap_host || ''}
                onChange={(e) => setSettings({ ...settings, imap_host: e.target.value })}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                Порт:
              </label>
              <input
                type="number"
                value={settings.imap_port || 993}
                onChange={(e) => setSettings({ ...settings, imap_port: parseInt(e.target.value) || 993 })}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                IMAP Логин:
              </label>
              <input
                type="text"
                value={settings.imap_user || ''}
                onChange={(e) => setSettings({ ...settings, imap_user: e.target.value })}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                IMAP Пароль {settings.imap_password_set && <span style={{ color: '#059669', fontWeight: 'normal' }}>(установлен)</span>}:
              </label>
              <input
                type="password"
                placeholder={settings.imap_password_set ? '••••••••' : 'Введите пароль'}
                value={imapPassword}
                onChange={(e) => setImapPassword(e.target.value)}
                style={{ fontFamily: 'monospace' }}
              />
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 12, borderTop: '1px solid #e2e8f0' }}>
          <button
            type="submit"
            disabled={loading}
            className="outreach-btn outreach-btn-primary"
            style={{ padding: '8px 18px', fontSize: 13 }}
          >
            {loading ? 'Сохранение...' : 'Сохранить настройки'}
          </button>
        </div>
      </form>
    </div>

    {/* Anti-Spam & Blacklist Card */}
    <div className="outreach-panel" style={{ maxWidth: 720, marginTop: 16 }}>
      <div>
        <h2 className="outreach-panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ShieldAlert size={18} style={{ color: '#ef4444' }} />
          <span>🛡️ Антиспам-фильтр и чёрный список</span>
        </h2>
        <p className="outreach-panel-desc">
          Система автоматически изолирует рассылки одноразовых доменов (Makita, водонагреватели, таро, курсы, заработок на ИИ, базы РФ, Google Forms),
          а также блокирует добавленные вами домены и фразы.
        </p>
      </div>

      {/* Add rule input */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}>
        <select
          value={newSpamRuleType}
          onChange={(e) => setNewSpamRuleType(e.target.value)}
          style={{ width: 150, padding: '6px 8px', fontSize: 12, borderRadius: 6, border: '1px solid #cbd5e1', background: '#fff' }}
        >
          <option value="domain">Заблокировать домен</option>
          <option value="keyword">Заблокировать фразу</option>
          <option value="sender">Заблокировать email</option>
        </select>
        <input
          type="text"
          placeholder={newSpamRuleType === 'domain' ? 'например: spammers.shop' : newSpamRuleType === 'keyword' ? 'например: продажа баз данных' : 'например: spam@domain.com'}
          value={newSpamRuleVal}
          onChange={(e) => setNewSpamRuleVal(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddSpamRule(); } }}
          style={{ flex: 1, padding: '6px 10px', fontSize: 12, borderRadius: 6, border: '1px solid #cbd5e1' }}
        />
        <button
          type="button"
          onClick={handleAddSpamRule}
          disabled={savingSpamRule || !newSpamRuleVal.trim()}
          className="outreach-btn outreach-btn-primary"
          style={{ minHeight: 32, padding: '4px 12px', fontSize: 12 }}
        >
          {savingSpamRule ? 'Добавление...' : 'Добавить правило'}
        </button>
      </div>

      {/* Rules list */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Пользовательские правила блокировки ({spamRules.length}):</span>
          {spamRules.length > 0 && (
            <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 'normal' }}>
              Письма сразу отправляются в спам
            </span>
          )}
        </div>
        {spamRules.length === 0 ? (
          <div style={{ padding: '14px', background: '#f8fafc', borderRadius: 6, border: '1px dashed #cbd5e1', fontSize: 12, color: '#64748b', textAlign: 'center' }}>
            Пользовательских правил пока нет. При нажатии кнопки «В спам» во входящих спам-домены будут сохраняться сюда автоматически.
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, maxHeight: 180, overflowY: 'auto', padding: 8, background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
            {spamRules.map((rule, idx) => (
              <span
                key={idx}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  background: '#fff',
                  border: '1px solid #e2e8f0',
                  padding: '3px 8px',
                  borderRadius: 6,
                  fontSize: 11,
                  color: '#334155',
                }}
              >
                <span style={{ fontSize: 10, textTransform: 'uppercase', color: '#64748b', fontWeight: 600 }}>
                  {rule.type === 'domain' ? 'Домен' : rule.type === 'keyword' ? 'Фраза' : 'Email'}:
                </span>
                <strong style={{ color: '#0f172a' }}>{rule.value}</strong>
                <button
                  type="button"
                  onClick={() => handleDeleteSpamRule(idx)}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#94a3b8', padding: 0, display: 'flex', alignItems: 'center' }}
                  title="Удалить правило"
                >
                  <Trash2 size={11} style={{ color: '#ef4444' }} />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Built-in heuristics summary */}
      <div style={{ padding: '10px 12px', background: '#f1f5f9', borderRadius: 6, fontSize: 11, color: '#475569', lineHeight: 1.5 }}>
        <strong>🛡️ Встроенная защита ядра:</strong> Автоматически фильтрует известные спам-сетки (.shop, .pro, .life, .store), массовую рекламу инструментов (Makita), водонагревателей, эзотерики/курсов, инфо-цыган, коммерческих рассылок и фишинговые формы Google Forms.
      </div>
    </div>
  </div>
  )}

      {/* ==================== LEAD HISTORY MODAL ==================== */}
      {historyLead && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(15, 23, 42, 0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div style={{ background: '#fff', borderRadius: 10, width: '100%', maxWidth: 640, maxHeight: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)' }}>
            <div style={{ padding: '14px 18px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong style={{ fontSize: 14, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <History size={16} style={{ color: '#0f766e' }} />
                  История переписки: {historyLead.lead.company_name}
                </strong>
                <div style={{ fontSize: 12, color: '#64748b', fontFamily: 'monospace' }}>{historyLead.lead.email}</div>
              </div>
              <button
                type="button"
                onClick={() => setHistoryLead(null)}
                className="outreach-btn outreach-btn-ghost"
                style={{ padding: 4 }}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: 18, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, flex: 1 }}>
              {historyLead.sent.length === 0 && historyLead.incoming.length === 0 ? (
                <p style={{ textAlign: 'center', color: '#94a3b8', padding: '30px 0', fontSize: 12 }}>
                  История переписки с этим контактом пока пуста.
                </p>
              ) : (
                <>
                  {historyLead.sent.map((s, idx) => (
                    <div key={`sent-${idx}`} style={{ padding: 12, background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontWeight: 700, color: '#1e40af' }}>
                        <span>Исходящее письмо</span>
                        <span>{formatDate(s.sent_at)}</span>
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a' }}>{s.subject}</div>
                    </div>
                  ))}

                  {historyLead.incoming.map((m, idx) => (
                    <div key={`inc-${idx}`} style={{ padding: 12, background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontWeight: 700, color: '#065f46' }}>
                        <span>Входящий ответ</span>
                        <span>{formatDate(m.date_received)}</span>
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a' }}>{m.subject}</div>
                      <div style={{ fontSize: 12, color: '#334155', whiteSpace: 'pre-wrap', marginTop: 4 }}>{m.body_text}</div>
                    </div>
                  ))}
                </>
              )}
            </div>

            <div style={{ padding: '10px 18px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => {
                  setComposeRecipients([historyLead.lead.email])
                  setHistoryLead(null)
                  changeMainTab('compose')
                }}
                className="outreach-btn outreach-btn-primary"
              >
                <PenTool size={14} />
                <span>Написать письмо</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================== CRM PICKER MODAL ==================== */}
      {showCrmPickerModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(15, 23, 42, 0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div style={{ background: '#fff', borderRadius: 10, width: '100%', maxWidth: 680, maxHeight: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)' }}>
            <div style={{ padding: '14px 18px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong style={{ fontSize: 14, color: '#0f172a' }}>Выбрать получателей из базы CRM</strong>
                <div style={{ fontSize: 11, color: '#64748b' }}>
                  {crmPickerTaskFilter && tasks.find((t) => t.id === crmPickerTaskFilter)
                    ? `Задача: «${tasks.find((t) => t.id === crmPickerTaskFilter)?.name}»`
                    : 'Все контакты по всем задачам'}{' '}
                  ({crmPickerLeads.length} контактов)
                </div>
              </div>
              <button type="button" onClick={() => setShowCrmPickerModal(false)} className="outreach-btn outreach-btn-ghost" style={{ padding: 4 }}>
                ✕
              </button>
            </div>

            <div style={{ padding: '12px 18px', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: 10 }}>
              <select
                value={crmPickerTaskFilter}
                onChange={async (e) => {
                  const val = e.target.value
                  setCrmPickerTaskFilter(val)
                  setCrmPickerLoading(true)
                  try {
                    const url = val
                      ? `/api/outreach/leads?task_id=${val}&page=1&page_size=5000`
                      : `/api/outreach/leads?page=1&page_size=5000`
                    const data = await outreachFetch<{ items: Lead[] }>(url)
                    setCrmPickerLeads(data.items || [])
                  } catch (err: any) {
                    showError(err.message)
                  } finally {
                    setCrmPickerLoading(false)
                  }
                }}
                style={{ height: 32, fontSize: 11, padding: '0 8px', maxWidth: 180 }}
              >
                <option value="">Все задачи ({tasks.length})</option>
                {tasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>

              <div style={{ position: 'relative', flex: 1 }}>
                <input
                  type="text"
                  placeholder="Поиск по названию, email, телефону..."
                  value={crmPickerSearch}
                  onChange={(e) => setCrmPickerSearch(e.target.value)}
                  style={{ paddingLeft: 28, height: 32, fontSize: 12 }}
                />
                <Search size={13} style={{ position: 'absolute', left: 8, top: 9, color: '#94a3b8' }} />
              </div>
              <button
                type="button"
                onClick={() => {
                  const filtered = crmPickerLeads.filter(
                    (l) =>
                      !crmPickerSearch ||
                      l.company_name.toLowerCase().includes(crmPickerSearch.toLowerCase()) ||
                      l.email.toLowerCase().includes(crmPickerSearch.toLowerCase()) ||
                      (l.phone && l.phone.includes(crmPickerSearch))
                  )
                  setCrmPickerSelected(filtered.map((l) => l.email))
                }}
                className="outreach-btn outreach-btn-secondary"
                style={{ height: 32, fontSize: 11, padding: '0 10px' }}
              >
                Выбрать всех ({crmPickerLeads.length})
              </button>
              {crmPickerSelected.length > 0 && (
                <button
                  type="button"
                  onClick={() => setCrmPickerSelected([])}
                  className="outreach-btn outreach-btn-ghost"
                  style={{ height: 32, fontSize: 11, padding: '0 8px' }}
                >
                  Сбросить
                </button>
              )}
            </div>

            <div style={{ padding: '8px 18px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {crmPickerLoading ? (
                <div style={{ padding: '40px 0', textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
                  <RefreshCw size={18} className="animate-spin" style={{ margin: '0 auto 6px', color: '#0f766e' }} />
                  Загрузка контактов...
                </div>
              ) : crmPickerLeads.length === 0 ? (
                <div style={{ padding: '40px 0', textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
                  Контакты не найдены.
                </div>
              ) : (
                crmPickerLeads
                  .filter(
                    (l) =>
                      !crmPickerSearch ||
                      l.company_name.toLowerCase().includes(crmPickerSearch.toLowerCase()) ||
                      l.email.toLowerCase().includes(crmPickerSearch.toLowerCase()) ||
                      (l.phone && l.phone.includes(crmPickerSearch))
                  )
                  .map((l) => {
                    const isChecked = crmPickerSelected.includes(l.email)
                    return (
                      <div
                        key={l.id}
                        onClick={() => {
                          setCrmPickerSelected((prev) =>
                            prev.includes(l.email) ? prev.filter((e) => e !== l.email) : [...prev, l.email]
                          )
                        }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '6px 10px',
                          borderRadius: 6,
                          cursor: 'pointer',
                          background: isChecked ? '#eff6ff' : '#fff',
                          border: `1px solid ${isChecked ? '#bfdbfe' : '#f1f5f9'}`,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                          {isChecked ? (
                            <CheckSquare size={15} style={{ color: '#2563eb', flexShrink: 0 }} />
                          ) : (
                            <Square size={15} style={{ color: '#cbd5e1', flexShrink: 0 }} />
                          )}
                          <div style={{ minWidth: 0 }}>
                            <strong style={{ fontSize: 12, color: '#0f172a', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {l.company_name}
                            </strong>
                            <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                              {l.email} {l.phone ? `• ${l.phone}` : ''}
                            </span>
                          </div>
                        </div>
                        {l.mx_valid && <span style={{ fontSize: 10, color: '#059669', fontWeight: 600 }}>✓ MX</span>}
                      </div>
                    )
                  })
              )}
            </div>

            <div style={{ padding: '10px 18px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: '#64748b' }}>
                Выбрано: <strong style={{ color: '#0f172a' }}>{crmPickerSelected.length}</strong>
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" onClick={() => setShowCrmPickerModal(false)} className="outreach-btn outreach-btn-secondary">
                  Отмена
                </button>
                <button
                  type="button"
                  disabled={crmPickerSelected.length === 0}
                  onClick={() => {
                    setComposeRecipients((prev) => [...new Set([...prev, ...crmPickerSelected])])
                    setShowCrmPickerModal(false)
                    showSuccess(`Добавлено ${crmPickerSelected.length} получателей`)
                  }}
                  className="outreach-btn outreach-btn-primary"
                >
                  Вставить в письмо ({crmPickerSelected.length})
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================== TEMPLATE MANAGER MODAL ==================== */}
      {showTemplateModal && (
        <div className="outreach-modal-overlay" onClick={() => setShowTemplateModal(false)}>
          <div className="outreach-modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 960 }}>
            {/* Modal Header */}
            <div className="outreach-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Sliders size={18} style={{ color: '#0f766e' }} />
                <div>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#0f172a' }}>
                    Библиотека шаблонов писем
                  </h3>
                  <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>
                    Создавайте, редактируйте тексты, удаляйте шаблоны и вставляйте динамические переменные
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowTemplateModal(false)}
                className="outreach-btn outreach-btn-ghost"
                style={{ padding: 4 }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body: 2 columns */}
            <div className="outreach-modal-body" style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 18, padding: 18, minHeight: 480 }}>
              {/* Left Column: Template List & Search */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, borderRight: '1px solid #e2e8f0', paddingRight: 16 }}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    type="text"
                    placeholder="Поиск шаблонов..."
                    value={templateSearch}
                    onChange={(e) => setTemplateSearch(e.target.value)}
                    style={{ fontSize: 12, height: 32, padding: '4px 8px' }}
                  />
                  <button
                    type="button"
                    onClick={handleStartNewTemplate}
                    className="outreach-btn outreach-btn-primary"
                    style={{ padding: '4px 8px', fontSize: 11, minHeight: 32 }}
                    title="Создать новый шаблон"
                  >
                    <Plus size={14} />
                    <span>Новый</span>
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, overflowY: 'auto', maxHeight: 420 }}>
                  {templates
                    .filter((t) => !templateSearch.trim() || t.name.toLowerCase().includes(templateSearch.toLowerCase()) || t.subject.toLowerCase().includes(templateSearch.toLowerCase()))
                    .map((t) => {
                      const isSelected = !isCreatingNewTemplate && selectedTemplateId === t.id
                      return (
                        <div
                          key={t.id}
                          onClick={() => handleSelectTemplateInList(t)}
                          style={{
                            padding: '10px 12px',
                            background: isSelected ? '#f0fdfa' : '#f8fafc',
                            border: isSelected ? '1.5px solid #0f766e' : '1px solid #e2e8f0',
                            borderRadius: 8,
                            cursor: 'pointer',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 4,
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong style={{ fontSize: 12, color: isSelected ? '#0f766e' : '#0f172a', lineHeight: 1.3 }}>
                              {t.name}
                            </strong>
                          </div>
                          <span style={{ fontSize: 11, color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {t.subject || 'Без темы'}
                          </span>
                        </div>
                      )
                    })}
                </div>

                <div style={{ marginTop: 'auto', paddingTop: 8, borderTop: '1px solid #f1f5f9' }}>
                  <button
                    type="button"
                    onClick={handleResetDefaultTemplates}
                    className="outreach-btn outreach-btn-ghost"
                    style={{ width: '100%', fontSize: 11, color: '#94a3b8' }}
                  >
                    <RotateCcw size={12} />
                    <span>Сбросить к стандартным</span>
                  </button>
                </div>
              </div>

              {/* Right Column: Template Editor & Preview */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>
                    {isCreatingNewTemplate ? '➕ Создание нового шаблона' : '✏️ Редактирование шаблона'}
                  </span>
                  {!isCreatingNewTemplate && selectedTemplateId && (
                    <div style={{ display: 'flex', gap: 6 }}>
                      {templates.find((t) => t.id === selectedTemplateId) && (
                        <button
                          type="button"
                          onClick={() => {
                            const t = templates.find((tpl) => tpl.id === selectedTemplateId)
                            if (t) handleDuplicateTemplate(t)
                          }}
                          className="outreach-btn outreach-btn-secondary"
                          style={{ padding: '3px 8px', fontSize: 11, minHeight: 24 }}
                          title="Создать копию этого шаблона"
                        >
                          <Copy size={12} />
                          <span>Копия</span>
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDeleteTemplate(selectedTemplateId)}
                        className="outreach-btn outreach-btn-danger"
                        style={{ padding: '3px 8px', fontSize: 11, minHeight: 24 }}
                        title="Удалить этот шаблон"
                      >
                        <Trash2 size={12} />
                        <span>Удалить</span>
                      </button>
                    </div>
                  )}
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                    Название шаблона (для меню выбора):
                  </label>
                  <input
                    type="text"
                    placeholder="Например: Поиск прямых производителей ТЗ..."
                    value={editingTemplateName}
                    onChange={(e) => setEditingTemplateName(e.target.value)}
                    style={{ fontWeight: 600, fontSize: 13 }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                    Тема письма:
                  </label>
                  <input
                    type="text"
                    placeholder="Тема рассылки или письма..."
                    value={editingTemplateSubject}
                    onChange={(e) => setEditingTemplateSubject(e.target.value)}
                    style={{ fontWeight: 600, fontSize: 13 }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                    Текст письма (шаблон):
                  </label>
                  <textarea
                    rows={12}
                    value={editingTemplateBody}
                    onChange={(e) => setEditingTemplateBody(e.target.value)}
                    placeholder="Здравствуйте! Текст шаблона..."
                    style={{ borderRadius: 8, minHeight: 280, fontSize: 13, lineHeight: 1.55 }}
                  />
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="outreach-modal-footer">
              <button
                type="button"
                onClick={() => setShowTemplateModal(false)}
                className="outreach-btn outreach-btn-secondary"
              >
                Закрыть
              </button>

              <button
                type="button"
                onClick={handleSaveTemplate}
                className="outreach-btn outreach-btn-primary"
              >
                <Save size={14} />
                <span>{isCreatingNewTemplate ? 'Создать шаблон' : 'Сохранить изменения'}</span>
              </button>

              {!isCreatingNewTemplate && selectedTemplateId && (
                <button
                  type="button"
                  onClick={() => {
                    const t = templates.find((tpl) => tpl.id === selectedTemplateId)
                    if (t) {
                      handleApplyTemplate(
                        { ...t, name: editingTemplateName, subject: editingTemplateSubject, body: editingTemplateBody },
                        templateModalTarget
                      )
                    }
                  }}
                  className="outreach-btn outreach-btn-emerald"
                  style={{ fontWeight: 700 }}
                >
                  <CheckCircle2 size={14} />
                  <span>Вставить в {templateModalTarget === 'campaign' ? 'рассылку' : 'письмо'}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ==================== DELETE TASK MODAL ==================== */}
      {deleteTaskId && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(15, 23, 42, 0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div className="outreach-panel" style={{ width: '100%', maxWidth: 420 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#0f172a' }}>Удалить задачу поиска?</h3>
            <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>
              Вы хотите удалить задачу поиска из истории. Выберите, что делать с собранными контактами:
            </p>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 10, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={deleteWithLeads}
                onChange={(e) => setDeleteWithLeads(e.target.checked)}
              />
              <span style={{ fontSize: 12, color: '#334155' }}>
                Удалить также все собранные контакты этой задачи из базы CRM
              </span>
            </label>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
              <button
                type="button"
                onClick={() => setDeleteTaskId(null)}
                className="outreach-btn outreach-btn-secondary"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleDeleteTask}
                className="outreach-btn outreach-btn-danger"
              >
                Удалить задачу
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
