import base64
import json
import uuid
from datetime import date, datetime

import pymongo
import pytest
import yaml

from endlessdb import (
    CollectionLogicContainer,
    EndlessCollection,
    EndlessConfiguration,
    EndlessDatabase,
    EndlessDocument,
    InvalidValueError,
    PropertyNotFoundError,
    ReadOnlyError,
    TypeExpectationError,
    UnsupportedComparisonError,
    json_default_encoder,
    mask_mongodb_url,
    mongodb_database_from_url,
)


TEST_COVERAGE_SUMMARY = [
    "EndlessConfiguration.apply and inherited overrides",
    "EndlessDatabase logic access, URL masking, and debug fluent return",
    "EndlessCollection document creation, write, reload, delete, and equality",
    "EndlessDocument attribute access, item access, nested dot paths, and integer ids",
    "Virtual descendants with create=True and rewrite=True",
    "Document references and ref_to_id serialization",
    "CollectionLogicContainer.find and find_one",
    "Per-instance EndlessDatabase connection overrides and URL helpers",
    "Typed EndlessDB exception classes",
    "Typed descendant strict mode",
    "Removed unused public w helper",
    "JSON, YAML, base64, bytes, date, and datetime serialization",
    "Read-only YAML collections loaded through from_yml",
    "Missing and non-dict YAML negative paths",
    "List and nested list values in Mongo writes",
    "Protected mode, invalid value validation, root read-only behavior, and comparison errors",
    "Debugger-friendly __repr__ and __str__ output",
]


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
    # Checks configuration overrides, database logic access, URL masking, and debug fluent return.
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
    assert edbl.url_info("mongodb://localhost:27017/")["masked"] == "mongodb://localhost:27017/"
    assert mask_mongodb_url("mongodb://user:p%40ss@localhost:27017/db?x=1") == (
        "mongodb://user:******@localhost:27017/db?x=1"
    )
    assert mongodb_database_from_url("mongodb://user:secret@localhost:27017/db?x=1") == "db"
    assert mongodb_database_from_url("mongodb://localhost:27017/") is None
    assert edbl.build_url("localhost", 27017, "root", "root", "tests-endlessdb") == (
        "mongodb://root:root@localhost:27017/tests-endlessdb?authSource=admin&authMechanism=SCRAM-SHA-256"
    )
    assert edbl.build_url("localhost", 27017, "", "", "tests-endlessdb") == (
        "mongodb://localhost:27017/tests-endlessdb"
    )

    assert edb(debug=True) is edb
    assert edb().debug is True


def test_database_constructor_connection_overrides(endlessdb_configuration, mongo_available):
    # Checks that explicit constructor arguments override configuration per database instance.
    edb = EndlessDatabase(
        host="localhost",
        port=27017,
        user="root",
        password="root",
        database="tests-endlessdb-explicit",
    )
    try:
        assert edb().key() == "tests-endlessdb-explicit"
        assert edb().url_info(edb()._url["url"])["masked"] == (
            "mongodb://root:****@localhost:27017/tests-endlessdb-explicit?authSource=admin&authMechanism=SCRAM-SHA-256"
        )
        edb().mongo().command("ping")
    finally:
        edb().mongo().client.drop_database("tests-endlessdb-explicit")

    url_database = f"tests-endlessdb-url-{uuid.uuid4().hex}"
    url_edb = EndlessDatabase(
        url=f"mongodb://root:root@localhost:27017/{url_database}?authSource=admin&authMechanism=SCRAM-SHA-256"
    )
    try:
        assert url_edb().key() == url_database
        url_edb().mongo().command("ping")
    finally:
        url_edb().mongo().client.drop_database(url_database)


def test_collection_document_write_reload_and_delete(collection):
    # Checks Mongo-backed collection writes, document reload, delete, and parent/path logic.
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
    # Checks attribute access, item access, nested dot paths, and integer document ids.
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {"profile": {"name": "Andrew"}}
    document = collection[doc_id]

    assert document.profile.name == "Andrew"

    document["ai.openai.api.base"] = "https://openai.com"
    assert document.ai.openai.api.base == "https://openai.com"

    document["ai.openai.api.base"] = "https://openai.example"
    document["ai.openai.api.timeout"] = 30
    document().reload()
    assert document["ai.openai.api.base"] == "https://openai.example"
    assert document["ai.openai.api.timeout"] == 30

    collection[157166437] = {"first_name": "Andrew"}
    assert collection[157166437].first_name == "Andrew"
    collection["157166437.first_name"] = "Andrew"
    assert collection[157166437].first_name == "Andrew"


def test_create_and_rewrite_virtual_descendants(collection):
    # Checks virtual document defaults with create=True and replacement with rewrite=True.
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
    # Checks assigning EndlessDocument references and serializing them as target ids.
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
    # Checks find and find_one wrappers around PyMongo collection queries.
    marker = uuid.uuid4().hex
    first_id = f"doc_{uuid.uuid4().hex}"
    second_id = f"doc_{uuid.uuid4().hex}"

    collection[first_id] = {"marker": marker, "order": 1}
    collection[second_id] = {"marker": marker, "order": 2}

    found = [document.id for document in collection().find({"marker": marker})]
    assert set(found) == {first_id, second_id}

    assert collection().find_one({"order": 1}).id == first_id
    assert list(collection().find({"marker": "missing"})) == []
    assert collection().find_one({"marker": "missing"}) is None


def test_typed_descendant_strict_mode(collection):
    # Checks typed descendant expectations with strict exception mode.
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {"count": 1, "name": "Andrew"}
    document = collection[doc_id]

    typed_document = document(int, exception=True)
    assert typed_document.count == 1

    with pytest.raises(TypeExpectationError, match="not instance"):
        typed_document.name

    with pytest.raises(PropertyNotFoundError, match="not found"):
        typed_document.missing


def test_unused_w_helper_is_not_public():
    # Checks that the old experimental w helper is no longer exported.
    import endlessdb as endlessdb_module

    assert "w" not in endlessdb_module.__all__
    assert not hasattr(endlessdb_module, "w")


def test_serialization_json_yaml_and_base64(collection):
    # Checks dict, JSON, base64 JSON, YAML, bytes, date, and datetime serialization.
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
    # Checks read-only YAML collections and reload behavior when YAML keys change.
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

    with pytest.raises(ReadOnlyError, match="read-only"):
        collection["service.debug"] = False

    config_path.write_text("service:\n  debug: false\n", encoding="utf-8")
    collection().reload()

    assert collection.service.debug is False
    assert "endpoint" not in dict(collection.service().to_dict())


def test_yml_collection_negative_paths(tmp_path):
    # Checks missing YAML files and YAML documents that are not mapping objects.
    missing_path = tmp_path / "missing.yml"
    with pytest.raises(FileNotFoundError):
        CollectionLogicContainer.from_yml(missing_path)

    list_path = tmp_path / "list.yml"
    list_path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(InvalidValueError, match="must be a dict"):
        CollectionLogicContainer.from_yml(list_path)


def test_list_values_and_nested_lists(collection):
    # Checks list and nested list values accepted by Mongo-backed writes.
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {
        "tags": ["alpha", "beta"],
        "matrix": [[1, 2], [3, 4]],
        "items": [{"name": "one"}, {"name": "two"}],
    }

    document = collection[doc_id]
    assert document.tags == ["alpha", "beta"]
    assert document.matrix == [[1, 2], [3, 4]]
    assert document.items == [{"name": "one"}, {"name": "two"}]

    document.tags = ["gamma", "delta"]
    document().reload()
    assert document.tags == ["gamma", "delta"]


def test_protected_mode_invalid_values_and_readonly_root(collection, edb):
    # Checks protected documents, invalid values, root read-only behavior, and comparison errors.
    doc_id = f"doc_{uuid.uuid4().hex}"
    collection[doc_id] = {"name": "readonly"}
    document = collection[doc_id]

    protected_document = document(protected=True)
    assert protected_document is document

    with pytest.raises(ReadOnlyError, match="protected and read-only"):
        document.name = "changed"

    with pytest.raises(InvalidValueError, match="Value must be instance"):
        collection[f"bad_{uuid.uuid4().hex}"] = {"value": object()}

    with pytest.raises(ReadOnlyError, match="Id is read-only"):
        document.id = "new-id"

    with pytest.raises(ReadOnlyError, match="read-only"):
        edb.anything = {"value": True}

    with pytest.raises(UnsupportedComparisonError, match="comparison"):
        document == "not-a-document"


def test_debugger_friendly_representations(collection):
    # Checks debugger-friendly __repr__ and __str__ markers for dynamic wrappers.
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
