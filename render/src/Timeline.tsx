import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export type TimelineEvent = {date: string; label: string; detail?: string};
export type TimelineProps = {title: string; asOf: string; events: TimelineEvent[]; format?: 'vertical' | 'wide'; seconds?: number};

export const Timeline: React.FC<TimelineProps> = ({title, asOf, events}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const wide = width > height;
  const step = Math.floor((durationInFrames - fps * 2) / Math.max(events.length, 1));
  return (
    <AbsoluteFill style={{background: '#10161c', color: '#eef2f4', fontFamily: 'Noto Sans, sans-serif', padding: wide ? 80 : 64}}>
      <div style={{fontSize: wide ? 64 : 72, fontWeight: 700, opacity: interpolate(frame, [0, 15], [0, 1], {extrapolateRight: 'clamp'})}}>{title}</div>
      <div style={{marginTop: 40, display: 'flex', flexDirection: 'column', gap: wide ? 24 : 36}}>
        {events.map((e, i) => {
          const start = fps + i * step;
          const o = interpolate(frame, [start, start + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const x = interpolate(frame, [start, start + 12], [-40, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <div key={i} style={{opacity: o, transform: `translateX(${x}px)`, borderLeft: '8px solid #4fd1a5', paddingLeft: 24}}>
              <div style={{fontSize: 36, color: '#4fd1a5'}}>{e.date}</div>
              <div style={{fontSize: wide ? 44 : 52, fontWeight: 600}}>{e.label}</div>
              {e.detail ? <div style={{fontSize: 30, color: '#aeb9bf'}}>{e.detail}</div> : null}
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', bottom: 48, left: wide ? 80 : 64, fontSize: 26, color: '#7f8d95'}}>{asOf ? `Facts as of ${asOf}` : ''}</div>
    </AbsoluteFill>
  );
};
