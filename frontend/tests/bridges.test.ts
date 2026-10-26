import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useExplorer } from '../src/stores/explorer'
import { useBridges } from '../src/stores/bridges'
beforeEach(() => { setActivePinia(createPinia()); vi.restoreAllMocks() })
it('deduplicates, rejects missing words and clears both groups on dataset changes', () => {
  const bridge = useBridges(), explorer = useExplorer()
  bridge.a = 'apple apple,苹果'; bridge.b = 'car'
  expect(bridge.wordsA).toEqual(['apple', '苹果'])
  void bridge.search()
  expect(bridge.error).toContain('未收录')
  explorer.datasetId = 'new'
  expect(bridge.a).toBe(''); expect(bridge.b).toBe('')
})
it('ignores responses after clear or changed input', async () => {
  const explorer = useExplorer(), bridge = useBridges()
  explorer.points = ['a', 'b'].map((word, id) => ({ id, word, positions: { pca: [0,0,0], umap: [0,0,0] } }))
  let resolve!: (value: unknown) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise(r => { resolve = r })))
  bridge.a = 'a'; bridge.b = 'b'
  const pending = bridge.search()
  bridge.clear()
  resolve({ ok: true, json: async () => ({ results: [{ id: 1 }] }) })
  await pending
  expect(bridge.result).toBeNull(); expect(bridge.busy).toBe(false)
})
