# llama.cpp CUDA compatibility: Kaggle T4 and the local GTX 1050 Ti (25 Nov 2026), read-only

## 1. The 24 Nov build failure: what is and is not known (VERIFIED from `data/compute/kaggle_outputs/8ba727ef5f45c77c/v1-20261124T171256Z/`)
- **Command** (`kaggleworker.py:394-395`): `CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75" FORCE_CMAKE=1 pip install -q --no-cache-dir llama-cpp-python`. This is a **source build**: PyPI's latest, 0.3.38 (2026-11-23), is an sdist only.
- **Recorded error:** pip's wrapper only, "Building wheel for llama-cpp-python (pyproject.toml) did not run successfully … exit code: 1 … No available output … Failed building wheel".
- **Why the real error is missing:** our code. `-q` suppressed the build log, and only the last 600 characters of stderr were kept (`r.stderr[-600:]`).
- **Timing:** `load_failed(load_transformers)` at 138.6 s and `load_failed(load_llamacpp)` at 157.9 s in the session log. The whole download, isolated build environment and failure took about **19 s**.
- **Conclusion:**
  - A CUDA compile of ggml takes minutes, so it failed **before compiling** kernels, at configure time (INFERENCE from the timing).
  - The most likely configure failures are no `nvcc` / CUDA toolkit in the image (torch's pip CUDA libraries carry no compiler) or a missing build tool. **UNVERIFIED:** Test A records `which nvcc`, `nvcc --version`, `gcc --version` and `cmake --version`.
  - Not a Python-version problem as far as is known: the prebuilt wheels below are `py3-none`.
- **Smallest safe fix:**
  - **Do not compile on Kaggle.** Use a pinned prebuilt binary (section 3).
  - If a build is ever needed, run it once with `-v`, keep the full log as an output file, and record the toolchain first.

## 2. Compatibility facts (sources)
| Fact | Source | Kind |
|---|---|---|
| CUDA 13.0 "Removed support for Maxwell, Pascal, and Volta GPUs, corresponding to compute capabilities earlier than Turing" | NVIDIA CUDA Toolkit release notes (docs.nvidia.com, current page = CUDA 13.5), read 25 Nov | official |
| CUDA 13.5 = driver branch R620; CUDA 13.0 = R580; "Existing CUDA 13.x applications run on drivers >=580 under CUDA minor version compatibility. CUDA 13.5 new features … require an R620 or later driver" | same | official |
| "Applications that compile device code to PTX will not work on older drivers. If the application requires PTX then administrators have to upgrade the installed driver" | NVIDIA CUDA Compatibility guide, Minor Version Compatibility page | official |
| llama-cpp-python: prebuilt CUDA wheels for 11.8, 12.1–12.5, 13.0, 13.2; "compute capability … 6.0 or newer for CUDA 12 wheels, or 7.5 or newer for CUDA 13 wheels" | README, commit 7f16fe19 (2026-06-06) | official (project) |
| Newest prebuilt wheels: 0.3.37 `py3-none-manylinux_2_35_x86_64` in cu125, cu130 and cu132 (any Python 3, glibc ≥ 2.35); cu124 stops at 0.3.19 (cp39–cp312) | abetlen.github.io wheel index, read 25 Nov | code/data |
| llama.cpp publishes `llama-bNNNN-bin-ubuntu-cuda-12.8-x64.tar.gz` and `…-cuda-13.5-x64.tar.gz` (+ `cudart-…` runtime bundles) | GitHub releases API, b12719 (2026-11-25) | data |
| Release builds: `nvidia/cuda:12.8.2` and `13.5.0` `-devel-ubuntu24.04` containers, `-DGGML_NATIVE=OFF -DGGML_CUDA=ON -DGGML_CUDA_NCCL=OFF`, no fixed arch list ("use the broad default arch set") | `.github/workflows/release.yml` fd24ee26 (2026-11-23) | code |
| Default arch set: CUDA < 13 adds `50-virtual 61-virtual 70-virtual`; all add `75-virtual 80-virtual 86-real`, (≥ 11.8) `89-real 90-virtual`, (≥ 12.8) `120a-real`, (≥ 12.9) `103-real 121a-real` | `ggml/src/ggml-cuda/CMakeLists.txt` 2cbfc3cf (2026-11-18) | code |
| Local GPU: GTX 1050 Ti, compute capability **6.1**, driver 580.178.04, "CUDA Version: 13.0" (the driver's maximum, not an installed toolkit) | `nvidia-smi`, 25 Nov 06:48 UTC | measured |
| Kaggle: Tesla T4 (compute capability 7.5, NVIDIA's published value), driver 580.178.04, torch 2.11.0+cu130, Python 3.13.16, glibc 2.39 | 3 real reports, 24 Nov | measured |

## 3. Compatibility table
| Environment | GPU | CC | Build that can run | Python | Engine | Status |
|---|---|---|---|---|---|---|
| Local PC | GTX 1050 Ti 4 GB | 6.1 | **CUDA 12.x only** (13.x has no Pascal). Official `ubuntu-cuda-12.8` binary: `61-virtual` PTX, JIT-compiled by driver 580 (newer than 12.8: allowed). Or llama-cpp-python `cu125` wheel 0.3.37 | 3.14 only on this PC (`py3-none` wheel works) | llama.cpp 12.8 binary, or Ollama 0.34.4 (already installed, own CUDA runner) | **COMPATIBLE BY DOCS, UNTESTED.** First-run PTX JIT time unknown; JIT cache `~/.nv/ComputeCache` persists locally |
| Kaggle | 2 x T4 15 GB | 7.5 | Official `ubuntu-cuda-12.8` binary (`75-virtual`, JIT). **Not** the 13.5 binary: its T4 code is 13.5 PTX only, and driver R580 cannot JIT newer PTX (NVIDIA rule above; INFERENCE to confirm in Test B) | 3.13.16 | llama.cpp 12.8 binary + its `cudart` bundle; or llama-cpp-python `cu125` / `cu130` wheel (needs CUDA 12 or 13 runtime libraries on the path) | **COMPATIBLE BY DOCS, UNTESTED.** JIT runs every session (no persistent cache) |

## 4. Recommended engine path (no compiling anywhere)
- **One pinned binary for both machines:** `llama-b12719-bin-ubuntu-cuda-12.8-x64.tar.gz` (220.6 MB, sha256 `823dc2fb…3fab`) plus `cudart-llama-b12719-bin-ubuntu-cuda-12.8-x64.tar.gz` (594.4 MB, sha256 `961183a1…7e53`). Pinned by build number and SHA-256, like the model twin.
- **In the notebook:** download from github.com, verify the hash, extract to `/tmp` (never into `/kaggle/working`), and run `llama-bench` and `llama-server` bound to 127.0.0.1 only, stopped before the notebook ends.
- **Locally:** the same two archives in an isolated folder (proposed `~/studio/data/engines/llama-b12719-cuda12.8/`). No system install, no driver or CUDA change, Ollama untouched. **Needs approval** (about 815 MB download).
- **Why not llama-cpp-python:** an extra Python layer, and its newest wheel (0.3.37) lags llama.cpp. Keep it as a fallback.
- **Cached build option (only if JIT is too slow):** a private Kaggle CPU notebook compiles `-DCMAKE_CUDA_ARCHITECTURES=75-real` once, and its output is attached to benchmark kernels as a `kernel_sources` input. Kaggle's Notebooks docs: "You can also use output files from another Notebook as a data source". It needs `nvcc` in the image, which is UNVERIFIED.

## 5. What must not be done
- No CUDA 13 build on the GTX 1050 Ti.
- No driver change, system CUDA install, global pip install or Ollama replacement.
- No re-quantisation of model files.
