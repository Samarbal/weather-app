export type CityMatch = {
  name: string
  state?: string | null
  country: string
  latitude: number
  longitude: number
}

export type CitySearchResponse = {
  query: string
  results: CityMatch[]
}

export type WeatherLocation = {
  name: string
  country: string | null
  latitude: number
  longitude: number
}

export type CurrentWeatherResponse = {
  location: WeatherLocation
  observed_at: string
  temperature_c: number
  feels_like_c: number
  humidity_percent: number
  condition: string
  description: string
  wind_speed_kmh: number | null
}

export type ForecastPoint = {
  forecast_at: string
  temperature_c: number
  feels_like_c: number | null
  humidity_percent: number | null
  condition: string
  description: string
  wind_speed_kmh: number | null
}

export type ForecastResponse = {
  location: WeatherLocation
  timezone_offset_seconds: number | null
  items: ForecastPoint[]
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class WeatherApiError extends Error {
  readonly status: number

  constructor(
    message: string,
    status: number,
  ) {
    super(message)
    this.name = 'WeatherApiError'
    this.status = status
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new WeatherApiError('Could not reach the weather service. Check that the API server is running.', 0)
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new WeatherApiError('The weather service returned an unreadable response.', response.status)
  }

  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? (payload as { detail?: unknown }).detail
        : undefined
    const message =
      typeof detail === 'string'
        ? detail
        : response.status === 404
          ? 'No weather data was found for that location.'
          : response.status === 422
            ? 'The location request was invalid. Please try another city.'
            : response.status === 503
              ? 'Weather service is temporarily unavailable. Please try again shortly.'
              : response.status === 504
                ? 'The weather service took too long to respond. Please try again.'
                : 'Weather data could not be loaded. Please try again.'
    throw new WeatherApiError(message, response.status)
  }

  return payload as T
}

export function searchCities(query: string, signal?: AbortSignal): Promise<CitySearchResponse> {
  const params = new URLSearchParams({ q: query, limit: '5' })
  return getJson<CitySearchResponse>(`/api/v1/cities/search?${params}`, signal)
}

export function getCurrentWeather(
  latitude: number,
  longitude: number,
  signal?: AbortSignal,
): Promise<CurrentWeatherResponse> {
  const params = new URLSearchParams({ lat: String(latitude), lon: String(longitude) })
  return getJson<CurrentWeatherResponse>(`/api/v1/weather/current?${params}`, signal)
}

export function getForecast(
  latitude: number,
  longitude: number,
  signal?: AbortSignal,
): Promise<ForecastResponse> {
  const params = new URLSearchParams({ lat: String(latitude), lon: String(longitude) })
  return getJson<ForecastResponse>(`/api/v1/weather/forecast?${params}`, signal)
}
