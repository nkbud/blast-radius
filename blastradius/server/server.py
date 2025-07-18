# standard libraries
import os
import subprocess
import itertools
import json
import logging

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
    completed = subprocess.run(['terraform', 'graph'], stdout=subprocess.PIPE)
    if completed.returncode != 0:
        raise Exception('Execution error', completed.stderr)
    return completed.stdout.decode('utf-8')


def generate_graph_from_state(state_data):
    """
    Generate a DotGraph from Terraform state data.
    This is a simplified implementation that creates nodes from resources.
    """
    # Generate a basic DOT graph from state resources
    dot_content = "digraph {\n"
    
    # Process resources from state
    if 'resources' in state_data:
        resources = state_data['resources']
        for resource in resources:
            if resource.get('mode') == 'managed':
                resource_type = resource.get('type', 'unknown')
                resource_name = resource.get('name', 'unknown')
                full_name = f"{resource_type}.{resource_name}"
                
                # Add node
                dot_content += f'  "{full_name}" [label="{full_name}"];\n'
                
                # Add dependencies if they exist
                if 'depends_on' in resource:
                    for dep in resource['depends_on']:
                        dot_content += f'  "{dep}" -> "{full_name}";\n'
    
    dot_content += "}\n"
    
    return DotGraph('', file_contents=dot_content)


@app.route('/api/s3/states')
def list_s3_states():
    """List available Terraform state files in S3."""
    if not s3_state_reader or not s3_state_reader.is_s3_enabled():
        return jsonify({"error": "S3 mode not enabled"}), 400
    
    states = s3_state_reader.list_available_states()
    return jsonify({"states": states})


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





