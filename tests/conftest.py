import pytest


@pytest.fixture
def example_data():
    flavors = [
        "Vanilla",
        "Chocolate",
        "Strawberry",
        "Mint",
        "Cookie Dough",
        "Rocky Road",
    ]

    votes = (
        ["Chocolate"] * 40
        + ["Vanilla"] * 30
        + ["Cookie Dough"] * 15
        + ["Strawberry"] * 10
        + ["Rocky Road"] * 5
        + ["Mint"] * 0
    )

    return flavors, votes
