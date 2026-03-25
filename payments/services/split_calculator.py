from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

class SplitCalculator:
    @staticmethod
    def quantize_amount(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_platform_fee(amount: Decimal, payment_method: str, installments: int | None) -> Decimal:
        if payment_method == "pix":
            return Decimal("0.00")

        if payment_method == "card":
            if installments == 1:
                fee_percent = Decimal("3.99")
            else:
                extra_installments = installments - 1
                fee_percent = Decimal("4.99") + (Decimal("2.00") * Decimal(extra_installments))

            fee_amount = amount * (fee_percent / Decimal("100"))
            return SplitCalculator.quantize_amount(fee_amount)

        raise ValueError("Unsupported payment method")

    @staticmethod
    def calculate_net_amount(amount: Decimal, platform_fee_amount: Decimal) -> Decimal:
        return SplitCalculator.quantize_amount(amount - platform_fee_amount)

    @staticmethod
    def distribute(net_amount: Decimal, splits: list[dict]) -> list[dict]:
        receivables = []
        allocated_total = Decimal("0.00")

        for split in splits:
            exact_amount = net_amount * (Decimal(str(split["percent"])) / Decimal("100"))
            rounded_down_amount = exact_amount.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            remainder_fraction = exact_amount - rounded_down_amount

            receivables.append(
                {
                    "recipient_id": split["recipient_id"],
                    "role": split["role"],
                    "percent": split["percent"],
                    "amount": rounded_down_amount,
                    "_remainder_fraction": remainder_fraction,
                }
            )
            allocated_total += rounded_down_amount

        remainder = net_amount - allocated_total
        cents_to_distribute = int((remainder / Decimal("0.01")).quantize(Decimal("1")))

        receivables.sort(
            key=lambda item: (
                -item["_remainder_fraction"],
                item["recipient_id"],
            )
        )

        for index in range(cents_to_distribute):
            receivables[index]["amount"] += Decimal("0.01")

        for item in receivables:
            item.pop("_remainder_fraction", None)

        return receivables

    @staticmethod
    def calculate(amount: Decimal, payment_method: str, installments: int | None, splits: list[dict]) -> dict:
        platform_fee_amount = SplitCalculator.calculate_platform_fee(
            amount=amount,
            payment_method=payment_method,
            installments=installments,
        )
        net_amount = SplitCalculator.calculate_net_amount(
            amount=amount,
            platform_fee_amount=platform_fee_amount,
        )
        receivables = SplitCalculator.distribute(
            net_amount=net_amount,
            splits=splits,
        )

        receivables_total = sum(item["amount"] for item in receivables)
        if receivables_total != net_amount:
            raise ValueError("Receivables total must match net amount")

        return {
            "gross_amount": SplitCalculator.quantize_amount(amount),
            "platform_fee_amount": platform_fee_amount,
            "net_amount": net_amount,
            "receivables": receivables,
        }