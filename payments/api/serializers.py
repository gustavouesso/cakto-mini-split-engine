from decimal import Decimal

from rest_framework import serializers


class SplitInputSerializer(serializers.Serializer):
    recipient_id = serializers.CharField(max_length=100)
    role = serializers.CharField(max_length=50)
    percent = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_percent(self, value: Decimal) -> Decimal:
        if value <= Decimal("0") or value > Decimal("100"):
            raise serializers.ValidationError("percent must be greater than 0 and less than or equal to 100")
        return value


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    payment_method = serializers.ChoiceField(choices=["pix", "card"])
    installments = serializers.IntegerField(required=False, allow_null=True)
    splits = SplitInputSerializer(many=True)

    def validate_amount(self, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise serializers.ValidationError("amount must be greater than 0")
        return value

    def validate_currency(self, value: str) -> str:
        if value != "BRL":
            raise serializers.ValidationError("currency must be BRL")
        return value

    def validate_splits(self, value: list[dict]) -> list[dict]:
        if not value:
            raise serializers.ValidationError("splits must not be empty")

        if len(value) < 1 or len(value) > 5:
            raise serializers.ValidationError("splits must contain between 1 and 5 recipients")

        recipient_ids = [item["recipient_id"] for item in value]
        if len(recipient_ids) != len(set(recipient_ids)):
            raise serializers.ValidationError("recipient_id must be unique within splits")

        total_percent = sum(Decimal(str(item["percent"])) for item in value)
        if total_percent != Decimal("100"):
            raise serializers.ValidationError("sum of split percents must be exactly 100")

        return value

    def validate(self, attrs: dict) -> dict:
        payment_method = attrs.get("payment_method")
        installments = attrs.get("installments")

        if payment_method == "pix":
            if installments not in (None, 1):
                raise serializers.ValidationError(
                    {"installments": "pix does not support installments"}
                )
            attrs["installments"] = None

        if payment_method == "card":
            if installments is None:
                raise serializers.ValidationError(
                    {"installments": "installments is required for card payments"}
                )

            if installments < 1 or installments > 12:
                raise serializers.ValidationError(
                    {"installments": "card installments must be between 1 and 12"}
                )

        return attrs