import hmac
import os
from functools import wraps

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, create_access_token, get_jwt, get_jwt_identity
from application import OficinaAppService
from flasgger import swag_from

api = Blueprint('api', __name__)

ADMIN = 'admin'
CLIENTE = 'cliente'


def papel_requerido(*papeis):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            if get_jwt().get('role') not in papeis:
                return jsonify({"erro": "Acesso negado para este perfil"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def id_cliente_autenticado():
    return int(get_jwt_identity()) if get_jwt().get('role') == CLIENTE else None


@api.route('/login', methods=['POST'])
@swag_from({
    'tags': ['Login'],
    'description': (
        'Login de funcionários (perfil admin), retorna o Bearer Token. '
        'Clientes se autenticam por CPF no API Gateway, rota POST /auth.'
    ),
    'security': [],
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['username', 'senha'],
            'properties': {
                'username': {'type': 'string', 'example': 'admin'},
                'senha': {'type': 'string', 'example': 'admin123'}
            }
        }
    }],
    'responses': {
        200: {'description': 'Token gerado com sucesso'},
        401: {'description': 'Credenciais inválidas'}
    }
})
def login():
    data = request.json or {}
    username = data.get('username')
    senha = data.get('senha')
    if not username or not senha:
        return jsonify({"erro": "username e senha são obrigatórios"}), 400
    user_id = OficinaAppService.autenticar_usuario(username, senha)
    if not user_id:
        return jsonify({"erro": "Credenciais inválidas"}), 401
    token = create_access_token(identity=user_id, additional_claims={"role": ADMIN})
    return jsonify(access_token=token)

@api.route('/clientes', methods=['POST'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Clientes'],
    'description': 'Cadastra um novo cliente no sistema',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['nome', 'documento'],
            'properties': {
                'nome': {'type': 'string', 'example': 'Gabriel Vieira'},
                'documento': {'type': 'string', 'example': '12345678909'}
            }
        }
    }],
    'responses': {
        201: {'description': 'Cliente criado com sucesso'},
        400: {'description': 'Erro de validação (CPF/CNPJ inválido ou já cadastrado)'}
    }
})
def post_cliente():
    data = request.json
    resultado = OficinaAppService.cadastrar_cliente(data['nome'], data['documento'])
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    return jsonify({"id_cliente": resultado}), 201


@api.route('/clientes', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Clientes'],
    'description': 'Lista todos os clientes cadastrados',
    'responses': {
        200: {'description': 'Lista de clientes'}
    }
})
def listar_clientes():
    return jsonify(OficinaAppService.listar_clientes()), 200


@api.route('/clientes/<int:id_cliente>', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Clientes'],
    'description': 'Busca um cliente pelo ID',
    'parameters': [{'name': 'id_cliente', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Dados do cliente'},
        404: {'description': 'Cliente não encontrado'}
    }
})
def get_cliente(id_cliente):
    c = OficinaAppService.buscar_cliente_por_id(id_cliente)
    if not c:
        return jsonify({"erro": "Cliente não encontrado"}), 404
    return jsonify(c), 200


@api.route('/clientes/documento/<doc>', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Clientes'],
    'description': 'Busca cliente pelo CPF ou CNPJ',
    'parameters': [{'name': 'doc', 'in': 'path', 'type': 'string', 'required': True, 'example': '12345678909'}],
    'responses': {
        200: {'description': 'Dados do cliente'},
        404: {'description': 'Cliente não encontrado'}
    }
})
def get_cliente_por_documento(doc):
    resultado = OficinaAppService.buscar_cliente_por_documento(doc)
    if not resultado:
        return jsonify({"erro": "Cliente não encontrado"}), 404
    return jsonify(resultado), 200


@api.route('/clientes/<int:id_cliente>', methods=['PUT'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Clientes'],
    'description': 'Atualiza os dados de um cliente. O status inativo bloqueia a autenticação por CPF.',
    'parameters': [
        {'name': 'id_cliente', 'in': 'path', 'type': 'integer', 'required': True},
        {
            'name': 'body', 'in': 'body', 'required': True,
            'schema': {
                'type': 'object',
                'required': ['nome', 'documento'],
                'properties': {
                    'nome': {'type': 'string', 'example': 'Gabriel Vieira'},
                    'documento': {'type': 'string', 'example': '12345678909'},
                    'status': {'type': 'string', 'enum': ['ativo', 'inativo'], 'example': 'ativo'}
                }
            }
        }
    ],
    'responses': {
        200: {'description': 'Cliente atualizado'},
        400: {'description': 'Erro de validação'},
        404: {'description': 'Cliente não encontrado'}
    }
})
def put_cliente(id_cliente):
    data = request.json
    resultado = OficinaAppService.atualizar_cliente(id_cliente, data['nome'], data['documento'], data.get('status'))
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    if not resultado:
        return jsonify({"erro": "Cliente não encontrado"}), 404
    return jsonify({"mensagem": "Cliente atualizado"}), 200


@api.route('/clientes/<int:id_cliente>', methods=['DELETE'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Clientes'],
    'description': 'Remove um cliente pelo ID',
    'parameters': [{'name': 'id_cliente', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Cliente removido'},
        404: {'description': 'Cliente não encontrado'},
        409: {'description': 'Cliente possui ordens de serviço vinculadas'}
    }
})
def delete_cliente(id_cliente):
    resultado = OficinaAppService.deletar_cliente(id_cliente)
    if isinstance(resultado, dict):
        return jsonify(resultado), 409
    if not resultado:
        return jsonify({"erro": "Cliente não encontrado"}), 404
    return jsonify({"mensagem": "Cliente removido"}), 200


@api.route('/veiculos', methods=['POST'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Veículos'],
    'description': 'Cadastra um veículo',
    'parameters': [{
        'name': 'body', 'in': 'body', 'required': True,
        'schema': {
            'type': 'object',
            'required': ['placa', 'marca', 'modelo', 'ano'],
            'properties': {
                'placa': {'type': 'string', 'example': 'ABC1D23'},
                'marca': {'type': 'string', 'example': 'Toyota'},
                'modelo': {'type': 'string', 'example': 'Corolla'},
                'ano': {'type': 'integer', 'example': 2022}
            }
        }
    }],
    'responses': {
        201: {'description': 'Veículo criado'},
        400: {'description': 'Erro de validação (placa inválida ou já cadastrada)'}
    }
})
def post_veiculo():
    data = request.json
    resultado = OficinaAppService.cadastrar_veiculo(
        data['placa'], data['marca'], data['modelo'], data['ano']
    )
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    return jsonify({"id_veiculo": resultado}), 201


@api.route('/veiculos', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Veículos'],
    'description': 'Lista todos os veículos cadastrados',
    'responses': {
        200: {'description': 'Lista de veículos'}
    }
})
def listar_veiculos():
    return jsonify(OficinaAppService.listar_veiculos()), 200


@api.route('/veiculos/<int:id_veiculo>', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Veículos'],
    'description': 'Busca um veículo pelo ID',
    'parameters': [{'name': 'id_veiculo', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Dados do veículo'},
        404: {'description': 'Veículo não encontrado'}
    }
})
def get_veiculo(id_veiculo):
    v = OficinaAppService.buscar_veiculo_por_id(id_veiculo)
    if not v:
        return jsonify({"erro": "Veículo não encontrado"}), 404
    return jsonify(v), 200


@api.route('/veiculos/placa/<placa>', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Veículos'],
    'description': 'Busca veículo pela placa (formato antigo AAA9999 ou Mercosul AAA9A99)',
    'parameters': [{'name': 'placa', 'in': 'path', 'type': 'string', 'required': True, 'example': 'ABC1D23'}],
    'responses': {
        200: {'description': 'Dados do veículo'},
        404: {'description': 'Veículo não encontrado'}
    }
})
def get_veiculo_por_placa(placa):
    resultado = OficinaAppService.buscar_veiculo_por_placa(placa)
    if not resultado:
        return jsonify({"erro": "Veiculo não encontrado"}), 404
    return jsonify(resultado), 200


@api.route('/veiculos/<int:id_veiculo>', methods=['PUT'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Veículos'],
    'description': 'Atualiza os dados de um veículo',
    'parameters': [
        {'name': 'id_veiculo', 'in': 'path', 'type': 'integer', 'required': True},
        {
            'name': 'body', 'in': 'body', 'required': True,
            'schema': {
                'type': 'object',
                'required': ['placa', 'marca', 'modelo', 'ano'],
                'properties': {
                    'placa': {'type': 'string', 'example': 'ABC1D23'},
                    'marca': {'type': 'string', 'example': 'Toyota'},
                    'modelo': {'type': 'string', 'example': 'Corolla'},
                    'ano': {'type': 'integer', 'example': 2022}
                }
            }
        }
    ],
    'responses': {
        200: {'description': 'Veículo atualizado'},
        400: {'description': 'Erro de validação'},
        404: {'description': 'Veículo não encontrado'}
    }
})
def put_veiculo(id_veiculo):
    data = request.json
    resultado = OficinaAppService.atualizar_veiculo(
        id_veiculo, data['placa'], data['marca'], data['modelo'], data['ano']
    )
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    if not resultado:
        return jsonify({"erro": "Veículo não encontrado"}), 404
    return jsonify({"mensagem": "Veículo atualizado"}), 200


@api.route('/veiculos/<int:id_veiculo>', methods=['DELETE'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Veículos'],
    'description': 'Remove um veículo pelo ID',
    'parameters': [{'name': 'id_veiculo', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Veículo removido'},
        404: {'description': 'Veículo não encontrado'},
        409: {'description': 'Veículo possui ordens de serviço vinculadas'}
    }
})
def delete_veiculo(id_veiculo):
    resultado = OficinaAppService.deletar_veiculo(id_veiculo)
    if isinstance(resultado, dict):
        return jsonify(resultado), 409
    if not resultado:
        return jsonify({"erro": "Veículo não encontrado"}), 404
    return jsonify({"mensagem": "Veículo removido"}), 200


@api.route('/pecas', methods=['POST'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Peças'],
    'description': 'Cadastra uma peça no catálogo',
    'parameters': [{
        'name': 'body', 'in': 'body', 'required': True,
        'schema': {
            'type': 'object',
            'required': ['nome', 'valor_unitario'],
            'properties': {
                'nome': {'type': 'string', 'example': 'Filtro de óleo'},
                'valor_unitario': {'type': 'number', 'example': 35.90},
                'estoque': {'type': 'integer', 'example': 10}
            }
        }
    }],
    'responses': {
        201: {'description': 'Peça cadastrada'},
        400: {'description': 'Valor ou estoque inválido'}
    }
})
def post_peca():
    data = request.json
    resultado = OficinaAppService.cadastrar_peca(
        data['nome'], data['valor_unitario'], data.get('estoque', 0)
    )
    if isinstance(resultado, dict):
        return jsonify(resultado), 400
    return jsonify({"id_peca": resultado}), 201


@api.route('/pecas', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Peças'],
    'description': 'Lista todas as peças do catálogo',
    'responses': {
        200: {'description': 'Lista de peças'}
    }
})
def listar_pecas():
    return jsonify(OficinaAppService.listar_pecas()), 200


@api.route('/pecas/<int:id_peca>', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Peças'],
    'description': 'Busca uma peça pelo ID',
    'parameters': [{'name': 'id_peca', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Dados da peça'},
        404: {'description': 'Peça não encontrada'}
    }
})
def get_peca(id_peca):
    p = OficinaAppService.buscar_peca_por_id(id_peca)
    if not p:
        return jsonify({"erro": "Peça não encontrada"}), 404
    return jsonify(p), 200


@api.route('/pecas/<int:id_peca>', methods=['PUT'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Peças'],
    'description': 'Atualiza os dados de uma peça',
    'parameters': [
        {'name': 'id_peca', 'in': 'path', 'type': 'integer', 'required': True},
        {
            'name': 'body', 'in': 'body', 'required': True,
            'schema': {
                'type': 'object',
                'required': ['nome', 'valor_unitario', 'estoque'],
                'properties': {
                    'nome': {'type': 'string', 'example': 'Filtro de óleo'},
                    'valor_unitario': {'type': 'number', 'example': 35.90},
                    'estoque': {'type': 'integer', 'example': 10}
                }
            }
        }
    ],
    'responses': {
        200: {'description': 'Peça atualizada'},
        400: {'description': 'Valor ou estoque inválido'},
        404: {'description': 'Peça não encontrada'}
    }
})
def put_peca(id_peca):
    data = request.json
    resultado = OficinaAppService.atualizar_peca(id_peca, data['nome'], data['valor_unitario'], data['estoque'])
    if isinstance(resultado, dict):
        return jsonify(resultado), 400
    if not resultado:
        return jsonify({"erro": "Peça não encontrada"}), 404
    return jsonify({"mensagem": "Peça atualizada"}), 200


@api.route('/pecas/<int:id_peca>', methods=['DELETE'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Peças'],
    'description': 'Remove uma peça do catálogo',
    'parameters': [{'name': 'id_peca', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Peça removida'},
        404: {'description': 'Peça não encontrada'}
    }
})
def delete_peca(id_peca):
    resultado = OficinaAppService.deletar_peca(id_peca)
    if isinstance(resultado, dict):
        return jsonify(resultado), 409
    if not resultado:
        return jsonify({"erro": "Peça não encontrada"}), 404
    return jsonify({"mensagem": "Peça removida"}), 200


@api.route('/servicos', methods=['POST'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Serviços'],
    'description': 'Cadastra um serviço no catálogo',
    'parameters': [{
        'name': 'body', 'in': 'body', 'required': True,
        'schema': {
            'type': 'object',
            'required': ['nome', 'valor'],
            'properties': {
                'nome': {'type': 'string', 'example': 'Troca de óleo'},
                'valor': {'type': 'number', 'example': 120.00}
            }
        }
    }],
    'responses': {
        201: {'description': 'Serviço cadastrado'},
        400: {'description': 'Valor inválido'}
    }
})
def post_servico():
    data = request.json
    resultado = OficinaAppService.cadastrar_servico_catalogo(data['nome'], data['valor'])
    if isinstance(resultado, dict):
        return jsonify(resultado), 400
    return jsonify({"id_servico": resultado}), 201


@api.route('/servicos', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Serviços'],
    'description': 'Lista todos os serviços do catálogo',
    'responses': {
        200: {'description': 'Lista de serviços'}
    }
})
def listar_servicos():
    return jsonify(OficinaAppService.listar_servicos_catalogo()), 200


@api.route('/servicos/<int:id_servico>', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Serviços'],
    'description': 'Busca um serviço pelo ID',
    'parameters': [{'name': 'id_servico', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Dados do serviço'},
        404: {'description': 'Serviço não encontrado'}
    }
})
def get_servico(id_servico):
    s = OficinaAppService.buscar_servico_por_id(id_servico)
    if not s:
        return jsonify({"erro": "Serviço não encontrado"}), 404
    return jsonify(s), 200


@api.route('/servicos/<int:id_servico>', methods=['PUT'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Serviços'],
    'description': 'Atualiza os dados de um serviço',
    'parameters': [
        {'name': 'id_servico', 'in': 'path', 'type': 'integer', 'required': True},
        {
            'name': 'body', 'in': 'body', 'required': True,
            'schema': {
                'type': 'object',
                'required': ['nome', 'valor'],
                'properties': {
                    'nome': {'type': 'string', 'example': 'Troca de óleo'},
                    'valor': {'type': 'number', 'example': 120.00}
                }
            }
        }
    ],
    'responses': {
        200: {'description': 'Serviço atualizado'},
        400: {'description': 'Valor inválido'},
        404: {'description': 'Serviço não encontrado'}
    }
})
def put_servico(id_servico):
    data = request.json
    resultado = OficinaAppService.atualizar_servico(id_servico, data['nome'], data['valor'])
    if isinstance(resultado, dict):
        return jsonify(resultado), 400
    if not resultado:
        return jsonify({"erro": "Serviço não encontrado"}), 404
    return jsonify({"mensagem": "Serviço atualizado"}), 200


@api.route('/servicos/<int:id_servico>', methods=['DELETE'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Serviços'],
    'description': 'Remove um serviço do catálogo',
    'parameters': [{'name': 'id_servico', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Serviço removido'},
        404: {'description': 'Serviço não encontrado'}
    }
})
def delete_servico(id_servico):
    resultado = OficinaAppService.deletar_servico(id_servico)
    if isinstance(resultado, dict):
        return jsonify(resultado), 409
    if not resultado:
        return jsonify({"erro": "Serviço não encontrado"}), 404
    return jsonify({"mensagem": "Serviço removido"}), 200


@api.route('/os', methods=['POST'])
@papel_requerido(ADMIN, CLIENTE)
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': (
        'Cria uma nova ordem de serviço, opcionalmente já com peças e serviços. '
        'Com token de cliente (CPF), o id_cliente vem do próprio token e o campo é ignorado.'
    ),
    'parameters': [{
        'name': 'body', 'in': 'body', 'required': True,
        'schema': {
            'type': 'object',
            'required': ['id_veiculo'],
            'properties': {
                'id_cliente': {'type': 'integer', 'example': 1},
                'id_veiculo': {'type': 'integer', 'example': 2},
                'pecas': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'peca': {'type': 'string', 'example': 'Filtro de óleo'},
                            'valor_total': {'type': 'number', 'example': 80.0}
                        }
                    }
                },
                'servicos': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'servico': {'type': 'string', 'example': 'Troca de óleo'},
                            'valor_total': {'type': 'number', 'example': 150.0}
                        }
                    }
                }
            }
        }
    }],
    'responses': {
        201: {'description': 'OS criada'},
        400: {'description': 'Dados inválidos, cliente ou veículo inexistente'}
    }
})
def criar_os():
    data = request.json or {}
    id_cliente = id_cliente_autenticado() or data.get('id_cliente')
    if not id_cliente or not data.get('id_veiculo'):
        return jsonify({"erro": "id_cliente e id_veiculo são obrigatórios"}), 400
    resultado = OficinaAppService.abrir_ordem_servico(
        id_cliente, data['id_veiculo'],
        pecas=data.get('pecas'), servicos=data.get('servicos')
    )
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    return jsonify({"id_os": resultado}), 201


@api.route('/os', methods=['GET'])
@papel_requerido(ADMIN, CLIENTE)
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': (
        'Lista ordens de serviço ativas, ordenadas por prioridade de status e data de abertura. '
        'Com token de cliente, lista apenas as ordens do próprio cliente.'
    ),
    'responses': {
        200: {'description': 'Lista de OS ativas (exclui Finalizada, Entregue e Recusada)'}
    }
})
def listar_os():
    return jsonify(OficinaAppService.listar_ordens(id_cliente_autenticado())), 200


@api.route('/os/tempo-medio', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': 'Tempo médio de execução das OS entregues e tempo médio em cada status, em dias',
    'responses': {
        200: {'description': 'Médias em dias, geral e por status'}
    }
})
def tempo_medio_os():
    return jsonify(OficinaAppService.tempo_medio_execucao()), 200


@api.route('/os/<int:id_os>', methods=['GET'])
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': 'Retorna os dados completos da OS com orçamento consolidado (rota pública)',
    'security': [],
    'parameters': [{'name': 'id_os', 'in': 'path', 'type': 'integer', 'required': True, 'example': 1}],
    'responses': {
        200: {'description': 'Dados completos da OS'},
        404: {'description': 'OS não encontrada'}
    }
})
def get_os(id_os):
    resultado = OficinaAppService.gerar_orcamento_consolidado(id_os)
    if not resultado:
        return jsonify({"erro": "Ordem de Serviço não encontrada"}), 404
    return jsonify(resultado), 200


@api.route('/os/<int:id_os>/status', methods=['GET'])
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': 'Retorna apenas o status atual da OS (rota pública)',
    'security': [],
    'parameters': [{'name': 'id_os', 'in': 'path', 'type': 'integer', 'required': True, 'example': 1}],
    'responses': {
        200: {'description': 'Status atual da OS'},
        404: {'description': 'OS não encontrada'}
    }
})
def get_os_status(id_os):
    resultado = OficinaAppService.gerar_orcamento_consolidado(id_os)
    if not resultado:
        return jsonify({"erro": "OS não encontrada"}), 404
    return jsonify({"id_os": id_os, "status": resultado["status"]}), 200


@api.route('/os/<int:id_os>/historico', methods=['GET'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': 'Histórico de status da OS, com a data de início de cada etapa',
    'parameters': [{'name': 'id_os', 'in': 'path', 'type': 'integer', 'required': True, 'example': 1}],
    'responses': {
        200: {'description': 'Lista de status em ordem cronológica'},
        404: {'description': 'OS não encontrada'}
    }
})
def get_os_historico(id_os):
    historico = OficinaAppService.historico_os(id_os)
    if not historico:
        return jsonify({"erro": "OS não encontrada"}), 404
    return jsonify(historico), 200


@api.route('/os/<int:id_os>/status', methods=['PUT'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': (
        'Avança o status da OS conforme o fluxo permitido: Recebida, Em diagnóstico, Aguardando aprovação, '
        'e então Aprovado, Recusada ou Solicitado alterações (que volta para Em diagnóstico). '
        'Aprovado segue para Em execução ou Aguardando peças, que também pode ir para Recusada. '
        'Depois vêm Finalizada e Entregue.'
    ),
    'parameters': [
        {'name': 'id_os', 'in': 'path', 'type': 'integer', 'required': True, 'example': 1},
        {
            'name': 'body', 'in': 'body', 'required': True,
            'schema': {
                'type': 'object',
                'required': ['status'],
                'properties': {
                    'status': {
                        'type': 'string',
                        'enum': ['Em diagnóstico', 'Aguardando aprovação', 'Aprovado', 'Recusada',
                                 'Solicitado alterações', 'Aguardando peças',
                                 'Em execução', 'Finalizada', 'Entregue'],
                        'example': 'Em diagnóstico'
                    }
                }
            }
        }
    ],
    'responses': {
        200: {'description': 'Status atualizado'},
        400: {'description': 'Transição inválida ou OS não encontrada'}
    }
})
def atualizar_status(id_os):
    data = request.json
    resultado = OficinaAppService.atualizar_progresso_os(id_os, data['status'])
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    if resultado is False:
        return jsonify({"erro": "OS não encontrada ou transição inválida"}), 400
    return jsonify({"mensagem": "Status atualizado"}), 200


@api.route('/os/<int:id_os>/aprovacao', methods=['POST'])
@papel_requerido(ADMIN, CLIENTE)
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': (
        'Aprova ou recusa o orçamento de uma OS que esteja em "Aguardando aprovação". '
        'Com token de cliente, só é permitido para as ordens do próprio cliente.'
    ),
    'parameters': [
        {'name': 'id_os', 'in': 'path', 'type': 'integer', 'required': True, 'example': 1},
        {
            'name': 'body', 'in': 'body', 'required': True,
            'schema': {
                'type': 'object',
                'required': ['aprovado'],
                'properties': {
                    'aprovado': {'type': 'boolean', 'example': True}
                }
            }
        }
    ],
    'responses': {
        200: {'description': 'Orçamento aprovado (status Aprovado) ou recusado (status Recusada)'},
        400: {'description': 'OS não está aguardando aprovação ou campo ausente'},
        403: {'description': 'OS não pertence ao cliente autenticado'}
    }
})
def aprovar_orcamento(id_os):
    data = request.json or {}
    if 'aprovado' not in data:
        return jsonify({"erro": "'aprovado' é obrigatório"}), 400
    id_cliente = id_cliente_autenticado()
    if id_cliente and not OficinaAppService.pertence_ao_cliente(id_os, id_cliente):
        return jsonify({"erro": "Acesso negado a esta ordem de serviço"}), 403
    resultado = OficinaAppService.aprovar_orcamento(id_os, data['aprovado'])
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    acao = "aprovado" if data['aprovado'] else "recusado"
    return jsonify({"mensagem": f"Orçamento {acao}"}), 200


@api.route('/os/<int:id_os>/servicos', methods=['POST'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': 'Adiciona um serviço a uma OS existente',
    'parameters': [
        {'name': 'id_os', 'in': 'path', 'type': 'integer', 'required': True, 'example': 1},
        {
            'name': 'body', 'in': 'body', 'required': True,
            'schema': {
                'type': 'object',
                'required': ['servico', 'valor_total'],
                'properties': {
                    'servico': {'type': 'string', 'example': 'Troca de óleo'},
                    'valor_total': {'type': 'number', 'example': 150.0}
                }
            }
        }
    ],
    'responses': {
        201: {'description': 'Serviço adicionado'},
        400: {'description': 'OS inexistente ou valor inválido'}
    }
})
def adicionar_servico(id_os):
    data = request.json
    resultado = OficinaAppService.adicionar_servico(id_os, data['servico'], data['valor_total'])
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    return jsonify({"mensagem": "Serviço adicionado"}), 201


@api.route('/os/<int:id_os>/pecas', methods=['POST'])
@papel_requerido(ADMIN)
@swag_from({
    'tags': ['Ordem de Serviço'],
    'description': 'Adiciona uma peça a uma OS existente',
    'parameters': [
        {'name': 'id_os', 'in': 'path', 'type': 'integer', 'required': True, 'example': 1},
        {
            'name': 'body', 'in': 'body', 'required': True,
            'schema': {
                'type': 'object',
                'required': ['peca', 'valor_total'],
                'properties': {
                    'peca': {'type': 'string', 'example': 'Filtro de óleo'},
                    'valor_total': {'type': 'number', 'example': 80.0}
                }
            }
        }
    ],
    'responses': {
        201: {'description': 'Peça adicionada'},
        400: {'description': 'OS inexistente ou valor inválido'}
    }
})
def adicionar_peca(id_os):
    data = request.json
    resultado = OficinaAppService.adicionar_peca(id_os, data['peca'], data['valor_total'])
    if isinstance(resultado, dict) and "erro" in resultado:
        return jsonify(resultado), 400
    return jsonify({"mensagem": "Peça adicionada"}), 201


@api.route('/os/webhook/status', methods=['POST'])
@swag_from({
    'tags': ['Webhook'],
    'description': (
        'Atualiza o status de uma OS via webhook externo. '
        'Autenticado pelo header X-Webhook-Token ou campo "token" no body.'
    ),
    'security': [],
    'parameters': [{
        'name': 'body', 'in': 'body', 'required': True,
        'schema': {
            'type': 'object',
            'required': ['id_os', 'status'],
            'properties': {
                'id_os': {'type': 'integer', 'example': 1},
                'status': {'type': 'string', 'example': 'Em diagnóstico'},
                'token': {'type': 'string', 'example': 'seu-token-seguro'}
            }
        }
    }],
    'responses': {
        200: {'description': 'Status atualizado'},
        400: {'description': 'Campos ausentes ou transição inválida'},
        401: {'description': 'Token inválido'}
    }
})
def webhook_status():
    data = request.json or {}
    token = request.headers.get('X-Webhook-Token') or data.get('token') or ''
    if not hmac.compare_digest(token.encode(), os.getenv('WEBHOOK_TOKEN', 'webhook-secret').encode()):
        OficinaAppService.registrar_erro_integracao('webhook', 'token_invalido')
        return jsonify({"erro": "Token inválido"}), 401
    id_os = data.get('id_os')
    novo_status = data.get('status')
    if not id_os or not novo_status:
        OficinaAppService.registrar_erro_integracao('webhook', 'campos_ausentes')
        return jsonify({"erro": "id_os e status são obrigatórios"}), 400
    resultado = OficinaAppService.atualizar_progresso_os(id_os, novo_status)
    if isinstance(resultado, dict) and "erro" in resultado:
        OficinaAppService.registrar_erro_integracao('webhook', 'transicao_invalida')
        return jsonify(resultado), 400
    if resultado is False:
        OficinaAppService.registrar_erro_integracao('webhook', 'os_nao_encontrada')
        return jsonify({"erro": "OS não encontrada ou transição inválida"}), 400
    return jsonify({"mensagem": "Status atualizado"}), 200


@api.route('/health', methods=['GET'])
@swag_from({
    'tags': ['Saúde'],
    'description': 'Liveness: indica que a aplicação está no ar',
    'security': [],
    'responses': {
        200: {'description': 'Aplicação no ar'}
    }
})
def health():
    return jsonify({"status": "ok"}), 200


@api.route('/ready', methods=['GET'])
@swag_from({
    'tags': ['Saúde'],
    'description': 'Readiness: indica que a aplicação consegue acessar o banco de dados',
    'security': [],
    'responses': {
        200: {'description': 'Pronta para receber tráfego'},
        503: {'description': 'Banco de dados indisponível'}
    }
})
def ready():
    if not OficinaAppService.banco_disponivel():
        return jsonify({"status": "indisponivel"}), 503
    return jsonify({"status": "ok"}), 200
