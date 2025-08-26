#!/bin/bash

# Variables
AWS_ACCOUNT_ID="412343402708"
REGION="us-west-2"
REPO_NAME="video-verify-metadata"
CLUSTER_NAME="vv-metadata-initial-test"
SERVICE_NAME="video-verify-metadata-service"
TASK_FAMILY="video-verify-metadata-task"
SUBNET="subnet-aa7d85cd"
SECURITY_GROUP="sg-5d879824"
TARGET_GROUP_ARN="arn:aws:elasticloadbalancing:us-west-2:412343402708:targetgroup/ecs-vv-met-video-verify-metadata/e82053a5c52f1f12"

# Authenticate Docker to ECR
echo "Authenticating Docker to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Create ECR repository
echo "Creating ECR repository..."
aws ecr create-repository --repository-name $REPO_NAME --region $REGION || echo "Repository $REPO_NAME already exists"

# Clean up old images to avoid cache issues
echo "Cleaning up old images..."
docker rmi $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:flask-app $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:celery-worker 2>/dev/null || echo "No old images to remove"

# Build images with no cache for flask-app and celery-worker
echo "Building flask-app and celery-worker images..."
docker-compose build --no-cache flask-app celery-worker

# Verify images were built
if ! docker images | grep -q "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME.*flask-app"; then
  echo "Error: $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:flask-app image not found. Build failed."
  exit 1
fi
if ! docker images | grep -q "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME.*celery-worker"; then
  echo "Error: $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:celery-worker image not found. Build failed."
  exit 1
fi

# Push images to ECR
for SERVICE in "flask-app" "celery-worker"; do
  echo "Pushing $SERVICE to ECR..."
  docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:$SERVICE
done

# Register task definition
echo "Registering task definition..."
aws ecs register-task-definition --cli-input-json file://infra/ecs/task-definition.json --region $REGION

# Update ECS service
echo "Updating ECS service..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition $TASK_FAMILY \
  --force-new-deployment \
  --load-balancers "targetGroupArn=$TARGET_GROUP_ARN,containerName=flask-app,containerPort=80" \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET],securityGroups=[$SECURITY_GROUP],assignPublicIp=ENABLED}" \
  --region $REGION

echo "Deployment completed."