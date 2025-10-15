from enum import Enum


class Capability(str, Enum):
    ANALYTICS = "cap:analytics"
    MONITORING = "cap:monitoring"
    OPS = "cap:ops"
    INGESTION = "cap:ingestion"
    TRANSFORM = "cap:transform"
    EXPORT = "cap:export"
    NOTIFY = "cap:notify"


class PiiRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HipaaFlag(str, Enum):
    NONE = "none"
    POSSIBLE = "possible"
    LIKELY = "likely"


class GdprFlag(str, Enum):
    NONE = "none"
    DATA_SUBJECT = "data-subject"
    EXPORT = "export"
    ERASURE = "erasure"


class Region(str, Enum):
    EU = "eu"
    US = "us"
    APAC = "apac"
    GLOBAL = "global"
