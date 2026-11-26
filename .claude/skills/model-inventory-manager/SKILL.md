---
name: model-inventory-manager
description: "Use when listing, finding or checking the models already downloaded on this PC (Ollama, GGUF, safetensors): read-only discovery, formats, architectures, licences, sizes, and avoiding a second download of a model that is already here."
---

# Model inventory manager (Story Studio)

Read-only discovery of the owner's models. Never copy, move or download a model to inspect it.

1. Run `python run.py compute inventory` (`modelinventory.py`): Ollama through its API (`modelinventory.ollama_models`), GGUF and safetensors files by their headers only (`modelinventory.gguf_meta`, `modelinventory.safetensors_header`), under the roots in `config/compute.json`. The forbidden folder in `never_scan` is skipped.
2. The result is `data/compute/models.json` (not in git: it holds paths). Each entry: name, path, format, architecture, parameters, quantization, size, context, layers and KV heads (for memory estimates), licence, kind (llm, vision-llm, lora-adapter, image, video, vae, text-encoder), `private` (the owner's own file: never uploaded).
3. Before downloading anything, search this inventory: two Ollama names on one blob are marked `same_as`.
4. A file that changed since the inventory (a half-finished download, an edit) is refused by `modelinventory.still_same`; run the inventory again.
5. In public reports name models and folders, never secrets; paths stay in `data/`.
