"""Dataset discovery and upload."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from astaverse.integrations import datasets


def test_bundled_hurricane_is_discoverable():
    found = datasets.get("hurricane")
    assert found is not None
    assert found.kind == "astaverse"
    assert found.n_rows == 94
    assert found.n_columns == 14
    assert any(field.get("name") == "masfem" for field in found.fields)


@pytest.fixture
def dataset_root(tmp_path, monkeypatch):
    root = tmp_path / "datasets"
    root.mkdir()
    monkeypatch.setenv("ASTAVERSE_DATASETS", str(root))
    return root


def test_slugify_normalizes_names():
    assert datasets.slugify("My Dataset.csv") == "my-dataset-csv"
    assert datasets.slugify("  hurricane_study  ") == "hurricane-study"


def test_slugify_rejects_empty():
    with pytest.raises(ValueError, match="at least one letter"):
        datasets.slugify("---")


def test_preview_upload_profiles_csv(dataset_root):
    content = b"year,deaths\n2000,12\n2001,8\n"
    preview = datasets.preview_upload(content, name="storm-data")

    assert preview["name"] == "storm-data"
    assert preview["n_rows"] == 2
    assert preview["n_columns"] == 2
    assert preview["available"] is True
    assert preview["columns"][0]["name"] == "year"
    assert preview["columns"][0]["dtype"] == "number"


def test_import_upload_writes_astaverse_folder(dataset_root):
    content = b"name,femininity,deaths\nAlice,0.9,120\nBob,0.1,80\n"
    created = datasets.import_upload(
        content,
        name="hurricane-demo",
        description="Storm fatalities by name gender coding.",
        column_descriptions={
            "min": "Minimum pressure of the storm",
            "deaths": "Number of fatalities",
        },
    )

    folder = dataset_root / "hurricane-demo"
    assert folder.is_dir()
    assert (folder / "data.csv").read_bytes() == content
    info = json.loads((folder / "info.json").read_text())
    assert "research_questions" not in info
    assert info["data_desc"]["dataset_description"] == (
        "Storm fatalities by name gender coding."
    )
    assert info["data_desc"]["num_rows"] == 2
    assert info["data_desc"]["field_names"] == ["name", "femininity", "deaths"]
    fields = {field["column"]: field["properties"] for field in info["data_desc"]["fields"]}
    assert fields["deaths"]["description"] == "Number of fatalities"
    assert fields["deaths"]["num_unique_values"] == 2
    assert fields["femininity"]["std"] is not None
    assert created.name == "hurricane-demo"
    assert created.kind == "astaverse"
    assert created.fields
    assert datasets.get("hurricane-demo") is not None


def test_import_upload_rejects_duplicate_name(dataset_root):
    content = b"x,y\n1,2\n"
    datasets.import_upload(content, name="duplicate")

    with pytest.raises(ValueError, match="already exists"):
        datasets.import_upload(content, name="duplicate")


@pytest.fixture
def client(dataset_root):
    from astaverse.adapters import api

    return TestClient(api.app)


def test_api_dataset_preview_and_create(client, dataset_root):
    csv = b"feature,outcome\n1,0\n2,1\n3,0\n"
    preview = client.post(
        "/api/datasets/preview",
        data={"name": "demo-panel", "description": "A small panel"},
        files={"file": ("demo.csv", csv, "text/csv")},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["name"] == "demo-panel"
    assert body["n_rows"] == 3
    assert body["available"] is True

    created = client.post(
        "/api/datasets",
        data={
            "name": "demo-panel",
            "description": "A small panel",
            "column_descriptions": '{"feature":"Predictor variable","outcome":"Binary outcome"}',
        },
        files={"file": ("demo.csv", csv, "text/csv")},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["name"] == "demo-panel"
    assert payload["kind"] == "astaverse"
    assert payload["fields"][0]["name"] == "feature"
    assert payload["fields"][0]["description"] == "Predictor variable"
    assert (dataset_root / "demo-panel" / "data.csv").exists()

    listed = client.get("/api/datasets").json()
    assert any(item["name"] == "demo-panel" for item in listed)


def test_head_streams_first_rows_of_bundled_dataset():
    preview = datasets.head("hurricane", limit=5)
    assert preview is not None
    assert preview["name"] == "hurricane"
    assert preview["n_rows"] == 94
    assert preview["limit"] == 5
    assert len(preview["columns"]) == 14
    assert len(preview["rows"]) == 5
    assert all(len(row) == 14 for row in preview["rows"])


def test_head_caps_limit_and_handles_missing_dataset(dataset_root):
    datasets.import_upload(b"x,y\n1,2\n3,4\n5,6\n", name="tiny")
    assert datasets.head("tiny", limit=0)["rows"] == [["1", "2"]]
    assert datasets.head("tiny", limit=10_000)["limit"] == datasets.MAX_PREVIEW_ROWS
    assert datasets.head("does-not-exist") is None


def test_api_dataset_rows(client, dataset_root):
    datasets.import_upload(b"x,y\n1,2\n3,4\n5,6\n", name="tiny")

    response = client.get("/api/datasets/tiny/rows", params={"limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == ["x", "y"]
    assert body["rows"] == [["1", "2"], ["3", "4"]]
    assert body["n_rows"] == 3

    assert client.get("/api/datasets/nope/rows").status_code == 404
