FROM node:22-bookworm-slim AS frontend
WORKDIR /work
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RUBBER_DATA_DIR=/data PORT=8000
WORKDIR /app
COPY requirements-tested.txt ./
RUN pip install --no-cache-dir -r requirements-tested.txt && useradd --uid 10001 --user-group --create-home rubber && mkdir /data && chown rubber:rubber /data
COPY backend/ ./backend/
COPY docs/ ./docs/
COPY THIRD_PARTY_NOTICES.txt ./
COPY --from=frontend /work/dist ./frontend/dist/
COPY run.sh ./
USER rubber
EXPOSE 8000
CMD ["bash", "run.sh"]
