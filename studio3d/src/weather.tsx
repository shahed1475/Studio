import React, {useLayoutEffect, useMemo, useRef} from 'react';
import * as THREE from 'three';
import {rnd, terrainY} from './world';

type IM = THREE.InstancedMesh;

/** A wall of layered dust puffs (outer pale, inner dark) whose front moves with time. frontZ(t) is where the wall's face is. */
export const StormWall: React.FC<{t: number; frontZ: number; width?: number; layers?: number}> = ({frontZ, width = 190, layers = 2}) => {
  const refs = [useRef<IM>(null), useRef<IM>(null), useRef<IM>(null)];
  const d = useMemo(() => new THREE.Object3D(), []);
  const M = 40;
  useLayoutEffect(() => {
    for (let L = 0; L < layers; L++) {
      for (let i = 0; i < M; i++) {
        const k = (i / M - 0.5) * 2;
        const x = k * width + (rnd(i + L * 50) - 0.5) * 20, z = frontZ - L * 22 - rnd(i + 7 * L) * 18;
        const base = terrainY(x, z), s = 15 + rnd(i + 3 + L) * 20 + L * 4;
        d.position.set(x, base + s * (0.55 + L * 0.12), z); d.scale.set(s * 1.5, s, s * 1.2); d.rotation.set(rnd(i), rnd(i + 1) * 6, 0); d.updateMatrix();
        refs[L].current!.setMatrixAt(i, d.matrix);
      }
      refs[L].current!.instanceMatrix.needsUpdate = true;
    }
  }, [frontZ]);
  const colors = ['#d2a169', '#a8743f', '#6d4426'];
  const opac = [0.5, 0.6, 0.72];
  return <>{refs.slice(0, layers).map((r, L) => <instancedMesh key={L} ref={r} args={[undefined, undefined, M]} frustumCulled={false}><icosahedronGeometry args={[1, 1]} /><meshStandardMaterial color={colors[L]} transparent opacity={opac[L]} depthWrite={false} roughness={1} /></instancedMesh>)}</>;
};

/** Fast sand streaks blown along +x, thicker as `density` goes up. */
export const Streaks: React.FC<{t: number; density?: number; cz?: number}> = ({t, density = 1, cz = -40}) => {
  const ref = useRef<IM>(null);
  const d = useMemo(() => new THREE.Object3D(), []);
  const M = 240;
  useLayoutEffect(() => {
    for (let i = 0; i < M; i++) {
      const on = rnd(i + 11) < density;
      const x = ((rnd(i) * 220 - 110 + t * (40 + rnd(i + 2) * 30)) % 220) - 110, z = cz + (rnd(i + 1) - 0.5) * 120, y = terrainY(x, z) + 0.8 + rnd(i + 2) * 9;
      d.position.set(x, y, z); d.rotation.set(0, 0, 0); const s = on ? 1 : 0.0001; d.scale.set(s * (3 + rnd(i + 4) * 5), s * 0.05, s * 0.05); d.updateMatrix(); ref.current!.setMatrixAt(i, d.matrix);
    }
    ref.current!.instanceMatrix.needsUpdate = true;
  }, [t, density]);
  return <instancedMesh ref={ref} args={[undefined, undefined, M]} frustumCulled={false}><boxGeometry args={[1, 1, 1]} /><meshBasicMaterial color="#f3dcae" transparent opacity={0.55} depthWrite={false} /></instancedMesh>;
};

export const Dust: React.FC<{t: number; cz?: number}> = ({t, cz = -60}) => {
  const ref = useRef<IM>(null);
  const d = useMemo(() => new THREE.Object3D(), []);
  const M = 220;
  useLayoutEffect(() => {
    for (let i = 0; i < M; i++) {
      const x = ((rnd(i) * 140 - 70 + t * 7) % 140) - 70, z = cz + rnd(i + 1) * 90 - 45, y = terrainY(x, z) + 0.6 + rnd(i + 2) * 5;
      d.position.set(x, y, z); d.rotation.set(t + i, t * 0.5, 0); const s = 0.12 + rnd(i + 3) * 0.2; d.scale.set(s, s, s); d.updateMatrix(); ref.current!.setMatrixAt(i, d.matrix);
    }
    ref.current!.instanceMatrix.needsUpdate = true;
  }, [t]);
  return <instancedMesh ref={ref} args={[undefined, undefined, M]} frustumCulled={false}><tetrahedronGeometry args={[1, 0]} /><meshBasicMaterial color="#f3dcae" transparent opacity={0.5} depthWrite={false} /></instancedMesh>;
};
