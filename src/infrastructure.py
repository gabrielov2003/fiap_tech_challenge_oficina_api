import os
import unicodedata
from contextlib import contextmanager

import psycopg2
from datadog.dogstatsd import DogStatsd
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from werkzeug.security import generate_password_hash

from domain import DomainError
from ports import (ClienteRepositoryPort, VeiculoRepositoryPort, PecaRepositoryPort, ServicoRepositoryPort,
                   OrdemServicoRepositoryPort, UsuarioRepositoryPort, SaudeRepositoryPort, MetricasPort)

DB_SCHEMA = os.getenv('DB_SCHEMA', 'public')
TRAVA_MIGRACAO = 20250301

psycopg2.extensions.register_type(psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values, 'DECIMAL_PARA_FLOAT',
    lambda valor, cursor: float(valor) if valor is not None else None
))

MENSAGENS_RESTRICAO = {
    'cliente_documento_key': 'Documento já cadastrado',
    'veiculo_placa_key': 'Placa já cadastrada',
    'ordem_servico_id_cliente_fkey': 'Cliente inexistente ou com ordens de serviço vinculadas',
    'ordem_servico_id_veiculo_fkey': 'Veículo inexistente ou com ordens de serviço vinculadas',
    'pecas_carro_id_os_fkey': 'Ordem de serviço inexistente',
    'servicos_carro_id_os_fkey': 'Ordem de serviço inexistente',
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cliente (
    id_cliente SERIAL PRIMARY KEY,
    documento VARCHAR(14) NOT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'inativo'))
);

CREATE TABLE IF NOT EXISTS veiculo (
    id_veiculo SERIAL PRIMARY KEY,
    placa VARCHAR(7) NOT NULL UNIQUE,
    marca VARCHAR(50),
    modelo VARCHAR(50),
    ano INTEGER
);

CREATE TABLE IF NOT EXISTS peca (
    id_peca SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    valor_unitario NUMERIC(10, 2) NOT NULL CHECK (valor_unitario >= 0),
    estoque INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0)
);

CREATE TABLE IF NOT EXISTS servico (
    id_servico SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    valor NUMERIC(10, 2) NOT NULL CHECK (valor >= 0)
);

CREATE TABLE IF NOT EXISTS ordem_servico (
    id_os SERIAL PRIMARY KEY,
    id_cliente INTEGER NOT NULL REFERENCES cliente (id_cliente),
    id_veiculo INTEGER NOT NULL REFERENCES veiculo (id_veiculo),
    status VARCHAR(30) NOT NULL DEFAULT 'Recebida',
    data_abertura TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_fechamento TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pecas_carro (
    id_peca_carro SERIAL PRIMARY KEY,
    id_os INTEGER NOT NULL REFERENCES ordem_servico (id_os) ON DELETE CASCADE,
    peca VARCHAR(100) NOT NULL,
    valor_total NUMERIC(10, 2) NOT NULL CHECK (valor_total >= 0)
);

CREATE TABLE IF NOT EXISTS servicos_carro (
    id_servico_carro SERIAL PRIMARY KEY,
    id_os INTEGER NOT NULL REFERENCES ordem_servico (id_os) ON DELETE CASCADE,
    servico VARCHAR(100) NOT NULL,
    valor_total NUMERIC(10, 2) NOT NULL CHECK (valor_total >= 0)
);

CREATE TABLE IF NOT EXISTS historico_status_os (
    id_historico SERIAL PRIMARY KEY,
    id_os INTEGER NOT NULL REFERENCES ordem_servico (id_os) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL,
    data_inicio TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ordem_servico_status ON ordem_servico (status);
CREATE INDEX IF NOT EXISTS idx_ordem_servico_cliente ON ordem_servico (id_cliente);
CREATE INDEX IF NOT EXISTS idx_ordem_servico_veiculo ON ordem_servico (id_veiculo);
CREATE INDEX IF NOT EXISTS idx_pecas_carro_os ON pecas_carro (id_os);
CREATE INDEX IF NOT EXISTS idx_servicos_carro_os ON servicos_carro (id_os);
CREATE INDEX IF NOT EXISTS idx_historico_status_os ON historico_status_os (id_os, data_inicio);
"""


class Infrastructure:
    _pool = None

    @classmethod
    def _obter_pool(cls):
        if cls._pool is None:
            cls._pool = ThreadedConnectionPool(
                1, int(os.getenv('DB_POOL_MAX', '5')),
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                dbname=os.getenv('DB_NAME', 'oficina'),
                user=os.getenv('DB_USER', 'oficina'),
                password=os.getenv('DB_PASSWORD', 'oficina'),
                options=f'-c search_path={DB_SCHEMA}',
                connect_timeout=5,
            )
        return cls._pool

    @classmethod
    @contextmanager
    def conexao(cls):
        pool = cls._obter_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except psycopg2.errors.CheckViolation as e:
            conn.rollback()
            raise DomainError('Valor inválido para o campo informado') from e
        except psycopg2.IntegrityError as e:
            conn.rollback()
            mensagem = MENSAGENS_RESTRICAO.get(e.diag.constraint_name, 'Dados inconsistentes com os registros existentes')
            raise DomainError(mensagem) from e
        except Exception:
            if not conn.closed:
                conn.rollback()
            raise
        finally:
            pool.putconn(conn, close=bool(conn.closed))

    @classmethod
    def init_db(cls):
        with cls.conexao() as conn, conn.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', (TRAVA_MIGRACAO,))
            cursor.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(DB_SCHEMA)))
            cursor.execute(SCHEMA_SQL)
            cursor.execute('SELECT 1 FROM usuario WHERE username = %s', ('admin',))
            if cursor.fetchone() is None:
                cursor.execute(
                    'INSERT INTO usuario (username, senha_hash) VALUES (%s, %s)',
                    ('admin', generate_password_hash(os.getenv('ADMIN_PASSWORD', 'admin123')))
                )

    @classmethod
    def execute_query(cls, query, params=()):
        with cls.conexao() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()[0]

    @classmethod
    def execute_update(cls, query, params=()):
        with cls.conexao() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    @classmethod
    def fetch_all(cls, query, params=()):
        with cls.conexao() as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def fetch_one(cls, query, params=()):
        with cls.conexao() as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None


class ClienteRepositoryPostgres(ClienteRepositoryPort):
    def listar(self):
        return Infrastructure.fetch_all('SELECT * FROM cliente ORDER BY id_cliente')

    def buscar_por_id(self, id_cliente):
        return Infrastructure.fetch_one('SELECT * FROM cliente WHERE id_cliente = %s', (id_cliente,))

    def buscar_por_documento(self, documento):
        return Infrastructure.fetch_all('SELECT * FROM cliente WHERE documento = %s', (documento,))

    def criar(self, nome, documento):
        return Infrastructure.execute_query(
            'INSERT INTO cliente (nome, documento) VALUES (%s, %s) RETURNING id_cliente', (nome, documento)
        )

    def atualizar(self, id_cliente, nome, documento, status=None):
        return Infrastructure.execute_update(
            'UPDATE cliente SET nome = %s, documento = %s, status = COALESCE(%s, status) WHERE id_cliente = %s',
            (nome, documento, status, id_cliente)
        )

    def deletar(self, id_cliente):
        return Infrastructure.execute_update('DELETE FROM cliente WHERE id_cliente = %s', (id_cliente,))


class VeiculoRepositoryPostgres(VeiculoRepositoryPort):
    def listar(self):
        return Infrastructure.fetch_all('SELECT * FROM veiculo ORDER BY id_veiculo')

    def buscar_por_id(self, id_veiculo):
        return Infrastructure.fetch_one('SELECT * FROM veiculo WHERE id_veiculo = %s', (id_veiculo,))

    def buscar_por_placa(self, placa):
        return Infrastructure.fetch_all('SELECT * FROM veiculo WHERE placa = %s', (placa,))

    def criar(self, placa, marca, modelo, ano):
        return Infrastructure.execute_query(
            'INSERT INTO veiculo (placa, marca, modelo, ano) VALUES (%s, %s, %s, %s) RETURNING id_veiculo',
            (placa, marca, modelo, ano)
        )

    def atualizar(self, id_veiculo, placa, marca, modelo, ano):
        return Infrastructure.execute_update(
            'UPDATE veiculo SET placa = %s, marca = %s, modelo = %s, ano = %s WHERE id_veiculo = %s',
            (placa, marca, modelo, ano, id_veiculo)
        )

    def deletar(self, id_veiculo):
        return Infrastructure.execute_update('DELETE FROM veiculo WHERE id_veiculo = %s', (id_veiculo,))


class PecaRepositoryPostgres(PecaRepositoryPort):
    def listar(self):
        return Infrastructure.fetch_all('SELECT * FROM peca ORDER BY id_peca')

    def buscar_por_id(self, id_peca):
        return Infrastructure.fetch_one('SELECT * FROM peca WHERE id_peca = %s', (id_peca,))

    def criar(self, nome, valor_unitario, estoque):
        return Infrastructure.execute_query(
            'INSERT INTO peca (nome, valor_unitario, estoque) VALUES (%s, %s, %s) RETURNING id_peca',
            (nome, valor_unitario, estoque)
        )

    def atualizar(self, id_peca, nome, valor_unitario, estoque):
        return Infrastructure.execute_update(
            'UPDATE peca SET nome = %s, valor_unitario = %s, estoque = %s WHERE id_peca = %s',
            (nome, valor_unitario, estoque, id_peca)
        )

    def deletar(self, id_peca):
        return Infrastructure.execute_update('DELETE FROM peca WHERE id_peca = %s', (id_peca,))


class ServicoRepositoryPostgres(ServicoRepositoryPort):
    def listar(self):
        return Infrastructure.fetch_all('SELECT * FROM servico ORDER BY id_servico')

    def buscar_por_id(self, id_servico):
        return Infrastructure.fetch_one('SELECT * FROM servico WHERE id_servico = %s', (id_servico,))

    def criar(self, nome, valor):
        return Infrastructure.execute_query(
            'INSERT INTO servico (nome, valor) VALUES (%s, %s) RETURNING id_servico', (nome, valor)
        )

    def atualizar(self, id_servico, nome, valor):
        return Infrastructure.execute_update(
            'UPDATE servico SET nome = %s, valor = %s WHERE id_servico = %s', (nome, valor, id_servico)
        )

    def deletar(self, id_servico):
        return Infrastructure.execute_update('DELETE FROM servico WHERE id_servico = %s', (id_servico,))


class OrdemServicoRepositoryPostgres(OrdemServicoRepositoryPort):
    def listar_ativas(self, id_cliente=None):
        return Infrastructure.fetch_all(
            """
            SELECT * FROM ordem_servico
            WHERE status NOT IN ('Finalizada', 'Entregue', 'Recusada')
              AND (%(id_cliente)s::integer IS NULL OR id_cliente = %(id_cliente)s)
            ORDER BY CASE status
                WHEN 'Em execução' THEN 1
                WHEN 'Aguardando peças' THEN 2
                WHEN 'Aprovado' THEN 3
                WHEN 'Aguardando aprovação' THEN 4
                WHEN 'Solicitado alterações' THEN 5
                WHEN 'Em diagnóstico' THEN 6
                WHEN 'Recebida' THEN 7
                ELSE 8
            END, data_abertura
            """,
            {'id_cliente': id_cliente}
        )

    def buscar_por_id(self, id_os):
        return Infrastructure.fetch_one('SELECT * FROM ordem_servico WHERE id_os = %s', (id_os,))

    def criar(self, id_cliente, id_veiculo, status, pecas, servicos):
        with Infrastructure.conexao() as conn, conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO ordem_servico (id_cliente, id_veiculo, status) VALUES (%s, %s, %s) RETURNING id_os',
                (id_cliente, id_veiculo, status)
            )
            id_os = cursor.fetchone()[0]
            cursor.execute('INSERT INTO historico_status_os (id_os, status) VALUES (%s, %s)', (id_os, status))
            cursor.executemany(
                'INSERT INTO pecas_carro (id_os, peca, valor_total) VALUES (%s, %s, %s)',
                [(id_os, peca, valor) for peca, valor in pecas]
            )
            cursor.executemany(
                'INSERT INTO servicos_carro (id_os, servico, valor_total) VALUES (%s, %s, %s)',
                [(id_os, servico, valor) for servico, valor in servicos]
            )
            return id_os

    def atualizar_status(self, id_os, status_atual, novo_status, fechar=False):
        with Infrastructure.conexao() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ordem_servico
                SET status = %s,
                    data_fechamento = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE data_fechamento END
                WHERE id_os = %s AND status = %s
                """,
                (novo_status, fechar, id_os, status_atual)
            )
            if cursor.rowcount == 0:
                return None
            cursor.execute(
                'SELECT EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - MAX(data_inicio)) FROM historico_status_os '
                'WHERE id_os = %s',
                (id_os,)
            )
            segundos = cursor.fetchone()[0]
            cursor.execute('INSERT INTO historico_status_os (id_os, status) VALUES (%s, %s)', (id_os, novo_status))
            return segundos or 0.0

    def adicionar_peca(self, id_os, peca, valor_total):
        return Infrastructure.execute_query(
            'INSERT INTO pecas_carro (id_os, peca, valor_total) VALUES (%s, %s, %s) RETURNING id_peca_carro',
            (id_os, peca, valor_total)
        )

    def adicionar_servico(self, id_os, servico, valor_total):
        return Infrastructure.execute_query(
            'INSERT INTO servicos_carro (id_os, servico, valor_total) VALUES (%s, %s, %s) RETURNING id_servico_carro',
            (id_os, servico, valor_total)
        )

    def buscar_pecas(self, id_os):
        return Infrastructure.fetch_all(
            'SELECT * FROM pecas_carro WHERE id_os = %s ORDER BY id_peca_carro', (id_os,)
        )

    def buscar_servicos(self, id_os):
        return Infrastructure.fetch_all(
            'SELECT * FROM servicos_carro WHERE id_os = %s ORDER BY id_servico_carro', (id_os,)
        )

    def historico(self, id_os):
        return Infrastructure.fetch_all(
            'SELECT status, data_inicio FROM historico_status_os WHERE id_os = %s ORDER BY data_inicio, id_historico',
            (id_os,)
        )

    def tempo_medio(self):
        return Infrastructure.fetch_one(
            """
            SELECT AVG(EXTRACT(EPOCH FROM data_fechamento - data_abertura)) / 86400 AS media_dias
            FROM ordem_servico
            WHERE data_fechamento IS NOT NULL
            """
        )['media_dias']

    def tempo_medio_por_status(self):
        return Infrastructure.fetch_all(
            """
            SELECT status, AVG(EXTRACT(EPOCH FROM proximo - data_inicio)) / 86400 AS media_dias
            FROM (
                SELECT status, data_inicio,
                       LEAD(data_inicio) OVER (PARTITION BY id_os ORDER BY data_inicio, id_historico) AS proximo
                FROM historico_status_os
            ) AS periodos
            WHERE proximo IS NOT NULL
            GROUP BY status
            ORDER BY status
            """
        )


class UsuarioRepositoryPostgres(UsuarioRepositoryPort):
    def buscar_por_username(self, username):
        return Infrastructure.fetch_one(
            'SELECT id_usuario, username, senha_hash FROM usuario WHERE username = %s', (username,)
        )


class SaudeRepositoryPostgres(SaudeRepositoryPort):
    def ping(self):
        return Infrastructure.fetch_one('SELECT 1 AS ok')['ok'] == 1


def _tag(valor):
    return unicodedata.normalize('NFKD', valor).encode('ascii', 'ignore').decode().lower().replace(' ', '_')


class MetricasDatadog(MetricasPort):
    def __init__(self):
        self.statsd = DogStatsd(
            host=os.getenv('DD_AGENT_HOST', 'localhost'),
            port=int(os.getenv('DD_DOGSTATSD_PORT', '8125')),
            disable_buffering=True,
        )

    def os_aberta(self):
        self.statsd.increment('oficina.os.abertas')

    def status_alterado(self, status_anterior, novo_status, segundos_no_status):
        self.statsd.increment('oficina.os.status_alterado', tags=[f'status:{_tag(novo_status)}'])
        self.statsd.distribution(
            'oficina.os.tempo_status', segundos_no_status, tags=[f'status:{_tag(status_anterior)}']
        )

    def falha_processamento_os(self, operacao):
        self.statsd.increment('oficina.os.falhas', tags=[f'operacao:{operacao}'])

    def erro_integracao(self, integracao, motivo):
        self.statsd.increment('oficina.integracao.erros', tags=[f'integracao:{integracao}', f'motivo:{motivo}'])
