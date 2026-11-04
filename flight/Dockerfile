FROM python:3.12-slim

WORKDIR /app

COPY flight/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flight.proto .
RUN mkdir generated && python -m grpc_tools.protoc -I . --python_out=generated --grpc_python_out=generated flight.proto

COPY flight/*.py .

ENV PYTHONPATH=/app:/app/generated
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
