"""Run MegaSAM's UniDepth depth script with the model in eval mode.

The pinned MegaSAM script (third_party/mega-sam/UniDepth/scripts/demo_mega-sam.py)
loads UniDepthV2 with from_pretrained() and never calls model.eval(), so the
network runs in training mode (issue #19). This wrapper makes from_pretrained()
return the model in eval mode and then runs the unmodified script.

Usage (from the mega-sam root, as tools/run_megasam.py does):
    python megasam_unidepth_eval.py UniDepth/scripts/demo_mega-sam.py [script args...]
"""
import runpy
import sys

from unidepth.models import UniDepthV2

_from_pretrained = UniDepthV2.from_pretrained


def _from_pretrained_eval(*args, **kwargs):
    return _from_pretrained(*args, **kwargs).eval()


UniDepthV2.from_pretrained = _from_pretrained_eval

if __name__ == "__main__":
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_path(script, run_name="__main__")
