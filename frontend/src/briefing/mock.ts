import type { Briefing } from './store'

// SAMPLE ONLY. Used when the data is mock (ships not known to a backend) so the panel can be built and demoed offline.
// The panel labels it. Nothing here is a real finding about any ship.
export function mockBriefing(mmsis: number[], nameOf: (mmsi: number) => string | null): Briefing {
  const many = mmsis.length > 1
  return {
    generated_at: Date.now(),
    model: 'sample',
    mock: true,
    mmsis,
    voice_available: false,
    summary: {
      headline: many ? `${mmsis.length} ships with quiet AIS in the same area (sample)` : 'One ship with a long AIS silence (sample)',
      overview: 'This is a sample briefing shown because the live backend is not connected. The real one is written by Gemini from the ships\' live data.',
      per_vessel: mmsis.map((mmsi, i) => ({
        mmsi,
        name: nameOf(mmsi),
        risk: ['moderate', 'low', 'high'][i % 3],
        findings: ['No AIS for 74 minutes while 6 ships nearby kept transmitting.', 'Last speed 11.2 kn, heading steady before the silence.'],
        caveats: ['Behaviour only. A silent ship is not evidence of wrongdoing; equipment faults are common.'],
      })),
      correlation: many
        ? { found: true, strength: 'weak', links: mmsis.slice(0, 2).map(String), explanation: 'Sample: two ships went quiet within 20 minutes of each other, about 12 km apart.' }
        : { found: false, strength: 'none', links: [], explanation: 'Sample: a single ship, so there is nothing to compare.' },
      speech_script: 'This is a sample briefing.',
    },
  }
}
