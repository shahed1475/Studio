import React, {useLayoutEffect} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {useThree} from '@react-three/fiber';
import * as THREE from 'three';
import {Dunes, Stage, terrainY} from './world';
import {Camels, Palms, Soldiers, Temple, camelPath} from './actors';
import {Dust, Streaks, StormWall} from './weather';
import {Overlay} from './Overlay';

const Rig: React.FC<{pos: [number, number, number]; look: [number, number, number]; fov?: number}> = ({pos, look, fov = 44}) => {
  const {camera} = useThree();
  useLayoutEffect(() => { camera.position.set(...pos); camera.lookAt(...look); (camera as THREE.PerspectiveCamera).fov = fov; camera.updateProjectionMatrix(); }, [pos[0], pos[1], pos[2], look[0], look[1], look[2], camera]);
  return null;
};
const useT = () => { const f = useCurrentFrame(); const {fps, durationInFrames: n} = useVideoConfig(); return {t: f / fps, k: f / (n - 1), f, n}; };
const ease = (k: number) => k * k * (3 - 2 * k);

/** 1. March: a column crosses the dunes at golden hour while a dust wall waits on the horizon; the camera drifts beside it and rises. */
export const March: React.FC = () => {
  const {t, k} = useT();
  const cz = 22 - t * 3, e = ease(k);  // the middle of the column (it is about 58 deep and starts at z -6)
  return (
    <AbsoluteFill>
      <Stage fogFar={interpolate(k, [0, 1], [260, 150])} sunPos={[-120, 14, -80]}>
        <Rig pos={[-46 + e * 14, 7 + e * 9, cz + 24 - e * 10]} look={[-13, 3.5, cz]} />
        <Dunes />
        <Soldiers t={t} ox={-18} oz={-6} n={204} cols={12} />
        <Dust t={t} cz={cz} />
        <StormWall t={t} frontZ={-205 + t * 3} />
      </Stage>
      <Overlay title="THE MARCH" sub="525 BC  ·  WESTERN DESERT" />
    </AbsoluteFill>
  );
};

/** 2. Caravan: an aerial move forward over a line of camels toward a temple in an oasis. */
export const Caravan: React.FC = () => {
  const {t, k} = useT();
  const e = ease(k);
  const cz = 30 - e * 120;
  return (
    <AbsoluteFill>
      <Stage fogFar={420} fogColor="#ecc78f" sunPos={[-90, 30, -120]} haze={7}>
        <Rig pos={[camelPath(cz) - 26 + e * 10, 22 - e * 9, 62 - e * 90]} look={[camelPath(cz - 60) + 3, 5, cz - 70]} fov={46} />
        <Dunes />
        <Camels t={t} />
        <Temple x={0} z={-205} />
        <Palms cx={4} cz={-185} />
        <Dust t={t} cz={-80} />
      </Stage>
      <Overlay title="THE CARAVAN" sub="THE ROAD TO SIWA" />
    </AbsoluteFill>
  );
};

/** 3. Storm: the column marches away from the camera into a wall that grows, darkens the light and swallows it. */
export const Storm: React.FC = () => {
  const {t, k} = useT();
  const front = -95 + t * 11;
  const dark = interpolate(k, [0.3, 1], [0, 1], {extrapolateLeft: 'clamp'});
  return (
    <AbsoluteFill>
      <Stage fogColor={dark > 0.5 ? '#a8743f' : '#d9b27c'} fogNear={30} fogFar={interpolate(k, [0, 1], [230, 55])} sun={interpolate(k, [0, 1], [3.0, 0.9])} sunPos={[-100, 16 - dark * 8, -60]} haze={interpolate(k, [0, 1], [9, 20])} bg={dark > 0.5 ? '#a8743f' : '#d9b27c'}>
        <Rig pos={[-4 + t * 0.3, 6 - k * 1.5, 64 - t * 2.2]} look={[0, 5, -60 - t * 2]} fov={50} />
        <Dunes />
        <Soldiers t={t} ox={-18} oz={-6} n={192} cols={12} speed={3.0} />
        <StormWall t={t} frontZ={front} />
        <Streaks t={t} density={interpolate(k, [0, 1], [0.15, 1])} cz={-30 - t * 2} />
        <Dust t={t} cz={-30} />
      </Stage>
      <Overlay title="THE STORM" sub="THEY WERE NEVER SEEN AGAIN" />
    </AbsoluteFill>
  );
};
