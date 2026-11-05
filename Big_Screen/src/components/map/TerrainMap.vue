<template>
  <div ref="host" class="terrain-canvas" :data-presentation="mode === 'terrain' ? 'geographic-surface' : 'command-platform'"
    :data-camera="cameraProjection" role="img" aria-label="可旋转的辽宁三维气象风险地图">
    <div v-if="failure" class="render-failure" role="alert">{{ failure }}，可切换“经典平面”继续查看。</div>
    <div v-else-if="loading" class="relief-loading">正在加载辽宁地形…</div>
    <div class="map-label-layer">
      <button v-for="label in labels" :key="label.name" type="button" class="city-label"
        :style="{ left: label.x + 'px', top: label.y + 'px', opacity: label.visible ? 1 : 0 }"
        :disabled="!label.visible" @click="emit('region-select', label.name)">{{ label.name }}</button>
    </div>
    <div v-if="hover" class="map-hover">{{ hover }}</div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { pointColor, pointCoordinates } from '@/utils/mapGeometry.mjs';
import { loadReliefAssets } from '@/utils/terrainAssets';
import { buildReliefScene, beamMaterial, glowTexture } from './reliefScene';

const props = defineProps<{ geoJson: any; points: any[]; mode: string; selectedPoint: any; terrainView?: 'overhead' | 'oblique' }>();
const emit = defineEmits<{ (event: 'region-select', name: string): void; (event: 'point-select', point: any): void }>();
const host = ref<HTMLDivElement>();
const failure = ref('');
const loading = ref(true);
const hover = ref('');
const cameraProjection = ref('');
const labels = ref<{ name: string; x: number; y: number; visible: boolean }[]>([]);
let renderer: THREE.WebGLRenderer | undefined;
let scene: THREE.Scene, camera: THREE.PerspectiveCamera | THREE.OrthographicCamera, controls: OrbitControls;
let content = new THREE.Group();
let pointGroup = new THREE.Group();
let observer: ResizeObserver | undefined;
let frame = 0;
let lastRender = 0;
let dirty = true;
let moving = true;
let dimensions = { width: 1, height: 1 };
let labelPositions: { name: string; position: THREE.Vector3 }[] = [];
let pickable: THREE.Object3D[] = [];
let pointPickable: THREE.Object3D[] = [];
let pointerStart = [0, 0];
const raycaster = new THREE.Raycaster();
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const temporary = new THREE.Vector3();
let project: (lng: number, lat: number) => number[];
let surfaceZ: (lng: number, lat: number) => number;
let updateRelief: ((time: number) => void) | undefined;
let regionAt: ((x: number, y: number) => string | undefined) | undefined;
let buildEpoch = 0;
let disposed = false;

function disposeGroup(group: THREE.Group) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  group.traverse((object: any) => {
    if (object.geometry) geometries.add(object.geometry);
    for (const material of object.material ? (Array.isArray(object.material) ? object.material : [object.material]) : []) {
      materials.add(material);
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
    }
  });
  geometries.forEach(item => item.dispose());
  materials.forEach(item => item.dispose());
  textures.forEach(item => item.dispose());
  group.clear();
}

async function rebuildMap() {
  if (!renderer || disposed) return;
  const epoch = ++buildEpoch;
  loading.value = true;
  failure.value = '';
  try {
    const assets = await loadReliefAssets();
    if (disposed || epoch !== buildEpoch) return;
    disposeGroup(content);
    const relief = buildReliefScene(content, props.geoJson, props.mode === 'terrain', assets,
      Math.min(8, renderer.capabilities.getMaxAnisotropy()));
    project = relief.project;
    surfaceZ = relief.surfaceZ;
    updateRelief = relief.update;
    regionAt = relief.regionAt;
    pickable = relief.pickable;
    labelPositions = relief.labels;
    configureCamera();
    rebuildPoints();
    resetView();
  } catch {
    if (!disposed && epoch === buildEpoch) failure.value = '地形资源加载失败，请刷新重试';
  } finally {
    if (epoch === buildEpoch) loading.value = false;
  }
}

function rebuildPoints() {
  if (!renderer || !project) return;
  disposeGroup(pointGroup);
  pointPickable = [];
  const terrain = props.mode === 'terrain';
  // Bound GPU objects while retaining the complete list in the parent point menu.
  const visiblePoints = props.points.filter(point => pointCoordinates(point)).slice(0, 300);
  if (props.selectedPoint && pointCoordinates(props.selectedPoint) && !visiblePoints.includes(props.selectedPoint)) {
    if (visiblePoints.length >= 300) visiblePoints.pop();
    visiblePoints.push(props.selectedPoint);
  }
  const glow = visiblePoints.length ? glowTexture() : undefined;
  visiblePoints.forEach((point, index) => {
    const coords = pointCoordinates(point);
    if (!coords) return;
    const [x, y] = project(coords[0], coords[1]);
    const baseHeight = surfaceZ(coords[0], coords[1]) + .035;
    const selected = point === props.selectedPoint;
    const color = selected ? '#fff3a1' : pointColor(point);
    const markerGeometry = terrain ? new THREE.SphereGeometry(selected ? .12 : .075, 10, 8) : new THREE.OctahedronGeometry(selected ? .19 : .13);
    const mesh = new THREE.Mesh(markerGeometry, new THREE.MeshBasicMaterial({ color: terrain ? color : '#ebf8ff' }));
    mesh.position.set(x, y, baseHeight + 0.07);
    mesh.userData = { kind: 'point', point, name: point.name || point.station || '气象点位' };
    pointGroup.add(mesh);
    pointPickable.push(mesh);
    const flare = new THREE.Sprite(new THREE.SpriteMaterial({map: glow, color, transparent: true,
      opacity: terrain ? .3 : .95, blending: THREE.AdditiveBlending, depthWrite: false}));
    flare.position.copy(mesh.position);
    flare.scale.setScalar(selected ? .95 : terrain ? .25 : .7);
    pointGroup.add(flare);
    if (!terrain || selected) {
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.15, 0.19, 24),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7, side: THREE.DoubleSide }));
      ring.position.set(x, y, baseHeight + 0.025);
      ring.userData.pulse = !terrain;
      pointGroup.add(ring);
    }
    if (!terrain && (index < 48 || selected)) {
      const height = selected ? 4 : 2 + Math.min(100, Math.max(0, Number(point.value?.[2]) || 0)) / 65;
      const material = beamMaterial(terrain ? color : '#90bdff');
      for (const angle of [0, Math.PI / 2]) {
        const geometry = new THREE.PlaneGeometry(selected ? .55 : .32, height);
        geometry.rotateX(Math.PI / 2);
        const beam = new THREE.Mesh(geometry, material);
        beam.rotation.z = angle;
        beam.position.set(x, y, baseHeight + height / 2);
        pointGroup.add(beam);
      }
    }
  });
  dirty = true;
}

function resetView() {
  if (!camera) return;
  if (props.mode === 'terrain') {
    camera.position.set(0, props.terrainView === 'overhead' ? -.05 : -10, 28);
    if (camera instanceof THREE.OrthographicCamera) camera.zoom = 1;
    controls.target.set(0, 0, .2);
  } else {
    camera.position.set(-.4, -25, 17);
    controls.target.set(0, 0, .5);
  }
  camera.updateProjectionMatrix();
  controls.update();
  dirty = true;
}
function configureCamera() {
  controls?.dispose();
  camera = props.mode === 'terrain' ? new THREE.OrthographicCamera(-12, 12, 12, -12, .1, 150) : new THREE.PerspectiveCamera(38, 1, .1, 150);
  camera.up.set(0, 0, 1);
  cameraProjection.value = camera.type;
  controls = new OrbitControls(camera, renderer!.domElement);
  controls.enableDamping = true;
  controls.enablePan = props.mode === 'terrain';
  controls.minDistance = 16;
  controls.maxDistance = 48;
  controls.minZoom = .65;
  controls.maxZoom = 2.8;
  controls.minPolarAngle = props.mode === 'terrain' ? .015 : .4;
  controls.maxPolarAngle = props.mode === 'terrain' ? .9 : 1.25;
  controls.addEventListener('change', () => { dirty = true; });
  controls.addEventListener('start', () => { moving = true; });
  controls.addEventListener('end', () => { moving = false; });
  resize();
}
defineExpose({ resetView });

function pick(event: PointerEvent) {
  if (!renderer) return undefined;
  const rect = renderer.domElement.getBoundingClientRect();
  raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1,
    -(event.clientY - rect.top) / rect.height * 2 + 1), camera);
  for (const hit of raycaster.intersectObjects([...pointPickable, ...pickable], false)) {
    if (hit.object.userData.kind !== 'surface') return hit.object.userData;
    const name = regionAt?.(hit.point.x, hit.point.y);
    if (name) return {kind: 'region', name};
  }
  return undefined;
}
function pointerDown(event: PointerEvent) { pointerStart = [event.clientX, event.clientY]; }
function pointerUp(event: PointerEvent) {
  if (Math.hypot(event.clientX - pointerStart[0], event.clientY - pointerStart[1]) > 5) return;
  const object = pick(event);
  if (object?.kind === 'point') emit('point-select', object.point);
  else if (object?.kind === 'region') emit('region-select', object.name);
}
function pointerMove(event: PointerEvent) {
  if (event.buttons) { hover.value = ''; return; }
  const object = pick(event);
  hover.value = object?.name || '';
  if (renderer) renderer.domElement.style.cursor = object ? 'pointer' : 'grab';
}
function contextLost(event: Event) { event.preventDefault(); failure.value = '三维图形上下文已中断'; }
function animate(time: number) {
  frame = requestAnimationFrame(animate);
  if (document.hidden || !renderer || failure.value) return;
  if (time - lastRender < 32) return;
  lastRender = time;
  controls.update();
  if (!dirty && !moving && (reducedMotion || props.mode === 'terrain')) return;
  updateRelief?.(reducedMotion ? 0 : time / 1000);
  pointGroup.children.forEach(object => {
    if (object.userData.pulse && !reducedMotion) object.scale.setScalar(1 + Math.sin(time / 800) * 0.18);
  });
  renderer.render(scene, camera);
  if (dirty || moving) {
    labels.value = labelPositions.map(label => {
      temporary.copy(label.position).project(camera);
      return { name: label.name, x: (temporary.x + 1) / 2 * dimensions.width, y: (1 - temporary.y) / 2 * dimensions.height,
        visible: Math.abs(temporary.x) < 0.96 && Math.abs(temporary.y) < 0.91 && temporary.z < 1 };
    });
    dirty = false;
  }
}
function resize() {
  if (!renderer || !host.value) return;
  dimensions = { width: host.value.clientWidth, height: host.value.clientHeight };
  if (!dimensions.width || !dimensions.height) return;
  renderer.setSize(dimensions.width, dimensions.height);
  const aspect = dimensions.width / dimensions.height;
  if (camera instanceof THREE.PerspectiveCamera) camera.aspect = aspect;
  else { camera.left = -11.7 * aspect; camera.right = 11.7 * aspect; camera.top = 11.7; camera.bottom = -11.7; }
  camera.updateProjectionMatrix();
  dirty = true;
}
onMounted(() => {
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
    renderer.setClearColor(0x000000, 0);
    host.value!.prepend(renderer.domElement);
    scene = new THREE.Scene();
    scene.add(content, pointGroup, new THREE.AmbientLight('#c3d3e0', .9));
    const key = new THREE.DirectionalLight('#fff5e7', 2.2);
    key.position.set(-12, 7, 22);
    scene.add(key);
    configureCamera();
    resetView();
    const canvas = renderer.domElement;
    canvas.addEventListener('pointerdown', pointerDown);
    canvas.addEventListener('pointerup', pointerUp);
    canvas.addEventListener('pointermove', pointerMove);
    canvas.addEventListener('pointerleave', () => { hover.value = ''; });
    canvas.addEventListener('webglcontextlost', contextLost);
    observer = new ResizeObserver(resize);
    observer.observe(host.value!);
    rebuildMap();
    resize();
    moving = false;
    frame = requestAnimationFrame(animate);
  } catch {
    failure.value = '当前浏览器无法启用 WebGL 三维渲染';
  }
});
watch(() => [props.geoJson, props.mode], rebuildMap);
watch(() => props.terrainView, () => { if (props.mode === 'terrain') resetView(); });
watch(() => [props.points, props.selectedPoint], rebuildPoints);
onBeforeUnmount(() => {
  disposed = true;
  buildEpoch++;
  cancelAnimationFrame(frame);
  observer?.disconnect();
  controls?.dispose();
  disposeGroup(content);
  disposeGroup(pointGroup);
  if (renderer) {
    const canvas = renderer.domElement;
    canvas.removeEventListener('pointerdown', pointerDown);
    canvas.removeEventListener('pointerup', pointerUp);
    canvas.removeEventListener('pointermove', pointerMove);
    canvas.removeEventListener('webglcontextlost', contextLost);
    renderer.dispose();
    canvas.remove();
  }
});
</script>

<style scoped>
.terrain-canvas { width: 100%; height: 100%; position: relative; }
.terrain-canvas :deep(canvas) { width: 100%; height: 100%; display: block; touch-action: none; }
.map-label-layer { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.city-label { position: absolute; transform: translate(-50%, -50%); pointer-events: auto; background: transparent; border: 1px solid transparent; border-radius: 2px; padding: 3px 5px; color: #e1f3ee; font: 12px sans-serif; white-space: nowrap; text-shadow: 0 1px 4px #000, 0 0 7px #02090b, 1px 0 2px #000; cursor: pointer; }
.city-label:hover, .city-label:focus-visible { color: #fff1ac; border-color: #d1ba71; outline: none; }
.terrain-canvas[data-presentation="geographic-surface"] .city-label { font-size: 11px; color: #c9d4bf; letter-spacing: .5px; }
.terrain-canvas[data-presentation="command-platform"] .city-label { font-size: 12px; color: #edf4ff; }
.map-hover { position: absolute; left: 50%; top: 26%; transform: translateX(-50%); padding: 6px 12px; background: #0a1a26e8; border: 1px solid #78b5b466; border-radius: 4px; color: #edf8f6; font-size: 13px; pointer-events: none; }
.render-failure { position: absolute; left: 15%; right: 15%; top: 45%; text-align: center; color: #eed8ac; z-index: 2; line-height: 1.8; }
.relief-loading { position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%); color: #a9b9c7; font-size: 12px; z-index: 2; }
</style>
