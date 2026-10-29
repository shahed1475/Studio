import React from 'react';
import {AbsoluteFill, Composition, interpolate, useCurrentFrame} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Cinzel';
import {Army} from './Army';
const {fontFamily} = loadFont();
const Brand: React.FC = () => {
  const f = useCurrentFrame();
  const a = interpolate(f, [10, 34, 108, 132], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const w = interpolate(f, [10, 40], [0, 360], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', padding: '0 0 74px 84px'}}>
      <div style={{opacity: a, transform: `translateY(${(1 - a) * 14}px)`}}>
        <div style={{width: w, height: 3, background: '#f1c56b', marginBottom: 14}} />
        <div style={{fontFamily, fontSize: 64, letterSpacing: 6, color: '#fff3d9', textShadow: '0 2px 18px rgba(20,10,0,.55)'}}>THE LOST ARMY</div>
        <div style={{fontFamily, fontSize: 26, letterSpacing: 8, color: '#f1c56b', marginTop: 6}}>525 BC  ·  WESTERN DESERT</div>
      </div>
    </AbsoluteFill>
  );
};
const Full: React.FC = () => <AbsoluteFill><Army /><Brand /></AbsoluteFill>;
export const Root: React.FC = () => <Composition id="Army" component={Full} durationInFrames={144} fps={24} width={1280} height={720} />;
