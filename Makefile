.PHONY: test test-unit test-integration test-file-operations build build-full start-fake-tus-server venv

# Virtual environment setup
venv:
	@echo "Setting up virtual environment..."
	@if [ ! -d "venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv venv; \
	fi
	@echo "Activating virtual environment and installing dependencies..."
	@bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
	@echo "Virtual environment ready!"

test: venv test-unit test-integration test-file-operations

test-unit: venv
	@bash -c "source venv/bin/activate && python -m unittest discover"

test-integration: venv
	cd tests/integration && ./run_docker_tests.sh 

test-file-operations:
	docker build --target file-operations-test -t comfyui-file-test .

build: test-file-operations
	docker build --target production -t comfyui-prod .

build-full: test-file-operations
	docker build --target final -t fajyz/ois-gold-runpod-worker-comfy:local .

start-fake-tus-server: venv
	@bash -c "source venv/bin/activate && python tests/integration/mock_tus_server.py"

tus-ngrok:
	ngrok http 1080
