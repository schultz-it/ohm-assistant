"""Minimal read-only Modbus TCP client (function codes 3 and 4).

Ohm Assistant never writes to the field bus — it only reads registers — so
instead of pulling in a full protocol stack we speak the handful of bytes a
read request needs: the 7-byte MBAP header followed by the PDU.

    MBAP: transaction id (2) | protocol id (2) = 0 | length (2) | unit id (1)
    PDU : function code (1)  | start address (2) | quantity (2)

One request in flight at a time, one connection per polling cycle (used as an
async context manager), so there are no stale sockets between polls.
"""
import asyncio
import struct

READ_HOLDING = 0x03
READ_INPUT = 0x04

INPUT_TYPES = {"holding": READ_HOLDING, "input": READ_INPUT}

# Modbus exception codes worth naming in a UI message.
_EXCEPTIONS = {
    0x01: "funzione non supportata",
    0x02: "indirizzo registro non valido",
    0x03: "valore non valido",
    0x04: "errore interno dello slave",
    0x06: "slave occupato",
    0x0B: "gateway: nessuna risposta dal dispositivo",
}

MAX_REGISTERS = 125  # Modbus caps a single FC3/FC4 read at 125 registers.


class ModbusError(Exception):
    """Any protocol-, transport- or device-level failure while reading."""


class ModbusTcpClient:
    """Read-only Modbus TCP connection.

    Usage::

        async with ModbusTcpClient("192.168.1.25") as client:
            regs = await client.read(1205, 5)
    """

    def __init__(self, host: str, port: int = 502, unit: int = 1,
                 timeout: float = 5.0) -> None:
        self.host = host
        self.port = int(port)
        self.unit = int(unit)
        self.timeout = float(timeout)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._tid = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "ModbusTcpClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def connect(self) -> None:
        if not self.host:
            raise ModbusError("host non configurato")
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout)
        except asyncio.TimeoutError as exc:
            raise ModbusError(
                f"timeout di connessione a {self.host}:{self.port}") from exc
        except OSError as exc:
            raise ModbusError(
                f"connessione a {self.host}:{self.port} fallita: {exc}") from exc

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = self._writer = None

    async def read(self, address: int, count: int = 1,
                   input_type: str = "holding") -> list[int]:
        """Read `count` 16-bit registers starting at `address` (raw words)."""
        if self._reader is None or self._writer is None:
            raise ModbusError("client non connesso")
        if not 1 <= count <= MAX_REGISTERS:
            raise ModbusError(f"quantità di registri non valida: {count}")
        fc = INPUT_TYPES.get(input_type)
        if fc is None:
            raise ModbusError(f"tipo di registro sconosciuto: {input_type}")

        async with self._lock:
            self._tid = (self._tid + 1) % 0x10000
            tid = self._tid
            pdu = struct.pack(">BHH", fc, address, count)
            frame = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit) + pdu
            try:
                self._writer.write(frame)
                await self._writer.drain()
                header = await asyncio.wait_for(
                    self._reader.readexactly(7), self.timeout)
                r_tid, proto, length, _unit = struct.unpack(">HHHB", header)
                if proto != 0:
                    raise ModbusError(f"protocol id inatteso: {proto}")
                if length < 2:
                    raise ModbusError("risposta troppo corta")
                body = await asyncio.wait_for(
                    self._reader.readexactly(length - 1), self.timeout)
            except asyncio.TimeoutError as exc:
                raise ModbusError("timeout di lettura") from exc
            except (asyncio.IncompleteReadError, OSError) as exc:
                raise ModbusError(f"connessione interrotta: {exc}") from exc

        if r_tid != tid:
            raise ModbusError("risposta fuori sequenza")
        r_fc = body[0]
        if r_fc & 0x80:
            code = body[1] if len(body) > 1 else 0
            raise ModbusError(
                f"eccezione Modbus {code}: {_EXCEPTIONS.get(code, 'sconosciuta')}")
        if r_fc != fc:
            raise ModbusError(f"function code inatteso: {r_fc}")
        byte_count = body[1]
        data = body[2:2 + byte_count]
        if len(data) != count * 2:
            raise ModbusError("lunghezza dei dati inattesa")
        return [x for (x,) in struct.iter_unpack(">H", data)]


def to_int16(word: int) -> int:
    """Interpret a raw register word as a signed 16-bit integer."""
    return word - 0x10000 if word >= 0x8000 else word
