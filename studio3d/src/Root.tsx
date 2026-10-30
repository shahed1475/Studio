import React from 'react';
import {Composition} from 'remotion';
import {Caravan, March, Storm} from './scenes';
import {FPS, SIZE} from './brand';
import {SubscribePop} from './SubscribePop';
export const Root: React.FC = () => (
  <>
    <Composition id="March" component={March} durationInFrames={FPS * 6} fps={FPS} {...SIZE} />
    <Composition id="Caravan" component={Caravan} durationInFrames={FPS * 8} fps={FPS} {...SIZE} />
    <Composition id="Storm" component={Storm} durationInFrames={FPS * 8} fps={FPS} {...SIZE} />
    <Composition id="SubscribePop" component={SubscribePop} durationInFrames={86} fps={FPS} width={640} height={200} />
  </>
);
