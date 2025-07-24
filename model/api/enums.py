from enum import StrEnum


class CollectionPermissionEnum(StrEnum):
    VIEW = "VIEW"
    EDIT = "EDIT"
    DELETE = "DELETE"
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_RESOURCES = "MANAGE_RESOURCES"


class ResourcePermissionEnum(StrEnum):
    VIEW = "VIEW"
    READ_CONTENTS = "READ_CONTENTS"
    DELETE = "DELETE"
