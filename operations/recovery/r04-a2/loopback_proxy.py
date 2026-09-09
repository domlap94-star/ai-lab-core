"""Fixed-target TCP bridge for the isolated R04-A2 localhost smoke."""

import asyncio


async def _copy(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while chunk := await reader.read(64 * 1024):
            writer.write(chunk)
            await writer.drain()
    finally:
        writer.close()


async def _forward(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
) -> None:
    backend_reader, backend_writer = await asyncio.open_connection("backend", 8000)
    await asyncio.gather(
        _copy(client_reader, backend_writer),
        _copy(backend_reader, client_writer),
    )


async def _main() -> None:
    server = await asyncio.start_server(_forward, "0.0.0.0", 18004)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_main())
