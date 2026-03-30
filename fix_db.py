import sqlite3

def adicionar_coluna():
    # Conecta ao seu arquivo banco.db
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    try:
        # Executa o comando para adicionar a coluna faltante
        cursor.execute("ALTER TABLE pedidos ADD COLUMN forma_pagamento VARCHAR;")
        conn.commit()
        print("✅ Coluna 'forma_pagamento' adicionada com sucesso!")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️ A coluna já existe no banco de dados.")
        else:
            print(f"❌ Erro operacional: {e}")
    except Exception as e:
        print(f"❌ Ocorreu um erro: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    adicionar_coluna()