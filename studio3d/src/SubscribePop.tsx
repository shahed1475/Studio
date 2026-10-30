import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Cinzel';
import {BRAND} from './brand';
const {fontFamily} = loadFont('normal', {weights: ['700'], subsets: ['latin']});

const CLICK = 46;  // frame of the click
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const Bell: React.FC<{color: string; angle: number}> = ({color, angle}) => (
  <svg width="46" height="46" viewBox="0 0 24 24" style={{transform: `rotate(${angle}deg)`, transformOrigin: '50% 8%'}}>
    <path d="M12 2.5a1.6 1.6 0 0 1 1.6 1.6v.5c2.6.7 4.4 3 4.4 5.8v3.7l1.6 2.4a.9.9 0 0 1-.8 1.4H5.2a.9.9 0 0 1-.8-1.4L6 13.6V9.9c0-2.8 1.8-5.1 4.4-5.8v-.5A1.6 1.6 0 0 1 12 2.5Zm-2.2 16.2h4.4a2.2 2.2 0 0 1-4.4 0Z" fill={color} />
  </svg>
);
const Check: React.FC<{color: string}> = ({color}) => (
  <svg width="34" height="34" viewBox="0 0 24 24"><path d="M5 12.8l4.4 4.4L19 7.6" fill="none" stroke={color} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
);
const Cursor: React.FC = () => (
  <svg width="44" height="44" viewBox="0 0 24 24"><path d="M5 3l14 8.2-6.1 1.5 3.4 6.3-2.6 1.4-3.4-6.3L5 18.6z" fill="#fff" stroke="#0b0f2a" strokeWidth="1.4" strokeLinejoin="round" /></svg>
);

/** A branded subscribe reminder, 86 frames at 24 fps on a transparent background: pop in, shine, a cursor clicks, it turns into "Subscribed" and the bell rings, it leaves. */
export const SubscribePop: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame: f, fps, config: {damping: 11, stiffness: 150, mass: 0.7}});
  const enter = interpolate(pop, [0, 1], [0.55, 1]);
  const fade = interpolate(f, [0, 5, 76, 85], [0, 1, 1, 0], clamp);
  const exitX = interpolate(f, [76, 85], [0, 60], clamp);
  const done = f >= CLICK;
  const press = interpolate(f, [CLICK - 1, CLICK + 1, CLICK + 4], [1, 0.95, 1], clamp);
  const shine = interpolate(f, [12, 30], [-240, 640], clamp);
  const ripple = interpolate(f, [CLICK, CLICK + 14], [0, 1], clamp);
  const out3 = (t: number) => 1 - Math.pow(1 - t, 3);
  const curX = interpolate(f, [26, CLICK], [560, 300], {...clamp, easing: out3});  // in the button's own box (520 x 108): from outside its lower right to the middle of the word
  const curY = interpolate(f, [26, CLICK], [150, 62], {...clamp, easing: out3});
  const curOp = interpolate(f, [26, 30, CLICK + 6, CLICK + 14], [0, 1, 1, 0], clamp);
  const swing = done ? Math.sin((f - CLICK) * 0.9) * 22 * Math.exp(-(f - CLICK) * 0.07) : 0;
  const bg = done ? BRAND.night : 'linear-gradient(180deg,#f8d684 0%,#e8b552 100%)';
  const ink = done ? BRAND.gold : BRAND.night;
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <div style={{position: 'relative', width: 520, height: 108, opacity: fade, transform: `translateX(${exitX}px) scale(${enter * press})`}}>
        <div style={{position: 'absolute', inset: 0, borderRadius: 54, background: bg, border: done ? `3px solid ${BRAND.gold}` : '3px solid rgba(255,241,212,0.9)', boxShadow: '0 10px 28px rgba(11,15,42,0.55)', overflow: 'hidden'}}>
          {!done && <div style={{position: 'absolute', top: 0, bottom: 0, width: 90, left: shine, background: 'linear-gradient(110deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.65) 50%, rgba(255,255,255,0) 100%)', transform: 'skewX(-18deg)'}} />}
          <div style={{position: 'absolute', left: 12, top: 12, width: 84, height: 84, borderRadius: 42, background: BRAND.night, display: 'flex', alignItems: 'center', justifyContent: 'center', border: `2px solid ${done ? 'rgba(242,196,109,0.5)' : 'rgba(242,196,109,0.9)'}`}}>
            <Img src={staticFile('mark.png')} style={{width: 62, height: 62}} />
          </div>
          <div style={{position: 'absolute', left: 112, right: 78, top: 0, bottom: 0, display: 'flex', alignItems: 'center', gap: 12, fontFamily, fontWeight: 700, fontSize: done ? 32 : 38, letterSpacing: 4, color: ink, whiteSpace: 'nowrap'}}>
            {done && <Check color={ink} />}
            {done ? 'SUBSCRIBED' : 'SUBSCRIBE'}
          </div>
          <div style={{position: 'absolute', right: 22, top: 31}}><Bell color={ink} angle={swing} /></div>
          {ripple > 0 && ripple < 1 && <div style={{position: 'absolute', left: 304 - (30 + 150 * ripple), top: 66 - (30 + 150 * ripple), width: 60 + 300 * ripple, height: 60 + 300 * ripple, borderRadius: '50%', border: `4px solid rgba(255,241,212,${0.8 * (1 - ripple)})`}} />}
        </div>
        <div style={{position: 'absolute', left: curX, top: curY, opacity: curOp}}><Cursor /></div>
      </div>
    </AbsoluteFill>
  );
};
