import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useExplorer } from '../src/stores/explorer'
beforeEach(() => { setActivePinia(createPinia()); vi.restoreAllMocks() })
it('caps selection and preserves selection on projection change', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
  const store = useExplorer()
  store.points = Array.from({ length: 11 }, (_, id) => ({ id, word: `word${id}`, positions: { pca: [0, 0, 0], umap: [1, 1, 1] } }))
  for (let i = 0; i < 11; i++) store.select(i)
  expect(store.selected).toHaveLength(10)
  expect(store.notice).toContain('10')
  store.projection = 'pca'
  expect(store.selected).toHaveLength(10)
  store.resetNonce++
  expect(store.selected).toHaveLength(10)
})
it('discards an analogy response when input is invalidated', async () => {
  let resolve!: (response: unknown) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise(r => { resolve = r })))
  const store = useExplorer()
  const pending = store.runAnalogy({ positive: ['king'], negative: [] })
  store.cancelAnalogy()
  resolve({ ok: true, json: async () => ({ results: [{ word: 'old' }] }) })
  await pending
  expect(store.analogy).toBeNull()
})
it('computes spatial neighborhoods for every input and updates for projection and radius', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
  const store = useExplorer()
  store.points = [
    { id: 0, word: 'apple', positions: { umap: [0, 0, 0], pca: [0, 0, 0] } },
    { id: 1, word: '苹果', positions: { umap: [0.1, 0, 0], pca: [0.5, 0, 0] } },
    { id: 2, word: 'car', positions: { umap: [0.9, 0, 0], pca: [0.05, 0, 0] } }
  ]
  store.select(0); store.select(2)
  expect(store.neighborhoods.map(n => n.words.map(w => w.point.word))).toEqual([['苹果'], []])
  store.projection = 'pca'
  expect(store.nearbyIds).toEqual([2, 0])
  store.neighborhoodRadius = 0.6
  expect(store.nearbyIds).toContain(1)
  store.clear()
  expect(store.neighborhoods).toEqual([])
  expect(store.focus).toBeNull()
})
