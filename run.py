import asyncpg, os, asyncio

async def test():
    conn = await asyncpg.connect(os.getenv("DB_AMBIENTAL_URL"))
    print(await conn.fetch("SELECT NOW()"))
    await conn.close()

asyncio.run(test())
