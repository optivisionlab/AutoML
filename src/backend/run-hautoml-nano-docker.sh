docker build -t hautoml-nano -f hautoml.nano.dockerfile .

docker run -it --rm --net=host \
--name hautoml_nano_v1 \
--log-opt max-size=10m --log-opt max-file=3 \
-p 80:7860 \
-d hautoml-nano python automl/demo_gradio.py
