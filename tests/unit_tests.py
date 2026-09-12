import unittest
import json
import random
import string
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from app import create_app


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
        app = create_app()
        app.config['TESTING'] = True
        self.client = app.test_client()

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


    def test_login(self):
        response = self.client.post(
            '/api/login',
            content_type='application/json',
            data=json.dumps({"username": "admin", "senha": "admin123"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access_token', response.get_json())

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


if __name__ == '__main__':
    unittest.main()