# standard libraries
import os
import subprocess
import itertools
import json
import logging
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# 3rd-party libraries
from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify
import jinja2

# 1st-party libraries
from blastradius.handlers.dot import DotGraph, Format, DotNode
from blastradius.handlers.terraform import Terraform
from blastradius.handlers.s3 import s3_state_reader
from blastradius.util import which
from blastradius.graph import Node, Edge, Counter, Graph

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread safety for terraform CLI operations
_terraform_lock = threading.RLock()
_terraform_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='terraform-worker')

@contextmanager
def terraform_cli_context():
    """Context manager to ensure thread-safe terraform CLI operations."""
    with _terraform_lock:
        logger.debug("Acquired terraform CLI lock")
        try:
            yield
        finally:
            logger.debug("Released terraform CLI lock")

app = Flask(__name__)

@app.route('/')
def index():
    # Check if S3 mode is enabled
    if s3_state_reader and s3_state_reader.is_s3_enabled():
        logger.info("Running in S3 mode")
        return render_template('index.html', help=get_help(), s3_mode=True)
    else:
        # Original local mode checks
        if not which('terraform') and not which('terraform.exe'):
            return render_template('error.html')
        elif not which('dot') and not which('dot.exe'):
            return render_template('error.html')
        elif not os.path.exists('.terraform'):
            return render_template('error.html')
        else:
            return render_template('index.html', help=get_help(), s3_mode=False)

@app.route('/graph.svg')
def graph_svg():
    Graph.reset_counters()
    
    # Check if we should use S3 state files
    s3_key = request.args.get('s3_key')
    if s3_state_reader and s3_state_reader.is_s3_enabled() and s3_key:
        # Get state from S3 and generate graph from state
        state_data = s3_state_reader.get_state_file(s3_key)
        if state_data:
            dot = generate_graph_from_state(state_data)
        else:
            return "Error: Could not load state file from S3", 404
    else:
        # Original terraform graph mode
        dot = DotGraph('', file_contents=run_tf_graph())

    module_depth = request.args.get('module_depth', default=None, type=int)
    refocus      = request.args.get('refocus', default=None, type=str)

    if module_depth is not None and module_depth >= 0:
        dot.set_module_depth(module_depth)

    if refocus is not None:
        node = dot.get_node_by_name(refocus)
        if node:
            dot.center(node)

    return dot.svg()


@app.route('/graph.json')
def graph_json():
    Graph.reset_counters()
    
    # Check if we should use S3 state files
    s3_key = request.args.get('s3_key')
    if s3_state_reader and s3_state_reader.is_s3_enabled() and s3_key:
        # Get state from S3 and generate graph from state
        state_data = s3_state_reader.get_state_file(s3_key)
        if state_data:
            dot = generate_graph_from_state(state_data)
        else:
            return jsonify({"error": "Could not load state file from S3"}), 404
    else:
        # Original terraform graph mode
        dot = DotGraph('', file_contents=run_tf_graph())
        
    module_depth = request.args.get('module_depth', default=None, type=int)
    refocus      = request.args.get('refocus', default=None, type=str)
    if module_depth is not None and module_depth >= 0:
        dot.set_module_depth(module_depth)

    tf = Terraform(os.getcwd())
    for node in dot.nodes:
        node.definition = tf.get_def(node)

    if refocus is not None:
        node = dot.get_node_by_name(refocus)
        if node:
            dot.center(node)

    return dot.json()

def run_tf_graph():
    """Run terraform graph command with thread safety."""
    with terraform_cli_context():
        logger.info("Executing terraform graph command")
        start_time = time.time()
        
        try:
            completed = subprocess.run(
                ['terraform', 'graph'], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60  # 60 second timeout
            )
            
            execution_time = time.time() - start_time
            logger.info(f"Terraform graph completed in {execution_time:.2f} seconds")
            
            if completed.returncode != 0:
                error_msg = completed.stderr.decode('utf-8') if completed.stderr else "Unknown error"
                logger.error(f"Terraform graph failed: {error_msg}")
                raise Exception('Terraform graph execution error', error_msg)
                
            return completed.stdout.decode('utf-8')
            
        except subprocess.TimeoutExpired:
            logger.error("Terraform graph command timed out")
            raise Exception('Terraform graph timeout', 'Command exceeded 60 second timeout')
        except FileNotFoundError:
            logger.error("Terraform CLI not found")
            raise Exception('Terraform CLI not found', 'terraform command not available in PATH')
        except Exception as e:
            logger.error(f"Unexpected error running terraform graph: {str(e)}")
            raise


def generate_graph_from_state(state_data):
    """
    Generate a DotGraph from Terraform state data.
    Enhanced implementation that handles various resource types, dependencies, 
    and terraform relationships more comprehensively.
    """
    import re
    
    dot_content = "digraph {\n"
    dot_content += '  rankdir="RL";\n'  # Right to Left layout like terraform graph
    dot_content += '  compound="true";\n'
    dot_content += '  newrank="true";\n'
    
    nodes = {}  # Track all nodes to avoid duplicates
    edges = set()  # Track edges to avoid duplicates
    
    # Process resources from state
    if 'resources' in state_data:
        resources = state_data['resources']
        
        # First pass: create all nodes
        for resource in resources:
            mode = resource.get('mode', 'unknown')
            resource_type = resource.get('type', 'unknown')
            resource_name = resource.get('name', 'unknown')
            module = resource.get('module', '')
            
            # Build full resource address
            if module:
                full_name = f"module.{module}.{resource_type}.{resource_name}"
            else:
                if mode == 'data':
                    full_name = f"data.{resource_type}.{resource_name}"
                else:
                    full_name = f"{resource_type}.{resource_name}"
            
            nodes[full_name] = resource
            
            # Determine node styling based on resource type and mode
            node_attrs = []
            if mode == 'data':
                node_attrs.append('shape="ellipse"')
                node_attrs.append('style="filled"')
                node_attrs.append('fillcolor="lightblue"')
            elif resource_type.startswith('aws_'):
                node_attrs.append('shape="box"')
                node_attrs.append('style="filled"')
                node_attrs.append('fillcolor="orange"')
            elif resource_type.startswith('kubernetes_'):
                node_attrs.append('shape="box"')
                node_attrs.append('style="filled"') 
                node_attrs.append('fillcolor="lightgreen"')
            else:
                node_attrs.append('shape="box"')
                node_attrs.append('style="filled"')
                node_attrs.append('fillcolor="lightgray"')
            
            # Clean label for display
            display_name = f"{resource_type}\\n{resource_name}"
            if module:
                display_name = f"module.{module}\\n{display_name}"
            
            node_attrs.append(f'label="{display_name}"')
            attrs_str = ', '.join(node_attrs)
            dot_content += f'  "{full_name}" [{attrs_str}];\n'
        
        # Second pass: create edges from dependencies
        for resource in resources:
            resource_type = resource.get('type', 'unknown')
            resource_name = resource.get('name', 'unknown')
            module = resource.get('module', '')
            mode = resource.get('mode', 'unknown')
            
            # Build source node name
            if module:
                source_name = f"module.{module}.{resource_type}.{resource_name}"
            else:
                if mode == 'data':
                    source_name = f"data.{resource_type}.{resource_name}"
                else:
                    source_name = f"{resource_type}.{resource_name}"
            
            # Process explicit dependencies
            if 'depends_on' in resource:
                for dep in resource['depends_on']:
                    if dep != source_name:  # Avoid self-references
                        edges.add((dep, source_name))
            
            # Process implicit dependencies from resource instances
            instances = resource.get('instances', [])
            for instance in instances:
                attrs = instance.get('attributes', {})
                dependencies = instance.get('dependencies', [])
                
                for dep in dependencies:
                    if dep != source_name:  # Avoid self-references
                        edges.add((dep, source_name))
                
                # Look for references in attributes (basic pattern matching)
                if isinstance(attrs, dict):
                    for attr_name, attr_value in attrs.items():
                        if isinstance(attr_value, str):
                            # Look for terraform references like ${aws_instance.example.id}
                            refs = re.findall(r'\$\{([^}]+)\}', attr_value)
                            for ref in refs:
                                # Clean up the reference
                                ref = ref.split('.')[0:2]  # Take resource type and name
                                if len(ref) == 2:
                                    ref_name = f"{ref[0]}.{ref[1]}"
                                    if ref_name in nodes and ref_name != source_name:
                                        edges.add((ref_name, source_name))
        
        # Add all edges to dot content
        for source, target in edges:
            dot_content += f'  "{source}" -> "{target}";\n'
    
    dot_content += "}\n"
    
    logger.debug(f"Generated graph with {len(nodes)} nodes and {len(edges)} edges")
    return DotGraph('', file_contents=dot_content)


@app.route('/api/s3/states')
def list_s3_states():
    """List available Terraform state files in S3."""
    if not s3_state_reader or not s3_state_reader.is_s3_enabled():
        return jsonify({"error": "S3 mode not enabled"}), 400
    
    detailed = request.args.get('detailed', 'false').lower() == 'true'
    states = s3_state_reader.list_available_states()
    
    if detailed:
        # Get detailed information for each state file
        detailed_states = []
        for state_key in states:
            info = s3_state_reader.get_state_file_info(state_key)
            if info:
                detailed_states.append(info)
        return jsonify({"states": detailed_states})
    else:
        return jsonify({"states": states})


@app.route('/api/s3/states/<path:state_key>')
def get_s3_state_info(state_key):
    """Get detailed information about a specific state file."""
    if not s3_state_reader or not s3_state_reader.is_s3_enabled():
        return jsonify({"error": "S3 mode not enabled"}), 400
    
    info = s3_state_reader.get_state_file_info(state_key)
    if info:
        return jsonify(info)
    else:
        return jsonify({"error": "State file not found"}), 404


@app.route('/api/s3/refresh')
def refresh_s3_cache():
    """Force refresh of S3 state cache."""
    if not s3_state_reader or not s3_state_reader.is_s3_enabled():
        return jsonify({"error": "S3 mode not enabled"}), 400
    
    s3_state_reader.clear_cache()
    return jsonify({"message": "Cache cleared successfully"})


@app.route('/api/health')
def health_check():
    """Health check endpoint for Kubernetes."""
    status = {
        "status": "healthy",
        "s3_enabled": s3_state_reader and s3_state_reader.is_s3_enabled(),
        "terraform_available": bool(which('terraform') or which('terraform.exe')),
        "graphviz_available": bool(which('dot') or which('dot.exe'))
    }
    
    if s3_state_reader and s3_state_reader.is_s3_enabled():
        status["s3_bucket"] = s3_state_reader.bucket
        status["s3_region"] = s3_state_reader.region
    
    return jsonify(status)


@app.route('/api/state/process', methods=['POST'])
def process_state_file():
    """
    Process a .tfstate file directly from uploaded content.
    Allows users to submit state files for graph generation.
    """
    try:
        # Check if JSON data was sent
        if request.is_json:
            state_data = request.get_json()
        else:
            # Check if a file was uploaded
            if 'state_file' not in request.files:
                return jsonify({"error": "No state file provided"}), 400
            
            file = request.files['state_file']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            # Read and parse the file
            try:
                content = file.read().decode('utf-8')
                state_data = json.loads(content)
            except json.JSONDecodeError as e:
                return jsonify({"error": f"Invalid JSON in state file: {str(e)}"}), 400
            except UnicodeDecodeError:
                return jsonify({"error": "State file must be UTF-8 encoded"}), 400
        
        # Validate that this looks like a terraform state file
        if not isinstance(state_data, dict):
            return jsonify({"error": "State file must be a JSON object"}), 400
        
        if 'terraform_version' not in state_data and 'version' not in state_data:
            return jsonify({"error": "Not a valid Terraform state file"}), 400
        
        # Generate the graph
        try:
            dot_graph = generate_graph_from_state(state_data)
            
            # Return the graph data based on requested format
            output_format = request.args.get('format', 'json')
            
            if output_format == 'svg':
                return dot_graph.svg(), 200, {'Content-Type': 'image/svg+xml'}
            elif output_format == 'dot':
                return dot_graph.dot(), 200, {'Content-Type': 'text/plain'}
            else:  # default to json
                # Add terraform definitions if available in local mode
                try:
                    tf = Terraform(os.getcwd())
                    for node in dot_graph.nodes:
                        node.definition = tf.get_def(node)
                except:
                    pass  # Ignore errors if terraform config not available
                
                return jsonify(json.loads(dot_graph.json()))
                
        except Exception as e:
            logger.error(f"Error generating graph from state: {str(e)}")
            return jsonify({"error": f"Failed to generate graph: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Error processing state file: {str(e)}")
        return jsonify({"error": f"Failed to process state file: {str(e)}"}), 500


@app.route('/api/terraform/capabilities')
def terraform_capabilities():
    """
    Check terraform CLI capabilities and requirements.
    Helps determine if local mode can function properly.
    """
    capabilities = {
        "terraform_cli_available": bool(which('terraform') or which('terraform.exe')),
        "graphviz_available": bool(which('dot') or which('dot.exe')),
        "terraform_initialized": os.path.exists('.terraform'),
        "can_process_state_files": True,  # We can always process state files directly
        "thread_safe": True,  # We have thread safety implemented
        "supports_s3": s3_state_reader and s3_state_reader.is_s3_enabled()
    }
    
    # Check terraform version if available
    if capabilities["terraform_cli_available"]:
        try:
            with terraform_cli_context():
                result = subprocess.run(
                    ['terraform', '--version'], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    timeout=10
                )
                if result.returncode == 0:
                    version_output = result.stdout.decode('utf-8').strip()
                    capabilities["terraform_version"] = version_output.split('\n')[0]
                else:
                    capabilities["terraform_version"] = "Unknown (command failed)"
        except Exception as e:
            capabilities["terraform_version"] = f"Error: {str(e)}"
    
    # Performance recommendations
    recommendations = []
    if not capabilities["terraform_cli_available"]:
        recommendations.append("Terraform CLI not available - only state file processing mode supported")
    if not capabilities["graphviz_available"]:
        recommendations.append("Graphviz not available - graph rendering may fail")
    if not capabilities["terraform_initialized"] and capabilities["terraform_cli_available"]:
        recommendations.append("Terraform not initialized in current directory - run 'terraform init' for local mode")
    if capabilities["supports_s3"]:
        recommendations.append("S3 mode enabled - can process remote state files")
    
    capabilities["recommendations"] = recommendations
    
    return jsonify(capabilities)

def get_help():
    help_info = { 
        'tf_version': get_terraform_version(),
        'tf_exe': get_terraform_exe(),
        'cwd': os.getcwd()
    }
    
    # Add S3 information if enabled
    if s3_state_reader and s3_state_reader.is_s3_enabled():
        help_info.update({
            's3_enabled': True,
            's3_bucket': s3_state_reader.bucket,
            's3_region': s3_state_reader.region,
            'refresh_interval': s3_state_reader.refresh_interval
        })
    else:
        help_info['s3_enabled'] = False
    
    return help_info

def get_terraform_version():
    completed = subprocess.run(['terraform', '--version'], stdout=subprocess.PIPE)
    if completed.returncode != 0:
        raise
    return completed.stdout.decode('utf-8').splitlines()[0].split(' ')[-1]

def get_terraform_exe():
    return which('terraform')





