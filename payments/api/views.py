import hashlib
import json

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.api.serializers import PaymentCreateSerializer
from payments.models import LedgerEntry, OutboxEvent, Payment
from payments.services.split_calculator import SplitCalculator


class PaymentCreateView(APIView):
    @staticmethod
    def build_payload_hash(payload: dict) -> str:
        normalized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized_payload.encode("utf-8")).hexdigest()

    @staticmethod
    def build_response(payment: Payment) -> dict:
        ledger_entries = payment.ledger_entries.all().order_by("id")
        outbox_event = payment.outbox_events.order_by("id").first()

        return {
            "payment_id": payment.id,
            "status": payment.status,
            "gross_amount": payment.gross_amount,
            "platform_fee_amount": payment.platform_fee_amount,
            "net_amount": payment.net_amount,
            "receivables": [
                {
                    "recipient_id": entry.recipient_id,
                    "role": entry.role,
                    "amount": entry.amount,
                }
                for entry in ledger_entries
            ],
            "outbox_event": {
                "type": outbox_event.type,
                "status": outbox_event.status,
            } if outbox_event else None,
        }

    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            return Response(
                {"detail": "Idempotency-Key header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        payload_hash = self.build_payload_hash(validated_data)

        existing_payment = Payment.objects.filter(idempotency_key=idempotency_key).first()

        if existing_payment:
            if existing_payment.payload_hash != payload_hash:
                return Response(
                    {"detail": "Idempotency-Key already used with a different payload"},
                    status=status.HTTP_409_CONFLICT,
                )

            return Response(
                self.build_response(existing_payment),
                status=status.HTTP_200_OK,
            )

        calculation = SplitCalculator.calculate(
            amount=validated_data["amount"],
            payment_method=validated_data["payment_method"],
            installments=validated_data.get("installments"),
            splits=validated_data["splits"],
        )

        with transaction.atomic():
            payment = Payment.objects.create(
                status=Payment.PAYMENT_STATUS_CAPTURED,
                gross_amount=calculation["gross_amount"],
                platform_fee_amount=calculation["platform_fee_amount"],
                net_amount=calculation["net_amount"],
                currency=validated_data["currency"],
                payment_method=validated_data["payment_method"],
                installments=validated_data.get("installments"),
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
            )

            ledger_entries = [
                LedgerEntry(
                    payment=payment,
                    recipient_id=receivable["recipient_id"],
                    role=receivable["role"],
                    amount=receivable["amount"],
                )
                for receivable in calculation["receivables"]
            ]
            LedgerEntry.objects.bulk_create(ledger_entries)

            outbox_payload = {
                "payment_id": payment.id,
                "status": payment.status,
                "gross_amount": str(payment.gross_amount),
                "platform_fee_amount": str(payment.platform_fee_amount),
                "net_amount": str(payment.net_amount),
                "currency": payment.currency,
                "payment_method": payment.payment_method,
                "installments": payment.installments,
                "receivables": [
                    {
                        "recipient_id": receivable["recipient_id"],
                        "role": receivable["role"],
                        "amount": str(receivable["amount"]),
                    }
                    for receivable in calculation["receivables"]
                ],
            }

            OutboxEvent.objects.create(
                payment=payment,
                type=OutboxEvent.TYPE_PAYMENT_CAPTURED,
                payload=outbox_payload,
                status=OutboxEvent.STATUS_PENDING,
            )

        payment.refresh_from_db()

        return Response(
            self.build_response(payment),
            status=status.HTTP_201_CREATED,
        )