# fiap_tech_challenge_oficina_api

Aplicação principal do sistema de gestão de uma oficina mecânica, responsável pelas regras de negócio (clientes, veículos, peças, serviços e ordens de serviço). Este é um dos 4 repositórios do Tech Challenge Fase 3:

| Repositório | Responsabilidade |
|---|---|
| `fiap_tech_challenge_oficina_api` | Este repositório. Aplicação principal, executando em Kubernetes |
| `fiap_tech_challenge_oficina_auth_lambda` | Function serverless de autenticação via CPF |
| `fiap_tech_challenge_oficina_infra_k8s` | Terraform do cluster Kubernetes |
| `fiap_tech_challenge_oficina_infra_database` | Terraform do banco de dados gerenciado |

## Tecnologias utilizadas

* Python 3.11+ / Flask, framework da API RESTful
* Flask-JWT-Extended, validação dos tokens JWT gerados na autenticação
* Werkzeug, hash seguro de senhas
* SQLite3 com Pandas, persistência atual (será migrada para o banco gerenciado do repositório `fiap_tech_challenge_oficina_infra_database`)
* Docker e Docker Compose, containerização e execução local
* Kubernetes, manifestos em `k8s/` para deploy no cluster
* GitHub Actions, pipeline de CI/CD com testes, build e deploy automático
* Flasgger (Swagger), documentação interativa da API
* Pytest, testes automatizados

## Arquitetura

O projeto segue Domain Driven Design com arquitetura hexagonal (ports and adapters):

* `src/domain.py`: entidades de negócio (`Cliente`, `Veiculo`, `OrdemServico`) e validações de CPF/CNPJ e placa
* `src/ports.py`: interfaces (ports) dos repositórios, contrato que a camada de aplicação enxerga
* `src/infrastructure.py`: implementação concreta dos repositórios sobre SQLite (adapters)
* `src/application.py`: casos de uso, orquestrando domínio e repositórios através das interfaces
* `src/web.py`: endpoints da API e documentação Swagger
* `src/app.py`: ponto de entrada, inicializa o Flask e injeta os repositórios concretos na aplicação

## Fluxo principal da Ordem de Serviço

A OS progride por um conjunto fixo de transições de status, definido em `TRANSICOES` (`src/domain.py`):

Recebida, Em diagnóstico, Aguardando aprovação, e a partir daí Aprovado, Recusada ou Solicitado alterações. Uma vez aprovada, segue para Em execução (ou Aguardando peças), Finalizada e Entregue. Qualquer transição fora dessa ordem é rejeitada pela regra de domínio.

## Como rodar localmente

Pré-requisitos: Git, Docker, Docker Compose, e Python 3.11+ caso queira rodar os testes sem Docker.

1. Clone o repositório.
2. Configure as variáveis de ambiente:
   ```bash
   cp .env.example .env
   ```
   | Variável | Descrição | Padrão |
   |---|---|---|
   | `FLASK_DEBUG` | Ativa o modo debug do Flask (`0` desligado) | `0` |
   | `DATABASE_PATH` | Caminho do arquivo SQLite | `instance/database.db` |
   | `JWT_SECRET_KEY` | Chave secreta para assinar os tokens JWT, troque em produção | |
   | `WEBHOOK_TOKEN` | Token de autenticação do endpoint de webhook, troque em produção | |
3. Suba o ambiente:
   ```bash
   docker-compose up --build
   ```
4. A API fica disponível em `http://localhost:5000`.
5. Faça login com **POST** em `http://localhost:5000/api/login`, body `{"username": "admin", "senha": "admin123"}`, e use o token retornado no header `Authorization: Bearer <token>` nas demais requisições.

## Swagger

Com o container rodando, a documentação interativa fica em `http://localhost:5000/apidocs/`.

## Testes automatizados

```bash
python -m unittest tests/unit_tests.py
```

Os testes cobrem autenticação, CRUD de clientes, veículos, peças e serviços, o fluxo completo da OS (incluindo aprovação, recusa e solicitação de alterações), o webhook de atualização de status, e cenários de erro (dados inválidos, transições de status fora de ordem, acesso sem token).

## Docker

O `Dockerfile` usa multi stage build e roda com usuário não root (`appuser`).

## Kubernetes

Os manifestos de deploy da aplicação ficam em `k8s/` (o provisionamento do cluster em si fica no repositório `fiap_tech_challenge_oficina_infra_k8s`):

| Arquivo | Recurso | Descrição |
|---|---|---|
| `configmap.yaml` | ConfigMap | Variáveis não sensíveis |
| `secret.yaml` | Secret | Variáveis sensíveis, injetadas via `envsubst` no CI/CD |
| `pvc.yaml` | PersistentVolumeClaim | Volume para persistência do banco |
| `deployment.yaml` | Deployment | Pod da API com limites de CPU/memória |
| `service.yaml` | Service (LoadBalancer) | Expõe a API |
| `hpa.yaml` | HorizontalPodAutoscaler | Escala de 1 a 5 pods por CPU/memória |

## CI/CD

O pipeline em `.github/workflows/ci-cd.yml` executa a cada push em `main`:

| Job | O que faz |
|---|---|
| `test` | Instala dependências e roda os testes |
| `build` | Build e push da imagem para o GHCR |
| `deploy` | Injeta secrets, aplica os manifestos k8s e atualiza a imagem do Deployment |

Secrets necessários no GitHub (Settings, Secrets and variables, Actions):

| Secret | Descrição |
|---|---|
| `KUBECONFIG_B64` | Conteúdo do kubeconfig do cluster, em base64 |
| `JWT_SECRET_KEY` | Chave secreta para assinar os tokens JWT |
| `WEBHOOK_TOKEN` | Token de autenticação do endpoint de webhook |

## Documentação

A documentação arquitetural completa (diagramas de componentes e de sequência, RFCs, ADRs, e a justificativa do banco de dados) será adicionada aqui conforme a Fase 3 avança.

---
Este projeto faz parte do Tech Challenge da Pós Graduação em Arquitetura de Software da FIAP.
