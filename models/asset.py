from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class AssetAnalysisRequest(BaseModel):
    asset_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    asset_price: Decimal = Field(
        ...,
        gt=0,
    )

    down_payment: Decimal = Field(
        ...,
        ge=0,
    )

    hp_period_months: int = Field(
        ...,
        gt=0,
    )

    hp_interest_rate: Decimal = Field(
        ...,
        ge=0,
    )

    lease_period_months: int = Field(
        ...,
        gt=0,
    )

    lease_monthly_payment: Decimal = Field(
        ...,
        gt=0,
    )

    hp_rate_type: str = Field(
        default="fixed",
        pattern="^(fixed|variable)$",
    )

    cash_discount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
    )


    @field_validator("asset_name")
    @classmethod
    def validate_asset_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Asset name cannot be empty.")

        return value

    @model_validator(mode="after")
    def validate_down_payment(self):
        if self.down_payment > self.asset_price:
            raise ValueError(
                "Down payment cannot exceed asset price."
            )

        if self.cash_discount > self.asset_price:
            raise ValueError(
                "Cash discount cannot exceed asset price."
            )

        return self