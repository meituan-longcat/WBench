import unittest

import numpy as np

from examples.hy_worldplay.navigation_to_poses import (
    generate_orbit_trajectory as generate_hy_orbit_trajectory,
)
from src.models.camera.poses import generate_orbit_trajectory
from src.models.navigation import action_to_navigation
from src.models.text.prompt_builder import build_turn_prompt


class ThirdPersonDirectionConventionTest(unittest.TestCase):
    def test_actions_map_left_and_right_to_opposite_yaw_signs(self):
        self.assertEqual(action_to_navigation("right")["yaw"], 1)
        self.assertEqual(action_to_navigation("left")["yaw"], -1)

    def test_reference_orbit_moves_to_the_named_subject_side(self):
        right_pose = generate_orbit_trajectory([{"yaw": 0.1}])[-1]
        left_pose = generate_orbit_trajectory([{"yaw": -0.1}])[-1]

        self.assertGreater(right_pose[0, 3], 0.0)
        self.assertLess(left_pose[0, 3], 0.0)
        np.testing.assert_allclose(
            right_pose[[0, 2], 3],
            [-left_pose[0, 3], left_pose[2, 3]],
        )

    def test_hy_worldplay_adapter_uses_the_same_orbit_convention(self):
        right_pose = generate_hy_orbit_trajectory([{"yaw": 0.1}])[-1]
        left_pose = generate_hy_orbit_trajectory([{"yaw": -0.1}])[-1]

        self.assertGreater(right_pose[0, 3], 0.0)
        self.assertLess(left_pose[0, 3], 0.0)

    def test_third_person_prompts_use_side_relative_wording(self):
        case = {}
        right_prompt = build_turn_prompt(
            case,
            {"type": "navigation", "action": "right"},
            perspective="third_person",
        )
        left_prompt = build_turn_prompt(
            case,
            {"type": "navigation", "action": "left"},
            perspective="third_person",
        )

        self.assertIn("subject's right side", right_prompt)
        self.assertIn("subject's left side", left_prompt)
        self.assertNotIn("clockwise", right_prompt.lower())
        self.assertNotIn("clockwise", left_prompt.lower())


if __name__ == "__main__":
    unittest.main()
