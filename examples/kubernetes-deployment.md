# Blast Radius Kubernetes Deployment Example

This directory contains example configurations for deploying Blast Radius on Kubernetes with AWS IRSA and S3 integration.

## Prerequisites

1. **EKS Cluster** with OIDC provider enabled
2. **S3 Bucket** containing Terraform state files
3. **IAM Role** with S3 read permissions configured for IRSA

## Setup Steps

### 1. Create IAM Role for IRSA

```bash
# Create IAM policy for S3 access
aws iam create-policy \
  --policy-name BlastRadiusS3Policy \
  --policy-document file://s3-policy.json

# Create IAM role with OIDC trust relationship
aws iam create-role \
  --role-name BlastRadiusRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policy to role
aws iam attach-role-policy \
  --role-name BlastRadiusRole \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT:policy/BlastRadiusS3Policy
```

### 2. Deploy with Helm

```bash
# Add values for your deployment
helm install blast-radius ./helm/blast-radius \
  --set aws.roleArn="arn:aws:iam::YOUR_ACCOUNT:role/BlastRadiusRole" \
  --set s3.bucket="your-terraform-state-bucket" \
  --set s3.region="us-east-1" \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host="blast-radius.your-domain.com"
```

### 3. Access the Application

Once deployed, access Blast Radius through the ingress or port-forward:

```bash
kubectl port-forward service/blast-radius 8080:80
```

Then open http://localhost:8080

## Configuration Options

See the `values.yaml` file for all available configuration options including:
- Resource limits
- Ingress configuration
- OAuth2 proxy integration
- Node selection and tolerations