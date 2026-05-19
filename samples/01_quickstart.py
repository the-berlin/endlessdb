from common import make_database, reset_collection, sample_key

edb = make_database()
collection_name = sample_key("quickstart")
people = edb[collection_name]

try:
    people["andrew"] = {"name": "Andrew", "role": "developer"}
    person = people["andrew"]
    person.role = "maintainer"

    print("collection:", people)
    print("document:", person)
    print("name:", person.name)
    print("role:", person.role)
    print("dict:", person().to_dict())
finally:
    reset_collection(edb, collection_name)
