from common import make_database, reset_collection, sample_key

edb = make_database()
collection_name = sample_key("nested")
settings = edb[collection_name]

try:
    settings["service"] = {"enabled": True}
    service = settings["service"]

    service["ai.openai.api.base"] = "https://api.example.test"
    service["ai.openai.api.timeout"] = 30
    service().reload()

    data = service().to_dict()
    api = data["ai"]["openai"]["api"]

    print("api base:", api["base"])
    print("api timeout:", api["timeout"])
    print("document path:", service().path(True))
finally:
    reset_collection(edb, collection_name)
