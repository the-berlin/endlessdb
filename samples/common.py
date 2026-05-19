import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from endlessdb import EndlessConfiguration, EndlessDatabase


class SamplesConfiguration(EndlessConfiguration):
    def override(self):
        self.CONFIG_YML = "samples/storage/config.yml"
        self.CONFIG_COLLECTION = "config"
        self.MONGO_URI = "mongodb://root:root@localhost:27017/"
        self.MONGO_DATABASE = "endlessdb-samples"


def make_database(strict=False):
    SamplesConfiguration.apply()
    return EndlessDatabase(strict=strict)


def sample_key(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def reset_collection(edb, name):
    edb().mongo().drop_collection(name)
    edb().collections().pop(name, None)
