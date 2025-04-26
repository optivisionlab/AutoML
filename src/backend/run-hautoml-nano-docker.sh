docker build -t hautoml-nano -f hautoml.nano.dockerfile .

docker run -it --rm --net=host \
--name hautoml_nano_v1 \
-v $(pwd):/app \
--log-opt max-size=10m --log-opt max-file=3 \
-p 7860:7860 \
-d hautoml-nano python automl/demo_gradio.py
