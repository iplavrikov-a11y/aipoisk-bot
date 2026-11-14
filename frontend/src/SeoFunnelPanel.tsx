import { useEffect, useState } from 'react'

type Counts = {
  entries: number
  registrations: number
  task_started: number
  result_ready: number
  first_payment: number
}

type Funnel = {
  period: { start_date: string; end_date: string }
  totals: Counts
  rows: Array<Counts & { source: string; landing: string }>
}

const stages: Array<[keyof Counts, string]> = [
  ['entries', 'Входы из поиска'],
  ['registrations', 'Новые регистрации'],
  ['task_started', 'Заказали задачу'],
  ['result_ready', 'Получили готовый результат'],
  ['first_payment', 'Подтверждённые оплаты'],
]

const engines: Record<string, string> = { google: 'Google', yandex: 'Яндекс', bing: 'Bing' }
const fmt = new Intl.NumberFormat('ru-RU')
const date = (value: string) => value.split('-').reverse().join('.')

export function SeoFunnelPanel() {
  const [report, setReport] = useState<Funnel | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const response = await fetch('/api/seo-analytics/funnel', {
          credentials: 'same-origin',
          cache: 'no-store',
          signal: controller.signal,
        })
        if (!response.ok) throw new Error(String(response.status))
        const data: Funnel = await response.json()
        if (!controller.signal.aborted) {
          setReport(data)
          setFailed(false)
        }
      } catch {
        if (!controller.signal.aborted) setFailed(true)
      }
    }
    void load()
    const timer = window.setInterval(load, 120000)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [])

  return (
    <section className="seo-panel" aria-label="Воронка поискового трафика">
      <h2>Воронка поискового трафика</h2>
      {failed && <p className="seo-notice" role="status">Обновление воронки недоступно.</p>}
      {!report && !failed && <p className="seo-empty">Загрузка…</p>}
      {report && <>
        <p className="seo-caption">
          {date(report.period.start_date)} — {date(report.period.end_date)} по Москве.
          Учитывается первый распознанный вход из поиска в браузере с согласием на аналитику.
        </p>
        <p className="seo-caption">
          Регистрации, задачи, результаты и оплаты подтверждаются данными TenderLex. Оплата может предшествовать задаче.
          Действия учитываются и после окна входа, поэтому свежие группы продолжают накапливать результаты.
        </p>
        <div className="seo-stats">
          {stages.map(([key, label]) => (
            <div className="seo-stat" key={key}>
              <span>{label}</span>
              <strong>{fmt.format(report.totals[key])}</strong>
            </div>
          ))}
        </div>
        {report.rows.length ? (
          <div className="seo-table-scroll">
            <table className="seo-table" aria-label="Поисковые системы и посадочные страницы">
              <thead><tr><th>Система</th><th>Страница входа</th>{stages.map(([key, label]) => <th key={key}>{label}</th>)}</tr></thead>
              <tbody>
                {report.rows.map((row) => (
                  <tr key={`${row.source}:${row.landing}`}>
                    <td>{engines[row.source] || row.source}</td>
                    <td className="seo-query">{row.landing}</td>
                    {stages.map(([key]) => <td key={key}>{fmt.format(row[key])}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="seo-empty">В этом периоде пока нет измеренных входов.</p>}
      </>}
    </section>
  )
}
