#!/bin/bash
set -e

IMAGE_NAME=webcloud7/keycloak-test
IMAGE_TAG=22.0.2.1

docker buildx build --platform linux/amd64,linux/arm64 --no-cache -t $IMAGE_NAME:$IMAGE_TAG -f ./Dockerfile --push .
