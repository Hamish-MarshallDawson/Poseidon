import { createStore } from '../store/store'

// Forecast-overlay UI state shared with the scrub bar (its freeze marker summons the check panel).
export const forecastUi = createStore({ checkOpen: false })
