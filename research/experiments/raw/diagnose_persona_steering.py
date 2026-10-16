"""Check whether the saved Extraversion vector changes this model's next-token logits.

This is a mechanism check, not a personality-validity test.
"""
import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

root = Path('/srv/gpu-home/kanishk/big-five-steering/persona-comparison-hauhau')
cfg = json.loads((root / 'config.json').read_text())
tok = AutoTokenizer.from_pretrained(cfg['model'], local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(
    cfg['model'], local_files_only=True, dtype=torch.bfloat16,
    device_map='cuda:0', attn_implementation='sdpa'
).eval()
vectors = torch.load(root / 'results/vectors.pt', map_location='cpu', weights_only=True)
print('vector_shape', tuple(vectors.shape))
text = tok.apply_chat_template([
    {'role': 'system', 'content': 'Answer as a person in a conversation.'},
    {'role': 'user', 'content': 'A stranger invites you to a lively party tonight. What do you say?'}
], tokenize=False, add_generation_prompt=True, enable_thinking=False)
inputs = tok(text, return_tensors='pt').to('cuda')

def next_logits(strength):
    hook = None
    if strength:
        delta = (vectors[0, 2].to('cuda').float() * strength).to(torch.bfloat16)
        def intervene(module, args, output):
            hidden = output[0] if isinstance(output, tuple) else output
            changed = hidden.clone()
            changed[:, -1, :] += delta
            return (changed, *output[1:]) if isinstance(output, tuple) else changed
        hook = model.model.layers[10].register_forward_hook(intervene)
    try:
        with torch.inference_mode():
            return model(**inputs).logits[0, -1].float().cpu()
    finally:
        if hook:
            hook.remove()

base = next_logits(0)
base_p = torch.softmax(base, dim=-1)
for strength in (0.5, 2, 10):
    altered = next_logits(strength)
    q = torch.softmax(altered, dim=-1)
    tv = (base_p - q).abs().sum().item() / 2
    print(json.dumps({
        'strength': strength,
        'max_abs_logit_change': (base - altered).abs().max().item(),
        'total_variation_next_token': tv,
        'baseline_top_token': int(base.argmax().item()),
        'altered_top_token': int(altered.argmax().item()),
    }))
