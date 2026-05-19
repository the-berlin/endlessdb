from common import make_database, reset_collection, sample_key

edb = make_database()
collection_name = sample_key("updates")
employees = edb[collection_name]

try:
    employees["john"] = {
        "name": "John",
        "age": 25,
        "profile": {"city": "New York", "zip": 10001},
        "settings": {"theme": "dark"},
    }

    employees["john"] = {"age": 26}
    john = employees["john"]
    john().reload()
    print("patch assignment:", john.name, john.age)

    employees().patch("john", {"role": "developer"})
    john().reload()
    print("explicit patch:", john.role)

    employees().replace("jane", {"name": "Jane", "status": "active"})
    print("replace document:", employees["jane"]().to_dict())

    john().unset("profile.city")
    john().reload()
    print("profile after unset:", john.profile().to_dict())

    john.settings().delete()
    john().reload()
    print("settings removed:", "settings" not in john().to_dict())

    employees["jane"]().delete()
    print("jane exists:", employees().exists({"_id": "jane"}))
finally:
    reset_collection(edb, collection_name)