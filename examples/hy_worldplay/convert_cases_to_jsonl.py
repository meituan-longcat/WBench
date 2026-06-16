import json
import glob
import re
import sys
import os

# 单键 → navigation 映射
# move: [forward, right], yaw: left(-)/right(+), pitch: down(-)/up(+)
SINGLE_KEY_NAV = {
    'W':     {"move": [1, 0],  "yaw": 0,  "pitch": 0},
    'S':     {"move": [-1, 0], "yaw": 0,  "pitch": 0},
    'A':     {"move": [0, -1], "yaw": 0,  "pitch": 0},
    'D':     {"move": [0, 1],  "yaw": 0,  "pitch": 0},
    '→':    {"move": [0, 0],  "yaw": 1,  "pitch": 0},
    'right': {"move": [0, 0],  "yaw": 1,  "pitch": 0},
    '←':    {"move": [0, 0],  "yaw": -1, "pitch": 0},
    'left':  {"move": [0, 0],  "yaw": -1, "pitch": 0},
    '↑':    {"move": [0, 0],  "yaw": 0,  "pitch": 1},
    'up':    {"move": [0, 0],  "yaw": 0,  "pitch": 1},
    '↓':    {"move": [0, 0],  "yaw": 0,  "pitch": -1},
    'down':  {"move": [0, 0],  "yaw": 0,  "pitch": -1},
    'stop':  {"move": [0, 0],  "yaw": 0,  "pitch": 0},
}

NAV_KEYS = set(SINGLE_KEY_NAV.keys())


def action_to_navigation(action_str):
    """将 action 字符串转换为 navigation 格式。
    支持单键 (W) 和组合键 (W+A, W+D 等，以 '+' 分隔)。
    返回 None 表示非导航动作。
    """
    parts = [p.strip() for p in action_str.split('+')]
    if not all(p in NAV_KEYS for p in parts):
        return None
    # 叠加各分量
    fwd, right, yaw, pitch = 0, 0, 0, 0
    for p in parts:
        nav = SINGLE_KEY_NAV[p]
        fwd += nav["move"][0]
        right += nav["move"][1]
        yaw += nav["yaw"]
        pitch += nav["pitch"]
    return {"move": [fwd, right], "yaw": yaw, "pitch": pitch}


def has_navigation_action(case):
    """检查 case 是否包含至少一个导航动作"""
    for interaction in case.get('interactions', []):
        action = interaction.get('action', interaction.get('action_key', ''))
        if action_to_navigation(action) is not None:
            return True
    return False


def has_lr_rotation(case):
    """检查第三人称 case 是否包含左/右旋转导航动作（←/→/left/right）。"""
    if case.get('settings', {}).get('perspective', 'third_person') != 'third_person':
        return False
    lr_keys = {'→', 'right', '←', 'left'}
    for interaction in case.get('interactions', []):
        action = interaction.get('action', interaction.get('action_key', ''))
        parts = [p.strip() for p in action.split('+')]
        if any(p in lr_keys for p in parts):
            return True
    return False


# ---------------------------------------------------------------------------
# Prompt 构造：从结构化 settings 字段组装，而非直接复制 image_prompt
# ---------------------------------------------------------------------------

def _build_scene_desc(settings):
    """从 scene 字段构建场景描述片段。"""
    scene = settings.get('scene', {})
    env = scene.get('environment', '')
    attr = scene.get('attribute', '')
    name = scene.get('name', '').replace('_', ' ')
    parts = [p for p in [attr, env, name] if p]
    if not parts:
        return ''
    return ' '.join(parts)


def _build_style_tag(settings):
    """返回风格标签（如 cinematic style, cartoon style）。"""
    style = settings.get('style', '')
    if not style:
        return ''
    return f"{style} style"


def _build_subject_desc(settings):
    """返回主体描述（仅第三人称有 subject 时）。
    自动去除 desc 中常见的 "The main subject is" 前缀，避免拼接重复。
    同时去除 desc 中内嵌的相机位置描述（这部分由视角模板统一处理）。
    """
    subject = settings.get('subject')
    if not subject:
        return ''
    desc = subject.get('desc', '').strip()
    if not desc:
        return ''
    # 去除 "The main subject is " 前缀
    for prefix in ('The main subject is ', 'the main subject is '):
        if desc.startswith(prefix):
            desc = desc[len(prefix):]
            break
    # 去除内嵌的相机位置描述句（"The camera is positioned ..." 到句末）
    desc = re.sub(r'\s*The camera is positioned[^.]*\.?', '', desc, flags=re.IGNORECASE).strip()
    # 去除 "This is a classic third-person ..." 之类的残留句
    desc = re.sub(r'\s*This is a classic[^.]*\.?', '', desc, flags=re.IGNORECASE).strip()
    # 清理尾部多余标点
    desc = desc.rstrip(',.')
    return desc


def _build_subject_movement(settings):
    """返回主体运动特征描述。"""
    subject = settings.get('subject')
    if not subject:
        return ''
    return subject.get('movement', '')


def _build_rule_desc(settings):
    """返回物理/规则描述（仅非 default 或有具体内容时）。"""
    rule = settings.get('rule')
    if not rule:
        return ''
    desc = rule.get('desc', '')
    if desc.strip().lower() in ('', 'normal physics', 'normal physics.', 'standard physics', 'standard physics.'):
        return ''
    return desc


def _build_tracking_desc(settings):
    """返回 tracking object 描述。"""
    track = settings.get('tracking_object')
    if not track:
        return ''
    return track.get('desc', '')


def build_base_prompt(case):
    """根据 case 的结构化字段组装基础 prompt（第 0 段使用）。

    第三人称：强调主体居中、相机跟随主体
    第一人称：强调沉浸视角、附属物跟随视线
    """
    settings = case.get('settings', {})
    perspective = settings.get('perspective', 'third_person')
    description = case.get('description', '')

    scene_desc = _build_scene_desc(settings)
    style_tag = _build_style_tag(settings)
    subject_desc = _build_subject_desc(settings)
    subject_movement = _build_subject_movement(settings)
    rule_desc = _build_rule_desc(settings)
    tracking_desc = _build_tracking_desc(settings)

    parts = []

    # 1) 场景总述：优先用 case.description，否则用 scene 字段拼接
    if description:
        parts.append(description)
    elif scene_desc:
        parts.append(scene_desc.capitalize() + '.')

    # 2) 风格标签
    if style_tag:
        parts.append(style_tag.capitalize() + '.')

    # 3) 视角与主体/相机关系
    if perspective == 'third_person':
        if subject_desc:
            parts.append(
                f"Third-person perspective. The main subject is {subject_desc}, "
                f"centered in the frame. The camera follows behind and slightly above the subject."
            )
        else:
            parts.append(
                "Third-person perspective. The camera follows behind and slightly above "
                "the central object in the scene."
            )
        if subject_movement:
            parts.append(f"The subject {subject_movement}.")
    else:
        # first_person
        parts.append(
            "First-person perspective. The camera represents the viewer's eyes. "
            "All attached objects (e.g. held items, HUD elements) move with the viewer's gaze."
        )

    # 4) 追踪目标
    if tracking_desc:
        parts.append(f"Key landmark: {tracking_desc}.")

    # 5) 特殊物理/规则
    if rule_desc:
        parts.append(rule_desc)

    # 6) 质量后缀
    parts.append("High quality, detailed.")

    return ' '.join(parts)


def build_segment_prompt(case, seg_index, interaction, base_prompt, short=False):
    """为第 seg_index 段构造 prompt。

    - navigation 段：第 0 段用 base_prompt，后续段留空
    - subject_action 段：将 action 与场景上下文结合
    - event_edit 段：将事件描述与场景上下文结合
    - short 模式下不拼接 base_prompt，仅保留交互内容
    """
    action = interaction.get('action', interaction.get('action_key', 'stop'))
    interaction_type = interaction.get('type', 'navigation')
    nav = action_to_navigation(action)

    if nav is not None:
        # 导航动作：动作信息编码在 navigation 字段
        if short:
            return ""
        return base_prompt if seg_index == 0 else ""

    # 非导航动作：直接使用 action 文本作为 prompt
    action_prompt = action

    if short:
        return action_prompt
    return (base_prompt + ' ' + action_prompt).strip() if seg_index == 0 else action_prompt


def convert_case(case, data_root, duration=4, short=False):
    """将单个 case 转换为 navigation 格式。
    data_root: WBench 数据根目录 (initial_image 相对于此目录)
    short: 若为 True，第0段 prompt 不拼接 base_setting，只保留 interaction 内容
    """
    case_id = case['id']
    settings = case.get('settings', {})
    interactions = case.get('interactions', [])
    perspective = settings.get('perspective', 'third_person')

    # 图片路径：相对于 data_root 解析
    image_path = settings.get('initial_image', '')
    if image_path and not os.path.isabs(image_path):
        image_path = os.path.abspath(os.path.join(data_root, image_path))

    # 组装基础 prompt
    base_prompt = build_base_prompt(case)

    result = {
        "name": f"case_{case_id}",
        "image_path": image_path,
        "perspective": perspective,
        "prompt": {},
        "navigation": {},
        "chunk_length": {},
        "rewrite": True
    }

    for i, interaction in enumerate(interactions):
        idx = str(i)
        action = interaction.get('action', interaction.get('action_key', 'stop'))

        nav = action_to_navigation(action)
        if nav:
            result["navigation"][idx] = nav
        else:
            result["navigation"][idx] = {"move": [0, 0], "yaw": 0, "pitch": 0}

        result["prompt"][idx] = build_segment_prompt(
            case, i, interaction, base_prompt, short=short
        )
        result["chunk_length"][idx] = duration

    return result


def load_cases_from_dir(cases_dir):
    """从 cases/ 目录加载所有 case_*.json 文件"""
    pattern = os.path.join(cases_dir, 'case_*.json')
    files = sorted(glob.glob(pattern))
    cases = []
    for f in files:
        with open(f, 'r', encoding='utf-8') as fh:
            cases.append(json.load(fh))
    return cases


def main(target_dir, case_ids=None, nav_only=False, short=False, skiplr=False,
         onlylr=False, output=None):
    cases_dir = os.path.join(target_dir, 'cases')
    # data_root: initial_image 路径 (如 "data/wbench_m2.5/images/...") 相对的根目录
    # cases_dir 的典型结构: <root>/data/wbench_m2.5/cases/
    # initial_image 形如: data/wbench_m2.5/images/...
    # 因此 data_root = target_dir 的上两级
    data_root = os.path.abspath(os.path.join(target_dir, '..', '..'))

    if output:
        output_path = output
    elif short:
        output_name = 'all_samples_short.jsonl'
        output_path = os.path.join(target_dir, output_name)
    elif nav_only:
        output_name = 'navigation_samples.jsonl'
        output_path = os.path.join(target_dir, output_name)
    else:
        output_name = 'all_samples.jsonl'
        output_path = os.path.join(target_dir, output_name)

    cases = load_cases_from_dir(cases_dir)
    print(f"Loaded {len(cases)} cases from {cases_dir}")

    if case_ids is not None:
        case_by_id = {c['id']: c for c in cases}
        selected = []
        for cid in case_ids:
            if cid not in case_by_id:
                print(f"Warning: case {cid} not found")
                continue
            selected.append(case_by_id[cid])
    else:
        selected = cases

    if nav_only:
        before = len(selected)
        selected = [c for c in selected if has_navigation_action(c)]
        print(f"nav_only: kept {len(selected)}/{before} cases with navigation actions")

    if skiplr:
        before = len(selected)
        selected = [c for c in selected if not has_lr_rotation(c)]
        print(f"skiplr: kept {len(selected)}/{before} cases after removing third-person LR rotation")

    if onlylr:
        before = len(selected)
        selected = [c for c in selected if has_lr_rotation(c)]
        print(f"onlylr: kept {len(selected)}/{before} third-person cases with LR rotation")

    results = [convert_case(c, data_root, short=short) for c in selected]

    with open(output_path, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f"Done! Saved {len(results)} samples to {output_path}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("target_dir",
                        help="Directory containing cases/ subdirectory (e.g. data/wbench_m2.5/)")
    parser.add_argument("case_ids", nargs="*", type=int,
                        help="Optional case IDs to convert (default: all)")
    parser.add_argument("--nav_only", action="store_true",
                        help="Only keep cases with navigation actions (W/S/A/D/arrows)")
    parser.add_argument("--short", action="store_true",
                        help="Short prompt mode: first segment uses only interaction content, "
                             "no base_setting prefix. Outputs all_samples_short.jsonl")
    parser.add_argument("--skiplr", action="store_true",
                        help="Skip third-person cases that contain left/right rotation actions "
                             "(←/→/left/right)")
    parser.add_argument("--onlylr", action="store_true",
                        help="Only keep third-person cases with left/right rotation actions "
                             "(inverse of --skiplr)")
    parser.add_argument("--output", type=str, default=None,
                        help="Custom output path (default: auto-named in target_dir)")
    args = parser.parse_args()

    case_ids = args.case_ids if args.case_ids else None
    main(args.target_dir, case_ids, nav_only=args.nav_only, short=args.short,
         skiplr=args.skiplr, onlylr=args.onlylr, output=args.output)
