"""Server-owned Genie identities; never fall back to an admin identity for a shop."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.config import get_settings


class GenieIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    client_id: str = Field(min_length=1)
    client_secret: SecretStr


class GenieConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = Field(
        pattern=r"^https://[a-zA-Z0-9.-]+\.(cloud\.databricks\.com|azuredatabricks\.net)$"
    )
    e4_passed: bool
    shared_shop_space_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    admin: GenieIdentity
    shops: dict[str, GenieIdentity]

    @model_validator(mode="after")
    def validate_isolation(self):
        if not self.e4_passed:
            raise ValueError("E4 must pass before enabling Genie")
        if any(not key.isdigit() or int(key) <= 0 or str(int(key)) != key for key in self.shops):
            raise ValueError("Shop IDs must be positive canonical integers")
        identities = [self.admin, *self.shops.values()]
        if len({i.client_id for i in identities}) != len(identities):
            raise ValueError("Each scope must have a distinct identity")
        if self.shared_shop_space_id:
            if self.admin.space_id == self.shared_shop_space_id or any(
                i.space_id != self.shared_shop_space_id for i in self.shops.values()
            ):
                raise ValueError("Shared shop space must be separate from admin")
        elif len({i.space_id for i in identities}) != len(identities):
            raise ValueError("Legacy spaces must be distinct")
        if any(not i.client_secret.get_secret_value().strip() for i in identities):
            raise ValueError("OAuth secrets are required")
        return self


def load_genie_config() -> GenieConfig | None:
    path = get_settings().genie_config_path
    if not path:
        return None
    try:
        return GenieConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Validation errors can include secret input. Do not log them or return them to clients.
        return None
