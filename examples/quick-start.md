# Blast Radius Kubernetes Quick Start

This guide helps you quickly deploy Blast Radius on Kubernetes with S3 integration.

## Prerequisites

1. **EKS Cluster** with OIDC provider enabled
2. **S3 Bucket** containing Terraform state files
3. **Helm 3.x** installed
4. **kubectl** configured for your cluster

## Quick Deployment

### 1. Create IAM Role for IRSA

```bash
# Replace with your values
export AWS_ACCOUNT_ID="123456789012"
export EKS_CLUSTER_NAME="my-cluster"
export S3_BUCKET_NAME="my-terraform-states"

# Get OIDC issuer URL
export OIDC_ISSUER=$(aws eks describe-cluster --name $EKS_CLUSTER_NAME --query "cluster.identity.oidc.issuer" --output text | sed 's|https://||')

# Create IAM policy
cat > blast-radius-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET_NAME}",
        "arn:aws:s3:::${S3_BUCKET_NAME}/*"
      ]
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name BlastRadiusS3Policy \
  --policy-document file://blast-radius-policy.json

# Create trust policy
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_ISSUER}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "${OIDC_ISSUER}:sub": "system:serviceaccount:default:blast-radius",
          "${OIDC_ISSUER}:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name BlastRadiusRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policy to role
aws iam attach-role-policy \
  --role-name BlastRadiusRole \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/BlastRadiusS3Policy
```

### 2. Deploy with Helm

```bash
# Clone the repository
git clone https://github.com/nkbud/blast-radius.git
cd blast-radius

# Deploy with Helm
helm install blast-radius ./helm/blast-radius \
  --set aws.roleArn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/BlastRadiusRole" \
  --set s3.bucket="${S3_BUCKET_NAME}" \
  --set s3.region="us-east-1"
```

### 3. Access the Application

```bash
# Port forward to access locally
kubectl port-forward service/blast-radius 8080:80

# Open in browser
open http://localhost:8080
```

## With Ingress (Production)

For production deployment with ingress:

```bash
helm install blast-radius ./helm/blast-radius \
  --set aws.roleArn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/BlastRadiusRole" \
  --set s3.bucket="${S3_BUCKET_NAME}" \
  --set s3.region="us-east-1" \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host="blast-radius.yourdomain.com" \
  --set ingress.hosts[0].paths[0].path="/" \
  --set ingress.hosts[0].paths[0].pathType="Prefix" \
  --set ingress.annotations."kubernetes\.io/ingress\.class"="nginx" \
  --set ingress.annotations."cert-manager\.io/cluster-issuer"="letsencrypt-prod"
```

## Viewing State Files

Once deployed, you can:

1. **List available state files**: `GET /api/s3/states`
2. **View a specific state**: Add `?s3_key=path/to/state.tfstate` to the main page
3. **Force refresh**: `POST /api/s3/refresh`

## Troubleshooting

### Check pod status
```bash
kubectl get pods -l app.kubernetes.io/name=blast-radius
kubectl logs -l app.kubernetes.io/name=blast-radius
```

### Verify IRSA configuration
```bash
kubectl describe serviceaccount blast-radius
```

### Test S3 access
```bash
kubectl exec -it deployment/blast-radius -- python3 -c "
import boto3
s3 = boto3.client('s3')
print('S3 client created successfully')
print('Buckets:', [b['Name'] for b in s3.list_buckets()['Buckets']][:5])
"
```

For more detailed configuration options, see the [examples/](../examples/) directory.