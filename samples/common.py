from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.endlessdb import EndlessConfiguration, EndlessDatabase


class SamplesConfiguration(EndlessConfiguration):
    def override(self):
        self.CONFIG_YML = "samples/storage/config.yml"
        self.CONFIG_COLLECTION = "config"
        self.MONGO_URI = "mongodb://root:root@localhost:27017/"
        self.MONGO_DATABASE = "endlessdb-samples"


def make_database():
    SamplesConfiguration.apply()
    return EndlessDatabase()


def sample_key(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def reset_collection(edb, name):
    edb().mongo().drop_collection(name)
    edb().collections().pop(name, None)
