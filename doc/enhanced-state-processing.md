# Enhanced State Processing and Browsing

This document describes the enhanced state file processing and browsing capabilities added to Blast Radius.

## Key Features

### 1. Enhanced State-to-Graph Conversion

The system can now convert Terraform state files (`.tfstate`) into comprehensive dependency graphs without requiring the Terraform CLI.

**Features:**
- **Comprehensive Resource Handling**: Processes managed resources, data sources, and modules
- **Advanced Dependency Detection**: Handles explicit dependencies, instance dependencies, and inferred relationships
- **Visual Styling**: Different colors and shapes for different resource types:
  - AWS resources: Orange boxes
  - Data sources: Light blue ellipses  
  - Other resources: Gray boxes
- **Module Support**: Properly handles module namespacing and dependencies

### 2. Thread Safety & Concurrency

All Terraform CLI operations are now thread-safe with proper queuing to prevent conflicts.

**Implementation:**
- Thread-safe terraform CLI operations using RLock
- Processing queue with ThreadPoolExecutor (single worker for terraform operations)
- 60-second timeout for terraform graph commands
- Comprehensive error handling and logging

### 3. Enhanced Browsing & Navigation

#### S3 Mode
- **Interactive State File Selection**: Dropdown menu showing all available `.tfstate` files
- **Cache Refresh Controls**: Manual refresh button for S3 state cache
- **Detailed File Information**: File size, modification dates, and metadata
- **Pagination Support**: Handles large S3 buckets efficiently

#### Local Mode
- **File Upload Capability**: Direct `.tfstate` file upload for processing
- **Drag-and-drop Support**: Easy file upload interface
- **Real-time Processing**: Immediate graph generation from uploaded files

## API Endpoints

### New Endpoints

#### `POST /api/state/process`
Process a `.tfstate` file directly from uploaded content.

**Parameters:**
- `format`: Output format (`json`, `svg`, `dot`) - default: `json`
- `state_file`: File upload (multipart/form-data)
- Or JSON state data in request body

**Example:**
```bash
curl -X POST -F "state_file=@terraform.tfstate" \
  http://localhost:5000/api/state/process?format=svg
```

#### `GET /api/terraform/capabilities`
Check terraform CLI capabilities and system requirements.

**Response:**
```json
{
  "terraform_cli_available": true,
  "graphviz_available": true,
  "terraform_initialized": true,
  "can_process_state_files": true,
  "thread_safe": true,
  "supports_s3": true,
  "terraform_version": "Terraform v1.5.7",
  "recommendations": [...]
}
```

#### `GET /api/s3/states/<path:state_key>`
Get detailed information about a specific state file.

**Response:**
```json
{
  "key": "production/terraform.tfstate",
  "size": 15420,
  "last_modified": "2024-01-15T10:30:00Z",
  "etag": "d41d8cd98f00b204e9800998ecf8427e",
  "content_type": "application/json"
}
```

### Enhanced Endpoints

#### `GET /api/s3/states?detailed=true`
List available state files with detailed metadata.

## Usage Examples

### Processing a Local State File

1. **Via Web Interface**: Click "Upload State" button and select your `.tfstate` file
2. **Via API**: 
```bash
curl -X POST -F "state_file=@my-terraform.tfstate" \
  http://localhost:5000/api/state/process
```

### Browsing S3 State Files

1. **Set Environment Variables**:
```bash
export S3_BUCKET=my-terraform-states
export S3_REGION=us-east-1
export STATE_REFRESH_INTERVAL=300
```

2. **Access Web Interface**: State files dropdown will automatically populate

3. **API Access**:
```bash
# List all state files
curl http://localhost:5000/api/s3/states

# Get detailed information
curl http://localhost:5000/api/s3/states?detailed=true

# Refresh cache
curl -X POST http://localhost:5000/api/s3/refresh
```

## Performance Considerations

### Thread Safety
- Only one Terraform CLI operation runs at a time
- State file processing can run concurrently
- Web requests are handled asynchronously

### Caching
- S3 state files are cached with configurable refresh intervals
- Graph generation results are cached per state file
- File metadata is cached separately for quick listing

### Resource Usage
- State file processing is memory-efficient
- Large state files (>10MB) are processed in streaming mode
- Comprehensive timeout handling prevents resource leaks

## Troubleshooting

### Common Issues

**1. "Terraform CLI not found"**
- Ensure terraform is in PATH or use state-only mode
- Check `/api/terraform/capabilities` endpoint for system status

**2. "Error processing state file"**
- Verify the file is valid JSON
- Check that it's a proper Terraform state file (has `version` or `terraform_version` fields)

**3. "S3 access denied"**
- Verify IRSA configuration for Kubernetes deployment
- Check AWS credentials and IAM permissions
- Ensure S3 bucket exists and is accessible

**4. "Graph generation timeout"**
- For large terraform configurations, increase timeout values
- Consider using state-only mode for faster processing
- Check system resources (memory, CPU)

### Debug Information

Check the health endpoint for system status:
```bash
curl http://localhost:5000/api/health
```

Check terraform capabilities:
```bash
curl http://localhost:5000/api/terraform/capabilities
```

## Migration Notes

### Backward Compatibility
All existing functionality is preserved:
- Original Docker usage unchanged
- Local terraform file support unchanged  
- Existing API endpoints unchanged

### New Features Are Opt-in
- S3 browsing: Only enabled when `S3_BUCKET` environment variable is set
- File upload: Only available in local mode (when S3 is not configured)
- Enhanced processing: Automatic for all modes