import ast
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from audit_urdf import compare_urdfs, inspect_urdf
from discover_tasks import validate_config
from make_eval_config import create_files, projection_config
from make_training_config import write_config
from summarize_eval import aggregate, eval_log_row
from estimate_budget import estimate
from estimate_storage import estimate_storage
from create_cloud_runbook import runbook
from inspect_hdf5 import dataset_episodes, sem_schema_errors
from prepare_collection import collection_config


class TestURDF(unittest.TestCase):
    def test_teacher_urdf_structure(self):
        result = inspect_urdf(ROOT / 'teacher_inputs/arx5_description_isaac.urdf')
        self.assertTrue(result['structural_valid'])
        self.assertEqual(result['robot_name'], 'arx5_description')
        self.assertEqual((result['links'], result['joints']), (54, 53))
        self.assertEqual(result['mesh_paths_unique'], 30)

    def test_bad_joint_parent(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'bad.urdf'
            path.write_text('<robot name="bad"><link name="a"/><joint name="j" type="fixed"><parent link="missing"/><child link="a"/></joint></robot>')
            r = inspect_urdf(path)
            self.assertFalse(r['structural_valid'])

    def test_disconnected_urdf_tree_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'disconnected.urdf'
            path.write_text('<robot name="bad"><link name="a"/><link name="b"/></robot>')
            self.assertFalse(inspect_urdf(path)['structural_valid'])

    def test_reports_same_joint_limit_change(self):
        xml = ('<robot name="r"><link name="a"/><link name="b"/>'
               '<joint name="j" type="revolute"><parent link="a"/><child link="b"/>'
               '<limit lower="-1" upper="%s"/></joint></robot>')
        with tempfile.TemporaryDirectory() as d:
            teacher = Path(d) / 'teacher.urdf'
            reference = Path(d) / 'reference.urdf'
            teacher.write_text(xml % '1')
            reference.write_text(xml % '2')
            diff = compare_urdfs(teacher, reference)
            limits = diff['common_joint_attribute_differences']['j']['limit']
            self.assertEqual((limits['teacher']['upper'], limits['reference']['upper']), ('1', '2'))


class TestEval(unittest.TestCase):
    def test_success_rate_and_multiple_seeds(self):
        result, skipped = aggregate([
            {'task_name': 'place_empty_cup', 'episodes': '100', 'successes': '80'},
            {'task_name': 'place_empty_cup', 'episodes': '50', 'successes': '40'},
            {'task_name': 'blank', 'episodes': '', 'successes': ''},
        ])
        self.assertEqual(result[0]['episodes'], 150)
        self.assertEqual(result[0]['successes'], 120)
        self.assertEqual(result[0]['success_rate_pct'], 80.0)
        self.assertEqual(skipped, 1)

    def test_bad_count_rejected(self):
        for s in ['101', '-1', 'abc', '']:
            with self.subTest(s=s), self.assertRaises(ValueError):
                aggregate([{'task_name': 't', 'episodes': '100', 'successes': s}])

    def test_eval_config_teacher_constraints(self):
        yaml, script = create_files('place_empty_cup', 'checkpoints/place_empty_cup/model.safetensors',
                                    'config_sem_robotwin.py', 5, ROOT / 'templates')
        self.assertIn('policy_name: sem_policy', yaml)
        self.assertIn('instruction_type: unseen', yaml)
        self.assertIn('seed=10000', script)
        self.assertIn('task_config=demo_clean', script)
        self.assertIn('expert_data_num="5"', script)

    def test_eval_task_injection_rejected(self):
        with self.assertRaises(ValueError):
            create_files('t;rm -rf /', 'model.safetensors', 'config_sem_robotwin.py', 5, ROOT / 'templates')

    def test_eval_projection_cast_precedes_matrix_multiplication(self):
        transforms = 'robo_orchard_lab.dataset.robotwin.transforms'
        module = ModuleType(transforms)
        module.ConvertDataType = object()
        module.GetProjectionMat = object()
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {transforms: module}):
            original = Path(directory) / 'train config.py'
            original.write_text(
                f'from {transforms} import GetProjectionMat\n'
                'config = {}\n'
                'def build_model(config): return config\n'
                'def build_transforms(config, calibration=None):\n'
                '    return ["train"], [{"type": GetProjectionMat}]\n'
            )
            wrapper = Path(directory) / 'eval_config.py'
            wrapper.write_text(projection_config(original))
            train, validation = runpy.run_path(wrapper)['build_transforms']({})
        self.assertEqual(train, ['train'])
        self.assertIs(validation[0]['type'], module.ConvertDataType)
        self.assertIs(validation[1]['type'], module.GetProjectionMat)
        self.assertEqual(validation[0]['convert_map'], dict.fromkeys(
            ('intrinsic', 'T_world2cam', 'T_base2world'), 'float32',
        ))

    def test_eval_log_requires_completed_count_sequence(self):
        log = ('Task Name: place_empty_cup\nPolicy Name: sem_policy\n'
               'Success rate: \x1b[96m1/1\x1b[0m => 100%\n'
               'Success rate: 1/2 => 50%\nData has been saved to path/_result.txt\n')
        self.assertEqual(eval_log_row(log, 'place_empty_cup', 2)['successes'], '1')
        for invalid in (log.replace('1/2', '1/3'), log.replace('Data has been saved to ', '')):
            with self.subTest(log=invalid), self.assertRaises(ValueError):
                eval_log_row(invalid, 'place_empty_cup', 2)

    def test_eval_stats_reject_mixed_checkpoint_and_repeated_seed(self):
        row = {'task_name': 'place_empty_cup', 'episodes': '100', 'successes': '80',
               'checkpoint': 'checkpoint-0', 'seed': '10000'}
        for second in (row, dict(row, checkpoint='checkpoint-1', seed='10001')):
            with self.subTest(row=second), self.assertRaises(ValueError):
                aggregate([row, second])


class TestTrainAndSource(unittest.TestCase):
    def test_config_patch(self):
        src = '# 中文注释\nconfig = dict(task_names=["old"], multi_task=True, max_step=100000, data_path="x", urdf="y")\ndef build_model(x):\n    return x\n'
        patched = write_config(src, {'task_names': ['place_empty_cup'], 'multi_task': False, 'max_step': 1000, 'data_path': '/data/lmdb', 'urdf': '/path/to.urdf'})
        ast.parse(patched)
        self.assertIn('task_names=[\'place_empty_cup\']', patched)
        self.assertIn('multi_task=False', patched)
        self.assertIn('def build_model', patched)

    def test_config_rejects_unknown_keys(self):
        with self.assertRaises(ValueError):
            write_config('config=dict(x=1)', {'task_names': []})

    def test_task_check_without_source(self):
        with tempfile.TemporaryDirectory() as d:
            issues, available, selected = validate_config(d, {'tasks': [{'name': 'place_empty_cup', 'status': 'pending_source_validation', 'include': True}]})
            self.assertGreater(len(issues), 0)
            self.assertEqual(available, 0)
            self.assertEqual(selected, 1)

    def test_task_check_with_mock_source(self):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / 'src/RoboTwin/envs'
            env.mkdir(parents=True)
            (env / 'place_empty_cup.py').write_text(
                'class place_empty_cup:\n'
                '    def setup_demo(self): pass\n'
                '    def play_once(self): pass\n'
                '    def check_success(self): pass\n'
            )
            prompts = env.parent / 'description/task_instruction'
            prompts.mkdir(parents=True)
            (prompts / 'place_empty_cup.json').write_text('{"seen": ["x"], "unseen": ["y"]}')
            result, _, selected = validate_config(d, {'tasks': [{'name': 'place_empty_cup', 'status': 'verified_in_pinned_source', 'include': True}]})
            self.assertEqual(result, [])
            self.assertEqual(selected, 1)

    def test_runbook_rejects_unverified(self):
        with self.assertRaises(ValueError):
            runbook({'tasks': [{'name':'place_empty_cup', 'include':True, 'status':'pending_source_validation'}], 'eval_seed':10000, 'train_mode':'single_task', 'eval_policy':'sem_policy', 'task_config':'demo_clean'})

    def test_budget(self):
        r = estimate(5, 100000, 20, 1.98)
        self.assertAlmostEqual(r['training_hours_all_tasks'], 166.6666666667)
        self.assertAlmostEqual(r['estimated_gpu_cost_cny'], 330)

    def test_storage(self):
        r = estimate_storage(1024**3, 1024**3, 10, 5, 100, 25)
        self.assertEqual(r['episodes'], 500)
        self.assertAlmostEqual(r['raw_plus_lmdb_gib'], 100)
        self.assertAlmostEqual(r['total_with_extra_gib'], 125)

    def test_storage_invalid(self):
        with self.assertRaises(ValueError):
            estimate_storage(1, 1, 0, 5, 100, 25)

    def test_bad_budget(self):
        with self.assertRaises(ValueError):
            estimate(0, 1000, 10, 2)


class TestCollection(unittest.TestCase):
    def test_collection_config_enables_required_fields(self):
        source = ('episode_num: 100\nsave_path: ./data\ncollect_data: true\ncamera:\n'
                  '  collect_head_camera: true\ndata_type:\n  rgb: true\n'
                  '  qpos: true\n  depth: false\n  endpose: false\n')
        output = collection_config(source, 10)
        for expected in ('episode_num: 10', 'save_path: ./data', '  depth: true', '  endpose: true'):
            self.assertIn(expected, output.splitlines())
        with self.assertRaises(ValueError):
            collection_config(source.replace('./data', '/other/location'), 10)

    def test_dataset_seed_and_episode_index(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / 'place_empty_cup/demo_clean'
            (base / 'data').mkdir(parents=True)
            (base / 'seed.txt').write_text('6 42 ')
            for index in range(2):
                (base / 'data' / f'episode{index}.hdf5').touch()
            self.assertEqual([seed for _, seed in dataset_episodes(Path(d), 'place_empty_cup', 2)], [6, 42])
            (base / 'data/episode1.hdf5').rename(base / 'data/episode3.hdf5')
            with self.assertRaises(ValueError):
                dataset_episodes(Path(d), 'place_empty_cup', 2)

    def test_sem_schema_requires_depth_and_aligned_frames(self):
        nodes = []
        def dataset(path, shape, kind='f'):
            nodes.append({'path': path, 'kind': 'dataset', 'shape': shape,
                          'dtype_kind': kind, 'dtype': kind})
        dataset('endpose', [5, 14])
        dataset('joint_action/vector', [5, 14])
        for camera in ('head_camera', 'left_camera', 'right_camera'):
            root = f'observation/{camera}'
            nodes.append({'path': root, 'kind': 'group'})
            dataset(f'{root}/rgb', [5], 'S')
            dataset(f'{root}/intrinsic_cv', [5, 3, 3])
            dataset(f'{root}/extrinsic_cv', [5, 3, 4])
            dataset(f'{root}/depth', [5, 6, 8])
        self.assertEqual(sem_schema_errors(nodes), [])
        nodes[-2]['shape'] = [4, 3, 4]
        nodes.pop()
        errors = sem_schema_errors(nodes)
        self.assertTrue(any('right_camera/depth' in error for error in errors))
        self.assertTrue(any('right_camera/extrinsic_cv' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
