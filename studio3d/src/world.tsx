import React, {useMemo} from 'react';
import {ThreeCanvas} from '@remotion/three';
import {useVideoConfig} from 'remotion';
import {Sky} from '@react-three/drei';
import * as THREE from 'three';

export const terrainY = (x: number, z: number) => Math.sin(x * 0.05) * 3 + Math.sin(z * 0.035 + x * 0.02) * 4 + Math.sin(x * 0.13 + z * 0.09) * 0.6;
export const rnd = (i: number) => { const s = Math.sin(i * 12.9898) * 43758.5453; return s - Math.floor(s); };

export const Dunes: React.FC<{lo?: string; hi?: string}> = ({lo = '#b9854c', hi = '#f0cf93'}) => {
  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(560, 560, 200, 200);
    g.rotateX(-Math.PI / 2);
    const p = g.attributes.position;
    const col = new Float32Array(p.count * 3);
    const a = new THREE.Color(lo), b = new THREE.Color(hi), c = new THREE.Color();
    for (let i = 0; i < p.count; i++) {
      const y = terrainY(p.getX(i), p.getZ(i)); p.setY(i, y);
      c.copy(a).lerp(b, THREE.MathUtils.clamp((y + 6) / 12, 0, 1)); col.set([c.r, c.g, c.b], i * 3);
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    g.computeVertexNormals();
    return g;
  }, [lo, hi]);
  return <mesh geometry={geo}><meshStandardMaterial vertexColors flatShading roughness={1} /></mesh>;
};

type StageProps = {fogColor?: string; fogNear?: number; fogFar: number; sun?: number; sunPos?: [number, number, number]; haze?: number; bg?: string; children: React.ReactNode};
export const Stage: React.FC<StageProps> = ({fogColor = '#e3bd86', fogNear = 40, fogFar, sun = 3.2, sunPos = [-120, 24, -80], haze = 9, bg = '#e8c48c', children}) => {
  const {width, height} = useVideoConfig();
  return (
    <ThreeCanvas width={width} height={height} camera={{fov: 44, position: [-40, 8, 26]}}>
      <color attach="background" args={[bg]} />
      <fog attach="fog" args={[fogColor, fogNear, fogFar]} />
      <Sky distance={450000} sunPosition={sunPos} turbidity={haze} rayleigh={1.6} mieCoefficient={0.012} mieDirectionalG={0.92} />
      <ambientLight intensity={0.75} color="#ffe6c0" />
      <hemisphereLight args={['#ffe2b0', '#7a4a28', 0.6]} />
      <directionalLight position={sunPos} intensity={sun} color="#ffc27a" />
      {children}
    </ThreeCanvas>
  );
};
