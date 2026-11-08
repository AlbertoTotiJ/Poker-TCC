import json
from pathlib import Path

brain_dir = Path(r"C:\Users\T-Gamer\.gemini\antigravity-cli\brain")

total_input = 0
total_cache_read = 0
total_output = 0
total_steps = 0

conv_stats = []

for conv in sorted(brain_dir.iterdir()):
    if not conv.is_dir():
        continue
    log_file = conv / ".system_generated" / "logs" / "transcript.jsonl"
    if not log_file.exists():
        continue

    c_in = 0
    c_cache = 0
    c_out = 0
    c_steps = 0

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    c_steps += 1
                    c_in += data.get("input_tokens", 0) or 0
                    c_cache += data.get("cache_read_tokens", 0) or 0
                    c_out += data.get("output_tokens", 0) or 0
                except Exception:
                    pass
    except Exception as e:
        print(f"Erro lendo {conv.name}: {e}")

    conv_stats.append({
        "conv_id": conv.name,
        "steps": c_steps,
        "input_tokens": c_in,
        "cache_read_tokens": c_cache,
        "output_tokens": c_out,
        "total_tokens": c_in + c_cache + c_out
    })

    total_input += c_in
    total_cache_read += c_cache
    total_output += c_out
    total_steps += c_steps

print("=" * 80)
print("AUDITORIA DE TOKENS DO PROJETO POKER-TCC (ANTIGRAVITY CLI)")
print("=" * 80)
print(f"Total de Conversas/Sessões Analisadas: {len(conv_stats)}")
print(f"Total de Passos/Interações Registradas: {total_steps:,}")
print(f"\n• Tokens de Entrada (Input Tokens):           {total_input:,}")
print(f"• Tokens de Cache Lido (Cache Read Tokens):    {total_cache_read:,}")
print(f"• Tokens de Saída (Output Tokens / Gerados):   {total_output:,}")
grand_total = total_input + total_cache_read + total_output
print(f"• TOTAL GERAL DE TOKENS PROCESSADOS:           {grand_total:,}")
print("=" * 80)

# Detalhe por conversa
print("\nDetalhamento por Sessão:")
for c in conv_stats:
    is_current = " (Sessão Atual)" if c["conv_id"] == "1d99d9d8-6035-4272-a2fe-f0ea967cc500" else ""
    print(f"  - {c['conv_id'][:8]}... | Passos: {c['steps']:4d} | Total: {c['total_tokens']:,} tokens{is_current}")
