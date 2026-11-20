#!/usr/bin/env python3
"""Inspect real HDF5 episode trees without assuming a specific RoboTwin schema.

Only runs if h5py is installed. Does not load entire RGB-D arrays into memory.
"""
import argparse
import json
from pathlib import Path


def inspect_file(filepath):
    try:
        import h5py
    except ImportError as e:
        raise RuntimeError('Optional h5py package not installed. Install only when validating actual HDF5 data.') from e
    nodes = []
    with h5py.File(filepath, 'r') as h5:
        def visitor(path, obj):
            node = {'path': path, 'kind': 'dataset' if isinstance(obj, h5py.Dataset) else 'group'}
            if isinstance(obj, h5py.Dataset):
                node.update(shape=list(obj.shape), dtype=str(obj.dtype))
            nodes.append(node)
        h5.visititems(visitor)
    hints = {
        'rgb_like': [n['path'] for n in nodes if n['kind'] == 'dataset' and ('rgb' in n['path'].lower() or 'image' in n['path'].lower())],
        'depth_like': [n['path'] for n in nodes if n['kind'] == 'dataset' and 'depth' in n['path'].lower()],
        'robot_state_like': [n['path'] for n in nodes if n['kind'] == 'dataset' and any(k in n['path'].lower() for k in ['qpos', 'joint', 'state', 'action'])],
    }
    return {'file': str(filepath), 'bytes': filepath.stat().st_size, 'dataset_tree': nodes, 'path_name_hints_only': hints}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--file', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if not a.file.is_file():
        p.error('Input file missing')
    out = inspect_file(a.file)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Inspected {len(out["dataset_tree"])} HDF5 nodes; wrote {a.output}')
    print('Path-name hints are NOT proof of correct semantic content. Compare against locked packer.py')


if __name__ == '__main__':
    main()
