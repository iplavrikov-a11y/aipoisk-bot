import React, { useState, useMemo, useEffect } from 'react'
import {
  ArrowLeft,
  User,
  Phone,
  Mail,
  ExternalLink,
  Search,
  Download,
  Paperclip,
  MessageSquare,
  Check,
  Loader2,
  Save,
  FileText,
  Filter,
  CornerDownLeft,
  Globe,
  Wallet,
} from 'lucide-react'
import {
  DialogClientProfile,
  DialogJobResultFile,
  DialogJobSummary,
  PendingJobFileAttachment,
} from './types'
import { formatDate, formatMoneyKopeks, jobStatusMeta } from './constants'

interface DialogContextPanelProps {
  client: DialogClientProfile | null
  jobs: DialogJobSummary[]
  generalMessagesCount: number
  activeJobFilter: string
  onSelectJobFilter: (jobId: string) => void
  onSetReplyJob: (jobId: string) => void
  onAttachJobFile: (item: PendingJobFileAttachment) => void
  onOpenJob?: (jobId: string, clientId?: string, jobNumber?: number | null) => void
  onOpenClient?: (clientId: string) => void
  onSaveNotes: (clientId: string, notes: string) => Promise<void>
  onBackToThread?: () => void
}

type JobsTab = 'with_chat' | 'with_result' | 'all'

export function DialogContextPanel({
  client,
  jobs,
  generalMessagesCount,
  activeJobFilter,
  onSelectJobFilter,
  onSetReplyJob,
  onAttachJobFile,
  onOpenJob,
  onOpenClient,
  onSaveNotes,
  onBackToThread,
}: DialogContextPanelProps) {
  const [jobSearch, setJobSearch] = useState('')
  const [jobsTab, setJobsTab] = useState<JobsTab>('all')
  const [visibleLimit, setVisibleLimit] = useState(25)
  const [notesDraft, setNotesDraft] = useState('')
  const [savingNotes, setSavingNotes] = useState(false)
  const [notesSavedOk, setNotesSavedOk] = useState(false)

  useEffect(() => {
    setNotesDraft(client?.notes || '')
    setNotesSavedOk(false)
    setJobSearch('')
    setVisibleLimit(25)
    // Default to 'with_chat' if there are many jobs and at least 1 has chat messages
    const hasChatted = jobs.some(j => (j.chat_messages_count || 0) > 0)
    if (jobs.length > 15 && hasChatted) {
      setJobsTab('with_chat')
    } else {
      setJobsTab('all')
    }
  }, [client?.id])

  useEffect(() => {
    if (client && !savingNotes) {
      setNotesDraft(client.notes || '')
    }
  }, [client?.notes])

  const chattedCount = useMemo(() => jobs.filter(j => (j.chat_messages_count || 0) > 0).length, [jobs])
  const resultCount = useMemo(() => jobs.filter(j => Boolean(j.has_result || j.result_files?.length || j.rerun_files?.length)).length, [jobs])

  const filteredJobs = useMemo(() => {
    const q = jobSearch.trim().toLowerCase()
    return jobs.filter(j => {
      if (jobsTab === 'with_chat' && !(j.chat_messages_count && j.chat_messages_count > 0)) return false
      if (jobsTab === 'with_result' && !(j.has_result || j.result_files?.length || j.rerun_files?.length)) return false
      if (!q) return true
      return (
        j.job_title.toLowerCase().includes(q) ||
        j.job_mode_label.toLowerCase().includes(q) ||
        (j.job_number && String(j.job_number).includes(q)) ||
        j.job_id.toLowerCase().includes(q)
      )
    })
  }, [jobs, jobsTab, jobSearch])

  const visibleJobs = useMemo(() => filteredJobs.slice(0, visibleLimit), [filteredJobs, visibleLimit])
  const remainingCount = Math.max(0, filteredJobs.length - visibleJobs.length)

  if (!client) {
    if (!onBackToThread) return null
    return (
      <div
        className="dialogs-context-col"
        style={{
          width: 350,
          minWidth: 280,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          background: '#fff',
          borderRadius: 10,
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
        }}
      >
        <div
          className="dialogs-mobile-context-bar"
          style={{
            padding: '8px 12px',
            borderBottom: '1px solid #e2e8f0',
            background: '#f8fafc',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <button
            type="button"
            className="ghost"
            onClick={onBackToThread}
            style={{ minHeight: 32, padding: '4px 10px', fontSize: 12, fontWeight: 600 }}
          >
            <ArrowLeft size={14} />
            <span>Назад к переписке</span>
          </button>
        </div>
        <div style={{ padding: 24, color: '#64748b', fontSize: 13, textAlign: 'center' }}>
          Загрузка карточки клиента и задач…
        </div>
      </div>
    )
  }

  const notesDirty = !client.is_guest && notesDraft !== (client.notes || '')

  async function handleNotesSave() {
    if (!client || client.is_guest || savingNotes) return
    setSavingNotes(true)
    setNotesSavedOk(false)
    try {
      await onSaveNotes(client.id, notesDraft)
      setNotesSavedOk(true)
      setTimeout(() => setNotesSavedOk(false), 2500)
    } finally {
      setSavingNotes(false)
    }
  }

  return (
    <div
      className="dialogs-context-col"
      style={{
        width: 350,
        minWidth: 280,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        background: '#fff',
        borderRadius: 10,
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
      }}
    >
      {/* Client Card Section */}
      {onBackToThread && (
        <div
          className="dialogs-mobile-context-bar"
          style={{
            padding: '8px 12px',
            borderBottom: '1px solid #e2e8f0',
            background: '#f8fafc',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <button
            type="button"
            className="ghost"
            onClick={onBackToThread}
            style={{ minHeight: 32, padding: '4px 10px', fontSize: 12, fontWeight: 600 }}
          >
            <ArrowLeft size={14} />
            <span>Назад к переписке</span>
          </button>
        </div>
      )}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid #e2e8f0', background: '#fafafa', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 700, color: '#0f172a', minWidth: 0 }}>
            <User size={15} color="#0d9488" />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {client.is_guest ? 'Гость сайта' : `Карточка клиента${client.number ? ` #${client.number}` : ''}`}
            </span>
          </div>
          {!client.is_guest && onOpenClient && (
            <button
              type="button"
              onClick={() => onOpenClient(client.id)}
              className="ghost"
              style={{ minHeight: 24, padding: '2px 7px', fontSize: 11, fontWeight: 600 }}
              title="Открыть в разделе «Клиенты»"
            >
              <ExternalLink size={11} />
              <span>Профиль</span>
            </button>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11.5, color: '#334155' }}>
          {client.phone && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Phone size={12} color="#0d9488" />
              <a href={`tel:${client.phone}`} style={{ color: '#0f766e', fontWeight: 600, textDecoration: 'none' }}>
                {client.phone}
              </a>
            </div>
          )}
          {client.email && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Mail size={12} color="#64748b" />
              <a href={`mailto:${client.email}`} style={{ color: '#334155', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {client.email}
              </a>
            </div>
          )}
          {(client.username || client.telegram_id) && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#0284c7' }}>
              <span>✈️</span>
              <span>
                {client.username ? `@${client.username.replace(/^@/, '')}` : ''}
                {client.username && client.telegram_id ? ' · ' : ''}
                {client.telegram_id ? `ID ${client.telegram_id}` : ''}
              </span>
            </div>
          )}
          {!client.is_guest && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginTop: 2, padding: '5px 8px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 6 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#475569', fontSize: 11 }}>
                <Wallet size={12} color="#0d9488" />
                Баланс:
              </span>
              <strong style={{ color: '#0f172a', fontSize: 12 }}>
                {formatMoneyKopeks(client.available_kopeks)}
              </strong>
            </div>
          )}
          {client.is_guest && client.source_url && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#64748b' }}>
              <Globe size={12} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={client.source_url}>
                {client.source_url}
              </span>
            </div>
          )}
        </div>

        {/* Internal Notes for registered clients */}
        {!client.is_guest && (
          <div style={{ marginTop: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                Заметка для команды
              </span>
              {notesSavedOk && (
                <span style={{ fontSize: 10.5, color: '#047857', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                  <Check size={11} /> Сохранено
                </span>
              )}
            </div>
            <textarea
              rows={2}
              value={notesDraft}
              onChange={e => setNotesDraft(e.target.value)}
              placeholder="Договорённости, особенности клиента (клиент не видит)..."
              style={{
                width: '100%',
                minHeight: 46,
                maxHeight: 90,
                fontSize: 11.5,
                padding: '5px 8px',
                borderRadius: 6,
                border: '1px solid #cbd5e1',
                background: '#fff',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />
            {notesDirty && (
              <button
                type="button"
                onClick={() => void handleNotesSave()}
                disabled={savingNotes}
                style={{
                  marginTop: 4,
                  width: '100%',
                  minHeight: 26,
                  fontSize: 11,
                  padding: '3px 8px',
                  background: '#0d9488',
                  color: '#fff',
                }}
              >
                {savingNotes ? <Loader2 size={12} className="spin" /> : <Save size={12} />}
                <span>Сохранить заметку</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Jobs & Results Section */}
      {!client.is_guest ? (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px 8px', borderBottom: '1px solid #f1f5f9', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 7 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12.5, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 5 }}>
                <FileText size={14} color="#0d9488" />
                Задачи и результаты ({jobs.length})
              </span>
              {activeJobFilter !== 'all' && (
                <button
                  type="button"
                  onClick={() => onSelectJobFilter('all')}
                  style={{ minHeight: 22, padding: '1px 7px', fontSize: 10.5, background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}
                >
                  Показать все
                </button>
              )}
            </div>

            {jobs.length > 0 && (
              <>
                <div style={{ position: 'relative' }}>
                  <Search size={12} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                  <input
                    type="text"
                    placeholder="Поиск по #номеру или названию ТЗ..."
                    value={jobSearch}
                    onChange={e => {
                      setJobSearch(e.target.value)
                      setVisibleLimit(25)
                    }}
                    style={{ width: '100%', minHeight: 28, padding: '4px 8px 4px 25px', fontSize: 11.5, background: '#f8fafc' }}
                  />
                </div>

                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => { setJobsTab('with_chat'); setVisibleLimit(25) }}
                    style={{
                      minHeight: 22,
                      padding: '2px 7px',
                      fontSize: 10.5,
                      borderRadius: 5,
                      background: jobsTab === 'with_chat' ? '#0284c7' : '#f1f5f9',
                      color: jobsTab === 'with_chat' ? '#fff' : '#475569',
                    }}
                  >
                    С перепиской ({chattedCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => { setJobsTab('with_result'); setVisibleLimit(25) }}
                    style={{
                      minHeight: 22,
                      padding: '2px 7px',
                      fontSize: 10.5,
                      borderRadius: 5,
                      background: jobsTab === 'with_result' ? '#0d9488' : '#f1f5f9',
                      color: jobsTab === 'with_result' ? '#fff' : '#475569',
                    }}
                  >
                    С результатом ({resultCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => { setJobsTab('all'); setVisibleLimit(25) }}
                    style={{
                      minHeight: 22,
                      padding: '2px 7px',
                      fontSize: 10.5,
                      borderRadius: 5,
                      background: jobsTab === 'all' ? '#334155' : '#f1f5f9',
                      color: jobsTab === 'all' ? '#fff' : '#475569',
                    }}
                  >
                    Все ({jobs.length})
                  </button>
                </div>
              </>
            )}
          </div>

          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '8px 12px 12px', display: 'flex', flexDirection: 'column', gap: 8, background: '#f8fafc' }}>
            {/* General chat shortcut card */}
            {generalMessagesCount > 0 && !jobSearch.trim() && (
              <div
                onClick={() => onSelectJobFilter(activeJobFilter === 'general' ? 'all' : 'general')}
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: activeJobFilter === 'general' ? '1.5px solid #0d9488' : '1px solid #e2e8f0',
                  background: activeJobFilter === 'general' ? '#f0fdfa' : '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: 11.5,
                }}
              >
                <span style={{ fontWeight: 600, color: '#334155' }}>💬 Общие сообщения (без задачи)</span>
                <span style={{ fontSize: 10.5, fontWeight: 700, background: '#f1f5f9', color: '#475569', padding: '1px 6px', borderRadius: 99 }}>
                  {generalMessagesCount}
                </span>
              </div>
            )}

            {visibleJobs.length === 0 ? (
              <div style={{ padding: '24px 10px', textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
                {jobs.length === 0
                  ? 'У клиента пока нет задач'
                  : jobsTab === 'with_chat'
                    ? 'Нет задач с перепиской'
                    : 'Подходящие задачи не найдены'}
              </div>
            ) : (
              visibleJobs.map(j => {
                const st = jobStatusMeta(j.job_status)
                const isFiltered = activeJobFilter === j.job_id
                const primaryFiles: DialogJobResultFile[] = j.result_files || []
                const rerunFiles: DialogJobResultFile[] = j.rerun_files || []
                const allFiles: Array<{ file: DialogJobResultFile; sourceJobId: string; isRerun: boolean }> = [
                  ...primaryFiles.map(f => ({ file: f, sourceJobId: j.job_id, isRerun: false })),
                  ...rerunFiles.map(f => ({ file: f, sourceJobId: j.rerun_id || j.job_id, isRerun: true })),
                ]
                return (
                  <div
                    key={j.job_id}
                    style={{
                      padding: '9px 10px',
                      borderRadius: 8,
                      border: isFiltered ? '1.5px solid #0284c7' : '1px solid #e2e8f0',
                      background: isFiltered ? '#f0f9ff' : '#fff',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: '#0369a1', background: '#e0f2fe', padding: '1px 6px', borderRadius: 4 }}>
                          #{j.job_number || j.job_id.slice(0, 5)}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            background: st.bg,
                            color: st.color,
                            border: `1px solid ${st.border}`,
                            padding: '1px 5px',
                            borderRadius: 4,
                          }}
                        >
                          {st.label}
                        </span>
                        {j.chat_messages_count ? (
                          <span style={{ fontSize: 10, fontWeight: 700, background: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4', padding: '1px 5px', borderRadius: 4 }}>
                            💬 {j.chat_messages_count}
                          </span>
                        ) : null}
                      </div>
                      <span style={{ fontSize: 10, color: '#94a3b8' }}>
                        {j.created_at ? formatDate(j.created_at).split(',')[0] : ''}
                      </span>
                    </div>

                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: '#0f172a',
                        lineHeight: 1.35,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                      title={j.job_title}
                    >
                      {j.job_title}
                    </div>

                    <div style={{ fontSize: 10.5, color: '#64748b' }}>
                      {j.job_mode_label}
                      {j.verified_count ? ` · найдено: ${j.verified_count}` : ''}
                    </div>

                    {j.error && j.job_status === 'failed' && (
                      <div style={{ fontSize: 10.5, color: '#b91c1c', background: '#fef2f2', padding: '4px 6px', borderRadius: 5, lineHeight: 1.3 }}>
                        {j.error.slice(0, 120)}
                      </div>
                    )}

                    {/* Result files list */}
                    {allFiles.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingTop: 4, borderTop: '1px dashed #e2e8f0' }}>
                        {allFiles.map((entry, idx) => (
                          <div
                            key={`${entry.sourceJobId}-${entry.file.kind}-${idx}`}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              gap: 4,
                              background: '#f8fafc',
                              border: '1px solid #e2e8f0',
                              borderRadius: 5,
                              padding: '3px 6px',
                            }}
                          >
                            <a
                              href={`/api/jobs/${encodeURIComponent(entry.sourceJobId)}/download/${encodeURIComponent(entry.file.kind)}`}
                              target="_blank"
                              rel="noreferrer"
                              download
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                                fontSize: 10.5,
                                color: '#0f766e',
                                fontWeight: 600,
                                textDecoration: 'none',
                                minWidth: 0,
                                flex: 1,
                              }}
                              title={`Скачать: ${entry.file.filename}`}
                            >
                              <Download size={11} style={{ flexShrink: 0 }} />
                              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {entry.isRerun ? '👑 ' : ''}{entry.file.label || entry.file.filename}
                              </span>
                            </a>
                            <button
                              type="button"
                              onClick={() => {
                                onSetReplyJob(j.job_id)
                                onAttachJobFile({
                                  job_id: entry.sourceJobId,
                                  job_number: j.job_number,
                                  kind: entry.file.kind,
                                  filename: entry.file.filename,
                                  label: entry.file.label || entry.file.filename,
                                })
                              }}
                              title="Прикрепить этот файл к ответу в чате"
                              style={{
                                minHeight: 20,
                                padding: '1px 6px',
                                fontSize: 10,
                                fontWeight: 600,
                                borderRadius: 4,
                                background: '#ecfdf5',
                                color: '#047857',
                                border: '1px solid #a7f3d0',
                                flexShrink: 0,
                              }}
                            >
                              <Paperclip size={10} />
                              <span>В чат</span>
                            </button>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Quick actions on job card */}
                    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', paddingTop: 2 }}>
                      <button
                        type="button"
                        onClick={() => onSelectJobFilter(isFiltered ? 'all' : j.job_id)}
                        style={{
                          flex: 1,
                          minHeight: 24,
                          padding: '2px 6px',
                          fontSize: 10.5,
                          fontWeight: 600,
                          borderRadius: 5,
                          background: isFiltered ? '#0284c7' : '#f1f5f9',
                          color: isFiltered ? '#fff' : '#334155',
                          border: '1px solid #cbd5e1',
                        }}
                        title="Показать переписку только по этой задаче"
                      >
                        <Filter size={10} />
                        <span>{isFiltered ? 'Сбросить' : 'Переписка'}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onSetReplyJob(j.job_id)}
                        style={{
                          flex: 1,
                          minHeight: 24,
                          padding: '2px 6px',
                          fontSize: 10.5,
                          fontWeight: 600,
                          borderRadius: 5,
                          background: '#f0fdfa',
                          color: '#0f766e',
                          border: '1px solid #99f6e4',
                        }}
                        title="Написать ответ в контексте этой задачи"
                      >
                        <CornerDownLeft size={10} />
                        <span>Ответить</span>
                      </button>
                      {onOpenJob && (
                        <button
                          type="button"
                          onClick={() => onOpenJob(j.job_id, client.id, j.job_number)}
                          style={{
                            minHeight: 24,
                            padding: '2px 7px',
                            fontSize: 10.5,
                            fontWeight: 600,
                            borderRadius: 5,
                            background: '#fff',
                            color: '#475569',
                            border: '1px solid #cbd5e1',
                          }}
                          title="Открыть эту задачу в разделе «Задачи»"
                        >
                          <ExternalLink size={10} />
                        </button>
                      )}
                    </div>
                  </div>
                )
              })
            )}

            {remainingCount > 0 && (
              <button
                type="button"
                onClick={() => setVisibleLimit(v => v + 25)}
                className="ghost"
                style={{ width: '100%', minHeight: 30, fontSize: 11.5 }}
              >
                Показать ещё ({remainingCount} осталось)
              </button>
            )}
          </div>
        </div>
      ) : (
        <div style={{ padding: 16, fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
          <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
            <MessageSquare size={14} color="#0d9488" />
            Гостевое обращение
          </div>
          <p style={{ margin: 0 }}>
            Посетитель написал через виджет чата на сайте без регистрации в кабинете. После регистрации задачи и история появятся в карточке клиента.
          </p>
        </div>
      )}
    </div>
  )
}
