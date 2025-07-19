#!/bin/sh
set -e

# If command starts with an option, prepend the blast-radius.
if [ "${1}" != "blast-radius" ]; then
  if [ -n "${1}" ]; then
    set -- blast-radius "$@"
  fi
fi

# Check if we're running in S3 mode
if [ -n "${S3_BUCKET}" ]; then
  echo "Running in S3 mode with bucket: ${S3_BUCKET}"
  echo "Skipping terraform initialization as we'll read state from S3"
  # For S3 mode, we don't need the overlay filesystem or terraform init
  cd /data
else
  echo "Running in local terraform mode"
  echo "Note: For full local mode functionality, container needs privileged access for overlay filesystem"
  echo "In S3 mode, this is not required"
  # We'll skip the overlay filesystem for now in non-root mode
  # This will only work if the container is run with proper volume mounts
  cd /data

  # Check if terraform files exist
  if [ -f "*.tf" ] || [ -d ".terraform" ]; then
    # Assert CLI args are overwritten, otherwise set them to preferred defaults
    export TF_CLI_ARGS_get=${TF_CLI_ARGS_get:'-update'}
    export TF_CLI_ARGS_init=${TF_CLI_ARGS_init:'-input=false'}

    # Is Terraform already initialized? Ensure modules are all downloaded.
    [ -d '.terraform' ] && terraform get

    # Initialize terraform
    terraform init || echo "Terraform init failed - this is expected in S3 mode"
  else
    echo "No terraform files found, assuming S3 mode or external configuration"
  fi
fi

# Let's go!
exec "$@"
