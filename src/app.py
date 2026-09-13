import os
from datetime import date, datetime

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flasgger import Swagger
from flask_jwt_extended import JWTManager

import application
from infrastructure import (Infrastructure, ClienteRepositoryPostgres, VeiculoRepositoryPostgres,
                            PecaRepositoryPostgres, ServicoRepositoryPostgres, OrdemServicoRepositoryPostgres,
                            UsuarioRepositoryPostgres, SaudeRepositoryPostgres, MetricasDatadog)
from observabilidade import configurar_logs, registrar_rastreamento
from web import api


class JSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


def create_app():
    configurar_logs()

    app = Flask(__name__)
    app.json = JSONProvider(app)
    app.config['SWAGGER'] = {
        'title': 'API Oficina',
        'uiversion': 3
    }
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fiap-soat-key')

    JWTManager(app)
    Swagger(app, template={
        'info': {
            'title': 'API Oficina',
            'version': '3.0',
            'description': (
                'Funcionários fazem login em POST /api/login. Clientes se autenticam com o CPF '
                'em POST /auth, rota do API Gateway atendida pela Lambda. '
                'Use o token no botão Authorize.'
            )
        },
        'securityDefinitions': {
            'Bearer': {
                'type': 'apiKey',
                'name': 'Authorization',
                'in': 'header',
                'description': 'Informe `Bearer <token>`'
            }
        },
        'security': [{'Bearer': []}]
    })

    Infrastructure.init_db()

    application.cliente_repo = ClienteRepositoryPostgres()
    application.veiculo_repo = VeiculoRepositoryPostgres()
    application.peca_repo = PecaRepositoryPostgres()
    application.servico_repo = ServicoRepositoryPostgres()
    application.os_repo = OrdemServicoRepositoryPostgres()
    application.usuario_repo = UsuarioRepositoryPostgres()
    application.saude_repo = SaudeRepositoryPostgres()
    application.metricas = MetricasDatadog()

    registrar_rastreamento(app)
    app.register_blueprint(api, url_prefix='/api')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host=os.getenv('FLASK_HOST', '127.0.0.1'), port=5000, debug=os.getenv('FLASK_DEBUG', '0') == '1')
