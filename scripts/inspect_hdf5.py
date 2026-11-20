#!/usr/bin/env python3
"""Inspect HDF5 metadata and optionally validate the locked SEM schema.

Only runs if h5py is installed. Does not load entire RGB-D arrays into memory.
"""
import argparse
import json
import re
from pathlib import Path

from discover_tasks import SAFE_NAME

POSE_KEYS = ('endpose', 'joint_action/vector')
REQUIRED_CAMERAS = {'head_camera', 'left_camera', 'right_camera'}
EPISODE_NAME = re.compile(r'episode(0|[1-9][0-9]*)\.hdf5')


def inspect_file(filepath, sem=False):
    try:
        import h5py
    except ImportError as e:
        raise RuntimeError('Optional h5py package not installed. Install only when validating actual HDF5 data.') from e
    nodes = []
    with h5py.File(filepath, 'r') as h5:
        def visitor(path, obj):
            node = {'path': path, 'kind': 'dataset' if isinstance(obj, h5py.Dataset) else 'group'}
            if isinstance(obj, h5py.Dataset):
                node.update(shape=list(obj.shape) if obj.shape is not None else None,
                            dtype=str(obj.dtype), dtype_kind=obj.dtype.kind)
            nodes.append(node)
        h5.visititems(visitor)
        errors = sem_schema_errors(nodes) if sem else []
        if sem and not errors:
            for node in nodes:
                if node['kind'] != 'dataset' or not node['path'].endswith('/rgb'):
                    continue
                rgb = h5[node['path']]
                for frame in sorted({0, len(rgb) - 1}):
                    jpeg = bytes(rgb[frame]).rstrip(b'\0')
                    if not jpeg.startswith(b'\xff\xd8') or not jpeg.endswith(b'\xff\xd9'):
                        errors.append(f"{node['path']}: frame {frame} lacks JPEG markers")
    hints = {
        'rgb_like': [n['path'] for n in nodes if n['kind'] == 'dataset' and ('rgb' in n['path'].lower() or 'image' in n['path'].lower())],
        'depth_like': [n['path'] for n in nodes if n['kind'] == 'dataset' and 'depth' in n['path'].lower()],
        'robot_state_like': [n['path'] for n in nodes if n['kind'] == 'dataset' and any(k in n['path'].lower() for k in ['qpos', 'joint', 'state', 'action'])],
    }
    report = {'file': str(filepath), 'bytes': filepath.stat().st_size,
              'dataset_tree': nodes, 'path_name_hints_only': hints}
    if sem:
        report['sem_schema_errors'] = errors
    return report


def sem_schema_errors(nodes):
    datasets = {node['path']: node for node in nodes if node['kind'] == 'dataset'}
    cameras = {node['path'].split('/')[1] for node in nodes
               if node['path'].startswith('observation/') and node['path'].count('/') == 1}
    missing_cameras = REQUIRED_CAMERAS - cameras
    errors = [f'Missing camera {camera}' for camera in sorted(missing_cameras)]
    rgb_kind = 'S'
    numeric = 'iuf'
    endpose = datasets.get('endpose', {}).get('shape')
    frames = endpose[0] if endpose else 0

    def require(path, dimensions, suffix, kinds):
        node = datasets.get(path)
        shape = node['shape'] if node else None
        if not frames or not shape or len(shape) != dimensions or shape[0] != frames or 0 in shape:
            errors.append(f'{path}: missing or incompatible frame shape {shape}')
        elif (suffix and shape[-len(suffix):] != suffix) or node['dtype_kind'] not in kinds:
            errors.append(f"{path}: unexpected shape/dtype {shape} / {node['dtype']}")

    for path in POSE_KEYS:
        require(path, 2, [14], numeric)
    for camera in sorted(cameras):
        root = f'observation/{camera}'
        require(f'{root}/rgb', 1, [], rgb_kind)
        require(f'{root}/depth', 3, [], numeric)
        require(f'{root}/intrinsic_cv', 3, [3, 3], numeric)
        require(f'{root}/extrinsic_cv', 3, [3, 4], numeric)
    return errors


def dataset_episodes(root, task, episodes):
    if not SAFE_NAME.fullmatch(task) or (episodes is not None and episodes < 1):
        raise ValueError('Use a valid task name and positive expected episode count')
    base = root / task / 'demo_clean'
    # The packer splits on spaces, using episode ID as an index.
    seeds = [int(seed) for seed in (base / 'seed.txt').read_text(encoding='utf-8').strip().split(' ')]
    if any(seed < 0 for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError('seed.txt must contain unique nonnegative seeds')
    data = base / 'data' if (base / 'data').is_dir() else base
    files = {}
    for path in data.glob('*.hdf5'):
        match = EPISODE_NAME.fullmatch(path.name)
        if not path.is_file() or not match:
            raise ValueError(f'Invalid episode filename: {path}')
        files[int(match[1])] = path
    expected = episodes if episodes is not None else len(seeds)
    if len(seeds) != expected or set(files) != set(range(expected)):
        raise ValueError(f'Expected {expected} seeds and contiguous episode IDs. Found {len(seeds)} seeds and {sorted(files)}')
    return [(files[index], seed) for index, seed in enumerate(seeds)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--file', type=Path)
    inputs.add_argument('--dataset-root', type=Path, help='Root containing task/demo_clean/seed.txt and episodes')
    p.add_argument('--task', help='Task to validate under --dataset-root')
    p.add_argument('--episodes', type=int, help='Expected number of collection episodes')
    p.add_argument('--sem', action='store_true', help='Validate one file against the locked SEM packer schema')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.dataset_root and not a.task:
        p.error('--dataset-root requires --task')
    if a.file and (a.task or a.episodes is not None):
        p.error('--task and --episodes are for --dataset-root')
    try:
        if a.file:
            out = inspect_file(a.file, a.sem)
            errors = len(out.get('sem_schema_errors', []))
        else:
            entries = []
            instructions = a.dataset_root / a.task / 'demo_clean' / 'instructions'
            for path, seed in dataset_episodes(a.dataset_root, a.task, a.episodes):
                report = inspect_file(path, sem=True)
                report['seed'] = seed
                prompt_file = instructions / f'{path.stem}.json'
                if prompt_file.is_file():
                    prompt = json.loads(prompt_file.read_text(encoding='utf-8'))
                    report['has_episode_instructions'] = bool(
                        isinstance(prompt, dict) and prompt.get('seen') and prompt.get('unseen')
                    )
                else:
                    report['has_episode_instructions'] = False
                entries.append(report)
            errors = sum(len(entry['sem_schema_errors']) for entry in entries)
            out = {'task': a.task, 'episode_count': len(entries), 'episodes': entries}
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open('x', encoding='utf-8') as handle:
            json.dump(out, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    except (OSError, ValueError, RuntimeError) as error:
        p.error(str(error))
    print(f'Wrote {a.output}. SEM schema errors: {errors}')
    if a.dataset_root and not all(entry['has_episode_instructions'] for entry in entries):
        print('Some episodes lack seen/unseen metadata. Review language generation before packing.')
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
