import sqlite3
import pandas as pd
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.getenv('DATABASE_PATH', 'instance/database.db')


class Infrastructure:
    @staticmethod
    def get_connection():
        os.makedirs('instance', exist_ok=True)
        return sqlite3.connect(DB_PATH)

    @classmethod
    def init_db(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()

        cursor.executescript('''
        CREATE TABLE IF NOT EXISTS Cliente (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Veiculo (
            id_veiculo INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT UNIQUE NOT NULL,
            marca TEXT,
            modelo TEXT,
            ano INTEGER
        );

        CREATE TABLE IF NOT EXISTS Peca (
            id_peca INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            valor_unitario REAL NOT NULL,
            estoque INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS Servico (
            id_servico INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            valor REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Ordem_Servico (
            id_os INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER NOT NULL,
            id_veiculo INTEGER NOT NULL,
            status TEXT DEFAULT 'Recebida',
            data_abertura DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_fechamento DATETIME,
            FOREIGN KEY(id_cliente) REFERENCES Cliente(id_cliente),
            FOREIGN KEY(id_veiculo) REFERENCES Veiculo(id_veiculo)
        );

        CREATE TABLE IF NOT EXISTS Servicos_carro (
            id_os INTEGER,
            servico TEXT NOT NULL,
            valor_total REAL NOT NULL,
            FOREIGN KEY(id_os) REFERENCES Ordem_Servico(id_os)
        );

        CREATE TABLE IF NOT EXISTS Pecas_carro (
            id_os INTEGER,
            peca TEXT NOT NULL,
            valor_total REAL NOT NULL,
            FOREIGN KEY(id_os) REFERENCES Ordem_Servico(id_os)
        );

        CREATE TABLE IF NOT EXISTS Usuario (
            id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL
        );
        ''')

        for col in [
            "ALTER TABLE Ordem_Servico ADD COLUMN data_abertura DATETIME DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE Ordem_Servico ADD COLUMN data_fechamento DATETIME",
        ]:
            try:
                cursor.execute(col)
            except Exception:
                pass

        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM Usuario WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO Usuario (username, senha_hash) VALUES (?, ?)",
                ('admin', generate_password_hash('admin123'))
            )
            conn.commit()

        conn.close()
        print("Banco de dados inicializado.")

    @staticmethod
    def execute_query(query, params=()):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def execute_update(query, params=()):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def fetch_pandas(query, params=()):
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(query, conn, params=params)

    @staticmethod
    def fetch_one(query, params=()):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None


from ports import (ClienteRepositoryPort, VeiculoRepositoryPort, PecaRepositoryPort,
                   ServicoRepositoryPort, OrdemServicoRepositoryPort, UsuarioRepositoryPort)


class ClienteRepositorySQLite(ClienteRepositoryPort):
    def listar(self):
        return Infrastructure.fetch_pandas("SELECT * FROM Cliente").to_dict(orient='records')

    def buscar_por_id(self, id_cliente):
        return Infrastructure.fetch_one("SELECT * FROM Cliente WHERE id_cliente = ?", (id_cliente,))

    def buscar_por_documento(self, documento):
        return Infrastructure.fetch_pandas(
            "SELECT * FROM Cliente WHERE documento = ?", (documento,)
        ).to_dict(orient='records')

    def criar(self, nome, documento):
        return Infrastructure.execute_query(
            "INSERT INTO Cliente (nome, documento) VALUES (?, ?)", (nome, documento)
        )

    def atualizar(self, id_cliente, nome, documento):
        return Infrastructure.execute_update(
            "UPDATE Cliente SET nome = ?, documento = ? WHERE id_cliente = ?", (nome, documento, id_cliente)
        )

    def deletar(self, id_cliente):
        return Infrastructure.execute_update("DELETE FROM Cliente WHERE id_cliente = ?", (id_cliente,))


class VeiculoRepositorySQLite(VeiculoRepositoryPort):
    def listar(self):
        return Infrastructure.fetch_pandas("SELECT * FROM Veiculo").to_dict(orient='records')

    def buscar_por_id(self, id_veiculo):
        return Infrastructure.fetch_one("SELECT * FROM Veiculo WHERE id_veiculo = ?", (id_veiculo,))

    def buscar_por_placa(self, placa):
        return Infrastructure.fetch_pandas(
            "SELECT * FROM Veiculo WHERE placa = ?", (placa,)
        ).to_dict(orient='records')

    def criar(self, placa, marca, modelo, ano):
        return Infrastructure.execute_query(
            "INSERT INTO Veiculo (placa, marca, modelo, ano) VALUES (?, ?, ?, ?)", (placa, marca, modelo, ano)
        )

    def atualizar(self, id_veiculo, placa, marca, modelo, ano):
        return Infrastructure.execute_update(
            "UPDATE Veiculo SET placa = ?, marca = ?, modelo = ?, ano = ? WHERE id_veiculo = ?",
            (placa, marca, modelo, ano, id_veiculo)
        )

    def deletar(self, id_veiculo):
        return Infrastructure.execute_update("DELETE FROM Veiculo WHERE id_veiculo = ?", (id_veiculo,))


class PecaRepositorySQLite(PecaRepositoryPort):
    def listar(self):
        return Infrastructure.fetch_pandas("SELECT * FROM Peca").to_dict(orient='records')

    def buscar_por_id(self, id_peca):
        return Infrastructure.fetch_one("SELECT * FROM Peca WHERE id_peca = ?", (id_peca,))

    def criar(self, nome, valor_unitario, estoque):
        return Infrastructure.execute_query(
            "INSERT INTO Peca (nome, valor_unitario, estoque) VALUES (?, ?, ?)",
            (nome, float(valor_unitario), int(estoque))
        )

    def atualizar(self, id_peca, nome, valor_unitario, estoque):
        return Infrastructure.execute_update(
            "UPDATE Peca SET nome = ?, valor_unitario = ?, estoque = ? WHERE id_peca = ?",
            (nome, float(valor_unitario), int(estoque), id_peca)
        )

    def deletar(self, id_peca):
        return Infrastructure.execute_update("DELETE FROM Peca WHERE id_peca = ?", (id_peca,))


class ServicoRepositorySQLite(ServicoRepositoryPort):
    def listar(self):
        return Infrastructure.fetch_pandas("SELECT * FROM Servico").to_dict(orient='records')

    def buscar_por_id(self, id_servico):
        return Infrastructure.fetch_one("SELECT * FROM Servico WHERE id_servico = ?", (id_servico,))

    def criar(self, nome, valor):
        return Infrastructure.execute_query(
            "INSERT INTO Servico (nome, valor) VALUES (?, ?)", (nome, float(valor))
        )

    def atualizar(self, id_servico, nome, valor):
        return Infrastructure.execute_update(
            "UPDATE Servico SET nome = ?, valor = ? WHERE id_servico = ?", (nome, float(valor), id_servico)
        )

    def deletar(self, id_servico):
        return Infrastructure.execute_update("DELETE FROM Servico WHERE id_servico = ?", (id_servico,))


class OrdemServicoRepositorySQLite(OrdemServicoRepositoryPort):
    def listar_ativas(self):
        query = """
            SELECT * FROM Ordem_Servico
            WHERE status NOT IN ('Finalizada', 'Entregue', 'Recusada')
            ORDER BY CASE status
                WHEN 'Em execução' THEN 1
                WHEN 'Aguardando aprovação' THEN 2
                WHEN 'Em diagnóstico' THEN 3
                WHEN 'Recebida' THEN 4
                ELSE 5
            END, data_abertura ASC
        """
        return Infrastructure.fetch_pandas(query).to_dict(orient='records')

    def buscar_por_id(self, id_os):
        return Infrastructure.fetch_one("SELECT * FROM Ordem_Servico WHERE id_os = ?", (id_os,))

    def criar(self, id_cliente, id_veiculo):
        return Infrastructure.execute_query(
            "INSERT INTO Ordem_Servico (id_cliente, id_veiculo, status) VALUES (?, ?, ?)",
            (id_cliente, id_veiculo, "Recebida")
        )

    def atualizar_status(self, id_os, novo_status, fechar=False):
        extra = ", data_fechamento = CURRENT_TIMESTAMP" if fechar else ""
        Infrastructure.execute_query(
            f"UPDATE Ordem_Servico SET status = ?{extra} WHERE id_os = ?", (novo_status, id_os)
        )

    def adicionar_peca(self, id_os, peca, valor_total):
        return Infrastructure.execute_query(
            "INSERT INTO Pecas_carro (id_os, peca, valor_total) VALUES (?, ?, ?)", (id_os, peca, valor_total)
        )

    def adicionar_servico(self, id_os, servico, valor_total):
        return Infrastructure.execute_query(
            "INSERT INTO Servicos_carro (id_os, servico, valor_total) VALUES (?, ?, ?)", (id_os, servico, valor_total)
        )

    def buscar_pecas(self, id_os):
        return Infrastructure.fetch_pandas("SELECT * FROM Pecas_carro WHERE id_os = ?", (id_os,))

    def buscar_servicos(self, id_os):
        return Infrastructure.fetch_pandas("SELECT * FROM Servicos_carro WHERE id_os = ?", (id_os,))

    def tempo_medio(self):
        return Infrastructure.fetch_one(
            "SELECT AVG(julianday(data_fechamento) - julianday(data_abertura)) AS media_dias "
            "FROM Ordem_Servico WHERE data_fechamento IS NOT NULL"
        )


class UsuarioRepositorySQLite(UsuarioRepositoryPort):
    def buscar_por_username(self, username):
        return Infrastructure.fetch_one(
            "SELECT id_usuario, username, senha_hash FROM Usuario WHERE username = ?", (username,)
        )