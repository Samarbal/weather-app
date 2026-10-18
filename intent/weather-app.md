# Weather Forecast App — Product Intent

## Intent

Build a simple, clear web app that lets people quickly understand the weather where they are and plan around the near-term forecast.

## Primary user and problem

- **User:** Anyone who wants a quick local weather forecast.
- **Problem:** People need an easy way to check current conditions and what weather to expect over the coming hours and days.

## Main workflow

1. The app offers city search and a "Use my location" action; it requests device location only after the user selects that action.
2. When location is available, the app shows current conditions, a 3-hourly forecast, and a 5-day forecast for that location.
3. City search is always available. The user selects the intended city from matching results before viewing its forecast.

## Initial scope

- Current weather conditions.
- 3-hourly forecast.
- 5-day forecast.
- Device geolocation initiated by user action and always-available city search with matching-city selection.
- English interface, temperatures in Celsius, and wind speed in km/h.
- Clear loading, empty, and error feedback for the forecast and location/search flow.

## Constraints and assumptions

- Deliver a simple web app; the approved estimate from the current empty app workspace is approximately 4 hours, excluding access/setup waits and major Figma-driven rework.
- Use the confirmed OpenWeather API through a server-side proxy; its API key must not be exposed to browser code.
- Keep the interface focused on the core forecast workflow; avoid nonessential features.
- Use the Figma designs the product owner will share as the visual reference when implementation begins.

## Success criteria

- A user can explicitly request a forecast for their current location when location access is available.
- A user can always search for a city, choose among matching results, and see the selected city's forecast.
- Current, 3-hourly, and 5-day forecast information is clearly presented.
- Temperature is shown in Celsius, wind speed in km/h, and the interface in English.
- The core experience remains simple and usable on common screen sizes.