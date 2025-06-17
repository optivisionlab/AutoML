docker build -t hautoml-frontend .

docker-compose up -d

# docker run -it --rm -d \
# --name hautoml_frontend \
# --log-driver=json-file \
# --log-opt max-size=10m \
# --log-opt max-file=3 \
# hautoml-frontend 
