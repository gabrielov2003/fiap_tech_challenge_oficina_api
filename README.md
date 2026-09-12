# fiap_tech_challenge_oficina_api

Aplicação principal do sistema de gestão da oficina mecânica, responsável pelas regras de negócio (clientes, veículos, peças, serviços e ordens de serviço).

Executa em um cluster Kubernetes provisionado pelo repositório `fiap_tech_challenge_oficina_infra_k8s`, e se conecta ao banco de dados gerenciado provisionado pelo repositório `fiap_tech_challenge_oficina_infra_database`.

As rotas sensíveis desta API são protegidas por autenticação via CPF, validada pela function serverless do repositório `fiap_tech_challenge_oficina_auth_lambda`, atrás de um API Gateway.

Este README será atualizado com tecnologias, instruções de execução e deploy, diagrama de arquitetura e link do Swagger conforme o desenvolvimento avançar.
