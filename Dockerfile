FROM node:22-alpine AS node

WORKDIR /app

COPY web ./web

RUN cd web && npm install && npx vite build

FROM python:3.12.7-slim

WORKDIR /app

COPY . .

COPY --from=node /app/web/dist ./web/dist
COPY deploy/render/start.sh /app/deploy/render/start.sh

COPY data ./render-seed-data
COPY deploy/render/start.sh /app/deploy/render/start.sh

RUN apt update \
    && apt install gcc curl unzip -y \
    && python -m pip install --no-cache-dir uv \
    && uv sync \
    && chmod +x /app/deploy/render/start.sh \
    && touch /.dockerenv

CMD [ "/app/deploy/render/start.sh" ]
