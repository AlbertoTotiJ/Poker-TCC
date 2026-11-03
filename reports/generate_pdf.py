import html
import re
import subprocess
import sys
from pathlib import Path

def convert_md_to_html(md_path: Path, html_path: Path):
    md_content = md_path.read_text(encoding="utf-8")
    
    css = """
    @page {
        size: A4;
        margin: 20mm 15mm 20mm 15mm;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        font-size: 10pt;
        line-height: 1.5;
        color: #1e293b;
        background-color: #fff;
    }
    h1 {
        font-size: 18pt;
        color: #0f172a;
        border-bottom: 2px solid #2563eb;
        padding-bottom: 6px;
        margin-top: 0;
        margin-bottom: 12px;
    }
    h2 {
        font-size: 13pt;
        color: #1d4ed8;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 4px;
        margin-top: 22px;
        margin-bottom: 8px;
        page-break-after: avoid;
    }
    h3 {
        font-size: 11pt;
        color: #334155;
        margin-top: 14px;
        margin-bottom: 6px;
        page-break-after: avoid;
    }
    h4 {
        font-size: 10pt;
        color: #475569;
        margin-top: 10px;
        margin-bottom: 4px;
        page-break-after: avoid;
    }
    p, ul, ol {
        margin-top: 3px;
        margin-bottom: 6px;
    }
    ul, ol {
        padding-left: 20px;
    }
    li {
        margin-bottom: 3px;
    }
    code {
        font-family: 'Consolas', 'Courier New', monospace;
        background-color: #f1f5f9;
        color: #0f172a;
        padding: 2px 4px;
        border-radius: 4px;
        font-size: 8.5pt;
    }
    pre {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 8px 12px;
        overflow-x: auto;
        font-size: 8pt;
        line-height: 1.35;
        page-break-inside: avoid;
    }
    pre code {
        background: none;
        padding: 0;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
        margin-bottom: 14px;
        font-size: 8.5pt;
        page-break-inside: avoid;
    }
    th, td {
        border: 1px solid #cbd5e1;
        padding: 6px 8px;
        text-align: left;
        vertical-align: top;
    }
    th {
        background-color: #f1f5f9;
        color: #1e293b;
        font-weight: 600;
    }
    tr:nth-child(even) {
        background-color: #f8fafc;
    }
    blockquote {
        border-left: 4px solid #2563eb;
        padding: 6px 12px;
        background-color: #eff6ff;
        color: #1e40af;
        margin: 8px 0;
    }
    hr {
        border: none;
        border-top: 1px solid #e2e8f0;
        margin: 16px 0;
    }
    .badge-alta {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 2px 5px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 7.5pt;
    }
    .badge-media {
        background-color: #fef3c7;
        color: #92400e;
        padding: 2px 5px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 7.5pt;
    }
    """
    
    lines = md_content.splitlines()
    body_parts = []
    
    in_code = False
    code_lines = []
    in_table = False
    table_lines = []
    
    def format_inline(text: str) -> str:
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
        text = text.replace('🔴 Alta', '<span class="badge-alta">🔴 Alta</span>')
        text = text.replace('🟡 Média', '<span class="badge-media">🟡 Média</span>')
        return text

    for line in lines:
        if line.startswith("```"):
            if in_code:
                in_code = False
                c_escaped = html.escape("\n".join(code_lines))
                body_parts.append(f"<pre><code>{c_escaped}</code></pre>")
                code_lines = []
            else:
                in_code = True
                code_lines = []
            continue
        
        if in_code:
            code_lines.append(line)
            continue
            
        # Tabela
        if line.strip().startswith("|") and line.strip().endswith("|"):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
            continue
        elif in_table:
            in_table = False
            t_out = ["<table>"]
            is_head = True
            for row in table_lines:
                cells = [c.strip() for c in row.strip()[1:-1].split("|")]
                if all(set(c).issubset({"-", ":", " "}) for c in cells):
                    is_head = False
                    continue
                t_out.append("<tr>")
                for cell in cells:
                    tag = "th" if is_head else "td"
                    t_out.append(f"<{tag}>{format_inline(cell)}</{tag}>")
                t_out.append("</tr>")
            t_out.append("</table>")
            body_parts.append("\n".join(t_out))
            table_lines = []
            
        if line.startswith("# "):
            body_parts.append(f"<h1>{format_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            body_parts.append(f"<h2>{format_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            body_parts.append(f"<h3>{format_inline(line[4:])}</h3>")
        elif line.startswith("#### "):
            body_parts.append(f"<h4>{format_inline(line[5:])}</h4>")
        elif line.strip() == "---":
            body_parts.append("<hr>")
        elif line.startswith("> "):
            body_parts.append(f"<blockquote>{format_inline(line[2:])}</blockquote>")
        elif line.startswith("* ") or line.startswith("- "):
            body_parts.append(f"<ul><li>{format_inline(line[2:])}</li></ul>")
        elif re.match(r"^\d+\.\s", line):
            content = re.sub(r"^\d+\.\s", "", line)
            body_parts.append(f"<ol><li>{format_inline(content)}</li></ol>")
        elif line.strip():
            body_parts.append(f"<p>{format_inline(line)}</p>")
            
    if in_table and table_lines:
        t_out = ["<table>"]
        is_head = True
        for row in table_lines:
            cells = [c.strip() for c in row.strip()[1:-1].split("|")]
            if all(set(c).issubset({"-", ":", " "}) for c in cells):
                is_head = False
                continue
            t_out.append("<tr>")
            for cell in cells:
                tag = "th" if is_head else "td"
                t_out.append(f"<{tag}>{format_inline(cell)}</{tag}>")
            t_out.append("</tr>")
        t_out.append("</table>")
        body_parts.append("\n".join(t_out))
        
    full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório de Auditoria Crítica</title>
<style>
{css}
</style>
</head>
<body>
{"".join(body_parts)}
</body>
</html>
"""
    html_path.write_text(full_html, encoding="utf-8")
    print(f"HTML gerado: {html_path}")

def generate_pdf(html_path: Path, pdf_path: Path):
    edge_paths = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    edge_bin = next((p for p in edge_paths if p.exists()), None)
    if not edge_bin:
        raise FileNotFoundError("Microsoft Edge não encontrado para impressão headless de PDF.")
        
    cmd = [
        str(edge_bin),
        "--headless",
        "--disable-gpu",
        f"--print-to-pdf={pdf_path}",
        "--no-pdf-header-footer",
        str(html_path.resolve())
    ]
    print(f"Executando Edge headless: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Erro ao gerar PDF: {res.stderr}")
        sys.exit(res.returncode)
    print(f"PDF gerado com sucesso: {pdf_path}")

if __name__ == "__main__":
    reports_dir = Path(__file__).resolve().parent
    if len(sys.argv) > 1:
        target_md = Path(sys.argv[1]).resolve()
    else:
        target_md = reports_dir / "RELATORIO_AUDITORIA_CRITICA_AGENTES.md"

    html_file = target_md.with_suffix(".html")
    pdf_file = target_md.with_suffix(".pdf")
    
    convert_md_to_html(target_md, html_file)
    generate_pdf(html_file, pdf_file)
    
    # Remove o arquivo html temporário se desejado
    if html_file.exists():
        html_file.unlink()
        print("HTML temporário removido.")
