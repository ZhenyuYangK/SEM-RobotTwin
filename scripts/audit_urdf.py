#!/usr/bin/env python3
"""Structural URDF audit: standard library, no ROS/GUI/CUDA required."""
import argparse
import json
import hashlib
import subprocess
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
    duplicate_link_names = sorted({name for name in names if names.count(name) > 1}, key=str)
    duplicate_joint_names = sorted({name for name in joint_names if joint_names.count(name) > 1}, key=str)
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
        if not any(x.is_file() for x in candidate_paths):
            unresolved.append(mesh)
    root_links = sorted(known_links - set(parent_of), key=str)
    cyclic_links = set()
    for link in known_links:
        current = link
        route = set()
        while current in parent_of:
            if current in route:
                cyclic_links.add(current)
                break
            route.add(current)
            current = parent_of[current]
    result = {
        'file': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
        'robot_name': root.get('name'), 'links': len(links), 'joints': len(joints),
        'joint_types': {joint_type: sum(j.get('type') == joint_type for j in joints) for joint_type in sorted({j.get('type') for j in joints}, key=str)},
        'mesh_paths_unique': len(meshes), 'unresolved_meshes': unresolved,
        'duplicate_link_names': duplicate_link_names, 'duplicate_joint_names': duplicate_joint_names,
        'broken_joint_references': bad_joints,
        'root_links': root_links,
        'cyclic_links': sorted(cyclic_links, key=str),
        'mesh_paths': meshes,
        'notes': 'This is a static XML check only. Kinematics, joint indices and SAPIEN loading need separate verification.'
    }
    result['structural_valid'] = bool(
        len(root_links) == 1 and all(names) and all(joint_names)
        and not duplicate_link_names and not duplicate_joint_names and not bad_joints
        and not cyclic_links
    )
    return result


def compare_urdfs(teacher, reference, asset_roots=None):
    def details(path):
        root = ET.parse(path).getroot()
        links = {link.attrib['name'] for link in root.findall('link')}
        joints = {
            node.attrib['name']: {
                'type': node.get('type'),
                **{tag: node.find(tag).attrib if node.find(tag) is not None else None
                   for tag in ('parent', 'child', 'origin', 'axis', 'limit', 'mimic')},
            }
            for node in root.findall('joint')
        }
        return links, joints

    teacher_links, teacher_joints = details(teacher)
    ref_links, ref_joints = details(reference)
    return {
        'reference': inspect_urdf(reference, asset_roots),
        'links_only_teacher': sorted(teacher_links - ref_links),
        'links_only_reference': sorted(ref_links - teacher_links),
        'joints_only_teacher': sorted(teacher_joints.keys() - ref_joints.keys()),
        'joints_only_reference': sorted(ref_joints.keys() - teacher_joints.keys()),
        'common_joint_attribute_differences': {
            name: {key: {'teacher': value, 'reference': ref_joints[name][key]}
                   for key, value in teacher_joints[name].items() if value != ref_joints[name][key]}
            for name in sorted(teacher_joints.keys() & ref_joints.keys())
            if teacher_joints[name] != ref_joints[name]
        },
    }


def reference_inventory(robotwin):
    checkout = Path(robotwin)
    if not (checkout / '.git').exists():
        return {'status': 'checkout_missing'}
    result = subprocess.run(
        ['git', '-C', str(checkout), 'ls-tree', '-r', '--name-only', 'HEAD'],
        capture_output=True, text=True, check=True,
    )
    tracked = [item for item in result.stdout.splitlines() if item.lower().endswith('.urdf')]
    available = sorted(str(path.relative_to(checkout)) for path in (checkout / 'assets').rglob('*.urdf'))
    return {'status': 'references_present' if available else 'no_local_asset_urdf',
            'tracked_urdfs': tracked, 'local_asset_urdfs': available}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--urdf', required=True)
    p.add_argument('--asset-root', action='append', default=[], help='Optional asset root(s) for mesh lookup')
    p.add_argument('--compare', help='Local reference URDF for a structural comparison')
    p.add_argument('--robotwin', help='Inventory URDF availability in this local RoboTwin checkout')
    p.add_argument('--output', default='reports/urdf_audit.json')
    args = p.parse_args()
    report = inspect_urdf(args.urdf, args.asset_root)
    if args.robotwin:
        report['robotwin_reference_inventory'] = reference_inventory(args.robotwin)
    if args.compare:
        report['comparison'] = compare_urdfs(args.urdf, args.compare, args.asset_root)
        reference = report['comparison']['reference']
        report['comparison']['same_hash'] = report['sha256'] == reference['sha256']
        report['comparison']['meshes_only_teacher'] = sorted(set(report['mesh_paths']) - set(reference['mesh_paths']))
        report['comparison']['meshes_only_reference'] = sorted(set(reference['mesh_paths']) - set(report['mesh_paths']))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"URDF={report['robot_name']}; links={report['links']}; joints={report['joints']}; unresolved mesh paths={len(report['unresolved_meshes'])}")
    print(f'Structural check: {"PASS" if report["structural_valid"] else "FAIL"}; report={out}')
    if not report['structural_valid']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
