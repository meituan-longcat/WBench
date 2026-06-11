"""
Compatibility stubs for optional third-party dependencies.

Import this module before importing DA3 or other third-party libs that have
heavy optional deps (moviepy, trimesh, plyfile, pycolmap, gsplat, evo, etc.).

Usage:
    import src.compat  # noqa: F401 — must be imported before DA3
"""
import sys
import types
import importlib.machinery


def _stub(name):
    """Register a placeholder module under `name` with a real ModuleSpec.

    A bare types.ModuleType has __spec__ = None. importlib.util.find_spec(name)
    reads sys.modules[name].__spec__ and raises "ValueError: <name>.__spec__ is
    None" on such a placeholder. HF datasets probes find_spec("trimesh") at import
    time, so a spec-less trimesh stub crashed every metric that imports datasets
    (e.g. hpsv3_quality). Attaching a ModuleSpec keeps the stub importable while
    find_spec stays happy.
    """
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    sys.modules[name] = mod
    return mod


_OPTIONAL_STUBS = [
    "pycolmap",
    "gsplat",
    "gsplat.rendering",
    "moviepy",
    "moviepy.editor",
    "trimesh",
]

for _mod in _OPTIONAL_STUBS:
    if _mod not in sys.modules:
        _stub(_mod)

# evo — trajectory evaluation library used by DA3 for pose alignment
if "evo" not in sys.modules:
    _evo = _stub("evo")
    _evo_core = _stub("evo.core")
    _evo_traj = _stub("evo.core.trajectory")
    _evo_metrics = _stub("evo.core.metrics")

    class _PosePath3D:
        def __init__(self, *a, **k): pass
    class _PoseTrajectory3D(_PosePath3D):
        pass

    _evo_traj.PosePath3D = _PosePath3D
    _evo_traj.PoseTrajectory3D = _PoseTrajectory3D
    _evo_metrics.APE = type("APE", (), {})
    _evo_metrics.RPE = type("RPE", (), {})

    _evo.core = _evo_core
    _evo_core.trajectory = _evo_traj
    _evo_core.metrics = _evo_metrics

# plyfile needs PlyData/PlyElement attributes
if "plyfile" not in sys.modules:
    _plyfile = _stub("plyfile")
    _plyfile.PlyData = type("PlyData", (), {})
    _plyfile.PlyElement = type("PlyElement", (), {"describe": staticmethod(lambda *a, **k: None)})
