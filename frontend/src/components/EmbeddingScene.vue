<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { useExplorer } from '../stores/explorer'
const store = useExplorer(), host = ref<HTMLDivElement>(), failure = ref(''), hoverWord = ref(''), fps = ref(0)
const labels = ref<{ word: string; x: number; y: number; selected: boolean }[]>([])
let renderer: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.PerspectiveCamera, controls: OrbitControls
let cloud: THREE.Points, lines: THREE.LineSegments, markers: THREE.Group, grid: THREE.GridHelper, observer: ResizeObserver
let raf = 0, hovered: number | null = null, lastHover = 0, frames = 0, lastFPS = 0, width = 1, height = 1
let down: { x: number; y: number; max: number; valid: boolean } | null = null
let animation: { start: number; from: THREE.Vector3; to: THREE.Vector3; targetFrom: THREE.Vector3; targetTo: THREE.Vector3 } | null = null
const raycaster = new THREE.Raycaster(), mouse = new THREE.Vector2(), temp = new THREE.Vector3()
const disposables: { dispose(): void }[] = []
const position = (id: number) => store.byId.get(id)?.positions[store.projection]
function disposeObject(object: THREE.Object3D) {
  object.traverse(child => {
    const mesh = child as THREE.Mesh
    mesh.geometry?.dispose()
    if (mesh.material) (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).forEach(m => m.dispose())
  })
}
function fit() {
  if (!camera || !controls) return
  animation = null
  const vertical = THREE.MathUtils.degToRad(camera.fov / 2)
  const horizontal = Math.atan(Math.tan(vertical) * camera.aspect)
  const distance = 1.18 / Math.sin(Math.min(vertical, horizontal))
  camera.position.set(0.9, 0.55, 1.8).normalize().multiplyScalar(distance)
  controls.target.set(0, 0, 0); controls.update()
}
function rebuild() {
  if (!scene || !controls) return
  if (cloud) { scene.remove(cloud); disposeObject(cloud) }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(store.points.flatMap(p => p.positions[store.projection]), 3))
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(store.points.length * 3), 3))
  const material = new THREE.PointsMaterial({ size: 0.018, vertexColors: true, transparent: true, opacity: 0.85,
    sizeAttenuation: true, depthWrite: false })
  material.onBeforeCompile = shader => { shader.fragmentShader = shader.fragmentShader.replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\nif (length(gl_PointCoord - vec2(0.5)) > 0.5) discard;') }
  cloud = new THREE.Points(geometry, material); scene.add(cloud)
  hovered = null; hoverWord.value = ''; updateSelection(); fit()
}
function updateSelection() {
  if (!cloud) return
  const colors = cloud.geometry.getAttribute('color') as THREE.BufferAttribute
  const selected = new Set(store.selected), highlighted = new Set(store.highlights)
  store.points.forEach((p, i) => {
    const color = new THREE.Color(selected.has(p.id) ? '#ffe2a0' : p.id === hovered ? '#ffffff' : highlighted.has(p.id) ? '#b4a0ff' : '#5b9aa7')
    colors.setXYZ(i, color.r, color.g, color.b)
  }); colors.needsUpdate = true
  if (lines) { scene.remove(lines); disposeObject(lines) }
  const vertices: number[] = []
  for (let i = 0; i < store.selected.length; i++) for (let j = i + 1; j < store.selected.length; j++) {
    const a = position(store.selected[i]!), b = position(store.selected[j]!); if (a && b) vertices.push(...a, ...b)
  }
  lines = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3)),
    new THREE.LineBasicMaterial({ color: '#e7c889', transparent: true, opacity: 0.5 }))
  scene.add(lines)
  if (markers) { scene.remove(markers); disposeObject(markers) }
  markers = new THREE.Group()
  for (const id of store.selected) {
    const p = position(id); if (!p) continue
    const marker = new THREE.Mesh(new THREE.OctahedronGeometry(0.028), new THREE.MeshBasicMaterial({ color: '#ffe2a0', wireframe: true }))
    marker.position.fromArray(p); markers.add(marker)
  }
  scene.add(markers)
}
function pick(event: PointerEvent) {
  if (!cloud) return null
  const box = renderer.domElement.getBoundingClientRect()
  mouse.set(((event.clientX - box.left) / width) * 2 - 1, -((event.clientY - box.top) / height) * 2 + 1)
  raycaster.params.Points!.threshold = Math.max(0.008, controls.getDistance() * 0.007)
  raycaster.setFromCamera(mouse, camera)
  const hit = raycaster.intersectObject(cloud)[0]
  return hit?.index === undefined ? null : store.points[hit.index]?.id ?? null
}
function pointerdown(event: PointerEvent) {
  animation = null
  if (down) { down.valid = false; return }
  down = { x: event.clientX, y: event.clientY, max: 0, valid: event.button === 0 && event.isPrimary }
}
function pointermove(event: PointerEvent) {
  if (down) { down.max = Math.max(down.max, Math.hypot(event.clientX - down.x, event.clientY - down.y)); return }
  if (performance.now() - lastHover < 40) return
  lastHover = performance.now()
  const id = pick(event)
  if (id !== hovered) { hovered = id; hoverWord.value = id === null ? '' : store.byId.get(id)?.word || ''; updateSelection() }
}
function pointerup(event: PointerEvent) {
  if (down?.valid && down.max <= 5 && Math.hypot(event.clientX - down.x, event.clientY - down.y) <= 5) {
    const id = pick(event); if (id !== null) store.select(id)
  }
  down = null
}
function cancel() { down = null }
function leave() { hovered = null; hoverWord.value = ''; updateSelection() }
function contextLost(event: Event) { event.preventDefault(); failure.value = '图形上下文已丢失，请刷新页面恢复。' }
function resize() {
  if (!host.value || !renderer) return
  width = host.value.clientWidth; height = host.value.clientHeight
  camera.aspect = width / Math.max(1, height); camera.updateProjectionMatrix()
  renderer.setSize(width, height); renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
}
function draw(now: number) {
  raf = requestAnimationFrame(draw)
  if (animation) {
    const t = Math.min(1, (now - animation.start) / 650), ease = 1 - (1 - t) ** 3
    camera.position.lerpVectors(animation.from, animation.to, ease)
    controls.target.lerpVectors(animation.targetFrom, animation.targetTo, ease)
    if (t === 1) animation = null
  }
  controls.update(); renderer.render(scene, camera)
  const ids = [...new Set([...store.selected, ...(hovered === null ? [] : [hovered]), ...store.highlights.slice(0, 5)])]
  const occupied: { x: number; y: number; w: number }[] = []
  labels.value = ids.flatMap(id => {
    const p = position(id); if (!p) return []
    temp.fromArray(p).project(camera)
    if (temp.z < -1 || temp.z > 1 || Math.abs(temp.x) > 1 || Math.abs(temp.y) > 1) return []
    const word = store.byId.get(id)!.word, w = word.length * 7 + 16
    const x = Math.max(8, Math.min(width - w - 8, (temp.x * .5 + .5) * width + 10))
    const screenY = (-temp.y * .5 + .5) * height
    for (const offset of [-18, -42, 8, -66, 32, 56]) {
      const y = screenY + offset
      if (y < 8 || y > height - 30 || occupied.some(r => x < r.x + r.w + 4 && x + w + 4 > r.x && y < r.y + 24 && y + 24 > r.y)) continue
      occupied.push({ x, y, w })
      return [{ word, x, y, selected: store.selected.includes(id) }]
    }
    return []
  })
  frames++
  if (now - lastFPS > 1000) { fps.value = Math.round(frames * 1000 / (now - lastFPS)); frames = 0; lastFPS = now }
}
onMounted(() => {
  try {
    scene = new THREE.Scene()
    camera = new THREE.PerspectiveCamera(42, 1, .01, 100)
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setClearColor('#0b111b', 0)
    renderer.domElement.setAttribute('aria-label', '可旋转的三维词向量点云；也可使用左侧词列表选择')
    renderer.domElement.setAttribute('role', 'img')
    host.value!.appendChild(renderer.domElement)
    controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.minDistance = .2; controls.maxDistance = 12
    grid = new THREE.GridHelper(3, 12, '#304451', '#182a37'); grid.position.y = -1.05; scene.add(grid)
    const axes = new THREE.AxesHelper(1.15); scene.add(axes)
    disposables.push(controls)
    observer = new ResizeObserver(resize); observer.observe(host.value!)
    const canvas = renderer.domElement
    canvas.addEventListener('pointerdown', pointerdown); canvas.addEventListener('pointermove', pointermove)
    canvas.addEventListener('pointerup', pointerup); canvas.addEventListener('pointercancel', cancel)
    canvas.addEventListener('pointerleave', leave); canvas.addEventListener('webglcontextlost', contextLost)
    resize(); rebuild(); lastFPS = performance.now(); raf = requestAnimationFrame(draw)
  } catch (e) { failure.value = `无法启动三维画布：${(e as Error).message}。可继续使用列表和数学面板。` }
})
watch(() => [store.points, store.projection], rebuild)
watch(() => [store.selected.join(','), store.highlights.join(',')], updateSelection)
watch(() => store.resetNonce, fit)
watch(() => store.focus, value => {
  if (!value || !camera || !controls) return
  const p = position(value.id); if (!p) return
  const target = new THREE.Vector3().fromArray(p)
  const offset = camera.position.clone().sub(controls.target).normalize().multiplyScalar(1.1)
  animation = { start: performance.now(), from: camera.position.clone(), to: target.clone().add(offset), targetFrom: controls.target.clone(), targetTo: target }
})
onBeforeUnmount(() => {
  cancelAnimationFrame(raf); observer?.disconnect(); disposables.forEach(d => d.dispose())
  if (renderer) {
    const canvas = renderer.domElement
    canvas.removeEventListener('pointerdown', pointerdown); canvas.removeEventListener('pointermove', pointermove)
    canvas.removeEventListener('pointerup', pointerup); canvas.removeEventListener('pointercancel', cancel)
    canvas.removeEventListener('pointerleave', leave); canvas.removeEventListener('webglcontextlost', contextLost)
    if (scene) disposeObject(scene)
    renderer.dispose(); renderer.forceContextLoss(); canvas.remove()
  }
})
</script>
<template>
  <div class="scene" ref="host" data-testid="scene">
    <div class="scene-top"><span class="eyebrow">SEMANTIC SPACE / {{ store.projection.toUpperCase() }}</span><span class="fps">{{ fps }} FPS</span></div>
    <div class="scene-heading"><h1>词语之间，<br><em>藏着怎样的距离？</em></h1><p>旋转空间，从一个词开始探索。</p></div>
    <div class="scene-label" :class="{ chosen: label.selected }" v-for="label in labels" :key="label.word" :style="{ left: `${label.x}px`, top: `${label.y}px` }">{{ label.word }}</div>
    <div v-if="failure" class="scene-failure" role="alert">{{ failure }}</div>
    <div class="scene-bottom"><span>{{ hoverWord ? `点击选择 · ${hoverWord}` : '拖动旋转 · 滚轮缩放 · 右键平移' }}</span><span>{{ store.projection === 'pca' ? 'PC1 / PC2 / PC3' : 'UMAP1 / UMAP2 / UMAP3' }}</span></div>
  </div>
</template>
