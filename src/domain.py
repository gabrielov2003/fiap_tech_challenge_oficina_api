import re
from werkzeug.security import generate_password_hash, check_password_hash

TRANSICOES = {
    "Recebida": ["Em diagnóstico"],
    "Em diagnóstico": ["Aguardando aprovação"],
    "Aguardando aprovação": ["Aprovado", "Recusada", "Solicitado alterações"],
    "Solicitado alterações": ["Em diagnóstico"],
    "Aprovado": ["Em execução", "Aguardando peças"],
    "Aguardando peças": ["Em execução", "Recusada"], # Pode ser recusada em caso de atraso no tempo de espera das peças
    "Em execução": ["Finalizada"],
    "Finalizada": ["Entregue"],
    "Recusada": [],
    "Entregue": [],
}

class DomainError(Exception):
    pass

class Validador:
    @staticmethod
    def validar_documento(doc):
        doc = re.sub(r'\D', '', doc)

        if len(doc) == 11:  # CPF
            if doc == doc[0] * 11:
                raise DomainError("CPF/CNPJ inválido")
            for i in range(9, 11):
                s = sum(int(doc[j]) * (i + 1 - j) for j in range(i))
                d = (s * 10 % 11) % 10
                if d != int(doc[i]):
                    raise DomainError("CPF/CNPJ inválido")
            return doc

        elif len(doc) == 14:  # CNPJ
            if doc == doc[0] * 14:
                raise DomainError("CPF/CNPJ inválido")
            pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
            for i in range(2):
                s = sum(int(doc[j]) * pesos[j] for j in range(12 + i))
                d = 11 - (s % 11)
                if d >= 10: d = 0
                if d != int(doc[12 + i]):
                    raise DomainError("CPF/CNPJ inválido")
                pesos = [6] + pesos
            return doc

        raise DomainError("CPF/CNPJ inválido")

    @staticmethod
    def validar_placa(placa):
        padrao = r'^[A-Z]{3}[0-9]{4}$|^[A-Z]{3}[0-9][A-Z][0-9]{2}$'
        if not re.match(padrao, placa.upper()):
            raise DomainError("Placa de veículo inválida")
        return placa.upper()

class Cliente:
    def __init__(self, documento, nome, id_cliente=None):
        self.id_cliente = id_cliente
        self.documento = Validador.validar_documento(documento)
        self.nome = nome

class Veiculo:
    def __init__(self, placa, marca, modelo, ano, id_veiculo=None):
        self.id_veiculo = id_veiculo
        self.placa = Validador.validar_placa(placa)
        self.marca = marca
        self.modelo = modelo
        self.ano = ano

class OrdemServico:
    def __init__(self, id_cliente, id_veiculo, id_os=None, status="Recebida"):
        self.id_os = id_os
        self.id_cliente = id_cliente
        self.id_veiculo = id_veiculo
        self.status = status

    def pode_transicionar_para(self, novo_status):
        return novo_status in TRANSICOES.get(self.status, [])

class PecasCarro:
    def __init__(self, id_os, peca, valor_total):
        self.id_os = id_os
        self.peca = peca
        self.valor_total = valor_total

class ServicosCarro:
    def __init__(self, id_os, servico, valor_total):
        self.id_os = id_os
        self.servico = servico
        self.valor_total = valor_total


class Usuario:
    def __init__(self, username, senha_hash=None, id_usuario=None):
        self.id_usuario = id_usuario
        self.username = username
        self.senha_hash = senha_hash

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)