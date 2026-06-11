# Multi-stage build: frontend -> static files served by FastAPI.
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
# vite.config builds to ../backend/static; override outDir for container layout
RUN npx vite build --outDir /static --emptyOutDir

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /static ./static
# Pipeline diagram, linked from the README (GitHub renders .html as source)
COPY docs/app-flow.html ./static/docs/app-flow.html
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
