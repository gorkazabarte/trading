FROM python:3.13-slim

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

WORKDIR /var/task
COPY lambda_function.py ./

ENTRYPOINT ["python3", "-m", "awslambdaric"]
CMD ["lambda_function.lambda_handler"]
