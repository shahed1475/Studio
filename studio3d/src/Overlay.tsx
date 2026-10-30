import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Cinzel';
import {BRAND} from './brand';
const {fontFamily} = loadFont('normal', {weights: ['500', '700'], subsets: ['latin']});

export const Overlay: React.FC<{title: string; sub: string}> = ({title, sub}) => {
  const f = useCurrentFrame();
  const {durationInFrames: n} = useVideoConfig();
  const a = interpolate(f, [8, 30, n - 36, n - 10], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const w = interpolate(f, [8, 36], [0, 300], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 22% 38%, rgba(255,214,150,0.20), rgba(255,214,150,0) 46%), radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 52%, rgba(11,15,42,0.58) 100%)'}} />
      <AbsoluteFill style={{background: 'linear-gradient(to top right, rgba(11,15,42,0.78) 0%, rgba(11,15,42,0.35) 32%, rgba(11,15,42,0) 55%)', opacity: a}} />
      <AbsoluteFill style={{justifyContent: 'flex-end', padding: '0 0 56px 64px'}}>
        <div style={{opacity: a, transform: `translateY(${(1 - a) * 12}px)`}}>
          <div style={{width: w, height: 3, background: BRAND.gold, marginBottom: 12}} />
          <div style={{fontFamily, fontWeight: 700, fontSize: 54, letterSpacing: 5, color: BRAND.cream, textShadow: '0 2px 16px rgba(11,15,42,.7)'}}>{title}</div>
          <div style={{fontFamily, fontWeight: 500, fontSize: 22, letterSpacing: 6, color: BRAND.gold, marginTop: 6}}>{sub}</div>
        </div>
      </AbsoluteFill>
      <div style={{position: 'absolute', top: 30, left: 40, display: 'flex', alignItems: 'center', gap: 12, opacity: 0.92}}>
        <Img src={staticFile('mark.png')} style={{width: 54, height: 54}} />
        <div style={{fontFamily, fontWeight: 700, fontSize: 22, letterSpacing: 5, color: BRAND.cream, textShadow: '0 1px 8px rgba(11,15,42,.8)'}}>{BRAND.name}</div>
      </div>
    </AbsoluteFill>
  );
};
