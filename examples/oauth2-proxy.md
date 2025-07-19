# Blast Radius with OAuth2 Proxy Example

This example shows how to deploy Blast Radius with OAuth2 Proxy for authentication.

## OAuth2 Proxy Configuration

Create a separate OAuth2 Proxy deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oauth2-proxy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: oauth2-proxy
  template:
    metadata:
      labels:
        app: oauth2-proxy
    spec:
      containers:
      - name: oauth2-proxy
        image: quay.io/oauth2-proxy/oauth2-proxy:v7.4.0
        args:
        - --provider=github
        - --email-domain=*
        - --upstream=http://blast-radius:80
        - --http-address=0.0.0.0:4180
        - --cookie-secure=true
        - --cookie-domain=.yourdomain.com
        env:
        - name: OAUTH2_PROXY_CLIENT_ID
          valueFrom:
            secretKeyRef:
              name: oauth2-proxy-secret
              key: client_id
        - name: OAUTH2_PROXY_CLIENT_SECRET
          valueFrom:
            secretKeyRef:
              name: oauth2-proxy-secret
              key: client_secret
        - name: OAUTH2_PROXY_COOKIE_SECRET
          valueFrom:
            secretKeyRef:
              name: oauth2-proxy-secret
              key: cookie_secret
        ports:
        - containerPort: 4180
---
apiVersion: v1
kind: Service
metadata:
  name: oauth2-proxy
spec:
  selector:
    app: oauth2-proxy
  ports:
  - port: 4180
    targetPort: 4180
---
apiVersion: v1
kind: Secret
metadata:
  name: oauth2-proxy-secret
type: Opaque
stringData:
  client_id: "your-github-oauth-app-client-id"
  client_secret: "your-github-oauth-app-client-secret"
  cookie_secret: "your-32-char-random-string"  # Generate with: openssl rand -base64 32
```

## Ingress with OAuth2 Proxy

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: blast-radius-auth
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - blast-radius.yourdomain.com
    secretName: blast-radius-tls
  rules:
  - host: blast-radius.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: oauth2-proxy
            port:
              number: 4180
```

## Deployment with OAuth2 Proxy

Deploy both Blast Radius and OAuth2 Proxy:

```bash
# Deploy Blast Radius without direct ingress
helm install blast-radius ./helm/blast-radius \
  --set aws.roleArn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/BlastRadiusRole" \
  --set s3.bucket="${S3_BUCKET_NAME}" \
  --set s3.region="us-east-1" \
  --set ingress.enabled=false

# Deploy OAuth2 Proxy
kubectl apply -f oauth2-proxy.yaml
kubectl apply -f ingress-with-oauth2.yaml
```

This setup provides:
- GitHub OAuth authentication
- Secure cookie-based sessions  
- TLS termination
- Protection for the entire Blast Radius application