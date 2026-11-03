ORG ?= ghcr.io/your-org
VLLM_TAG ?= 0.27.0
INIT_TAG ?= 0.1.0

.PHONY: build build-vllm build-init

build: build-vllm build-init

build-vllm:
	docker build \
	  --build-arg VLLM_VERSION=$(VLLM_TAG) \
	  -t $(ORG)/vllm-cpu:local \
	  -f docker/Dockerfile .

build-init:
	docker build \
	  -t $(ORG)/vllm-downloader:$(INIT_TAG) \
	  -f docker/Dockerfile.init .
