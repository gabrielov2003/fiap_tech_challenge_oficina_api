import pytest
from flask_jwt_extended import create_access_token
from pytest_bdd import given, parsers, scenarios, then, when

import application
from app import create_app
from application import SagaOrdemServico
from unit_tests import evento, gerar_cpf, gerar_placa, preparar_mensageria

scenarios('features/saga_ordem_servico.feature')


@pytest.fixture
def contexto():
    app = create_app()
    http = app.test_client()
    token = http.post('/api/login', json={'username': 'admin', 'senha': 'admin123'}).get_json()['access_token']
    return {'app': app, 'http': http, 'admin': {'Authorization': f'Bearer {token}'}, 'mensageria': preparar_mensageria()}


@given('um cliente com um veículo cadastrado')
def cliente_com_veiculo(contexto):
    http, admin = contexto['http'], contexto['admin']
    contexto['id_cliente'] = http.post(
        '/api/clientes', json={'nome': 'Maria Silva', 'documento': gerar_cpf()}, headers=admin
    ).get_json()['id_cliente']
    contexto['id_veiculo'] = http.post(
        '/api/veiculos', json={'placa': gerar_placa(), 'marca': 'Fiat', 'modelo': 'Argo', 'ano': 2022}, headers=admin
    ).get_json()['id_veiculo']


@when('o cliente abre uma OS com uma troca de óleo de 150 reais')
def abrir_os(contexto):
    with contexto['app'].app_context():
        token = create_access_token(identity=str(contexto['id_cliente']), additional_claims={'role': 'cliente'})
    resposta = contexto['http'].post(
        '/api/os',
        json={'id_veiculo': contexto['id_veiculo'], 'servicos': [{'servico': 'Troca de óleo', 'valor_total': 150}]},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resposta.status_code == 201
    contexto['id_os'] = resposta.get_json()['id_os']


@when(parsers.parse('o Billing publica "{tipo}"'))
def billing_publica(contexto, tipo):
    evento(contexto['id_os'], tipo)


@when(parsers.parse('a Execução avisa o status "{status}"'))
def execucao_avisa_status(contexto, status):
    evento(contexto['id_os'], 'ExecucaoAtualizada', status=status)


@when(parsers.parse('a Execução avisa a falha "{motivo}"'))
def execucao_avisa_falha(contexto, motivo):
    evento(contexto['id_os'], 'ExecucaoFalhou', status='Falhou', motivo=motivo)


@when('o funcionário marca a OS como entregue')
def marcar_entregue(contexto):
    resposta = contexto['http'].put(
        f"/api/os/{contexto['id_os']}/status", json={'status': 'Entregue'}, headers=contexto['admin']
    )
    assert resposta.status_code == 200


@then(parsers.parse('a OS fica com o status "{status}"'))
def os_fica_com_status(contexto, status):
    assert contexto['http'].get(f"/api/os/{contexto['id_os']}/status").get_json()['status'] == status


@then(parsers.parse('o comando "{tipo}" é publicado na fila "{fila}"'))
def comando_publicado(contexto, tipo, fila):
    while SagaOrdemServico.publicar_pendentes():
        pass
    enviados = [(f, m['tipo']) for f, m in contexto['mensageria'].enviadas if m['id_os'] == contexto['id_os']]
    assert (application.filas[fila], tipo) in enviados
