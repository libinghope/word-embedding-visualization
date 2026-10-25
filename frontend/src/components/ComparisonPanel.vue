<script setup lang="ts">
import { useExplorer } from '../stores/explorer'
const store = useExplorer()
</script>
<template>
  <section class="details-section">
    <div class="section-label"><span>02 / 高维关系</span><span>{{ store.metadata?.embedding_dimensions }}D</span></div>
    <div class="details-title"><h2>{{ store.active?.word || '语义近邻' }}</h2><label class="k-label">TOP <select aria-label="最近邻数量" v-model.number="store.k" @change="store.refreshMath"><option :value="5">5</option><option :value="10">10</option><option :value="20">20</option><option :value="50">50</option></select></label></div>
    <p class="muted small">当前数据集内最近邻 · 原始 {{ store.metadata?.embedding_dimensions }}D 余弦</p>
    <div v-if="store.mathLoading" class="panel-empty">正在计算高维关系…</div>
    <div v-else-if="store.mathError" class="error" role="alert">{{ store.mathError }} <button class="text-button" @click="store.refreshMath">重试</button></div>
    <div v-else-if="store.neighbors" class="rank-list" data-testid="neighbors">
      <button v-for="(word, index) in store.neighbors.results" :key="word.id" class="rank-row" @click="store.focusWord(word.id)">
        <span class="rank-index">{{ String(index + 1).padStart(2, '0') }}</span><span class="rank-word">{{ word.word }}</span><span class="rank-value">{{ word.score.toFixed(3) }}</span>
        <span class="score-bar" :style="{ width: `${Math.max(0, word.score) * 100}%` }"></span>
      </button>
      <p class="small muted" v-if="!store.neighbors.returned_count">没有剩余候选词。</p>
    </div>
    <div v-else class="panel-empty">选中一个词后，查看它在高维空间中的最近邻。</div>
    <details class="matrix-details" :open="store.selected.length > 1">
      <summary>两两相似度 <span>{{ store.selected.length }} × {{ store.selected.length }}</span></summary>
      <div v-if="store.comparison" class="matrix-scroll" data-testid="similarity"><table><thead><tr><th></th><th v-for="word in store.comparison.words" :key="word">{{ word }}</th></tr></thead><tbody><tr v-for="(row, i) in store.comparison.matrix" :key="i"><th>{{ store.comparison.words[i] }}</th><td v-for="(score, j) in row" :key="j" :style="{ backgroundColor: `rgba(125, 209, 190, ${Math.max(0, score) * .23})` }">{{ score.toFixed(3) }}</td></tr></tbody></table></div>
      <p v-else class="muted small">添加词语以查看比较矩阵。</p>
    </details>
  </section>
</template>
