from pydantic import BaseModel, Field

from orion.api.server.config_manager.config_enums import CONFIG_LIMITS


class SystemConfigUpdateRequest(BaseModel):
    outgoing_attachment_max_size_mb: int = Field(ge=CONFIG_LIMITS.OUTGOING_ATTACHMENT_MAX_SIZE_MB_MIN, le=CONFIG_LIMITS.OUTGOING_ATTACHMENT_MAX_SIZE_MB_MAX)
    incoming_attachment_max_size_mb: int = Field(ge=CONFIG_LIMITS.INCOMING_ATTACHMENT_MAX_SIZE_MB_MIN, le=CONFIG_LIMITS.INCOMING_ATTACHMENT_MAX_SIZE_MB_MAX)
    attachment_retention_hours: int = Field(ge=CONFIG_LIMITS.ATTACHMENT_RETENTION_HOURS_MIN, le=CONFIG_LIMITS.ATTACHMENT_RETENTION_HOURS_MAX)
