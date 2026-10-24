# One-template render test for Story Studio (Remotion spike). Own container, no secrets, no studio code. Run with --memory 2g --cpus 2.
FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg bc ca-certificates fonts-noto-core libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libasound2 libxrandr2 libxkbcommon-x11-0 libxfixes3 libxcomposite1 libxdamage1 libgbm1 libcups2 libcairo2 libpango-1.0-0 libxshmfence1 \
 && apt-get clean
WORKDIR /render
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY tsconfig.json ./
COPY src ./src
COPY examples ./examples
COPY measure.sh ./
RUN npx remotion browser ensure
CMD ["bash", "measure.sh"]
