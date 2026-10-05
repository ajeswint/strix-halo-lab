---
name: torch-install
description: Add or upgrade Python packages in the /data/envs/torch training env without breaking the AMD gfx1151 torch build. Use for any uv/pip install into that env, and before proposing a new training library.
---

# Installing into /data/envs/torch

The env is a uv venv on system Python 3.14.4. torch comes from AMD's gfx1151 wheel index (README Software state).

Install command shape. Always all three: the AMD index, `--index-strategy unsafe-best-match`, and the constraints file.

```
uv pip install --python /data/envs/torch/bin/python --constraint envs/torch-constraints.txt --index https://stable.repo.amd.com/rocm/whl-next/ --index-strategy unsafe-best-match evaluate
```

Why each part:
- `--constraint envs/torch-constraints.txt` pins torch/torchvision/torchaudio to the `+rocm10.0.0` builds. Without it a dependency can pull a CPU or CUDA torch from PyPI.
- `--index-strategy unsafe-best-match`: the AMD index also hosts one `fsspec` version. uv's default first-index rule then pins it and silently backtracks `datasets`/`trl` to 2020-era releases.

## Before installing

- Check the package's current version and its torch/Python 3.14 support on PyPI or its upstream docs. Cite the URL.
- Install the whole stack for the step at once, then test. Never test while other installs are pending.
- Dry run first and read the plan: same command plus `--dry-run`. Stop if torch, torchvision or torchaudio would change, or if any package goes down a major version.

## After installing

- Verify torch still sees the GPU: `/data/envs/torch/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"`. Expect `2.13.0+rocm10.0.0 True` and the Radeon 8060S. This initialises the GPU runtime, so run `preflight` first.
- If the change should survive a rebuild, add it to `envs/install-torch-env.sh` and note the live-vs-freeze delta in README.

## Never

- `download.pytorch.org` ROCm wheels (no gfx1151 kernels).
- Unsloth in this env (needs Python <= 3.13 and its own torch; separate env if ever).
- `HSA_OVERRIDE_GFX_VERSION`.
- bitsandbytes (not installed, by decision).
