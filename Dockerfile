# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY prototype/ ./prototype/
COPY docs/pitch/pitch-deck.html ./docs/pitch/pitch-deck.html

# Create data and model directories
RUN mkdir -p prototype/data prototype/models prototype/static

# Copy static assets
COPY prototype/static/ ./prototype/static/

EXPOSE 5050

# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--timeout", "120", "--workers", "2", "--chdir", "prototype", "app:app"]
