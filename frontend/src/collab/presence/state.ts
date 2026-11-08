import { createStore } from '../../store/store'

// Presence-only UI state: the private switch (the profile menu calls setPrivate) and whose view I follow.
export const presenceUi = createStore<{ private: boolean; followUser: string | null }>({ private: false, followUser: null })

export const setPrivate = (on: boolean) => presenceUi.set({ private: on })
export const followUser = (id: string | null) => presenceUi.set({ followUser: id })
