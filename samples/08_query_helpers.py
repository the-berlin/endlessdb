from common import make_database, reset_collection, sample_key

edb = make_database()
collection_name = sample_key("queries")
tasks = edb[collection_name]

try:
    tasks["build"] = {"name": "Build", "priority": 2, "done": False}
    tasks["ship"] = {"name": "Ship", "priority": 3, "done": False}
    tasks["archive"] = {"name": "Archive", "priority": 1, "done": True}

    open_tasks = list(
        tasks().find(
            {"done": False},
            sort=[("priority", -1)],
            limit=2,
        )
    )

    print("open order:", [task.id for task in open_tasks])
    print("open count:", tasks().count({"done": False}))
    print("has archive:", tasks().exists({"_id": "archive"}))
    print("first open:", tasks().first({"done": False}, sort=[("priority", -1)]).name)
    print("raw collection:", tasks().raw().name)
finally:
    reset_collection(edb, collection_name)
