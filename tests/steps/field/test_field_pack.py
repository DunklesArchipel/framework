from frictionless import Resource, Pipeline, steps


# General


def test_step_field_pack():
    source = Resource("data/transform.csv")
    pipeline = Pipeline(
        steps=[
            steps.field_pack(name="details", from_names=["name", "population"]),
        ],
    )
    target = source.transform(pipeline)
    assert target.schema.to_descriptor() == {
        "fields": [
            {"name": "id", "type": "integer"},
            {"name": "details", "type": "array"},
        ]
    }
    assert target.read_rows()[0] == {
        "id": 1,
        "details": ["germany", "83"],
    }


def test_step_field_pack_header_preserve():
    source = Resource("data/transform.csv")
    pipeline = Pipeline(
        steps=[
            steps.field_pack(
                name="details", from_names=["name", "population"], preserve=True
            )
        ],
    )
    target = source.transform(pipeline)
    assert target.schema.to_descriptor() == {
        "fields": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "string"},
            {"name": "population", "type": "integer"},
            {"name": "details", "type": "array"},
        ]
    }
    assert target.read_rows()[0] == {
        "id": 1,
        "name": "germany",
        "population": 83,
        "details": ["germany", "83"],
    }


def test_step_field_pack_object():
    source = Resource("data/transform.csv")
    pipeline = Pipeline(
        steps=[
            steps.field_pack(
                name="details",
                from_names=["name", "population"],
                as_object=True,
                preserve=True,
            )
        ],
    )
    target = source.transform(pipeline)
    assert target.schema.to_descriptor() == {
        "fields": [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "string"},
            {"name": "population", "type": "integer"},
            {"name": "details", "type": "object"},
        ]
    }
    assert target.read_rows()[0] == {
        "id": 1,
        "name": "germany",
        "population": 83,
        "details": {"name": "germany", "population": "83"},
    }
