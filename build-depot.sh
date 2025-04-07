LATEST_COMMIT_SHA=$(git rev-parse HEAD)
depot build --push . -t fajyz/ois-gold-runpod-worker-comfy:${LATEST_COMMIT_SHA} --platform linux/amd64 --target=base
