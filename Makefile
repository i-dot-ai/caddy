-include .env
export

run_model_locally:
	./.venv/bin/python -m uvicorn api.app:app --reload

pre-commit-install:
	pre-commit install

build_model:
	make docker_login_public && \
	docker compose build

.PHONY: generate_aws_diagram
generate_aws_diagram:
	cd model && poetry run python ../terraform/diagram_script.py

run_model:
	cd model && docker compose up -d --wait

run_backend:
	cd model && poetry run python -m uvicorn api.app:app --reload

run_tests:
	docker compose up -d qdrant postgres minio --wait && \
	cd model && poetry install && poetry run pytest --cov=tests -v --cov-report=term-missing --cov-fail-under=60

setup_local_postgres:
	psql -f model/scripts/postgres-init.sql

run:
	# will run with local client by default
	docker compose -f docker-compose.yaml -f docker-compose-config/local-client.yaml up

stop:
	docker compose down

model_run_evals:
	@cd model && echo "Running all evaluation scripts..."
	@cd model && find evals -name "eval_*.py" -exec poetry run python {} \;

model_run_backend:
	@ cd model && poetry run uvicorn api.app:app --host 0.0.0.0 --port 7001 --reload --log-level debug

model_run_streamlit:
	@ cd model && poetry run streamlit run streamlit_app.py --server.address 0.0.0.0

model_run_dev:
	@make model_run_backend & make model_run_streamlit

model_run_tests:
	echo "Running model tests..." && \
	cd model && poetry run pytest -vv --cov=tests -v --cov-report=term-missing --cov-fail-under=60

scraper_run:
	@cd scraper && poetry run python run_scrape.py

# Docker
REPO_POSTFIX = $(if $(findstring /,$(service)),$(notdir $(service)),$(service))

ECR_REPO_NAME=$(APP_NAME)-$(REPO_POSTFIX)
ECR_URL=$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
ECR_REPO_URL=$(ECR_URL)/$(ECR_REPO_NAME)

IMAGE_TAG=$$(git rev-parse HEAD)
IMAGE=$(ECR_REPO_URL):$(IMAGE_TAG)

PUBLIC_ECR_URL=public.ecr.aws
PUBLIC_ECR_REPO_URL=$(PUBLIC_ECR_URL)/idotai
PUBLIC_IMAGE=$(PUBLIC_ECR_REPO_URL)/$(ECR_REPO_NAME):$(VERSION)

DOCKER_BUILDER_CONTAINER=$(APP_NAME)

docker_login:
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_URL)

ifndef cache
	override cache = ./.build-cache
endif

docker_login_public:
	aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(PUBLIC_ECR_URL)

docker_build: ## Build the docker container for the specified service when running in CI/CD
	DOCKER_BUILDKIT=1 docker buildx build --platform linux/amd64 --load --builder=$(DOCKER_BUILDER_CONTAINER) -t $(IMAGE) \
	--cache-to type=local,dest=$(cache) \
	--cache-from type=local,src=$(cache) -f $(service)/Dockerfile $(service) # where service is the dirname of the component, like "model"

docker_build_public_image: ## Build the docker container for the specified service when running in CI/CD
	DOCKER_BUILDKIT=1 docker buildx build --platform linux/amd64 --load --builder=$(DOCKER_BUILDER_CONTAINER) -t $(PUBLIC_IMAGE) \
	--cache-to type=local,dest=$(cache) \
	--cache-from type=local,src=$(cache) -f $(service)/Dockerfile frontend/

docker_build_local: ## Build the docker container for the specified service locally
	DOCKER_BUILDKIT=1 docker build --platform=linux/amd64 -t $(IMAGE) -f $(service)/Dockerfile .

docker_push:
	docker push $(IMAGE)

docker_push_public_ecr:
	docker push $(PUBLIC_IMAGE)
	
docker_tag_is_present_on_image:
	aws ecr describe-images --repository-name $(repo) --image-ids imageTag=$(IMAGE_TAG) --query 'imageDetails[].imageTags' | jq -e '.[]|any(. == "$(tag)")' >/dev/null

docker_update_tag: ## Tag the docker image with the specified tag
	# repo and tag variable are set from git-hub core workflow. example: repo=ecr-repo-name, tag=dev
	if make docker_tag_is_present_on_image 2>/dev/null; then echo "Image already tagged with $(tag)" && exit 0; fi && \
	MANIFEST=$$(aws ecr batch-get-image --repository-name $(repo) --image-ids imageTag=$(IMAGE_TAG) --query 'images[].imageManifest' --output text) && \
	aws ecr put-image --repository-name $(repo) --image-tag $(tag) --image-manifest "$$MANIFEST"

docker_echo:
	echo $($(value))

## Terraform 

ifndef env
override env = default
endif
workspace = $(env)
CONFIG_DIR=../../caddy-infra-config
tf_build_args =-var "image_tag=$(IMAGE_TAG)" -var-file="$(CONFIG_DIR)/global.tfvars" -var-file="$(CONFIG_DIR)/$(env).tfvars"  
TF_BACKEND_CONFIG=$(CONFIG_DIR)/backend.hcl



AUTO_APPLY_RESOURCES = module.model.aws_ecs_service.aws-ecs-service \
  					   module.model.data.aws_ecs_task_definition.main \
					   module.model.aws_ecs_task_definition.task_definition \
					   module.frontend.aws_ecs_service.aws-ecs-service \
  					   module.frontend.data.aws_ecs_task_definition.main \
					   module.frontend.aws_ecs_task_definition.task_definition \
					   module.load_balancer.aws_security_group.load_balancer_security_group \
					   module.load_balancer.aws_security_group_rule.load_balancer_https_whitelist


auto_apply_target_resources = $(foreach resource,$(AUTO_APPLY_RESOURCES),-target $(resource))

tf_set_workspace:
	terraform -chdir=terraform/ workspace select $(workspace)

tf_new_workspace:
	terraform -chdir=terraform/ workspace new $(workspace)

tf_set_or_create_workspace:
	make tf_set_workspace || make tf_new_workspace

tf_init_and_set_workspace:
	make tf_init && make tf_set_workspace

.PHONY: tf_init
tf_init:
	terraform -chdir=./terraform/ init \
		-backend-config=$(TF_BACKEND_CONFIG) \
		-backend-config="dynamodb_table=i-dot-ai-$(env)-dynamo-lock" \
		-reconfigure \

.PHONY: tf_fmt
tf_fmt:
	terraform fmt

.PHONY: tf_plan
tf_plan:
	make tf_init_and_set_workspace && \
	terraform -chdir=./terraform/ plan -var-file=$(CONFIG_DIR)/${env}.tfvars ${tf_build_args} ${args}

.PHONY: tf_apply
tf_apply:
	make tf_init_and_set_workspace && \
	terraform -chdir=./terraform/ apply -var-file=$(CONFIG_DIR)/${env}.tfvars ${tf_build_args} ${args}

.PHONY: tf_auto_apply
tf_auto_apply: ## Auto apply terraform
	make tf_init_and_set_workspace && \
	terraform -chdir=./terraform/ apply  -var-file=$(CONFIG_DIR)/${env}.tfvars ${tf_build_args} $(auto_apply_target_resources) ${args} -auto-approve

## Release app
.PHONY: release
release: 
	chmod +x ./release.sh && ./release.sh $(env)


