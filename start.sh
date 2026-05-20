docker build -f Dockerfile.prod -t birdle .
docker run -d -p 8000:8000 birdle
