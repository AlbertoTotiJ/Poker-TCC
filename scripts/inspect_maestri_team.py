import json
from pathlib import Path

roles_dir = Path(r"C:\Users\T-Gamer\Desktop\Poker-TCC\.maestri\roles")

roles_info = []
for p in sorted(roles_dir.iterdir()):
    if p.is_dir():
        r_file = p / "role.json"
        if r_file.exists():
            with open(r_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                roles_info.append({
                    "id": p.name,
                    "name": data.get("name", "Sem nome"),
                    "title": data.get("title", ""),
                    "description": data.get("description", ""),
                    "instructions": data.get("instructions", "")[:200] + "..." if data.get("instructions") else ""
                })

print("Equipe Maestri encontrada:")
for r in roles_info:
    print(f"\n• Nome: {r['name']} | Título: {r['title']}")
    print(f"  Descrição: {r['description']}")
