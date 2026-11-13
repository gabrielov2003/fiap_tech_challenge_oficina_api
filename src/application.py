import logging
from functools import wraps

from domain import Cliente, Veiculo, OrdemServico, DomainError, PecasCarro, ServicosCarro, Usuario, STATUS_MANUAIS
from ports import (ClienteRepositoryPort, VeiculoRepositoryPort, PecaRepositoryPort, ServicoRepositoryPort,
                   OrdemServicoRepositoryPort, UsuarioRepositoryPort, SaudeRepositoryPort, MetricasPort,
                   MensageriaPort)

logger = logging.getLogger('oficina.aplicacao')

cliente_repo: ClienteRepositoryPort = None
veiculo_repo: VeiculoRepositoryPort = None
peca_repo: PecaRepositoryPort = None
servico_repo: ServicoRepositoryPort = None
os_repo: OrdemServicoRepositoryPort = None
usuario_repo: UsuarioRepositoryPort = None
saude_repo: SaudeRepositoryPort = None
metricas: MetricasPort = None
mensageria: MensageriaPort = None
filas = {'eventos': None, 'billing': None, 'execucao': None}

EVENTOS_SAGA = {
    'OrcamentoGerado': "Aguardando aprovação",
    'OrcamentoFalhou': "Cancelada",
    'OrcamentoAprovado': "Aguardando pagamento",
    'OrcamentoRecusado': "Recusada",
    'PagamentoAprovado': "Aprovado",
    'PagamentoRecusado': "Cancelada",
    'ExecucaoFalhou': "Cancelada",
}


class MensagemInvalida(Exception):
    pass


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
    def abrir_ordem_servico(id_cliente, id_veiculo, pecas=None, servicos=None, correlation_id=None):
        try:
            os_dominio = OrdemServico(id_cliente=id_cliente, id_veiculo=id_veiculo)
            itens_pecas = [PecasCarro(None, p['peca'], p['valor_total']) for p in (pecas or [])]
            itens_servicos = [ServicosCarro(None, s['servico'], s['valor_total']) for s in (servicos or [])]
            if not itens_pecas and not itens_servicos:
                raise DomainError("Informe pelo menos uma peça ou um serviço para gerar o orçamento")
            gerar_orcamento = {
                'tipo': 'GerarOrcamento',
                'dados': {'id_cliente': id_cliente, 'itens': itens_da_os(itens_pecas, itens_servicos)},
                'correlation_id': correlation_id,
            }
            id_os = os_repo.criar(
                os_dominio.id_cliente, os_dominio.id_veiculo, os_dominio.status,
                [(p.peca, p.valor_total) for p in itens_pecas],
                [(s.servico, s.valor_total) for s in itens_servicos],
                mensagens=[(filas['billing'], gerar_orcamento)]
            )
        except DomainError as e:
            return {"erro": str(e)}
        metricas.os_aberta()
        logger.info('os_aberta', extra={'id_os': id_os, 'id_cliente': id_cliente})
        return id_os

    @staticmethod
    def listar_ordens(id_cliente=None):
        return os_repo.listar_ativas(id_cliente)

    @staticmethod
    def historico_os(id_os):
        return os_repo.historico(id_os)

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
        if novo_status not in STATUS_MANUAIS:
            return {"erro": f"O status '{novo_status}' é controlado pela saga, manualmente só é possível marcar 'Entregue'"}
        return OficinaAppService._transicionar(row, novo_status)

    @staticmethod
    def _transicionar(row, novo_status, mensagens=()):
        os_obj = OrdemServico(row['id_cliente'], row['id_veiculo'], id_os=row['id_os'], status=row['status'])
        if not os_obj.pode_transicionar_para(novo_status):
            logger.warning('transicao_rejeitada', extra={
                'id_os': os_obj.id_os, 'status_atual': os_obj.status, 'status_solicitado': novo_status
            })
            return {"erro": f"Transição inválida de '{os_obj.status}' para '{novo_status}'"}
        segundos = os_repo.atualizar_status(
            os_obj.id_os, os_obj.status, novo_status, fechar=novo_status == "Entregue", mensagens=mensagens
        )
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



def itens_da_os(pecas, servicos):
    return (
        [{'descricao': p.peca, 'tipo': 'peca', 'valor': p.valor_total} for p in pecas]
        + [{'descricao': s.servico, 'tipo': 'servico', 'valor': s.valor_total} for s in servicos]
    )


class SagaOrdemServico:
    @staticmethod
    def tratar_evento(mensagem):
        tipo, dados = mensagem.get('tipo'), mensagem.get('dados') or {}
        row = os_repo.buscar_por_id(mensagem['id_os']) if mensagem.get('id_os') else None
        contexto = {'tipo': tipo, 'id_os': mensagem.get('id_os'), 'correlation_id': mensagem.get('correlation_id')}
        if row and tipo == 'PagamentoEstornado':
            logger.info('compensacao_concluida', extra=contexto)
            metricas.evento_saga(tipo, 'processado')
            return
        novo_status = dados.get('status') if tipo == 'ExecucaoAtualizada' else EVENTOS_SAGA.get(tipo)
        if not row or not novo_status:
            raise MensagemInvalida(f"Evento inválido: {tipo}")
        os_obj = OrdemServico(row['id_cliente'], row['id_veiculo'], id_os=row['id_os'], status=row['status'])
        if not os_obj.pode_transicionar_para(novo_status):
            logger.info('evento_ignorado', extra={**contexto, 'status_atual': row['status'], 'status_evento': novo_status})
            metricas.evento_saga(tipo, 'ignorado')
            return
        comandos = SagaOrdemServico._comandos(tipo, row, dados, mensagem.get('correlation_id'))
        if OficinaAppService._transicionar(row, novo_status, comandos) is not True:
            raise RuntimeError(f"OS {row['id_os']} alterada por outra operação, o evento será reprocessado")
        metricas.evento_saga(tipo, 'processado')
        logger.info('evento_processado', extra={**contexto, 'novo_status': novo_status})

    @staticmethod
    def _comandos(tipo, row, dados, correlation_id):
        if tipo == 'PagamentoAprovado':
            pecas = [PecasCarro(row['id_os'], p['peca'], p['valor_total']) for p in os_repo.buscar_pecas(row['id_os'])]
            servicos = [
                ServicosCarro(row['id_os'], s['servico'], s['valor_total']) for s in os_repo.buscar_servicos(row['id_os'])
            ]
            return [(filas['execucao'], {
                'tipo': 'IniciarExecucao', 'id_os': row['id_os'],
                'dados': {'itens': itens_da_os(pecas, servicos)}, 'correlation_id': correlation_id,
            })]
        if tipo == 'ExecucaoFalhou':
            logger.warning('compensacao_iniciada', extra={'id_os': row['id_os'], 'motivo': dados.get('motivo')})
            return [(filas['billing'], {
                'tipo': 'EstornarPagamento', 'id_os': row['id_os'],
                'dados': {'motivo': dados.get('motivo')}, 'correlation_id': correlation_id,
            })]
        return []

    @staticmethod
    def publicar_pendentes():
        return os_repo.publicar_outbox(mensageria.enviar)


def processar_eventos():
    try:
        SagaOrdemServico.publicar_pendentes()
    except Exception:
        logger.exception('falha_publicacao_outbox')
        metricas.erro_integracao('sqs', 'falha_publicacao')
    for mensagem, recibo in mensageria.receber(filas['eventos']):
        contexto = {
            'tipo': mensagem.get('tipo'), 'id_os': mensagem.get('id_os'), 'correlation_id': mensagem.get('correlation_id')
        }
        try:
            SagaOrdemServico.tratar_evento(mensagem)
        except MensagemInvalida:
            logger.warning('mensagem_invalida', extra=contexto)
            metricas.erro_integracao('sqs', 'mensagem_invalida')
        except Exception:
            logger.exception('falha_processamento_mensagem', extra=contexto)
            metricas.erro_integracao('sqs', 'falha_processamento')
            continue
        mensageria.confirmar(filas['eventos'], recibo)
