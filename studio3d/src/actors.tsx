import React, {useLayoutEffect, useMemo, useRef} from 'react';
import * as THREE from 'three';
import {rnd, terrainY} from './world';

type IM = THREE.InstancedMesh;
const mk = () => ({m: new THREE.Matrix4(), q: new THREE.Quaternion(), e: new THREE.Euler(), p: new THREE.Vector3(), s: new THREE.Vector3(), c: new THREE.Color()});

export const Soldiers: React.FC<{t: number; n?: number; cols?: number; ox?: number; oz?: number; speed?: number}> = ({t, n = 420, cols = 14, ox = -22, oz = -6, speed = 3.0}) => {
  const R = {legL: useRef<IM>(null), legR: useRef<IM>(null), torso: useRef<IM>(null), head: useRef<IM>(null), helm: useRef<IM>(null), shield: useRef<IM>(null), spear: useRef<IM>(null), shadow: useRef<IM>(null)};
  const d = useMemo(() => new THREE.Object3D(), []);
  const legGeo = useMemo(() => { const g = new THREE.BoxGeometry(0.3, 0.95, 0.32); g.translate(0, -0.47, 0); return g; }, []);
  useLayoutEffect(() => {
    const c = new THREE.Color();
    const put = (m: IM, i: number, x: number, y: number, z: number, rx = 0, ry = 0, sx = 1, sy = 1, sz = 1) => { d.position.set(x, y, z); d.rotation.set(rx, ry, 0); d.scale.set(sx, sy, sz); d.updateMatrix(); m.setMatrixAt(i, d.matrix); };
    for (let i = 0; i < n; i++) {
      const col = i % cols, row = Math.floor(i / cols);
      const x = ox + col * 3.0 + (rnd(i) - 0.5) * 1.2, z = oz + row * 3.4 - t * speed + (rnd(i + 99) - 0.5) * 1.2;
      const ph = t * 6.0 + rnd(i + 7) * 6.28, gy = terrainY(x, z), hip = gy + 1.0 + Math.abs(Math.sin(ph)) * 0.12;
      put(R.legL.current!, i, x - 0.18, hip, z, Math.sin(ph) * 0.7); put(R.legR.current!, i, x + 0.18, hip, z, -Math.sin(ph) * 0.7);
      put(R.torso.current!, i, x, hip + 0.75, z); put(R.head.current!, i, x, hip + 1.7, z); put(R.helm.current!, i, x, hip + 1.95, z);
      put(R.shield.current!, i, x - 0.62, hip + 0.85, z, 0, Math.PI / 2); put(R.spear.current!, i, x + 0.62, hip + 0.95, z, 0.05);
      put(R.shadow.current!, i, x, gy + 0.05, z, -Math.PI / 2, 0, 1.1, 1.1, 1);
      R.torso.current!.setColorAt(i, c.setHSL(0.985 + rnd(i + 3) * 0.02, 0.5, 0.24 + rnd(i + 5) * 0.06));
      R.shield.current!.setColorAt(i, c.setHSL(0.11, 0.55, 0.38 + rnd(i + 9) * 0.1));
    }
    Object.values(R).forEach((r) => { r.current!.instanceMatrix.needsUpdate = true; if (r.current!.instanceColor) r.current!.instanceColor.needsUpdate = true; });
  }, [t]);
  const inst = (k: keyof typeof R, geo: React.ReactNode, mat: React.ReactNode) => <instancedMesh ref={R[k]} args={[undefined, undefined, n]} frustumCulled={false}>{geo}{mat}</instancedMesh>;
  return (
    <>
      <instancedMesh ref={R.legL} args={[legGeo, undefined, n]} frustumCulled={false}><meshStandardMaterial color="#3b2a22" flatShading /></instancedMesh>
      <instancedMesh ref={R.legR} args={[legGeo, undefined, n]} frustumCulled={false}><meshStandardMaterial color="#3b2a22" flatShading /></instancedMesh>
      {inst('torso', <cylinderGeometry args={[0.42, 0.55, 1.5, 6]} />, <meshStandardMaterial flatShading />)}
      {inst('head', <icosahedronGeometry args={[0.32, 1]} />, <meshStandardMaterial color="#a9714a" flatShading />)}
      {inst('helm', <coneGeometry args={[0.36, 0.5, 6]} />, <meshStandardMaterial color="#c79a4b" metalness={0.5} roughness={0.5} flatShading />)}
      {inst('shield', <cylinderGeometry args={[0.55, 0.55, 0.08, 8]} />, <meshStandardMaterial flatShading />)}
      {inst('spear', <cylinderGeometry args={[0.04, 0.04, 3.8, 5]} />, <meshStandardMaterial color="#4a3422" flatShading />)}
      {inst('shadow', <circleGeometry args={[0.8, 10]} />, <meshBasicMaterial color="#5a3a1c" transparent opacity={0.35} depthWrite={false} />)}
    </>
  );
};

export const camelPath = (z: number) => 14 * Math.sin(z * 0.035) + 6 * Math.sin(z * 0.011 + 1);

export const Camels: React.FC<{t: number; n?: number; z0?: number; gap?: number; speed?: number}> = ({t, n = 28, z0 = 30, gap = 6.5, speed = 2.4}) => {
  const R = {body: useRef<IM>(null), hump: useRef<IM>(null), neck: useRef<IM>(null), head: useRef<IM>(null), pack: useRef<IM>(null), l0: useRef<IM>(null), l1: useRef<IM>(null), l2: useRef<IM>(null), l3: useRef<IM>(null), shadow: useRef<IM>(null)};
  const leg = useMemo(() => { const g = new THREE.BoxGeometry(0.24, 1.4, 0.24); g.translate(0, -0.7, 0); return g; }, []);
  useLayoutEffect(() => {
    const {m, q, e, p, s, c} = mk();
    const root = new THREE.Matrix4(), loc = new THREE.Matrix4();
    const put = (r: IM, i: number, x: number, y: number, z: number, rx = 0, sx = 1, sy = 1, sz = 1) => {
      e.set(rx, 0, 0); q.setFromEuler(e); p.set(x, y, z); s.set(sx, sy, sz); loc.compose(p, q, s); m.multiplyMatrices(root, loc); r.setMatrixAt(i, m);
    };
    for (let i = 0; i < n; i++) {
      const z = z0 - i * gap - t * speed + (rnd(i) - 0.5) * 1.2, x = camelPath(z) + (rnd(i + 5) - 0.5) * 1.6, gy = terrainY(x, z);
      const dx = (camelPath(z + 0.5) - camelPath(z - 0.5));
      const yaw = Math.atan2(dx, 1);  // moving toward -z: turn with the path
      e.set(0, yaw, 0); q.setFromEuler(e); root.compose(new THREE.Vector3(x, gy, z), q, new THREE.Vector3(1, 1, 1));
      const ph = t * 4.2 + i * 0.9, bob = Math.abs(Math.sin(ph)) * 0.06;
      put(R.body.current!, i, 0, 1.95 + bob, 0, 0, 1, 1, 1); put(R.hump.current!, i, 0, 2.75 + bob, 0.2, 0, 1, 1, 1.2);
      put(R.neck.current!, i, 0, 2.75 + bob, -1.35, -0.55); put(R.head.current!, i, 0, 3.5 + bob, -1.9);
      put(R.pack.current!, i, 0, 2.95 + bob, 0.25);
      const legs = [[-0.35, 0.9, 0], [0.35, 0.9, 2], [-0.35, -0.9, 1], [0.35, -0.9, 3]];
      [R.l0, R.l1, R.l2, R.l3].forEach((r, k) => put(r.current!, i, legs[k][0], 1.4 + bob, legs[k][1], Math.sin(ph + (k % 2 ? Math.PI : 0) + (k > 1 ? 1.6 : 0)) * 0.5));
      e.set(-Math.PI / 2, 0, 0); q.setFromEuler(e); p.set(0, 0.06, 0); s.set(1.9, 1.5, 1); loc.compose(p, q, s); m.multiplyMatrices(root, loc); R.shadow.current!.setMatrixAt(i, m);
      R.pack.current!.setColorAt(i, c.setHSL(0.02 + (i % 4) * 0.07, 0.45, 0.32 + rnd(i + 2) * 0.1));
    }
    Object.values(R).forEach((r) => { r.current!.instanceMatrix.needsUpdate = true; if (r.current!.instanceColor) r.current!.instanceColor.needsUpdate = true; });
  }, [t]);
  const body = '#b98a4e';
  const I = (k: keyof typeof R, args: any[], geo: React.ReactNode, color?: string) => <instancedMesh ref={R[k]} args={[args[0], undefined, n]} frustumCulled={false}>{geo}<meshStandardMaterial color={color ?? '#ffffff'} flatShading /></instancedMesh>;
  return (
    <>
      {I('body', [undefined], <boxGeometry args={[1.0, 1.1, 2.6]} />, body)}
      {I('hump', [undefined], <icosahedronGeometry args={[0.55, 1]} />, '#c39556')}
      {I('neck', [undefined], <boxGeometry args={[0.38, 1.5, 0.4]} />, '#a77a44')}
      {I('head', [undefined], <boxGeometry args={[0.42, 0.4, 0.85]} />, '#a77a44')}
      {I('pack', [undefined], <boxGeometry args={[1.25, 0.7, 1.3]} />)}
      {[R.l0, R.l1, R.l2, R.l3].map((r, k) => <instancedMesh key={k} ref={r} args={[leg, undefined, n]} frustumCulled={false}><meshStandardMaterial color="#8e6538" flatShading /></instancedMesh>)}
      <instancedMesh ref={R.shadow} args={[undefined, undefined, n]} frustumCulled={false}><circleGeometry args={[0.8, 10]} /><meshBasicMaterial color="#5a3a1c" transparent opacity={0.35} depthWrite={false} /></instancedMesh>
    </>
  );
};

export const Palms: React.FC<{cx: number; cz: number; n?: number}> = ({cx, cz, n = 16}) => {
  const trunk = useRef<IM>(null), crown = useRef<IM>(null);
  const d = useMemo(() => new THREE.Object3D(), []);
  useLayoutEffect(() => {
    for (let i = 0; i < n; i++) {
      const x = cx + (rnd(i + 40) - 0.5) * 46, z = cz + (rnd(i + 80) - 0.5) * 30, y = terrainY(x, z), h = 6 + rnd(i + 3) * 4;
      d.rotation.set(0, 0, (rnd(i) - 0.5) * 0.15); d.position.set(x, y + h / 2, z); d.scale.set(1, h / 8, 1); d.updateMatrix(); trunk.current!.setMatrixAt(i, d.matrix);
      d.rotation.set(0, i, 0); d.position.set(x, y + h + 0.4, z); d.scale.set(2.8, 1.0, 2.8); d.updateMatrix(); crown.current!.setMatrixAt(i, d.matrix);
    }
    trunk.current!.instanceMatrix.needsUpdate = true; crown.current!.instanceMatrix.needsUpdate = true;
  }, []);
  return (
    <>
      <instancedMesh ref={trunk} args={[undefined, undefined, n]} frustumCulled={false}><cylinderGeometry args={[0.25, 0.35, 8, 5]} /><meshStandardMaterial color="#6b4a2f" flatShading /></instancedMesh>
      <instancedMesh ref={crown} args={[undefined, undefined, n]} frustumCulled={false}><icosahedronGeometry args={[1, 0]} /><meshStandardMaterial color="#4f7a3a" flatShading /></instancedMesh>
    </>
  );
};

export const Temple: React.FC<{x: number; z: number}> = ({x, z}) => {
  const y = terrainY(x, z);
  const sand = '#d9bd8e', dark = '#a98a5e';
  return (
    <group position={[x, y, z]}>
      <mesh position={[0, 1, 0]}><boxGeometry args={[46, 2, 26]} /><meshStandardMaterial color={dark} flatShading /></mesh>
      {[-14, -7, 0, 7, 14].flatMap((cx) => [-6, 6].map((cz) => <mesh key={`${cx}${cz}`} position={[cx, 7.5, cz]}><cylinderGeometry args={[1.1, 1.3, 11, 8]} /><meshStandardMaterial color={sand} flatShading /></mesh>))}
      <mesh position={[0, 14, 0]}><boxGeometry args={[40, 2.4, 18]} /><meshStandardMaterial color={sand} flatShading /></mesh>
      {[-26, 26].map((px) => <mesh key={px} position={[px, 10, 12]}><boxGeometry args={[8, 20, 7]} /><meshStandardMaterial color={sand} flatShading /></mesh>)}
      <mesh position={[0, 16.2, 0]}><boxGeometry args={[30, 0.8, 12]} /><meshStandardMaterial color="#f2c46d" flatShading /></mesh>
    </group>
  );
};
