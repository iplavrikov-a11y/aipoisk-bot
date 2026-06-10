"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  FileText,
  HelpCircle,
  Loader2,
  LogOut,
  Mail,
  MessageCircle,
  Paperclip,
  Pencil,
  Receipt,
  Search,
  XCircle,
  type LucideIcon,
} from "lucide-react";

type JobMode = "supplier_search" | "procurement_report" | "analysis_and_suppliers";
type Scenario = "supplier_search" | "procurement_report" | "analysis_and_suppliers";

type BalanceCounter = {
  label: string;
  available: number | null;
  reserved: number;
  spent: number;
  granted: number;
  low: boolean;
};

type Tariff = {
  id: string;
  kind: string;
  name: string;
  units: number;
  price_kopeks: number;
  description: string;
};

type SessionPayload = {
  authenticated: boolean;
  csrf_token?: string;
  user?: {
    email: string;
    name: string;
    is_trial: boolean;
    is_email_verified: boolean;
  };
  balance?: {
    supplier_search: BalanceCounter;
    procurement_report: BalanceCounter;
  };
  limits?: {
    max_upload_mb: number;
    max_files_per_batch: number;
    default_supplier_target: number;
  };
  tariff_groups?: {
    supplier_search: Tariff[];
    procurement_report: Tariff[];
  };
  contacts?: {
    email: string;
    telegram: string;
    telegram_url: string;
    max: string;
    max_url: string;
  };
  payment?: {
    provider: string;
    instructions: string;
    yookassa_ready: boolean;
  };
  verification_email_sent?: boolean;
  message?: string;
};

type CustomerJob = {
  id: string;
  mode: JobMode;
  mode_label: string;
  status: string;
  status_label: string;
  progress: number;
  message: string;
  human_title: string;
  target_suppliers: number;
  verified_count: number;
  file_count: number;
  has_result: boolean;
  can_download: boolean;
  can_find_more_suppliers: boolean;
  result_files: Array<{
    kind: string;
    label: string;
    filename: string;
  }>;
  awaiting_customer_confirmation: boolean;
  error: string;
  created_at: string | null;
  updated_at: string | null;
};

type CustomerJobsResponse = {
  items: CustomerJob[];
  total: number;
  limit: number;
  offset: number;
};

const CUSTOMER_JOBS_PAGE_SIZE = 15;

const scenarioOptions: Array<{ id: Scenario; label: string; description: string; icon: LucideIcon }> = [
  {
    id: "supplier_search",
    label: "Поиск поставщиков",
    description: "ТЗ файлом, текстом или архивом",
    icon: Search,
  },
  {
    id: "procurement_report",
    label: "Анализ закупки",
    description: "номер, ссылка или документы закупки",
    icon: FileText,
  },
  {
    id: "analysis_and_suppliers",
    label: "Анализ + поиск",
    description: "анализ закупки и поставщики",
    icon: Receipt,
  },
];

const modeCopy: Record<Scenario, {
  mode: JobMode;
  uploadTitle: string;
  uploadText: string;
  multipleFiles: boolean;
  textLabel?: string;
  textPlaceholder?: string;
  sourceLabel?: string;
  sourcePlaceholder?: string;
  hint: string;
  submit: string;
}> = {
  supplier_search: {
    mode: "supplier_search",
    uploadTitle: "Загрузите ТЗ",
    uploadText: "Каждый отдельный файл даст отдельный поиск поставщиков.",
    multipleFiles: true,
    textLabel: "Или вставьте ТЗ текстом",
    textPlaceholder: "Например: сотовый поликарбонат 10 мм, прозрачный, лист 2,1 x 6 м, количество 120 листов. Нужны поставщики с контактами для запроса КП.",
    hint: "Если одно ТЗ состоит из нескольких файлов, объедините их в архив и загрузите одним файлом. Разные ТЗ загружайте отдельными файлами.",
    submit: "Запустить поиск поставщиков",
  },
  procurement_report: {
    mode: "procurement_report",
    uploadTitle: "Приложите документы закупки",
    uploadText: "Можно перетащить документацию, проект контракта или архив.",
    multipleFiles: true,
    sourceLabel: "Номер извещения или ссылка",
    sourcePlaceholder: "Например: номер извещения или ссылка на закупку",
    hint: "Можно указать только номер извещения или ссылку, если документация доступна по закупке.",
    submit: "Запустить анализ закупки",
  },
  analysis_and_suppliers: {
    mode: "analysis_and_suppliers",
    uploadTitle: "Приложите документы закупки или ТЗ",
    uploadText: "Можно перетащить материалы закупки, ТЗ или архив.",
    multipleFiles: true,
    sourceLabel: "Номер извещения или ссылка",
    sourcePlaceholder: "Например: номер извещения или ссылка на закупку",
    hint: "Результат: анализ закупки и поставщики по найденному ТЗ.",
    submit: "Запустить анализ + поиск",
  },
};

const statusClasses: Record<string, string> = {
  pending: "pending",
  running: "running",
  completed: "completed",
  partial: "completed",
  needs_review: "review",
  awaiting_customer_confirmation: "review",
  failed: "failed",
  customer_declined: "failed",
};

const MOSCOW_TIME_ZONE = "Europe/Moscow";

function apiDateValue(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return `${trimmed}T00:00:00Z`;
  }
  if (/(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed)) {
    return trimmed;
  }
  return `${trimmed}Z`;
}

function formatDate(value: string | null) {
  if (!value) return "-";
  const date = new Date(apiDateValue(value));
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short", timeZone: MOSCOW_TIME_ZONE });
}

function formatRubles(kopeks: number) {
  if (!kopeks) return "по запросу";
  return `${new Intl.NumberFormat("ru-RU").format(Math.round(kopeks / 100))} ₽`;
}

function balanceValue(counter?: BalanceCounter) {
  if (!counter) return "0";
  return counter.available === null ? "без лимита" : String(counter.available);
}

function accessValue(counter?: BalanceCounter) {
  return balanceValue(counter);
}

function tariffDisplayName(tariff: Tariff) {
  if (tariff.kind === "procurement_report") {
    return `${tariff.units} ${pluralizeRu(tariff.units, ["анализ закупки", "анализа закупки", "анализов закупки"])}`;
  }
  if (tariff.kind === "supplier_search") {
    return `${tariff.units} ${pluralizeRu(tariff.units, ["поиск поставщиков", "поиска поставщиков", "поисков поставщиков"])}`;
  }
  return tariff.name;
}

function modeDisplayName(mode: JobMode) {
  if (mode === "procurement_report") return "Анализ закупки";
  if (mode === "analysis_and_suppliers") return "Анализ + поиск";
  return "Поиск поставщиков";
}

function pluralizeRu(value: number, [one, few, many]: [string, string, string]) {
  const mod10 = Math.abs(value) % 10;
  const mod100 = Math.abs(value) % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function parseError(raw: string) {
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch {
    return raw;
  }
  return raw || "Ошибка запроса";
}

function filenameFromResponse(response: Response, fallback: string) {
  const header = response.headers.get("content-disposition") || "";
  const utf = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf?.[1]) return decodeURIComponent(utf[1]);
  const plain = header.match(/filename="?([^";]+)"?/i);
  return plain?.[1] || fallback;
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!response.ok) throw new Error(parseError(text));
  return text ? (JSON.parse(text) as T) : ({} as T);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function CabinetClient() {
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [jobs, setJobs] = useState<CustomerJob[]>([]);
  const [jobsPage, setJobsPage] = useState(1);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [authMode, setAuthMode] = useState<"login" | "register" | "reset">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [website, setWebsite] = useState("");
  const [emailDraft, setEmailDraft] = useState("");
  const [emailEditOpen, setEmailEditOpen] = useState(false);
  const [scenario, setScenario] = useState<Scenario>("supplier_search");
  const [text, setText] = useState("");
  const [sourceUrls, setSourceUrls] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [findMoreConfirmJob, setFindMoreConfirmJob] = useState<CustomerJob | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const csrf = session?.csrf_token || "";
  const authenticated = Boolean(session?.authenticated && session.user);
  const selectedCopy = modeCopy[scenario];
  const selectedMode = selectedCopy.mode;
  const acceptsSources = Boolean(selectedCopy.sourceLabel);
  const acceptsText = Boolean(selectedCopy.textLabel);
  const maxFiles = session?.limits?.max_files_per_batch || 20;
  const emailVerified = session?.user?.is_email_verified !== false;
  const supplierMultiFileWarning = scenario === "supplier_search" && selectedFiles.length > 1;
  const activeJobs = useMemo(
    () => jobs.filter((job) => ["pending", "running", "awaiting_customer_confirmation"].includes(job.status)).length,
    [jobs],
  );
  const jobsPageCount = Math.max(1, Math.ceil(jobsTotal / CUSTOMER_JOBS_PAGE_SIZE));
  const jobsStart = jobsTotal ? (jobsPage - 1) * CUSTOMER_JOBS_PAGE_SIZE + 1 : 0;
  const jobsEnd = Math.min(jobsTotal, jobsPage * CUSTOMER_JOBS_PAGE_SIZE);
  const hasFindMoreSuppliers = jobs.some((job) => job.can_find_more_suppliers);

  async function loadSession() {
    const response = await fetch("/api/customer/auth/session", { credentials: "same-origin" });
    if (response.status === 401 || response.status === 404) {
      setSession(null);
      return;
    }
    const payload = await readJson<SessionPayload>(response);
    setSession(payload.authenticated ? payload : null);
  }

  async function loadJobs(page = jobsPage) {
    if (!authenticated) return;
    setJobsLoading(true);
    try {
      const offset = (page - 1) * CUSTOMER_JOBS_PAGE_SIZE;
      const response = await fetch(`/api/customer/jobs?limit=${CUSTOMER_JOBS_PAGE_SIZE}&offset=${offset}&include_pagination=true`, { credentials: "same-origin" });
      const payload = await readJson<CustomerJobsResponse | CustomerJob[]>(response);
      if (Array.isArray(payload)) {
        setJobs(payload);
        setJobsTotal(payload.length);
        return;
      }
      const nextPageCount = Math.max(1, Math.ceil(payload.total / payload.limit));
      setJobsTotal(payload.total);
      if (page > nextPageCount) {
        setJobsPage(nextPageCount);
        return;
      }
      setJobs(payload.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setJobsLoading(false);
    }
  }

  function syncSelectedFiles(files: File[]) {
    setSelectedFiles(files);
    if (!fileInputRef.current) return;
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    fileInputRef.current.files = transfer.files;
  }

  function filesFromList(fileList: FileList | null) {
    const files = Array.from(fileList || []);
    const limited = selectedCopy.multipleFiles ? files.slice(0, maxFiles) : files.slice(0, 1);
    syncSelectedFiles(limited);
  }

  function clearSelectedFiles() {
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function selectScenario(next: Scenario) {
    setScenario(next);
    setText("");
    setSourceUrls("");
    clearSelectedFiles();
  }

  function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    filesFromList(event.currentTarget.files);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    filesFromList(event.dataTransfer.files);
  }

  useEffect(() => {
    loadSession().catch((err) => setError(err instanceof Error ? err.message : String(err)));
    const params = new URLSearchParams(window.location.search);
    const verified = params.get("email_verified");
    const verifyToken = params.get("email_verify_token");
    if (verified === "1") setMessage("Email подтверждён. Теперь можно запускать задачи.");
    if (verified === "0") setError("Ссылка подтверждения недействительна или устарела.");
    if (verifyToken) {
      confirmEmailToken(verifyToken).catch((err) => setError(err instanceof Error ? err.message : String(err)));
      params.delete("email_verify_token");
    }
    if (verified) {
      params.delete("email_verified");
    }
    if (verified || verifyToken) {
      const nextQuery = params.toString();
      window.history.replaceState(null, "", `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`);
    }
  }, []);

  useEffect(() => {
    if (session?.user?.email && !emailEditOpen) setEmailDraft(session.user.email);
  }, [emailEditOpen, session?.user?.email]);

  useEffect(() => {
    if (!authenticated) return;
    loadJobs();
    const timer = window.setInterval(loadJobs, 7000);
    return () => window.clearInterval(timer);
  }, [authenticated, jobsPage]);

  useEffect(() => {
    if (!findMoreConfirmJob) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setFindMoreConfirmJob(null);
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [findMoreConfirmJob]);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (authMode === "reset") {
        const response = await fetch("/api/customer/auth/password-reset/request", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const payload = await readJson<{ message?: string }>(response);
        setMessage(payload.message || "Заявка отправлена. Мы поможем восстановить доступ.");
        return;
      }
      const response = await fetch(`/api/customer/auth/${authMode}`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name, website: authMode === "register" ? website : "" }),
      });
      const payload = await readJson<SessionPayload>(response);
      setSession(payload);
      setPassword("");
      setWebsite("");
      setMessage(authMode === "register" ? (payload.message || "Кабинет создан. Подтвердите email, чтобы запускать задачи.") : "");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    if (!csrf) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/customer/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      await readJson(response);
      setSession(null);
      setJobs([]);
      setJobsPage(1);
      setJobsTotal(0);
      setFindMoreConfirmJob(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function resendVerification() {
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/customer/auth/verify-email/request", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      const payload = await readJson<{ message?: string }>(response);
      setMessage(payload.message || "Письмо отправлено. Проверьте почту.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmEmailToken(token: string) {
    if (!token) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/customer/auth/verify-email/confirm", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const payload = await readJson<{ user?: SessionPayload["user"] }>(response);
      if (payload.user) {
        setSession((current) => (current ? { ...current, user: payload.user } : current));
      }
      setMessage("Email подтверждён. Теперь можно запускать задачи.");
      await loadSession();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function changeAccountEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/customer/auth/email", {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf },
        body: JSON.stringify({ email: emailDraft }),
      });
      const payload = await readJson<SessionPayload>(response);
      setSession(payload);
      setEmailEditOpen(false);
      setMessage(payload.message || "Email обновлён. Проверьте письмо для подтверждения.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrf) return;
    if (!emailVerified) {
      setError("Подтвердите email, чтобы запускать задачи.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const form = new FormData();
      form.append("mode", selectedMode);
      form.append("text", acceptsText ? text : "");
      form.append("source_urls", acceptsSources ? sourceUrls : "");
      form.append("target_suppliers", "0");
      selectedFiles.forEach((file) => form.append("files", file));
      const response = await fetch("/api/customer/jobs", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
        body: form,
      });
      const payload = await readJson<{ batch: boolean; count: number }>(response);
      setText("");
      setSourceUrls("");
      clearSelectedFiles();
      setMessage(payload.batch ? `Запущено задач: ${payload.count}.` : "Задача запущена.");
      setJobsPage(1);
      await loadSession();
      await loadJobs(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadJob(job: CustomerJob) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/download`, { credentials: "same-origin" });
      if (!response.ok) throw new Error(parseError(await response.text()));
      downloadBlob(await response.blob(), filenameFromResponse(response, `${job.human_title || "result"}.zip`));
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadJobFile(job: CustomerJob, file: CustomerJob["result_files"][number]) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/download/${encodeURIComponent(file.kind)}`, { credentials: "same-origin" });
      if (!response.ok) throw new Error(parseError(await response.text()));
      downloadBlob(await response.blob(), filenameFromResponse(response, file.filename || `${job.human_title || "result"}`));
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function acceptPartial(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/accept-partial`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      if (!response.ok) throw new Error(parseError(await response.text()));
      await readJson(response);
      setMessage("Отчёт принят. Результат можно скачать в строке задачи.");
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function declinePartial(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/decline-partial`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      await readJson(response);
      await loadSession();
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function findMoreSuppliers(job: CustomerJob) {
    if (!csrf) return;
    setBusy(true);
    setError("");
    setMessage("");
    setFindMoreConfirmJob(null);
    try {
      const response = await fetch(`/api/customer/jobs/${job.id}/find-more-suppliers`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      const payload = await readJson<{ message?: string; job?: CustomerJob }>(response);
      setMessage(payload.message || "Запущен дополнительный поиск поставщиков.");
      setJobsPage(1);
      await loadSession();
      await loadJobs(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!authenticated) {
    return (
      <main className="cabinet-shell auth-shell">
        <header className="cabinet-header">
          <a className="brand" href="/">
            <Image src="/tenderlex-logo.png" alt="" width={32} height={32} priority />
            <span>TenderLex</span>
          </a>
          <a className="cabinet-header-link" href="/">
            На главную
            <ArrowRight size={16} aria-hidden="true" />
          </a>
        </header>
        <section className="auth-layout">
          <div className="auth-copy">
            <h1>Работайте с закупками прямо на сайте</h1>
            <p>Войдите или создайте кабинет, чтобы запускать анализ закупок, искать поставщиков и скачивать готовые результаты.</p>
            <div className="auth-benefits">
              <article>
                <FileText size={18} aria-hidden="true" />
                <strong>Анализ закупки</strong>
                <span>условия, риски, сроки, вопросы заказчику</span>
              </article>
              <article>
                <Search size={18} aria-hidden="true" />
                <strong>Поиск поставщиков</strong>
                <span>контакты компаний для запроса КП</span>
              </article>
              <article>
                <CheckCircle2 size={18} aria-hidden="true" />
                <strong>Вернуться к результатам</strong>
                <span>история задач и скачивание готовых файлов</span>
              </article>
            </div>
          </div>
          <form className="auth-panel" onSubmit={submitAuth}>
            {authMode === "reset" ? (
              <div className="auth-panel-title">
                <h2>Восстановить доступ</h2>
                <p>Укажите email кабинета. Мы проверим заявку и поможем войти снова.</p>
              </div>
            ) : (
              <div className="auth-tabs" role="tablist" aria-label="Режим входа">
                <button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>
                  Вход
                </button>
                <button type="button" className={authMode === "register" ? "active" : ""} onClick={() => setAuthMode("register")}>
                  Регистрация
                </button>
              </div>
            )}
            {authMode === "register" ? (
              <label>
                Имя
                <input value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" />
              </label>
            ) : null}
            {authMode === "register" ? (
              <label className="bot-trap" aria-hidden="true">
                Сайт
                <input value={website} onChange={(event) => setWebsite(event.target.value)} tabIndex={-1} autoComplete="off" />
              </label>
            ) : null}
            <label>
              Email
              <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" required />
            </label>
            {authMode !== "reset" ? (
              <label>
                Пароль
                <input
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  type="password"
                  autoComplete={authMode === "login" ? "current-password" : "new-password"}
                  minLength={8}
                  required
                />
              </label>
            ) : null}
            {error ? <div className="form-error">{error}</div> : null}
            {message ? <div className="form-success">{message}</div> : null}
            <button className="primary-action" type="submit" disabled={busy}>
              {busy ? <Loader2 size={18} aria-hidden="true" /> : <ArrowRight size={18} aria-hidden="true" />}
              {authMode === "reset" ? "Отправить заявку" : authMode === "login" ? "Войти" : "Создать кабинет"}
            </button>
            <button
              className="auth-secondary"
              type="button"
              onClick={() => {
                setError("");
                setMessage("");
                setAuthMode(authMode === "reset" ? "login" : "reset");
              }}
            >
              {authMode === "reset" ? "Вернуться ко входу" : "Не помню пароль"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="cabinet-shell">
      <header className="cabinet-header">
        <a className="brand" href="/">
          <Image src="/tenderlex-logo.png" alt="" width={32} height={32} priority />
          <span>TenderLex</span>
        </a>
        <div className="account-chip">
          <span>{session?.user?.email}</span>
          <button type="button" onClick={logout} disabled={busy} aria-label="Выйти">
            <LogOut size={17} aria-hidden="true" />
          </button>
        </div>
      </header>

      {(message || error) ? (
        <div className={`cabinet-toast ${error ? "error" : ""}`}>
          {error ? <XCircle size={18} aria-hidden="true" /> : <CheckCircle2 size={18} aria-hidden="true" />}
          {error || message}
        </div>
      ) : null}

      {!emailVerified ? (
        <section className="email-verify-banner">
          <Mail size={18} aria-hidden="true" />
          <div>
            <strong>Подтвердите email</strong>
            <span>После подтверждения можно запускать задачи на сайте.</span>
          </div>
          <div className="email-verify-actions">
            <button type="button" onClick={resendVerification} disabled={busy}>
              {busy ? <Loader2 size={16} aria-hidden="true" /> : <Mail size={16} aria-hidden="true" />}
              Отправить письмо
            </button>
            <button type="button" onClick={() => setEmailEditOpen((value) => !value)} disabled={busy}>
              <Pencil size={16} aria-hidden="true" />
              Исправить email
            </button>
          </div>
          {emailEditOpen ? (
            <form className="email-change-form" onSubmit={changeAccountEmail}>
              <label>
                Новый email
                <input value={emailDraft} onChange={(event) => setEmailDraft(event.target.value)} type="email" autoComplete="email" required />
              </label>
              <button type="submit" disabled={busy}>
                {busy ? <Loader2 size={16} aria-hidden="true" /> : <Mail size={16} aria-hidden="true" />}
                Сохранить и отправить письмо
              </button>
            </form>
          ) : null}
        </section>
      ) : null}

      <section className="cabinet-top">
        <div>
          <h1>Рабочий кабинет</h1>
          <p>{activeJobs ? `В обработке: ${activeJobs}` : "Активных обработок нет"}</p>
        </div>
        <a className="telegram-option" href="https://t.me/tenderlex_bot" target="_blank" rel="noreferrer">
          <MessageCircle size={17} aria-hidden="true" />
          Telegram-бот
        </a>
      </section>

      <section className="cabinet-grid">
        <form id="create" className="work-panel" onSubmit={submitJob}>
          <div className="panel-title">
            <h2>Выберите функцию</h2>
            <span>загрузка до {session?.limits?.max_upload_mb || 50} МБ</span>
          </div>
          <div className="scenario-grid" role="radiogroup" aria-label="Сценарий">
            {scenarioOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                className={scenario === option.id ? "active" : ""}
                onClick={() => selectScenario(option.id)}
              >
                <option.icon size={18} aria-hidden="true" />
                <strong>{option.label}</strong>
                <span>{option.description}</span>
              </button>
            ))}
          </div>

          <label
            className={`upload-zone ${dragActive ? "drag-active" : ""}`}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
          >
            <Paperclip size={20} aria-hidden="true" />
            <strong>{selectedCopy.uploadTitle}</strong>
            <span>{selectedCopy.uploadText}</span>
            <em>{selectedFiles.length ? `${selectedFiles.length} ${pluralizeRu(selectedFiles.length, ["файл выбран", "файла выбрано", "файлов выбрано"])}` : "Нажмите или перетащите файлы сюда"}</em>
            <input ref={fileInputRef} type="file" multiple={selectedCopy.multipleFiles} onChange={handleFileInput} />
          </label>

          {selectedFiles.length ? (
            <div className="selected-files" aria-label="Выбранные файлы">
              <div>
                {selectedFiles.map((file) => (
                  <span key={`${file.name}-${file.size}`}>{file.name}</span>
                ))}
              </div>
              <button type="button" onClick={clearSelectedFiles}>
                Очистить
              </button>
            </div>
          ) : null}

          <div className={`task-fields ${acceptsSources && acceptsText ? "" : "single"}`}>
            {acceptsSources ? (
              <label className="source-field">
                {selectedCopy.sourceLabel}
                <input
                  value={sourceUrls}
                  onChange={(event) => setSourceUrls(event.target.value)}
                  placeholder={selectedCopy.sourcePlaceholder}
                />
              </label>
            ) : null}
            {acceptsText ? (
              <label>
                {selectedCopy.textLabel}
                <textarea
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  rows={5}
                  placeholder={selectedCopy.textPlaceholder}
                />
              </label>
            ) : null}
          </div>

          <p className="task-hint">{selectedCopy.hint}</p>
          {supplierMultiFileWarning ? (
            <p className="task-hint task-hint-warning">
              Выбрано {selectedFiles.length} {pluralizeRu(selectedFiles.length, ["файл", "файла", "файлов"])}. Они будут обработаны как отдельные ТЗ. Если это части одного ТЗ, объедините их в архив и загрузите одним файлом.
            </p>
          ) : null}
          {!emailVerified ? <p className="task-hint">Подтвердите email, чтобы запускать задачи.</p> : null}

          <div className="submit-row submit-row-compact">
            <button className="primary-action" type="submit" disabled={busy || !emailVerified}>
              {busy ? <Loader2 size={18} aria-hidden="true" /> : <ArrowRight size={18} aria-hidden="true" />}
              {selectedCopy.submit}
            </button>
          </div>
        </form>

        <aside id="balance" className="side-rail">
          <section className="balance-panel">
            <div className="panel-title">
              <h2>Доступно</h2>
              {session?.user?.is_trial ? <span>пробный доступ</span> : null}
            </div>
            <div className="balance-row">
              <Search size={18} aria-hidden="true" />
              <div>
                <span>Поиск поставщиков</span>
                <strong>{accessValue(session?.balance?.supplier_search)}</strong>
              </div>
            </div>
            <div className="balance-row">
              <FileText size={18} aria-hidden="true" />
              <div>
                <span>Анализ закупки</span>
                <strong>{accessValue(session?.balance?.procurement_report)}</strong>
              </div>
            </div>
          </section>

          <section className="payment-panel">
            <div className="panel-title">
              <h2>Пополнить доступ</h2>
              <span>через менеджера</span>
            </div>
            <div className="payment-copy">
              <p>Выберите пакет ниже и напишите в Telegram: укажите email кабинета и нужный пакет. После подтверждения мы начислим доступ.</p>
              <p>Возможен индивидуальный подход: если нужен больший лимит поставщиков, больше компаний в одном поиске или другой объём генераций, напишите нам — настроим условия под вашу задачу.</p>
            </div>
            <div className="payment-tariffs">
              <TariffList title="Поиск поставщиков" tariffs={session?.tariff_groups?.supplier_search || []} />
              <TariffList title="Анализ закупки" tariffs={session?.tariff_groups?.procurement_report || []} />
            </div>
            <div className="contact-actions">
              {session?.contacts?.telegram_url ? (
                <a href={session.contacts.telegram_url} target="_blank" rel="noreferrer">
                  <MessageCircle size={16} aria-hidden="true" />
                  Написать в Telegram
                </a>
              ) : null}
              {session?.contacts?.max_url ? (
                <a href={session.contacts.max_url} target="_blank" rel="noreferrer">
                  <MessageCircle size={16} aria-hidden="true" />
                  Написать в MAX
                </a>
              ) : session?.contacts?.max ? (
                <span className="contact-text">
                  <MessageCircle size={16} aria-hidden="true" />
                  MAX: {session.contacts.max}
                </span>
              ) : null}
              {session?.contacts?.email ? (
                <a href={`mailto:${session.contacts.email}`}>
                  <Mail size={16} aria-hidden="true" />
                  Написать на email
                </a>
              ) : null}
            </div>
          </section>
        </aside>
      </section>

      <section id="jobs" className="jobs-panel">
        <div className="panel-title">
          <h2>Задачи</h2>
          <span>{jobsTotal ? `${jobsStart}-${jobsEnd} из ${jobsTotal}` : "0 задач"}</span>
          {jobsTotal > CUSTOMER_JOBS_PAGE_SIZE ? (
            <div className="jobs-pagination jobs-pagination-inline" aria-label="Навигация по задачам">
              <button type="button" onClick={() => setJobsPage((page) => Math.max(1, page - 1))} disabled={jobsPage <= 1 || jobsLoading}>
                <ChevronLeft size={16} aria-hidden="true" />
                Назад
              </button>
              <span>Страница {jobsPage} из {jobsPageCount}</span>
              <button type="button" onClick={() => setJobsPage((page) => Math.min(jobsPageCount, page + 1))} disabled={jobsPage >= jobsPageCount || jobsLoading}>
                Вперёд
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          ) : null}
          <button type="button" onClick={() => void loadJobs()} disabled={jobsLoading}>
            {jobsLoading ? <Loader2 size={16} aria-hidden="true" /> : <Clock3 size={16} aria-hidden="true" />}
            Обновить
          </button>
        </div>
        {hasFindMoreSuppliers ? (
          <p className="jobs-help">
            В готовом поиске кнопка «Найти ещё» запускает новый платный добор по тому же ТЗ: списывается одна генерация, а уже найденные компании исключаются из результата.
          </p>
        ) : null}
        <div className="jobs-table">
          <div className="jobs-head">
            <span>Задача</span>
            <span>Режим</span>
            <span>Статус</span>
            <span>Прогресс</span>
            <span>Результат</span>
          </div>
          {jobs.length ? (
            jobs.map((job) => (
              <article key={job.id} className="job-row">
                <div>
                  <strong>{job.human_title}</strong>
                  <span>{formatDate(job.created_at)} · файлов: {job.file_count}</span>
                </div>
                <div>{modeDisplayName(job.mode)}</div>
                <div>
                  <span className={`status-pill ${statusClasses[job.status] || ""}`}>{job.status_label}</span>
                  {job.error ? <small>{job.error}</small> : null}
                </div>
                <div>
                  <div className="progress-line" aria-label={`Прогресс ${job.progress}%`}>
                    <i style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }} />
                  </div>
                  <span>{job.message || `${job.progress}%`}</span>
                </div>
                <div className="job-actions">
                  {job.awaiting_customer_confirmation ? (
                    <>
                      <button type="button" onClick={() => acceptPartial(job)} disabled={busy}>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        Принять
                      </button>
                      <button type="button" onClick={() => declinePartial(job)} disabled={busy}>
                        <XCircle size={16} aria-hidden="true" />
                        Отказаться
                      </button>
                    </>
                  ) : (
                    <>
                      {job.result_files?.length ? (
                        job.result_files.map((file) => (
                          <button key={`${job.id}-${file.kind}`} type="button" onClick={() => downloadJobFile(job, file)} disabled={busy}>
                            <Download size={16} aria-hidden="true" />
                            {file.label || "Скачать"}
                          </button>
                        ))
                      ) : job.can_download ? (
                        <button type="button" onClick={() => downloadJob(job)} disabled={busy}>
                          <Download size={16} aria-hidden="true" />
                          Скачать
                        </button>
                      ) : null}
                      {job.can_find_more_suppliers ? (
                        <button
                          type="button"
                          className="secondary-action"
                          onClick={() => setFindMoreConfirmJob(job)}
                          disabled={busy}
                          title="Новый поиск поставщиков списывает одну генерацию"
                        >
                          <Search size={16} aria-hidden="true" />
                          Найти ещё
                        </button>
                      ) : null}
                      {!job.result_files?.length && !job.can_download && !job.can_find_more_suppliers ? (
                        <span className="muted-action">-</span>
                      ) : null}
                    </>
                  )}
                </div>
              </article>
            ))
          ) : (
            <div className="empty-jobs">
              <HelpCircle size={20} aria-hidden="true" />
              Задач пока нет
            </div>
          )}
        </div>
        {jobsTotal > CUSTOMER_JOBS_PAGE_SIZE ? (
          <div className="jobs-pagination" aria-label="Навигация по задачам">
            <button type="button" onClick={() => setJobsPage((page) => Math.max(1, page - 1))} disabled={jobsPage <= 1 || jobsLoading}>
              <ChevronLeft size={16} aria-hidden="true" />
              Назад
            </button>
            <span>Страница {jobsPage} из {jobsPageCount}</span>
            <button type="button" onClick={() => setJobsPage((page) => Math.min(jobsPageCount, page + 1))} disabled={jobsPage >= jobsPageCount || jobsLoading}>
              Вперёд
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
        ) : null}
      </section>

      {findMoreConfirmJob ? (
        <div
          className="confirm-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setFindMoreConfirmJob(null);
          }}
        >
          <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="find-more-confirm-title" aria-describedby="find-more-confirm-copy">
            <div className="confirm-icon">
              <Search size={18} aria-hidden="true" />
            </div>
            <div>
              <h2 id="find-more-confirm-title">Найти ещё поставщиков?</h2>
              <p id="find-more-confirm-copy">Спишется 1 генерация поиска поставщиков. Уже найденные компании не попадут в новый результат.</p>
              <span>{findMoreConfirmJob.human_title}</span>
            </div>
            <div className="confirm-actions">
              <button className="confirm-cancel" type="button" onClick={() => setFindMoreConfirmJob(null)} disabled={busy}>
                Отмена
              </button>
              <button className="primary-action" type="button" onClick={() => void findMoreSuppliers(findMoreConfirmJob)} disabled={busy}>
                {busy ? <Loader2 size={16} aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
                Продолжить
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function TariffList({ title, tariffs }: { title: string; tariffs: Tariff[] }) {
  return (
    <div className="mini-tariffs">
      <span>{title}</span>
      {tariffs.slice(0, 3).map((tariff) => (
        <div key={tariff.id}>
          <strong>{tariffDisplayName(tariff)}</strong>
          <b>{formatRubles(tariff.price_kopeks)}</b>
        </div>
      ))}
    </div>
  );
}
