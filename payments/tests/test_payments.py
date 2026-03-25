from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from payments.models import LedgerEntry, OutboxEvent, Payment


class PaymentCreateApiTests(APITestCase):
    @property
    def url(self):
        return reverse("payment-create")

    def test_pix_with_zero_fee_and_full_split(self):
        payload = {
            "amount": "100.00",
            "currency": "BRL",
            "payment_method": "pix",
            "splits": [
                {
                    "recipient_id": "producer_1",
                    "role": "producer",
                    "percent": "100.00",
                }
            ],
        }

        response = self.client.post(
            self.url,
            data=payload,
            format="json",
            headers={"Idempotency-Key": "pix-key-1"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.count(), 1)

        body = response.json()
        self.assertEqual(body["status"], "captured")
        self.assertEqual(Decimal(str(body["gross_amount"])), Decimal("100.00"))
        self.assertEqual(Decimal(str(body["platform_fee_amount"])), Decimal("0.00"))
        self.assertEqual(Decimal(str(body["net_amount"])), Decimal("100.00"))

        self.assertEqual(len(body["receivables"]), 1)
        self.assertEqual(body["receivables"][0]["recipient_id"], "producer_1")
        self.assertEqual(Decimal(str(body["receivables"][0]["amount"])), Decimal("100.00"))

        self.assertEqual(body["outbox_event"]["type"], "payment_captured")
        self.assertEqual(body["outbox_event"]["status"], "pending")

    def test_card_3x_split_70_30_should_match_net_amount(self):
        payload = {
            "amount": "297.00",
            "currency": "BRL",
            "payment_method": "card",
            "installments": 3,
            "splits": [
                {
                    "recipient_id": "producer_1",
                    "role": "producer",
                    "percent": "70.00",
                },
                {
                    "recipient_id": "affiliate_9",
                    "role": "affiliate",
                    "percent": "30.00",
                },
            ],
        }

        response = self.client.post(
            self.url,
            data=payload,
            format="json",
            headers={"Idempotency-Key": "card-key-1"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 2)
        self.assertEqual(OutboxEvent.objects.count(), 1)

        body = response.json()
        self.assertEqual(Decimal(str(body["gross_amount"])), Decimal("297.00"))
        self.assertEqual(Decimal(str(body["platform_fee_amount"])), Decimal("26.70"))
        self.assertEqual(Decimal(str(body["net_amount"])), Decimal("270.30"))

        receivables_total = sum(Decimal(str(item["amount"])) for item in body["receivables"])
        self.assertEqual(receivables_total, Decimal("270.30"))

        receivables_by_recipient = {item["recipient_id"]: Decimal(str(item["amount"])) for item in body["receivables"]}
        self.assertEqual(receivables_by_recipient["producer_1"], Decimal("189.21"))
        self.assertEqual(receivables_by_recipient["affiliate_9"], Decimal("81.09"))

    def test_rounding_case_should_distribute_remaining_cent_correctly(self):
        payload = {
            "amount": "100.00",
            "currency": "BRL",
            "payment_method": "pix",
            "splits": [
                {
                    "recipient_id": "recipient_b",
                    "role": "affiliate",
                    "percent": "33.33",
                },
                {
                    "recipient_id": "recipient_a",
                    "role": "producer",
                    "percent": "33.33",
                },
                {
                    "recipient_id": "recipient_c",
                    "role": "coproducer",
                    "percent": "33.34",
                },
            ],
        }

        response = self.client.post(
            self.url,
            data=payload,
            format="json",
            headers={"Idempotency-Key": "rounding-key-1"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        body = response.json()
        self.assertEqual(Decimal(str(body["net_amount"])), Decimal("100.00"))

        receivables = {item["recipient_id"]: Decimal(str(item["amount"])) for item in body["receivables"]}
        receivables_total = sum(receivables.values())

        self.assertEqual(receivables_total, Decimal("100.00"))
        self.assertEqual(receivables["recipient_c"], Decimal("33.34"))
        self.assertEqual(receivables["recipient_a"], Decimal("33.33"))
        self.assertEqual(receivables["recipient_b"], Decimal("33.33"))

    def test_same_idempotency_key_with_same_payload_should_not_duplicate_records(self):
        payload = {
            "amount": "150.00",
            "currency": "BRL",
            "payment_method": "pix",
            "splits": [
                {
                    "recipient_id": "producer_1",
                    "role": "producer",
                    "percent": "100.00",
                }
            ],
        }

        headers = {"Idempotency-Key": "idem-key-1"}

        first_response = self.client.post(
            self.url,
            data=payload,
            format="json",
            headers=headers,
        )
        second_response = self.client.post(
            self.url,
            data=payload,
            format="json",
            headers=headers,
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.count(), 1)

        first_body = first_response.json()
        second_body = second_response.json()

        self.assertEqual(first_body["payment_id"], second_body["payment_id"])
        self.assertEqual(first_body["net_amount"], second_body["net_amount"])
        self.assertEqual(first_body["platform_fee_amount"], second_body["platform_fee_amount"])

    def test_same_idempotency_key_with_different_payload_should_return_conflict(self):
        first_payload = {
            "amount": "150.00",
            "currency": "BRL",
            "payment_method": "pix",
            "splits": [
                {
                    "recipient_id": "producer_1",
                    "role": "producer",
                    "percent": "100.00",
                }
            ],
        }

        second_payload = {
            "amount": "200.00",
            "currency": "BRL",
            "payment_method": "pix",
            "splits": [
                {
                    "recipient_id": "producer_1",
                    "role": "producer",
                    "percent": "100.00",
                }
            ],
        }

        headers = {"Idempotency-Key": "idem-key-2"}

        first_response = self.client.post(
            self.url,
            data=first_payload,
            format="json",
            headers=headers,
        )
        second_response = self.client.post(
            self.url,
            data=second_payload,
            format="json",
            headers=headers,
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)

        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)
        self.assertEqual(OutboxEvent.objects.count(), 1)

        self.assertEqual(
            second_response.json()["detail"],
            "Idempotency-Key already used with a different payload",
        )