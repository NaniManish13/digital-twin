import * as THREE from "https://esm.sh/three@0.166.1";
import { OrbitControls } from "https://esm.sh/three@0.166.1/examples/jsm/controls/OrbitControls.js";
import { FBXLoader } from "https://esm.sh/three@0.166.1/examples/jsm/loaders/FBXLoader.js";
import { GLTFLoader } from "https://esm.sh/three@0.166.1/examples/jsm/loaders/GLTFLoader.js";

const app = document.getElementById("app");
const bpmEl = document.getElementById("bpm");
const statusEl = document.getElementById("status");
const modelEl = document.getElementById("model");
const resetViewBtn = document.getElementById("resetView");
const chartCanvas = document.getElementById("signalChart");
const chartCtx = chartCanvas ? chartCanvas.getContext("2d") : null;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f172a);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 5000);
camera.position.set(0, 1.2, 4.5);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
app.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.enablePan = false;
controls.target.set(0, 0.6, 0);
controls.minDistance = 8.0;
controls.maxDistance = 90;

const ambient = new THREE.AmbientLight(0xffffff, 0.55);
scene.add(ambient);

const key = new THREE.DirectionalLight(0xffffff, 1.0);
key.position.set(3, 5, 4);
scene.add(key);

const rim = new THREE.DirectionalLight(0x7dd3fc, 0.45);
rim.position.set(-4, 2, -3);
scene.add(rim);

const floor = new THREE.Mesh(
  new THREE.CircleGeometry(3.5, 64),
  new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.95, metalness: 0.0 })
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -1.45;
scene.add(floor);

let heartMesh = null;
let beatTimer = null;
let bpmValue = 72;
let signal = [];
let peakIndices = [];
let dataPollTimer = null;
let framedCenter = new THREE.Vector3(0, 0.6, 0);
let framedDistance = 18;
let framedRadius = 2;
const framedViewDirection = new THREE.Vector3(0.22, 0.28, 1.0).normalize();

function setStatus(text) {
  statusEl.textContent = text;
}

function pulseHeart(mesh) {
  if (!mesh) {
    return;
  }

  mesh.scale.set(1.3, 1.3, 1.3);
  setTimeout(() => {
    mesh.scale.set(1.0, 1.0, 1.0);
  }, 100);
}

function centerAndNormalizeModel(root, targetSize = 2.0) {
  const box = new THREE.Box3().setFromObject(root);
  if (box.isEmpty()) {
    return;
  }

  const center = box.getCenter(new THREE.Vector3());
  root.position.sub(center);

  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 0.0001);
  const uniformScale = targetSize / maxDim;
  root.scale.multiplyScalar(uniformScale);
}

function frameObjectInView(object3d) {
  const box = new THREE.Box3().setFromObject(object3d);
  if (box.isEmpty()) {
    return;
  }

  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 0.5);
  const radius = Math.max(sphere.radius, maxDim * 0.5, 0.5);
  const fovRad = THREE.MathUtils.degToRad(camera.fov);
  const fitHeightDistance = maxDim / (2 * Math.tan(fovRad / 2));
  const fitWidthDistance = fitHeightDistance / Math.max(camera.aspect, 0.5);
  const distance = Math.max(fitHeightDistance, fitWidthDistance) * 3.2;
  framedCenter = center.clone();
  framedRadius = radius;
  framedDistance = Math.max(distance, radius * 4.2, 24);
  controls.minDistance = Math.max(8.0, framedRadius * 2.2);
  controls.maxDistance = Math.max(controls.minDistance + 10.0, framedDistance * 1.8);

  camera.near = Math.max(0.01, radius / 80);
  camera.far = Math.max(1000, framedDistance * 12);
  camera.updateProjectionMatrix();

  const cameraPos = framedCenter.clone().add(framedViewDirection.clone().multiplyScalar(framedDistance));
  camera.position.copy(cameraPos);
  controls.target.copy(framedCenter);
  camera.lookAt(framedCenter);
  controls.update();
}

function resetCameraView() {
  const safeDistance = Math.max(framedDistance, framedRadius * 4.2, controls.minDistance + 2.0, 24);
  const cameraPos = framedCenter.clone().add(framedViewDirection.clone().multiplyScalar(safeDistance));
  camera.position.copy(cameraPos);
  controls.target.copy(framedCenter);
  camera.lookAt(framedCenter);
  controls.update();
}

function applyHeartbeat(mesh, bpm) {
  if (beatTimer) {
    clearInterval(beatTimer);
  }

  const safeBpm = Number.isFinite(bpm) && bpm > 0 ? bpm : 72;
  const interval = 60 / safeBpm;

  beatTimer = setInterval(() => {
    pulseHeart(mesh);
  }, interval * 1000);

  console.log("BPM value:", safeBpm, "Interval(s):", interval.toFixed(3));
}

function drawSignalChart(values, peaks) {
  if (!chartCtx || !chartCanvas) {
    return;
  }

  const width = chartCanvas.width;
  const height = chartCanvas.height;
  chartCtx.clearRect(0, 0, width, height);

  chartCtx.fillStyle = "#0f172a";
  chartCtx.fillRect(0, 0, width, height);

  // Draw center baseline for quick visual reference.
  chartCtx.strokeStyle = "rgba(148, 163, 184, 0.45)";
  chartCtx.lineWidth = 1;
  chartCtx.beginPath();
  chartCtx.moveTo(0, height / 2);
  chartCtx.lineTo(width, height / 2);
  chartCtx.stroke();

  if (!Array.isArray(values) || values.length < 2) {
    chartCtx.fillStyle = "#94a3b8";
    chartCtx.font = "12px Arial";
    chartCtx.fillText("No signal data", 10, 20);
    return;
  }

  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;

  chartCtx.strokeStyle = "#22d3ee";
  chartCtx.lineWidth = 1.6;
  chartCtx.beginPath();
  for (let i = 0; i < values.length; i += 1) {
    const x = (i / (values.length - 1)) * (width - 1);
    const y = height - ((values[i] - minV) / range) * (height - 1);
    if (i === 0) {
      chartCtx.moveTo(x, y);
    } else {
      chartCtx.lineTo(x, y);
    }
  }
  chartCtx.stroke();

  chartCtx.fillStyle = "#f43f5e";
  for (const idx of peaks || []) {
    if (idx < 0 || idx >= values.length) {
      continue;
    }
    const x = (idx / (values.length - 1)) * (width - 1);
    const y = height - ((values[idx] - minV) / range) * (height - 1);
    chartCtx.beginPath();
    chartCtx.arc(x, y, 2.6, 0, Math.PI * 2);
    chartCtx.fill();
  }
}

async function loadSignalData() {
  const candidates = [
    { url: "../backend/biogears_live.json", source: "BioGears" },
    { url: "/backend/biogears_live.json", source: "BioGears" },
    { url: "../backend/output.json", source: "Signal" },
    { url: "/backend/output.json", source: "Signal" },
    { url: "./output.json", source: "Signal" },
  ];

  try {
    let data = null;
    let source = "Signal";
    for (const candidate of candidates) {
      try {
        const response = await fetch(candidate.url, { cache: "no-store" });
        if (!response.ok) {
          continue;
        }
        data = await response.json();
        source = candidate.source;
        console.log("Data loaded from:", candidate.url);
        break;
      } catch (innerError) {
        console.warn("Fetch failed for", candidate.url, innerError);
      }
    }

    if (!data) {
      throw new Error("output.json not found in expected locations");
    }

    const nextBpm = Number(data.bpm ?? data.heart_rate_bpm ?? data?.vitals?.heart_rate_bpm);
    bpmValue = Number.isFinite(nextBpm) && nextBpm > 0 ? nextBpm : bpmValue;
    signal = Array.isArray(data.signal) ? data.signal : [];
    peakIndices = Array.isArray(data.peak_indices) ? data.peak_indices : [];

    bpmEl.textContent = String(Math.round(bpmValue));
    console.log("Data loaded:", data);
    setStatus(source === "BioGears" ? "BioGears live data linked" : "Signal loaded");
    drawSignalChart(signal, peakIndices);

    return data;
  } catch (error) {
    console.error("Failed to fetch output.json, using defaults:", error);
    bpmValue = 72;
    signal = [];
    peakIndices = [];
    bpmEl.textContent = "72";
    setStatus("Using default BPM");
    drawSignalChart(signal, peakIndices);
    return { bpm: bpmValue, signal };
  }
}

function postprocessLoadedModel(root, modelName) {
  root.position.set(0, 0, 0);
  root.scale.set(1, 1, 1);

  root.traverse((obj) => {
    if (obj.isMesh && obj.material) {
      const applyMaterial = (material) => {
        if (!material) {
          return;
        }
        // FBX assets may include mixed/inside-out normals; double-sided avoids full culling.
        material.side = THREE.DoubleSide;
        material.transparent = false;
        material.opacity = 1.0;
        material.depthWrite = true;
        material.depthTest = true;
        if (material.color) {
          material.color.multiplyScalar(1.2);
        }
        if (typeof material.roughness === "number") {
          material.roughness = Math.max(material.roughness, 0.45);
        }
        if (typeof material.metalness === "number") {
          material.metalness = Math.min(material.metalness, 0.12);
        }
        material.needsUpdate = true;
      };

      if (Array.isArray(obj.material)) {
        obj.material.forEach(applyMaterial);
      } else {
        applyMaterial(obj.material);
      }
      obj.castShadow = true;
      obj.receiveShadow = true;
    }
  });

  centerAndNormalizeModel(root, 2.2);
  scene.add(root);
  frameObjectInView(root);
  modelEl.textContent = modelName;
}

async function refreshDataAndHeartbeat() {
  const previousBpm = bpmValue;
  await loadSignalData();
  if (!heartMesh) {
    return;
  }
  if (Math.abs(bpmValue - previousBpm) >= 0.5) {
    applyHeartbeat(heartMesh, bpmValue);
  }
}

function loadFbxModel(url) {
  return new Promise((resolve, reject) => {
    const loader = new FBXLoader();
    loader.load(url, resolve, undefined, reject);
  });
}

function loadGltfModel(url) {
  return new Promise((resolve, reject) => {
    const loader = new GLTFLoader();
    loader.load(url, resolve, undefined, reject);
  });
}

function createFallbackCube() {
  const geometry = new THREE.BoxGeometry(2.0, 2.0, 2.0);
  const material = new THREE.MeshStandardMaterial({ color: 0xf43f5e, roughness: 0.35, metalness: 0.2 });
  const cube = new THREE.Mesh(geometry, material);
  scene.add(cube);
  frameObjectInView(cube);
  modelEl.textContent = "Fallback Cube";
  setStatus("Model load failed - fallback cube active");
  return cube;
}

function loadHeartModel() {
  return new Promise(async (resolve) => {
    const fbxCandidates = [
      "/realistic-human-heart/source/Heart.fbx",
      "../realistic-human-heart/source/Heart.fbx",
    ];
    for (const fbxPath of fbxCandidates) {
      try {
        setStatus(`Loading FBX: ${fbxPath}`);
        const model = await loadFbxModel(fbxPath);
        postprocessLoadedModel(model, "realistic-human-heart/source/Heart.fbx");
        setStatus("Realistic heart loaded");
        console.log("Model loaded:", fbxPath);
        resolve(model);
        return;
      } catch (error) {
        console.warn("FBX load failed:", fbxPath, error);
      }
    }

    const glbCandidates = ["./heart.glb", "/frontend/heart.glb"];
    for (const glbPath of glbCandidates) {
      try {
        setStatus(`Loading GLB fallback: ${glbPath}`);
        const gltf = await loadGltfModel(glbPath);
        const root = gltf.scene;
        postprocessLoadedModel(root, "heart.glb");
        setStatus("heart.glb loaded");
        console.log("Model loaded:", glbPath);
        resolve(root);
        return;
      } catch (error) {
        console.warn("GLB load failed:", glbPath, error);
      }
    }

    resolve(createFallbackCube());
  });
}

function animate() {
  requestAnimationFrame(animate);

  if (heartMesh) {
    heartMesh.rotation.y += 0.004;
  }

  controls.update();
  renderer.render(scene, camera);
}

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  resetCameraView();
});

if (resetViewBtn) {
  resetViewBtn.addEventListener("click", () => {
    resetCameraView();
    setStatus("Camera reset to full-heart view");
  });
}

(async function init() {
  setStatus("Loading signal...");
  await loadSignalData();

  setStatus("Loading 3D model...");
  heartMesh = await loadHeartModel();
  resetCameraView();

  applyHeartbeat(heartMesh, bpmValue);
  if (dataPollTimer) {
    clearInterval(dataPollTimer);
  }
  // Keep heartbeat in sync with latest user-provided/BioGears JSON updates.
  dataPollTimer = setInterval(refreshDataAndHeartbeat, 1000);
  setStatus("Running");
  animate();
})();

