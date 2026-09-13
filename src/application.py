import logging
from functools import wraps

from domain import Cliente, Veiculo, OrdemServico, DomainError, PecasCarro, ServicosCarro, Usuario
from ports import (ClienteRepositoryPort, VeiculoRepositoryPort, PecaRepositoryPort, ServicoRepositoryPort,
                   OrdemServicoRepositoryPort, UsuarioRepositoryPort, SaudeRepositoryPort, MetricasPort)

logger = logging.getLogger('oficina.aplicacao')

cliente_repo: ClienteRepositoryPort = None
veiculo_repo: VeiculoRepositoryPort = None
peca_repo: PecaRepositoryPort = None
servico_repo: ServicoRepositoryPort = None
os_repo: OrdemServicoRepositoryPort = None
usuario_repo: UsuarioRepositoryPort = None
saude_repo: SaudeRepositoryPort = None
metricas: MetricasPort = None


def monitorar_os(operacao):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                logger.exception('falha_processamento_os', extra={'operacao': operacao})
                metricas.falha_processamento_os(operacao)
                raise
        return wrapper
    return decorator


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
    def atualizar_cliente(id_cliente, nome, documento, status=None):
        try:
            c = Cliente(documento=documento, nome=nome, status=status or "ativo")
            rows = cliente_repo.atualizar(id_cliente, c.nome, c.documento, status)
            return rows > 0
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def deletar_cliente(id_cliente):
        try:
            return cliente_repo.deletar(id_cliente) > 0
        except DomainError as e:
            return {"erro": str(e)}

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
        try:
            return veiculo_repo.deletar(id_veiculo) > 0
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def cadastrar_peca(nome, valor_unitario, estoque=0):
        try:
            return peca_repo.criar(nome, float(valor_unitario), int(estoque))
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def listar_pecas():
        return peca_repo.listar()

    @staticmethod
    def buscar_peca_por_id(id_peca):
        return peca_repo.buscar_por_id(id_peca)

    @staticmethod
    def atualizar_peca(id_peca, nome, valor_unitario, estoque):
        try:
            return peca_repo.atualizar(id_peca, nome, float(valor_unitario), int(estoque)) > 0
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def deletar_peca(id_peca):
        try:
            return peca_repo.deletar(id_peca) > 0
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def cadastrar_servico_catalogo(nome, valor):
        try:
            return servico_repo.criar(nome, float(valor))
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def listar_servicos_catalogo():
        return servico_repo.listar()

    @staticmethod
    def buscar_servico_por_id(id_servico):
        return servico_repo.buscar_por_id(id_servico)

    @staticmethod
    def atualizar_servico(id_servico, nome, valor):
        try:
            return servico_repo.atualizar(id_servico, nome, float(valor)) > 0
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def deletar_servico(id_servico):
        try:
            return servico_repo.deletar(id_servico) > 0
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    @monitorar_os('abertura')
    def abrir_ordem_servico(id_cliente, id_veiculo, pecas=None, servicos=None):
        try:
            os_dominio = OrdemServico(id_cliente=id_cliente, id_veiculo=id_veiculo)
            itens_pecas = [PecasCarro(None, p['peca'], p['valor_total']) for p in (pecas or [])]
            itens_servicos = [ServicosCarro(None, s['servico'], s['valor_total']) for s in (servicos or [])]
            id_os = os_repo.criar(
                os_dominio.id_cliente, os_dominio.id_veiculo, os_dominio.status,
                [(p.peca, p.valor_total) for p in itens_pecas],
                [(s.servico, s.valor_total) for s in itens_servicos]
            )
        except DomainError as e:
            return {"erro": str(e)}
        metricas.os_aberta()
        logger.info('os_aberta', extra={'id_os': id_os, 'id_cliente': id_cliente})
        return id_os

    @staticmethod
    @monitorar_os('inclusao_peca')
    def adicionar_peca(id_os, nome_peca, valor):
        try:
            peca = PecasCarro(id_os=id_os, peca=nome_peca, valor_total=valor)
            return os_repo.adicionar_peca(peca.id_os, peca.peca, peca.valor_total)
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    @monitorar_os('inclusao_servico')
    def adicionar_servico(id_os, nome_servico, valor):
        try:
            s = ServicosCarro(id_os=id_os, servico=nome_servico, valor_total=valor)
            return os_repo.adicionar_servico(s.id_os, s.servico, s.valor_total)
        except DomainError as e:
            return {"erro": str(e)}

    @staticmethod
    def listar_ordens(id_cliente=None):
        return os_repo.listar_ativas(id_cliente)

    @staticmethod
    def pertence_ao_cliente(id_os, id_cliente):
        row = os_repo.buscar_por_id(id_os)
        return bool(row) and row['id_cliente'] == id_cliente

    @staticmethod
    def historico_os(id_os):
        return os_repo.historico(id_os)

    @staticmethod
    @monitorar_os('aprovacao')
    def aprovar_orcamento(id_os, aprovado):
        row = os_repo.buscar_por_id(id_os)
        if not row:
            return {"erro": "OS não encontrada"}
        if row['status'] != "Aguardando aprovação":
            return {"erro": f"OS não está aguardando aprovação (status atual: '{row['status']}')"}
        return OficinaAppService._transicionar(row, "Aprovado" if aprovado else "Recusada")

    @staticmethod
    def tempo_medio_execucao():
        return {
            "media_dias": os_repo.tempo_medio(),
            "por_status": {r['status']: r['media_dias'] for r in os_repo.tempo_medio_por_status()},
        }

    @staticmethod
    @monitorar_os('atualizacao_status')
    def atualizar_progresso_os(id_os, novo_status):
        row = os_repo.buscar_por_id(id_os)
        if not row:
            return False
        return OficinaAppService._transicionar(row, novo_status)

    @staticmethod
    def _transicionar(row, novo_status):
        os_obj = OrdemServico(row['id_cliente'], row['id_veiculo'], id_os=row['id_os'], status=row['status'])
        if not os_obj.pode_transicionar_para(novo_status):
            logger.warning('transicao_rejeitada', extra={
                'id_os': os_obj.id_os, 'status_atual': os_obj.status, 'status_solicitado': novo_status
            })
            return {"erro": f"Transição inválida de '{os_obj.status}' para '{novo_status}'"}
        segundos = os_repo.atualizar_status(os_obj.id_os, os_obj.status, novo_status, fechar=novo_status == "Entregue")
        if segundos is None:
            return {"erro": "A OS foi alterada por outra operação, tente novamente"}
        metricas.status_alterado(os_obj.status, novo_status, segundos)
        logger.info('status_alterado', extra={
            'id_os': os_obj.id_os, 'status_anterior': os_obj.status, 'novo_status': novo_status,
            'segundos_no_status': segundos
        })
        return True

    @staticmethod
    def gerar_orcamento_consolidado(id_os):
        row = os_repo.buscar_por_id(id_os)
        if not row:
            return None

        os_dominio = OrdemServico(id_cliente=row['id_cliente'], id_veiculo=row['id_veiculo'],
                                  id_os=id_os, status=row['status'])

        pecas = [{'peca': p['peca'], 'valor_peca': p['valor_total']} for p in os_repo.buscar_pecas(id_os)]
        servicos = [{'servico': s['servico'], 'valor_servico': s['valor_total']} for s in os_repo.buscar_servicos(id_os)]
        valor_total = sum(p['valor_peca'] for p in pecas) + sum(s['valor_servico'] for s in servicos)

        return {
            "id_os": os_dominio.id_os,
            "id_veiculo": os_dominio.id_veiculo,
            "id_cliente": os_dominio.id_cliente,
            "status": os_dominio.status,
            "total_orcamento": float(valor_total),
            "detalhes": {"pecas": pecas, "servicos": servicos}
        }

    @staticmethod
    def banco_disponivel():
        try:
            return saude_repo.ping()
        except Exception:
            logger.exception('banco_indisponivel')
            return False

    @staticmethod
    def registrar_erro_integracao(integracao, motivo):
        logger.warning('erro_integracao', extra={'integracao': integracao, 'motivo': motivo})
        metricas.erro_integracao(integracao, motivo)
