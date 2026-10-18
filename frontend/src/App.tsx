import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import {
  AlertCircle,
  Check,
  ChevronDown,
  Cloud,
  CloudRain,
  CloudSun,
  Droplets,
  LocateFixed,
  MapPin,
  Search,
  Sparkles,
  Sun,
  Wind,
  X,
} from 'lucide-react'
import {
  getCurrentWeather,
  getForecast,
  searchCities,
  type CityMatch,
  type CurrentWeatherResponse,
  type ForecastPoint,
  type ForecastResponse,
  WeatherApiError,
} from './api/weather'
import './App.css'

type WeatherKind = 'sunny' | 'cloudy' | 'rainy'

type ForecastDayGroup = {
  key: string
  date: Date
  items: ForecastPoint[]
}

function weatherKind(condition: string): WeatherKind {
  const normalized = condition.toLowerCase()
  if (normalized.includes('rain') || normalized.includes('drizzle') || normalized.includes('thunder')) {
    return 'rainy'
  }
  if (
    normalized.includes('clear') ||
    normalized.includes('sun')
  ) {
    return 'sunny'
  }
  return 'cloudy'
}

function WeatherIcon({ condition, size = 22 }: { condition: string; size?: number }) {
  const kind = weatherKind(condition)
  if (kind === 'sunny') return <Sun size={size} strokeWidth={1.6} aria-hidden="true" />
  if (kind === 'rainy') return <CloudRain size={size} strokeWidth={1.6} aria-hidden="true" />
  return <CloudSun size={size} strokeWidth={1.6} aria-hidden="true" />
}

function offsetDate(timestamp: string, offsetSeconds: number | null): Date {
  return new Date(Date.parse(timestamp) + (offsetSeconds ?? 0) * 1000)
}

function formatLocalDate(timestamp: string, offsetSeconds: number | null, options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat('en', { ...options, timeZone: 'UTC' }).format(
    offsetDate(timestamp, offsetSeconds),
  )
}

function formatLocalTime(timestamp: string, offsetSeconds: number | null) {
  return formatLocalDate(timestamp, offsetSeconds, { hour: 'numeric', minute: '2-digit' })
}

function formatForecastTime(timestamp: string, offsetSeconds: number | null) {
  return formatLocalDate(timestamp, offsetSeconds, { hour: '2-digit', minute: '2-digit' })
}

function groupForecast(forecast: ForecastResponse | null): ForecastDayGroup[] {
  if (!forecast) return []
  const groups = new Map<string, ForecastDayGroup>()

  for (const item of forecast.items) {
    const date = offsetDate(item.forecast_at, forecast.timezone_offset_seconds)
    const key = `${date.getUTCFullYear()}-${date.getUTCMonth()}-${date.getUTCDate()}`
    const group = groups.get(key)
    if (group) {
      group.items.push(item)
    } else {
      groups.set(key, { key, date, items: [item] })
    }
  }
  return [...groups.values()].slice(0, 5)
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof WeatherApiError) return error.message
  return fallback
}

function App() {
  const [selectedPlace, setSelectedPlace] = useState<CityMatch | null>(null)
  const [currentWeather, setCurrentWeather] = useState<CurrentWeatherResponse | null>(null)
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<CityMatch[]>([])
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const [activeResult, setActiveResult] = useState(0)
  const [isSearching, setIsSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [expandedDay, setExpandedDay] = useState<string | null>(null)
  const [isLoadingWeather, setIsLoadingWeather] = useState(false)
  const [currentError, setCurrentError] = useState('')
  const [forecastError, setForecastError] = useState('')
  const [locationError, setLocationError] = useState('')
  const [locationMessage, setLocationMessage] = useState('')
  const searchController = useRef<AbortController | null>(null)
  const weatherRequestId = useRef(0)

  useEffect(() => {
    const searchTerm = query.trim()
    searchController.current?.abort()

    if (searchTerm.length < 2) {
      return
    }

    const controller = new AbortController()
    searchController.current = controller
    const timeout = window.setTimeout(async () => {
      try {
        const response = await searchCities(searchTerm, controller.signal)
        setSearchResults(response.results)
        setActiveResult(0)
      } catch (error) {
        if (!controller.signal.aborted) {
          setSearchError(getErrorMessage(error, 'City search is unavailable. Please try again.'))
        }
      } finally {
        if (!controller.signal.aborted) setIsSearching(false)
      }
    }, 300)

    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [query])

  const forecastDays = useMemo(() => groupForecast(forecast), [forecast])
  const selectedCoordinates = selectedPlace
    ? { latitude: selectedPlace.latitude, longitude: selectedPlace.longitude }
    : null
  const condition = currentWeather?.condition ?? ''
  const heroKind = currentWeather ? weatherKind(condition) : 'cloudy'
  const timezoneOffset = forecast?.timezone_offset_seconds ?? 0

  async function loadWeather(
    place: CityMatch,
    displayName?: string,
  ) {
    const requestId = ++weatherRequestId.current
    setSelectedPlace(place)
    setCurrentWeather(null)
    setForecast(null)
    setExpandedDay(null)
    setCurrentError('')
    setForecastError('')
    setLocationError('')
    setLocationMessage('')
    setIsSearchOpen(false)
    setIsLoadingWeather(true)

    const [currentResult, forecastResult] = await Promise.allSettled([
      getCurrentWeather(place.latitude, place.longitude),
      getForecast(place.latitude, place.longitude),
    ])

    if (requestId !== weatherRequestId.current) return

    if (currentResult.status === 'fulfilled') {
      setCurrentWeather(currentResult.value)
    } else {
      setCurrentError(getErrorMessage(currentResult.reason, 'Current weather could not be loaded.'))
    }

    if (forecastResult.status === 'fulfilled') {
      setForecast(forecastResult.value)
      const firstDay = groupForecast(forecastResult.value)[0]
      setExpandedDay(firstDay?.key ?? null)
    } else {
      setForecastError(getErrorMessage(forecastResult.reason, 'Forecast could not be loaded.'))
    }

    setIsLoadingWeather(false)
    if (displayName) setLocationMessage(`Showing weather near ${displayName}.`)
  }

  function selectCity(city: CityMatch) {
    setQuery('')
    setSearchResults([])
    setSearchError('')
    void loadWeather(city)
  }

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown' && searchResults.length > 0) {
      event.preventDefault()
      setIsSearchOpen(true)
      setActiveResult((current) => (current + 1) % searchResults.length)
    } else if (event.key === 'ArrowUp' && searchResults.length > 0) {
      event.preventDefault()
      setActiveResult((current) => (current - 1 + searchResults.length) % searchResults.length)
    } else if (event.key === 'Enter' && searchResults.length > 0) {
      event.preventDefault()
      selectCity(searchResults[activeResult] ?? searchResults[0])
    } else if (event.key === 'Escape') {
      setIsSearchOpen(false)
    }
  }

  function useMyLocation() {
    setLocationError('')
    setLocationMessage('')
    setCurrentError('')
    setForecastError('')
    if (!navigator.geolocation) {
      setLocationError('Location access is not available in this browser. Search for a city instead.')
      return
    }

    setIsLoadingWeather(true)
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const place: CityMatch = {
          name: 'Your location',
          state: null,
          country: '',
          latitude: coords.latitude,
          longitude: coords.longitude,
        }
        void loadWeather(place, 'your current position')
      },
      (error) => {
        setIsLoadingWeather(false)
        setLocationError(
          error.code === error.PERMISSION_DENIED
            ? 'Location permission was denied. You can allow access in browser settings or search for a city.'
            : 'We couldn’t determine your location. Please try again or search for a city.',
        )
      },
      { timeout: 10000, maximumAge: 300000 },
    )
  }

  function retryWeather() {
    if (selectedPlace) void loadWeather(selectedPlace)
  }

  function clearSearch() {
    searchController.current?.abort()
    setQuery('')
    setSearchResults([])
    setSearchError('')
    setIsSearching(false)
    setIsSearchOpen(false)
  }

  return (
    <main className="app-shell min-h-screen">
      <a className="skip-link" href="#main-content">
        Skip to weather
      </a>

      <div className="page-wrap mx-auto w-full">
        <header className="topbar">
          <a className="brand" href="#" aria-label="Stillweather home">
            <span className="brand-mark">
              <Sun size={19} strokeWidth={1.8} aria-hidden="true" />
            </span>
            <span>stillweather</span>
            <span className="brand-period" aria-hidden="true">.</span>
          </a>
          <span className="preview-badge">
            <span className="preview-dot" />
            Live weather
          </span>
        </header>

        <section className="search-section" aria-label="Find a city">
          <div className="search-copy">
            <p className="eyebrow">A little closer to the sky</p>
            <h1>Weather, wherever you are.</h1>
          </div>
          <div className="search-actions">
            <div className="search-wrap">
              <label className="sr-only" htmlFor="city-search">Search for a city</label>
              <Search className="search-icon" size={19} aria-hidden="true" />
              <input
                id="city-search"
                type="search"
                value={query}
                placeholder="Search a city"
                autoComplete="off"
                maxLength={100}
                disabled={isLoadingWeather}
                aria-autocomplete="list"
                aria-controls="city-results"
                aria-expanded={isSearchOpen && query.trim().length >= 2}
                aria-activedescendant={
                  isSearchOpen && searchResults[activeResult]
                    ? `city-option-${activeResult}`
                    : undefined
                }
                onChange={(event) => {
                  const nextQuery = event.target.value
                  setQuery(nextQuery)
                  setActiveResult(0)
                  setIsSearchOpen(true)
                  setSearchError('')
                  setSearchResults([])
                  setIsSearching(nextQuery.trim().length >= 2)
                }}
                onFocus={() => query.trim().length >= 2 && setIsSearchOpen(true)}
                onKeyDown={handleSearchKeyDown}
              />
              {query && (
                <button
                  className="clear-search"
                  type="button"
                  aria-label="Clear city search"
                  onClick={clearSearch}
                >
                  <X size={16} aria-hidden="true" />
                </button>
              )}
              {isSearchOpen && query.trim().length >= 2 && (
                <div className="search-popover" id="city-results" role="listbox" aria-label="Matching cities">
                  <p className="results-caption">
                    {isSearching
                      ? 'Searching places…'
                      : searchError
                        ? 'Search unavailable'
                        : `${searchResults.length} ${searchResults.length === 1 ? 'place' : 'places'} found`}
                  </p>
                  {isSearching && (
                    <div className="search-status" role="status">
                      <span className="button-spinner" aria-hidden="true" />
                      Finding matching cities…
                    </div>
                  )}
                  {!isSearching && searchError && (
                    <div className="search-status search-error" role="alert">{searchError}</div>
                  )}
                  {!isSearching && !searchError && searchResults.length === 0 && (
                    <div className="no-results" role="status">
                      <span className="no-results-icon"><Search size={17} aria-hidden="true" /></span>
                      <span>
                        <strong>No cities found</strong>
                        <small>Try another spelling or a nearby city.</small>
                      </span>
                    </div>
                  )}
                  {!isSearching && !searchError && searchResults.map((city, index) => {
                    const cityId = `${city.name}-${city.country}-${city.latitude}-${city.longitude}`
                    const isSelected =
                      selectedPlace?.latitude === city.latitude &&
                      selectedPlace.longitude === city.longitude
                    return (
                      <button
                        className={`city-option ${index === activeResult ? 'is-active' : ''}`}
                        id={`city-option-${index}`}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        key={cityId}
                        onMouseEnter={() => setActiveResult(index)}
                        onClick={() => selectCity(city)}
                      >
                        <span className="option-pin"><MapPin size={17} aria-hidden="true" /></span>
                        <span className="option-place">
                          <span>{city.name}</span>
                          <small>{[city.state, city.country].filter(Boolean).join(', ')}</small>
                        </span>
                        {isSelected && <Check size={16} aria-label="Currently selected" />}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
            <button
              className="location-button"
              type="button"
              aria-label="Use my location"
              onClick={useMyLocation}
              disabled={isLoadingWeather}
            >
              {isLoadingWeather && !selectedPlace ? (
                <span className="button-spinner" aria-hidden="true" />
              ) : (
                <LocateFixed size={17} strokeWidth={1.8} aria-hidden="true" />
              )}
              <span>Use my location</span>
            </button>
          </div>
        </section>

        {(locationError || currentError) && (
          <div className="notice notice-error" role="alert">
            <AlertCircle size={18} aria-hidden="true" />
            <span>{locationError || currentError}</span>
            {currentError && selectedPlace && (
              <button type="button" onClick={retryWeather}>Try again</button>
            )}
            <button
              type="button"
              onClick={() => {
                setLocationError('')
                setCurrentError('')
              }}
              aria-label="Dismiss error"
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        )}
        {locationMessage && (
          <div className="notice notice-info" role="status">
            <MapPin size={17} aria-hidden="true" />
            <span>{locationMessage}</span>
            <button type="button" onClick={() => setLocationMessage('')} aria-label="Dismiss location message">
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        )}

        <div id="main-content" className="weather-content" aria-busy={isLoadingWeather}>
          <section
            className={`weather-hero ${heroKind}`}
            aria-labelledby="weather-heading"
          >
            {currentWeather ? (
              <>
                <div className="hero-copy">
                  <div className="hero-location">
                    <MapPin size={15} strokeWidth={1.9} aria-hidden="true" />
                    <span>{currentWeather.location.name}</span>
                    {selectedPlace?.state && <span className="location-region">{selectedPlace.state}</span>}
                    {currentWeather.location.country && (
                      <span className="location-region">{currentWeather.location.country}</span>
                    )}
                  </div>
                  <p className="hero-date">
                    {formatLocalDate(currentWeather.observed_at, timezoneOffset, {
                      weekday: 'long',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </p>
                  <div className="temperature-line">
                    <h2 id="weather-heading">{Math.round(currentWeather.temperature_c)}</h2>
                    <span className="temperature-unit">°</span>
                    <span className="temperature-scale">C</span>
                  </div>
                  <div className="condition-line">
                    <span className="condition-icon"><WeatherIcon condition={condition} size={18} /></span>
                    <span>{currentWeather.description}</span>
                  </div>
                  <p className="feels-like">Feels like {Math.round(currentWeather.feels_like_c)}°</p>
                </div>

                <div className="hero-art" aria-hidden="true">
                  <div className="art-orbit art-orbit-one" />
                  <div className="art-orbit art-orbit-two" />
                  <div className="art-glow" />
                  {heroKind === 'sunny' && <div className="sun-disc" />}
                  {heroKind === 'cloudy' && <div className="sun-disc sun-disc-soft" />}
                  <div className="art-cloud art-cloud-back"><Cloud size={119} strokeWidth={0.85} /></div>
                  <div className="art-cloud art-cloud-front">
                    {heroKind === 'rainy' ? (
                      <CloudRain size={152} strokeWidth={0.9} />
                    ) : (
                      <Cloud size={152} strokeWidth={0.9} />
                    )}
                  </div>
                  {heroKind === 'rainy' && (
                    <div className="rain-strokes">
                      <span /><span /><span /><span /><span />
                    </div>
                  )}
                  {heroKind === 'sunny' && <div className="art-sparkles"><i /><i /><i /></div>}
                  <span className="art-caption">
                    {heroKind === 'rainy' ? 'soft rain' : heroKind === 'cloudy' ? 'clouds & light' : 'clear skies'}
                  </span>
                </div>

                <div className="hero-bottom">
                  <div className="hero-meta">
                    <span className="meta-label">Observed</span>
                    <span className="meta-value">
                      {formatLocalTime(currentWeather.observed_at, timezoneOffset)}
                    </span>
                  </div>
                  <div className="hero-meta">
                    <span className="meta-label">Coordinates</span>
                    <span className="meta-value coordinate-value">
                      {currentWeather.location.latitude.toFixed(2)}°, {currentWeather.location.longitude.toFixed(2)}°
                    </span>
                  </div>
                  <span className="hero-updated">Current conditions</span>
                </div>
              </>
            ) : (
              <div className="weather-empty">
                <div className="empty-weather-icon">
                  {isLoadingWeather ? (
                    <span className="button-spinner" aria-hidden="true" />
                  ) : currentError ? (
                    <AlertCircle size={25} aria-hidden="true" />
                  ) : (
                    <CloudSun size={28} strokeWidth={1.5} aria-hidden="true" />
                  )}
                </div>
                <p className="eyebrow">{isLoadingWeather ? 'One moment' : 'Your sky, at a glance'}</p>
                <h2 id="weather-heading">
                  {isLoadingWeather
                    ? 'Gathering the weather.'
                    : currentError
                      ? 'Weather is taking a pause.'
                      : 'Start with a place.'}
                </h2>
                <p>
                  {isLoadingWeather
                    ? 'Getting the latest conditions and forecast.'
                    : currentError
                      ? 'Try again, or choose a different city.'
                      : 'Search for a city above to see what the sky is doing.'}
                </p>
              </div>
            )}
          </section>

          <section className="conditions-strip" aria-label="Current weather details">
            <div className="detail-intro">
              <span className="detail-overline">Right now</span>
              <span className="detail-heading">The small details</span>
            </div>
            {currentWeather ? (
              <>
                <div className="detail-item">
                  <span className="detail-icon humidity-icon"><Droplets size={18} strokeWidth={1.7} aria-hidden="true" /></span>
                  <span className="detail-text">
                    <small>Humidity</small>
                    <strong>{currentWeather.humidity_percent}<span>%</span></strong>
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-icon wind-icon"><Wind size={19} strokeWidth={1.7} aria-hidden="true" /></span>
                  <span className="detail-text">
                    <small>Wind</small>
                    <strong>
                      {currentWeather.wind_speed_kmh == null
                        ? '—'
                        : <>{Math.round(currentWeather.wind_speed_kmh)}<span> km/h</span></>}
                    </strong>
                  </span>
                </div>
                <div className="detail-item detail-note">
                  <span className="detail-icon feel-icon"><CloudSun size={18} strokeWidth={1.7} aria-hidden="true" /></span>
                  <span className="detail-text">
                    <small>Feels like</small>
                    <strong>{Math.round(currentWeather.feels_like_c)}<span>°</span></strong>
                  </span>
                </div>
              </>
            ) : (
              <p className="detail-empty">
                {isLoadingWeather ? 'Updating conditions…' : 'Choose a city to see the current details.'}
              </p>
            )}
          </section>

          <section className="forecast-section" aria-labelledby="forecast-heading">
            <div className="forecast-heading-row">
              <div>
                <p className="eyebrow">A little further ahead</p>
                <h2 id="forecast-heading">The next five days</h2>
                <p className="forecast-subtitle">A closer look, every three hours.</p>
              </div>
              {forecast && <span className="forecast-timezone">Local time · 3-hour intervals</span>}
            </div>

            {forecastError ? (
              <div className="forecast-message forecast-error" role="alert">
                <AlertCircle size={18} aria-hidden="true" />
                <span>{forecastError}</span>
                <button type="button" onClick={retryWeather}>Try again</button>
              </div>
            ) : isLoadingWeather && !forecast ? (
              <div className="forecast-message" role="status">
                <span className="button-spinner" aria-hidden="true" />
                Loading forecast…
              </div>
            ) : forecastDays.length > 0 ? (
              <>
                <div className="forecast-days">
                  {forecastDays.map((day, dayIndex) => {
                    const isExpanded = expandedDay === day.key
                    const dateLabel = dayIndex === 0
                      ? 'Today'
                      : new Intl.DateTimeFormat('en', {
                          weekday: 'long',
                          timeZone: 'UTC',
                        }).format(day.date)
                    return (
                      <article className={`forecast-day ${isExpanded ? 'expanded' : ''}`} key={day.key}>
                        <button
                          className="day-toggle"
                          type="button"
                          aria-expanded={isExpanded}
                          aria-controls={`forecast-slots-${day.key}`}
                          onClick={() => setExpandedDay(isExpanded ? null : day.key)}
                        >
                          <span className="day-date">
                            <strong>{dateLabel}</strong>
                            <small>
                              {new Intl.DateTimeFormat('en', {
                                month: 'short',
                                day: 'numeric',
                                timeZone: 'UTC',
                              }).format(day.date)}
                            </small>
                          </span>
                          <span className="day-interval-count">
                            {day.items.length} {day.items.length === 1 ? 'interval' : 'intervals'}
                          </span>
                          <span className="day-chevron"><ChevronDown size={18} aria-hidden="true" /></span>
                        </button>
                        {isExpanded && (
                          <div className="forecast-slots" id={`forecast-slots-${day.key}`}>
                            {day.items.map((item) => (
                              <div className="forecast-slot" key={item.forecast_at}>
                                <span className="slot-time">
                                  {formatForecastTime(item.forecast_at, forecast?.timezone_offset_seconds ?? null)}
                                </span>
                                <span className={`slot-icon ${weatherKind(item.condition)}`}>
                                  <WeatherIcon condition={item.condition} size={20} />
                                </span>
                                <strong className="slot-temp">{Math.round(item.temperature_c)}°</strong>
                                <span className="slot-condition">{item.description}</span>
                                {item.humidity_percent != null && (
                                  <span className="slot-detail">
                                    <Droplets size={12} aria-hidden="true" /> {item.humidity_percent}%
                                  </span>
                                )}
                                {item.wind_speed_kmh != null && (
                                  <span className="slot-detail slot-wind">
                                    <Wind size={12} aria-hidden="true" /> {Math.round(item.wind_speed_kmh)}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </article>
                    )
                  })}
                </div>
                <p className="forecast-footnote">
                  <Sparkles className="footnote-spark" size={13} aria-hidden="true" />
                  Forecast intervals shown in the selected location’s local time.
                </p>
              </>
            ) : (
              <div className="forecast-message">
                <Cloud size={19} aria-hidden="true" />
                <span>{selectedCoordinates ? 'No forecast intervals are available for this location.' : 'Choose a city to explore its forecast.'}</span>
              </div>
            )}
          </section>
        </div>

        <footer className="page-footer">
          <span>Made for looking up.</span>
          <span className="footer-mark"><Sun size={13} aria-hidden="true" /> stillweather</span>
        </footer>
      </div>
    </main>
  )
}

export default App
