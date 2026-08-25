docker build -f Dockerfile.prod -t birdle .
docker rm -f birdle 2>/dev/null
docker run -d -p 8000:8000 --name birdle birdle
