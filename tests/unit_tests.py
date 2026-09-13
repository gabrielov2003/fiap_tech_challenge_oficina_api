import unittest
import json
import random
import string
import sys
import os
import time
import uuid

import jwt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from app import create_app
from infrastructure import Infrastructure


def gerar_cpf():
    def calc_digito(cpf, peso):
        soma = sum(int(cpf[i]) * (peso - i) for i in range(len(cpf)))
        resto = (soma * 10) % 11
        return resto if resto < 10 else 0

    cpf = [random.randint(0, 9) for _ in range(9)]
    cpf.append(calc_digito(cpf, 10))
    cpf.append(calc_digito(cpf, 11))
    return ''.join(map(str, cpf))


def gerar_placa():
    letras = string.ascii_uppercase
    return (
        random.choice(letras) +
        random.choice(letras) +
        random.choice(letras) +
        str(random.randint(0, 9)) +
        random.choice(letras) +
        str(random.randint(0, 9)) +
        str(random.randint(0, 9))
    )


class TestAPI(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Login
        response = self.client.post(
            '/api/login',
            content_type='application/json',
            data=json.dumps({"username": "admin", "senha": "admin123"})
        )
        self.token = response.get_json()['access_token']

        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

    def headers_cliente(self, id_cliente, cpf):
        agora = int(time.time())
        claims = {
            "sub": str(id_cliente), "role": "cliente", "cpf": cpf, "type": "access", "fresh": False,
            "jti": str(uuid.uuid4()), "iat": agora, "nbf": agora, "exp": agora + 3600
        }
        token = jwt.encode(claims, self.app.config['JWT_SECRET_KEY'], algorithm="HS256")
        return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    def criar_cliente(self):
        cpf = gerar_cpf()
        response = self.client.post(
            '/api/clientes',
            headers=self.headers,
            data=json.dumps({
                "documento": cpf,
                "nome": "Gabriel Vieira"
            })
        )
        return cpf, response.get_json()['id_cliente']

    def criar_veiculo(self):
        placa = gerar_placa()
        response = self.client.post(
            '/api/veiculos',
            headers=self.headers,
            data=json.dumps({
                "ano": 2022,
                "marca": "Toyota",
                "modelo": "Corolla",
                "placa": placa
            })
        )
        return placa, response.get_json()['id_veiculo']

    def criar_os(self, id_cliente, id_veiculo):
        response = self.client.post(
            '/api/os',
            headers=self.headers,
            data=json.dumps({
                "id_cliente": id_cliente,
                "id_veiculo": id_veiculo
            })
        )
        return response.get_json()['id_os']

    def avancar_status(self, id_os, *status_lista):
        for status in status_lista:
            self.client.put(f'/api/os/{id_os}/status', headers=self.headers, data=json.dumps({"status": status}))


    def test_login(self):
        response = self.client.post(
            '/api/login',
            content_type='application/json',
            data=json.dumps({"username": "admin", "senha": "admin123"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access_token', response.get_json())

    def test_senha_do_admin_atualizada_pela_variavel(self):
        anterior = os.environ.get('ADMIN_PASSWORD')
        os.environ['ADMIN_PASSWORD'] = 'nova_senha_do_admin'
        try:
            Infrastructure.init_db()
            nova = self.client.post('/api/login', content_type='application/json',
                                    data=json.dumps({"username": "admin", "senha": "nova_senha_do_admin"}))
            antiga = self.client.post('/api/login', content_type='application/json',
                                      data=json.dumps({"username": "admin", "senha": "admin123"}))
        finally:
            os.environ['ADMIN_PASSWORD'] = 'admin123'
            Infrastructure.init_db()
            if anterior is None:
                del os.environ['ADMIN_PASSWORD']
            else:
                os.environ['ADMIN_PASSWORD'] = anterior
        self.assertEqual(nova.status_code, 200)
        self.assertEqual(antiga.status_code, 401)

    def test_criar_cliente(self):
        cpf, _ = self.criar_cliente()
        self.assertIsNotNone(cpf)

    def test_buscar_cliente(self):
        cpf, _ = self.criar_cliente()

        response = self.client.get(
            f'/api/clientes/documento/{cpf}',
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)

    def test_criar_veiculo(self):
        _, id_veiculo = self.criar_veiculo()
        self.assertIsNotNone(id_veiculo)

    def test_buscar_veiculo(self):
        placa, _ = self.criar_veiculo()

        response = self.client.get(
            f'/api/veiculos/placa/{placa}',
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)

    def test_criar_os(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()

        id_os = self.criar_os(id_cliente, id_veiculo)
        self.assertIsNotNone(id_os)

    def test_atualizar_status(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.put(
            f'/api/os/{id_os}/status',
            headers=self.headers,
            data=json.dumps({"status": "Em diagnóstico"})
        )
        self.assertEqual(response.status_code, 200)

    def test_adicionar_servico(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.post(
            f'/api/os/{id_os}/servicos',
            headers=self.headers,
            data=json.dumps({
                "servico": "Troca de óleo",
                "valor_total": 150
            })
        )
        self.assertEqual(response.status_code, 201)

    def test_adicionar_peca(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.post(
            f'/api/os/{id_os}/pecas',
            headers=self.headers,
            data=json.dumps({
                "peca": "Filtro de óleo",
                "valor_total": 80
            })
        )
        self.assertEqual(response.status_code, 201)

    def test_fluxo_completo_os(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        self.client.post(
            f'/api/os/{id_os}/servicos',
            headers=self.headers,
            data=json.dumps({"servico": "Troca de óleo", "valor_total": 150})
        )
        self.client.post(
            f'/api/os/{id_os}/pecas',
            headers=self.headers,
            data=json.dumps({"peca": "Filtro de óleo", "valor_total": 80})
        )

        for status in ["Em diagnóstico", "Aguardando aprovação"]:
            self.client.put(f'/api/os/{id_os}/status', headers=self.headers,
                            data=json.dumps({"status": status}))

        r = self.client.post(f'/api/os/{id_os}/aprovacao', headers=self.headers,
                             data=json.dumps({"aprovado": True}))
        self.assertEqual(r.status_code, 200)

        for status in ["Em execução", "Finalizada", "Entregue"]:
            r = self.client.put(f'/api/os/{id_os}/status', headers=self.headers,
                                data=json.dumps({"status": status}))
            self.assertEqual(r.status_code, 200)

        data = self.client.get(f'/api/os/{id_os}').get_json()
        self.assertEqual(data["status"], "Entregue")
        self.assertEqual(data["total_orcamento"], 230.0)
        self.assertEqual(data["detalhes"]["servicos"][0]["servico"], "Troca de óleo")
        self.assertEqual(data["detalhes"]["pecas"][0]["peca"], "Filtro de óleo")

    def test_fluxo_com_solicitacao_alteracoes(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        for status in ["Em diagnóstico", "Aguardando aprovação"]:
            self.client.put(f'/api/os/{id_os}/status', headers=self.headers,
                            data=json.dumps({"status": status}))

        r = self.client.put(f'/api/os/{id_os}/status', headers=self.headers,
                            data=json.dumps({"status": "Solicitado alterações"}))
        self.assertEqual(r.status_code, 200)

        r = self.client.put(f'/api/os/{id_os}/status', headers=self.headers,
                            data=json.dumps({"status": "Em diagnóstico"}))
        self.assertEqual(r.status_code, 200)

        data = self.client.get(f'/api/os/{id_os}').get_json()
        self.assertEqual(data["status"], "Em diagnóstico")

    def test_login_senha_errada(self):
        response = self.client.post(
            '/api/login',
            content_type='application/json',
            data=json.dumps({"username": "admin", "senha": "errada"})
        )
        self.assertEqual(response.status_code, 401)

    def test_cpf_invalido(self):
        response = self.client.post(
            '/api/clientes',
            headers=self.headers,
            data=json.dumps({"documento": "00000000000", "nome": "Teste"})
        )
        self.assertEqual(response.status_code, 400)

    def test_placa_invalida(self):
        response = self.client.post(
            '/api/veiculos',
            headers=self.headers,
            data=json.dumps({"placa": "INVALIDA", "marca": "X", "modelo": "Y", "ano": 2020})
        )
        self.assertEqual(response.status_code, 400)

    def test_placa_com_zero_e_nove(self):
        letras = string.ascii_uppercase
        placa = (
            random.choice(letras) + random.choice(letras) + random.choice(letras) +
            "0" + random.choice(letras) + "9" + str(random.randint(0, 9))
        )
        response = self.client.post(
            '/api/veiculos',
            headers=self.headers,
            data=json.dumps({"placa": placa, "marca": "X", "modelo": "Y", "ano": 2020})
        )
        self.assertEqual(response.status_code, 201)

    def test_salto_de_status_rejeitado(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.put(
            f'/api/os/{id_os}/status',
            headers=self.headers,
            data=json.dumps({"status": "Em execução"})
        )
        self.assertEqual(response.status_code, 400)

    def test_rota_publica_sem_token(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.get(f'/api/os/{id_os}')
        self.assertEqual(response.status_code, 200)

    def test_criar_os_com_pecas_e_servicos(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()

        response = self.client.post(
            '/api/os',
            headers=self.headers,
            data=json.dumps({
                "id_cliente": id_cliente,
                "id_veiculo": id_veiculo,
                "pecas": [{"peca": "Filtro", "valor_total": 50.0}],
                "servicos": [{"servico": "Revisão", "valor_total": 100.0}]
            })
        )
        self.assertEqual(response.status_code, 201)
        id_os = response.get_json()['id_os']

        orcamento = self.client.get(f'/api/os/{id_os}').get_json()
        self.assertEqual(orcamento['total_orcamento'], 150.0)
        self.assertEqual(len(orcamento['detalhes']['pecas']), 1)
        self.assertEqual(len(orcamento['detalhes']['servicos']), 1)

    def test_aprovacao_orcamento(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        for status in ["Em diagnóstico", "Aguardando aprovação"]:
            self.client.put(f'/api/os/{id_os}/status', headers=self.headers,
                            data=json.dumps({"status": status}))

        response = self.client.post(
            f'/api/os/{id_os}/aprovacao',
            headers=self.headers,
            data=json.dumps({"aprovado": True})
        )
        self.assertEqual(response.status_code, 200)

        os_data = self.client.get(f'/api/os/{id_os}').get_json()
        self.assertEqual(os_data['status'], "Aprovado")

    def test_recusa_orcamento(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        for status in ["Em diagnóstico", "Aguardando aprovação"]:
            self.client.put(f'/api/os/{id_os}/status', headers=self.headers,
                            data=json.dumps({"status": status}))

        response = self.client.post(
            f'/api/os/{id_os}/aprovacao',
            headers=self.headers,
            data=json.dumps({"aprovado": False})
        )
        self.assertEqual(response.status_code, 200)

        os_data = self.client.get(f'/api/os/{id_os}').get_json()
        self.assertEqual(os_data['status'], "Recusada")

    def test_webhook_atualiza_status(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.post(
            '/api/os/webhook/status',
            content_type='application/json',
            headers={'X-Webhook-Token': 'webhook-secret'},
            data=json.dumps({"id_os": id_os, "status": "Em diagnóstico"})
        )
        self.assertEqual(response.status_code, 200)

        os_data = self.client.get(f'/api/os/{id_os}').get_json()
        self.assertEqual(os_data['status'], "Em diagnóstico")

    def test_webhook_token_invalido(self):
        response = self.client.post(
            '/api/os/webhook/status',
            content_type='application/json',
            headers={'X-Webhook-Token': 'token-errado'},
            data=json.dumps({"id_os": 1, "status": "Em diagnóstico"})
        )
        self.assertEqual(response.status_code, 401)

    def test_listar_os_ordenada(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.get('/api/os', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        ordens = response.get_json()
        ids = [o['id_os'] for o in ordens]
        self.assertIn(id_os, ids)

    def test_get_os_status_publico(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.get(f'/api/os/{id_os}/status')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['id_os'], id_os)
        self.assertEqual(data['status'], "Recebida")

    def test_rota_protegida_sem_token(self):
        response = self.client.get('/api/clientes')
        self.assertEqual(response.status_code, 401)

    def test_listar_clientes(self):
        self.criar_cliente()
        response = self.client.get('/api/clientes', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), list)

    def test_buscar_cliente_por_id(self):
        _, id_cliente = self.criar_cliente()
        response = self.client.get(f'/api/clientes/{id_cliente}', headers=self.headers)
        self.assertEqual(response.status_code, 200)

    def test_atualizar_cliente(self):
        _, id_cliente = self.criar_cliente()
        response = self.client.put(
            f'/api/clientes/{id_cliente}',
            headers=self.headers,
            data=json.dumps({"nome": "Novo Nome", "documento": gerar_cpf()})
        )
        self.assertEqual(response.status_code, 200)

    def test_deletar_cliente(self):
        _, id_cliente = self.criar_cliente()
        response = self.client.delete(f'/api/clientes/{id_cliente}', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/api/clientes/{id_cliente}', headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_listar_veiculos(self):
        self.criar_veiculo()
        response = self.client.get('/api/veiculos', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), list)

    def test_buscar_veiculo_por_id(self):
        _, id_veiculo = self.criar_veiculo()
        response = self.client.get(f'/api/veiculos/{id_veiculo}', headers=self.headers)
        self.assertEqual(response.status_code, 200)

    def test_atualizar_veiculo(self):
        _, id_veiculo = self.criar_veiculo()
        response = self.client.put(
            f'/api/veiculos/{id_veiculo}',
            headers=self.headers,
            data=json.dumps({"placa": gerar_placa(), "marca": "Fiat", "modelo": "Palio", "ano": 2015})
        )
        self.assertEqual(response.status_code, 200)

    def test_deletar_veiculo(self):
        _, id_veiculo = self.criar_veiculo()
        response = self.client.delete(f'/api/veiculos/{id_veiculo}', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/api/veiculos/{id_veiculo}', headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_crud_peca(self):
        response = self.client.post(
            '/api/pecas',
            headers=self.headers,
            data=json.dumps({"nome": "Pastilha de freio", "valor_unitario": 45.0, "estoque": 5})
        )
        self.assertEqual(response.status_code, 201)
        id_peca = response.get_json()['id_peca']

        response = self.client.get('/api/pecas', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/api/pecas/{id_peca}', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        response = self.client.put(
            f'/api/pecas/{id_peca}',
            headers=self.headers,
            data=json.dumps({"nome": "Pastilha de freio dianteira", "valor_unitario": 50.0, "estoque": 3})
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.delete(f'/api/pecas/{id_peca}', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/api/pecas/{id_peca}', headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_crud_servico(self):
        response = self.client.post(
            '/api/servicos',
            headers=self.headers,
            data=json.dumps({"nome": "Alinhamento", "valor": 80.0})
        )
        self.assertEqual(response.status_code, 201)
        id_servico = response.get_json()['id_servico']

        response = self.client.get('/api/servicos', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/api/servicos/{id_servico}', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        response = self.client.put(
            f'/api/servicos/{id_servico}',
            headers=self.headers,
            data=json.dumps({"nome": "Alinhamento e balanceamento", "valor": 100.0})
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.delete(f'/api/servicos/{id_servico}', headers=self.headers)
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/api/servicos/{id_servico}', headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_aprovacao_fora_do_status_esperado(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)

        response = self.client.post(
            f'/api/os/{id_os}/aprovacao',
            headers=self.headers,
            data=json.dumps({"aprovado": True})
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_campos_faltando(self):
        response = self.client.post(
            '/api/os/webhook/status',
            content_type='application/json',
            headers={'X-Webhook-Token': 'webhook-secret'},
            data=json.dumps({"id_os": 1})
        )
        self.assertEqual(response.status_code, 400)

    def test_tempo_medio_execucao(self):
        response = self.client.get('/api/os/tempo-medio', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('media_dias', response.get_json())
        self.assertIn('por_status', response.get_json())

    def test_token_admin_tem_papel_admin(self):
        claims = jwt.decode(self.token, self.app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
        self.assertEqual(claims['role'], 'admin')

    def test_cliente_nao_acessa_rota_administrativa(self):
        cpf, id_cliente = self.criar_cliente()
        response = self.client.get('/api/clientes', headers=self.headers_cliente(id_cliente, cpf))
        self.assertEqual(response.status_code, 403)

    def test_cliente_abre_propria_os(self):
        cpf, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()

        response = self.client.post(
            '/api/os',
            headers=self.headers_cliente(id_cliente, cpf),
            data=json.dumps({"id_veiculo": id_veiculo})
        )
        self.assertEqual(response.status_code, 201)

        os_data = self.client.get(f"/api/os/{response.get_json()['id_os']}").get_json()
        self.assertEqual(os_data['id_cliente'], id_cliente)

    def test_cliente_lista_apenas_as_proprias_os(self):
        cpf, id_cliente = self.criar_cliente()
        _, outro_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        minha_os = self.criar_os(id_cliente, id_veiculo)
        self.criar_os(outro_cliente, id_veiculo)

        ordens = self.client.get('/api/os', headers=self.headers_cliente(id_cliente, cpf)).get_json()
        self.assertEqual({o['id_cliente'] for o in ordens}, {id_cliente})
        self.assertIn(minha_os, [o['id_os'] for o in ordens])

    def test_cliente_aprova_propria_os(self):
        cpf, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)
        self.avancar_status(id_os, "Em diagnóstico", "Aguardando aprovação")

        response = self.client.post(
            f'/api/os/{id_os}/aprovacao',
            headers=self.headers_cliente(id_cliente, cpf),
            data=json.dumps({"aprovado": True})
        )
        self.assertEqual(response.status_code, 200)

    def test_cliente_nao_aprova_os_de_outro_cliente(self):
        cpf, id_cliente = self.criar_cliente()
        _, dono = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(dono, id_veiculo)
        self.avancar_status(id_os, "Em diagnóstico", "Aguardando aprovação")

        response = self.client.post(
            f'/api/os/{id_os}/aprovacao',
            headers=self.headers_cliente(id_cliente, cpf),
            data=json.dumps({"aprovado": True})
        )
        self.assertEqual(response.status_code, 403)

    def test_historico_e_tempo_medio_por_status(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        id_os = self.criar_os(id_cliente, id_veiculo)
        self.avancar_status(id_os, "Em diagnóstico", "Aguardando aprovação")

        historico = self.client.get(f'/api/os/{id_os}/historico', headers=self.headers).get_json()
        self.assertEqual([h['status'] for h in historico], ["Recebida", "Em diagnóstico", "Aguardando aprovação"])

        tempos = self.client.get('/api/os/tempo-medio', headers=self.headers).get_json()
        self.assertIn("Recebida", tempos['por_status'])
        self.assertIn("Em diagnóstico", tempos['por_status'])

    def test_documento_duplicado(self):
        cpf, _ = self.criar_cliente()
        response = self.client.post(
            '/api/clientes',
            headers=self.headers,
            data=json.dumps({"documento": cpf, "nome": "Outro Nome"})
        )
        self.assertEqual(response.status_code, 400)

    def test_placa_duplicada(self):
        placa, _ = self.criar_veiculo()
        response = self.client.post(
            '/api/veiculos',
            headers=self.headers,
            data=json.dumps({"placa": placa, "marca": "Fiat", "modelo": "Uno", "ano": 2010})
        )
        self.assertEqual(response.status_code, 400)

    def test_os_com_cliente_inexistente(self):
        _, id_veiculo = self.criar_veiculo()
        response = self.client.post(
            '/api/os',
            headers=self.headers,
            data=json.dumps({"id_cliente": 999999999, "id_veiculo": id_veiculo})
        )
        self.assertEqual(response.status_code, 400)

    def test_adicionar_peca_em_os_inexistente(self):
        response = self.client.post(
            '/api/os/999999999/pecas',
            headers=self.headers,
            data=json.dumps({"peca": "Filtro", "valor_total": 10})
        )
        self.assertEqual(response.status_code, 400)

    def test_deletar_cliente_com_os_vinculada(self):
        _, id_cliente = self.criar_cliente()
        _, id_veiculo = self.criar_veiculo()
        self.criar_os(id_cliente, id_veiculo)

        response = self.client.delete(f'/api/clientes/{id_cliente}', headers=self.headers)
        self.assertEqual(response.status_code, 409)

    def test_inativar_cliente(self):
        cpf, id_cliente = self.criar_cliente()
        response = self.client.put(
            f'/api/clientes/{id_cliente}',
            headers=self.headers,
            data=json.dumps({"nome": "Gabriel Vieira", "documento": cpf, "status": "inativo"})
        )
        self.assertEqual(response.status_code, 200)

        cliente = self.client.get(f'/api/clientes/{id_cliente}', headers=self.headers).get_json()
        self.assertEqual(cliente['status'], 'inativo')

    def test_status_cliente_invalido(self):
        cpf, id_cliente = self.criar_cliente()
        response = self.client.put(
            f'/api/clientes/{id_cliente}',
            headers=self.headers,
            data=json.dumps({"nome": "Gabriel Vieira", "documento": cpf, "status": "bloqueado"})
        )
        self.assertEqual(response.status_code, 400)

    def test_health_e_ready(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        self.assertEqual(self.client.get('/api/ready').status_code, 200)

    def test_correlation_id_propagado(self):
        response = self.client.get('/api/health', headers={'X-Correlation-ID': 'teste-correlacao'})
        self.assertEqual(response.headers['X-Correlation-ID'], 'teste-correlacao')

    def test_correlation_id_gerado(self):
        response = self.client.get('/api/health')
        self.assertTrue(response.headers.get('X-Correlation-ID'))


if __name__ == '__main__':
    unittest.main()
