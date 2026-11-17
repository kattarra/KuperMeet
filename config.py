import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _parse_ids(raw: str) -> set[int]:
    result: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if item:
            try:
                result.add(int(item))
            except ValueError as exc:
                raise ValueError(f"Invalid Telegram user ID in ADMIN_IDS: {item}") from exc
    return result


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: set[int] = _parse_ids(os.getenv("ADMIN_IDS", ""))
    enable_teen_segment: bool = os.getenv("ENABLE_TEEN_SEGMENT", "false").lower() == "true"
    teen_age_verification_enabled: bool = (
        os.getenv("TEEN_AGE_VERIFICATION_ENABLED", "false").lower() == "true"
    )
    channels: tuple[str, ...] = (
        os.getenv("CHANNEL_KUPERCOIN", ""),
        os.getenv("CHANNEL_LUXDECOR", ""),
        os.getenv("CHANNEL_KUPERSHOP", ""),
        os.getenv("CHANNEL_4", ""),
        os.getenv("CHANNEL_5", ""),
    )
    report_channel: str = os.getenv("REPORT_CHANNEL", "")
    moderation_channel: str = os.getenv("MOD_CHANNEL", "")

    @property
    def teen_segment_is_live(self) -> bool:
        # Both switches must be enabled; a self-declared age is not verification.
        return self.enable_teen_segment and self.teen_age_verification_enabled


settings = Settings()
