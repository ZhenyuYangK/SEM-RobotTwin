from runpy import run_path

from robo_orchard_lab.dataset.robotwin.transforms import ConvertDataType, GetProjectionMat


original = run_path('/root/sj-tmp/SEM-RoboTwin/runs/c7-formal/adjust_bottle/staged/train_config.py')
config = original['config']
build_model = original['build_model']


def build_transforms(config, calibration=None):
    train, validation = original['build_transforms'](config, calibration)
    index, = (i for i, transform in enumerate(validation) if transform['type'] is GetProjectionMat)
    match_projection_dtype = dict(type=ConvertDataType, convert_map={
        name: 'float32' for name in ('intrinsic', 'T_world2cam', 'T_base2world')
    })
    return train, [*validation[:index], match_projection_dtype, *validation[index:]]
