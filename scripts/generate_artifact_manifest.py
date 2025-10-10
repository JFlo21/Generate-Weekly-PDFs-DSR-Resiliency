#!/usr/bin/env python3
"""
Generate Artifact Manifest for GitHub Actions Uploads
Creates a comprehensive JSON manifest of all generated Excel files with metadata
for easy discovery, auditing, and cloud storage organization.
"""

import os
import json
import hashlib
import datetime
from pathlib import Path

# Set the trusted root directory for generated documents
SAFE_DOCS_ROOT = os.path.abspath("generated_docs")

def calculate_file_hash(filepath):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"⚠️ Could not hash {filepath}: {e}")
        return None

def parse_excel_filename(filename):
    """Parse structured filename: WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_{hash}.xlsx"""
    try:
        if not filename.startswith('WR_') or not filename.endswith('.xlsx'):
            return None
        
        # Remove .xlsx extension
        base = filename[:-5]
        parts = base.split('_')
        
        if len(parts) < 4:
            return None
        
        # Parse structured filename
        if parts[0] == 'WR' and parts[2] == 'WeekEnding':
            wr_number = parts[1]
            week_ending = parts[3]
            timestamp = parts[4] if len(parts) > 4 else None
            data_hash = parts[5] if len(parts) > 5 else None
            
            return {
                'work_request': wr_number,
                'week_ending': week_ending,
                'timestamp': timestamp,
                'data_hash': data_hash
            }
    except Exception as e:
        print(f"⚠️ Could not parse filename {filename}: {e}")
    return None

def get_file_metadata(filepath):
    """Get comprehensive file metadata."""
    try:
        stat = os.stat(filepath)
        return {
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'created': datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
    except Exception as e:
        print(f"⚠️ Could not get metadata for {filepath}: {e}")
        return None

def generate_manifest(docs_folder='generated_docs', output_file='artifact_manifest.json'):
    """Generate comprehensive artifact manifest."""

    # Validate supplied docs_folder to prevent path traversal or absolute paths.
    # Only allow relative, normalized directory names with no traversal ('..') or leading slashes.
    norm_docs_folder = os.path.normpath(docs_folder)
    if os.path.isabs(norm_docs_folder):
        print(f"❌ Unsafe docs_folder path: {docs_folder}. Aborting for security.")
        return {
            'error': f"Unsafe docs_folder path: {docs_folder}"
        }
    abs_docs_folder = os.path.abspath(norm_docs_folder)
    # Enforce abs_docs_folder is inside SAFE_DOCS_ROOT
    safe_root = SAFE_DOCS_ROOT
    try:
        common = os.path.commonpath([abs_docs_folder, safe_root])
        if common != safe_root:
            print(f"❌ docs_folder path {docs_folder} escapes safe root {safe_root}. Aborting for security.")
            return {
                'error': f"docs_folder path {docs_folder} escapes safe root {safe_root}"
            }
    except Exception as e:
        print(f"❌ Error validating docs_folder path: {e}")
        return {
            'error': f"Error validating docs_folder path: {e}"
        }

    manifest = {
        'generated_at': datetime.datetime.now().isoformat(),
        'generator': 'generate_artifact_manifest.py',
        'version': '1.0',
        'source_folder': abs_docs_folder,
        'artifacts': [],
        'summary': {
            'total_files': 0,
            'total_size_bytes': 0,
            'total_size_mb': 0,
            'work_requests': [],
            'week_endings': [],
            'by_week': {},
            'by_wr': {}
        }
    }
    
    if not os.path.exists(abs_docs_folder):
        print(f"⚠️ Folder {abs_docs_folder} does not exist")
        return manifest
    
    excel_files = [f for f in os.listdir(abs_docs_folder) 
                   if f.startswith('WR_') and f.endswith('.xlsx')]
    
    print(f"📊 Processing {len(excel_files)} Excel files...")
    
    for filename in sorted(excel_files):
        filepath = os.path.join(docs_folder, filename)
        
        # Parse filename structure
        parsed = parse_excel_filename(filename)
        
        # Get file metadata
        metadata = get_file_metadata(filepath)
        
        # Calculate file hash for validation
        file_hash = calculate_file_hash(filepath)
        
        artifact_entry = {
            'filename': filename,
            'filepath': filepath,
            'sha256': file_hash,
        }
        
        if parsed:
            artifact_entry.update({
                'work_request': parsed['work_request'],
                'week_ending': parsed['week_ending'],
                'timestamp': parsed['timestamp'],
                'data_hash': parsed['data_hash'],
            })
            
            # Track unique values
            if parsed['work_request'] not in manifest['summary']['work_requests']:
                manifest['summary']['work_requests'].append(parsed['work_request'])
            if parsed['week_ending'] not in manifest['summary']['week_endings']:
                manifest['summary']['week_endings'].append(parsed['week_ending'])
            
            # Group by week
            week = parsed['week_ending']
            if week not in manifest['summary']['by_week']:
                manifest['summary']['by_week'][week] = []
            manifest['summary']['by_week'][week].append(filename)
            
            # Group by WR
            wr = parsed['work_request']
            if wr not in manifest['summary']['by_wr']:
                manifest['summary']['by_wr'][wr] = []
            manifest['summary']['by_wr'][wr].append(filename)
        
        if metadata:
            artifact_entry.update(metadata)
            manifest['summary']['total_size_bytes'] += metadata['size_bytes']
        
        manifest['artifacts'].append(artifact_entry)
    
    # Calculate summary statistics
    manifest['summary']['total_files'] = len(manifest['artifacts'])
    manifest['summary']['total_size_mb'] = round(
        manifest['summary']['total_size_bytes'] / (1024 * 1024), 2
    )
    manifest['summary']['work_requests'].sort()
    manifest['summary']['week_endings'].sort()
    
    # Write manifest
    output_path = os.path.join(abs_docs_folder, output_file)
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2, default=str)
    
    print(f"✅ Manifest generated: {output_path}")
    print(f"📋 Summary:")
    print(f"   Total Files: {manifest['summary']['total_files']}")
    print(f"   Total Size: {manifest['summary']['total_size_mb']} MB")
    print(f"   Work Requests: {len(manifest['summary']['work_requests'])}")
    print(f"   Week Endings: {len(manifest['summary']['week_endings'])}")
    
    return manifest

if __name__ == '__main__':
    import sys
    docs_folder = sys.argv[1] if len(sys.argv) > 1 else 'generated_docs'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'artifact_manifest.json'
    
    manifest = generate_manifest(docs_folder, output_file)
