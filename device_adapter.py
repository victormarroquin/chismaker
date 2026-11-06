"""
Adaptador de dispositivo SuperChis - versión segura para hilos
Cada instancia de dispositivo gestiona su propia conexión serial
"""

import struct
import serial
import time
import serial.tools.list_ports


# Constantes de configuración de SuperChis
MAGIC_ADDRESS = 0x01FFFFFE  # Dirección mágica de desbloqueo
MAGIC_VALUE = 0xA55A        # Valor mágico de desbloqueo

# Constantes de metadatos de Flash
ROM_OFF_FLASHMETA = 0x00200000
FLASH_METADATA_SIZE = 0x00200000

class SuperChisDevice:
    """Clase de dispositivo SuperChis - segura para hilos"""
    
    def __init__(self, serial_port):
        """
        Inicializar dispositivo
        Args:
            serial_port: objeto serial.Serial
        """
        self.ser = serial_port
    
    def writeRom(self, addr_word, dat):
        """Escribir datos en una dirección ROM"""
        if isinstance(dat, int):
            dat = struct.pack("<H", dat)
        
        cmd = []
        cmd.extend(struct.pack("<H", 2 + 1 + 4 + len(dat) + 2))
        cmd.append(0xf5)
        cmd.extend(struct.pack("<I", addr_word))
        cmd.extend(dat)
        cmd.extend([0, 0])
        
        self.ser.write(cmd)
        ack = self.ser.read(1)
        return ack
    
    def readRom(self, addr_word, length_byte):
        """Leer datos de una dirección ROM"""
        cmd = []
        cmd.extend(struct.pack("<H", 2 + 1 + 4 + 2 + 2))
        cmd.append(0xf6)
        cmd.extend(struct.pack("<I", addr_word << 1))
        cmd.extend(struct.pack("<H", length_byte))
        cmd.extend([0, 0])
        
        self.ser.write(cmd)
        respon = self.ser.read(length_byte + 2)
        return respon[2:]
    
    def writeRam(self, addr, dat):
        """Escribir datos en una dirección RAM"""
        if isinstance(dat, int):
            dat = struct.pack("B", dat)
        
        cmd = []
        cmd.extend(struct.pack("<H", 2 + 1 + 4 + len(dat) + 2))
        cmd.append(0xf7)
        cmd.extend(struct.pack("<I", addr))
        cmd.extend(dat)
        cmd.extend([0, 0])
        
        self.ser.write(cmd)
        ack = self.ser.read(1)
        return ack
    
    def readRam(self, addr, length_byte):
        """Leer datos de una dirección RAM"""
        cmd = []
        cmd.extend(struct.pack("<H", 2 + 1 + 4 + 2 + 2))
        cmd.append(0xf8)
        cmd.extend(struct.pack("<I", addr))
        cmd.extend(struct.pack("<H", length_byte))
        cmd.extend([0, 0])
        
        self.ser.write(cmd)
        respon = self.ser.read(length_byte + 2)
        return respon[2:]
    
    def set_sc_mode(self, sdram, sd_enable, write_enable, sram_bank=0, ctrl=0x8):
        """Ejecutar la secuencia de desbloqueo de SuperChis"""
        magic_addr_word = MAGIC_ADDRESS >> 1
        config1 = (ctrl << 4) | (sdram | (sd_enable << 1) | (write_enable << 2) | (sram_bank << 3))
        
        self.writeRom(magic_addr_word, MAGIC_VALUE)
        self.writeRom(magic_addr_word, MAGIC_VALUE)
        self.writeRom(magic_addr_word, config1)
        self.writeRom(magic_addr_word, config1)
        return True
    
    def sram_bank_select(self, bank):
        """Seleccionar banco SRAM"""
        # Compatible con el cambio de banco de la tarjeta D
        self.writeRom(0x800000, bank)
        return self.set_sc_mode(sdram=0, sd_enable=0, write_enable=0, sram_bank=bank, ctrl=0xF^(1<<3))
    
    def set_flashmapping(self, mapping):
        """Configurar el mapeo de Flash"""
        if len(mapping) != 8:
            raise ValueError("Mapping must be a list of 8 integers.")
        
        magic_addr_word = MAGIC_ADDRESS >> 1
        
        for i in range(8):
            self.writeRom(magic_addr_word, MAGIC_VALUE)
            self.writeRom(magic_addr_word, MAGIC_VALUE)
            self.writeRom(magic_addr_word, 0x0100|mapping[i])
            self.writeRom(magic_addr_word, 0x0100|mapping[i])
        
        return True
    
    def readRomID(self):
        """Leer el ID de la Flash ROM"""
        self.writeRom(0x000555, 0xaa)
        self.writeRom(0x0002aa, 0x55)
        self.writeRom(0x000555, 0x90)
        
        id_data = {}
        id_data['manufacturer'] = struct.unpack("<H", self.readRom(0x00, 2))[0]
        id_data['device_id1'] = struct.unpack("<H", self.readRom(0x01, 2))[0]
        id_data['device_id2'] = struct.unpack("<H", self.readRom(0x0e, 2))[0]
        id_data['device_id3'] = struct.unpack("<H", self.readRom(0x0f, 2))[0]
        
        self.writeRom(0x000000, 0xf0)
        return id_data
    
    def getRomCFI(self):
        """Obtener información CFI de la ROM"""
        self.writeRom(0x55, 0x98)
        cfi = self.readRom(0x27, 20)
        self.writeRom(0x00, 0xf0)
        
        temp = struct.unpack("<H", cfi[0:2])[0]
        device_size = 2 ** temp
        
        temp = struct.unpack("<H", cfi[6:8])[0]
        buffer_write_bytes = 2 ** temp if temp != 0 else 0
        
        temp = struct.unpack("<H", cfi[12:14])[0]
        temp1 = struct.unpack("<H", cfi[14:16])[0]
        sector_count = (((temp1 & 0xff) << 8) | (temp & 0xff)) + 1
        
        temp = struct.unpack("<H", cfi[16:18])[0]
        temp1 = struct.unpack("<H", cfi[18:20])[0]
        sector_size = (((temp1 & 0xff) << 8) | (temp & 0xff)) * 256
        
        return {
            'device_size': device_size,
            'sector_count': sector_count,
            'sector_size': sector_size,
            'buffer_write_bytes': buffer_write_bytes
        }
    
    def getRomEraseTime(self):
        """Obtener el tiempo de borrado de la ROM (milisegundos)"""
        cfi_info = self.getRomCFI()
        
        self.writeRom(0x55, 0x98)
        cfi = self.readRom(0x1f, 20)
        self.writeRom(0x00, 0xf0)
        
        temp = struct.unpack("<H", cfi[4:6])[0]
        timeout_block = 2 ** temp
        
        temp = struct.unpack("<H", cfi[6:8])[0]
        timeout_chip = 2 ** temp
        
        if timeout_chip == 1:
            return timeout_block * cfi_info['sector_count']
        else:
            return timeout_chip
    
    def eraseChip(self):
        """Borrar el chip completo"""
        self.writeRom(0x000555, 0xaa)
        self.writeRom(0x0002aa, 0x55)
        self.writeRom(0x000555, 0x80)
        self.writeRom(0x000555, 0xaa)
        self.writeRom(0x0002aa, 0x55)
        self.writeRom(0x000555, 0x10)
        
        time.sleep(0.1)
        while True:
            data = self.readRom(0x000000, 2)
            if struct.unpack("<H", data)[0] == 0xffff:
                break
            time.sleep(0.5)
        
        return True
    
    def eraseSector(self, addr_word, sector_size_words):
        """Borrar el sector indicado"""
        self.writeRom(0x000555, 0xaa)
        self.writeRom(0x0002aa, 0x55)
        self.writeRom(0x000555, 0x80)
        self.writeRom(0x000555, 0xaa)
        self.writeRom(0x0002aa, 0x55)
        self.writeRom(addr_word, 0x30)
        
        time.sleep(0.01)
        while True:
            data = self.readRom(addr_word, 2)
            if struct.unpack("<H", data)[0] == 0xffff:
                break
            time.sleep(0.1)
        
        return True
    
    def programRom(self, addr_byte, data, buffer_write_bytes=None):
        """
        Escribir datos en la ROM (usando el comando 0xf4 del firmware)
        
        Args:
            addr_byte: dirección en bytes (nota: el comando 0xf4 usa direcciones en bytes, no en palabras)
            data: datos a escribir
            buffer_write_bytes: tamaño de Buffer Write (si es None se consulta el CFI automáticamente)
        """
        if isinstance(data, int):
            data = struct.pack("<H", data)
        
        # Si no se indicó buffer_write_bytes, se consulta el CFI
        if buffer_write_bytes is None:
            cfi_info = self.getRomCFI()
            buffer_write_bytes = cfi_info['buffer_write_bytes']
        
        # Construir el paquete de datos
        cmd = []
        cmd.extend(struct.pack("<H", 2 + 1 + 4 + 2 + len(data) + 2))  # tamaño del paquete
        cmd.append(0xf4)  # rom program cmd
        cmd.extend(struct.pack("<I", addr_byte))  # base address (dirección en bytes)
        cmd.extend(struct.pack("<H", buffer_write_bytes))  # bufferWriteBytes
        cmd.extend(data)  # data
        cmd.extend([0, 0])  # marcador de posición CRC
        
        self.ser.write(cmd)
        ack = self.ser.read(1)
        
        return ack == b'\xaa'
    
    def unlockPPB(self):
        """Desbloquear la protección PPB de todos los sectores"""
        self.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])
        
        self.writeRom(0x000555, 0xaa)
        self.writeRom(0x0002aa, 0x55)
        self.writeRom(0x000555, 0xc0)
        
        self.writeRom(0, 0x80)
        self.writeRom(0, 0x30)
        
        time.sleep(0.1)
        for _ in range(100):
            self.writeRom(0x000555, 0x70)
            status = self.readRom(0, 2)
            if struct.unpack("<H", status)[0] & 0x80:
                break
            time.sleep(0.01)
        
        self.writeRom(0, 0x90)
        self.writeRom(0, 0x00)
        self.writeRom(0x000000, 0xf0)
        
        return True
    
    def checkPPBLocked(self):
        """Comprobar si el PPB está bloqueado"""
        self.writeRom(0x000555, 0xaa)
        self.writeRom(0x0002aa, 0x55)
        self.writeRom(0x000555, 0x50)
        
        status = self.readRom(0, 2)
        lock_status = struct.unpack("<H", status)[0]
        
        self.writeRom(0, 0x90)
        self.writeRom(0, 0x00)
        self.writeRom(0, 0xf0)
        
        return lock_status != 0
    
    def verifyRom(self, addr_word, expected_data):
        """Verificar los datos de la ROM"""
        actual_data = self.readRom(addr_word, len(expected_data))
        return actual_data == expected_data
    
    def eraseFlashMetadata(self):
        """Borrar la zona de constantes de metadatos de Flash - función de reinicio de juegos NOR"""
        self.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])
        # Dirección inicial y tamaño de la zona de metadatos de Flash
        meta_start = ROM_OFF_FLASHMETA  # 0x00200000
        meta_size = FLASH_METADATA_SIZE  # 0x00200000 (2MB)
        
        # Obtener información CFI
        cfi_info = self.getRomCFI()
        sector_size = cfi_info['sector_size']
        
        # Calcular el número de sectores a borrar
        sector_count = meta_size // sector_size
        
        # Borrar todos los sectores de la zona de metadatos
        for i in range(sector_count):
            addr_byte = meta_start + i * sector_size
            addr_word = addr_byte >> 1
            self.eraseSector(addr_word, sector_size >> 1)
        
        return True
