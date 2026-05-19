from datetime import datetime
import base64
import json

import yaml

from common import make_database, reset_collection, sample_key


edb = make_database()
collection_name = sample_key("serialization")
files = edb[collection_name]

try:
    now = datetime.now().replace(microsecond=0)
    files["readme"] = {
        "name": "README.md",
        "payload": b"hello",
        "created_at": now,
        "metadata": {"kind": "text"},
    }

    readme = files["readme"]
    json_text = readme().to_json()
    base64_json = readme().to_json(base64=True)
    yaml_text = files().to_yml()

    print("json:", json.loads(json_text))
    print("base64 json:", json.loads(base64.b64decode(base64_json).decode("utf-8")))
    print("yaml keys:", list(yaml.safe_load(yaml_text).keys()))
finally:
    reset_collection(edb, collection_name)
