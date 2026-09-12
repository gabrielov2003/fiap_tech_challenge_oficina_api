from flask import Flask
from flasgger import Swagger
from flask_jwt_extended import JWTManager
from infrastructure import (Infrastructure, ClienteRepositorySQLite, VeiculoRepositorySQLite,
                             PecaRepositorySQLite, ServicoRepositorySQLite,
                             OrdemServicoRepositorySQLite, UsuarioRepositorySQLite)
from web import api
import os
import application


def create_app():
    app = Flask(__name__)
    app.config['SWAGGER'] = {
        'title': 'API Oficina',
        'uiversion': 3
    }
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fiap-soat-key')

    JWTManager(app)
    Swagger(app)

    Infrastructure.init_db()

    application.cliente_repo = ClienteRepositorySQLite()
    application.veiculo_repo = VeiculoRepositorySQLite()
    application.peca_repo = PecaRepositorySQLite()
    application.servico_repo = ServicoRepositorySQLite()
    application.os_repo = OrdemServicoRepositorySQLite()
    application.usuario_repo = UsuarioRepositorySQLite()

    app.register_blueprint(api, url_prefix='/api')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=os.getenv('FLASK_DEBUG', '0') == '1')