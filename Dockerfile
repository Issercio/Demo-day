FROM python:3.12-slim

WORKDIR /app
COPY Demoday/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY Demoday /app
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} run:app"]
