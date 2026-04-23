"""Apache Arrow IPC Stream (RecordBatchStream) — konsistent zu shared_py SharedMemory/IPC-Stil."""

from __future__ import annotations

import pyarrow as pa
from pyarrow import ipc


def encode_table_ipc_stream(table: pa.Table) -> bytes:
    """Serialisiert eine Tabelle als Arrow IPC *Stream* (mehrere Chunks moeglich)."""
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return sink.getvalue().to_pybytes()


def decode_table_ipc_stream(blob: bytes) -> pa.Table:
    reader = ipc.open_stream(pa.BufferReader(blob))
    return reader.read_all()
