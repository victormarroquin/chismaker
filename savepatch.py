"""Parche de guardado: convierte juegos con guardado SRAM/EEPROM a Flash 512Kbit.

Necesario para cartuchos cuya memoria de guardado es un chip Flash (por ejemplo
ChisFlash "1M Flash"/Celebi) y que por tanto no pueden guardar juegos de SRAM.

Es un port a Python de gba-flash-patcher (https://github.com/metroid-maniac/gba-flash-patcher),
de Metroid Maniac, con licencia MIT. El payload ARM incluido (PAYLOAD_B64) se compiló
a partir de su payload.c con arm-none-eabi-gcc.

MIT License
Copyright (c) 2023 Metroid Maniac
Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
to whom the Software is furnished to do so, subject to the following conditions: The above
copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
"""
import base64
import struct

MAX_ROM = 0x02000000
ALIGN = 0x40000

PAYLOAD_B64 = """
zwEAABcCAADhAQAARQIAAPcBAABzAgAAAAAAAHtGCDsbaBhocEcwtaohVSSAJQpLCkoZcBRwHXAZ
cBRwJTwEcMBGBHj/LPzRGXBVIRFw8CIacDC8AbwAR1VVAA6qKgAOMLWqJFUlCUsJShxwFXBLNR1w
AXDARgV4jUL80VUhHHARcPAiGnAwvAG8AEdVVQAOqioADvC1nEYEAAAgBZ4ALgLR8LwCvAhHF3gl
eO0bax6dQSdwQBlkGGJEAT7v5wMA4CCLQAAFGENwR/C1gCRkARxBibACr3phakb7YOMd2wjbANMa
nUYCqzhgOWG7YHtpACsE0b1GB7DwvAG8AEc6aWMePmmaQx5AEwD6aJNA4CJ9aRIFGkNzGXpgo0IA
2aUbASMAlPpoASGTQLhoemj/97H/u2iYGQEjAJUZADpo//ep/wAoCdE7aFsZO2A7aVsZO2F7aVsb
e2HJ53ho//dj/wAmtELv0DAAu2iZXftomEB7aBgY//d0/wE28ufTtRcAASKaQJRGCgDgJJpAJAUA
l2NGASEiQ//3ff/TvAG8AEdwteAlihhAGi0FkUIC0QEgQEIH4AwAnEAsQ0ZcJHimQgPQCABwvAK8
CEcBMe3nELVJBAEjSQz/93j/ELwBvABHELUMAEEEASMgAEkM//fG/xC8AbwAR0kEASMQtUkM//fP
/wIAACCCQgLb4CAABRBDELwCvAhHcLUEAA0A//f+/gEjACgK0IKIAjNAKgDRBDMIIigA4QD/90j/
ACMYAHC8ArwIR3C1BAANAP/35/4BIwAoCtCCiAIzQCoA0QQzCCIoAOEA//eK/wAjGABwvAK8CEdw
tQQADQD/99D+AwABIAArC9CaiAMjQCoA0QQzCCIoAOEA//eE/8BDwA9wvAK8CEfARg==
"""
PAYLOAD = base64.b64decode("".join(PAYLOAD_B64.split()))

# Índices (en palabras de 32 bits) de la tabla de offsets al inicio del payload
WRITE_SRAM, WRITE_EEPROM, READ_SRAM, READ_EEPROM, VERIFY_SRAM, VERIFY_EEPROM, EEPROM_META = range(7)

THUMB_THUNK = bytes([0x00, 0x4B, 0x18, 0x47])                       # ldr r3,[pc]; bx r3
ARM_THUNK = bytes([0x00, 0x30, 0x9F, 0xE5, 0x13, 0xFF, 0x2F, 0xE1])  # ldr r3,[pc]; bx r3

# (nombre, firma, thunk, palabra donde va la dirección, entrada de la tabla del payload)
SIGNATURES = [
    ("WriteSram", bytes([0x30, 0xB5, 0x05, 0x1C, 0x0C, 0x1C, 0x13, 0x1C, 0x0B, 0x4A, 0x10, 0x88, 0x0B, 0x49, 0x08, 0x40]), THUMB_THUNK, 1, WRITE_SRAM),
    ("WriteSram2", bytes([0x80, 0xB5, 0x83, 0xB0, 0x6F, 0x46, 0x38, 0x60, 0x79, 0x60, 0xBA, 0x60, 0x09, 0x48, 0x09, 0x49]), THUMB_THUNK, 1, WRITE_SRAM),
    ("WriteSramFast", bytes([0x04, 0xC0, 0x90, 0xE4, 0x01, 0xC0, 0xC1, 0xE4, 0x2C, 0xC4, 0xA0, 0xE1, 0x01, 0xC0, 0xC1, 0xE4]), ARM_THUNK, 2, WRITE_SRAM),
    ("ReadSram", bytes([0x70, 0xB5, 0xA0, 0xB0, 0x04, 0x1C, 0x0D, 0x1C, 0x16, 0x1C, 0x08, 0x4A, 0x10, 0x88, 0x08, 0x49]), THUMB_THUNK, 1, READ_SRAM),
    ("VerifySram", bytes([0x70, 0xB5, 0xB0, 0xB0, 0x04, 0x1C, 0x0D, 0x1C, 0x16, 0x1C, 0x08, 0x4A, 0x10, 0x88, 0x08, 0x49]), THUMB_THUNK, 1, VERIFY_SRAM),
    ("ProgramEepromDword", bytes([0x70, 0xB5, 0x00, 0x04, 0x0A, 0x1C, 0x40, 0x0B, 0xE0, 0x21, 0x09, 0x05, 0x41, 0x18, 0x07, 0x31, 0x00, 0x23, 0x10, 0x78]), THUMB_THUNK, 1, WRITE_EEPROM),
    ("ReadEepromDword", bytes([0x70, 0xB5, 0x00, 0x04, 0x0A, 0x1C, 0x40, 0x0B, 0xE0, 0x21, 0x09, 0x05, 0x41, 0x18, 0x07, 0x31]), THUMB_THUNK, 1, READ_EEPROM),
    ("VerifyEepromDword", bytes([0x30, 0xB5, 0x82, 0xB0, 0x0C, 0x1C, 0x00, 0x04, 0x01, 0x0C, 0x00, 0x25, 0x03, 0x48, 0x00, 0x68]), THUMB_THUNK, 1, VERIFY_EEPROM),
]
IDENTIFY_EEPROM = bytes([0x00, 0x04, 0x00, 0x0C, 0x00, 0x22, 0x04, 0x28, 0x08, 0xD1, 0x02, 0x49, 0x02, 0x48, 0x08, 0x60])

SAVE_MARKERS = [
    (b"SRAM_F_V", "SRAM"), (b"SRAM_V", "SRAM"),
    (b"FLASH1M_V", "FLASH1M"), (b"FLASH512_V", "FLASH512"), (b"FLASH_V", "FLASH"),
    (b"EEPROM_V", "EEPROM"),
]


class PatchError(Exception):
    pass


def detect_save_type(rom: bytes) -> str:
    """Devuelve 'SRAM', 'EEPROM', 'FLASH', 'FLASH512', 'FLASH1M' o 'NONE' según las cadenas de la librería de guardado."""
    for marker, name in SAVE_MARKERS:
        if marker in rom:
            return name
    return "NONE"


def is_patched(rom: bytes) -> bool:
    """True si la ROM ya contiene el payload de este parche (la palabra EEPROM_META puede variar)."""
    return PAYLOAD[:EEPROM_META * 4] in rom and PAYLOAD[(EEPROM_META + 1) * 4:] in rom


def needs_flash_patch(save_type: str) -> bool:
    return save_type in ("SRAM", "EEPROM")


def patch_rom(data: bytes):
    """Parchea la ROM. Devuelve (rom_parcheada, nº_de_funciones_enganchadas). Lanza PatchError si no se puede."""
    hooks = 0
    if len(data) > MAX_ROM:
        raise PatchError("ROM过大(不像GBA ROM)")
    romsize = len(data)
    if romsize & (ALIGN - 1):
        romsize = (romsize & ~(ALIGN - 1)) + ALIGN
    rom = bytearray(b"\xff" * MAX_ROM)
    rom[:len(data)] = data

    plen = len(PAYLOAD)
    # Buscar un hueco (todo 0x00 o todo 0xFF) donde instalar el payload, desde el final
    payload_base = romsize - plen
    while payload_base >= 0:
        chunk = rom[payload_base:payload_base + plen]
        if chunk.count(0) == plen or chunk.count(0xFF) == plen:
            break
        payload_base -= 4
    if payload_base < 0:
        if romsize + plen > MAX_ROM:
            raise PatchError("ROM已是最大尺寸，无法安装补丁载荷")
        romsize += plen
        payload_base = romsize - plen
    rom[payload_base:payload_base + plen] = PAYLOAD

    def u32(off):
        return struct.unpack_from("<I", rom, off)[0]

    # Candidatos: posiciones pares donde empieza alguna firma (búsqueda rápida con find)
    limit = romsize - 64
    candidates = set()
    for sig in [x[1] for x in SIGNATURES] + [IDENTIFY_EEPROM]:
        pos = rom.find(sig, 0, romsize)
        while pos != -1:
            if pos % 2 == 0 and pos < limit:
                candidates.add(pos)
            pos = rom.find(sig, pos + 1, romsize)

    found = False
    for loc in sorted(candidates):          # mismo orden y semántica que el parcheador original
        for name, sig, thunk, word, entry in SIGNATURES:
            if rom[loc:loc + len(sig)] == sig:
                found = True
                rom[loc:loc + len(thunk)] = thunk
                target = 0x08000000 + payload_base + struct.unpack_from("<I", PAYLOAD, entry * 4)[0]
                struct.pack_into("<I", rom, loc + word * 4, target)
                hooks += 1
        if rom[loc:loc + len(IDENTIFY_EEPROM)] == IDENTIFY_EEPROM:
            found = True
            info = u32(loc + 5 * 4)
            struct.pack_into("<I", rom, payload_base + EEPROM_META * 4, info)
            hooks += 1
    if not found:
        raise PatchError("未找到可挂钩的存档函数(可能已打过补丁或游戏无存档)")
    return bytes(rom[:romsize]), hooks
