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
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(0, 0.58, 7.4);
    camera.lookAt(0, 0.58, 0);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
    host.appendChild(renderer.domElement);

    const root = new THREE.Group();
    root.scale.setScalar(flags.mobile ? 1.06 : 1.23);
    scene.add(root);

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
      { radius: 1.82, tube: 0.009, rotation: [Math.PI / 2.25, 0.2, 0.1], speed: 0.34, color: "#25d8ff" },
      { radius: 2.06, tube: 0.007, rotation: [0.2, Math.PI / 2.1, -0.45], speed: -0.28, color: "#2f6dff" },
      { radius: 2.28, tube: 0.006, rotation: [Math.PI / 3.1, Math.PI / 4.4, 0.7], speed: 0.22, color: "#bffaff" },
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
    platform.position.set(0, -1.7, 0);
    platform.rotation.x = Math.PI / 2;
    root.add(platform);
    [1.2, 1.65, 2.05].forEach((radius, index) => {
      const mesh = new THREE.Mesh(
        new THREE.TorusGeometry(radius, index === 0 ? 0.012 : 0.009, 10, 140),
        new THREE.MeshBasicMaterial({
          color: index === 1 ? "#1d8cff" : "#7df9ff",
          transparent: true,
          opacity: index === 0 ? 0.42 : 0.28,
        }),
      );
      mesh.userData.direction = index % 2 === 0 ? 1 : -1;
      platform.add(mesh);
    });
    platform.add(
      new THREE.Mesh(
        new THREE.CircleGeometry(1.38, 96),
        new THREE.MeshBasicMaterial({
          color: "#1abfff",
          transparent: true,
          opacity: 0.055,
          side: THREE.DoubleSide,
        }),
      ),
    );
    platform.add(
      new THREE.Mesh(
        new THREE.CylinderGeometry(0.22, 1.18, 2.25, 64, 1, true),
        new THREE.MeshBasicMaterial({
          color: "#7df9ff",
          transparent: true,
          opacity: 0.075,
          side: THREE.DoubleSide,
          depthWrite: false,
        }),
      ),
    );

    const particleCount = flags.mobile ? 26 : 64;
    const particleGroup = new THREE.Group();
    root.add(particleGroup);
    const particleMeshes = Array.from({ length: particleCount }, (_, index) => {
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(1, 10, 10),
        new THREE.MeshBasicMaterial({
          color: index % 4 === 0 ? "#ffffff" : "#6ee7ff",
          transparent: true,
          opacity: 0.86,
        }),
      );
      mesh.userData = {
        offset: (index % 12) / 12 + Math.floor(index / 12) * 0.035,
        lane: ((index * 37) % 100) / 100 - 0.5,
        depth: ((index * 53) % 100) / 100 - 0.5,
        size: 0.025 + (((index * 17) % 100) / 100) * 0.026,
      };
      particleGroup.add(mesh);
      return mesh;
    });

    const clock = new THREE.Clock();
    let frameId = 0;

    const resize = () => {
      const width = Math.max(host.clientWidth, 1);
      const height = Math.max(host.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };

    const animate = () => {
      const elapsed = clock.getElapsedTime();
      const phase = elapsed % 8;
      const trainPower = phase > 4 && phase < 6 ? 1 : 0;
      const outputPower = phase > 6 && phase < 7 ? 1 : 0;
      const pointerPower = flags.reduced || flags.mobile ? 0 : 1;
      const latestPointer = pointerRef.current;

      root.rotation.y = THREE.MathUtils.lerp(root.rotation.y, latestPointer.x * 0.16 * pointerPower, 0.045);
      root.rotation.x = THREE.MathUtils.lerp(root.rotation.x, -latestPointer.y * 0.08 * pointerPower, 0.045);
      root.position.set(0.1, 0.52 + Math.sin(elapsed * 0.8) * (flags.reduced ? 0.025 : 0.075), 0);

      coreGroup.rotation.y += (flags.reduced ? 0.05 : 0.18 + trainPower * 0.12) * 0.012;
      coreGroup.rotation.x = Math.sin(elapsed * 0.34) * 0.08;
      coreGroup.position.y = 0.35 + Math.sin(elapsed * 0.86) * (flags.reduced ? 0.04 : 0.14);
      coreGroup.scale.setScalar(1 + trainPower * 0.035 + outputPower * 0.055);
      coreLight.intensity = 2.1 + Math.sin(elapsed * 2.3) * 0.32 + trainPower * 0.8 + outputPower * 1.2;
      coreGlow.scale.setScalar(1 + Math.sin(elapsed * 2.4) * 0.12 + trainPower * 0.18 + outputPower * 0.24);
      (coreGlow.material as THREE.MeshBasicMaterial).opacity = 0.52 + Math.sin(elapsed * 2.6) * 0.12 + outputPower * 0.18;
      innerGlow.scale.setScalar(1 + Math.sin(elapsed * 1.1) * 0.04 + trainPower * 0.08);
      (innerGlow.material as THREE.MeshBasicMaterial).opacity = 0.07 + trainPower * 0.05 + outputPower * 0.06;
      wireShell.rotation.y -= (flags.reduced ? 0.001 : 0.006 + trainPower * 0.003);
      wireShell.rotation.z += (flags.reduced ? 0.0008 : 0.003);
      (wireShell.material as THREE.LineBasicMaterial).opacity = 0.12 + trainPower * 0.09 + outputPower * 0.07;

      nodeMeshes.forEach((mesh, index) => {
        const input = phase > 2 && phase < 4;
        const pulse = Math.sin(elapsed * (flags.reduced ? 0.8 : 2.2) + index * 0.9) * 0.5 + 0.5;
        const activation = trainPower || (input && index % 3 === 0) ? pulse : pulse * 0.35;
        mesh.scale.setScalar(nodes[index].size * (1 + activation * (flags.reduced ? 0.04 : 0.22)));
        const material = mesh.material as THREE.MeshStandardMaterial;
        material.emissiveIntensity = 0.85 + activation * 1.55;
      });

      ringGroup.children.forEach((child) => {
        child.rotation.z += (child.userData.speed as number) * (flags.reduced ? 0.18 : 1 + trainPower * 0.5) * 0.012;
        child.rotation.x += (child.userData.speed as number) * 0.002;
      });

      platform.children.forEach((child) => {
        child.rotation.z += (child.userData.direction || 1) * (flags.reduced ? 0.002 : 0.006);
      });
      platform.scale.setScalar(1 + Math.sin(elapsed * 1.2) * (flags.reduced ? 0.01 : 0.03));

      const signalActive = phase > 4 && phase < 6.8 && !flags.reduced;
      signalParticles.forEach((mesh, index) => {
        mesh.visible = signalActive;
        if (!signalActive) return;

        const [startIndex, endIndex] = signalEdges[index];
        const progress = ((phase - 4) * 0.52 + index * 0.13) % 1;
        mesh.position.lerpVectors(nodes[startIndex].position, nodes[endIndex].position, progress);
        (mesh.material as THREE.MeshBasicMaterial).opacity = Math.sin(progress * Math.PI);
      });

      const inputActive = phase > 2 && phase < 4;
      const outputActive = phase > 6 && phase < 7;
      particleGroup.visible = (inputActive || outputActive) && !flags.reduced;
      if (particleGroup.visible) {
        particleMeshes.forEach((mesh) => {
          const seed = mesh.userData as { offset: number; lane: number; depth: number; size: number };
          const rawProgress = inputActive
            ? (phase - 2) / 2 - seed.offset * 0.42
            : (phase - 6) / 1 - seed.offset * 0.32;
          const progress = THREE.MathUtils.clamp(rawProgress, 0, 1);
          const laneY = seed.lane * 1.6;
          const laneZ = seed.depth * 1.3;
          const start = inputActive
            ? new THREE.Vector3(-4.3, laneY - 0.45, laneZ)
            : new THREE.Vector3(0, 0.35, 0);
          const end = inputActive
            ? new THREE.Vector3(seed.lane * 0.55, seed.depth * 0.45 + 0.35, seed.depth * 0.28)
            : new THREE.Vector3(3.6, laneY * 0.35 + 0.35, laneZ * 0.55);
          const point = new THREE.Vector3()
            .lerpVectors(start, end, progress)
            .add(new THREE.Vector3(0, Math.sin(progress * Math.PI) * (inputActive ? 0.72 : 0.35), 0));

          mesh.visible = rawProgress > 0 && rawProgress < 1;
          mesh.position.copy(point);
          mesh.scale.setScalar(seed.size * (1 + Math.sin(progress * Math.PI) * 1.25));
        });
      }

      renderer.render(scene, camera);
      frameId = window.requestAnimationFrame(animate);
    };

    resize();
    window.addEventListener("resize", resize);
    frameId = window.requestAnimationFrame(animate);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
      renderer.dispose();
      disposeObject(root);
      disposeObject(scene);
      renderer.domElement.remove();
    };
  }, [pointerRef]);

  return <div ref={hostRef} className="automl-ai-canvas-shell" />;
}
