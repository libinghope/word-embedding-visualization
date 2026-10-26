import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useExplorer } from './explorer'
import { post } from '../api/client'

interface Result { id: number; word: string; sA: number; sB: number; bridge: number; evidence_status: string }
interface Response { results: Result[]; candidate_count: number; eligible_count: number; shared_inputs: string[]; algorithm_version: string }
export const useBridges = defineStore('bridges', () => {
  const explorer = useExplorer()
  const enabled = ref(false), a = ref(''), b = ref(''), k = ref(20), threshold = ref(0)
  const result = ref<Response | null>(null), busy = ref(false), error = ref(''), focused = ref<number | null>(null)
  let seq = 0
  const tokens = (value: string) => [...new Set(value.trim().split(/[\s,，;；]+/).filter(Boolean))]
  const wordsA = computed(() => tokens(a.value)), wordsB = computed(() => tokens(b.value))
  const ids = (words: string[]) => explorer.points.filter(p => words.includes(p.word)).map(p => p.id)
  const idsA = computed(() => ids(wordsA.value)), idsB = computed(() => ids(wordsB.value))
  const shared = computed(() => wordsA.value.filter(w => wordsB.value.includes(w)))
  function invalidate() { seq++; result.value = null; error.value = ''; busy.value = false; focused.value = null }
  watch([a, b, k, threshold], invalidate, { flush: 'sync' })
  function clear() { a.value = ''; b.value = ''; invalidate() }
  watch(() => explorer.datasetId, clear, { flush: 'sync' })
  async function search() {
    invalidate()
    const groups = [wordsA.value, wordsB.value]
    if (groups.some(g => g.length < 1 || g.length > 5)) { error.value = 'A、B 各需 1–5 个不同词条，合计最多 10 个。'; return }
    const missing = [...new Set(groups.flat().filter(w => !explorer.points.some(p => p.word === w)))]
    if (missing.length) { error.value = `当前数据集未收录：${missing.join('、')}`; return }
    const current = seq
    busy.value = true
    try {
      const response = await post<Response>('/bridges', { dataset_id: explorer.datasetId, a: groups[0], b: groups[1], k: k.value, threshold: threshold.value })
      if (current === seq) result.value = response
    } catch (e) { if (current === seq) error.value = (e as Error).message }
    finally { if (current === seq) busy.value = false }
  }
  function focus(id: number) { focused.value = id; explorer.focusWord(id) }
  function remove(side: 'a' | 'b', word: string) {
    if (side === 'a') a.value = wordsA.value.filter(w => w !== word).join(' ')
    else b.value = wordsB.value.filter(w => w !== word).join(' ')
  }
  function swap() { const old = a.value; a.value = b.value; b.value = old }
  return { enabled, a, b, k, threshold, result, busy, error, focused, wordsA, wordsB, idsA, idsB, shared, search, clear, remove, swap, focus }
})
