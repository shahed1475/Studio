import React, {useLayoutEffect, useMemo, useRef} from 'react';
import {ThreeCanvas} from '@remotion/three';
import {useCurrentFrame, useVideoConfig, interpolate} from 'remotion';
import {useThree} from '@react-three/fiber';
import {Sky} from '@react-three/drei';
import {EffectComposer, Bloom, Vignette} from '@react-three/postprocessing';
import * as THREE from 'three';

const N = 420;
const COLS = 14;
const terrainY = (x: number, z: number) => Math.sin(x * 0.05) * 3 + Math.sin(z * 0.035 + x * 0.02) * 4 + Math.sin(x * 0.13 + z * 0.09) * 0.6;
const rnd = (i: number) => { const s = Math.sin(i * 12.9898) * 43758.5453; return s - Math.floor(s); };

const Dunes: React.FC = () => {
  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(520, 520, 220, 220);
    g.rotateX(-Math.PI / 2);
    const p = g.attributes.position;
    const col = new Float32Array(p.count * 3);
    const lo = new THREE.Color('#b9854c'), hi = new THREE.Color('#f0cf93'), c = new THREE.Color();
    for (let i = 0; i < p.count; i++) {
      const y = terrainY(p.getX(i), p.getZ(i)); p.setY(i, y);
      c.copy(lo).lerp(hi, THREE.MathUtils.clamp((y + 6) / 12, 0, 1)); col.set([c.r, c.g, c.b], i * 3);
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    g.computeVertexNormals();
    return g;
  }, []);
  return <mesh geometry={geo}><meshStandardMaterial vertexColors flatShading roughness={1} /></mesh>;
};

const Soldiers: React.FC<{t: number}> = ({t}) => {
  const refs = {legL: useRef<THREE.InstancedMesh>(null), legR: useRef<THREE.InstancedMesh>(null), torso: useRef<THREE.InstancedMesh>(null), head: useRef<THREE.InstancedMesh>(null),
    helm: useRef<THREE.InstancedMesh>(null), shield: useRef<THREE.InstancedMesh>(null), spear: useRef<THREE.InstancedMesh>(null), shadow: useRef<THREE.InstancedMesh>(null)};
  const d = useMemo(() => new THREE.Object3D(), []);
  const legGeo = useMemo(() => { const g = new THREE.BoxGeometry(0.3, 0.95, 0.32); g.translate(0, -0.47, 0); return g; }, []);
  useLayoutEffect(() => {
    const c = new THREE.Color();
    const put = (m: THREE.InstancedMesh, i: number, x: number, y: number, z: number, rx = 0, ry = 0, sx = 1, sy = 1, sz = 1) => {
      d.position.set(x, y, z); d.rotation.set(rx, ry, 0); d.scale.set(sx, sy, sz); d.updateMatrix(); m.setMatrixAt(i, d.matrix);
    };
    for (let i = 0; i < N; i++) {
      const col = i % COLS, row = Math.floor(i / COLS);
      const x = -22 + col * 3.0 + (rnd(i) - 0.5) * 1.2;
      const z = -6 + row * 3.4 - t * 3.0 + (rnd(i + 99) - 0.5) * 1.2;
      const ph = t * 6.0 + rnd(i + 7) * 6.28;
      const gy = terrainY(x, z);
      const bob = Math.abs(Math.sin(ph)) * 0.12;
      const hip = gy + 1.0 + bob;
      put(refs.legL.current!, i, x - 0.18, hip, z, Math.sin(ph) * 0.7);
      put(refs.legR.current!, i, x + 0.18, hip, z, -Math.sin(ph) * 0.7);
      put(refs.torso.current!, i, x, hip + 0.75, z, 0, 0);
      put(refs.head.current!, i, x, hip + 1.7, z);
      put(refs.helm.current!, i, x, hip + 1.95, z);
      put(refs.shield.current!, i, x - 0.62, hip + 0.85, z, 0, Math.PI / 2);
      put(refs.spear.current!, i, x + 0.62, hip + 0.95, z, 0.05);
      put(refs.shadow.current!, i, x, gy + 0.05, z, -Math.PI / 2, 0, 1.1, 1.1, 1);
      refs.torso.current!.setColorAt(i, c.setHSL(0.985 + rnd(i + 3) * 0.02, 0.5, 0.24 + rnd(i + 5) * 0.06));
      refs.shield.current!.setColorAt(i, c.setHSL(0.11, 0.55, 0.38 + rnd(i + 9) * 0.1));
    }
    Object.values(refs).forEach((r) => { r.current!.instanceMatrix.needsUpdate = true; if (r.current!.instanceColor) r.current!.instanceColor.needsUpdate = true; });
  }, [t]);
  const inst = (key: keyof typeof refs, geo: React.ReactNode, mat: React.ReactNode) => <instancedMesh ref={refs[key]} args={[undefined, undefined, N]} frustumCulled={false}>{geo}{mat}</instancedMesh>;
  return (
    <>
      <instancedMesh ref={refs.legL} args={[legGeo, undefined, N]} frustumCulled={false}><meshStandardMaterial color="#3b2a22" flatShading /></instancedMesh>
      <instancedMesh ref={refs.legR} args={[legGeo, undefined, N]} frustumCulled={false}><meshStandardMaterial color="#3b2a22" flatShading /></instancedMesh>
      {inst('torso', <cylinderGeometry args={[0.42, 0.55, 1.5, 6]} />, <meshStandardMaterial flatShading />)}
      {inst('head', <icosahedronGeometry args={[0.32, 1]} />, <meshStandardMaterial color="#a9714a" flatShading />)}
      {inst('helm', <coneGeometry args={[0.36, 0.5, 6]} />, <meshStandardMaterial color="#c79a4b" metalness={0.5} roughness={0.5} flatShading />)}
      {inst('shield', <cylinderGeometry args={[0.55, 0.55, 0.08, 8]} />, <meshStandardMaterial flatShading />)}
      {inst('spear', <cylinderGeometry args={[0.04, 0.04, 3.8, 5]} />, <meshStandardMaterial color="#4a3422" flatShading />)}
      {inst('shadow', <circleGeometry args={[0.8, 10]} />, <meshBasicMaterial color="#5a3a1c" transparent opacity={0.35} depthWrite={false} />)}
    </>
  );
};

const StormWall: React.FC<{t: number}> = ({t}) => {
  const ref = useRef<THREE.InstancedMesh>(null);
  const d = useMemo(() => new THREE.Object3D(), []);
  const M = 46;
  useLayoutEffect(() => {
    for (let i = 0; i < M; i++) {
      const a = (i / M - 0.5) * 2.4;
      const dist = 190 - t * 5 + rnd(i) * 30;
      d.position.set(Math.sin(a) * dist * 1.1 - 10, 14 + rnd(i + 4) * 22, -Math.cos(a) * dist - 70);
      const s = 16 + rnd(i + 2) * 22; d.scale.set(s * 1.5, s, s * 1.2); d.rotation.set(rnd(i), rnd(i + 1) * 6, 0); d.updateMatrix(); ref.current!.setMatrixAt(i, d.matrix);
    }
    ref.current!.instanceMatrix.needsUpdate = true;
  }, [t]);
  return <instancedMesh ref={ref} args={[undefined, undefined, M]} frustumCulled={false}><icosahedronGeometry args={[1, 1]} /><meshStandardMaterial color="#b98a55" transparent opacity={0.5} depthWrite={false} roughness={1} /></instancedMesh>;
};

const Dust: React.FC<{t: number}> = ({t}) => {
  const ref = useRef<THREE.InstancedMesh>(null);
  const d = useMemo(() => new THREE.Object3D(), []);
  const M = 260;
  useLayoutEffect(() => {
    for (let i = 0; i < M; i++) {
      const x = ((rnd(i) * 140 - 70 + t * 7) % 140) - 70, z = -60 + rnd(i + 1) * 90 - t * 3, y = terrainY(x, z) + 0.6 + rnd(i + 2) * 5;
      d.position.set(x, y, z); d.rotation.set(t + i, t * 0.5, 0); const s = 0.12 + rnd(i + 3) * 0.2; d.scale.set(s, s, s); d.updateMatrix(); ref.current!.setMatrixAt(i, d.matrix);
    }
    ref.current!.instanceMatrix.needsUpdate = true;
  }, [t]);
  return <instancedMesh ref={ref} args={[undefined, undefined, M]} frustumCulled={false}><tetrahedronGeometry args={[1, 0]} /><meshBasicMaterial color="#f3dcae" transparent opacity={0.5} depthWrite={false} /></instancedMesh>;
};

const Rig: React.FC<{t: number}> = ({t}) => {
  const {camera} = useThree();
  useLayoutEffect(() => {
    const k = t / 6;
    camera.position.set(-40 + k * 14, 3.2 + k * 8.5, 26 - k * 30);
    camera.lookAt(-4, 3.5, -34 - t * 3);
    (camera as THREE.PerspectiveCamera).fov = 44; camera.updateProjectionMatrix();
  }, [t, camera]);
  return null;
};

export const Army: React.FC = () => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const t = frame / fps;
  const far = interpolate(frame, [0, durationInFrames - 1], [260, 120]);
  return (
    <ThreeCanvas width={width} height={height} camera={{fov: 44, position: [-40, 3.2, 26]}}>
      <color attach="background" args={['#e8c48c']} />
      <fog attach="fog" args={['#e3bd86', 40, far]} />
      <Sky distance={450000} sunPosition={[-120, 14, -80]} turbidity={9} rayleigh={1.6} mieCoefficient={0.012} mieDirectionalG={0.92} />
      <ambientLight intensity={0.75} color="#ffe6c0" />
      <hemisphereLight args={['#ffe2b0', '#7a4a28', 0.6]} />
      <directionalLight position={[-120, 30, -80]} intensity={3.2} color="#ffc27a" />
      <Rig t={t} />
      <Dunes />
      <Soldiers t={t} />
      <Dust t={t} />
      <StormWall t={t} />
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.55} luminanceThreshold={0.82} mipmapBlur />
        <Vignette offset={0.25} darkness={0.6} />
      </EffectComposer>
    </ThreeCanvas>
  );
};
