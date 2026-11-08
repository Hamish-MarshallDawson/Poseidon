import { createStore } from '../../store/store'
import { collab } from './core'

// Whose view I follow. Private mode lives in the core store (collab.private; the profile menu sets it).
export const presenceUi = createStore<{ followUser: string | null }>({ followUser: null })

export const followUser = (id: string | null) => presenceUi.set({ followUser: id })
export const setPrivate = (on: boolean) => collab.set({ private: on })
