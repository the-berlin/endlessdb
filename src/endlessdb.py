"""Dynamic object wrapper around MongoDB databases, collections, and documents.

EndlessDB intentionally exposes MongoDB data through Python attribute and item
access. Public wrappers (`EndlessDatabase`, `EndlessCollection`, and
`EndlessDocument`) stay small and debugger-friendly; their operational state
lives in the matching `*LogicContainer` classes stored on each wrapper.
"""

from __future__ import annotations

import base64
import inspect
import json
import logging
import os
import re
import uuid
from abc import abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import bson
import pymongo
import pymongo.collection
import pymongo.database
import yaml
from bson.objectid import ObjectId

__all__ = [
    "CollectionLogicContainer",
    "DatabaseLogicContainer",
    "DocumentLogicContainer",
    "EndlessCollection",
    "EndlessConfiguration",
    "EndlessDBError",
    "EndlessDatabase",
    "EndlessDocument",
    "Formatter",
    "InvalidValueError",
    "Logger",
    "PropertyNotFoundError",
    "ReadOnlyError",
    "TypeExpectationError",
    "UnsupportedComparisonError",
    "is_magic_method",
    "is_valid_value",
    "json_default_encoder",
    "re_mask_subgroup",
]

LOGIC_KEY = "***"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EndlessDBError(Exception):
    """Base class for all EndlessDB-specific errors."""


class ReadOnlyError(EndlessDBError):
    """Raised when a write is attempted against a read-only wrapper."""


class InvalidValueError(EndlessDBError, TypeError):
    """Raised when a value cannot be represented by the EndlessDB storage model."""


class UnsupportedComparisonError(EndlessDBError, TypeError):
    """Raised when a dynamic wrapper is compared with an unsupported object."""


class PropertyNotFoundError(EndlessDBError, AttributeError):
    """Raised when strict dynamic lookup cannot find a requested property."""


class TypeExpectationError(EndlessDBError, TypeError):
    """Raised when a value does not satisfy a typed descendant expectation."""


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


class Formatter(logging.Formatter):
    """ANSI color formatter used by the optional module logger."""

    default = "\x1b[39;20m\x1b[49;20m"

    white_background = "\x1b[47;20m"
    cyan_background = "\x1b[46;20m"

    white = "\x1b[37;20m"
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"

    bold_blue = "\x1b[34;1m"
    bold_magenta = "\x1b[35;1m"
    bold_green = "\x1b[32;1m"
    bold_white = "\x1b[37;1m"
    bold_red = "\x1b[31;1m"
    bold_yellow = "\x1b[33;1m"

    reset = "\x1b[0m"

    _levelname = f"{bold_yellow}[{bold_red}%(levelname)s{bold_yellow}]{default}"
    _application = f"{bold_yellow}[{bold_magenta}%(name)s{bold_yellow}]{default}"
    _time = f"{bold_yellow}[{bold_white}%(asctime)s{bold_yellow}]{default}"

    _title = f"{_levelname}{_application}{_time} "
    _format = f"%(message)s{reset}"

    FORMATS = {
        logging.DEBUG: f"{blue}{_title}{blue}{_format}",
        logging.INFO: f"{green}{_title}{green}{_format}",
        logging.WARNING: f"{yellow}{_title}{yellow}{_format}",
        logging.ERROR: f"{red}{_title}{red}{_format}",
        logging.CRITICAL: f"{bold_red}{_title}{bold_red}{_format}",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with the color assigned to its level."""
        log_fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class Logger:
    """Tiny logger facade retained for sample/debug output compatibility."""

    _ch = None

    def __init__(self, name: str) -> None:
        """Create or reuse a configured logger with EndlessDB formatting."""
        self._name = name
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        if Logger._ch is None:
            Logger.init()
        if Logger._ch not in self._logger.handlers:
            self._logger.addHandler(Logger._ch)
        self._logger.propagate = False

    @staticmethod
    def init() -> None:
        """Initialize the shared stream handler used by all Logger instances."""
        Logger._ch = logging.StreamHandler()
        Logger._ch.setLevel(logging.DEBUG)
        Logger._ch.setFormatter(Formatter())

    def __str__(self) -> str:
        """Return a compact logger label for debugger views."""
        return f"📝{self._name}Logger"

    def __repr__(self) -> str:
        """Return the same compact label used by `str()`."""
        return self.__str__()

    def debug(self, msg: Any) -> None:
        """Write a DEBUG log message."""
        self._logger.debug(msg)

    def info(self, msg: Any) -> None:
        """Write an INFO log message."""
        self._logger.info(msg)

    def warning(self, msg: Any) -> None:
        """Write a WARNING log message."""
        self._logger.warning(msg)

    def error(self, msg: Any) -> None:
        """Write an ERROR log message."""
        self._logger.error(msg)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class EndlessConfiguration:
    """Runtime configuration with inheritable override classes.

    A subclass can override values and call `apply()`. The override is then
    consulted by base configuration instances through dynamic attribute access.
    Missing keys intentionally return `None`, matching the public dynamic API.
    """

    _override = {}

    def __init__(self) -> None:
        """Load base values from the environment or initialize a subclass override."""
        if type(self) == EndlessConfiguration:
            self.MONGO_HOST = os.environ.get("CORE_MONGO_HOST", "mongo")
            self.MONGO_PORT = int(os.environ.get("CORE_MONGO_PORT", 27017))
            self.MONGO_USER = os.environ.get("CORE_MONGO_USER", "root")
            self.MONGO_PASSWORD = os.environ.get("CORE_MONGO_PASSWORD", "root")
            self.MONGO_DATABASE = os.environ.get("CORE_MONGO_DATABASE", "endlessdb")
            self.MONGO_URI = os.environ.get("CORE_MONGO_URI", "mongodb://localhost:27017/")

            self.CONFIG_COLLECTION = "config"
            self.CONFIG_YML: str = "~/config.yml"
        else:
            self.override()

    def __str__(self) -> str:
        """Return a compact configuration label for debugger views."""
        return f"⚙️Endlessdb configuration({self.__class__.__name__})"

    def __repr__(self) -> str:
        """Return the same compact label used by `str()`."""
        return self.__str__()

    @classmethod
    def apply(cls) -> None:
        """Register a configuration subclass as an override for its base class."""
        if issubclass(cls, EndlessConfiguration):
            if len(cls.__bases__) > 0 and issubclass(cls.__bases__[0], EndlessConfiguration):
                EndlessConfiguration._override[str(cls.__bases__[0])] = cls()

    @abstractmethod
    def override(self) -> None:
        """Override configuration values in subclasses."""
        pass

    def __getattr__(self, key: str) -> Any:
        """Resolve overrides before falling back to local attributes."""
        c = type(self)
        cs = str(c)
        _ov = None
        if cs in EndlessConfiguration._override:
            _ov = EndlessConfiguration._override[cs].__getattr__(key)

        if _ov is not None:
            return _ov

        if key in self.__dict__:
            return self.__dict__[key]

        return None

    def __getitem__(self, key: str) -> Any:
        """Resolve configuration values by item access."""
        return self.__getattr__(key)

    def __getattribute__(self, name: str) -> Any:
        """Preserve dynamic config lookup while keeping Python internals intact."""
        if name == "__class__":
            return type(self)

        _dict = super().__getattribute__("__dict__")
        if name == "__dict__":
            return _dict

        _dir = dir(self)
        if name in _dict or name not in _dir:
            return self.__getattr__(name)

        return super().__getattribute__(name)


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------


def re_mask_subgroup(subgroup: str, mask: str, m: re.Match[str]) -> str | None:
    """Mask a regex subgroup while preserving the rest of the match."""
    if m.group(subgroup) not in [None, ""]:
        start = m.start(subgroup)
        end = m.end(subgroup)
        length = end - start
        return m.group()[:start] + mask * length + m.group()[end:]


def json_default_encoder(obj: Any) -> Any:
    """JSON fallback encoder for EndlessDB values."""
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")

    if isinstance(obj, (date, datetime)):
        return obj.isoformat()

    if hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return obj.__str__()


def is_magic_method(method: Any) -> bool:
    """Return True when a key looks like a Python dunder method name."""
    if isinstance(method, int):
        return False

    return method.startswith("__") and method.endswith("__")


def is_valid_value(value: Any) -> bool:
    """Validate values before sending them to PyMongo/BSON."""
    valid_types = [EndlessDocument, str, int, float, bool, bytes, bytearray, datetime, uuid.UUID, type(None)]
    if type(value) in valid_types:
        return True

    if isinstance(value, dict):
        return all(is_valid_value(item) for item in value.values())

    if isinstance(value, list):
        return all(is_valid_value(item) for item in value)

    return False


def to_storage_value(value: Any) -> Any:
    """Convert EndlessDB wrapper values into MongoDB-storable values."""
    if isinstance(value, EndlessDocument):
        return value().to_ref()

    if isinstance(value, dict):
        return {key: to_storage_value(item) for key, item in value.items()}

    if isinstance(value, list):
        return [to_storage_value(item) for item in value]

    return value


def normalize_document_key(key: Any) -> Any:
    """Coerce string integer keys to int while leaving other keys unchanged."""
    try:
        return int(key)
    except (TypeError, ValueError):
        return key


def mongodb_database_from_url(url: str | None) -> str | None:
    """Extract the database path segment from a MongoDB URL when one exists."""
    if not url:
        return None

    path = urlsplit(url).path.strip("/")
    if not path:
        return None

    return path.split("/", 1)[0] or None


def mask_mongodb_url(url: str, mask: str = "*") -> str:
    """Mask the password part of a MongoDB URL while preserving its shape."""
    parts = urlsplit(url)
    if not parts.password:
        return url

    username = parts.username or ""
    password = mask * len(parts.password)
    credentials = f"{username}:{password}"
    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port else ""

    return urlunsplit((parts.scheme, f"{credentials}@{host}{port}", parts.path, parts.query, parts.fragment))


# ---------------------------------------------------------------------------
# Logic containers
# ---------------------------------------------------------------------------


class DocumentLogicContainer:
    """Mutable operational state for one `EndlessDocument` wrapper."""

    def __init__(
        self, _: EndlessDocument, key: Any, obj: dict[str, Any] | None, parent_logic: Any, virtual: bool
    ) -> None:
        """Bind the wrapper to its parent and load the initial document data."""
        self.uuid = str(uuid.uuid4())
        self._ = _
        self.__ = _.__dict__
        self._key = key
        self._keys = []
        self._path = f"{parent_logic.path(True)}/{key}"
        self._parent_logic = parent_logic
        self._iteration = None

        self.static = False
        self.debug = False
        self.emojify = getattr(parent_logic, "emojify", False)
        self.strict = getattr(parent_logic, "strict", False)
        self.virtual = virtual
        self.protected = parent_logic.protected

        self.descendant_expected = None
        self.descendant_create = False
        self.descendant_rewrite = False
        self.descendant_exception = False

        self._reload(obj)

    def __call__(self) -> EndlessDocument:
        """Return the public document wrapper owned by this logic container."""
        return self._

    def __repr__(self) -> str:
        """Return the debugger-friendly logic representation."""
        if self.emojify or self.debug:
            return f"🧩logic({self.repr()})"
        return f"Logic({self.repr()})"

    def _reload(self, obj: dict[str, Any] | None) -> None:
        """Refresh wrapper attributes from MongoDB, YAML, or supplied data."""
        mongo = None
        _self = self._
        if obj is None:
            _parent = self.parent()
            if isinstance(_parent, EndlessCollection):
                mongo = self.mongo()
                if mongo is None:
                    collection = self.collection()
                    collection().reload()
                    return
                else:
                    obj = mongo.find_one({"_id": self._key})
                    if obj is None:
                        self.virtual = True
                        return
                    else:
                        self.virtual = False
            else:
                _parent()._reload(None)
                return

        if self._key is None:
            path = self._path.split("/")
            self._key = normalize_document_key(path[-1])

        virtual = self.virtual

        _keys = self._keys.copy()
        self._keys.clear()
        _path = f"{self.path(True)}"
        _edb = self.edb()
        for _key in obj:
            value = obj[_key]
            self._keys.append(_key)

            if isinstance(value, bson.dbref.DBRef):
                value = _edb[value.collection][value.id]

            if self.descendant_expected is None:
                if isinstance(value, EndlessDocument) or isinstance(value, dict):
                    if self.static:
                        if _key in self.__ and isinstance(self.__[_key], EndlessDocument):
                            _self[_key]()._reload(value)
                        else:
                            self.__[_key] = self.descendant(_key, value, virtual, False)
                    else:
                        if isinstance(value, EndlessDocument) and isinstance(value().parent(), EndlessCollection):
                            document = value
                        else:
                            _property_path = f"{_path}/{_key}"
                            if mongo is None:
                                document = self.descendant(_key, value, virtual, False)
                            else:
                                documents = self.edb()().documents()
                                if _property_path in documents:
                                    document = documents[_property_path]
                                else:
                                    document = None

                                if document is not None:
                                    document()._reload(value)
                                else:
                                    document = self.descendant(_key, value, virtual, False)
                                    documents[_property_path] = document

                        self.__[_key] = document
                else:
                    if isinstance(value, ObjectId):
                        self.__[_key] = str(value)
                    else:
                        self.__[_key] = value
            else:
                if inspect.isclass(self.descendant_expected):
                    _type = self.descendant_expected
                else:
                    _type = type(self.descendant_expected)

                if isinstance(value, _type):
                    self.__[_key] = value

        for _key in _keys:
            if _key not in self._keys:
                del self.__[_key]

    def repr(self, srepr: str | None = None) -> str:
        """Build the compact debugger representation for this document path."""
        parent = self.parent()
        if not (self.emojify or self.debug):
            flags = []
            if self.virtual:
                flags.append("virtual=True")
            if self.protected:
                flags.append("protected=True")
            if self.descendant_expected is not None:
                flags.append("typed=True")

            flag_text = f", {', '.join(flags)}" if flags else ""
            repr = f"Document({self._key!r}, len={self.len()}{flag_text})"
            if srepr is not None:
                repr = f"{repr}/{srepr}"

            if parent is None:
                return repr
            return parent().repr(repr)

        repr = ""
        if self.debug:
            repr += "🐞"

        repr += "📑"

        if self.descendant_expected is not None:
            repr += "🔎"
        else:
            if self.virtual:
                repr += "🆕"

        if self.protected:
            repr += "🔒"
        else:
            repr += "🔓"

        repr += f"{self._key}"
        repr += "{" + f"ℓ{self.len()}" + "}"

        if srepr is not None:
            repr = f"{repr}/{srepr}"

        if parent is None:
            return repr
        else:
            return parent().repr(repr)

    def descendant(
        self, key: Any, obj: dict[str, Any] | None, virtual: bool = False, reload: bool = True
    ) -> EndlessDocument:
        """Return a cached child document or create one for a nested object."""
        edb = self.edb()
        if edb is not None:
            documents = self.edb()().documents()
            _path = f"{self.path(True)}/{key}"
            if _path in documents:
                document = documents[_path]
                if reload or obj is not None:
                    document()._reload(obj)
            else:
                document = EndlessDocument(key, obj, self, virtual)
                documents[_path] = document
            return document

        return EndlessDocument(key, obj, self, virtual)

    def len(self) -> int:
        """Return the number of known fields in the document."""
        return len(self._keys)

    def key(self) -> Any:
        """Return the MongoDB `_id` for this document."""
        return self._key

    def relative_path(self, current: str | None = None) -> str:
        """Return this document path relative to its collection."""
        if current is None:
            _path = str(self._key)
        else:
            _path = f"{self._key}/{current}"
        if isinstance(self._parent_logic, CollectionLogicContainer):
            return _path

        return f"{self._parent_logic.relative_path(_path)}"

    def path(self, full: bool = False) -> str:
        """Return the full or collection-relative document path."""
        if full:
            return self._path
        else:
            return self.relative_path()

    def parent(self) -> Any:
        """Return the parent public wrapper."""
        return self._parent_logic()

    def keys(self) -> list[Any]:
        """Return known field names in load order."""
        return self._keys

    def mongo(self) -> pymongo.collection.Collection:
        """Return the backing PyMongo collection when the document is Mongo-backed."""
        return self.collection()().mongo()

    def reload(self) -> EndlessDocument:
        """Reload the document from its backing source and return the wrapper."""
        self._reload(None)
        return self._

    def unset(self, path: str) -> EndlessDocument:
        """Unset a root or nested field below this document."""
        if not path:
            raise InvalidValueError("Unset path must not be empty")

        if self.protected:
            raise ReadOnlyError(f"{self} is protected and read-only")

        document_path = self.path().replace("/", ".")
        self.collection()().unset(f"{document_path}.{path}")
        return self._

    def delete(self) -> None:
        """Delete the root Mongo document, or delegate nested deletion upward."""
        if self.protected:
            raise ReadOnlyError(f"{self} is protected and read-only")

        if isinstance(self._parent_logic, CollectionLogicContainer):
            collection = self.mongo()
            if collection is None:
                raise ReadOnlyError(f"{self} is read-only")

            collection.delete_one({"_id": self._key})
            documents = self._parent_logic.edb()().documents()
            path = self.path(True)
            if path in documents:
                document = documents[path]
                document().virtual = True
                del documents[path]
        else:
            self.collection()().unset(self.path().replace("/", "."))
            self.virtual = True
            documents = self.edb()().documents()
            path = self.path(True)
            if path in documents:
                del documents[path]

    def edb(self) -> EndlessDatabase:
        """Return the owning database wrapper."""
        if isinstance(self._parent_logic, CollectionLogicContainer):
            return self._parent_logic.edb()

        return self._parent_logic._parent_logic.edb()

    def collection(self) -> EndlessCollection:
        """Return the owning collection wrapper."""
        if isinstance(self._parent_logic, CollectionLogicContainer):
            return self._parent_logic()

        return self._parent_logic.collection()

    def to_ref(self) -> dict[str, Any]:
        """Return a MongoDB DBRef-compatible dictionary for this document."""
        return {"$ref": self.collection()().key(), "$id": self._key}

    def iter_items(self, *args: Any, **kwargs: Any) -> Iterator[tuple[Any, Any]]:
        """Yield serializable key/value pairs for the document."""
        if "exclude" in kwargs:
            exclude = kwargs["exclude"]
        else:
            exclude = []

        if "include" in kwargs:
            include = kwargs["include"]
        else:
            include = []

        if "ref_to_id" in kwargs and kwargs["ref_to_id"]:
            ref_to_id = True
        else:
            ref_to_id = False

        _self = self._
        for key in self._keys:
            if key == "_id":
                _key = "id"
            else:
                _key = key
            if _key in exclude:
                continue

            if len(include) > 0 and _key not in include:
                continue

            value = _self[key]
            if isinstance(value, EndlessDocument):
                if ref_to_id:
                    data = value().key()
                else:
                    data = value().to_dict()
                yield (_key, data)
            else:
                yield (_key, value)

    def to_dict(self, *args: Any, **kwargs: Any) -> dict[Any, Any]:
        """Return a serializable dictionary for the document."""
        return dict(self.iter_items(*args, **kwargs))

    def to_json(self, *args: Any, **kwargs: Any) -> str:
        """Serialize the document to JSON, optionally base64-encoded."""
        if "base64" in kwargs and kwargs["base64"]:
            to_base64 = kwargs.pop("base64")
        else:
            to_base64 = False

        _dict = self.to_dict(**kwargs)
        _json = json.dumps(_dict, default=json_default_encoder, ensure_ascii=False)

        if to_base64:
            return base64.b64encode(_json.encode("utf-8")).decode("utf-8")

        return _json

    def to_yml(self) -> str:
        """Serialize the document to YAML."""
        _dict = self.to_dict()
        _yaml = yaml.dump(_dict, default_flow_style=False, allow_unicode=True)
        return _yaml


class CollectionLogicContainer:
    """Mutable operational state for one `EndlessCollection` wrapper."""

    def __init__(
        self,
        _: EndlessCollection,
        edb: EndlessDatabase | None,
        key: Any,
        yml: dict[str, Any] | None = None,
        defaults: EndlessCollection | None = None,
        _mongo: pymongo.database.Database | None = None,
    ) -> None:
        """Bind a collection wrapper to MongoDB or to read-only YAML data."""
        self.protected = False
        self.static = False
        self.debug = False
        self.emojify = False
        self.strict = False
        if edb is not None and LOGIC_KEY in edb.__dict__:
            self.emojify = edb().emojify
            self.strict = edb().strict
        self.virtual = False

        if isinstance(key, Path):
            _key = key.name
            self._source_path = key
        else:
            _key = key
            self._source_path = Path(key) if edb is None else None

        self._ = _
        self.__ = _.__dict__
        self._edb = edb
        if edb is None:
            self._collection = None
        else:
            if _mongo is None:
                self._collection = edb().mongo()[_key]
            else:
                self._collection = _mongo[_key]

        self._keys = []
        self._key = _key

        self.defaults = defaults

        if self._collection is None:
            if yml is None:
                raise ReadOnlyError(f"You must provide either yml or edb object for {self}")
            else:
                self._reload(yml)

    def __call__(self) -> EndlessCollection:
        """Return the public collection wrapper owned by this logic container."""
        return self._

    def __repr__(self) -> str:
        """Return the debugger-friendly logic representation."""
        if self.emojify or self.debug:
            return f"🧩logic:({self.repr()})"
        return f"Logic({self.repr()})"

    def _reload(self, yml: dict[str, Any] | None) -> None:
        """Refresh a read-only YAML collection from parsed YAML data."""
        if not isinstance(yml, dict):
            raise InvalidValueError(f"YAML collection data for {self} must be a dict")

        for _key in list(self._keys):
            if _key not in yml and _key in self.__:
                del self.__[_key]

        self._keys.clear()
        for _key in yml:
            value = yml[_key]
            self._keys.append(_key)
            if isinstance(value, dict):
                self.__[_key] = self.descendant(_key, value)
            elif isinstance(value, ObjectId):
                self.__[_key] = str(value)
            else:
                self.__[_key] = value

    def descendant(self, key: Any, value: dict[str, Any] | None, virtual: bool = False) -> EndlessDocument:
        """Return a cached child document or create one for a collection item."""
        if self._edb is not None:
            _path = f"{self.path(True)}/{key}"
            documents = self._edb().documents()
            if _path in documents:
                document = documents[_path]
                document()._reload(value)
            else:
                document = EndlessDocument(key, value, self, virtual)
                if not self.debug:
                    documents[_path] = document
            return document

        return EndlessDocument(key, value, self, virtual)

    def len(self) -> int:
        """Return document count for Mongo-backed collections or YAML key count."""
        collection = self.mongo()
        if collection is not None:
            return collection.count_documents({})

        return len(self._keys)

    def key(self) -> Any:
        """Return the collection name."""
        return self._key

    def path(self, full: bool = True) -> str:
        """Return the full database path or the collection-local path."""
        if full:
            if self._edb is None:
                return f"yml/{self._key}"
            return f"{self._edb().key()}/{self._key}"
        else:
            return self._key

    def repr(self, srepr: str | None = None) -> str:
        """Build the compact debugger representation for this collection path."""
        parent = self.parent()
        if not (self.emojify or self.debug):
            if self._edb is None:
                repr = f"YamlCollection({str(self._source_path)!r}, len={self.len()})"
            else:
                flags = []
                if self.protected:
                    flags.append("protected=True")
                if self.strict:
                    flags.append("strict=True")

                flag_text = f", {', '.join(flags)}" if flags else ""
                repr = f"Collection({self._key!r}, len={self.len()}{flag_text})"

            if srepr is not None:
                repr = f"{repr}/{srepr}"

            if parent is None:
                return repr
            return parent().repr(repr)

        repr = ""
        if self.debug:
            repr += "🐞"

        if self._edb is None:
            repr = f"⚓{self.path(True)}"
        else:
            repr += "📚"

            if self.protected:
                repr += "🔒"
            else:
                repr += "🔓"

            repr += f"{self._key}"
            repr += "{" + f"ℓ{self.len()}" + "}"

        if srepr is not None:
            repr += f"/{srepr}"

        if parent is None:
            return repr
        else:
            return parent().repr(repr)

    def keys(self) -> list[Any]:
        """Return document ids for Mongo-backed collections or YAML keys."""
        if self._collection is None:
            return self._keys

        try:
            return self._collection.distinct("_id")
        except Exception:
            keys = []

        return keys

    def _reload_cached_document(self, key: Any) -> None:
        """Reload a cached document wrapper after a MongoDB write."""
        if self._edb is None:
            return

        path = f"{self.path(True)}/{key}"
        documents = self._edb().documents()
        if path in documents:
            documents[path]().reload()

    def set(self, path: str, value: Any, descendant_expected: Any = None) -> None:
        """Set a root document or nested field using MongoDB dotted updates."""
        if self.protected:
            raise ReadOnlyError(f"{self} is protected and read-only")

        if descendant_expected is not None and inspect.isclass(descendant_expected):
            if not isinstance(value, descendant_expected):
                raise TypeExpectationError(f"Value must be instance of {descendant_expected}")

        collection = self.mongo()
        if collection is None:
            raise ReadOnlyError(f"{self} is read-only")
        else:
            _path = path.split(".")
            _id = normalize_document_key(_path[0])

            if len(_path) == 1:
                self.patch(_id, value, descendant_expected)
                return
            else:
                _value = to_storage_value(value)
                _data = {"$set": {".".join(_path[1:]): _value}}

            collection.update_one({"_id": _id}, _data, upsert=True)
            self._reload_cached_document(_id)

    def patch(self, key: Any, value: dict[str, Any], descendant_expected: Any = None) -> None:
        """Patch a root document with MongoDB `$set` semantics."""
        if self.protected:
            raise ReadOnlyError(f"{self} is protected and read-only")

        collection = self.mongo()
        if collection is None:
            raise ReadOnlyError(f"{self} is read-only")

        if descendant_expected is not None and inspect.isclass(descendant_expected):
            if not isinstance(value, descendant_expected):
                raise TypeExpectationError(f"Value must be instance of {descendant_expected}")

        if not isinstance(value, dict):
            raise InvalidValueError(f"You must pass dict value for {self}")

        if not is_valid_value(value):
            raise InvalidValueError("Value must be instance of valid EndlessDB value types")

        key = normalize_document_key(key)
        collection.update_one({"_id": key}, {"$set": to_storage_value(value)}, upsert=True)
        self._reload_cached_document(key)

    def replace(self, key: Any, value: dict[str, Any]) -> None:
        """Replace a root document with MongoDB replacement semantics."""
        if self.protected:
            raise ReadOnlyError(f"{self} is protected and read-only")

        collection = self.mongo()
        if collection is None:
            raise ReadOnlyError(f"{self} is read-only")

        if not isinstance(value, dict):
            raise InvalidValueError(f"You must pass dict value for {self}")

        if not is_valid_value(value):
            raise InvalidValueError("Value must be instance of valid EndlessDB value types")

        key = normalize_document_key(key)
        data = to_storage_value(value).copy()
        data["_id"] = key
        collection.replace_one({"_id": key}, data, upsert=True)
        self._reload_cached_document(key)

    def unset(self, path: str) -> None:
        """Unset a field path below a root document."""
        if self.protected:
            raise ReadOnlyError(f"{self} is protected and read-only")

        collection = self.mongo()
        if collection is None:
            raise ReadOnlyError(f"{self} is read-only")

        parts = path.split(".")
        if len(parts) < 2:
            raise InvalidValueError("Unset path must include a document id and field path")

        key = normalize_document_key(parts[0])
        field_path = ".".join(parts[1:])
        collection.update_one({"_id": key}, {"$unset": {field_path: ""}})
        self._reload_cached_document(key)

    def find(
        self,
        filter: dict[str, Any] | None = None,
        sort: Any = None,
        limit: int | None = None,
        skip: int | None = None,
        projection: Any = None,
        **kwargs: Any,
    ) -> Iterator[EndlessDocument]:
        """Yield documents matching a PyMongo filter and cursor options."""
        query = filter or {}
        effective_projection = {"_id": 1} if projection is None else projection
        cursor = self.mongo().find(query, effective_projection, **kwargs)
        if sort is not None:
            cursor = cursor.sort(sort)
        if skip is not None:
            cursor = cursor.skip(skip)
        if limit is not None:
            cursor = cursor.limit(limit)

        for document in cursor:
            if "_id" not in document:
                raise InvalidValueError("Projection must include _id when returning EndlessDocument wrappers")
            yield self.descendant(document["_id"], None)

    def find_one(
        self,
        filter: dict[str, Any] | None = None,
        sort: Any = None,
        projection: Any = None,
        **kwargs: Any,
    ) -> EndlessDocument | None:
        """Return the first matching document wrapper or `None`."""
        effective_projection = {"_id": 1} if projection is None else projection
        document = self.mongo().find_one(filter or {}, effective_projection, sort=sort, **kwargs)
        if document is not None:
            if "_id" not in document:
                raise InvalidValueError("Projection must include _id when returning EndlessDocument wrappers")
            return self.descendant(document["_id"], None)
        else:
            return None

    def first(self, filter: dict[str, Any] | None = None, **kwargs: Any) -> EndlessDocument | None:
        """Return the first document matching a filter."""
        return self.find_one(filter, **kwargs)

    def count(self, filter: dict[str, Any] | None = None) -> int:
        """Return the number of documents matching a filter."""
        return self.mongo().count_documents(filter or {})

    def exists(self, filter: dict[str, Any] | None = None) -> bool:
        """Return True when at least one document matches a filter."""
        return self.find_one(filter) is not None

    def raw(self) -> pymongo.collection.Collection | None:
        """Return the backing PyMongo collection."""
        return self.mongo()

    def reload(self) -> None:
        """Reload a YAML-backed collection from its source path."""
        if self._edb is None:
            with open(self._source_path, "r") as stream:
                try:
                    yml = yaml.safe_load(stream)
                except yaml.YAMLError as exc:
                    print(f"YAML parsing error:\n{exc}")
                    raise exc
        else:
            raise ReadOnlyError(f"{self} can reload only yml collection")

        self._reload(yml)

    def mongo(self) -> pymongo.collection.Collection | None:
        """Return the backing PyMongo collection, or `None` for YAML data."""
        return self._collection

    def collections(self) -> dict[str, EndlessCollection]:
        """Return the owning database collection cache."""
        return self._parent_logic.collections()

    def parent(self) -> EndlessDatabase | None:
        """Return the owning database wrapper, or `None` for YAML collections."""
        return self.edb()

    def edb(self) -> EndlessDatabase | None:
        """Return the owning database wrapper."""
        return self._edb

    def delete(self) -> None:
        """Drop the MongoDB collection and remove it from the database cache."""
        collections = self._edb().collections()
        if self._key in collections:
            del collections[self._key]

        self._collection.drop()
        self.virtual = True

    def iter_items(self, *args: Any, **kwargs: Any) -> Iterator[tuple[Any, Any]]:
        """Yield serializable key/value pairs for every document in the collection."""
        _self = self._
        keys = self.keys()
        for key in keys:
            data = _self[key]().to_dict(**kwargs)
            yield (key, data)

    def to_dict(self, *args: Any, **kwargs: Any) -> dict[Any, Any]:
        """Return a serializable dictionary for every document in the collection."""
        return dict(self.iter_items(*args, **kwargs))

    def to_json(self, *args: Any, **kwargs: Any) -> str:
        """Serialize the collection to JSON, optionally base64-encoded."""
        if "base64" in kwargs and kwargs["base64"]:
            to_base64 = kwargs.pop("base64")
        else:
            to_base64 = False

        _dict = self.to_dict(**kwargs)
        _json = json.dumps(_dict, default=json_default_encoder, ensure_ascii=False)

        if to_base64:
            return base64.b64encode(_json.encode("utf-8")).decode("utf-8")

        return _json

    def to_yml(self) -> str:
        """Serialize the collection to YAML."""
        _dict = self.to_dict()
        _yaml = yaml.dump(_dict, default_flow_style=False, allow_unicode=True)
        return _yaml

    @staticmethod
    def from_yml(path: str | Path) -> EndlessCollection:
        """Create a read-only collection wrapper from a YAML file."""
        path = Path(path).expanduser()
        with open(path, "r") as stream:
            try:
                yml = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(f"YAML parsing error:\n{exc}")
                raise exc
        return EndlessCollection(path, None, yml)


class DatabaseLogicContainer:
    """Mutable operational state for one `EndlessDatabase` wrapper."""

    _collections: dict[str, EndlessCollection]
    _documents: dict[str, EndlessDocument]

    def __call__(self) -> EndlessDatabase:
        """Return the public database wrapper owned by this logic container."""
        return self._

    def __init__(
        self,
        _: EndlessDatabase,
        url: str | None = None,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        strict: bool = False,
        emojify: bool = False,
    ) -> None:
        """Connect the wrapper to MongoDB and initialize collection caches."""
        self._cfg = EndlessConfiguration()
        self.debug = False
        self.emojify = emojify
        self.protected = False
        self.strict = strict
        self._ = _
        self.__ = _.__dict__
        self._collections = {}
        self._documents = {}
        self._defaults_collection = CollectionLogicContainer.from_yml(self._cfg.CONFIG_YML)
        defaults = self.defaults()

        connection_url = self.resolve_url(url, host, port, user, password, database)
        self._url = self.url_info(connection_url)
        self._key = database or mongodb_database_from_url(connection_url) or self._cfg.MONGO_DATABASE

        self._mongo = pymongo.MongoClient(connection_url, connect=False)
        self._edb = self._mongo[self._key]

        self._collections[self._cfg.CONFIG_COLLECTION] = EndlessCollection(
            self._cfg.CONFIG_COLLECTION, self(), None, defaults, self._edb
        )

    def __repr__(self) -> str:
        """Return the debugger-friendly logic representation."""
        if self.emojify or self.debug:
            return f"🧩logic:({self.repr()})"
        return f"Logic({self.repr()})"

    def repr(self, srepr: str | None = None) -> str:
        """Build the compact debugger representation for this database path."""
        if not (self.emojify or self.debug):
            flags = []
            if self.strict:
                flags.append("strict=True")
            if self.protected:
                flags.append("protected=True")

            flag_text = f", {', '.join(flags)}" if flags else ""
            repr = f"Database({self._key!r}, len={self.len()}{flag_text})"
            if srepr is None:
                return repr
            return f"{repr}/{srepr}"

        repr = ""
        if self.debug:
            repr += "🐞"

        if self._edb is None:
            repr += "📀"
        else:
            repr += "💿"

        repr += f"{self._key}"
        repr += "{" + f"ℓ{self.len()}" + "}"

        if srepr is None:
            return f"{repr}"
        else:
            return f"{repr}/{srepr}"

    def len(self) -> int:
        """Return the number of non-config collections visible in the database."""
        return len(self.keys())

    def key(self) -> str:
        """Return the configured MongoDB database name."""
        return self._key

    def keys(self) -> list[str]:
        """Return MongoDB collection names excluding the config collection."""
        _filter = {"name": {"$regex": r"^(?!^%s$).+$" % self._cfg.CONFIG_COLLECTION}}
        return self.mongo().list_collection_names(filter=_filter)

    def mongo(self) -> pymongo.database.Database:
        """Return the backing PyMongo database."""
        return self._edb

    def parent(self) -> None:
        """Return `None` because the database wrapper is the root object."""
        return None

    def config(self) -> EndlessCollection:
        """Return the configured config collection wrapper."""
        return self._collections[self._cfg.CONFIG_COLLECTION]

    def defaults(self) -> EndlessCollection:
        """Return the read-only defaults collection loaded from YAML."""
        return self._defaults_collection

    def documents(self) -> dict[str, EndlessDocument]:
        """Return the database-wide document cache keyed by full wrapper path."""
        return self._documents

    def collections(self) -> dict[str, EndlessCollection]:
        """Return the database-wide collection cache."""
        return self._collections

    def url_info(self, url: str) -> dict[str, str]:
        """Return the MongoDB URL with a masked password for display/debugging."""
        return {"url": url, "masked": mask_mongodb_url(url)}

    def resolve_url(
        self,
        url: str | None,
        host: str | None,
        port: int | None,
        user: str | None,
        password: str | None,
        database: str | None = None,
    ) -> str:
        """Resolve per-instance connection arguments over configuration defaults."""
        if url:
            return url

        explicit_parts = any(value is not None for value in [host, port, user, password])
        if not explicit_parts:
            return self._cfg.MONGO_URI

        return self.build_url(
            host or self._cfg.MONGO_HOST,
            self._cfg.MONGO_PORT if port is None else port,
            self._cfg.MONGO_USER if user is None else user,
            self._cfg.MONGO_PASSWORD if password is None else password,
            database or self._cfg.MONGO_DATABASE,
        )

    def build_url(
        self,
        host: str,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> str:
        """Build a SCRAM-SHA-256 MongoDB URL from connection parts."""
        credentials = ""
        if user or password:
            credentials = f"{quote(user or '', safe='')}:{quote(password or '', safe='')}@"

        host_part = host
        if ":" in host_part and not host_part.startswith("["):
            host_part = f"[{host_part}]"
        if port is not None:
            host_part = f"{host_part}:{port}"

        path = f"/{database}" if database else "/"
        query = urlencode({"authSource": "admin", "authMechanism": "SCRAM-SHA-256"}) if credentials else ""
        return urlunsplit(("mongodb", f"{credentials}{host_part}", path, query, ""))

    def iter_items(self) -> Iterator[tuple[str, Any]]:
        """Yield serializable key/value pairs for every collection."""
        _self = self._
        keys = self.keys()
        for key in keys:
            data = _self[key]().to_dict()
            yield (key, data)

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable dictionary for every collection."""
        return dict(self.iter_items())

    def to_json(self, *args: Any, **kwargs: Any) -> str:
        """Serialize the database to JSON, optionally base64-encoded."""
        if "base64" in kwargs and kwargs["base64"]:
            to_base64 = kwargs.pop("base64")
        else:
            to_base64 = False

        _dict = self.to_dict()
        _json = json.dumps(_dict, default=json_default_encoder, ensure_ascii=False)

        if to_base64:
            return base64.b64encode(_json.encode("utf-8")).decode("utf-8")

        return _json

    def to_yml(self) -> str:
        """Serialize the database to YAML."""
        _dict = self.to_dict()
        _yaml = yaml.dump(_dict, default_flow_style=False, allow_unicode=True)
        return _yaml

    def load_defaults(self) -> None:
        """Copy YAML defaults into the config collection when configured to rewrite."""
        defaults = self.defaults()
        config = self.config()
        if defaults.config_collection_rewrite:
            for key, value in defaults:
                if isinstance(value, EndlessDocument):
                    _value = value()
                    data = _value.to_dict()
                    config[key] = data


# ---------------------------------------------------------------------------
# Public dynamic wrappers
# ---------------------------------------------------------------------------


class EndlessDocument:
    """Dynamic wrapper for one MongoDB/YAML document.

    Attributes map to document fields. Calling the wrapper returns its
    `DocumentLogicContainer`, unless fluent flags such as `debug=True` are used.
    """

    def __init__(self, key: Any, obj: dict[str, Any] | None, parent_logic: Any, virtual: bool = False) -> None:
        """Create a public document wrapper and attach its logic container."""
        self.__dict__[LOGIC_KEY] = DocumentLogicContainer(self, key, obj, parent_logic, virtual)

    def __call__(self, descendant_expected: Any = None, **kwargs: Any) -> DocumentLogicContainer | EndlessDocument:
        """Return logic, configure fluent flags, or project a typed/default child."""
        _self = self.__dict__[LOGIC_KEY]
        _parent = _self.parent()()
        if _parent.protected:
            _self.protected = True

        if _parent.static:
            _self.static = True

        if _parent.debug:
            _self.debug = True

        if getattr(_parent, "emojify", False):
            _self.emojify = True

        if getattr(_parent, "strict", False):
            _self.strict = True

        ret = False
        if "debug" in kwargs:
            _self.debug = kwargs["debug"] == True
            ret = True

        if "emojify" in kwargs:
            _self.emojify = kwargs["emojify"] == True
            ret = True

        if "protected" in kwargs:
            _self.protected = kwargs["protected"] == True
            ret = True

        if "static" in kwargs:
            _self.static = kwargs["static"] == True
            ret = True

        if "strict" in kwargs:
            _self.strict = kwargs["strict"] == True
            ret = True

        if "exception" in kwargs:
            _self.descendant_exception = kwargs["exception"] == True
            ret = True

        if "create" in kwargs:
            _self.descendant_create = kwargs["create"] == True
            ret = True

        if "rewrite" in kwargs:
            _self.descendant_rewrite = kwargs["rewrite"] == True
            ret = True

        if descendant_expected is not None:
            if isinstance(descendant_expected, dict):
                document = EndlessDocument(_self.key(), descendant_expected, _parent, True)
            else:
                document = EndlessDocument(_self.key(), _self.to_dict(), _parent, True)

            documentl = document()
            if not isinstance(descendant_expected, dict):
                documentl.descendant_expected = descendant_expected
            documentl.descendant_create = _self.descendant_create
            documentl.descendant_rewrite = _self.descendant_rewrite
            documentl.descendant_exception = _self.descendant_exception
            if _parent.debug:
                documentl.debug = True

            if _self.descendant_create or _self.descendant_rewrite:
                _self.collection()().set(_self.path(), descendant_expected)
                documentl._reload(descendant_expected)

            return document

        if ret:
            return self
        else:
            return _self

    def __delete__(self, instance: Any) -> None:
        """Descriptor hook intentionally unused by the dynamic wrapper."""
        pass

    def __del__(self) -> None:
        """Keep destruction side-effect free; Mongo deletes are explicit."""
        pass

    def __len__(self) -> int:
        """Return the number of known fields."""
        return self().len()

    def __str__(self) -> str:
        """Return a compact human-readable document label."""
        _self = self.__dict__[LOGIC_KEY]
        _str = f"{_self.key()}"
        _str += "{" + f"ℓ{_self.len()}" + "}"
        if _self.virtual:
            _str += "*"
        return _str

    def __repr__(self) -> str:
        """Return the debugger-friendly document path representation."""
        _self = self.__dict__[LOGIC_KEY]
        return _self.repr()

    def __getattribute__(self, key: str) -> Any:
        """Enforce strict typed descendant checks for already-loaded fields."""
        if key in {"__class__", "__dict__", LOGIC_KEY} or is_magic_method(key):
            return object.__getattribute__(self, key)

        data = object.__getattribute__(self, "__dict__")
        if key in data and LOGIC_KEY in data:
            logic = data[LOGIC_KEY]
            descendant_expected = logic.descendant_expected
            if logic.descendant_exception and inspect.isclass(descendant_expected):
                value = data[key]
                if not isinstance(value, descendant_expected):
                    if not (descendant_expected is dict and isinstance(value, EndlessDocument)):
                        raise TypeExpectationError(f"Property {key} is not instance of {descendant_expected}")
            return data[key]

        return object.__getattribute__(self, key)

    def __eq__(self, other: Any) -> bool:
        """Compare documents by full path; `None` means a virtual document."""
        _self = self.__dict__[LOGIC_KEY]
        if other is None:
            return _self.virtual
        if isinstance(other, EndlessDocument):
            return _self.path(True) == other().path(True)

        raise UnsupportedComparisonError("This type of comparison is not supported yet")

    def __iter__(self) -> Iterator[tuple[Any, Any]]:
        """Iterate over known field names and values."""
        _self = self.__dict__[LOGIC_KEY]
        for key in _self.keys():
            if key in self.__dict__:
                yield key, self.__dict__[key]
            else:
                path = f"{_self.path(True)}/{key}"
                documents = _self.edb()().documents()
                if path in documents:
                    yield key, documents[path]
                else:
                    raise PropertyNotFoundError(f"Property {key} not found in {self}")

    def __setattr__(self, key: str, value: Any) -> None:
        """Persist a field assignment to MongoDB through the owning collection."""
        if key == "id" or key == "_id":
            raise ReadOnlyError("Id is read-only")

        valid_types = [
            EndlessDocument,
            str,
            int,
            float,
            bool,
            dict,
            list,
            bytes,
            bytearray,
            datetime,
            uuid.UUID,
            type(None),
        ]
        if not type(value) in valid_types:
            raise InvalidValueError(f"Value must be instance of {valid_types}")

        _self = self.__dict__[LOGIC_KEY]
        if _self.protected:
            raise ReadOnlyError(f"{self} is protected and read-only")

        if is_magic_method(key):
            key = "*" + key

        _path = _self.path().replace("/", ".")
        _self.collection()().set(f"{_path}.{key}", value, _self.descendant_expected)

    def __getattr__(self, key: str) -> Any:
        """Resolve a field, id alias, typed descendant, or virtual child document."""
        if key == "id" or key == "_id":
            return self.__dict__[LOGIC_KEY].key()

        _self = self.__dict__[LOGIC_KEY]
        descendant_expected = _self.descendant_expected
        descendant_expected_is_type = inspect.isclass(descendant_expected)
        if descendant_expected_is_type:
            value = descendant_expected()
        else:
            value = descendant_expected

        if value is not None:
            if _self.descendant_create and _self.virtual:
                _self.collection()().set(_self.path(), value, descendant_expected)
                _self._reload(value)

            if _self.descendant_rewrite:
                _self.collection()().set(_self.path(), value, descendant_expected)
                _self._reload(value)
                return value

        if key in self.__dict__:
            if _self.descendant_exception and descendant_expected_is_type:
                if not isinstance(self.__dict__[key], descendant_expected):
                    if not (descendant_expected is dict and isinstance(self.__dict__[key], EndlessDocument)):
                        raise TypeExpectationError(f"Property {key} is not instance of {descendant_expected}")

            return self.__dict__[key]
        elif _self.descendant_exception:
            raise PropertyNotFoundError(f"Property {key} not found in {self}")

        if _self.strict:
            raise PropertyNotFoundError(f"Property {key} not found in {self}")

        return _self.descendant(key, None, True)

    def __getitem__(self, key: Any) -> Any:
        """Resolve a document field by key, supporting dotted nested paths."""
        if isinstance(key, int):
            return self.__getattr__(key)

        if is_magic_method(key):
            key = "*" + key

        path = key.split(".", 1)
        if len(path) > 1:
            return self[path[0]][path[1]]

        return self.__getattr__(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a document field by key, supporting dotted nested paths."""
        if is_magic_method(key):
            key = "*" + key

        path = key.split(".", 1)
        if len(path) > 1:
            self[path[0]][path[1]] = value
            return

        return self.__setattr__(key, value)


class EndlessCollection:
    """Dynamic wrapper for one MongoDB collection or read-only YAML collection."""

    def __init__(
        self,
        key: Any,
        edb: EndlessDatabase | None = None,
        yml: dict[str, Any] | None = None,
        defaults: EndlessCollection | None = None,
        _database: pymongo.database.Database | None = None,
    ) -> None:
        """Create a public collection wrapper and attach its logic container."""
        self.__dict__[LOGIC_KEY] = CollectionLogicContainer(self, edb, key, yml, defaults, _database)

    def __call__(self, *args: Any, **kwargs: Any) -> CollectionLogicContainer | EndlessCollection:
        """Return logic, or configure fluent collection flags."""
        _self = self.__dict__[LOGIC_KEY]

        ret = False
        if "debug" in kwargs:
            _self.debug = kwargs["debug"] == True
            ret = True

        if "emojify" in kwargs:
            _self.emojify = kwargs["emojify"] == True
            ret = True

        if "protected" in kwargs:
            _self.protected = kwargs["protected"] == True
            ret = True

        if "static" in kwargs:
            _self.static = kwargs["static"] == True
            ret = True

        if "strict" in kwargs:
            _self.strict = kwargs["strict"] == True
            ret = True

        if ret:
            return self
        else:
            return _self

    def __eq__(self, other: Any) -> bool | None:
        """Compare collections by full path; `None` means virtual/read-only absence."""
        _self = self.__dict__[LOGIC_KEY]
        if other is None:
            return _self.virtual
        if isinstance(other, EndlessCollection):
            return _self.path(True) == other().path(True)

    def __delete__(self, instance: Any) -> None:
        """Descriptor hook intentionally unused by the dynamic wrapper."""
        pass

    def __len__(self) -> int:
        """Return the collection document count."""
        _self = self.__dict__[LOGIC_KEY]
        return _self.len()

    def __str__(self) -> str:
        """Return a compact human-readable collection label."""
        _self = self.__dict__[LOGIC_KEY]
        _str = f"{_self.key()}"
        _str += "{" + f"ℓ{_self.len()}" + "}"

        return _str

    def __repr__(self) -> str:
        """Return the debugger-friendly collection path representation."""
        _self = self.__dict__[LOGIC_KEY]
        return _self.repr()

    def __iter__(self) -> Iterator[tuple[Any, EndlessDocument]]:
        """Iterate over document ids and document wrappers."""
        _self = self.__dict__[LOGIC_KEY]
        for key in _self.keys():
            yield key, self.__getattr__(key)

    def __getattr__(self, key: Any) -> Any:
        """Resolve an existing, defaulted, or virtual document by id."""
        _self = self.__dict__[LOGIC_KEY]
        collection = _self.mongo()
        if key in self.__dict__:
            if collection is None or key not in _self.keys():
                return self.__dict__[key]

        if collection is None:
            if _self.strict:
                raise PropertyNotFoundError(f"Document {key} not found in {self}")
            return None
        else:
            _path = f"{_self.path(True)}/{key}"
            documents = _self._edb().documents()
            if _path in documents:
                document = documents[_path]
                document().reload()
                return document

            _obj = collection.find_one({"_id": key})
            defaults = _self.defaults
            if _obj is None and defaults is not None:
                default_value = _self.defaults[key]
                if default_value is not None:
                    if isinstance(default_value, EndlessDocument):
                        _path = default_value().path()
                        _data = default_value().to_dict()
                        _self.set(_path, _data)
                        _obj = collection.find_one({"_id": key})
                    else:
                        _self.set(_path, default_value)
                        return default_value

            if _obj is None:
                if _self.strict:
                    raise PropertyNotFoundError(f"Document {key} not found in {self}")
                document = _self.descendant(key, None, True)
            else:
                document = _self.descendant(key, _obj)

            documents[_path] = document
            return document

    def __setattr__(self, key: Any, value: Any) -> None:
        """Create or replace a root document in the collection."""
        _self = self.__dict__[LOGIC_KEY]
        if is_magic_method(key):
            key = "*" + key

        collection = _self.mongo()
        if collection is None:
            raise ReadOnlyError(f"{self} is read-only")

        _self.patch(key, value)

    def __getitem__(self, key: Any) -> Any:
        """Resolve a document or nested document path by item access."""
        if key is None:
            return None

        _self = self.__dict__[LOGIC_KEY]
        if is_magic_method(key):
            key = "*" + key

        key = normalize_document_key(key)

        if isinstance(key, int):
            return self.__getattr__(key)

        path = key.replace("/", ".").split(".", 1)
        if len(path) > 1:
            next_path = path[0]
            next_path = normalize_document_key(next_path)
            return self[next_path][path[1]]

        return self.__getattr__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        """Set a root document or nested document path by item access."""
        if is_magic_method(key):
            key = "*" + key

        key = normalize_document_key(key)
        if isinstance(key, int):
            return self.__setattr__(key, value)

        path = key.split(".", 1)
        if len(path) > 1:
            next_path = path[0]
            next_path = normalize_document_key(next_path)
            self[next_path][path[1]] = value
            return

        return self.__setattr__(key, value)


class EndlessDatabase:
    """Dynamic root wrapper for a MongoDB database."""

    def __init__(
        self,
        url: str | None = None,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        strict: bool = False,
        emojify: bool = False,
    ) -> None:
        """Create a public database wrapper and attach its logic container."""
        self.__dict__[LOGIC_KEY] = DatabaseLogicContainer(
            self, url, host, port, user, password, database, strict, emojify
        )

    def __call__(self, *args: Any, **kwargs: Any) -> DatabaseLogicContainer | EndlessDatabase:
        """Return logic, or configure fluent database flags."""
        _self = self.__dict__[LOGIC_KEY]

        ret = False
        if "debug" in kwargs:
            _self.debug = kwargs["debug"] == True
            ret = True

        if "emojify" in kwargs:
            _self.emojify = kwargs["emojify"] == True
            ret = True

        if "protected" in kwargs:
            _self.protected = kwargs["protected"] == True
            ret = True

        if "strict" in kwargs:
            _self.strict = kwargs["strict"] == True
            ret = True

        if ret:
            return self
        else:
            return _self

    def __delete__(self, instance: Any) -> None:
        """Descriptor hook intentionally unused by the dynamic wrapper."""
        pass

    def __len__(self) -> int:
        """Return the number of non-config collections."""
        _self = self.__dict__[LOGIC_KEY]
        return _self.len()

    def __str__(self) -> str:
        """Return a compact human-readable database label."""
        _self = self.__dict__[LOGIC_KEY]
        _str = f"{_self.key()}"
        _str += "{" + f"ℓ{_self.len()}" + "}"
        return _str

    def __repr__(self) -> str:
        """Return the debugger-friendly database representation."""
        _self = self.__dict__[LOGIC_KEY]
        return _self.repr()

    def __getattr__(self, key: Any) -> EndlessCollection:
        """Resolve an existing or virtual collection by name/path."""
        _self = self.__dict__[LOGIC_KEY]
        if key in self.__dict__:
            return self.__dict__[key]

        key = normalize_document_key(key)
        if isinstance(key, int):
            raise InvalidValueError("There is no numeric keys in edb")

        path = key.split("/", 1)
        if len(path) > 1:
            next_path = path[0]
            next_path = normalize_document_key(next_path)
            if isinstance(key, int):
                raise InvalidValueError("There is no numeric keys in edb")

            return self[next_path][path[1]]

        collections = _self.collections()
        if not _self.debug and key in collections:
            return collections[key]

        if _self.strict and key not in _self.keys():
            raise PropertyNotFoundError(f"Collection {key} not found in {self}")

        collection = EndlessCollection(key, self)
        if not _self.debug:
            collections[key] = collection

        return collection

    def __setattr__(self, key: Any, value: Any) -> None:
        """Route nested writes to collections; direct root writes are read-only."""
        key = normalize_document_key(key)
        if isinstance(key, int):
            raise InvalidValueError("There is no numeric keys in edb")

        path = key.split("/", 1)
        if len(path) > 1:
            next_path = path[0]
            next_path = normalize_document_key(next_path)
            if isinstance(key, int):
                raise InvalidValueError("There is no numeric keys in edb")

            self[next_path][path[1]] = value
            return

        raise ReadOnlyError("This is edb root and it is read-only")

    def __setitem__(self, key: Any, value: Any) -> None:
        """Set a nested collection/document path by item access."""
        self.__setattr__(key, value)

    def __getitem__(self, key: Any) -> EndlessCollection:
        """Resolve a collection or nested path by item access."""
        return self.__getattr__(key)

    def __iter__(self) -> Iterator[tuple[str, EndlessCollection]]:
        """Iterate over collection names and collection wrappers."""
        _self = self.__dict__[LOGIC_KEY]
        for key in _self.keys():
            yield key, self.__getattr__(key)
