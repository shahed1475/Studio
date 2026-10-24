import React from 'react';
import {Composition} from 'remotion';
import {Timeline, TimelineProps} from './Timeline';

const FPS = 30;

export const Root: React.FC = () => (
  <Composition
    id="Timeline"
    component={Timeline}
    fps={FPS}
    width={1080}
    height={1920}
    durationInFrames={300}
    defaultProps={{title: 'Example', asOf: '', events: []} as TimelineProps}
    calculateMetadata={({props}) => {
      const wide = props.format === 'wide';
      return {width: wide ? 1920 : 1080, height: wide ? 1080 : 1920, durationInFrames: Math.round((props.seconds ?? 10) * FPS)};
    }}
  />
);
