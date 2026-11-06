FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Tables are created on start-up; run `alembic upgrade head` instead when managing a production database.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
