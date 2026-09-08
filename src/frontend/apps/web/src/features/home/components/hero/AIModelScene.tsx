"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

import type { HeroPointer } from "./HeroSection";

type AIModelSceneProps = {
  pointer: HeroPointer;
};

type NodeSeed = {
  position: THREE.Vector3;
  size: number;
};

const nodeSeeds: Array<{ position: [number, number, number]; size: number }> = [
  { position: [0, 1.55, 0], size: 0.08 },
  { position: [0.92, 1.15, 0.42], size: 0.06 },
  { position: [-0.95, 1.05, 0.38], size: 0.06 },
  { position: [1.35, 0.35, -0.18], size: 0.07 },
  { position: [-1.38, 0.28, -0.1], size: 0.07 },
  { position: [0.58, 0.58, 1.1], size: 0.065 },
  { position: [-0.5, 0.55, 1.16], size: 0.065 },
  { position: [0.42, 0.12, -1.35], size: 0.06 },
  { position: [-0.5, 0.06, -1.28], size: 0.06 },
  { position: [1.06, -0.45, 0.62], size: 0.07 },
  { position: [-1.05, -0.48, 0.6], size: 0.07 },
  { position: [0, -0.1, 0.15], size: 0.1 },
  { position: [0.68, -1.05, -0.28], size: 0.065 },
  { position: [-0.7, -1.02, -0.24], size: 0.065 },
  { position: [0.1, -1.42, 0.48], size: 0.075 },
  { position: [1.42, -0.08, 0.08], size: 0.055 },
  { position: [-1.45, -0.06, 0.1], size: 0.055 },
  { position: [0.12, 1.0, -0.92], size: 0.06 },
  { position: [0.08, -0.72, 1.1], size: 0.06 },
  { position: [0.72, 1.38, -0.36], size: 0.052 },
  { position: [-0.76, 1.28, -0.42], size: 0.052 },
  { position: [1.18, 0.82, -0.76], size: 0.05 },
  { position: [-1.18, 0.78, -0.72], size: 0.05 },
  { position: [1.52, -0.72, -0.22], size: 0.058 },
  { position: [-1.48, -0.74, -0.18], size: 0.058 },
  { position: [0.72, -1.34, 0.42], size: 0.055 },
  { position: [-0.66, -1.38, 0.38], size: 0.055 },
  { position: [0.98, -0.12, 1.08], size: 0.05 },
  { position: [-0.98, -0.18, 1.04], size: 0.05 },
  { position: [0.34, 1.55, 0.62], size: 0.048 },
  { position: [-0.28, -1.58, -0.68], size: 0.048 },
];

const signalEdges: Array<[number, number]> = [
  [0, 1],
  [2, 6],
  [5, 11],
  [11, 9],
  [4, 10],
  [7, 12],
  [13, 14],
  [3, 15],
];

function useLatestPointer(pointer: HeroPointer) {
  const pointerRef = useRef(pointer);
  pointerRef.current = pointer;
  return pointerRef;
}

function buildConnections(nodes: NodeSeed[]) {
  const connections: Array<[number, number]> = [];

  for (let i = 0; i < nodes.length; i += 1) {
    for (let j = i + 1; j < nodes.length; j += 1) {
      const distance = nodes[i].position.distanceTo(nodes[j].position);
      if (distance < 1.42 || (i === 11 && distance < 2.05)) {
        connections.push([i, j]);
      }
    }
  }

  return connections.slice(0, 86);
}

function disposeObject(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();

    const material = mesh.material;
    if (Array.isArray(material)) {
      material.forEach((item) => item.dispose());
    } else if (material) {
      material.dispose();
    }
  });
}

function getMotionFlags() {
  return {
    reduced: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    mobile: window.matchMedia("(max-width: 768px)").matches,
  };
}

export default function AIModelScene({ pointer }: AIModelSceneProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const pointerRef = useLatestPointer(pointer);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const flags = getMotionFlags();
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(44, 1, 0.1, 100);
    camera.position.set(0, 0.20, 8.2);
    camera.lookAt(0, 0.20, 0);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      });
    } catch (err) {
      console.warn("WebGL initialization failed:", err);
      return;
    }
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
    host.appendChild(renderer.domElement);

    const root = new THREE.Group();
    scene.add(root);

    const updateScale = (w: number, h: number) => {
      const minDim = Math.min(w, h);
      const isDesktop = w >= 768;

      if (isDesktop) {
        camera.position.set(0, 0.20, 8.2);
        camera.lookAt(0, 0.20, 0);
        const targetScale = THREE.MathUtils.clamp(minDim / 500, 1.08, 1.25);
        root.scale.setScalar(targetScale);
      } else {
        // On mobile/tablet, bring camera closer and scale up so the 3D sphere is prominently sized
        camera.position.set(0, 0.22, 6.3);
        camera.lookAt(0, 0.22, 0);
        const targetScale = THREE.MathUtils.clamp(minDim / 270, 1.15, 1.35);
        root.scale.setScalar(targetScale);
      }
      camera.updateProjectionMatrix();
    };

    const coreGroup = new THREE.Group();
    coreGroup.position.y = 0.35;
    root.add(coreGroup);

    scene.add(new THREE.AmbientLight(0xffffff, 0.72));
    const keyLight = new THREE.PointLight("#67e8f9", 2.4, 8);
    keyLight.position.set(3.8, 3.2, 4.2);
    scene.add(keyLight);
    const fillLight = new THREE.PointLight("#2563ff", 1.3, 8);
    fillLight.position.set(-4.2, -1.5, 3.6);
    scene.add(fillLight);
    const coreLight = new THREE.PointLight("#9af7ff", 2.2, 8);
    coreLight.position.set(0, 0.25, 0.3);
    coreGroup.add(coreLight);

    const coreGlow = new THREE.Mesh(
      new THREE.SphereGeometry(0.34, 32, 32),
      new THREE.MeshBasicMaterial({
        color: "#8ffcff",
        transparent: true,
        opacity: 0.62,
        depthWrite: false,
      }),
    );
    coreGroup.add(coreGlow);

    const innerGlow = new THREE.Mesh(
      new THREE.SphereGeometry(1.48, 48, 48),
      new THREE.MeshBasicMaterial({
        color: "#16b9ff",
        transparent: true,
        opacity: 0.08,
        depthWrite: false,
      }),
    );
    coreGroup.add(innerGlow);

    const wireShell = new THREE.LineSegments(
      new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(1.64, 2)),
      new THREE.LineBasicMaterial({
        color: "#5eeaff",
        transparent: true,
        opacity: 0.16,
      }),
    );
    coreGroup.add(wireShell);

    const nodes = nodeSeeds.map((seed) => ({
      position: new THREE.Vector3(...seed.position),
      size: seed.size,
    }));

    const nodeMaterial = new THREE.MeshStandardMaterial({
      color: "#dffcff",
      emissive: "#18c8ff",
      emissiveIntensity: 1.2,
      roughness: 0.32,
      metalness: 0.18,
    });
    const nodeGeometry = new THREE.SphereGeometry(1, 18, 18);
    const nodeMeshes = nodes.map((node) => {
      const mesh = new THREE.Mesh(nodeGeometry, nodeMaterial.clone());
      mesh.position.copy(node.position);
      mesh.scale.setScalar(node.size);
      coreGroup.add(mesh);
      return mesh;
    });

    const connectionPositions: number[] = [];
    buildConnections(nodes).forEach(([a, b]) => {
      connectionPositions.push(...nodes[a].position.toArray(), ...nodes[b].position.toArray());
    });
    const connectionGeometry = new THREE.BufferGeometry();
    connectionGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(connectionPositions, 3),
    );
    const connectionLines = new THREE.LineSegments(
      connectionGeometry,
      new THREE.LineBasicMaterial({ color: "#27b9ff", transparent: true, opacity: 0.38 }),
    );
    coreGroup.add(connectionLines);

    const signalGeometry = new THREE.SphereGeometry(0.035, 12, 12);
    const signalMaterial = new THREE.MeshBasicMaterial({
      color: "#ffffff",
      transparent: true,
      opacity: 0,
    });
    const signalParticles = signalEdges.map(() => {
      const mesh = new THREE.Mesh(signalGeometry, signalMaterial.clone());
      mesh.visible = false;
      coreGroup.add(mesh);
      return mesh;
    });

    const ringGroup = new THREE.Group();
    coreGroup.add(ringGroup);
    [
      { radius: 1.76, tube: 0.009, rotation: [Math.PI / 2.25, 0.2, 0.1], speed: 0.34, color: "#25d8ff" },
      { radius: 2.00, tube: 0.007, rotation: [0.2, Math.PI / 2.1, -0.45], speed: -0.28, color: "#2f6dff" },
      { radius: 2.20, tube: 0.006, rotation: [Math.PI / 3.1, Math.PI / 4.4, 0.7], speed: 0.22, color: "#bffaff" },
    ].forEach((ring) => {
      const mesh = new THREE.Mesh(
        new THREE.TorusGeometry(ring.radius, ring.tube, 10, 160),
        new THREE.MeshBasicMaterial({ color: ring.color, transparent: true, opacity: 0.62 }),
      );
      mesh.rotation.set(ring.rotation[0], ring.rotation[1], ring.rotation[2]);
      mesh.userData.speed = ring.speed;
      ringGroup.add(mesh);
    });

    const platform = new THREE.Group();
    platform.position.set(0, -1.35, 0);
    platform.rotation.x = Math.PI * 0.46;
    root.add(platform);
    [1.0, 1.45, 1.85].forEach((radius, index) => {
      const mesh = new THREE.Mesh(
        new THREE.TorusGeometry(radius, index === 0 ? 0.012 : 0.009, 12, 140),
        new THREE.MeshBasicMaterial({
          color: index === 1 ? "#1d8cff" : "#7df9ff",
          transparent: true,
          opacity: index === 0 ? 0.45 : 0.30,
        }),
      );
      mesh.userData.direction = index % 2 === 0 ? 1 : -1;
      platform.add(mesh);
    });
    platform.add(
      new THREE.Mesh(
        new THREE.CircleGeometry(1.22, 64),
        new THREE.MeshBasicMaterial({
          color: "#1abfff",
          transparent: true,
          opacity: 0.06,
          side: THREE.DoubleSide,
        }),
      ),
    );

    const particleCount = flags.mobile ? 28 : 68;
    const particleGroup = new THREE.Group();
    root.add(particleGroup);
    const particleMeshes = Array.from({ length: particleCount }, (_, index) => {
      const isWhite = index % 3 === 0;
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(1, 8, 8),
        new THREE.MeshBasicMaterial({
          color: isWhite ? "#ffffff" : index % 2 === 0 ? "#7df9ff" : "#38bdf8",
          transparent: true,
          opacity: 0,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        }),
      );
      mesh.userData = {
        progress: index / particleCount,
        seedAngle: (index / particleCount) * Math.PI * 2 + Math.sin(index * 9.1) * 0.4,
        seedRadius: 0.45 + (((index * 29) % 100) / 100) * 1.25,
        speed: 0.16 + (((index * 17) % 100) / 100) * 0.10,
        swirlSpeed: (index % 2 === 0 ? 1 : -1) * (1.1 + (((index * 31) % 100) / 100) * 0.8),
        baseSize: 0.028 + (((index * 41) % 100) / 100) * 0.026,
        startY: -1.35 + (((index * 13) % 100) / 100) * 0.15,
      };
      particleGroup.add(mesh);
      return mesh;
    });

    const clock = new THREE.Clock();
    let frameId = 0;
    let elapsed = 0;
    let smoothTrain = 0;
    let smoothOutput = 0;

    let lastW = 0;
    let lastH = 0;
    const resize = () => {
      const width = Math.round(host.clientWidth);
      const height = Math.round(host.clientHeight);
      if (width === 0 || height === 0) return;
      if (Math.abs(width - lastW) < 2 && Math.abs(height - lastH) < 2) return;
      lastW = width;
      lastH = height;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
      updateScale(width, height);
    };

    const animate = () => {
      const delta = Math.min(clock.getDelta(), 0.05);
      elapsed += delta;
      const phase = elapsed % 8;

      // Smooth bell-curve energy powers without abrupt step-function jumps
      const rawTrain = phase > 3.2 && phase < 6.5
        ? Math.sin(((phase - 3.2) / 3.3) * Math.PI)
        : 0;
      smoothTrain = THREE.MathUtils.lerp(smoothTrain, rawTrain, delta * 5);

      const rawOutput = phase > 6.4 && phase < 7.8
        ? Math.sin(((phase - 6.4) / 1.4) * Math.PI)
        : 0;
      smoothOutput = THREE.MathUtils.lerp(smoothOutput, rawOutput, delta * 5);

      const trainPower = smoothTrain;
      const outputPower = smoothOutput;
      const pointerPower = flags.reduced || flags.mobile ? 0 : 1;
      const latestPointer = pointerRef.current;

      root.rotation.y = THREE.MathUtils.lerp(root.rotation.y, latestPointer.x * 0.16 * pointerPower, 0.045);
      root.rotation.x = THREE.MathUtils.lerp(root.rotation.x, -latestPointer.y * 0.08 * pointerPower, 0.045);
      root.position.set(0, 0.18, 0);

      coreGroup.rotation.y += (flags.reduced ? 0.05 : 0.18 + trainPower * 0.12) * delta * 0.8;
      coreGroup.rotation.x = Math.sin(elapsed * 0.34) * 0.04;
      coreGroup.position.y = 0.35;
      coreGroup.scale.setScalar(1 + trainPower * 0.035 + outputPower * 0.055);
      coreLight.intensity = 2.1 + Math.sin(elapsed * 2.3) * 0.32 + trainPower * 0.8 + outputPower * 1.2;
      coreGlow.scale.setScalar(1 + Math.sin(elapsed * 2.4) * 0.12 + trainPower * 0.18 + outputPower * 0.24);
      (coreGlow.material as THREE.MeshBasicMaterial).opacity = 0.52 + Math.sin(elapsed * 2.6) * 0.12 + outputPower * 0.18;
      innerGlow.scale.setScalar(1 + Math.sin(elapsed * 1.1) * 0.04 + trainPower * 0.08);
      (innerGlow.material as THREE.MeshBasicMaterial).opacity = 0.07 + trainPower * 0.05 + outputPower * 0.06;
      wireShell.rotation.y -= (flags.reduced ? 0.001 : 0.006 + trainPower * 0.003) * delta * 60;
      wireShell.rotation.z += (flags.reduced ? 0.0008 : 0.003) * delta * 60;
      (wireShell.material as THREE.LineBasicMaterial).opacity = 0.12 + trainPower * 0.09 + outputPower * 0.07;

      nodeMeshes.forEach((mesh, index) => {
        const pulse = Math.sin(elapsed * (flags.reduced ? 0.8 : 2.0) + index * 0.9) * 0.5 + 0.5;
        const activation = trainPower * pulse + pulse * 0.25;
        mesh.scale.setScalar(nodes[index].size * (1 + activation * (flags.reduced ? 0.04 : 0.2)));
        const material = mesh.material as THREE.MeshStandardMaterial;
        material.emissiveIntensity = 0.85 + activation * 1.45;
      });

      ringGroup.children.forEach((child) => {
        const speed = child.userData.speed as number;
        child.rotation.z += speed * (flags.reduced ? 0.18 : 1 + trainPower * 0.35) * delta * 0.75;
        child.rotation.x += speed * delta * 0.12;
      });

      platform.children.forEach((child) => {
        child.rotation.z += (child.userData.direction || 1) * (flags.reduced ? 0.002 : 0.006);
      });
      platform.scale.setScalar(1 + Math.sin(elapsed * 1.2) * (flags.reduced ? 0.01 : 0.03));

      signalParticles.forEach((mesh, index) => {
        const [startIndex, endIndex] = signalEdges[index];
        const prog = (elapsed * 0.48 + index * 0.125) % 1;
        mesh.position.lerpVectors(nodes[startIndex].position, nodes[endIndex].position, prog);
        (mesh.material as THREE.MeshBasicMaterial).opacity = Math.sin(prog * Math.PI) * trainPower;
        mesh.visible = trainPower > 0.03 && !flags.reduced;
      });

      if (!flags.reduced) {
        const speedMultiplier = 1 + trainPower * 0.45;
        particleMeshes.forEach((mesh) => {
          const seed = mesh.userData as {
            progress: number;
            seedAngle: number;
            seedRadius: number;
            speed: number;
            swirlSpeed: number;
            baseSize: number;
            startY: number;
          };

          // Continuous delta integration: NEVER teleports or stutters
          seed.progress = (seed.progress + delta * seed.speed * speedMultiplier) % 1;
          const p = seed.progress;

          // Smooth cubic easing for fluid acceleration
          const easeProg = p * p * (3 - 2 * p);

          // Flow upward from bottom platform into core center
          const currentY = THREE.MathUtils.lerp(seed.startY, 0.35, easeProg);
          const currentR = seed.seedRadius * Math.pow(1 - p, 0.82);
          const currentAngle = seed.seedAngle + p * seed.swirlSpeed * Math.PI;

          const x = Math.cos(currentAngle) * currentR;
          const z = Math.sin(currentAngle) * currentR * 0.75;

          mesh.position.set(x, currentY, z);

          let alpha = 1;
          if (p < 0.18) {
            alpha = p / 0.18;
          } else if (p > 0.76) {
            alpha = (1 - p) / 0.24;
          }

          const mat = mesh.material as THREE.MeshBasicMaterial;
          mat.opacity = alpha * 0.9;

          const scale = seed.baseSize * (0.8 + Math.sin(p * Math.PI) * 0.75 + trainPower * 0.3);
          mesh.scale.setScalar(scale);
        });
      }

      renderer.render(scene, camera);
      frameId = window.requestAnimationFrame(animate);
    };

    resize();
    const resizeObserver = new ResizeObserver(() => {
      resize();
    });
    resizeObserver.observe(host);
    window.addEventListener("resize", resize);
    frameId = window.requestAnimationFrame(animate);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
      resizeObserver.disconnect();
      renderer.dispose();
      disposeObject(root);
      disposeObject(scene);
      renderer.domElement.remove();
    };
  }, [pointerRef]);

  return <div ref={hostRef} className="automl-ai-canvas-shell" />;
}
