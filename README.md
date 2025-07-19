# Blast Radius

[![CircleCI](https://circleci.com/gh/28mm/blast-radius/tree/master.svg?style=svg)](https://circleci.com/gh/28mm/blast-radius/tree/master)
[![PyPI version](https://badge.fury.io/py/BlastRadius.svg)](https://badge.fury.io/py/BlastRadius)

[terraform]: https://www.terraform.io/
[examples]: https://28mm.github.io/blast-radius-docs/

_Blast Radius_ is a tool for reasoning about [Terraform][] dependency graphs
with interactive visualizations. Now enhanced with Kubernetes support, S3 integration,
and advanced state file processing capabilities.

Use _Blast Radius_ to:

* __Learn__ about *Terraform* or one of its providers through real [examples][]
* __Document__ your infrastructure  
* __Reason__ about relationships between resources and evaluate changes to them
* __Interact__ with the diagram below (and many others) [in the docs][examples]
* __Browse__ and visualize Terraform state files from S3 or local uploads
* __Deploy__ as a production-ready Kubernetes application

![screenshot](doc/blastradius-interactive.png)

## ✨ What's New

### 🔗 **S3 Integration & State Processing**
- Read and visualize Terraform state files directly from S3 buckets
- Enhanced state-to-graph conversion with comprehensive dependency detection
- Upload local `.tfstate` files for instant visualization
- Thread-safe processing with automatic caching

### ☸️ **Kubernetes Native**
- Complete Helm chart with production-ready defaults
- IRSA integration for secure AWS authentication
- Health check endpoints and proper lifecycle management

### 🎯 **Enhanced Browsing**
- Interactive dropdown to browse S3 state files
- File upload interface for local state files
- Real-time graph generation and caching
- Detailed file metadata and information

[📖 **Enhanced State Processing Guide**](doc/enhanced-state-processing.md)

![screenshot](doc/blastradius-interactive.png)

## Prerequisites

* [Graphviz](https://www.graphviz.org/)
* [Python](https://www.python.org/) 3.7 or newer

> __Note:__ For macOS you can `brew install graphviz`

## Quickstart

### Traditional Local Mode
The fastest way to get up and running with *Blast Radius* is to install it with
`pip` to your pre-existing environment:

```sh
pip install blastradius
```

Once installed just point *Blast Radius* at any initialized *Terraform*
directory:

```sh
blast-radius --serve /path/to/terraform/directory
```

And you will shortly be rewarded with a browser link http://127.0.0.1:5000/.

### ⚡ New: State File Processing

**Process any `.tfstate` file directly** (no terraform CLI required):

1. **Upload via Web UI**: Start the server and click "Upload State" to select your `.tfstate` file
2. **Via API**: 
   ```bash
   curl -X POST -F "state_file=@terraform.tfstate" \
     http://localhost:5000/api/state/process?format=svg
   ```

### ☁️ New: S3 Integration

**Visualize state files from S3 buckets**:

```bash
# Set environment variables
export S3_BUCKET=my-terraform-states
export S3_REGION=us-east-1

# Start server - automatically detects S3 mode
blast-radius --serve
```

Then browse available state files via the dropdown menu in the web interface.

## Docker

[privileges]: https://docs.docker.com/engine/reference/run/#runtime-privilege-and-linux-capabilities
[overlayfs]: https://wiki.archlinux.org/index.php/Overlay_filesystem

To launch *Blast Radius* for a local directory by manually running:

```sh
docker run --rm -it -p 5000:5000 \
  -v $(pwd):/data:ro \
  --security-opt apparmor:unconfined \
  --cap-add=SYS_ADMIN \
  28mm/blast-radius
```

A slightly more customized variant of this is also available as an example
[docker-compose.yml](./examples/docker-compose.yml) usecase for Workspaces.

### Docker configurations

*Terraform* module links are saved as _absolute_ paths in relative to the
project root (note `.terraform/modules/<uuid>`). Given these paths will vary
betwen Docker and the host, we mount the volume as read-only, assuring we don't
ever interfere with your real environment.

However, in order for *Blast Radius* to actually work with *Terraform*, it needs
to be initialized. To accomplish this, the container creates an [overlayfs][]
that exists within the container, overlaying your own, so that it can operate
independently. To do this, certain runtime privileges are required --
specifically `--cap-add=SYS_ADMIN`.

For more information on how this works and what it means for your host, check
out the [runtime privileges][privileges] documentation.

#### Docker & Subdirectories

If you organized your *Terraform* project using stacks and modules,
*Blast Radius* must be called from the project root and reference them as
subdirectories -- don't forget to prefix `--serve`!

For example, let's create a Terraform `project` with the following:

```txt
$ tree -d
`-- project/
    |-- modules/
    |   |-- foo
    |   |-- bar
    |   `-- dead
    `-- stacks/
        `-- beef/
             `-- .terraform
```

It consists of 3 modules `foo`, `bar` and `dead`, followed by one `beef` stack.
To apply *Blast Radius* to the `beef` stack, you would want to run the container
with the following:

```sh
$ cd project
$ docker run --rm -it -p 5000:5000 \
    -v $(pwd):/data:ro \
    --security-opt apparmor:unconfined \
    --cap-add=SYS_ADMIN \
    28mm/blast-radius --serve stacks/beef
```

## Embedded Figures

You may wish to embed figures produced with *Blast Radius* in other documents.
You will need the following:

1. An `svg` file and `json` document representing the graph and its layout.
2. `javascript` and `css` found in `.../blastradius/server/static`
3. A uniquely identified DOM element, where the `<svg>` should appear.

You can read more details in the [documentation](doc/embedded.md)

## Implementation Details

*Blast Radius* uses the [Graphviz][] package to layout graph diagrams,
[PyHCL](https://github.com/virtuald/pyhcl) to parse [Terraform][] configuration,
and [d3.js](https://d3js.org/) to implement interactive features and animations.

## Further Reading

The development of *Blast Radius* is documented in a series of
[blog](https://28mm.github.io) posts:

* [part 1](https://28mm.github.io/notes/d3-terraform-graphs): motivations, d3 force-directed layouts vs. vanilla graphviz.
* [part 2](https://28mm.github.io/notes/d3-terraform-graphs-2): d3-enhanced graphviz layouts, meaningful coloration, animations.
* [part 3](https://28mm.github.io/notes/terraform-graphs-3): limiting horizontal sprawl, supporting modules.
* [part 4](https://28mm.github.io/notes/d3-terraform-graphs-4): search, pan/zoom, prune-to-selection, docker.

A catalog of example *Terraform* configurations, and their dependency graphs
can be found [here](https://28mm.github.io/blast-radius-docs/).

* [AWS two-tier architecture](https://28mm.github.io/blast-radius-docs/examples/terraform-provider-aws/two-tier/)
* [AWS networking (featuring modules)](https://28mm.github.io/blast-radius-docs/examples/terraform-provider-aws/networking/)
* [Google two-tier architecture](https://28mm.github.io/blast-radius-docs/examples/terraform-provider-google/two-tier/)
* [Azure load-balancing with 2 vms](https://28mm.github.io/blast-radius-docs/examples/terraform-provider-azurem/2-vms-loadbalancer-lbrules/)

These examples are drawn primarily from the `examples/` directory distributed
with various *Terraform* providers, and aren't necessarily ideal. Additional
examples, particularly demonstrations of best-practices, or of multi-cloud
configurations strongly desired.

## Kubernetes Deployment with S3 and IRSA

*Blast Radius* can now be deployed on Kubernetes with AWS S3 integration for reading Terraform state files. This enables visualization of Terraform resources without requiring local terraform files.

### Features

* **S3 Integration**: Read Terraform state files directly from S3
* **AWS IRSA Support**: Secure authentication using IAM Roles for Service Accounts
* **Kubernetes Native**: Deploy as a scalable service with health checks
* **Helm Chart**: Easy deployment and configuration management
* **Sensitive Data Redaction**: Automatic redaction of sensitive attributes in state files

### Quick Start with Kubernetes

1. **Deploy with Helm**:

```bash
helm install blast-radius ./helm/blast-radius \
  --set aws.roleArn="arn:aws:iam::YOUR_ACCOUNT:role/BlastRadiusRole" \
  --set s3.bucket="your-terraform-state-bucket" \
  --set s3.region="us-east-1"
```

2. **Access the service**:

```bash
kubectl port-forward service/blast-radius 8080:80
```

3. **View your Terraform state**: Navigate to http://localhost:8080

### Configuration

Key environment variables for S3 mode:

* `S3_BUCKET`: S3 bucket containing Terraform state files (required)
* `S3_REGION`: AWS region for the S3 bucket (default: us-east-1)
* `STATE_REFRESH_INTERVAL`: Refresh interval in seconds (default: 300)

### IRSA Setup

Create an IAM role with S3 read permissions and trust relationship for your EKS service account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::your-bucket",
        "arn:aws:s3:::your-bucket/*"
      ]
    }
  ]
}
```

See the `examples/` directory for complete setup instructions and example configurations.

### API Endpoints

When running in Kubernetes mode, additional API endpoints are available:

* `/api/health` - Health check endpoint
* `/api/s3/states` - List available state files in S3
* `/api/s3/refresh` - Force refresh of cached state files
