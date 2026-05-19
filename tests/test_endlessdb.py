import base64
import json
import uuid
from datetime import date, datetime

import pymongo
import pytest
import yaml

from src.endlessdb import (
    CollectionLogicContainer,
    EndlessCollection,
    EndlessConfiguration,
    EndlessDatabase,
    EndlessDocument,
    json_default_encoder,
)


class TestConfiguration(EndlessConfiguration):
    __test__ = False

    def override(self):
        self.CONFIG_YML = "tests/config.yml"
        self.MONGO_URI = "mongodb://admin:admin@localhost:27017/"


class TestInheritedConfiguration(TestConfiguration):
    __test__ = False

    def override(self):
        self.CONFIG_COLLECTION = "test_config"
        self.CONFIG_YML = "tests/config.yml"
        self.MONGO_URI = "mongodb://root:root@localhost:27017/"
        self.MONGO_DATABASE = "tests-endlessdb"


@pytest.fixture(scope="session", autouse=True)
def endlessdb_configuration():
    cfg = EndlessConfiguration()

    TestConfiguration.apply()
    assert cfg.MONGO_URI == "mongodb://admin:admin@localhost:27017/"

    TestInheritedConfiguration.apply()
    assert cfg.CONFIG_COLLECTION == "test_config"
    assert cfg.CONFIG_YML == "tests/config.yml"
    assert cfg.MONGO_URI == "mongodb://root:root@localhost:27017/"
    assert cfg.MONGO_DATABASE == "tests-endlessdb"
    assert cfg.eee is None

    return cfg


@pytest.fixture(scope="session", autouse=True)
def mongo_available(endlessdb_configuration):
    client = pymongo.MongoClient(
        endlessdb_configuration.MONGO_URI,
        serverSelectionTimeoutMS=5000,
    )
    try:
        client.admin.command("ping")
    except Exception as exc:
        pytest.skip(f"MongoDB integration database is unavailable: {exc}")
    finally:
        client.close()


@pytest.fixture
def edb(mongo_available):
    return EndlessDatabase()


@pytest.fixture
def collection_name(edb):
    name = f"test_{uuid.uuid4().hex}"
    yield name
    edb().mongo().drop_collection(name)
    edb().collections().pop(name, None)


@pytest.fixture
def collection(edb, collection_name):
    return edb[collection_name]


def test_database_and_configuration_logic(edb):
    edbl = edb()

    assert isinstance(str(edb), str)
    assert isinstance(repr(edb), str)
    assert isinstance(len(edb), int)
    assert isinstance(edbl.keys(), list)
    assert isinstance(edbl.mongo(), pymongo.database.Database)
    assert isinstance(edbl.config(), EndlessCollection)
    assert isinstance(edbl.defaults(), EndlessCollection)
    assert edbl.key() == "tests-endlessdb"
    assert edbl.url_info("mongodb://user:secret@localhost:27017/db?x=1")["masked"] == (
        "mongodb://user:******@localhost:27017/db?x=1"
    )

    assert edb(debug=True) is edb
    assert edb().debug is True


def test_collection_document_write_reload_and_delete(collection):
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {"property1": 0}

    document = collection[doc_id]
    document_logic = document()

    assert isinstance(collection(), CollectionLogicContainer)
    assert isinstance(document, EndlessDocument)
    assert document.property1 == 0
    assert document.id == doc_id
    assert len(document) == 2
    assert document_logic.parent() == collection
    assert document_logic.collection() == collection
    assert document_logic.edb() == collection().edb()
    assert document_logic.path(True).endswith(f"/{doc_id}")

    document.property1 = 1
    document.property2 = 2
    assert document.property1 == 1
    assert document.property2 == 2

    collection().mongo().update_one(
        {"_id": doc_id},
        {"$set": {"property2": 3}},
        upsert=True,
    )
    assert document.property2 == 2

    document_logic.reload()
    assert document.property2 == 3

    document_logic.delete()
    assert document == None


def test_nested_attribute_and_item_paths(collection):
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {"profile": {"name": "Andrew"}}
    document = collection[doc_id]

    assert document.profile.name == "Andrew"

    document["ai.openai.api.base"] = "https://openai.com"
    assert document.ai.openai.api.base == "https://openai.com"

    document["ai.openai.api.base"] = "https://openai.example"
    assert document["ai.openai.api.base"] == "https://openai.example"

    collection[157166437] = {"first_name": "Andrei"}
    assert collection[157166437].first_name == "Andrei"
    collection["157166437.first_name"] = "Andrew"
    assert collection[157166437].first_name == "Andrew"


def test_create_and_rewrite_virtual_descendants(collection):
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {"seed": True}
    document = collection[doc_id]

    created = document.something({"haha": {"bla": "bla-bla"}}, create=True)
    assert created.haha.bla == "bla-bla"

    document().reload()
    assert document.something.haha.bla == "bla-bla"

    rewritten = document.something({"haha": {"bla": "bla-bla-bla"}}, rewrite=True)
    assert rewritten.haha.bla == "bla-bla-bla"

    document().reload()
    assert document.something.haha.bla == "bla-bla-bla"


def test_document_references(collection, edb):
    employee_collection = collection
    department_collection_name = f"test_department_{uuid.uuid4().hex}"
    department_collection = edb[department_collection_name]

    try:
        employee_id = f"employee_{uuid.uuid4().hex}"
        department_id = f"department_{uuid.uuid4().hex}"

        employee_collection[employee_id] = {"Name": "John", "Age": 25}
        department_collection[department_id] = {"Name": "IT", "Location": "New York"}

        employee = employee_collection[employee_id]
        department = department_collection[department_id]

        employee.Department = department
        employee().reload()

        assert employee.Department == department
        assert dict(employee().to_dict(ref_to_id=True))["Department"] == department_id
    finally:
        edb().mongo().drop_collection(department_collection_name)
        edb().collections().pop(department_collection_name, None)


def test_find_and_find_one(collection):
    marker = uuid.uuid4().hex
    first_id = f"doc_{uuid.uuid4().hex}"
    second_id = f"doc_{uuid.uuid4().hex}"

    collection[first_id] = {"marker": marker, "order": 1}
    collection[second_id] = {"marker": marker, "order": 2}

    found = [document.id for document in collection().find({"marker": marker})]
    assert set(found) == {first_id, second_id}

    assert collection().find_one({"order": 1}).id == first_id
    assert list(collection().find({"marker": "missing"})) == [None]
    assert collection().find_one({"marker": "missing"}) is None


def test_serialization_json_yaml_and_base64(collection):
    doc_id = f"doc_{uuid.uuid4().hex}"
    now = datetime.now()
    now = now.replace(microsecond=(now.microsecond // 1000) * 1000)

    collection[doc_id] = {
        "name": "binary",
        "payload": b"hello",
        "now": now,
        "nested": {"value": 5},
    }
    document = collection[doc_id]

    data = dict(document().to_dict())
    assert data["id"] == doc_id
    assert data["nested"] == {"value": 5}

    json_data = json.loads(document().to_json())
    assert json_data["payload"] == base64.b64encode(b"hello").decode("utf-8")
    assert json_data["now"] == now.isoformat()
    assert json_default_encoder(date.today()) == date.today().isoformat()

    encoded_json = document().to_json(base64=True)
    decoded_json = json.loads(base64.b64decode(encoded_json).decode("utf-8"))
    assert decoded_json["name"] == "binary"

    yaml_data = yaml.safe_load(collection().to_yml())
    assert yaml_data[doc_id]["name"] == "binary"


def test_yml_collection_is_read_only_and_reloadable(tmp_path):
    config_path = tmp_path / "defaults.yml"
    config_path.write_text(
        "service:\n  debug: true\n  endpoint: https://example.test\n",
        encoding="utf-8",
    )

    collection = CollectionLogicContainer.from_yml(config_path)

    assert collection.service.debug is True
    assert collection.service.endpoint == "https://example.test"
    assert collection().mongo() is None
    assert collection().path(True) == "yml/defaults.yml"

    with pytest.raises(Exception, match="read-only"):
        collection["service.debug"] = False

    config_path.write_text("service:\n  debug: false\n", encoding="utf-8")
    collection().reload()

    assert collection.service.debug is False
    assert "endpoint" not in dict(collection.service().to_dict())


def test_protected_mode_invalid_values_and_readonly_root(collection, edb):
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {"name": "readonly"}
    document = collection[doc_id]

    protected_document = document(protected=True)
    assert protected_document is document

    with pytest.raises(Exception, match="protected and read-only"):
        document.name = "changed"

    with pytest.raises(Exception, match="Value must be instance"):
        collection[f"bad_{uuid.uuid4().hex}"] = {"value": object()}

    with pytest.raises(Exception, match="Id is read-only"):
        document.id = "new-id"

    with pytest.raises(Exception, match="read-only"):
        edb.anything = {"value": True}

    with pytest.raises(Exception, match="comparison"):
        document == "not-a-document"


def test_debugger_friendly_representations(collection):
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {"name": "debug"}
    document = collection[doc_id]

    collection(debug=True)
    document(debug=True)

    assert "tests-endlessdb" in repr(collection)
    assert collection().key() in str(collection)
    assert doc_id in repr(document)
    assert doc_id in str(document)
    assert "🐞" in repr(document)
