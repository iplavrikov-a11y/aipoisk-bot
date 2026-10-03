import { useEffect, useState, type ReactNode } from 'react'
import './seo-dashboard.css'

type Data = Record<string, unknown>
const object = (value: unknown): Data =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Data)
    : {}
const rows = (value: unknown): Data[] =>
  Array.isArray(value)
    ? value.filter(
        (item) => item && typeof item === 'object' && !Array.isArray(item),
      )
    : []
const number = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? value
    : null
const shown = (value: unknown, digits = 0) =>
  number(value)?.toLocaleString('ru-RU', { maximumFractionDigits: digits }) ??
  '—'
const text = (value: unknown) => (typeof value === 'string' ? value : '')
const sourceName = (value: unknown) => {
  const name = text(value)
  const names: Record<string, string> = {
    'Link traffic': 'Переходы по ссылкам',
    'Direct traffic': 'Прямые заходы',
    'Search engine traffic': 'Переходы из поисковиков',
    'Social network traffic': 'Переходы из социальных сетей',
    'Ad traffic': 'Реклама',
    'Internal traffic': 'Внутренние переходы',
    'Messenger traffic': 'Переходы из мессенджеров',
    'Recommendation systems traffic': 'Рекомендательные системы',
  }
  return names[name] ?? name
}
const date = (value: unknown) => {
  const valueText = text(value)
  return /^\d{4}-\d{2}-\d{2}$/.test(valueText)
    ? valueText.split('-').reverse().join('.')
    : '—'
}
const period = (value: unknown) => {
  const source = object(value)
  return source.start_date && source.end_date
    ? `${date(source.start_date)} — ${date(source.end_date)}`
    : 'Период не предоставлен'
}
const stamp = (value: unknown) => {
  const parsed = new Date(text(value))
  return Number.isNaN(parsed.getTime())
    ? 'Время не предоставлено'
    : `${parsed.toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' })} МСК`
}
const percent = (value: unknown) =>
  number(value) === null ? '—' : `${shown(value, 1)}%`
function Card({
  title,
  value,
  children,
}: {
  title: string
  value: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="seo-stat">
      <span>{title}</span>
      <strong>{value}</strong>
      {children && <small>{children}</small>}
    </div>
  )
}
function Table({
  labels,
  children,
}: {
  labels: string[]
  children: ReactNode
}) {
  return (
    <div
      className="seo-table-scroll"
      tabIndex={0}
      role="region"
      aria-label={labels.join(', ')}
    >
      <table>
        <thead>
          <tr>
            {labels.map((label) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}
function DailyChart({ daily }: { daily: Data[] }) {
  const ordered = [...daily].reverse()
  const max = Math.max(
    1,
    ...ordered.flatMap((row) => [
      number(row.shows) ?? 0,
      number(row.clicks) ?? 0,
    ]),
  )
  return (
    <div className="seo-chart-scroll" aria-hidden="true">
      <div
        className="seo-chart"
        style={{
          gridTemplateColumns: `repeat(${ordered.length}, minmax(32px, 1fr))`,
        }}
      >
        {ordered.map((row) => (
          <div
            className="seo-chart-day"
            key={text(row.date)}
            title={`${date(row.date)}: показы ${shown(row.shows)}, клики ${shown(row.clicks)}`}
          >
            <div className="seo-bars">
              {(['shows', 'clicks'] as const).map(
                (metric) =>
                  number(row[metric]) !== null && (
                    <span
                      key={metric}
                      className={metric}
                      style={{
                        height: `${(number(row[metric])! / max) * 100}%`,
                      }}
                    />
                  ),
              )}
            </div>
            <small>{date(row.date).slice(0, 5)}</small>
          </div>
        ))}
      </div>
    </div>
  )
}
function Source({
  name,
  source,
  google,
}: {
  name: string
  source: Data
  google?: boolean
}) {
  const unavailable = google
    ? !['active', 'partial'].includes(text(source.status))
    : Boolean(source.error) || !Object.keys(source).length
  const totals = object(source.property_totals)
  const queriesUnavailable =
    unavailable || object(source.query_sample).status === 'unavailable'
  const queries = queriesUnavailable ? [] : rows(source.top_queries)
  const daily = unavailable
    ? []
    : rows(source.daily_dynamics)
        .filter((row) => /^\d{4}-\d{2}-\d{2}$/.test(text(row.date)))
        .sort((a, b) => text(b.date).localeCompare(text(a.date)))
        .slice(0, 14)
  const totalsUnavailable =
    unavailable || source.totals_status === 'unavailable'
  const field = (key: string, fallback: string) =>
    totalsUnavailable ? null : key in totals ? totals[key] : source[fallback]
  return (
    <section
      className={`seo-panel seo-source ${google ? 'google' : 'yandex'}`}
      aria-label={name}
    >
      <div className="seo-panel-heading">
        <h2>{name}</h2>
        <span
          className={`seo-badge ${unavailable || source.status === 'partial' ? 'warning' : ''}`}
        >
          {unavailable
            ? 'Данные недоступны'
            : source.status === 'partial'
              ? 'Частичные данные'
              : 'Данные получены'}
        </span>
      </div>
      <p className="seo-caption">
        {period(source.period)} ·{' '}
        {google
          ? 'America/Los_Angeles · завершённые данные'
          : 'Период популярных запросов задан Вебмастером'}
      </p>
      {google ? (
        <div className="seo-stats compact">
          <Card
            title="Показы ресурса"
            value={shown(field('impressions', 'total_impressions'))}
          />
          <Card
            title="Клики ресурса"
            value={shown(field('clicks', 'total_clicks'))}
          />
          <Card
            title="CTR ресурса"
            value={percent(field('ctr_percent', 'avg_ctr_percent'))}
          />
          <Card
            title="Средняя позиция ресурса"
            value={
              number(field('avg_position', 'avg_position')) === 0
                ? '—'
                : shown(field('avg_position', 'avg_position'), 2)
            }
          />
        </div>
      ) : (
        <div className="seo-stats compact">
          <Card title="ИКС" value={shown(unavailable ? null : source.sqi)} />
          <Card
            title="Страницы в поиске"
            value={shown(unavailable ? null : source.searchable_pages)}
          />
          <Card
            title="Исключённые страницы"
            value={shown(unavailable ? null : source.excluded_pages)}
          />
          <Card
            title="Фразы в выборке"
            value={unavailable ? '—' : shown(queries.length)}
          />
        </div>
      )}
      <p className="seo-caption">
        {queriesUnavailable
          ? 'Выборка запросов недоступна. Число видимых фраз пока неизвестно.'
          : google
            ? `В выборке ${queries.length} видимых фраз. Итоги ресурса учитывают также запросы, скрытые источником.`
            : 'Показы и клики ниже относятся к видимым фразам, а не ко всему сайту.'}{' '}
        Показатели поисковиков не суммируются.
      </p>
      <h3>Динамика по дням</h3>
      <p className="seo-caption">
        {daily.length > 0 &&
          `${date(daily.at(-1)?.date)} — ${date(daily[0]?.date)}. `}
        Последние {daily.length} доступных дней. Средняя позиция зависит от
        состава запросов; её изменение не подтверждает рост ранжирования.
        Отсутствующие значения обозначены прочерком.
      </p>
      {daily.length ? (
        <div className="seo-daily">
          <p className="seo-caption">
            График: синий — показы, зелёный — клики; единая шкала внутри
            поисковика.
          </p>
          <DailyChart daily={daily} />
          <Table
            labels={[
              'Дата',
              'Клики',
              'Показы',
              'Средняя позиция',
              ...(google ? [] : ['Фраз в выборке']),
            ]}
          >
            {daily.map((row) => (
              <tr key={text(row.date)}>
                <td>{date(row.date)}</td>
                <td>{shown(row.clicks)}</td>
                <td>{shown(row.shows)}</td>
                <td>
                  {number(row.avg_position) === 0
                    ? '—'
                    : shown(row.avg_position, 2)}
                </td>
                {!google && <td>{shown(row.queries_count)}</td>}
              </tr>
            ))}
          </Table>
        </div>
      ) : (
        <p className="seo-empty">Нет доступных посуточных данных.</p>
      )}
      <h3>Видимые поисковые запросы</h3>
      <p className="seo-caption">
        {queriesUnavailable
          ? 'Источник не предоставил доступную выборку запросов.'
          : `Показано ${Math.min(queries.length, 20)} из ${queries.length} фраз полученной выборки.`}{' '}
        Это не полный список поискового спроса.
      </p>
      {queries.length ? (
        <Table labels={['Запрос', 'Показы', 'Клики', 'Средняя позиция']}>
          {queries.slice(0, 20).map((row, i) => (
            <tr key={`${text(row.text)}-${i}`}>
              <td className="seo-query">{text(row.text) || '—'}</td>
              <td>{shown(row.shows ?? row.impressions)}</td>
              <td>{shown(row.clicks)}</td>
              <td>
                {number(row.avg_position ?? row.position) === 0
                  ? '—'
                  : shown(row.avg_position ?? row.position, 2)}
              </td>
            </tr>
          ))}
        </Table>
      ) : (
        <p className="seo-empty">
          Видимые запросы не предоставлены источником.
        </p>
      )}
    </section>
  )
}
function Conversion({ conversion }: { conversion: Data }) {
  const organic = object(conversion.organic)
  const valid = conversion.status === 'available'
  const rate = (scope: Data) =>
    valid &&
    number(scope.visits) !== null &&
    number(scope.visits)! > 0 &&
    number(scope.goal_visits) !== null &&
    number(scope.goal_visits)! <= number(scope.visits)!
      ? (number(scope.goal_visits)! / number(scope.visits)!) * 100
      : null
  const reason =
    number(conversion.visits) === 0 && valid
      ? 'В периоде регистрации ещё нет визитов; процент конверсии пока не рассчитывается.'
      : !valid
        ? 'Расчёт недоступен: источник не подтвердил цель успешной регистрации и сопоставимые визиты.'
        : rate(conversion) === null
          ? 'Для расчёта недостаточно сопоставимых данных.'
          : 'Учтены визиты с успешной регистрацией; повторные достижения цели не суммируются.'
  return (
    <section className="seo-panel">
      <h2>Подтверждённые регистрации</h2>
      <p className="seo-caption">
        {period(conversion.period)} · отдельный период после включения
        измерений. Он может отличаться от общего отчёта посещаемости.
      </p>
      <div className="seo-stats compact">
        <Card title="Конверсия всех визитов" value={percent(rate(conversion))}>
          {valid
            ? `${shown(conversion.goal_visits)} из ${shown(conversion.visits)} визитов`
            : 'Данные недоступны'}
        </Card>
        <Card
          title="Конверсия из поиска"
          value={percent(
            organic.status === 'unavailable' ? null : rate(organic),
          )}
        >
          {valid && organic.status !== 'unavailable'
            ? `${shown(organic.goal_visits)} из ${shown(organic.visits)} органических визитов`
            : 'Данные недоступны'}
        </Card>
      </div>
      <p className="seo-caption">{reason}</p>
    </section>
  )
}

export function SeoTrafficView() {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [checkedAt, setCheckedAt] = useState('')
  useEffect(() => {
    let disposed = false
    let controller: AbortController | null = null
    async function sync() {
      if (disposed || document.hidden || controller) return
      controller = new AbortController()
      const current = controller
      const timeout = window.setTimeout(() => current.abort(), 90000)
      setLoading(true)
      try {
        const response = await fetch('/api/seo-analytics', {
          credentials: 'same-origin',
          cache: 'no-store',
          signal: current.signal,
        })
        if (!response.ok) throw new Error(String(response.status))
        const value: unknown = await response.json()
        const snapshot = object(value)
        if (
          snapshot.schema_version !== 2 ||
          !text(snapshot.updated_at) ||
          !Object.keys(object(snapshot.metrika)).length
        )
          throw new Error('Invalid snapshot')
        if (!disposed) {
          setData(snapshot)
          setError('')
          setCheckedAt(new Date().toISOString())
        }
      } catch (cause) {
        if (!disposed)
          setError(
            cause instanceof Error && cause.message === '401'
              ? 'Сессия завершилась. Данные не обновляются до восстановления авторизации.'
              : 'Не удалось обновить данные. Панель повторит проверку автоматически; сохранённые показатели могут быть устаревшими.',
          )
      } finally {
        window.clearTimeout(timeout)
        if (!disposed) setLoading(false)
        if (controller === current) controller = null
      }
    }
    void sync()
    const interval = window.setInterval(() => void sync(), 120000)
    const onVisible = () => {
      if (!document.hidden) void sync()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      disposed = true
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisible)
      controller?.abort()
    }
  }, [])
  const metrika = object(data?.metrika)
  const conversion = object(metrika.primary_conversion)
  const duration = number(metrika.avg_duration_seconds)
  const collected = new Date(text(data?.updated_at)).getTime()
  const stale =
    !Number.isFinite(collected) ||
    collected > Date.now() + 300000 ||
    Date.now() - collected >= 21600000
  return (
    <div className="seo-overview" aria-busy={loading}>
      <section className="seo-panel seo-status">
        <div>
          <h2>SEO под управлением агента</h2>
          <p>
            Анализ и улучшения выполняем через агента. Панель показывает
            измерения и состояние источников; ручные согласования здесь не
            требуются.
          </p>
        </div>
        <span className={`seo-badge ${error || stale ? 'warning' : ''}`}>
          {loading
            ? 'Проверка данных…'
            : error
              ? 'Обновление недоступно'
              : stale
                ? 'Снимок требует обновления'
                : 'Данные загружены'}
        </span>
        <p className="seo-caption">
          Сбор источников: {stamp(data?.updated_at)}. Проверка панели:{' '}
          {stamp(checkedAt)}. Панель проверяет данные каждые 2 минуты, пока
          открыта; сбор источников использует отдельный фоновый цикл.
        </p>
      </section>
      {error && (
        <div className="seo-notice" role="alert">
          {error}
        </div>
      )}
      {!data ? (
        <p className="seo-empty">
          {loading ? 'Загрузка аналитики…' : 'Аналитика пока недоступна.'}
        </p>
      ) : (
        <>
          {data.collection_status &&
          !['ok', 'active'].includes(text(data.collection_status)) ? (
            <div className="seo-notice">
              Часть источников не предоставила полные данные. Проверенные
              значения показаны ниже; недоступные не заменяются нулями.
            </div>
          ) : null}
          <section className="seo-panel">
            <h2>Посещаемость сайта · Яндекс.Метрика</h2>
            <p className="seo-caption">
              {period(metrika.period)} ·{' '}
              {text(object(metrika.period).timezone) ||
                'Часовой пояс не предоставлен'}
            </p>
            <div className="seo-stats">
              <Card title="Посетители сайта" value={shown(metrika.users)} />
              <Card title="Всего визитов" value={shown(metrika.visits)} />
              <Card
                title="Просмотры страниц"
                value={shown(metrika.pageviews)}
              />
              <Card
                title="Средняя длительность визита"
                value={
                  duration === null
                    ? '—'
                    : `${Math.floor(duration / 60)} мин ${Math.floor(duration % 60)} сек`
                }
              />
              <Card title="Отказы" value={percent(metrika.bounce_rate)} />
            </div>
            {metrika.error ? (
              <p className="seo-notice">
                Метрика предоставила неполные данные. Недоступные значения
                показаны прочерками.
              </p>
            ) : null}
          </section>
          <Conversion conversion={conversion} />
          <div className="seo-sources">
            <Source name="Яндекс.Вебмастер" source={object(data.webmaster)} />
            <Source
              name="Google Search Console"
              source={object(data.google)}
              google
            />
          </div>
          <div className="seo-sources">
            <section className="seo-panel">
              <h2>Источники визитов</h2>
              {rows(metrika.sources).length ? (
                <Table labels={['Источник', 'Визиты', 'Посетители']}>
                  {rows(metrika.sources).map((row, i) => (
                    <tr key={i}>
                      <td>{sourceName(row.name)}</td>
                      <td>{shown(row.visits)}</td>
                      <td>{shown(row.users)}</td>
                    </tr>
                  ))}
                </Table>
              ) : (
                <p className="seo-empty">
                  Разбивка по источникам не предоставлена.
                </p>
              )}
            </section>
            <section className="seo-panel">
              <h2>Посещаемые страницы</h2>
              {rows(metrika.top_pages).length ? (
                <Table labels={['Страница', 'Визиты', 'Посетители', 'Отказы']}>
                  {rows(metrika.top_pages).map((row, i) => (
                    <tr key={i}>
                      <td className="seo-query">{text(row.path)}</td>
                      <td>{shown(row.visits)}</td>
                      <td>{shown(row.users)}</td>
                      <td>{percent(row.bounce_rate)}</td>
                    </tr>
                  ))}
                </Table>
              ) : (
                <p className="seo-empty">Данные страниц не предоставлены.</p>
              )}
            </section>
          </div>
          <section className="seo-panel">
            <h2>Достижения целей Метрики</h2>
            <p className="seo-caption">
              Число достижений цели может включать повторные действия. Это не
              число регистраций или оплат.
            </p>
            {rows(metrika.goals).length ? (
              <Table labels={['Цель', 'Достижения']}>
                {rows(metrika.goals).map((row, i) => (
                  <tr key={i}>
                    <td>{text(row.name)}</td>
                    <td>{shown(row.reaches)}</td>
                  </tr>
                ))}
              </Table>
            ) : (
              <p className="seo-empty">Данные целей не предоставлены.</p>
            )}
          </section>
          <section className="seo-panel">
            <h2>Что проверяем с агентом</h2>
            <div className="seo-stats compact">
              <div className="seo-observation">
                <h3>Поисковые страницы</h3>
                <p>
                  Сопоставляем видимые запросы с содержанием, заголовками и
                  описаниями опубликованных страниц.
                </p>
              </div>
              <div className="seo-observation">
                <h3>Качество измерений</h3>
                <p>
                  Проверяем доступность источников и цель регистрации. Для
                  оценки конверсии из поиска доступно{' '}
                  {shown(object(conversion.organic).visits)} визитов за период
                  регистрации.
                </p>
              </div>
              <div className="seo-observation">
                <h3>Результат изменений</h3>
                <p>
                  Сравниваем завершённые периоды и одинаковые запросы после
                  публикации. Рост позиций не подтверждён одним изменением
                  средней позиции выборки.
                </p>
              </div>
            </div>
            <p className="seo-caption">
              Решения и публикации выполняются в работе с агентом. Эти
              наблюдения не означают, что изменения уже применены, и не обещают
              рост трафика или выход в ТОП.
            </p>
          </section>
        </>
      )}
    </div>
  )
}
