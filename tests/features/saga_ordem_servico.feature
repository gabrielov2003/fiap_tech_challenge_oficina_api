# language: pt
Funcionalidade: Saga da ordem de serviço
  A OS passa pelo OS Service, pelo Billing Service e pelo Execution Service.
  O OS Service orquestra a saga pelas filas e compensa as etapas quando algo falha.

  Contexto:
    Dado um cliente com um veículo cadastrado

  Cenário: OS aprovada, paga, executada e entregue
    Quando o cliente abre uma OS com uma troca de óleo de 150 reais
    Então o comando "GerarOrcamento" é publicado na fila "billing"
    Quando o Billing publica "OrcamentoGerado"
    E o Billing publica "OrcamentoAprovado"
    E o Billing publica "PagamentoAprovado"
    Então a OS fica com o status "Aprovado"
    E o comando "IniciarExecucao" é publicado na fila "execucao"
    Quando a Execução avisa o status "Em diagnóstico"
    E a Execução avisa o status "Em execução"
    E a Execução avisa o status "Finalizada"
    E o funcionário marca a OS como entregue
    Então a OS fica com o status "Entregue"

  Cenário: cliente recusa o orçamento
    Quando o cliente abre uma OS com uma troca de óleo de 150 reais
    E o Billing publica "OrcamentoGerado"
    E o Billing publica "OrcamentoRecusado"
    Então a OS fica com o status "Recusada"

  Cenário: pagamento recusado cancela a OS
    Quando o cliente abre uma OS com uma troca de óleo de 150 reais
    E o Billing publica "OrcamentoGerado"
    E o Billing publica "OrcamentoAprovado"
    E o Billing publica "PagamentoRecusado"
    Então a OS fica com o status "Cancelada"

  Cenário: falha na execução cancela a OS e estorna o pagamento
    Quando o cliente abre uma OS com uma troca de óleo de 150 reais
    E o Billing publica "OrcamentoGerado"
    E o Billing publica "OrcamentoAprovado"
    E o Billing publica "PagamentoAprovado"
    E a Execução avisa o status "Em diagnóstico"
    E a Execução avisa a falha "Peça indisponível"
    Então a OS fica com o status "Cancelada"
    E o comando "EstornarPagamento" é publicado na fila "billing"
    Quando o Billing publica "PagamentoEstornado"
    Então a OS fica com o status "Cancelada"
