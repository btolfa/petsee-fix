# Автономный прокси-корректор координат трекера apptrackpets.
# Только stdlib — никаких зависимостей, минимальный образ.
FROM python:3.12-slim

WORKDIR /app
COPY src/ ./src/

# Непривилегированный пользователь
RUN useradd --no-create-home --uid 10001 petsee
USER petsee

ENV LISTEN=0.0.0.0:5455 \
    UPSTREAM=apptrackpets.com:5455 \
    PYTHONUNBUFFERED=1

EXPOSE 5455

ENTRYPOINT ["python3", "src/proxy.py"]
