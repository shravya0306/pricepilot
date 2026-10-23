import pytest

from app.pricing import evaluate_discount, price_offers, summarize


@pytest.mark.parametrize(
    ("text", "base", "expected"),
    [
        ("₹2000 off", 10000, ("fixed", 2000, False)),
        ("10% off", 10000, ("percent", 1000, False)),
        ("Flat 15% off", 10000, ("percent", 1500, False)),
        ("Up to ₹1200 off", 10000, ("upto_fixed", 1200, True)),
        ("7.5% up to ₹7500", 20000, ("percent_capped", 1500, False)),
        ("7.5% up to ₹7500", 200000, ("percent_capped", 7500, False)),
        ("10% off up to ₹500", 10000, ("percent_capped", 500, False)),
        ("Flat ₹1,500 off", 8000, ("fixed", 1500, False)),
        ("Rs. 1,500 Instant Discount", 8000, ("fixed", 1500, False)),
        ("10% off on minimum purchase of ₹5000", 10000, ("percent", 1000, False)),
        ("₹2,000 off on orders above ₹10,000", 20000, ("fixed", 2000, False)),
        ("₹300 cashback", 10000, ("fixed", 300, False)),
    ],
)
def test_discount_rules(text, base, expected):
    assert evaluate_discount(text, base) == expected


@pytest.mark.parametrize(
    "text",
    [
        "₹500 off and 10% off",
        "Up to 10% off",
        "Great deal today",
        "₹0 off",
        "100% off",
        "₹10000 off",
    ],
)
def test_unclear_or_unrealistic_discounts_are_skipped(text):
    assert evaluate_discount(text, 10000) is None


def test_minimum_purchase_makes_offer_ineligible():
    groups, notes = price_offers(
        {"coupons": [{"code": "MIN", "discount": "10% off on minimum purchase of ₹5000"}]},
        3000,
    )
    assert groups.coupons == []
    assert any("minimum purchase" in note for note in notes)


def test_offer_groups_keep_guaranteed_conditional_and_cashback_separate():
    groups, notes = price_offers(
        {
            "bank_offers": [
                {"bank": "HDFC", "discount": "10% off", "eligibility": "HDFC credit card"},
                {"bank": "SBI", "discount": "₹500 off", "eligibility": "SBI cards"},
            ],
            "coupons": [{"code": "SAVE200", "discount": "₹200 off"}],
            "exchange_offers": [{"discount": "Up to ₹3000 off", "eligibility": "Exchange a phone"}],
            "cashback_offers": [
                {"provider": "Pay Balance", "discount": "₹300 cashback", "eligibility": "After delivery"}
            ],
        },
        10000,
    )
    summary = summarize(10000, groups)

    assert notes == []
    assert [offer.label for offer in groups.coupons] == ["SAVE200"]
    assert groups.coupons[0].timing == "guaranteed"
    assert [offer.label for offer in groups.bank_offers] == ["HDFC", "SBI"]
    assert all(offer.timing == "conditional" for offer in groups.bank_offers)
    assert groups.exchange_offers[0].maximum_estimate is True
    assert groups.cashback_offers[0].timing == "post_purchase"
    assert summary.checkout_price == 9800
    assert summary.guaranteed_discount == 200
    assert summary.best_conditional_label == "HDFC"
    assert summary.best_conditional_price == 9000
    assert summary.best_exchange_price == 7000
    assert summary.cashback_value == 300
    assert summary.estimated_net == 9500
    assert summary.stacked_checkout is None
    assert any("cannot be combined" in note for note in summary.incompatible_notes)
    assert any("Bank offers are alternatives" in note for note in summary.incompatible_notes)
    assert any("Exchange savings" in note for note in summary.incompatible_notes)
    assert any("Cashback is credited" in note for note in summary.incompatible_notes)


def test_stackable_offers_get_a_separate_combined_checkout():
    groups, _notes = price_offers(
        {
            "coupons": [{"code": "EXTRA", "discount": "extra ₹200 off", "stackable": True}],
            "bank_offers": [
                {"bank": "HDFC", "discount": "₹1000 off", "stackable": True, "eligibility": "HDFC card"}
            ],
        },
        10000,
    )
    summary = summarize(10000, groups)
    assert summary.checkout_price == 9800
    assert summary.stacked_checkout == 8800
    assert summary.stacked_label == "EXTRA + HDFC"


def test_bank_cashback_is_not_treated_as_an_instant_discount():
    groups, _notes = price_offers(
        {"bank_offers": [{"bank": "HDFC", "discount": "₹800 cashback", "eligibility": "HDFC card"}]},
        5000,
    )
    summary = summarize(5000, groups)
    assert groups.bank_offers == []
    assert groups.cashback_offers[0].timing == "post_purchase"
    assert summary.checkout_price == 5000
    assert summary.estimated_net == 4200
