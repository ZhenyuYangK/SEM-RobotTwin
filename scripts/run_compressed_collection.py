#!/usr/bin/env python3
"""Collect with the locked RoboTwin entry point and lossless HDF5 depth compression."""
import argparse
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

from discover_tasks import require_locked_task


COLLECTOR = 'script/collect_data.py'
HDF5_WRITER = 'envs/utils/pkl2hdf5.py'


def compress_observation_depth(create_dataset):
    def write_dataset(group, name, *args, **kwargs):
        data = kwargs.get('data')
        if name == 'depth' and group.name.startswith('/observation/') and getattr(data, 'ndim', None) == 3:
            kwargs.update(chunks=(1, *data.shape[1:]), compression='gzip', compression_opts=1, shuffle=True)
        return create_dataset(group, name, *args, **kwargs)

    return write_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--task', required=True)
    args = parser.parse_args()
    try:
        pinned = require_locked_task(args.workspace, args.task, COLLECTOR, HDF5_WRITER)
        runtime = args.runtime.resolve(strict=True)
        if runtime == pinned:
            raise ValueError('Use a separate runtime copy')
        for name in (COLLECTOR, HDF5_WRITER):
            if (runtime / name).read_bytes() != (pinned / name).read_bytes():
                raise ValueError(f'Runtime file differs from the locked source: {name}')
    except (OSError, ValueError) as error:
        parser.error(str(error))

    import h5py

    collector = runtime / COLLECTOR
    os.chdir(runtime)
    sys.path.insert(0, str(collector.parent))
    sys.argv = [str(collector), args.task, 'demo_clean']
    writer = compress_observation_depth(h5py.Group.create_dataset)
    with patch.object(h5py.Group, 'create_dataset', writer):
        runpy.run_path(str(collector), run_name='__main__')


if __name__ == '__main__':
    main()
