import { expect, test } from 'vitest'
import { clearReview, removeReview, review, toggleReview } from './store'

test('removing a ship also dismisses its System entry, so it cannot come back', () => {
  toggleReview(111111111)
  toggleReview(222222222)
  removeReview(111111111)
  expect(review.get().list).toEqual([222222222])
  expect(review.get().dismissed).toContain(111111111)
  clearReview()
  expect(review.get().list).toEqual([])
  expect(review.get().dismissed).toContain(222222222)
})
