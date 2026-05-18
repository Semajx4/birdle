docker build -f Dockerfile.prod -t birdle .
docker run -p 8000:8000 birdle
