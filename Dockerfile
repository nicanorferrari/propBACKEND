
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Renombrar archivos .txt a .py recursivamente para que FastAPI pueda importar los módulos en subcarpetas
RUN find . -name "*.txt" -exec sh -c 'mv "$1" "${1%.txt}.py"' _ {} \;

EXPOSE 80

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
