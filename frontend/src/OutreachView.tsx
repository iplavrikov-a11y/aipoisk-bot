import React, { useState, useEffect, useCallback } from 'react'
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
} from 'lucide-react'

type TaskSubTab = 'leads' | 'campaign' | 'compose' | 'inbox' | 'settings'

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
  started_at: string | null
  completed_at: string | null
  created_at: string
}

interface Lead {
  id: string
  task_id: string
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
  mx_valid_leads: number
}

interface LeadHistory {
  lead: Lead
  sent: any[]
  incoming: IncomingMessage[]
}

const COLD_EMAIL_TEMPLATES = [
  {
    id: 'tender_subcontract',
    name: 'Поиск субподрядчиков и поставщиков (44-ФЗ / 223-ФЗ)',
    subject: 'Сотрудничество по поставкам и субподрядам для {company}',
    body: 'Здравствуйте, коллеги из {company}!\n\nОбращаемся к вам как к надежному участнику и исполнителю контрактов.\nСервис TenderLex помогает оперативно находить проверенных производителей и поставщиков оборудования, материалов и комплексного снабжения по спецификациям 44-ФЗ и 223-ФЗ.\n\nПодскажите, актуально ли для вас ускорить подбор поставщиков и снизить себестоимость закрытия спецификаций?\n\nБудем рады предоставить тестовый доступ.\n\nС уважением,\nКоманда TenderLex\ninfo@tenderlex.ru | https://tenderlex.ru',
  },
  {
    id: 'b2b_supply',
    name: 'Коммерческое предложение по закупкам',
    subject: 'Предложение по оптимизации закупок для {company}',
    body: 'Добрый день!\n\nИзучили профиль деятельности компании {company}.\nПредлагаем автоматизированное решение для поиска прямых заводов-производителей и дилеров по вашим техническим заданиям.\n\nПреимущества:\n- Поиск по реестрам Минпромторга и прямым контактам ЛПР\n- Проверка контрагентов и актуальности цен\n- Экономия до 40% времени отдела снабжения\n\nГотовы направить короткую презентацию или провести демонстрацию.\n\nС уважением,\nОтдел развития TenderLex\ninfo@tenderlex.ru',
  },
  {
    id: 'follow_up',
    name: 'Краткое напоминание (Follow-up)',
    subject: 'Re: Сотрудничество с {company}',
    body: 'Здравствуйте!\n\nНедавно отправляли вам предложение по автоматизации подбора поставщиков для компании {company}.\n\nУдалось ли ознакомиться? Готовы ответить на любые вопросы и подобрать поставщиков под один из ваших текущих запросов бесплатно в качестве теста.\n\nХорошего дня!\nКоманда TenderLex\ninfo@tenderlex.ru',
  },
]

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
      const j = await res.json()
      errText = j.detail || j.message || JSON.stringify(j)
    } catch {
      errText = await res.text()
    }
    throw new Error(errText || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function OutreachView() {
  // Global & Task selection state
  const [tasks, setTasks] = useState<SearchTask[]>([])
  const [selectedTask, setSelectedTask] = useState<SearchTask | null>(null)
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null)
  const [taskSubTab, setTaskSubTab] = useState<TaskSubTab>('leads')

  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // New Search Task Modal / Form state
  const [showNewTaskModal, setShowNewTaskModal] = useState(false)
  const [taskName, setTaskName] = useState('')
  const [searchPrompt, setSearchPrompt] = useState('')
  const [targetCount, setTargetCount] = useState<number>(500)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [searchStatus, setSearchStatus] = useState<any>(null)
  const [deleteTaskId, setDeleteTaskId] = useState<string | null>(null)
  const [deleteWithLeads, setDeleteWithLeads] = useState(false)

  // Leads CRM state (inside selected task)
  const [leads, setLeads] = useState<Lead[]>([])
  const [leadTotal, setLeadTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [searchFilter, setSearchFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([])

  // History modal
  const [historyLead, setHistoryLead] = useState<LeadHistory | null>(null)

  // Campaign state (inside selected task)
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [campSubject, setCampSubject] = useState('Сотрудничество с TenderLex')
  const [campBody, setCampBody] = useState(
    'Здравствуйте!\n\nОбращаемся к компании {company}.\nПредлагаем автоматизированный поиск поставщиков и производителей по техническому заданию для ваших закупок и контрактов.\n\nБудем рады ответить на ваши вопросы,\nКоманда TenderLex\ninfo@tenderlex.ru\nhttps://tenderlex.ru'
  )
  const [campAudienceType, setCampAudienceType] = useState<'all' | 'selected'>('all')
  const [campDelay, setCampDelay] = useState<number>(2.0)
  const [testEmail, setTestEmail] = useState('')
  const [sendingTest, setSendingTest] = useState(false)

  // Compose state (inside selected task)
  const [composeRecipients, setComposeRecipients] = useState<string[]>([])
  const [composeRecipientInput, setComposeRecipientInput] = useState('')
  const [composeSubject, setComposeSubject] = useState('Предложение о сотрудничестве')
  const [composeBody, setComposeBody] = useState('')
  const [composeTone, setComposeTone] = useState('professional')
  const [aiPrompt, setAiPrompt] = useState('')
  const [aiGenerating, setAiGenerating] = useState(false)
  const [sendingDirect, setSendingDirect] = useState(false)

  // Inbox state (inside selected task)
  const [inboxMessages, setInboxMessages] = useState<IncomingMessage[]>([])
  const [inboxFilter, setInboxFilter] = useState<'all' | 'unread' | 'spam'>('all')
  const [inboxSearch, setInboxSearch] = useState('')
  const [syncingInbox, setSyncingInbox] = useState(false)
  const [selectedMsg, setSelectedMsg] = useState<IncomingMessage | null>(null)
  const [replyText, setReplyText] = useState('')
  const [sendingReply, setSendingReply] = useState(false)
  const [aiReplyGenerating, setAiReplyGenerating] = useState(false)

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

  // Fetch all tasks
  const fetchTasks = useCallback(async () => {
    try {
      const data = await outreachFetch<{ items: SearchTask[] }>('/api/outreach/tasks')
      setTasks(data.items || [])
      const running = data.items?.find((t) => t.status === 'running')
      if (running) {
        setActiveTaskId(running.id)
        setSearchStatus(running)
      } else if (activeTaskId) {
        const current = data.items?.find((t) => t.id === activeTaskId)
        if (current) setSearchStatus(current)
      }
    } catch (e: any) {
      console.error('fetchTasks error:', e)
      showError(`Ошибка загрузки задач: ${e.message}`)
    }
  }, [activeTaskId])

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
    async (taskId: string, p = 1, search = '', status = '') => {
      setLoading(true)
      try {
        const params = new URLSearchParams({
          page: String(p),
          page_size: '50',
          search,
          status,
          task_id: taskId,
        })
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
    []
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

  // Fetch inbox for the selected task
  const fetchInbox = useCallback(
    async (taskId: string, filter = inboxFilter, search = inboxSearch) => {
      try {
        const params = new URLSearchParams({
          limit: '100',
          unread_only: String(filter === 'unread'),
          is_spam: String(filter === 'spam'),
          search,
          task_id: taskId,
        })
        const data = await outreachFetch<{ items: IncomingMessage[] }>(`/api/outreach/inbox?${params.toString()}`)
        setInboxMessages(data.items || [])
        if (data.items?.length && !selectedMsg) {
          setSelectedMsg(data.items[0])
        }
      } catch {
        // ignore
      }
    },
    [inboxFilter, inboxSearch, selectedMsg]
  )

  // Fetch settings
  const fetchSettings = useCallback(async () => {
    try {
      const data = await outreachFetch<any>('/api/outreach/settings')
      setSettings(data)
    } catch {
      // ignore
    }
  }, [])

  // Initial load
  useEffect(() => {
    fetchTasks()
    fetchSettings()
  }, [])

  // When a task is selected, load its workspace data
  const handleSelectTask = (task: SearchTask) => {
    setSelectedTask(task)
    setTaskSubTab('leads')
    setSelectedLeadIds([])
    setSearchFilter('')
    setStatusFilter('')
    fetchTaskStats(task.id)
    fetchLeads(task.id, 1, '', '')
    fetchCampaigns(task.id)
    fetchInbox(task.id)
  }

  // Polling for active search task
  useEffect(() => {
    if (!activeTaskId) return
    const interval = setInterval(async () => {
      try {
        const data = await outreachFetch<any>(`/api/outreach/search/status/${activeTaskId}`)
        setSearchStatus(data)
        if (data.status === 'completed' || data.status === 'error' || data.status === 'cancelled') {
          setActiveTaskId(null)
          fetchTasks()
          if (selectedTask && selectedTask.id === activeTaskId) {
            fetchTaskStats(selectedTask.id)
            fetchLeads(selectedTask.id, 1, searchFilter, statusFilter)
          }
        }
      } catch {
        // ignore
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [activeTaskId, selectedTask, searchFilter, statusFilter, fetchTasks, fetchTaskStats, fetchLeads])

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

  // Select all leads on page
  const handleSelectAllLeads = () => {
    if (selectedLeadIds.length === leads.length) {
      setSelectedLeadIds([])
    } else {
      setSelectedLeadIds(leads.map((l) => l.id))
    }
  }

  // Toggle single lead selection
  const handleToggleLead = (id: string) => {
    setSelectedLeadIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  // Send selected leads to campaign inside task
  const handleSendSelectedToCampaign = () => {
    if (!selectedLeadIds.length) {
      showError('Выберите хотя бы один контакт')
      return
    }
    setCampAudienceType('selected')
    setTaskSubTab('campaign')
    showSuccess(`Выбрано ${selectedLeadIds.length} контактов для рассылки`)
  }

  // Send selected leads to compose tab inside task
  const handleSendSelectedToCompose = () => {
    if (!selectedLeadIds.length) {
      showError('Выберите хотя бы один контакт')
      return
    }
    const selectedEmails = leads.filter((l) => selectedLeadIds.includes(l.id)).map((l) => l.email)
    setComposeRecipients(selectedEmails)
    setTaskSubTab('compose')
    showSuccess(`Добавлено ${selectedEmails.length} получателей во вкладку "Написать"`)
  }

  // Delete selected leads
  const handleDeleteSelectedLeads = async () => {
    if (!selectedLeadIds.length || !selectedTask) return
    if (!confirm(`Удалить выбранные контакты (${selectedLeadIds.length} шт.)?`)) return
    try {
      await outreachFetch('/api/outreach/leads/delete', {
        method: 'POST',
        body: JSON.stringify({ lead_ids: selectedLeadIds }),
      })
      setSelectedLeadIds([])
      showSuccess('Контакты удалены')
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
        delay_seconds: campDelay,
      }
      if (campAudienceType === 'selected') {
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

  // AI Assistant for Email
  const handleAiAction = async (action: string, customPrompt = '') => {
    setAiGenerating(true)
    try {
      const data = await outreachFetch<any>('/api/outreach/ai/generate', {
        method: 'POST',
        body: JSON.stringify({
          action,
          prompt: customPrompt || aiPrompt,
          context: composeBody || campBody,
          tone: composeTone,
          company_name: composeRecipients[0] || selectedTask?.name || '',
        }),
      })
      if (action === 'cold_email') {
        if (data.subject) setComposeSubject(data.subject)
        if (data.body_text) setComposeBody(data.body_text)
        showSuccess('AI сгенерировал текст письма!')
      } else if (action === 'improve' || action === 'shorten' || action === 'grammar') {
        if (data.body_text) setComposeBody(data.body_text)
        showSuccess('Текст обновлен с помощью AI!')
      } else if (action === 'subject') {
        if (data.subjects?.length) {
          setComposeSubject(data.subjects[0])
          showSuccess(`AI предложил тему: "${data.subjects[0]}"`)
        }
      }
    } catch (e: any) {
      showError(`Ошибка AI: ${e.message}`)
    } finally {
      setAiGenerating(false)
    }
  }

  // Sync Inbox
  const handleSyncInbox = async () => {
    setSyncingInbox(true)
    try {
      const res = await outreachFetch<any>('/api/outreach/inbox/sync', { method: 'POST' })
      showSuccess(`Синхронизация завершена (новых писем: ${res.synced || 0})`)
      if (selectedTask) {
        fetchInbox(selectedTask.id)
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
      if (selectedTask) {
        fetchInbox(selectedTask.id)
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
      showSuccess(res.is_spam ? 'Письмо перемещено в Спам' : 'Письмо возвращено из Спама')
      if (selectedTask) {
        fetchInbox(selectedTask.id)
        fetchTaskStats(selectedTask.id)
      }
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
      if (selectedTask) {
        fetchInbox(selectedTask.id)
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

      {/* ========================================================================= */}
      {/* LEVEL 1: NO TASK SELECTED (MAIN DASHBOARD: LIST OF SEARCH PROJECTS)       */}
      {/* ========================================================================= */}
      {!selectedTask && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* Active Search Banner (if running) */}
          {searchStatus && (searchStatus.status === 'running' || activeTaskId) && (
            <div className="outreach-live-banner">
              <div className="outreach-live-top">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ color: '#2563eb', fontWeight: 700, fontSize: 11, textTransform: 'uppercase' }}>
                      ● Активный сбор контактов
                    </span>
                    <span style={{ fontSize: 11, background: '#dbeafe', color: '#1e40af', padding: '2px 8px', borderRadius: 999, fontWeight: 700 }}>
                      Себестоимость: {(searchStatus.total_cost_rub || 0).toFixed(2)} ₽
                    </span>
                  </div>
                  <h3 style={{ margin: '4px 0 0', fontSize: 16, fontWeight: 700, color: '#0f172a' }}>
                    {searchStatus.name || 'Поиск целевых контактов'}
                  </h3>
                  <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748b' }}>{searchStatus.prompt}</p>
                </div>

                <button
                  type="button"
                  onClick={() => handleCancelSearch(searchStatus.id || activeTaskId!)}
                  className="outreach-btn outreach-btn-danger"
                >
                  <Pause size={14} />
                  <span>Остановить</span>
                </button>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                  <span>{searchStatus.message || 'Сбор контактов...'}</span>
                  <span>
                    {searchStatus.collected || 0} / {searchStatus.target_count || targetCount} контактов
                  </span>
                </div>
                <div style={{ width: '100%', height: 8, background: '#bfdbfe', borderRadius: 999, overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      background: '#2563eb',
                      borderRadius: 999,
                      width: `${Math.min(
                        100,
                        Math.round(((searchStatus.collected || 0) / (searchStatus.target_count || targetCount || 1)) * 100)
                      )}%`,
                      transition: 'width 0.5s ease',
                    }}
                  />
                </div>
              </div>
            </div>
          )}

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
                    Количество контактов (от 1 до 10 000):
                  </label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
                    <input
                      type="number"
                      min={1}
                      max={10000}
                      style={{ width: 110, fontWeight: 700 }}
                      value={targetCount}
                      onChange={(e) => setTargetCount(Math.max(1, Math.min(10000, parseInt(e.target.value) || 1)))}
                    />
                    {[100, 500, 1000, 3000, 5000, 10000].map((cnt) => (
                      <button
                        key={cnt}
                        type="button"
                        onClick={() => setTargetCount(cnt)}
                        className={`outreach-btn ${targetCount === cnt ? 'outreach-btn-primary' : 'outreach-btn-secondary'}`}
                      >
                        {cnt >= 1000 ? `${cnt / 1000} тыс.` : cnt}
                      </button>
                    ))}
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
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 14, marginTop: 6 }}>
                {tasks.map((task) => (
                  <div
                    key={task.id}
                    style={{
                      background: '#fff',
                      border: '1px solid #cbd5e1',
                      borderRadius: 10,
                      padding: 16,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      gap: 12,
                      boxShadow: '0 2px 4px rgba(15, 23, 42, 0.04)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#0f172a', lineHeight: 1.3 }}>
                          {task.name}
                        </h3>
                        {task.status === 'completed' && (
                          <span className="outreach-badge completed" style={{ flexShrink: 0 }}>
                            <CheckCircle2 size={12} /> Готово
                          </span>
                        )}
                        {task.status === 'running' && (
                          <span className="outreach-badge running" style={{ flexShrink: 0 }}>
                            <RefreshCw size={12} className="animate-spin" /> В процессе
                          </span>
                        )}
                        {task.status === 'cancelled' && (
                          <span className="outreach-badge cancelled" style={{ flexShrink: 0 }}>Остановлена</span>
                        )}
                      </div>

                      <p style={{ margin: '6px 0 0', fontSize: 11, color: '#64748b', lineClamp: 2, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {task.prompt}
                      </p>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
                        <div style={{ background: '#f1f5f9', padding: '4px 8px', borderRadius: 6, fontSize: 11, color: '#334155' }}>
                          Лидов: <strong style={{ color: '#0f172a' }}>{task.collected_count}</strong> / {task.target_count}
                        </div>
                        <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '4px 8px', borderRadius: 6, fontSize: 11, color: '#047857', fontWeight: 700 }}>
                          Себестоимость: {task.cost_label || `${(task.total_cost_rub || 0).toFixed(2)} ₽`}
                        </div>
                        <div style={{ background: '#f8fafc', padding: '4px 8px', borderRadius: 6, fontSize: 11, color: '#94a3b8' }}>
                          {formatDate(task.created_at)}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 10, borderTop: '1px solid #f1f5f9' }}>
                      <button
                        type="button"
                        onClick={() => handleSelectTask(task)}
                        className="outreach-btn outreach-btn-primary"
                        style={{ padding: '6px 14px', fontSize: 12, flex: 1, marginRight: 8 }}
                      >
                        <FolderOpen size={14} />
                        <span>Открыть задачу ({task.collected_count}) →</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setDeleteTaskId(task.id)}
                        className="outreach-btn outreach-btn-danger"
                        style={{ padding: '6px 8px' }}
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
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '12px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button
                type="button"
                onClick={() => {
                  setSelectedTask(null)
                  fetchTasks()
                }}
                className="outreach-btn outreach-btn-secondary"
                style={{ padding: '6px 12px', fontSize: 12 }}
              >
                <ArrowLeft size={14} />
                <span>Все задачи</span>
              </button>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#0f766e', background: '#f0fdfa', padding: '2px 6px', borderRadius: 4 }}>
                    Проект поиска
                  </span>
                  <h2 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: '#0f172a' }}>
                    {selectedTask.name}
                  </h2>
                </div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                  {selectedTask.prompt} • Себестоимость: <strong style={{ color: '#047857' }}>{selectedTask.cost_label || selectedTask.total_cost_rub + ' ₽'}</strong>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                type="button"
                onClick={() => {
                  fetchTaskStats(selectedTask.id)
                  fetchLeads(selectedTask.id, 1, searchFilter, statusFilter)
                  fetchCampaigns(selectedTask.id)
                  fetchInbox(selectedTask.id)
                }}
                className="outreach-btn outreach-btn-secondary"
              >
                <RefreshCw size={13} />
                <span>Обновить задачу</span>
              </button>
            </div>
          </div>

          {/* Task-Specific 4 Metrics Cards */}
          <div className="outreach-metrics-grid">
            <div className="outreach-metric-card">
              <div className="outreach-metric-header">
                <div className="outreach-metric-icon blue">
                  <Users size={20} />
                </div>
                <div className="outreach-metric-info">
                  <span className="outreach-metric-label">Лидов в задаче</span>
                  <strong className="outreach-metric-value">{taskStats?.total_leads ?? selectedTask.collected_count}</strong>
                </div>
              </div>
              <span className="outreach-metric-sub">Цель: {selectedTask.target_count} контактов</span>
            </div>

            <div className="outreach-metric-card">
              <div className="outreach-metric-header">
                <div className="outreach-metric-icon green">
                  <ShieldCheck size={20} />
                </div>
                <div className="outreach-metric-info">
                  <span className="outreach-metric-label">MX проверен</span>
                  <strong className="outreach-metric-value" style={{ color: '#059669' }}>
                    {taskStats?.mx_valid_leads ?? (selectedTask.collected_count ? Math.round(selectedTask.collected_count * 0.93) : 0)}
                  </strong>
                </div>
              </div>
              <span className="outreach-metric-sub">Валидные почтовые домены</span>
            </div>

            <div className="outreach-metric-card">
              <div className="outreach-metric-header">
                <div className="outreach-metric-icon indigo">
                  <Send size={20} />
                </div>
                <div className="outreach-metric-info">
                  <span className="outreach-metric-label">Отправлено писем</span>
                  <strong className="outreach-metric-value">{taskStats?.sent_leads ?? 0}</strong>
                </div>
              </div>
              <span className="outreach-metric-sub">По контактам этой задачи</span>
            </div>

            <div className="outreach-metric-card">
              <div className="outreach-metric-header">
                <div className="outreach-metric-icon amber">
                  <MessageSquare size={20} />
                </div>
                <div className="outreach-metric-info">
                  <span className="outreach-metric-label">Получено ответов</span>
                  <strong className="outreach-metric-value" style={{ color: '#d97706' }}>
                    {taskStats?.replied_leads ?? inboxMessages.length}
                  </strong>
                </div>
              </div>
              <span className="outreach-metric-sub">Входящие ответы</span>
            </div>
          </div>

          {/* Sub-Navigation Tabs inside Selected Task */}
          <div className="outreach-tabs">
            <button
              type="button"
              onClick={() => setTaskSubTab('leads')}
              className={`outreach-tab-btn ${taskSubTab === 'leads' ? 'active' : ''}`}
            >
              <Users size={16} />
              <span>База контактов ({taskStats?.total_leads ?? selectedTask.collected_count})</span>
            </button>

            <button
              type="button"
              onClick={() => setTaskSubTab('campaign')}
              className={`outreach-tab-btn ${taskSubTab === 'campaign' ? 'active' : ''}`}
            >
              <Send size={16} />
              <span>Email-рассылка</span>
            </button>

            <button
              type="button"
              onClick={() => setTaskSubTab('compose')}
              className={`outreach-tab-btn ${taskSubTab === 'compose' ? 'active' : ''}`}
            >
              <PenTool size={16} />
              <span>Написать письмо</span>
              {composeRecipients.length > 0 && (
                <span className="outreach-tab-badge">{composeRecipients.length}</span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setTaskSubTab('inbox')}
              className={`outreach-tab-btn ${taskSubTab === 'inbox' ? 'active' : ''}`}
            >
              <Inbox size={16} />
              <span>Входящие ответы</span>
              {inboxMessages.length > 0 && (
                <span className="outreach-tab-badge" style={{ background: '#3b82f6' }}>
                  {inboxMessages.length}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setTaskSubTab('settings')}
              className={`outreach-tab-btn ${taskSubTab === 'settings' ? 'active' : ''}`}
            >
              <SettingsIcon size={16} />
              <span>Настройки почты</span>
            </button>
          </div>

          {/* SUBTAB 1: LEADS IN TASK */}
          {taskSubTab === 'leads' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Filter Bar */}
              <div className="outreach-panel" style={{ padding: 14 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, flex: 1 }}>
                    <div style={{ position: 'relative', minWidth: 260 }}>
                      <input
                        type="text"
                        placeholder="Поиск по компании, email, телефону..."
                        value={searchFilter}
                        onChange={(e) => setSearchFilter(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && fetchLeads(selectedTask.id, 1, searchFilter, statusFilter)}
                        style={{ paddingLeft: 30 }}
                      />
                      <Search size={14} style={{ position: 'absolute', left: 9, top: 11, color: '#94a3b8' }} />
                    </div>

                    <select
                      value={statusFilter}
                      onChange={(e) => {
                        setStatusFilter(e.target.value)
                        fetchLeads(selectedTask.id, 1, searchFilter, e.target.value)
                      }}
                      style={{ width: 140 }}
                    >
                      <option value="">Все статусы</option>
                      <option value="new">Новый</option>
                      <option value="sent">Отправлено</option>
                      <option value="replied">Ответил</option>
                      <option value="spam">Спам</option>
                    </select>

                    <button
                      type="button"
                      onClick={() => fetchLeads(selectedTask.id, 1, searchFilter, statusFilter)}
                      className="outreach-btn outreach-btn-primary"
                    >
                      Найти
                    </button>
                  </div>
                </div>
              </div>

              {/* Selection Action Bar (when 1+ items selected) */}
              {selectedLeadIds.length > 0 && (
                <div className="outreach-action-bar">
                  <strong style={{ color: '#1e40af', fontSize: 13 }}>
                    Выбрано контактов: {selectedLeadIds.length} из {leads.length}
                  </strong>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <button
                      type="button"
                      onClick={handleSendSelectedToCampaign}
                      className="outreach-btn outreach-btn-emerald"
                    >
                      <Send size={14} />
                      <span>Отправить выбранные ({selectedLeadIds.length}) в рассылку</span>
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
                      <span>Удалить ({selectedLeadIds.length})</span>
                    </button>
                  </div>
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
                          <td colSpan={8} style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
                            <RefreshCw size={22} className="animate-spin" style={{ margin: '0 auto 8px', color: '#0f766e' }} />
                            Загрузка контактов задачи...
                          </td>
                        </tr>
                      ) : leads.length === 0 ? (
                        <tr>
                          <td colSpan={8} style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
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
                                  {lead.status === 'new' ? 'Новый' : lead.status === 'sent' ? 'Отправлено' : lead.status === 'replied' ? 'Ответил' : lead.status}
                                </span>
                              </td>
                              <td style={{ textAlign: 'right' }}>
                                <div style={{ display: 'inline-flex', gap: 4 }}>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setComposeRecipients([lead.email])
                                      setTaskSubTab('compose')
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
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 18 }}>
              {/* Campaign Form */}
              <div className="outreach-panel" style={{ gridColumn: 'span 7' }}>
                <div>
                  <h2 className="outreach-panel-title">Email-рассылка по задаче «{selectedTask.name}»</h2>
                  <p className="outreach-panel-desc">
                    Персональная отправка писем по базе контактов текущей задачи с автоподстановкой названия компании.
                  </p>
                </div>

                <form onSubmit={handleCreateCampaign} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                      Аудитория получателей:
                    </label>
                    <select
                      value={campAudienceType}
                      onChange={(e) => setCampAudienceType(e.target.value as any)}
                      style={{ fontWeight: 600 }}
                    >
                      <option value="all">Всем проверенным контактам этой задачи ({selectedTask.collected_count} шт.)</option>
                      {selectedLeadIds.length > 0 && (
                        <option value="selected">
                          Выбранным вручную в CRM контактам ({selectedLeadIds.length} шт.)
                        </option>
                      )}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                      Тема письма:
                    </label>
                    <input
                      type="text"
                      required
                      value={campSubject}
                      onChange={(e) => setCampSubject(e.target.value)}
                    />
                  </div>

                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <label style={{ fontSize: 12, fontWeight: 600, color: '#334155' }}>
                        Текст письма (доступна переменная {'{company}'}):
                      </label>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {['{company}', '{phone}', '{site}'].map((v) => (
                          <button
                            key={v}
                            type="button"
                            onClick={() => setCampBody((prev) => `${prev} ${v}`)}
                            className="outreach-btn outreach-btn-secondary"
                            style={{ padding: '2px 6px', fontSize: 11, minHeight: 22 }}
                          >
                            +{v}
                          </button>
                        ))}
                      </div>
                    </div>
                    <textarea
                      rows={8}
                      required
                      style={{ minHeight: 160 }}
                      value={campBody}
                      onChange={(e) => setCampBody(e.target.value)}
                    />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                        Задержка между письмами:
                      </label>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input
                          type="number"
                          step={0.5}
                          min={0.5}
                          max={60}
                          style={{ width: 80 }}
                          value={campDelay}
                          onChange={(e) => setCampDelay(parseFloat(e.target.value) || 2.0)}
                        />
                        <span style={{ fontSize: 12, color: '#64748b' }}>сек</span>
                      </div>
                    </div>

                    <div style={{ paddingTop: 20 }}>
                      <button
                        type="submit"
                        disabled={loading}
                        className="outreach-btn outreach-btn-emerald"
                        style={{ padding: '8px 18px', fontSize: 13 }}
                      >
                        <Send size={15} />
                        <span>Запустить рассылку</span>
                      </button>
                    </div>
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

              {/* Campaigns History */}
              <div className="outreach-panel" style={{ gridColumn: 'span 5' }}>
                <h2 className="outreach-panel-title">Рассылки по этой задаче</h2>
                {campaigns.length === 0 ? (
                  <p style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', padding: '30px 0' }}>
                    Рассылок по этой задаче пока не было.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {campaigns.map((c) => (
                      <div
                        key={c.id}
                        style={{ padding: 12, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 8 }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong style={{ fontSize: 13, color: '#0f172a' }}>{c.name}</strong>
                          <span className={`outreach-badge ${c.status}`}>{c.status}</span>
                        </div>

                        <div style={{ fontSize: 12, color: '#64748b' }}>
                          Отправлено: <strong style={{ color: '#0f172a' }}>{c.sent_count}</strong> из{' '}
                          <strong style={{ color: '#0f172a' }}>{c.total_recipients}</strong>
                        </div>

                        <div style={{ width: '100%', height: 6, background: '#e2e8f0', borderRadius: 999, overflow: 'hidden' }}>
                          <div
                            style={{
                              height: '100%',
                              background: '#0f766e',
                              borderRadius: 999,
                              width: `${Math.min(100, Math.round((c.sent_count / (c.total_recipients || 1)) * 100))}%`,
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
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* SUBTAB 3: COMPOSE IN TASK */}
          {taskSubTab === 'compose' && (
            <div className="outreach-panel" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12, borderBottom: '1px solid #e2e8f0' }}>
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
                          ×
                        </button>
                      </span>
                    ))}
                    <input
                      type="text"
                      placeholder={composeRecipients.length === 0 ? 'Введите email получателей из этой задачи (через Enter)...' : ''}
                      value={composeRecipientInput}
                      onChange={(e) => setComposeRecipientInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ',') {
                          e.preventDefault()
                          if (composeRecipientInput.trim() && composeRecipientInput.includes('@')) {
                            setComposeRecipients((prev) => [...new Set([...prev, composeRecipientInput.trim()])])
                            setComposeRecipientInput('')
                          }
                        }
                      }}
                      style={{ border: 'none', outline: 'none', flex: 1, minWidth: 200, minHeight: 28, padding: 0 }}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => setTaskSubTab('leads')}
                    className="outreach-btn outreach-btn-secondary"
                  >
                    <Users size={14} />
                    <span>Выбрать из CRM</span>
                  </button>
                </div>

                <div className="outreach-composer-row">
                  <span className="outreach-composer-label">Тема</span>
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <input
                      type="text"
                      placeholder="Тема письма..."
                      value={composeSubject}
                      onChange={(e) => setComposeSubject(e.target.value)}
                      style={{ fontWeight: 600 }}
                    />
                    <button
                      type="button"
                      onClick={() => handleAiAction('subject')}
                      disabled={aiGenerating}
                      className="outreach-btn outreach-btn-indigo"
                      title="Сгенерировать привлекательную тему с помощью AI"
                    >
                      <Sparkles size={14} />
                      <span>AI Тема</span>
                    </button>
                  </div>

                  <select
                    onChange={(e) => {
                      const tpl = COLD_EMAIL_TEMPLATES.find((t) => t.id === e.target.value)
                      if (tpl) {
                        setComposeSubject(tpl.subject)
                        setComposeBody(tpl.body)
                      }
                    }}
                    style={{ width: 'auto', minWidth: 180 }}
                  >
                    <option value="">Выбрать шаблон...</option>
                    {COLD_EMAIL_TEMPLATES.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Formatting & AI Toolbar */}
              <div className="outreach-composer-toolbar">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button
                    type="button"
                    onClick={() => setComposeBody((prev) => `**${prev}**`)}
                    className="outreach-btn outreach-btn-ghost"
                    style={{ padding: '4px 6px' }}
                    title="Жирный"
                  >
                    <Bold size={15} />
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposeBody((prev) => `*${prev}*`)}
                    className="outreach-btn outreach-btn-ghost"
                    style={{ padding: '4px 6px' }}
                    title="Курсив"
                  >
                    <Italic size={15} />
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposeBody((prev) => `_${prev}_`)}
                    className="outreach-btn outreach-btn-ghost"
                    style={{ padding: '4px 6px' }}
                    title="Подчеркнутый"
                  >
                    <Underline size={15} />
                  </button>
                  <span style={{ width: 1, height: 16, background: '#cbd5e1', margin: '0 4px' }} />
                  {['{company}', '{name}', '{phone}', '{site}'].map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => setComposeBody((prev) => `${prev} ${chip}`)}
                      className="outreach-btn outreach-btn-secondary"
                      style={{ padding: '2px 6px', fontSize: 11, minHeight: 24, fontFamily: 'monospace' }}
                    >
                      +{chip}
                    </button>
                  ))}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button
                    type="button"
                    onClick={() => handleAiAction('cold_email')}
                    disabled={aiGenerating}
                    className="outreach-btn outreach-btn-indigo"
                  >
                    <Sparkles size={14} />
                    <span>{aiGenerating ? 'AI пишет...' : '✨ Написать с AI'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAiAction('improve')}
                    disabled={aiGenerating || !composeBody.trim()}
                    className="outreach-btn outreach-btn-secondary"
                  >
                    <Wand2 size={14} style={{ color: '#6366f1' }} />
                    <span>Улучшить</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAiAction('shorten')}
                    disabled={aiGenerating || !composeBody.trim()}
                    className="outreach-btn outreach-btn-secondary"
                  >
                    <Scissors size={14} style={{ color: '#f59e0b' }} />
                    <span>Сократить</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAiAction('grammar')}
                    disabled={aiGenerating || !composeBody.trim()}
                    className="outreach-btn outreach-btn-secondary"
                  >
                    <SpellCheck size={14} style={{ color: '#10b981' }} />
                    <span>Орфография</span>
                  </button>

                  <select
                    value={composeTone}
                    onChange={(e) => setComposeTone(e.target.value)}
                    style={{ width: 'auto', minWidth: 120, height: 32, fontSize: 11 }}
                  >
                    <option value="professional">Деловой тон</option>
                    <option value="friendly">Дружелюбный</option>
                    <option value="selling">Продающий</option>
                    <option value="concise">Краткий</option>
                  </select>
                </div>
              </div>

              {/* Editor Body */}
              <div style={{ padding: 18 }}>
                <textarea
                  rows={14}
                  placeholder="Напишите текст письма здесь или используйте кнопку «✨ Написать с AI»..."
                  value={composeBody}
                  onChange={(e) => setComposeBody(e.target.value)}
                  style={{ border: 'none', outline: 'none', resize: 'vertical', width: '100%', minHeight: 280, fontSize: 14, lineHeight: 1.6, padding: 0 }}
                />
              </div>

              {/* Footer */}
              <div style={{ padding: '12px 18px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ fontSize: 12, color: '#64748b' }}>
                  Получателей: <strong style={{ color: '#0f172a' }}>{composeRecipients.length}</strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => {
                      setCampSubject(composeSubject)
                      setCampBody(composeBody)
                      setTaskSubTab('campaign')
                    }}
                    className="outreach-btn outreach-btn-secondary"
                  >
                    Перенести в рассылку по задаче
                  </button>

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

          {/* SUBTAB 4: INBOX IN TASK */}
          {taskSubTab === 'inbox' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="outreach-panel" style={{ padding: 14 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
                    <div style={{ position: 'relative', minWidth: 260 }}>
                      <input
                        type="text"
                        placeholder="Поиск по ответам в задаче..."
                        value={inboxSearch}
                        onChange={(e) => setInboxSearch(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && fetchInbox(selectedTask.id, inboxFilter, inboxSearch)}
                        style={{ paddingLeft: 30 }}
                      />
                      <Search size={14} style={{ position: 'absolute', left: 9, top: 11, color: '#94a3b8' }} />
                    </div>

                    <div style={{ display: 'inline-flex', background: '#f1f5f9', borderRadius: 8, padding: 3, gap: 2 }}>
                      <button
                        type="button"
                        onClick={() => {
                          setInboxFilter('all')
                          fetchInbox(selectedTask.id, 'all', inboxSearch)
                        }}
                        className={`outreach-btn ${inboxFilter === 'all' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                        style={{ minHeight: 28, padding: '2px 10px', fontSize: 11 }}
                      >
                        Все
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setInboxFilter('unread')
                          fetchInbox(selectedTask.id, 'unread', inboxSearch)
                        }}
                        className={`outreach-btn ${inboxFilter === 'unread' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                        style={{ minHeight: 28, padding: '2px 10px', fontSize: 11 }}
                      >
                        Новые
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setInboxFilter('spam')
                          fetchInbox(selectedTask.id, 'spam', inboxSearch)
                        }}
                        className={`outreach-btn ${inboxFilter === 'spam' ? 'outreach-btn-primary' : 'outreach-btn-ghost'}`}
                        style={{ minHeight: 28, padding: '2px 10px', fontSize: 11 }}
                      >
                        Спам
                      </button>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleSyncInbox}
                    disabled={syncingInbox}
                    className="outreach-btn outreach-btn-secondary"
                  >
                    <RefreshCw size={13} className={syncingInbox ? 'animate-spin' : ''} />
                    <span>{syncingInbox ? 'Синхронизация...' : 'Синхронизировать почту'}</span>
                  </button>
                </div>
              </div>

              {/* 2-Pane Split Inbox */}
              <div className="outreach-inbox-split">
                <div className="outreach-inbox-list">
                  {inboxMessages.length === 0 ? (
                    <div style={{ padding: '40px 16px', textAlign: 'center', color: '#94a3b8' }}>
                      <Inbox size={32} style={{ margin: '0 auto 8px', opacity: 0.6 }} />
                      <p style={{ margin: 0, fontWeight: 500, fontSize: 13 }}>Ответов по этой задаче пока нет</p>
                      <p style={{ margin: '4px 0 0', fontSize: 11 }}>
                        Ответы появятся здесь автоматически после рассылки по контактам этой задачи.
                      </p>
                    </div>
                  ) : (
                    inboxMessages.map((msg) => {
                      const isSelected = selectedMsg?.id === msg.id
                      const initial = (msg.sender_name || msg.sender_email || 'U').charAt(0).toUpperCase()
                      return (
                        <div
                          key={msg.id}
                          onClick={() => {
                            setSelectedMsg(msg)
                            if (!msg.is_read) {
                              outreachFetch(`/api/outreach/inbox/${msg.id}/read`, { method: 'PATCH' })
                            }
                          }}
                          className={`outreach-inbox-item ${isSelected ? 'selected' : ''}`}
                        >
                          <div className="outreach-inbox-avatar">{initial}</div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                              <strong style={{ fontSize: 12, color: !msg.is_read ? '#0f172a' : '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {msg.sender_name || msg.sender_email.split('@')[0]}
                              </strong>
                              <span style={{ fontSize: 10, color: '#94a3b8', flexShrink: 0 }}>{formatDate(msg.date_received)}</span>
                            </div>
                            <div style={{ fontSize: 12, fontWeight: !msg.is_read ? 700 : 500, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 2 }}>
                              {msg.subject || '(Без темы)'}
                            </div>
                            <div style={{ fontSize: 11, color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 2 }}>
                              {msg.body_text}
                            </div>
                            {msg.is_spam && (
                              <span className="outreach-badge spam" style={{ marginTop: 4 }}>
                                Спам
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>

                <div className="outreach-inbox-detail">
                  {selectedMsg ? (
                    <>
                      <div style={{ paddingBottom: 14, borderBottom: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#0f172a' }}>
                          {selectedMsg.subject || '(Без темы)'}
                        </h2>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <div className="outreach-inbox-avatar" style={{ width: 36, height: 36, fontSize: 14 }}>
                              {(selectedMsg.sender_name || selectedMsg.sender_email || 'U').charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <strong style={{ fontSize: 13, color: '#0f172a' }}>
                                {selectedMsg.sender_name || selectedMsg.sender_email}
                              </strong>
                              <div style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                                {selectedMsg.sender_email}
                              </div>
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <button
                              type="button"
                              onClick={() => handleToggleSpam(selectedMsg)}
                              className={`outreach-btn ${selectedMsg.is_spam ? 'outreach-btn-danger' : 'outreach-btn-secondary'}`}
                              title={selectedMsg.is_spam ? 'Убрать из спама' : 'В спам'}
                            >
                              <ShieldAlert size={14} />
                              <span>{selectedMsg.is_spam ? 'В спаме' : 'В спам'}</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => window.print()}
                              className="outreach-btn outreach-btn-secondary"
                              title="Распечатать письмо"
                            >
                              <Printer size={14} />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteInboxMsg(selectedMsg.id)}
                              className="outreach-btn outreach-btn-danger"
                              title="Удалить"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      </div>

                      <div style={{ fontSize: 13, lineHeight: 1.6, color: '#1e293b', whiteSpace: 'pre-wrap', flex: 1 }}>
                        {selectedMsg.body_text || '(Пустое тело письма)'}
                      </div>

                      <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                          <strong style={{ fontSize: 12, color: '#334155', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Sparkles size={14} style={{ color: '#4f46e5' }} />
                            Быстрый ответ с AI
                          </strong>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button
                              type="button"
                              onClick={() => handleAiReply('agree')}
                              disabled={aiReplyGenerating}
                              className="outreach-btn outreach-btn-secondary"
                              style={{ fontSize: 11, padding: '3px 8px' }}
                            >
                              ✓ Согласиться
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAiReply('request_quote')}
                              disabled={aiReplyGenerating}
                              className="outreach-btn outreach-btn-secondary"
                              style={{ fontSize: 11, padding: '3px 8px' }}
                            >
                              📋 Запросить КП
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAiReply('decline')}
                              disabled={aiReplyGenerating}
                              className="outreach-btn outreach-btn-secondary"
                              style={{ fontSize: 11, padding: '3px 8px' }}
                            >
                              ✕ Вежливый отказ
                            </button>
                          </div>
                        </div>

                        <textarea
                          rows={3}
                          placeholder="Напишите ответ или выберите шаблон выше..."
                          value={replyText}
                          onChange={(e) => setReplyText(e.target.value)}
                          style={{ minHeight: 70 }}
                        />

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: 11, color: '#94a3b8' }}>
                            Ответ будет отправлен через info@tenderlex.ru
                          </span>
                          <button
                            type="button"
                            onClick={handleSendReply}
                            disabled={sendingReply || !replyText.trim()}
                            className="outreach-btn outreach-btn-primary"
                          >
                            <Send size={13} />
                            <span>{sendingReply ? 'Отправка...' : 'Отправить ответ'}</span>
                          </button>
                        </div>
                      </div>
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

          {/* SUBTAB 5: SETTINGS */}
          {taskSubTab === 'settings' && (
            <div className="outreach-panel" style={{ maxWidth: 720 }}>
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
          )}
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
                  setTaskSubTab('compose')
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
