from common import make_database, reset_collection, sample_key

edb = make_database()
employees_name = sample_key("employees")
departments_name = sample_key("departments")
employees = edb[employees_name]
departments = edb[departments_name]

try:
    employees["john"] = {"name": "John", "age": 25}
    departments["it"] = {"name": "IT", "location": "New York"}

    john = employees["john"]
    it = departments["it"]
    john.department = it
    john().reload()

    print("employee:", john.name)
    print("department:", john.department.name)
    print("department id:", john().to_dict(ref_to_id=True)["department"])
finally:
    reset_collection(edb, employees_name)
    reset_collection(edb, departments_name)
