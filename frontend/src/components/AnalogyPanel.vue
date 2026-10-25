<script setup lang="ts">
import { ref, watch } from 'vue'
import { useExplorer } from '../stores/explorer'
import { parseExpression } from '../lib/analogy'
const store = useExplorer(), expression = ref('king - man + woman'), busy = ref(false), error = ref('')
let seq = 0
watch([expression, () => store.datasetId, () => store.k], () => { ++seq; busy.value = false; error.value = ''; store.cancelAnalogy() })
async function run() {
  const current = ++seq; busy.value = true; error.value = ''
  try { await store.runAnalogy(parseExpression(expression.value)) }
  catch (e) { if (current === seq) error.value = (e as Error).message }
  finally { if (current === seq) busy.value = false }
}
</script>
<template>
  <section class="details-section analogy-section">
    <div class="section-label"><span>03 / 向量运算</span><span>A − B + C</span></div>
    <h2>探索语义方向</h2><p class="muted small">原始向量加减，再检索余弦最近邻。</p>
    <form @submit.prevent="run"><input v-model="expression" aria-label="向量表达式" class="expression" placeholder="king - man + woman" maxlength="1300"><button class="primary" :disabled="busy || !store.metadata">{{ busy ? '计算中…' : '计算向量' }} <span>↗</span></button></form>
    <p v-if="error" class="error small" role="alert">{{ error }}</p>
    <div v-if="store.analogy" class="analogy-results" data-testid="analogy-results"><p class="small muted">当前集合内 · 已排除输入词 · {{ store.analogy.returned_count }} 个结果</p><button v-for="word in store.analogy.results" :key="word.id" @click="store.focusWord(word.id)"><span>{{ word.word }}</span><span>{{ word.score.toFixed(3) }}</span></button><p v-if="!store.analogy.returned_count" class="small muted">没有剩余候选词。</p></div>
  </section>
</template>
