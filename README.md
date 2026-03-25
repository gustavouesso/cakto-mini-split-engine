# Cakto Mini Split Engine

## 📌 Visão Geral

Este projeto implementa uma API de pagamentos simplificada com foco em:

* Cálculo de taxas
* Split de recebíveis
* Precisão financeira em centavos
* Idempotência
* Ledger (auditabilidade)
* Outbox pattern (event-driven)

A solução foi desenvolvida com foco em clareza, corretude financeira e comportamento esperado em ambientes de produção.

---

## 🚀 Stack

* Python 3
* Django
* Django REST Framework

---

## ▶️ Como rodar o projeto

```bash
# criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# instalar dependências
pip install -r requirements.txt

# rodar migrations
python3 manage.py migrate

# rodar servidor
python3 manage.py runserver
```

---

## 📡 Endpoint principal

### POST `/api/v1/payments`

#### Headers

```
Idempotency-Key: <string>
```

#### Body (exemplo)

```json
{
  "amount": "297.00",
  "currency": "BRL",
  "payment_method": "card",
  "installments": 3,
  "splits": [
    { "recipient_id": "producer_1", "role": "producer", "percent": 70 },
    { "recipient_id": "affiliate_9", "role": "affiliate", "percent": 30 }
  ]
}
```

---

## 🧠 Decisões Técnicas

### 💰 Precisão financeira

* Todos os valores monetários utilizam `Decimal`
* Nenhum cálculo utiliza `float`
* Arredondamento realizado com `ROUND_HALF_UP` para valores finais

---

### 🧮 Regra de distribuição de centavos

A distribuição do split segue o algoritmo de **maior resto primeiro**:

1. Cada recebedor tem seu valor calculado
2. O valor é truncado para baixo (`ROUND_DOWN`)
3. O restante (centavos) é redistribuído para quem perdeu mais no arredondamento
4. Em caso de empate, o desempate é feito por `recipient_id`

Essa abordagem:

* garante que `sum(receivables) == net_amount`
* minimiza distorção causada por arredondamento
* evita viés por ordem de entrada

---

### 🔁 Idempotência

Implementação baseada em:

* `Idempotency-Key` (header obrigatório)
* Hash do payload normalizado

Regras:

* Mesmo key + mesmo payload → retorna mesma resposta (200)
* Mesmo key + payload diferente → retorna `409 Conflict`

Detalhe importante:

* O payload é normalizado (Decimal → string) antes do hash para garantir consistência e precisão

---

### 📒 Ledger

* Cada recebedor gera um `LedgerEntry`
* Permite rastreabilidade completa do pagamento
* Facilita reconciliação

---

### 📤 Outbox Pattern

* Cada pagamento gera um `OutboxEvent`
* Status inicial: `pending`
* Representa integração futura com mensageria/eventos

---

## 🧪 Testes

Foram implementados testes cobrindo cenários críticos:

* PIX com taxa zero
* Cartão 3x com split 70/30
* Caso de arredondamento com centavos residuais
* Idempotência (mesmo payload)
* Idempotência com conflito

Rodar testes:

```bash
python3 manage.py test
```

---

## 📊 Métricas que seriam adicionadas em produção

* Taxa de erro por endpoint
* Latência de processamento de pagamento
* Volume de pagamentos por método
* Divergência de centavos (alerta)
* Taxa de retries/idempotência

---

## 🔮 Se tivesse mais tempo

* Implementar fila para processamento assíncrono do outbox
* Retry automático de eventos
* Persistência com isolamento transacional mais robusto
* Endpoint de consulta de pagamento
* Logging estruturado
* Observabilidade (OpenTelemetry)

---

## 🤖 Uso de IA

Foi utilizada IA como apoio no desenvolvimento, principalmente para:

* Geração inicial dos modelos (Django ORM)
* Criação dos testes automatizados
* Revisão de lógica e edge cases

A lógica de negócio, decisões arquiteturais e validações foram definidas manualmente, com foco em comportamento de produção.

---

## 📂 Estrutura do projeto

```
payments/
  models.py
  api/
    serializers.py
    views.py
    urls.py
  services/
    split_calculator.py
  tests/
    test_payments.py
```

---

## ✅ Conclusão

A solução foi construída com foco em:

* Corretude financeira
* Determinismo
* Simplicidade com qualidade de produção
* Clareza de decisões técnicas

---
