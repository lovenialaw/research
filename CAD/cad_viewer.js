
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

function parsePartCodeFromName(name) {
  if (!name || typeof name !== 'string') return null;
  const m = name.match(/^(\d{1,2})(?=_)/);
  if (m) return parseInt(m[1], 10);
  return null;
}

function partCodeForObject(obj) {
  let o = obj;
  while (o) {
    const pc = parsePartCodeFromName(o.name);
    if (pc != null) return pc;
    o = o.parent;
  }
  return null;
}

function ensureUniqueMaterial(mesh) {
  if (!mesh.material) return;
  if (!mesh.userData._cadMatCloned) {
    mesh.material = mesh.material.clone();
    mesh.userData._cadMatCloned = true;
  }
}

function storeOriginalEmissive(mesh) {
  ensureUniqueMaterial(mesh);
  const m = mesh.material;
  if (!m) return;
  if (mesh.userData._origEmissiveStored) return;
  mesh.userData._origEmissive = m.emissive ? m.emissive.clone() : new THREE.Color(0);
  mesh.userData._origEmissiveIntensity = m.emissiveIntensity != null ? m.emissiveIntensity : 1;
  mesh.userData._origEmissiveStored = true;
}

function resetMeshHighlight(mesh) {
  if (!mesh.userData._origEmissiveStored) return;
  const m = mesh.material;
  if (!m) return;
  m.emissive.copy(mesh.userData._origEmissive);
  m.emissiveIntensity = mesh.userData._origEmissiveIntensity;
}

function setMeshHighlight(mesh, rgb, intensity) {
  storeOriginalEmissive(mesh);
  const m = mesh.material;
  if (!m || !m.emissive) return;
  m.emissive.setRGB(rgb.r, rgb.g, rgb.b);
  m.emissiveIntensity = intensity;
}

function colorForProb(p) {
  const t = Math.max(0, Math.min(1, p));
  return {
    r: (220 + (34 - 220) * t) / 255,
    g: (38 + (197 - 38) * t) / 255,
    b: (59 + (94 - 59) * t) / 255,
  };
}

/**
 * @param {HTMLElement} container
 * @param {object} hooks
 * @param {() => Array} hooks.getNodes - build_data nodes
 * @param {(nodeId: string) => void} hooks.onGoalNode - user picked a component goal
 * @param {(graphNodeIds: string[], message: string) => void} hooks.onGraphFocus - highlight / message
 */
export function createCadViewer(container, hooks) {
  const getNodes = hooks.getNodes || (() => []);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0f172a);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
  camera.position.set(120, 90, 140);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, 0, 10);
  // No mouse-wheel / touch-pinch zoom — use + / − buttons only
  controls.enableZoom = false;

  const MIN_CAM_DIST = 12;
  const MAX_CAM_DIST = 12000;
  const ZOOM_FACTOR_PER_CLICK = 0.88;

  function dollyCamera(mult) {
    const offset = new THREE.Vector3().subVectors(camera.position, controls.target);
    let dist = offset.length();
    if (dist < 1e-6) return;
    dist *= mult;
    dist = Math.max(MIN_CAM_DIST, Math.min(MAX_CAM_DIST, dist));
    offset.normalize().multiplyScalar(dist);
    camera.position.copy(controls.target).add(offset);
    camera.updateProjectionMatrix();
  }

  function zoomIn() {
    dollyCamera(ZOOM_FACTOR_PER_CLICK);
  }

  function zoomOut() {
    dollyCamera(1 / ZOOM_FACTOR_PER_CLICK);
  }

  scene.add(new THREE.HemisphereLight(0x9fb8ff, 0x1e293b, 0.85));
  const dir = new THREE.DirectionalLight(0xffffff, 1.1);
  dir.position.set(40, 80, 60);
  scene.add(dir);

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();

  /** @type {Map<number, THREE.Mesh[]>} */
  const meshesByPartCode = new Map();
  /** @type {THREE.Mesh[]} */
  let allMeshes = [];
  let modelRoot = null;

  function indexMeshes(root) {
    meshesByPartCode.clear();
    allMeshes = [];
    root.traverse((o) => {
      if (!o.isMesh) return;
      allMeshes.push(o);
      const pc = partCodeForObject(o);
      if (pc == null) return;
      if (!meshesByPartCode.has(pc)) meshesByPartCode.set(pc, []);
      meshesByPartCode.get(pc).push(o);
    });
  }

  function resetAllHighlights() {
    for (const m of allMeshes) resetMeshHighlight(m);
  }

  function handlePick(clientX, clientY) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(allMeshes, true);
    if (!hits.length) return;

    const pc = partCodeForObject(hits[0].object);
    const nodes = getNodes();
    if (pc == null) {
      hooks.onGraphFocus?.([], 'Could not read part code from mesh name (expected names like 01_00_Base, 16_Screw_00).');
      return;
    }

    const comps = nodes.filter((n) => n.kind === 'C' && n.partCode === pc);
    const fasts = nodes.filter((n) => n.kind === 'F' && n.partCode === pc);

    if (comps.length === 1) {
      hooks.onGoalNode?.(comps[0].id);
      hooks.onGraphFocus?.([comps[0].id], `Goal set to ${comps[0].id} (part code ${pc}).`);
      return;
    }
    if (comps.length > 1) {
      const ids = comps.map((c) => c.id).sort();
      const choice = window.prompt(
        `Part code ${pc} maps to several components. Enter goal node id:\n${ids.join(', ')}`,
        ids[0]
      );
      if (choice && ids.includes(choice)) {
        hooks.onGoalNode?.(choice);
        hooks.onGraphFocus?.([choice], `Goal set to ${choice}.`);
      }
      return;
    }
    if (fasts.length >= 1) {
      const ids = fasts.map((f) => f.id).sort();
      hooks.onGraphFocus?.(ids, `Fastener mesh (part ${pc}) → graph: ${ids.join(', ')}. Pick a component goal from the graph or another CAD part.`);
      return;
    }
    hooks.onGraphFocus?.([], `Part code ${pc} has no matching graph node in build_data.json.`);
  }

  /**
   * @param {string[]} sequence - graph node ids in removal order
   * @param {Record<string, number>} pAtSelection
   * @param {Map<string, object>} nodeById
   */
  function syncSequenceHighlight(sequence, pAtSelection, nodeById) {
    resetAllHighlights();
    if (!sequence || !sequence.length || !meshesByPartCode.size) return;

    for (let i = 0; i < sequence.length; i++) {
      const vid = sequence[i];
      const rec = nodeById.get(vid);
      if (!rec || rec.partCode == null) continue;
      const p = pAtSelection[vid] ?? 0.5;
      const rgb = colorForProb(p);
      const meshes = meshesByPartCode.get(rec.partCode) || [];
      const intensity = 0.35 + 0.45 * (i / Math.max(1, sequence.length - 1));
      for (const mesh of meshes) setMeshHighlight(mesh, rgb, intensity);
    }
  }

  function fitCameraToObject(object) {
    const box = new THREE.Box3().setFromObject(object);
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    controls.target.copy(center);
    const maxDim = Math.max(size.x, size.y, size.z, 1);
    const dist = maxDim * 1.8 / Math.tan((camera.fov * Math.PI) / 360);
    camera.position.set(center.x + dist * 0.6, center.y + dist * 0.45, center.z + dist * 0.6);
    camera.near = Math.max(0.1, dist / 200);
    camera.far = dist * 50;
    camera.updateProjectionMatrix();
  }

  function resize() {
    const w = container.clientWidth || 400;
    const h = container.clientHeight || 200;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  }

  const ro = new ResizeObserver(() => resize());
  ro.observe(container);

  let anim = 0;
  function loop() {
    anim = requestAnimationFrame(loop);
    controls.update();
    renderer.render(scene, camera);
  }

  async function tryLoad(url) {
    return new Promise((resolve) => {
      const loader = new GLTFLoader();
      loader.load(
        url,
        (gltf) => {
          if (modelRoot) {
            scene.remove(modelRoot);
            modelRoot.traverse((o) => {
              if (o.geometry) o.geometry.dispose();
            });
          }
          modelRoot = gltf.scene;
          scene.add(modelRoot);
          indexMeshes(modelRoot);
          fitCameraToObject(modelRoot);
          resize();
          resolve({ ok: true, meshCount: allMeshes.length, partCodes: meshesByPartCode.size });
        },
        undefined,
        () => {
          resolve({ ok: false, error: 'load_failed' });
        }
      );
    });
  }

  renderer.domElement.style.cursor = 'grab';
  renderer.domElement.addEventListener('pointerdown', () => {
    renderer.domElement.style.cursor = 'grabbing';
  });
  renderer.domElement.addEventListener('pointerup', () => {
    renderer.domElement.style.cursor = 'grab';
  });
  renderer.domElement.addEventListener('click', (e) => {
    if (e.button !== 0) return;
    handlePick(e.clientX, e.clientY);
  });

  resize();
  loop();

  return {
    tryLoad,
    syncSequenceHighlight,
    resetAllHighlights,
    zoomIn,
    zoomOut,
    getStats: () => ({ meshes: allMeshes.length, partCodes: meshesByPartCode.size }),
  };
}
