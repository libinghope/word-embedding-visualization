<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useExplorer } from './stores/explorer'
import EmbeddingScene from './components/EmbeddingScene.vue'
import WordSearch from './components/WordSearch.vue'
import ComparisonPanel from './components/ComparisonPanel.vue'
import BridgePanel from './components/BridgePanel.vue'
import { useBridges } from './stores/bridges'
import AnalogyPanel from './components/AnalogyPanel.vue'
const bridge = useBridges()
const store = useExplorer(), help = ref(false), mobilePanel = ref<'scene' | 'search' | 'details'>('scene')
onMounted(store.initialize)
</script>
<template>
  <div class="app-shell">
    <header class="topbar"><a class="brand" href="#" @click.prevent="store.resetNonce++"><span class="brand-mark">✳</span><span>semantic<span class="brand-light">atlas</span><small>WORD EMBEDDING EXPLORER</small></span></a>
      <div class="header-controls"><label class="dataset-label"><span>DATASET</span><select aria-label="数据集" :value="store.datasetId" @change="store.loadDataset(($event.target as HTMLSelectElement).value)"><option v-for="dataset in store.datasets" :key="dataset.dataset_id" :value="dataset.dataset_id">{{ dataset.dataset_id }}</option></select></label><div class="projection-switch" aria-label="投影算法"><button :class="{ active: store.projection === 'pca' }" @click="store.projection = 'pca'">PCA</button><button :class="{ active: store.projection === 'umap' }" @click="store.projection = 'umap'">UMAP</button></div><button class="reset-button" @click="store.resetNonce++">↺ <span>重置视角</span></button><button class="help-button" aria-label="使用说明" @click="help = true">?</button></div>
    </header>
    <div v-if="store.metadata?.data_kind === 'synthetic'" class="synthetic-banner" role="status"><span>实验数据</span> 当前为 synthetic-demo：随机生成的测试向量，仅用于功能演示，不代表真实词语语义。<button @click="help = true">了解数据 ↗</button></div>
    <nav class="explorer-modes"><button :class="{ active: !bridge.enabled }" @click="bridge.enabled = false">词语探索</button><button :class="{ active: bridge.enabled }" @click="bridge.enabled = true">连接探索</button></nav>
    <nav class="mobile-tabs"><button v-for="tab in [{ id: 'search', label: '搜索 / 选择' }, { id: 'scene', label: '三维空间' }, { id: 'details', label: '关系 / 运算' }]" :key="tab.id" :class="{ active: mobilePanel === tab.id }" @click="mobilePanel = tab.id as typeof mobilePanel">{{ tab.label }}</button></nav>
    <main class="workspace" :data-panel="mobilePanel">
      <aside class="left-sidebar"><BridgePanel v-if="bridge.enabled" /><WordSearch v-else /></aside>
      <div class="canvas-wrap"><EmbeddingScene /><div v-if="store.loading" class="loading-overlay"><span class="spinner"></span>正在加载语义空间…</div><div v-else-if="store.error" class="loading-overlay" role="alert"><p>{{ store.error }}</p><button class="primary" @click="store.initialize">重新加载</button></div><div v-if="!bridge.enabled" class="canvas-legend"><span><i class="legend-dot"></i>词语</span><span><i class="legend-diamond"></i>已选</span><span><i class="legend-dot neighbor"></i>计算结果</span></div></div>
      <aside class="right-sidebar"><BridgePanel v-if="bridge.enabled" results /><template v-else><ComparisonPanel /><AnalogyPanel /></template></aside>
    </main>
    <footer class="statusbar"><span><i class="status-dot"></i>{{ store.points.length.toLocaleString() }} WORDS <b>/</b> {{ store.metadata?.embedding_dimensions || '—' }} DIMENSIONS</span><span v-if="store.metadata">局部可信度 <strong>{{ store.metadata.diagnostics.trustworthiness[store.projection].value.toFixed(3) }}</strong><span v-if="store.projection === 'pca'"> · 方差保留 {{ (store.metadata.diagnostics.pca_explained_variance_total * 100).toFixed(1) }}%</span></span><button @click="help = true">三维投影有失真，高维计算提供依据 ⓘ</button></footer>
    <div v-if="help" class="modal-backdrop" @click.self="help = false"><section role="dialog" aria-modal="true" aria-label="数据与投影说明" class="help-dialog" @keydown.esc="help = false" tabindex="-1"><button class="close-dialog" aria-label="关闭说明" @click="help = false">×</button><span class="eyebrow">ABOUT THE SPACE</span><h2>看见结构，理解边界。</h2><p>PCA 保留原始向量方差；UMAP 侧重局部邻域。三维位置、全局间距和轴方向不能证明语义关系。连线只表示你正在比较这些词。</p><p>相似度、最近邻与向量运算均由后端在原始高维空间计算，候选范围仅限当前数据集。每个词只有一个静态向量，不能区分不同语境。</p><p>局部可信度采用高维余弦距离与三维欧氏距离，邻居数 {{ store.metadata?.diagnostics.trustworthiness[store.projection].n_neighbors ?? 10 }}。分数接近 1 表示较少引入错误邻居，不代表投影无损。</p><div class="source-card"><strong>{{ store.metadata?.model_name || '尚未加载数据' }}</strong><p>{{ store.metadata?.license_note }}</p><a v-if="store.metadata?.source_url.startsWith('https://')" :href="store.metadata.source_url" target="_blank" rel="noopener noreferrer">查看数据来源 ↗</a></div><p class="small muted">切换真实数据：按项目 README 构建本地预训练数据集，重启后端后刷新页面。搜索保留大小写及下划线；向量表达式请在 + / - 两侧使用空格。</p><button class="primary" @click="help = false">开始探索</button></section></div>
  </div>
</template>
