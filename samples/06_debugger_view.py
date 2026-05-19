from common import make_database, reset_collection, sample_key

edb = make_database()
collection_name = sample_key("debugger")
collection = edb[collection_name]

try:
    collection["example"] = {"name": "Debugger View", "nested": {"value": 1}}
    document = collection["example"]

    collection(debug=True)
    document(debug=True)

    print("database repr:", repr(edb))
    print("collection repr:", repr(collection))
    print("document repr:", repr(document))
    print("nested repr:", repr(document.nested))
finally:
    reset_collection(edb, collection_name)
