#!/usr/bin/env python3
"""
Generate Artifact Manifest for GitHub Actions Uploads
Creates a comprehensive JSON and/or CSV manifest of all generated Excel files with metadata
for easy discovery, auditing, and cloud storage organization.

CSV Export Feature:
- Exports data in human-readable CSV format
- Converts week ending codes (MMDDYY) to readable dates
- Suitable for importing into ChatGPT, Excel, or other tools
"""

import os
import json
import csv
import hashlib
import datetime
from pathlib import Path

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


def format_week_ending(week_code):
    """Convert MMDDYY week ending code to readable date format."""
    if not week_code or len(week_code) != 6:
        return week_code
    try:
        month = week_code[0:2]
        day = week_code[2:4]
        year = '20' + week_code[4:6]
        return f"{month}/{day}/{year}"
    except (ValueError, IndexError):
        return week_code


def export_to_csv(manifest, docs_folder, output_file='artifact_manifest.csv'):
    """Export manifest data to CSV format with human-readable values."""
    csv_path = os.path.join(docs_folder, output_file)
    
    # Define CSV columns with human-readable headers
    fieldnames = [
        'Filename',
        'Work Request #',
        'Week Ending Date',
        'File Size (MB)',
        'Created Date',
        'Modified Date'
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for artifact in manifest.get('artifacts', []):
            # Format week ending to readable date
            week_ending_raw = artifact.get('week_ending', '')
            week_ending_formatted = format_week_ending(week_ending_raw)
            
            row = {
                'Filename': artifact.get('filename', ''),
                'Work Request #': artifact.get('work_request', ''),
                'Week Ending Date': week_ending_formatted,
                'File Size (MB)': artifact.get('size_mb', ''),
                'Created Date': artifact.get('created', ''),
                'Modified Date': artifact.get('modified', '')
            }
            writer.writerow(row)
    
    print(f"✅ CSV manifest generated: {csv_path}")
    return csv_path


def export_hash_history_to_csv(hash_history_path, output_path):
    """Export hash_history.json to CSV format with human-readable values.
    
    This function converts the hash history JSON file which contains:
    - Key format: "WR_NUMBER|WEEK_CODE" (e.g., "89708709.0|071325")
      Extended format may include: "WR_NUMBER|WEEK_CODE|VARIANT|IDENTIFIER"
    - Values: hash, rows, updated_at, foreman, week
    
    Into a CSV with clear column headers and human-readable date formats.
    """
    try:
        with open(hash_history_path, 'r') as f:
            hash_history = json.load(f)
    except FileNotFoundError:
        print(f"⚠️ Hash history file not found: {hash_history_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️ Could not parse hash history JSON: {e}")
        return None
    
    # Define CSV columns with human-readable headers
    fieldnames = [
        'Work Request #',
        'Week Ending Date',
        'Foreman',
        'Row Count',
        'Last Updated',
        'Data Hash'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for key, data in hash_history.items():
            # Parse the key format: "WR_NUMBER|WEEK_CODE"
            # The key contains the work request number as the first part
            key_parts = key.split('|')
            work_request = key_parts[0] if key_parts else ''
            
            # Format week ending from MMDDYY to MM/DD/YYYY
            week_code = data.get('week', '')
            week_ending_formatted = format_week_ending(week_code)
            
            # Format the updated_at timestamp to readable date
            updated_at_raw = data.get('updated_at', '')
            updated_at_formatted = ''
            if updated_at_raw:
                try:
                    # Handle ISO format with various timezone suffixes
                    # Replace 'Z' with '+00:00' for fromisoformat compatibility
                    normalized = updated_at_raw.replace('Z', '+00:00')
                    # Handle cases where timezone may be missing
                    if '+' not in normalized and '-' not in normalized[10:]:
                        # No timezone info, treat as UTC
                        dt = datetime.datetime.fromisoformat(normalized)
                    else:
                        dt = datetime.datetime.fromisoformat(normalized)
                    updated_at_formatted = dt.strftime('%m/%d/%Y %I:%M %p')
                except (ValueError, TypeError, AttributeError):
                    # If parsing fails, use the raw value
                    updated_at_formatted = updated_at_raw
            
            row = {
                'Work Request #': work_request,
                'Week Ending Date': week_ending_formatted,
                'Foreman': data.get('foreman', ''),
                'Row Count': data.get('rows', ''),
                'Last Updated': updated_at_formatted,
                'Data Hash': data.get('hash', '')
            }
            writer.writerow(row)
    
    print(f"✅ Hash history CSV generated: {output_path}")
    return output_path

def generate_manifest(docs_folder='generated_docs', output_file='artifact_manifest.json'):
    """Generate comprehensive artifact manifest.
    
    Args:
        docs_folder: Path to folder containing Excel files
        output_file: Output JSON filename, or None to skip JSON output
    
    Returns:
        dict: The manifest data structure
    """
    
    manifest = {
        'generated_at': datetime.datetime.now().isoformat(),
        'generator': 'generate_artifact_manifest.py',
        'version': '1.0',
        'source_folder': docs_folder,
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
    
    if not os.path.exists(docs_folder):
        print(f"⚠️ Folder {docs_folder} does not exist")
        return manifest
    
    excel_files = [f for f in os.listdir(docs_folder) 
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
    
    # Write JSON manifest if output_file is provided
    if output_file:
        output_path = os.path.join(docs_folder, output_file)
        with open(output_path, 'w') as f:
            json.dump(manifest, f, indent=2, default=str)
        print(f"✅ JSON manifest generated: {output_path}")
    
    print(f"📋 Summary:")
    print(f"   Total Files: {manifest['summary']['total_files']}")
    print(f"   Total Size: {manifest['summary']['total_size_mb']} MB")
    print(f"   Work Requests: {len(manifest['summary']['work_requests'])}")
    print(f"   Week Endings: {len(manifest['summary']['week_endings'])}")
    
    return manifest

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate artifact manifest in JSON and/or CSV format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Generate both JSON and CSV manifests (default)
  python generate_artifact_manifest.py
  
  # Generate only CSV output
  python generate_artifact_manifest.py --format csv
  
  # Export hash history to CSV
  python generate_artifact_manifest.py --export-hash-history
  
  # Specify custom folder
  python generate_artifact_manifest.py --folder generated_docs --format both
'''
    )
    
    parser.add_argument(
        '--folder', '-f',
        default='generated_docs',
        help='Source folder containing Excel files (default: generated_docs)'
    )
    parser.add_argument(
        '--output', '-o',
        default='artifact_manifest',
        help='Output filename without extension (default: artifact_manifest)'
    )
    parser.add_argument(
        '--format', '-t',
        choices=['json', 'csv', 'both'],
        default='both',
        help='Output format: json, csv, or both (default: both)'
    )
    parser.add_argument(
        '--export-hash-history', '-e',
        action='store_true',
        help='Also export hash_history.json to CSV format'
    )
    
    # Support legacy positional arguments for backward compatibility
    args, remaining = parser.parse_known_args()
    
    # Handle legacy positional args if no named args provided
    if len(sys.argv) == 2 and not sys.argv[1].startswith('-'):
        args.folder = sys.argv[1]
    elif len(sys.argv) == 3 and not sys.argv[1].startswith('-'):
        args.folder = sys.argv[1]
        args.output = sys.argv[2].replace('.json', '').replace('.csv', '')
    
    # Generate manifest
    manifest = generate_manifest(
        docs_folder=args.folder,
        output_file=f'{args.output}.json' if args.format in ['json', 'both'] else None
    )
    
    # Export to CSV if requested
    if args.format in ['csv', 'both']:
        export_to_csv(manifest, args.folder, f'{args.output}.csv')
    
    # Export hash history to CSV if requested
    if args.export_hash_history:
        hash_history_path = os.path.join(args.folder, 'hash_history.json')
        hash_history_csv_path = os.path.join(args.folder, 'hash_history.csv')
        export_hash_history_to_csv(hash_history_path, hash_history_csv_path)
