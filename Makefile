.PHONY: test test-unit test-integration start-fake-tus-server

test: test-unit test-integration

test-unit:
	python -m unittest discover

test-integration:
	cd tests/integration && ./run_docker_tests.sh 

start-fake-tus-server:
	python tests/integration/mock_tus_server.py & \
	ngrok http 1080 