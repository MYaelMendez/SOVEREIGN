---
library_name: asimov
pipeline_tag: robotics
license: bsd-3-clause
---

# Asimov 1 locomotion policy checkpoint — 2026-09-24 ankle update

- Velocity-commanded locomotion policy for Asimov 1, trained in Isaac Lab with PPO and adversarial motion priors (AMP).
- Ankle-update checkpoint from the `decouple_finetune_og_pose` run, exported from `model_9999.pt`.
- `policy.onnx` is the exported policy for inference, producing joint-position actions.
- `policy.pt` is the same policy as TorchScript, for running it from PyTorch.
- `agent.yaml` records the actor-critic and AMP training settings, including the motion data configuration.
- `env.yaml` records the simulation and locomotion task settings, including observations, actions, commands, and rewards.
- Training and evaluation code: [menloresearch/cyclotron](https://github.com/menloresearch/cyclotron).

## Ankle update

This policy keeps the 78-value observation interface, 23-action joint order, and
50 Hz control rate of [asimov1-locomotion-0818](https://huggingface.co/Menlo/asimov1-locomotion-0818).
Its saved configuration changes the ankle settings:

- Ankle-roll action scale is `0.08`; the other joints use `0.25`.
- Ankle-roll position targets are clipped to `[-0.09, 0.09]` radians after applying the action scale and default pose.
- Ankle-pitch stiffness/damping are `224.42` / `10.201`, with effort limit `72` and armature `0.42984`.
- Ankle-roll stiffness/damping are `35.2` / `1.6`, with effort limit `18` and armature `0.05814`.

Use this model's `env.yaml` for the full settings rather than reusing the older
checkpoint's ankle configuration.

## How to run

Load `policy.onnx` with ONNX Runtime, or `policy.pt` with PyTorch, in an Asimov 1
runtime that implements the observation recipe and joint-position action
processing in `env.yaml`. The action scales, default pose, and target clipping
are applied by the runtime, outside the ONNX graph. The ONNX metadata also
records the deployment interface.

The [humanoid-policy-viewer](https://github.com/menloresearch/humanoid-policy-viewer)
used by the older checkpoint currently rejects policies with action clipping.
This checkpoint requires support for ankle-roll target clipping before it can
run there with its trained action settings. See the viewer's
[supported policies](https://github.com/menloresearch/humanoid-policy-viewer/blob/main/docs/huggingface.md#supported-policies).

## Inputs and outputs

- **Input:** 78 values at 50 Hz: base angular velocity, projected gravity,
  velocity command (`vx, vy, wz`), joint positions and velocities, and the
  previous action. All of these are available on the real robot.
- **Output:** 23 joint position actions (legs, waist and arms; the neck is not
  driven). Each target is `default_joint_pos + action_scale * action`, followed
  by the ankle-roll target clipping specified above. The full settings are in
  `env.yaml`.
- Trained in Isaac Lab (PhysX).

The full observation order and action joint list are recorded in `env.yaml`.
