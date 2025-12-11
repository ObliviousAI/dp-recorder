def test_example_data_fixture(example_data):
    flavors, votes = example_data

    assert "Chocolate" in flavors
    assert len(votes) == 100
    assert votes.count("Chocolate") == 40
