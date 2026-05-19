from pathlib import Path

from common import ROOT

from src.endlessdb import CollectionLogicContainer


config_path = ROOT / "samples" / "storage" / "config.yml"
config = CollectionLogicContainer.from_yml(config_path)

print("config path:", config().path(True))
print("debug:", config.debug)
print("mongo:", config().mongo())
