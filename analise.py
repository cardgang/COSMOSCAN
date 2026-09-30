import os
import sqlite3
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
DB = BASE / "_internal" / "cosmoscan.db"
SAIDA = BASE / "relatorio_cosmoscan_db.txt"

def tamanho_legivel(n):
    for unidade in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f} {unidade}"
        n /= 1024
    return f"{n:.2f} PB"

def titulo(f, texto):
    f.write("\n")
    f.write("=" * 80 + "\n")
    f.write(texto + "\n")
    f.write("=" * 80 + "\n")

def safe_query(cur, sql, params=()):
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception as e:
        return [("ERRO", str(e))]

if not DB.exists():
    print(f"[ERRO] Banco nao encontrado: {DB}")
    raise SystemExit(1)

tamanho_db = DB.stat().st_size

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = con.cursor()

with open(SAIDA, "w", encoding="utf-8") as f:
    f.write("RELATORIO DO BANCO COSMOSCAN\n")
    f.write(f"Gerado em: {datetime.now():%d/%m/%Y %H:%M:%S}\n")
    f.write(f"Arquivo: {DB}\n")
    f.write(f"Tamanho: {tamanho_legivel(tamanho_db)}\n")

    titulo(f, "INFORMACOES GERAIS")

    for pragma in [
        "page_size",
        "page_count",
        "freelist_count",
        "journal_mode",
        "encoding",
        "schema_version",
        "user_version"
    ]:
        try:
            cur.execute(f"PRAGMA {pragma}")
            valor = cur.fetchone()
            f.write(f"{pragma}: {valor[0] if valor else 'N/A'}\n")
        except Exception as e:
            f.write(f"{pragma}: ERRO - {e}\n")

    titulo(f, "TABELAS")

    cur.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)

    tabelas = cur.fetchall()

    f.write(f"Total de tabelas: {len(tabelas)}\n\n")

    for nome, sql in tabelas:
        f.write(f"TABELA: {nome}\n")
        f.write("-" * 80 + "\n")

        try:
            cur.execute(f'SELECT COUNT(*) FROM "{nome}"')
            total = cur.fetchone()[0]
            f.write(f"Registros: {total:,}\n")
        except Exception as e:
            f.write(f"Registros: ERRO - {e}\n")

        f.write("\nColunas:\n")

        try:
            cur.execute(f'PRAGMA table_info("{nome}")')
            colunas = cur.fetchall()

            for col in colunas:
                cid, col_nome, tipo, notnull, default, pk = col

                f.write(
                    f"  - {col_nome}"
                    f" | tipo={tipo or 'SEM TIPO'}"
                    f" | NOT NULL={bool(notnull)}"
                    f" | PK={bool(pk)}"
                    f" | default={default}\n"
                )

        except Exception as e:
            f.write(f"  ERRO: {e}\n")

        f.write("\nIndices:\n")

        try:
            cur.execute(f'PRAGMA index_list("{nome}")')
            indices = cur.fetchall()

            if not indices:
                f.write("  Nenhum indice\n")

            for idx in indices:
                seq, idx_nome, unique, origin, partial = idx

                f.write(
                    f"  - {idx_nome}"
                    f" | unique={bool(unique)}"
                    f" | origem={origin}"
                    f" | parcial={bool(partial)}\n"
                )

                try:
                    cur.execute(f'PRAGMA index_info("{idx_nome}")')
                    cols_idx = cur.fetchall()

                    nomes_idx = [x[2] for x in cols_idx]
                    f.write(f"    colunas: {', '.join(nomes_idx)}\n")

                except Exception:
                    pass

        except Exception as e:
            f.write(f"  ERRO: {e}\n")

        f.write("\nSQL de criacao:\n")
        f.write((sql or "N/A") + "\n")

        f.write("\nAmostra estrutural dos dados:\n")

        try:
            cur.execute(f'SELECT * FROM "{nome}" LIMIT 3')
            amostra = cur.fetchall()

            nomes_colunas = [d[0] for d in cur.description] if cur.description else []

            if nomes_colunas:
                f.write("  Colunas: " + " | ".join(nomes_colunas) + "\n")

            # Não imprime valores completos.
            # Só informa tipo e tamanho aproximado para evitar expor dados.
            for i, linha in enumerate(amostra, 1):
                f.write(f"  Linha {i}:\n")

                for col_nome, valor in zip(nomes_colunas, linha):
                    if valor is None:
                        descricao = "NULL"
                    elif isinstance(valor, bytes):
                        descricao = f"BLOB ({len(valor)} bytes)"
                    elif isinstance(valor, str):
                        descricao = f"TEXT ({len(valor)} caracteres)"
                    elif isinstance(valor, int):
                        descricao = "INTEGER"
                    elif isinstance(valor, float):
                        descricao = "REAL"
                    else:
                        descricao = type(valor).__name__

                    f.write(f"    {col_nome}: {descricao}\n")

        except Exception as e:
            f.write(f"  ERRO: {e}\n")

        f.write("\n\n")

    titulo(f, "INDICES GLOBAIS")

    cur.execute("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type='index'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY tbl_name, name
    """)

    for idx_nome, tabela, sql in cur.fetchall():
        f.write(f"Indice: {idx_nome}\n")
        f.write(f"Tabela: {tabela}\n")
        f.write(f"SQL: {sql}\n\n")

    titulo(f, "VIEWS")

    cur.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='view'
        ORDER BY name
    """)

    views = cur.fetchall()

    if not views:
        f.write("Nenhuma view encontrada.\n")
    else:
        for nome, sql in views:
            f.write(f"VIEW: {nome}\n")
            f.write(f"{sql}\n\n")

    titulo(f, "TRIGGERS")

    cur.execute("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type='trigger'
        ORDER BY tbl_name, name
    """)

    triggers = cur.fetchall()

    if not triggers:
        f.write("Nenhum trigger encontrado.\n")
    else:
        for nome, tabela, sql in triggers:
            f.write(f"Trigger: {nome}\n")
            f.write(f"Tabela: {tabela}\n")
            f.write(f"{sql}\n\n")

    titulo(f, "ESTIMATIVA DE ESPACO LIVRE")

    try:
        cur.execute("PRAGMA page_size")
        page_size = cur.fetchone()[0]

        cur.execute("PRAGMA freelist_count")
        freelist = cur.fetchone()[0]

        espaco_livre = page_size * freelist

        f.write(f"Paginas livres: {freelist:,}\n")
        f.write(f"Espaco reaproveitavel: {tamanho_legivel(espaco_livre)}\n")

        if espaco_livre > 0:
            f.write("\n")
            f.write(
                "OBS: esse espaco pode potencialmente ser recuperado com VACUUM,\n"
                "mas faca backup antes de qualquer alteracao.\n"
            )

    except Exception as e:
        f.write(f"Erro ao calcular: {e}\n")

con.close()

print()
print("=" * 70)
print("ANALISE FINALIZADA")
print("=" * 70)
print()
print(f"Banco: {DB}")
print(f"Tamanho: {tamanho_legivel(tamanho_db)}")
print()
print(f"Relatorio salvo em:")
print(SAIDA)
print()