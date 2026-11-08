import { expect, test } from 'vitest'
import { briefingText, canSummarise, initials, pinnedSummary, reportedShips, tokenize } from './logic'
import type { Doc } from '../client'
import type { Briefing } from '../../briefing/store'

const doc = (id: number, kind: Doc['kind'], mmsis: number[] = []): Doc => ({ id, mmsi: null, author_id: 'u', body: 'b', created_at: id, kind, mmsis })

test('tokenize turns 9-digit MMSIs and doc#n into references and leaves the rest as text', () => {
  expect(tokenize('see 230000001 and doc#12, not 12345')).toEqual([
    { text: 'see ' }, { ship: 230000001 }, { text: ' and ' }, { doc: 12 }, { text: ', not 12345' },
  ])
  expect(tokenize('<b>plain</b>')).toEqual([{ text: '<b>plain</b>' }])
  expect(tokenize('1234567890')).toEqual([{ text: '1234567890' }])   // ten digits is not an MMSI
})

test('canSummarise needs a note, a briefing or a tracked ship', () => {
  expect(canSummarise([], 0)).toBe(false)
  expect(canSummarise([doc(1, 'summary')], 0)).toBe(false)
  expect(canSummarise([doc(1, 'note')], 0)).toBe(true)
  expect(canSummarise([doc(1, 'briefing', [5])], 0)).toBe(true)
  expect(canSummarise([], 1)).toBe(true)
})

test('reportedShips and pinnedSummary read the documents', () => {
  const docs = [doc(1, 'note', [5]), doc(2, 'briefing', [230000001, 244660000]), doc(3, 'summary'), doc(4, 'summary')]
  expect([...reportedShips(docs)]).toEqual([230000001, 244660000])
  expect(pinnedSummary(docs)?.id).toBe(4)
  expect(pinnedSummary([doc(1, 'note')])).toBeUndefined()
})

test('briefingText lists every ship, keeps the caveats and stays under the cap', () => {
  const b = {
    generated_at: 1, model: 'm', mmsis: [230000001], voice_available: false,
    summary: {
      headline: 'H', overview: 'O', speech_script: '',
      per_vessel: [{ mmsi: 230000001, name: 'Aurora', risk: 'low', findings: ['quiet 20 min'], caveats: ['coverage hole'] }],
      correlation: { found: false, strength: 'none', links: [], explanation: '' },
    },
  } satisfies Briefing
  const t = briefingText(b)
  expect(t).toContain('Aurora (230000001) · low')
  expect(t).toContain('Caveat: coverage hole')
  expect(briefingText({ ...b, summary: { ...b.summary, overview: 'x'.repeat(9000) } }).length).toBe(4000)
})

test('initials fall back to ?', () => {
  expect([initials('Aiden Ruz'), initials('mano'), initials(null)]).toEqual(['AR', 'M', '?'])
})
