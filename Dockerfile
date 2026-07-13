# Small, non-root, healthchecked image (see Beginner 01 for the line-by-line).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # deps first -> better layer caching
COPY main.py .
COPY static ./static
EXPOSE 8080
RUN useradd -u 10001 app && chown -R app /app         # run as non-root
USER app
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8080/healthz')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
