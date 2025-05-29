FROM python:3.10.12

# setup system
RUN apt-get update && apt-get install vim -y

# setup project
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENV PYTHONPATH="/app"

# CMD ["python", "app.py"]
