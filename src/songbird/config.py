from pydantic import BaseModel, Field, RootModel
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource


class _DomainMapping(BaseModel):
    swap: str | None = None
    follow: bool | None = None
    clean: bool | None = None
    clean_exceptions: list[str] | None = None
    chat: bool | None = None


class BotSettings(BaseModel):
    command_prefix: str = "/"
    status: str = "online"
    activity: str = "Hello World"
    owner_id: int | None = None
    feedback_channel_id: int | None = None
    debug_guild_id: int | None = Field(default=None, validation_alias="DEBUG_GUILD_ID")


class DatabaseSettings(BaseModel):
    url: str


class LLMSettings(BaseModel):
    model: str = "gemini-2.5-flash"
    message_count: int = 30
    system_prompt_path: str = "prompts/default.xml"
    summary_system_prompt: str = "Briefly summarize the given text concisely, capturing the main points and key details. Do not add any personal opinions or additional information. Keep the summary clear and to the point."
    quickchat_system_prompt: str = "Your purpose is to provide precise and factual answers using your advanced data analysis capabilities. For this interaction, you have access to Google Search and URL lookups. Provide concise, direct answers, maintaining your characteristic dry wit and technical professionalism. When providing measurements, use metric units (e.g. kg, meter, celsius, etc.). Keep the answer concise and to the point, under 2000 characters Be brief."
    api_key: str


class WolframSettings(BaseModel):
    api_key: str


class LinksSettings(RootModel[dict[str, _DomainMapping]]):
    pass


class Settings(BaseSettings):
    """Main application settings."""

    discord_token: str = Field(validation_alias="DISCORD_TOKEN")
    log_level: str = "INFO"

    bot: BotSettings
    db: DatabaseSettings
    llm: LLMSettings
    wolfram: WolframSettings
    links: LinksSettings

    model_config = SettingsConfigDict(
        extra="ignore",
        toml_file="config.toml",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            TomlConfigSettingsSource(settings_cls),
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


def load_config() -> Settings:
    return Settings()  # type: ignore[call-arg]
