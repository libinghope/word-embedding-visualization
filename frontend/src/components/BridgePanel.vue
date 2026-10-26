<script setup lang="ts">
import { useBridges } from '../stores/bridges'
import { useExplorer } from '../stores/explorer'
const bridge = useBridges(), explorer = useExplorer()
defineProps<{ results?: boolean }>()
</script>
<template>
  <section class="details-section bridge-panel">
    <template v-if="!results">
      <div class="section-label">跨领域连接 / INPUT</div>
      <p class="small muted">每组 1–5 个词，以空格或逗号分隔。只检索当前词表，组内自动去重。</p>
      <form @submit.prevent="bridge.search">
        <label v-for="side in (['a', 'b'] as const)" :key="side" class="domain-input">领域 {{ side.toUpperCase() }}
          <input :aria-label="`领域 ${side.toUpperCase()}`" v-model="bridge[side]" list="bridge-vocabulary" :placeholder="side === 'a' ? '例如 water ocean' : '例如 energy power'" maxlength="650" />
          <span class="domain-chips"><button type="button" v-for="word in (side === 'a' ? bridge.wordsA : bridge.wordsB)" :key="word" @click="bridge.remove(side, word)" :aria-label="`移除 ${side.toUpperCase()} ${word}`">{{ word }} ×</button></span>
        </label>
        <datalist id="bridge-vocabulary"><option v-for="p in explorer.points" :key="p.id" :value="p.word" /></datalist>
        <p v-if="bridge.shared.length" class="warning small">共同输入：{{ bridge.shared.join('、') }}。可能降低领域区分度。</p>
        <label class="domain-input">最低双侧相似度<input aria-label="最低双侧相似度" type="number" min="0" max="1" step="0.05" v-model.number="bridge.threshold" required /></label>
        <label class="domain-input">候选数量<select aria-label="候选数量" v-model.number="bridge.k"><option v-for="n in [10,20,50]" :key="n">{{ n }}</option></select></label>
        <button class="primary" :disabled="bridge.busy || explorer.loading || !explorer.points.length">{{ bridge.busy ? '计算中…' : '寻找桥梁' }}</button>
      </form>
      <div class="bridge-actions"><button @click="bridge.swap">交换 A/B</button><button @click="bridge.clear">清空领域</button></div>
      <p v-if="bridge.error" role="alert" class="error">{{ bridge.error }}</p>
      <p class="small muted">{{ explorer.metadata?.model_name }} · 当前 {{ explorer.points.length }} 词。语言范围取决于所选词表，未收录词不会自动补全。</p>
    </template>
    <template v-else>
      <div class="section-label">桥梁候选 / VECTOR ONLY</div>
      <p class="small muted">按两侧相似度的较小值排序；并列按平均分、ID 排序。仅向量关联，无文献证据，不表示因果或创新价值。</p>
      <p v-if="bridge.busy" role="status">正在查找…</p>
      <template v-else-if="bridge.result">
        <p class="small muted">{{ bridge.result.candidate_count }} 个候选，{{ bridge.result.eligible_count }} 个达到阈值。点击词语定位。</p>
        <div class="matrix-scroll"><table data-testid="bridge-results"><thead><tr><th>词语</th><th>A</th><th>B</th><th>连接分</th></tr></thead><tbody><tr v-for="row in bridge.result.results" :key="row.id"><th><button @click="bridge.focus(row.id)">{{ row.word }}</button></th><td>{{ row.sA.toFixed(3) }}</td><td>{{ row.sB.toFixed(3) }}</td><td>{{ row.bridge.toFixed(3) }}</td></tr></tbody></table></div>
        <p v-if="!bridge.result.results.length" class="panel-empty">当前阈值内没有候选。可降低阈值或调整领域词；结果受当前词表覆盖限制。</p>
      </template>
      <p v-else class="panel-empty">输入两个领域并点击“寻找桥梁”，查看可复算的高维关联。</p>
      <p class="small muted">图例：A 蓝色、B 橙色、共同输入金色、桥梁紫色。连线仅关联当前定位的桥梁词与领域输入。</p>
    </template>
  </section>
</template>
