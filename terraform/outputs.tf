output "fila_eventos" {
  value = aws_sqs_queue.eventos.name
}

output "role_worker" {
  value = aws_iam_role.worker.arn
}
