FROM python:3.10.12

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 7860
ENV GRADIO_SERVER_NAME="0.0.0.0"

CMD ["python", "automl/demo_gradio.py"]