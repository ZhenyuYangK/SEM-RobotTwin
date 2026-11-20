#!/usr/bin/env python3
"""Structural URDF audit: standard library, no ROS/GUI/CUDA required."""
import argparse
import json
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


def inspect_urdf(path, asset_roots=None):
    path = Path(path)
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    if root.tag != 'robot':
        raise ValueError(f'Root must be robot, got {root.tag}')
    links = root.findall('link')
    joints = root.findall('joint')
    names = [link.get('name') for link in links]
    joint_names = [joint.get('name') for joint in joints]
    duplicate_link_names = sorted({name for name in names if names.count(name) > 1})
    duplicate_joint_names = sorted({name for name in joint_names if joint_names.count(name) > 1})
    known_links = set(names)
    bad_joints = []
    parent_of = {}
    for joint in joints:
        name = joint.get('name', '')
        p = joint.find('parent')
        c = joint.find('child')
        parent = p.get('link') if p is not None else None
        child = c.get('link') if c is not None else None
        if parent not in known_links or child not in known_links or child == parent:
            bad_joints.append({'joint': name, 'parent': parent, 'child': child})
        if child in parent_of:
            bad_joints.append({'joint': name, 'problem': 'child has multiple parent joints', 'child': child})
        parent_of[child] = parent
    meshes = sorted({element.get('filename') for element in root.findall('.//mesh') if element.get('filename')})
    unresolved = []
    roots = [Path(p) for p in (asset_roots or [])]
    for mesh in meshes:
        if mesh.startswith('package://'):
            relative = mesh.removeprefix('package://')
        else:
            relative = mesh
        candidate_paths = [path.parent / relative] + [p / relative for p in roots]
        if not any(x.exists() for x in candidate_paths):
            unresolved.append(mesh)
    result = {
        'file': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
        'robot_name': root.get('name'), 'links': len(links), 'joints': len(joints),
        'joint_types': {joint_type: sum(j.get('type') == joint_type for j in joints) for joint_type in sorted({j.get('type') for j in joints})},
        'mesh_paths_unique': len(meshes), 'unresolved_meshes': unresolved,
        'duplicate_link_names': duplicate_link_names, 'duplicate_joint_names': duplicate_joint_names,
        'broken_joint_references': bad_joints,
        'root_links': sorted(known_links - set(parent_of)),
        'notes': 'This is a static XML check only. Kinematics, joint indices and SAPIEN loading need separate verification.'
    }
    result['structural_valid'] = not duplicate_link_names and not duplicate_joint_names and not bad_joints
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--urdf', required=True)
    p.add_argument('--asset-root', action='append', default=[], help='Optional asset root(s) for mesh lookup')
    p.add_argument('--compare', help='Optional comparison URDF; report SHA256 and joint name/type differences')
    p.add_argument('--output', default='reports/urdf_audit.json')
    args = p.parse_args()
    report = inspect_urdf(args.urdf, args.asset_root)
    if args.compare:
        other = inspect_urdf(args.compare, args.asset_root)
        def joints(path):
            r = ET.parse(path).getroot()
            return {j.get('name'): j.get('type') for j in r.findall('joint')}
        original, upstream = joints(args.urdf), joints(args.compare)
        report['comparison'] = {
            'with': args.compare, 'same_hash': report['sha256'] == other['sha256'],
            'joints_only_teacher': sorted(set(original) - set(upstream)),
            'joints_only_reference': sorted(set(upstream) - set(original)),
            'joint_type_differences': {k: [original[k], upstream[k]] for k in sorted(set(original) & set(upstream)) if original[k] != upstream[k]},
            'links_reference': other['links'], 'joints_reference': other['joints']
        }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"URDF={report['robot_name']}; links={report['links']}; joints={report['joints']}; unresolved mesh paths={len(report['unresolved_meshes'])}")
    print(f'Structural check: {"PASS" if report["structural_valid"] else "FAIL"}; report={out}')
    if not report['structural_valid']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
