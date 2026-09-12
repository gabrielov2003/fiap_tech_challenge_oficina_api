from domain import Cliente, Veiculo, OrdemServico, DomainError, PecasCarro, ServicosCarro, Usuario
from ports import (ClienteRepositoryPort, VeiculoRepositoryPort, PecaRepositoryPort,
                   ServicoRepositoryPort, OrdemServicoRepositoryPort, UsuarioRepositoryPort)

cliente_repo: ClienteRepositoryPort = None
veiculo_repo: VeiculoRepositoryPort = None
peca_repo: PecaRepositoryPort = None
servico_repo: ServicoRepositoryPort = None
os_repo: OrdemServicoRepositoryPort = None
usuario_repo: UsuarioRepositoryPort = None


class OficinaAppService:
    @staticmethod
    def autenticar_usuario(username, senha):
        row = usuario_repo.buscar_por_username(username)
        if not row:
            return None
        u = Usuario(username=row['username'], senha_hash=row['senha_hash'], id_usuario=row['id_usuario'])
        return str(u.id_usuario) if u.verificar_senha(senha) else None

    @staticmethod
    def cadastrar_cliente(nome, documento):
        try:
            novo_cliente = Cliente(documento=documento, nome=nome)
            return cliente_repo.criar(novo_cliente.nome, novo_cliente.documento)
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def listar_clientes():
        return cliente_repo.listar()

    @staticmethod
    def buscar_cliente_por_id(id_cliente):
        return cliente_repo.buscar_por_id(id_cliente)

    @staticmethod
    def buscar_cliente_por_documento(documento):
        return cliente_repo.buscar_por_documento(documento)

    @staticmethod
    def atualizar_cliente(id_cliente, nome, documento):
        try:
            c = Cliente(documento=documento, nome=nome)
            rows = cliente_repo.atualizar(id_cliente, c.nome, c.documento)
            return rows > 0
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def deletar_cliente(id_cliente):
        return cliente_repo.deletar(id_cliente) > 0

    @staticmethod
    def listar_veiculos():
        return veiculo_repo.listar()

    @staticmethod
    def buscar_veiculo_por_id(id_veiculo):
        return veiculo_repo.buscar_por_id(id_veiculo)

    @staticmethod
    def buscar_veiculo_por_placa(placa):
        return veiculo_repo.buscar_por_placa(placa)

    @staticmethod
    def cadastrar_veiculo(placa, marca, modelo, ano):
        try:
            novo_veiculo = Veiculo(placa=placa, marca=marca, modelo=modelo, ano=ano)
            return veiculo_repo.criar(novo_veiculo.placa, novo_veiculo.marca, novo_veiculo.modelo, novo_veiculo.ano)
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def atualizar_veiculo(id_veiculo, placa, marca, modelo, ano):
        try:
            v = Veiculo(placa=placa, marca=marca, modelo=modelo, ano=ano)
            rows = veiculo_repo.atualizar(id_veiculo, v.placa, v.marca, v.modelo, v.ano)
            return rows > 0
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def deletar_veiculo(id_veiculo):
        return veiculo_repo.deletar(id_veiculo) > 0

    @staticmethod
    def cadastrar_peca(nome, valor_unitario, estoque=0):
        return peca_repo.criar(nome, float(valor_unitario), int(estoque))

    @staticmethod
    def listar_pecas():
        return peca_repo.listar()

    @staticmethod
    def buscar_peca_por_id(id_peca):
        return peca_repo.buscar_por_id(id_peca)

    @staticmethod
    def atualizar_peca(id_peca, nome, valor_unitario, estoque):
        return peca_repo.atualizar(id_peca, nome, float(valor_unitario), int(estoque)) > 0

    @staticmethod
    def deletar_peca(id_peca):
        return peca_repo.deletar(id_peca) > 0

    @staticmethod
    def cadastrar_servico_catalogo(nome, valor):
        return servico_repo.criar(nome, float(valor))

    @staticmethod
    def listar_servicos_catalogo():
        return servico_repo.listar()

    @staticmethod
    def buscar_servico_por_id(id_servico):
        return servico_repo.buscar_por_id(id_servico)

    @staticmethod
    def atualizar_servico(id_servico, nome, valor):
        return servico_repo.atualizar(id_servico, nome, float(valor)) > 0

    @staticmethod
    def deletar_servico(id_servico):
        return servico_repo.deletar(id_servico) > 0

    @staticmethod
    def abrir_ordem_servico(id_cliente, id_veiculo, pecas=None, servicos=None):
        os_dominio = OrdemServico(id_cliente=id_cliente, id_veiculo=id_veiculo)
        id_os = os_repo.criar(os_dominio.id_cliente, os_dominio.id_veiculo)
        for p in (pecas or []):
            OficinaAppService.adicionar_peca(id_os, p['peca'], p['valor_total'])
        for s in (servicos or []):
            OficinaAppService.adicionar_servico(id_os, s['servico'], s['valor_total'])
        return id_os

    @staticmethod
    def adicionar_peca(id_os, nome_peca, valor):
        peca = PecasCarro(id_os=id_os, peca=nome_peca, valor_total=valor)
        return os_repo.adicionar_peca(peca.id_os, peca.peca, peca.valor_total)

    @staticmethod
    def adicionar_servico(id_os, nome_servico, valor):
        s = ServicosCarro(id_os=id_os, servico=nome_servico, valor_total=valor)
        return os_repo.adicionar_servico(s.id_os, s.servico, s.valor_total)

    @staticmethod
    def listar_ordens():
        return os_repo.listar_ativas()

    @staticmethod
    def aprovar_orcamento(id_os, aprovado):
        row = os_repo.buscar_por_id(id_os)
        if not row:
            return {"erro": "OS não encontrada"}
        if row['status'] != "Aguardando aprovação":
            return {"erro": f"OS não está aguardando aprovação (status atual: '{row['status']}')"}
        if aprovado:
            return OficinaAppService.atualizar_progresso_os(id_os, "Aprovado")
        os_repo.atualizar_status(id_os, "Recusada")
        return True

    @staticmethod
    def tempo_medio_execucao():
        row = os_repo.tempo_medio()
        return row['media_dias'] if row else None

    @staticmethod
    def atualizar_progresso_os(id_os, novo_status):
        row = os_repo.buscar_por_id(id_os)
        if not row:
            return False
        os_obj = OrdemServico(0, 0, id_os=id_os, status=row['status'])
        if not os_obj.pode_transicionar_para(novo_status):
            return {"erro": f"Transição inválida de '{row['status']}' para '{novo_status}'"}
        os_repo.atualizar_status(id_os, novo_status, fechar=(novo_status == "Entregue"))
        return True

    @staticmethod
    def gerar_orcamento_consolidado(id_os):
        row = os_repo.buscar_por_id(id_os)
        if not row:
            return None

        os_dominio = OrdemServico(id_cliente=row['id_cliente'], id_veiculo=row['id_veiculo'],
                                  id_os=id_os, status=row['status'])

        df_pecas = os_repo.buscar_pecas(id_os)
        df_servicos = os_repo.buscar_servicos(id_os)

        valor_total = 0.0
        pecas = []
        servicos = []

        for _, r in df_pecas.iterrows():
            pecas.append({'peca': r['peca'], 'valor_peca': r['valor_total']})
            valor_total += r['valor_total']

        for _, r in df_servicos.iterrows():
            servicos.append({'servico': r['servico'], 'valor_servico': r['valor_total']})
            valor_total += r['valor_total']

        return {
            "id_os": os_dominio.id_os,
            "id_veiculo": os_dominio.id_veiculo,
            "id_cliente": os_dominio.id_cliente,
            "status": os_dominio.status,
            "total_orcamento": valor_total,
            "detalhes": {"pecas": pecas, "servicos": servicos}
        }
