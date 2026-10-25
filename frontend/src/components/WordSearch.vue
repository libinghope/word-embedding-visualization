<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { request } from '../api/client'
import { useExplorer } from '../stores/explorer'
const store = useExplorer(), query = ref(''), results = ref<{ id: number; word: string }[]>([]), busy = ref(false), error = ref('')
let timer: ReturnType<typeof setTimeout>, controller: AbortController | undefined, seq = 0
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
    <label class="search-box"><span aria-hidden="true">⌕</span><input aria-label="搜索词语" v-model="query" maxlength="128" placeholder="搜索英文词，例如 apple" /></label>
    <p class="muted small">区分大小写 · 当前数据集内搜索</p>
    <div class="search-results" v-if="query.trim()">
      <p v-if="busy" class="muted">正在搜索…</p><p v-else-if="error" class="error" role="alert">{{ error }}</p>
      <p v-else-if="!results.length" class="muted">未收录该词。试试 apple 或 king。</p>
      <button v-for="word in results" :key="word.id" @click="store.focusWord(word.id, true)"><span>{{ word.word }}</span><span>{{ store.selected.includes(word.id) ? '✓' : '+' }}</span></button>
    </div>
    <template v-else><p class="mini-title">从这些词开始</p><div class="suggestions"><button v-for="word in ['apple', 'orange', 'car', 'king', 'woman']" :key="word" @click="query = word">{{ word }} ↗</button></div></template>
    <div class="selection-heading"><h2>比较词语 <span>{{ store.selected.length }}/10</span></h2><button class="text-button" @click="store.clear" :disabled="!store.selected.length">清空</button></div>
    <div class="selected-list" v-if="store.selectedPoints.length">
      <div v-for="(point, index) in store.selectedPoints" :key="point.id" class="selected-word" :class="{ active: point.id === store.activeId }">
        <button class="word-focus" @click="store.select(point.id, false); store.focusWord(point.id)"><span class="word-number">{{ String(index + 1).padStart(2, '0') }}</span>{{ point.word }}</button>
        <button class="remove" :aria-label="`移除 ${point.word}`" @click="store.select(point.id)">×</button>
      </div>
    </div>
    <div v-else class="empty-selection"><span>◇</span><p>选择一个词，<br>打开它的语义邻域。</p><small>点击点云或搜索结果加入比较</small></div>
    <p v-if="store.notice" role="status" class="warning small">{{ store.notice }}</p>
    <div class="left-note"><span class="tiny-dot"></span><p>连线仅表示当前比较。<br>空间距离不代表真实语义相似度。</p></div>
  </section>
</template>
