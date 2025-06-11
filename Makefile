.PHONY: test test-unit test-integration test-file-operations build build-full start-fake-tus-server

test: test-unit test-integration test-file-operations

test-unit:
	python -m unittest discover

test-integration:
	cd tests/integration && ./run_docker_tests.sh 

test-file-operations:
	docker build --target file-operations-test -t comfyui-file-test .

build: test-file-operations
	docker build --target production -t comfyui-prod .

build-full: test-file-operations
	docker build --target final -t fajyz/ois-gold-runpod-worker-comfy:local .

start-fake-tus-server:
	python tests/integration/mock_tus_server.py

tus-ngrok:
	ngrok http 1080
