# Model Backend Contract (Spec)
- `generate(prompts: list[dict], params: dict, seed: int) -> list[str]`
- Backends: `colab`, `hf`, `lmstudio`. All must honor `temperature`, `top_p`, `max_tokens`, and fixed seeds.
