import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { post, request } from '../api/client'
import type { Comparison, DatasetSummary, Metadata, Point, Projection, Ranking } from '../types/api'
export const useExplorer = defineStore('explorer', () => {
  const datasets = ref<DatasetSummary[]>([]), datasetId = ref(''), metadata = ref<Metadata | null>(null), points = ref<Point[]>([])
  const projection = ref<Projection>('umap'), selected = ref<number[]>([]), activeId = ref<number | null>(null), k = ref(10)
  const comparison = ref<Comparison | null>(null), neighbors = ref<Ranking | null>(null), analogy = ref<Ranking | null>(null)
  const loading = ref(false), mathLoading = ref(false), error = ref(''), mathError = ref(''), notice = ref('')
  const focus = ref<{ id: number; nonce: number } | null>(null), resetNonce = ref(0)
  let datasetSeq = 0, mathSeq = 0, analogySeq = 0
  const byId = computed(() => new Map(points.value.map(p => [p.id, p])))
  const selectedPoints = computed(() => selected.value.map(id => byId.value.get(id)!).filter(Boolean))
  const active = computed(() => activeId.value === null ? null : byId.value.get(activeId.value))
  const highlights = computed(() => [...new Set([...(neighbors.value?.results.map(w => w.id) || []), ...(analogy.value?.results.map(w => w.id) || [])])])
  async function initialize() {
    loading.value = true; error.value = ''
    try {
      datasets.value = await request<DatasetSummary[]>('/datasets')
      if (!datasets.value.length) throw new Error('没有可用数据集，请先按 README 构建数据，再点击重试。')
      await loadDataset(datasets.value.find(d => d.data_kind === 'pretrained')?.dataset_id || datasets.value[0]!.dataset_id)
    } catch (e) { error.value = (e as Error).message } finally { loading.value = false }
  }
  async function loadDataset(id: string) {
    const seq = ++datasetSeq; ++mathSeq; ++analogySeq
    loading.value = true; error.value = ''; datasetId.value = id
    selected.value = []; activeId.value = null; points.value = []; metadata.value = null
    comparison.value = null; neighbors.value = null; analogy.value = null; focus.value = null; notice.value = ''; mathError.value = ''; mathLoading.value = false
    try {
      const [meta, data] = await Promise.all([request<Metadata>(`/datasets/${id}/metadata`), request<{ points: Point[] }>(`/datasets/${id}/points`)])
      if (seq !== datasetSeq) return
      metadata.value = meta; points.value = data.points; resetNonce.value++
    } catch (e) { if (seq === datasetSeq) error.value = (e as Error).message }
    finally { if (seq === datasetSeq) loading.value = false }
  }
  async function refreshMath() {
    const seq = ++mathSeq
    comparison.value = null; neighbors.value = null; mathError.value = ''
    if (!selected.value.length) { mathLoading.value = false; return }
    mathLoading.value = true
    try {
      const id = datasetId.value, word = active.value?.word || selectedPoints.value[0]!.word
      const [matrix, ranked] = await Promise.all([
        post<Comparison>('/similarity', { dataset_id: id, words: selectedPoints.value.map(p => p.word) }),
        request<Ranking>(`/neighbors?${new URLSearchParams({ dataset_id: id, word, k: String(k.value) })}`)])
      if (seq === mathSeq) { comparison.value = matrix; neighbors.value = ranked }
    } catch (e) { if (seq === mathSeq) mathError.value = (e as Error).message }
    finally { if (seq === mathSeq) mathLoading.value = false }
  }
  function select(id: number, toggle = true) {
    notice.value = ''
    if (!byId.value.has(id)) return
    if (selected.value.includes(id)) {
      if (toggle) selected.value = selected.value.filter(x => x !== id)
    } else if (selected.value.length >= 10) { notice.value = '最多比较 10 个词，请先移除一个。'; return }
    else selected.value.push(id)
    activeId.value = selected.value.includes(id) ? id : selected.value.at(-1) ?? null
    void refreshMath()
  }
  function focusWord(id: number, add = false) {
    if (add) select(id, false)
    focus.value = { id, nonce: (focus.value?.nonce || 0) + 1 }
  }
  function clear() { selected.value = []; activeId.value = null; void refreshMath() }
  async function runAnalogy(terms: { positive: string[]; negative: string[] }) {
    const seq = ++analogySeq; analogy.value = null
    try {
      const result = await post<Ranking>('/analogy', { dataset_id: datasetId.value, ...terms, k: k.value, exclude_input_words: true })
      if (seq === analogySeq) analogy.value = result
    } catch (e) { if (seq === analogySeq) throw e }
  }
  function cancelAnalogy() { ++analogySeq; analogy.value = null }
  return { datasets, datasetId, metadata, points, projection, selected, activeId, k, comparison, neighbors, analogy, loading, mathLoading,
    error, mathError, notice, focus, resetNonce, byId, selectedPoints, active, highlights, initialize, loadDataset, refreshMath, select, focusWord, clear, runAnalogy, cancelAnalogy }
})
