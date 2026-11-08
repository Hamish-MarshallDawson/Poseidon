import { expect, test } from 'vitest'
import { activityText, fanOffsets, initials, ringIndex, safePicture, shouldSend, trackedText, viewerText, viewersByShip, type PresenceOut, type PresenceUser } from './logic'

const check = (c: boolean, m: string) => expect(c, m).toBe(true)
const P = (o: Partial<PresenceOut> = {}): PresenceOut => ({ viewing: null, following: [], bbox: null, private: false, ...o })

test('presence logic', () => {
check(shouldSend(null, 0, P(), 0), 'first send')
check(!shouldSend(P(), 1000, P({ viewing: 5 }), 1500), 'throttled under 2 s')
check(shouldSend(P(), 1000, P({ viewing: 5 }), 3000), 'change after 2 s')
check(!shouldSend(P(), 1000, P(), 3000), 'no change, no heartbeat yet')
check(shouldSend(P(), 1000, P(), 9500), 'heartbeat')
check(!shouldSend(P({ bbox: [1, 2, 3, 4] }), 0, P({ bbox: [1, 2, 3, 4.0001] }), 3000), 'tiny bbox jitter ignored')

const u = (id: string, name: string, viewing: number | null): PresenceUser => ({ id, name, picture: null, viewing, following: [], bbox: null, ts: 0 })
const g = viewersByShip([u('a', 'Aiden', 1), u('me', 'Me', 1), u('j', 'Jake', 1), u('m', 'Mano', null)], 'me')
check(g.size === 1 && g.get(1)!.length === 2, 'group excludes me and idle users')

check(viewerText([{ name: 'Aiden Ruz' }]) === 'Aiden is viewing', 'one')
check(viewerText([{ name: 'Aiden' }, { name: 'Jake' }]) === 'Aiden and Jake are viewing', 'two')
check(viewerText([{ name: 'A' }, { name: 'B' }, { name: 'C' }, { name: 'D' }]) === 'A, B and 2 others are viewing', 'four')
check(viewerText([]) === '', 'none')
check(trackedText(['Mano Hil']) === 'Tracked by Mano', 'tracked')
check(initials('Hamish Marshall Dawson') === 'HD' && initials(null) === '?' && initials('aiden') === 'A', 'initials')
check(ringIndex('x') === ringIndex('x') && ringIndex('abc') < 6, 'ring stable')
check(safePicture('http://x') === null && safePicture('https://x/y.png') === 'https://x/y.png' && safePicture(null) === null, 'picture')
const f = fanOffsets(3)
check(f.length === 3 && new Set(f.map((p) => `${p.x},${p.y}`)).size === 3, 'fan distinct')
check(activityText('noted', 'Jake') === 'Jake added a note', 'activity')
})
