FROM python:3.10.12

# setup system
RUN apt-get update && apt-get install vim -y

# setup project
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 7860
ENV GRADIO_SERVER_NAME="0.0.0.0"
ENV PYTHONPATH="/app"

# CMD ["python", "automl/demo_gradio.py"]
