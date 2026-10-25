<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { request } from '../api/client'
import { useExplorer } from '../stores/explorer'
const store = useExplorer(), query = ref(''), results = ref<{ id: number; word: string }[]>([]), busy = ref(false), error = ref('')
let timer: ReturnType<typeof setTimeout>, controller: AbortController | undefined, seq = 0
function compositionEnter(event: KeyboardEvent) { if (event.isComposing) event.preventDefault() }
function addInput() {
  const point = store.points.find(p => p.word === query.value.trim())
  if (!point) { store.notice = '当前数据集未收录该词，请从搜索结果中选择。'; return }
  store.focusWord(point.id, true)
}
function clearInputs() { query.value = ''; store.clear() }
watch([query, () => store.datasetId], () => {
  clearTimeout(timer); controller?.abort(); const current = ++seq
  results.value = []; error.value = ''; busy.value = false
  if (!query.value.trim() || !store.datasetId) return
  busy.value = true
  timer = setTimeout(async () => {
    controller = new AbortController()
    try {
      const data = await request<{ id: number; word: string }[]>(`/words/search?${new URLSearchParams({ dataset_id: store.datasetId, q: query.value.trim(), limit: '20' })}`, { signal: controller.signal })
      if (current === seq) results.value = data
    } catch (e) { if (current === seq && (e as Error).name !== 'AbortError') error.value = (e as Error).message }
    finally { if (current === seq) busy.value = false }
  }, 200)
})
onBeforeUnmount(() => { clearTimeout(timer); controller?.abort() })
</script>
<template>
  <section class="search-panel">
    <div class="section-label"><span>01 / 探索词语</span><span>SEARCH</span></div>
    <form @submit.prevent="addInput"><label class="search-box"><span aria-hidden="true">⌕</span><input aria-label="搜索词语" v-model="query" maxlength="128" placeholder="输入词语，按回车定位" @keydown.enter="compositionEnter" /></label><button class="primary" type="submit" :disabled="!query.trim() || store.loading">添加并定位 <span>↗</span></button></form>
    <p class="muted small">区分大小写 · 当前数据集内搜索</p>
    <div class="search-results" v-if="query.trim()">
      <p v-if="busy" class="muted">正在搜索…</p><p v-else-if="error" class="error" role="alert">{{ error }}</p>
      <p v-else-if="!results.length" class="muted">未收录该词。试试 apple 或 king。</p>
      <button v-for="word in results" :key="word.id" @click="store.focusWord(word.id, true)"><span>{{ word.word }}</span><span>{{ store.selected.includes(word.id) ? '✓' : '+' }}</span></button>
    </div>
    <template v-else><p class="mini-title">从这些词开始</p><div class="suggestions"><button v-for="word in (store.datasetId === 'fasttext-en-zh-v1' ? ['apple', '苹果', '国王', 'king', '汽车'] : ['apple', 'orange', 'car', 'king', 'woman'])" :key="word" @click="query = word">{{ word }} ↗</button></div></template>
    <div class="selection-heading"><h2>输入词汇 <span>{{ store.selected.length }}/10</span></h2><button class="text-button" @click="clearInputs" :disabled="!store.selected.length && !query">清空</button></div>
    <div class="selected-list" v-if="store.selectedPoints.length">
      <div v-for="(point, index) in store.selectedPoints" :key="point.id" class="selected-word" :class="{ active: point.id === store.activeId }">
        <button class="word-focus" @click="store.select(point.id, false); store.focusWord(point.id)"><span class="word-number">{{ String(index + 1).padStart(2, '0') }}</span>{{ point.word }}</button>
        <button class="remove" :aria-label="`移除 ${point.word}`" @click="store.select(point.id)">×</button>
      </div>
    </div>
    <div v-else class="empty-selection"><span>◇</span><p>选择一个词，<br>打开它的语义邻域。</p><small>点击点云或搜索结果加入比较</small></div>
    <p v-if="store.notice" role="status" class="warning small">{{ store.notice }}</p>
    <section v-if="store.selected.length" class="neighborhoods" data-testid="neighborhoods">
      <label class="small">周边半径 {{ store.neighborhoodRadius.toFixed(2) }}<input aria-label="周边半径" type="range" min="0.02" max="0.6" step="0.02" v-model.number="store.neighborhoodRadius" /></label>
      <p class="small muted">当前 {{ store.projection.toUpperCase() }} 三维距离；切换投影后重新计算。周边词不占用 10 个输入名额。</p>
      <details v-for="group in store.neighborhoods" :key="group.center.id" open>
        <summary>{{ group.center.word }} · {{ group.words.length }} 个周边词</summary>
        <div class="nearby-list"><button v-for="item in group.words" :key="item.point.id" @click="store.focusWord(item.point.id)">{{ item.point.word }} <small>{{ item.distance.toFixed(3) }}</small></button><p v-if="!group.words.length" class="small muted">范围内没有其他词，可增大半径。</p></div>
      </details>
    </section>
    <div class="left-note"><span class="tiny-dot"></span><p>连线仅表示当前比较。<br>空间距离不代表真实语义相似度。</p></div>
  </section>
</template>
