from __future__ import annotations

from app.services.first_party_identity_registry import (
    FirstPartyIdentityRegistry,
)


def assert_true(
    value,
    label,
):
    if not value:
        raise RuntimeError(
            f"Expected TRUE: {label}"
        )


def assert_false(
    value,
    label,
):
    if value:
        raise RuntimeError(
            f"Expected FALSE: {label}"
        )


def main():
    registry = (
        FirstPartyIdentityRegistry
    )

    print()
    print("=" * 120)
    print(
        "FIRST-PARTY IDENTITY REGISTRY 1.0"
    )
    print("=" * 120)

    # ========================================================
    # EMAIL
    # ========================================================

    own_emails = (
        "kontakt@podnoszenieposadzek.pl",
        "podnoszenieposadzek@gmail.com",
        "domlap94@gmail.com",
        "pawcioou@gmail.com",
        "inna-skrzynka@podnoszenieposadzek.pl",
    )

    external_emails = (
        "l-tynk@wp.pl",
        "monika.mikolajczak@projektbudowa.pl",
        "m.maciejewska@kancelarialmk.pl",
        "j.barzynski@tbinvest.pl",
        "jaroslaw.burzykowski@powiatlowicki.pl",
    )

    for value in own_emails:
        result = (
            registry.is_first_party_email(
                value
            )
        )

        print(
            "OWN EMAIL",
            repr(value),
            "=>",
            result,
        )

        assert_true(
            result,
            value,
        )

    for value in external_emails:
        result = (
            registry.is_first_party_email(
                value
            )
        )

        print(
            "EXTERNAL EMAIL",
            repr(value),
            "=>",
            result,
        )

        assert_false(
            result,
            value,
        )

    # ========================================================
    # TAX IDS
    # ========================================================

    own_tax_ids = (
        "8211139503",
        "821-113-95-03",
        "8212697553",
        "821-269-75-53",
    )

    external_tax_ids = (
        "6912229250",
        "5140120304",
        "8341882519",
        "5841352935",
        "5210124745",
        "8212663873",
    )

    for value in own_tax_ids:
        result = (
            registry.is_first_party_tax_id(
                value
            )
        )

        print(
            "OWN TAX",
            repr(value),
            "=>",
            result,
        )

        assert_true(
            result,
            value,
        )

    for value in external_tax_ids:
        result = (
            registry.is_first_party_tax_id(
                value
            )
        )

        print(
            "EXTERNAL TAX",
            repr(value),
            "=>",
            result,
        )

        assert_false(
            result,
            value,
        )

    # ========================================================
    # PEOPLE
    # ========================================================

    own_people = (
        "Dominik Łapiński",
        "Wojciech Łapiński",
        "Dominik Lapinski",
        "WOJCIECH ŁAPIŃSKI",
    )

    external_people = (
        "Mariusz Lipski",
        "Monika Mikołajczak",
        "Marta Maciejewska",
        "Jacek Barzyński",
        "Karol Walczak",
    )

    for value in own_people:
        result = (
            registry.is_first_party_person(
                value
            )
        )

        print(
            "OWN PERSON",
            repr(value),
            "=>",
            result,
        )

        assert_true(
            result,
            value,
        )

    for value in external_people:
        result = (
            registry.is_first_party_person(
                value
            )
        )

        print(
            "EXTERNAL PERSON",
            repr(value),
            "=>",
            result,
        )

        assert_false(
            result,
            value,
        )

    # ========================================================
    # ENTITIES
    # ========================================================

    own_entities = (
        "NEXT Stabil Sp. z o.o.",
        "NEXT - Podnoszenie Posadzek",
        "Podnoszenie Posadzek",
    )

    external_entities = (
        "Projekt Budowa Sp. z o.o.",
        "Polski Komfort Sp. z o.o.",
        "Trasko Invest",
        "BOWIM S.A.",
        "Przedsiębiorstwo Budowlane TB.INVEST Tomasz Brzeziński",
        "Starostwo Powiatowe w Łowiczu",
    )

    for value in own_entities:
        result = (
            registry.is_first_party_entity(
                value
            )
        )

        print(
            "OWN ENTITY",
            repr(value),
            "=>",
            result,
        )

        assert_true(
            result,
            value,
        )

    for value in external_entities:
        result = (
            registry.is_first_party_entity(
                value
            )
        )

        print(
            "EXTERNAL ENTITY",
            repr(value),
            "=>",
            result,
        )

        assert_false(
            result,
            value,
        )

    print()
    print("=" * 120)
    print("VALIDATION")
    print("=" * 120)

    print(
        "first-party email recognition: OK"
    )

    print(
        "external email isolation: OK"
    )

    print(
        "first-party historical tax IDs: OK"
    )

    print(
        "external tax IDs preserved: OK"
    )

    print(
        "first-party person recognition: OK"
    )

    print(
        "external person isolation: OK"
    )

    print(
        "first-party entity recognition: OK"
    )

    print(
        "external entity isolation: OK"
    )

    print()
    print(
        "FIRST-PARTY IDENTITY REGISTRY 1.0: OK"
    )


if __name__ == "__main__":
    main()
