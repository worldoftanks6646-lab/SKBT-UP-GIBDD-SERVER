import asyncio

from app.core.database import AsyncSessionLocal
from app.services.ban_expiry_service import BanExpiryService


async def main() -> None:
    async with AsyncSessionLocal() as db:
        processed = await BanExpiryService.process(db)
        print(f"expired_bans_processed={processed}")


if __name__ == "__main__":
    asyncio.run(main())
