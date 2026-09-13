# fiap_tech_challenge_oficina_api

Aplicação principal do sistema de gestão de uma oficina mecânica, responsável pelas regras de negócio (clientes, veículos, peças, serviços e ordens de serviço). Este é um dos 4 repositórios do Tech Challenge Fase 3:

| Repositório | Responsabilidade |
|---|---|
| `fiap_tech_challenge_oficina_api` | Este repositório. Aplicação principal, executando em Kubernetes |
| `fiap_tech_challenge_oficina_auth_lambda` | Function serverless de autenticação via CPF e API Gateway |
| `fiap_tech_challenge_oficina_infra_k8s` | Terraform da rede, do cluster Kubernetes, do registro de imagens e do monitoramento |
| `fiap_tech_challenge_oficina_infra_database` | Terraform do banco de dados gerenciado |

## Tecnologias utilizadas

* Python 3.11 e Flask, API RESTful
* Gunicorn, servidor de aplicação em produção
* Flask-JWT-Extended, validação dos tokens JWT de funcionários e de clientes
* PostgreSQL gerenciado (AWS RDS), acessado com psycopg2 e pool de conexões
* Docker e Docker Compose
* Kubernetes (AWS EKS) com HorizontalPodAutoscaler
* Datadog: APM com ddtrace, métricas customizadas via DogStatsD, logs em JSON e healthcheck
* GitHub Actions, CI/CD com deploy automático por ambiente
* Flasgger (Swagger)
* Pytest e Bandit

## Arquitetura

O projeto segue Domain Driven Design com arquitetura hexagonal (ports and adapters):

* `src/domain.py`: entidades de negócio, validações de CPF/CNPJ e placa, status do cliente e as transições permitidas da OS (`TRANSICOES`)
* `src/ports.py`: interfaces que a aplicação enxerga: repositórios, verificação de saúde do banco e métricas
* `src/infrastructure.py`: adapters concretos, repositórios PostgreSQL e métricas Datadog
* `src/application.py`: casos de uso, orquestrando domínio, repositórios e métricas através das interfaces
* `src/web.py`: endpoints, controle de acesso por perfil e documentação Swagger
* `src/observabilidade.py`: logs estruturados em JSON e correlação de requisições
* `src/app.py`: ponto de entrada, injeta os adapters concretos na aplicação

## Integração com os outros repositórios

Os repositórios se comunicam pelo AWS SSM Parameter Store, sem nenhum segredo versionado:

| Parâmetro | Quem cria | Uso nesta API |
|---|---|---|
| `/oficina/eks/cluster_name` | infra_k8s | Pipeline configura o kubectl |
| `/oficina/db/host`, `port`, `name`, `username`, `password` | infra_database | Conexão com o RDS |
| `/oficina/<env>/jwt_secret` | infra_k8s | Validação dos tokens, o mesmo segredo que a Lambda usa para assinar |
| `/oficina/<env>/webhook_token` | infra_k8s | Autenticação do webhook |
| `/oficina/<env>/admin_password` | infra_k8s | Senha inicial do usuário admin |
| `/oficina/<env>/api_url` | pipeline desta API | Endereço do LoadBalancer, usado pelo API Gateway para rotear as requisições |

Fluxo de uma requisição de cliente: o cliente chama `POST /auth` no API Gateway com o CPF, a Lambda valida o CPF, confere se o cliente existe e está ativo e devolve um JWT. Com esse token o cliente chama as rotas da API pelo mesmo API Gateway, que repassa a requisição ao LoadBalancer da API incluindo o header `X-Correlation-ID`.

## Perfis de acesso

| Perfil | Como obtém o token | O que acessa |
|---|---|---|
| `admin` (funcionário) | `POST /api/login` com usuário e senha | Todas as rotas protegidas |
| `cliente` | `POST /auth` no API Gateway, com o CPF | Abrir OS para si, listar as próprias OS e aprovar ou recusar o orçamento das próprias OS |

Rotas públicas: `GET /api/os/{id}`, `GET /api/os/{id}/status`, `POST /api/os/webhook/status` (autenticada pelo token do webhook), `GET /api/health` e `GET /api/ready`.

## Fluxo da Ordem de Serviço

Recebida, Em diagnóstico, Aguardando aprovação, e então Aprovado, Recusada ou Solicitado alterações (que volta para Em diagnóstico). Aprovado segue para Em execução ou Aguardando peças, e depois Finalizada e Entregue. Qualquer transição fora dessa ordem é rejeitada, e cada mudança de status fica registrada na tabela `historico_status_os`, o que permite medir o tempo gasto em cada etapa.

## Banco de dados

Principais ajustes no modelo relacional em relação à fase anterior:

* Migração de SQLite para PostgreSQL gerenciado
* Chaves estrangeiras reais entre ordem de serviço, cliente, veículo e itens, com exclusão em cascata dos itens e do histórico da OS
* Chave primária nas tabelas de peças e serviços da OS
* Restrições de consistência: valores e estoque não negativos, documento e placa únicos, status do cliente limitado a `ativo` e `inativo`
* Índices em status, cliente e veículo da OS, e nas chaves das tabelas filhas
* Tabela `historico_status_os`, base do tempo médio por status
* Coluna `status` no cliente, consultada pela Lambda na autenticação
* Mudança de status atômica com controle de concorrência: a atualização só acontece se o status atual ainda for o esperado

As tabelas são criadas pela própria aplicação na inicialização, dentro de um lock no banco, então várias réplicas podem subir ao mesmo tempo sem conflito. Cada ambiente usa o próprio schema (`dev` ou `prod`) no mesmo RDS.

## Observabilidade

* Logs em JSON no stdout, com `correlation_id` (o header `X-Correlation-ID` recebido do API Gateway ou um id gerado), `dd.trace_id` para ligar o log ao trace no Datadog, e método, rota, status e duração de cada requisição
* APM com ddtrace, que mede a latência por endpoint
* Métricas customizadas enviadas ao agente do Datadog:

| Métrica | Descrição |
|---|---|
| `oficina.os.abertas` | Ordens de serviço abertas, base do volume diário |
| `oficina.os.tempo_status` | Tempo em segundos que a OS ficou em cada status, com a tag `status` |
| `oficina.os.status_alterado` | Mudanças de status |
| `oficina.os.falhas` | Falhas inesperadas no processamento de OS, com a tag `operacao` |
| `oficina.integracao.erros` | Erros no webhook, com as tags `integracao` e `motivo` |

* Healthcheck: `/api/health` (liveness) e `/api/ready` (readiness, verifica o banco), usados pelas probes do Kubernetes e pelo `http_check` do agente do Datadog

O dashboard e os alertas são criados pelo repositório `fiap_tech_challenge_oficina_infra_k8s`.

## Como rodar localmente

Pré-requisitos: Git, Docker e Docker Compose, e Python 3.11+ para rodar os testes fora do Docker.

1. Clone o repositório.
2. Configure as variáveis de ambiente:
   ```bash
   cp .env.example .env
   ```
   | Variável | Descrição | Padrão |
   |---|---|---|
   | `FLASK_DEBUG` | Ativa o modo debug do Flask (`0` desligado) | `0` |
   | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Conexão com o PostgreSQL | banco do Docker Compose |
   | `DB_SCHEMA` | Schema onde as tabelas são criadas | `public` |
   | `JWT_SECRET_KEY` | Chave de assinatura dos tokens JWT | |
   | `WEBHOOK_TOKEN` | Token de autenticação do webhook | |
   | `ADMIN_PASSWORD` | Senha do usuário admin criado na primeira inicialização | `admin123` |
   | `DD_API_KEY`, `DD_SITE` | Chave e site do Datadog, usados apenas pelo agente local | `datadoghq.com` |
3. Suba o banco e a API:
   ```bash
   docker compose up --build
   ```
4. A API fica em `http://localhost:5000` e o Swagger em `http://localhost:5000/apidocs/`.
5. Faça login com `POST /api/login`, body `{"username": "admin", "senha": "admin123"}`, e use o token no header `Authorization: Bearer <token>` (no Swagger, pelo botão Authorize).

### Monitoramento local com Datadog

O arquivo `docker-compose.datadog.yml` sobe o agente do Datadog junto com a API, com APM, coleta dos logs dos containers, métricas customizadas e o healthcheck. Preencha `DD_API_KEY` e `DD_SITE` no `.env` e rode:

```bash
docker compose -f docker-compose.yml -f docker-compose.datadog.yml up -d --build
```

Os dados chegam no Datadog com a tag `env:local`.

## Testes automatizados

Os testes rodam contra um PostgreSQL real. Com o banco do Docker Compose no ar:

```bash
docker compose up -d db
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/unit_tests.py -v
```

Cobrem CRUD de clientes, veículos, peças e serviços, o fluxo completo da OS (aprovação, recusa e solicitação de alterações), permissões por perfil (cliente só acessa as próprias OS e não acessa rotas administrativas), tokens no mesmo formato gerado pela Lambda, histórico e tempo médio por status, restrições do banco (documento e placa duplicados, cliente inexistente, exclusão bloqueada por vínculo), webhook, healthchecks e propagação do correlation id.

## Kubernetes

Os manifestos ficam em `k8s/` e são parametrizados por ambiente pelo pipeline, via `envsubst`:

| Arquivo | Recurso | Descrição |
|---|---|---|
| `namespace.yaml` | Namespace | Um namespace por ambiente (`dev` e `prod`) |
| `configmap.yaml` | ConfigMap | Conexão com o banco (sem a senha) e schema do ambiente |
| `secret.yaml` | Secret | Senha do banco, segredo JWT, token do webhook e senha do admin, lidos do SSM |
| `deployment.yaml` | Deployment | Pods da API com probes, limites de CPU e memória, tags do Datadog e healthcheck do agente |
| `service.yaml` | Service (LoadBalancer) | Expõe a API para o API Gateway |
| `hpa.yaml` | HorizontalPodAutoscaler | Escala de 1 a 5 pods por CPU (70%) ou memória (80%) |

## CI/CD e ambientes

| Branch | Ambiente | Namespace | Schema no banco |
|---|---|---|---|
| `dev` | dev | `dev` | `dev` |
| `main` | prod | `prod` | `prod` |

O pipeline em `.github/workflows/ci-cd.yml`:

| Job | Quando roda | O que faz |
|---|---|---|
| `test` | Pull requests para `main` ou `dev`, e pushes | Sobe um PostgreSQL de serviço, roda os testes e o Bandit |
| `build` | Push em `dev` ou `main` | Builda a imagem e envia para o ECR `oficina-api` |
| `deploy` | Depois do build | Lê os parâmetros do SSM, aplica os manifestos no namespace do ambiente, espera o rollout e publica a URL do LoadBalancer |

Secrets necessários (Settings, Secrets and variables, Actions): `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY`. Variável opcional: `AWS_REGION` (padrão `us-east-1`). Sem as credenciais, o pipeline roda os testes e ignora build e deploy.

Ordem do primeiro deploy: `infra_k8s`, `infra_database`, esta API, e por último a `auth_lambda`, que usa a URL publicada aqui para rotear as requisições.

## Documentação

A documentação arquitetural completa (diagramas de componentes e de sequência, RFCs, ADRs, diagrama ER e justificativa do banco de dados) será adicionada aqui.

---
Este projeto faz parte do Tech Challenge da Pós Graduação em Arquitetura de Software da FIAP.
