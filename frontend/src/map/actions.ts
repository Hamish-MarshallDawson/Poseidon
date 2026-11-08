// Map-side actions on the shared ui store. Window placement belongs to windows/; the map re-exports its opener so a
// ship click, a watchlist row and a scrub-bar marker all go through the same code.
export { openShipWindow } from '../windows/open'
