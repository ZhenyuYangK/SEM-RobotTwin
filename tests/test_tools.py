import ast
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from audit_urdf import inspect_urdf
from audit_sources import config_constants
from discover_tasks import validate_config
from make_eval_config import create_files
from make_training_config import write_config
from summarize_eval import aggregate
from estimate_budget import estimate
from estimate_storage import estimate_storage
from create_cloud_runbook import runbook


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
            (env / 'place_empty_cup.py').write_text('# stub')
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


if __name__ == '__main__':
    unittest.main()
