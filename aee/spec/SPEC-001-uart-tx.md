# AEE SPEC-001: UART Transmitter
# æ:// Agentic Electronic Engineering — First Hardware Design
# Author: Yæl Méndez
# Date: 2026-10-08
# Target: iCE40 HX8K (Lattice)
# Toolchain: Icarus Verilog → Yosys → nextpnr-ice40

## 1. Overview

A synchronous UART transmitter with configurable baud rate, 8N1 format,
and FIFO buffering. Designed for inter-node communication in the sovereign mesh.

## 2. Interface

### 2.1 Clock and Reset
- `clk` — system clock (50 MHz target)
- `rst_n` — active-low asynchronous reset

### 2.2 TX Data Interface
- `tx_data[7:0]` — byte to transmit
- `tx_valid` — data valid (pulse for 1 clock)
- `tx_ready` — FIFO not full (backpressure)

### 2.3 Serial Output
- `tx` — UART TX line (idle high)

### 2.4 Configuration
- `baud_div[15:0]` — baud rate divider (clk_freq / baud_rate)

## 3. Protocol

### 3.1 Frame Format (8N1)
```
[Start=0][D0][D1][D2][D3][D4][D5][D6][D7][Stop=1]
```

### 3.2 Baud Rate
- Default: 115200 baud
- Divider: 50_000_000 / 115200 = 434
- Configurable at runtime via `baud_div`

### 3.3 FIFO
- Depth: 16 bytes
- Width: 8 bits
- Almost-full threshold: 14 bytes

## 4. Timing

### 4.1 Bit Period
- Each bit lasts `baud_div` clock cycles
- Bit sampling at center of bit period

### 4.2 Throughput
- Max: 1 byte per 10 bit periods = 10 × baud_div clocks
- At 115200 baud, 50 MHz clock: ~4340 clocks/byte ≈ 11.5 KB/s

## 5. Verification

### 5.1 Testbench
- Transmit 0x55 (01010101) — alternating pattern
- Transmit 0x00 — all zeros
- Transmit 0xFF — all ones
- Verify start bit, data bits LSB first, stop bit

### 5.2 Synthesis Target
- Device: iCE40 HX8K (CT256)
- Max frequency: > 50 MHz
- LUT utilization: < 100

## 6. Receipt

```
SPEC-001 → SHA256 → genesis chain
```

**Genesis block:** `ae://receipt/genesis-aee-20261007`
**SPEC hash:** computed at commit time
