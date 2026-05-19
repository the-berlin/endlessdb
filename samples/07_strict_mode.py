from common import make_database, reset_collection, sample_key
from endlessdb import PropertyNotFoundError

edb = make_database(strict=True)
collection_name = sample_key("strict")

try:
    edb().mongo().create_collection(collection_name)
    users = edb[collection_name]

    try:
        users["missing"]
    except PropertyNotFoundError as exc:
        print("missing document:", exc)

    users["andrew"] = {"name": "Andrew", "role": "maintainer"}
    user = users["andrew"]

    print("name:", user.name)

    try:
        user.rol
    except PropertyNotFoundError as exc:
        print("missing property:", exc)
finally:
    reset_collection(edb, collection_name)
