#!/usr/bin/env python3
"""
SuperChis Herramienta de Producción Automática V2
Funciones:
1. Gestión de múltiples dispositivos (conexión/desconexión automática, indicador de estado)
2. Control de calidad automático configurable (lectura/escritura SRAM, borrado de Flash, desbloqueo PPB, detección de Backup Flash, etc.)
3. Producción automática con el archivo elegido (borrado y escritura directa de la ROM)
"""

import sys
import os
import time
import struct
import threading
import traceback
import random
from pathlib import Path
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QFileDialog,
    QProgressBar, QTextEdit, QGroupBox, QCheckBox, QSpinBox, QMessageBox,
    QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor

import serial.tools.list_ports
import serial

# Importar el adaptador de dispositivo
from device_adapter import SuperChisDevice


# Clase de configuración del control de calidad
class QualityCheckConfig:
    """Configuración del control de calidad"""
    def __init__(self):
        self.enable_ppb_unlock = True         # Desbloqueo PPB de Flash
        self.enable_sram_test = False          # Prueba de lectura/escritura SRAM
        self.enable_flash_erase = False        # Borrado y verificación de Flash vacía
        self.enable_fast_flash = False        # Control rápido de Flash (4M iniciales y finales + 8M aleatorios)
        self.enable_full_sram = True         # Prueba completa de SRAM (128KB)
        self.enable_ram_flash = False         # Detección de Backup Flash


class DeviceInfo:
    """Clase de información del dispositivo"""
    def __init__(self, port_name: str):
        self.port_name = port_name
        self.serial: Optional[serial.Serial] = None
        self.status = "Desconectado"
        self.rom_id = None
        self.cfi_info = None
        self.last_operation = ""
        self.error_count = 0
    
    def connect(self) -> bool:
        """Conectar dispositivo"""
        try:
            self.serial = serial.Serial()
            self.serial.port = self.port_name
            self.serial.baudrate = 115200
            self.serial.timeout = 5
            self.serial.open()
            self.serial.dtr = True
            self.serial.dtr = False
            self.status = "Conectado"
            return True
        except Exception as e:
            self.status = f"Conexión fallida: {e}"
            return False
    
    def disconnect(self):
        """Desconectar dispositivo"""
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.status = "Desconectado"
    
    def is_connected(self) -> bool:
        """Comprobar si está conectado"""
        return self.serial is not None and self.serial.is_open


class DeviceScanner(QThread):
    """Hilo de escaneo de dispositivos"""
    devices_found = Signal(list)
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    def run(self):
        """Escanear dispositivos"""
        while self.running:
            ports = serial.tools.list_ports.comports()
            device_ports = []
            
            for port in ports:
                if port.vid == 0x0483 and port.pid == 0x0721:
                    device_ports.append(port.device)
            
            self.devices_found.emit(device_ports)
            time.sleep(2)  # escanear cada 2 segundos
    
    def stop(self):
        """Detener escaneo"""
        self.running = False


class QualityCheckWorker(QThread):
    """Hilo de trabajo de control de calidad"""
    log_signal = Signal(str, str)  # (device_name, message)
    progress_signal = Signal(str, int)  # (device_name, progress)
    finished_signal = Signal(str, bool)  # (device_name, success)
    
    def __init__(self, device: DeviceInfo, config: QualityCheckConfig):
        super().__init__()
        self.device = device
        self.config = config
        self.running = True
    
    def stop(self):
        """Detener hilo"""
        self.running = False
    
    def run(self):
        """Ejecutar el proceso de control de calidad"""
        # Crear el adaptador de dispositivo
        device_adapter = SuperChisDevice(self.device.serial)
        
        try:
            self.log_signal.emit(self.device.port_name, "Iniciando control de calidad...")
            
            # Calcular el número de pruebas habilitadas
            test_count = sum([
                self.config.enable_sram_test,
                self.config.enable_flash_erase or self.config.enable_fast_flash,
                self.config.enable_ppb_unlock,
                self.config.enable_full_sram,
                self.config.enable_ram_flash
            ])
            
            if test_count == 0:
                self.log_signal.emit(self.device.port_name, "No hay ninguna prueba habilitada")
                self.finished_signal.emit(self.device.port_name, False)
                return
            
            current_test = 0
            progress_per_test = 100 / test_count
            
            # 1. Desbloqueo PPB de Flash (antes de las operaciones de Flash)
            if self.config.enable_ppb_unlock and self.running:
                current_test += 1
                self.log_signal.emit(self.device.port_name, f"{current_test}/{test_count} Desbloqueo PPB de Flash...")
                self.progress_signal.emit(self.device.port_name, int((current_test - 0.5) * progress_per_test))
                
                device_adapter.set_sc_mode(sdram=0, sd_enable=0, write_enable=1)
                device_adapter.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])
                device_adapter.unlockPPB()
                
                self.log_signal.emit(self.device.port_name, "✓ Desbloqueo PPB completado")
                self.progress_signal.emit(self.device.port_name, int(current_test * progress_per_test))

            # 2. Prueba de lectura/escritura SRAM (básica)
            if self.config.enable_sram_test and self.running:
                current_test += 1
                self.log_signal.emit(self.device.port_name, f"{current_test}/{test_count} Prueba básica de lectura/escritura SRAM...")
                self.progress_signal.emit(self.device.port_name, int((current_test - 0.5) * progress_per_test))
                
                device_adapter.sram_bank_select(0)
                time.sleep(0.01)
                
                test_data = b'\xAA\x55\x12\x34'
                device_adapter.writeRam(0x0000, test_data)
                time.sleep(0.01)
                read_data = device_adapter.readRam(0x0000, len(test_data))
                
                if read_data != test_data:
                    raise Exception(f"Fallo en la prueba básica de SRAM")
                
                self.log_signal.emit(self.device.port_name, "✓ Prueba básica de SRAM superada")
                self.progress_signal.emit(self.device.port_name, int(current_test * progress_per_test))
            
            # 3. Prueba completa de SRAM (opcional)
            if self.config.enable_full_sram and self.running:
                current_test += 1
                self.log_signal.emit(self.device.port_name, f"{current_test}/{test_count} Prueba completa de SRAM (128KB)...")
                self.progress_signal.emit(self.device.port_name, int((current_test - 0.5) * progress_per_test))

                # Probar 128KB
                device_adapter.sram_bank_select(0)
                time.sleep(0.01)
                
                # Escribir datos de prueba
                chunk_size = 1024
                for addr in range(0, 65536*2, chunk_size):
                    if addr % (65536) == 0:
                        device_adapter.sram_bank_select(addr // 65536)
                        self.log_signal.emit(self.device.port_name, 
                            f"  Cambiando al banco SRAM {addr // 65536}")
                    # Generar datos de prueba
                    test_data = bytes([(addr + i) & 0xFF for i in range(chunk_size)])
                    device_adapter.writeRam(addr, test_data)
                    
                    # Verificar de inmediato
                    read_data = device_adapter.readRam(addr, chunk_size)
                    if read_data != test_data:
                        raise Exception(f"Fallo en la prueba completa de SRAM en la dirección 0x{addr:04X}")
                
                self.log_signal.emit(self.device.port_name, "✓ Prueba completa de SRAM superada (128KB)")
                self.progress_signal.emit(self.device.port_name, int(current_test * progress_per_test))
            
            
            # 4. Borrado/verificación de Flash vacía o control rápido de Flash
            if (self.config.enable_flash_erase or self.config.enable_fast_flash) and self.running:
                current_test += 1
                
                device_adapter.set_sc_mode(sdram=0, sd_enable=0, write_enable=1)
                device_adapter.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])
                
                if self.config.enable_fast_flash:
                    # Control rápido de Flash: 4M iniciales y finales + 8M aleatorios
                    self.log_signal.emit(self.device.port_name, f"{current_test}/{test_count} Control rápido de Flash (4M iniciales y finales + 8M aleatorios)...")
                    self.progress_signal.emit(self.device.port_name, int((current_test - 0.5) * progress_per_test))
                    
                    # Obtener información CFI
                    cfi_info = device_adapter.getRomCFI()
                    sector_size = cfi_info['sector_size']
                    device_size = cfi_info['device_size']
                    
                    # Calcular las zonas a borrar
                    test_regions = []
                    
                    # Primeros 4M
                    test_regions.append((0, 4 * 1024 * 1024))
                    
                    # Últimos 4M
                    end_start = device_size - 4 * 1024 * 1024
                    test_regions.append((end_start, device_size))
                    
                    # 8M aleatorios (en 4 zonas de 2M)
                    random.seed(int(time.time()))
                    for _ in range(4):
                        random_start = random.randint(4 * 1024 * 1024, device_size - 6 * 1024 * 1024)
                        random_start = (random_start // sector_size) * sector_size  # alinear al sector
                        test_regions.append((random_start, random_start + 2 * 1024 * 1024))
                    
                    # Borrar las zonas de prueba
                    total_sectors = 0
                    for start, end in test_regions:
                        sector_count = (end - start) // sector_size
                        total_sectors += sector_count
                    
                    erased_sectors = 0
                    for start, end in test_regions:
                        sector_count = (end - start) // sector_size
                        for i in range(sector_count):
                            addr = start + i * sector_size
                            device_adapter.eraseSector(addr >> 1, sector_size >> 1)
                            erased_sectors += 1
                            
                            if erased_sectors % 10 == 0:
                                self.log_signal.emit(self.device.port_name, 
                                    f"Borrados {erased_sectors}/{total_sectors} sectores")
                    
                    # Verificar el resultado del borrado
                    for start, end in test_regions:
                        for addr in range(start, end, 4096):
                            data = device_adapter.readRom(addr >> 1, min(4096, end - addr))
                            if not all(b == 0xff for b in data):
                                raise Exception(f"Falló la verificación del borrado de Flash en la dirección 0x{addr:08X}")
                    
                    self.log_signal.emit(self.device.port_name, "✓ Control rápido de Flash superado (16MB)")
                    
                else:
                    # Borrado total y verificación de vacío
                    self.log_signal.emit(self.device.port_name, f"{current_test}/{test_count} Borrado y verificación de Flash vacía...")
                    self.progress_signal.emit(self.device.port_name, int((current_test - 0.5) * progress_per_test))
                    
                    # Comprobar si el primer sector está vacío
                    first_sector = device_adapter.readRom(0x000000, 512)
                    is_empty = all(b == 0xff for b in first_sector)
                    
                    if not is_empty:
                        self.log_signal.emit(self.device.port_name, "La Flash no está vacía, ejecutando borrado total...")
                        device_adapter.eraseChip()
                        self.log_signal.emit(self.device.port_name, "✓ Borrado de Flash completado")
                    else:
                        self.log_signal.emit(self.device.port_name, "✓ La Flash ya está vacía")
                
                self.progress_signal.emit(self.device.port_name, int(current_test * progress_per_test))
            
            # 5. Detección de Backup Flash (dirección RAM mapeada a Flash)
            if self.config.enable_ram_flash and self.running:
                current_test += 1
                self.log_signal.emit(self.device.port_name, f"{current_test}/{test_count} Detección de Backup Flash...")
                self.progress_signal.emit(self.device.port_name, int((current_test - 0.5) * progress_per_test))
                
                # Probar si la dirección RAM está mapeada a Flash
                # Normalmente 0x0A000000-0x0AFFFFFF debería estar mapeado a Flash
                test_patterns = [
                    (0x5555, 0xAA),
                    (0x2AAA, 0x55),
                    (0x0000, 0x90),  # comando de ID de Flash
                ]
                
                for addr, value in test_patterns:
                    device_adapter.writeRam(addr, value)
                    time.sleep(0.001)
                
                # Leer el ID de Flash a través de la interfaz RAM
                manufacturer = device_adapter.readRam(0x0000, 2)
                device_id = device_adapter.readRam(0x0002, 2)
                
                # Salir del modo ID
                device_adapter.writeRam(0x0000, 0xF0)
                
                # Verificar que se leyó un ID válido
                if manufacturer != b'\xff\xff' and device_id != b'\xff\xff':
                    self.log_signal.emit(self.device.port_name, 
                        f"✓ Detección de Backup Flash superada (Mfr: {manufacturer.hex()}, ID: {device_id.hex()})")
                else:
                    raise Exception("Falló la detección de Backup Flash: no se pudo leer el ID de Flash")
                
                self.progress_signal.emit(self.device.port_name, int(current_test * progress_per_test))
            
            self.progress_signal.emit(self.device.port_name, 100)
            self.log_signal.emit(self.device.port_name, "Control de calidad completado ✓")
            self.finished_signal.emit(self.device.port_name, True)
            
        except Exception as e:
            self.log_signal.emit(self.device.port_name, f"Falló el control de calidad: {e}")
            self.finished_signal.emit(self.device.port_name, False)


class ResetNorWorker(QThread):
    """Hilo de trabajo de reinicio de juegos NOR"""
    log_signal = Signal(str, str)  # (device_name, message)
    progress_signal = Signal(str, int)  # (device_name, progress)
    finished_signal = Signal(str, bool)  # (device_name, success)
    
    def __init__(self, device: DeviceInfo):
        super().__init__()
        self.device = device
        self.running = True
    
    def stop(self):
        """Detener hilo"""
        self.running = False
    
    def run(self):
        """Ejecutar el proceso de reinicio de juegos NOR"""
        device_adapter = SuperChisDevice(self.device.serial)
        
        try:
            self.log_signal.emit(self.device.port_name, "Iniciando reinicio de juegos NOR...")
            self.progress_signal.emit(self.device.port_name, 10)
            
            # Configurar el modo de escritura habilitada
            device_adapter.set_sc_mode(sdram=0, sd_enable=0, write_enable=1)
            device_adapter.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])
            self.log_signal.emit(self.device.port_name, "Mapeo de Flash configurado")
            self.progress_signal.emit(self.device.port_name, 20)
            
            # Desbloquear la protección PPB
            self.log_signal.emit(self.device.port_name, "Desbloqueando la protección PPB de Flash...")
            device_adapter.unlockPPB()
            self.progress_signal.emit(self.device.port_name, 30)
            
            # Borrar la zona de metadatos de Flash
            self.log_signal.emit(self.device.port_name, "Borrando la zona de metadatos de Flash (2MB)...")
            device_adapter.eraseFlashMetadata()
            self.progress_signal.emit(self.device.port_name, 80)
            
            # Verificar el resultado del borrado
            self.log_signal.emit(self.device.port_name, "Verificando el resultado del borrado...")
            meta_start_word = 0x00200000 >> 1
            verify_data = device_adapter.readRom(meta_start_word, 512)
            
            if not all(b == 0xff for b in verify_data):
                raise Exception("Falló la verificación del borrado de la zona de metadatos de Flash")
            
            self.log_signal.emit(self.device.port_name, "Reinicio de juegos NOR completado ✓")
            self.progress_signal.emit(self.device.port_name, 100)
            self.finished_signal.emit(self.device.port_name, True)
            
        except Exception as e:
            traceback.print_exc()
            self.log_signal.emit(self.device.port_name, f"Falló el reinicio de juegos NOR: {e}")
            self.finished_signal.emit(self.device.port_name, False)


class BackupFlashWorker(QThread):
    """Hilo de trabajo de respaldo de Flash"""
    log_signal = Signal(str, str)  # (device_name, message)
    progress_signal = Signal(str, int)  # (device_name, progress)
    finished_signal = Signal(str, bool)  # (device_name, success)
    
    def __init__(self, device: DeviceInfo, backup_file: str, backup_size: int = 128 * 1024 * 1024):
        super().__init__()
        self.device = device
        self.backup_file = backup_file
        self.backup_size = backup_size  # por defecto 128MB
        self.running = True
    
    def stop(self):
        """Detener hilo"""
        self.running = False
    
    def run(self):
        """Ejecutar el proceso de respaldo"""
        device_adapter = SuperChisDevice(self.device.serial)
        
        try:
            self.log_signal.emit(self.device.port_name, "Iniciando respaldo de Flash...")
            self.progress_signal.emit(self.device.port_name, 0)
            
            # Configurar el modo de lectura de Flash
            device_adapter.set_sc_mode(sdram=0, sd_enable=0, write_enable=0)
            device_adapter.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])
            time.sleep(0.01)
            
            self.log_signal.emit(self.device.port_name, "Mapeo de Flash configurado")
            
            # Obtener información CFI
            cfi_info = device_adapter.getRomCFI()
            device_size = cfi_info['device_size']
            
            self.log_signal.emit(self.device.port_name, f"Tamaño de Flash: {device_size // (1024*1024)}MB")
            
            # Usar el menor entre el tamaño indicado y el del dispositivo
            total_size = min(self.backup_size, device_size)
            self.log_signal.emit(self.device.port_name, f"Tamaño del respaldo: {total_size // (1024*1024)}MB")
            
            # Abrir el archivo para escribir
            with open(self.backup_file, 'wb') as f:
                read_chunk_size = 4096  # leer 4KB cada vez
                read_bytes = 0
                
                # Cambiar el mapeo por segmentos de 32MB
                segment_size = 32 * 1024 * 1024
                current_segment = 0
                
                while read_bytes < total_size and self.running:
                    # Comprobar si hay que cambiar el mapeo de Flash
                    new_segment = read_bytes // segment_size
                    if new_segment != current_segment:
                        current_segment = new_segment
                        mapping_offset = current_segment * 8
                        device_adapter.set_flashmapping([
                            0 + mapping_offset, 1 + mapping_offset, 2 + mapping_offset, 3 + mapping_offset,
                            4 + mapping_offset, 5 + mapping_offset, 6 + mapping_offset, 7 + mapping_offset
                        ])
                        self.log_signal.emit(self.device.port_name, f"Cambiando el mapeo al segmento {current_segment}")
                    
                    # Calcular el desplazamiento dentro del segmento actual
                    offset_in_segment = read_bytes % segment_size
                    addr_word = offset_in_segment >> 1
                    
                    # Calcular la longitud de esta lectura
                    remaining = total_size - read_bytes
                    chunk_size = min(read_chunk_size, remaining)
                    
                    # Leer datos
                    data = device_adapter.readRom(addr_word, chunk_size)
                    f.write(data)
                    
                    read_bytes += chunk_size
                    
                    # Actualizar progreso (registrar cada 1MB)
                    if read_bytes % (1024 * 1024) == 0 or read_bytes >= total_size:
                        progress = int(read_bytes / total_size * 100)
                        self.progress_signal.emit(self.device.port_name, progress)
                        self.log_signal.emit(self.device.port_name, 
                            f"Respaldados {read_bytes // (1024*1024)}MB / {total_size // (1024*1024)}MB ({progress}%)")
            
            if not self.running:
                self.log_signal.emit(self.device.port_name, "Respaldo cancelado")
                self.finished_signal.emit(self.device.port_name, False)
                return
            
            self.log_signal.emit(self.device.port_name, "Respaldo completado ✓")
            self.progress_signal.emit(self.device.port_name, 100)
            self.finished_signal.emit(self.device.port_name, True)
            
        except Exception as e:
            traceback.print_exc()
            self.log_signal.emit(self.device.port_name, f"Falló el respaldo: {e}")
            self.finished_signal.emit(self.device.port_name, False)


class ProductionWorker(QThread):
    """Hilo de trabajo de producción"""
    log_signal = Signal(str, str)  # (device_name, message)
    progress_signal = Signal(str, int)  # (device_name, progress)
    finished_signal = Signal(str, bool)  # (device_name, success)
    
    def __init__(self, device: DeviceInfo, rom_file: str):
        super().__init__()
        self.device = device
        self.rom_file = rom_file
        self.running = True
    
    def stop(self):
        """Detener hilo"""
        self.running = False
    
    def run(self):
        """Ejecutar el proceso de producción"""
        # Crear el adaptador de dispositivo
        device_adapter = SuperChisDevice(self.device.serial)
        
        try:
            self.log_signal.emit(self.device.port_name, "Iniciando producción...")
            
            # Leer el archivo ROM
            with open(self.rom_file, 'rb') as f:
                rom_data = f.read()
            
            file_size = len(rom_data)
            self.log_signal.emit(self.device.port_name, f"Tamaño del archivo ROM: {file_size} bytes")
            
            # Alinear a número par
            if file_size % 2 != 0:
                rom_data += b'\x00'
                file_size = len(rom_data)
            
            # Cambiar al modo Flash
            device_adapter.set_sc_mode(sdram=0, sd_enable=0, write_enable=1)
            device_adapter.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])
            time.sleep(0.01)
            
            # Obtener información CFI
            cfi_info = device_adapter.getRomCFI()
            sector_size = cfi_info['sector_size']
            buffer_size = cfi_info['buffer_write_bytes']
            
            self.log_signal.emit(self.device.port_name, f"Tamaño de sector: {sector_size} bytes, tamaño de buffer: {buffer_size} bytes")
            
            # Comprobar el contenido de Flash y hallar la primera diferencia
            self.log_signal.emit(self.device.port_name, "Comprobando el contenido de Flash...")
            self.progress_signal.emit(self.device.port_name, 0)
            segment_size = 32 * 1024 * 1024
            check_chunk_size = 4096
            first_diff_addr = None
            checked = 0
            current_segment = 0
            last_progress = 0
            
            while checked < file_size and self.running:
                # Comprobar si hay que cambiar el mapeo de Flash
                new_segment = checked // segment_size
                if new_segment != current_segment:
                    current_segment = new_segment
                    mapping_offset = current_segment * 8
                    device_adapter.set_flashmapping([
                        0 + mapping_offset, 1 + mapping_offset, 2 + mapping_offset, 3 + mapping_offset,
                        4 + mapping_offset, 5 + mapping_offset, 6 + mapping_offset, 7 + mapping_offset
                    ])
                
                # Calcular el desplazamiento dentro del segmento actual
                offset_in_segment = checked % segment_size
                addr_word = offset_in_segment >> 1
                
                # Calcular la longitud de esta comprobación
                length = min(check_chunk_size, file_size - checked)
                expected = rom_data[checked:checked + length]
                
                # Leer y comparar
                actual = device_adapter.readRom(addr_word, length)
                if actual != expected:
                    first_diff_addr = checked
                    self.log_signal.emit(self.device.port_name, 
                        f"Diferencia encontrada en: 0x{first_diff_addr:08X} ({first_diff_addr // (1024*1024)}MB)")
                    break
                
                checked += length
                
                # Actualizar progreso (registrar cada 0.5MB o 1MB comprobado)
                progress = int(checked / file_size * 15)
                if progress != last_progress:
                    self.progress_signal.emit(self.device.port_name, progress)
                    last_progress = progress
                
                if checked % (1024 * 1024) == 0:
                    self.log_signal.emit(self.device.port_name, 
                        f"Comprobados {checked // (1024*1024)}MB / {file_size // (1024*1024)}MB")

            
            if not self.running:
                self.log_signal.emit(self.device.port_name, "Producción cancelada")
                self.finished_signal.emit(self.device.port_name, False)
                return
            
            # Si el contenido es idéntico, terminar directamente
            if first_diff_addr is None:
                self.log_signal.emit(self.device.port_name, "El contenido de Flash es idéntico a la ROM, se omite la escritura ✓")
                self.progress_signal.emit(self.device.port_name, 100)
                self.finished_signal.emit(self.device.port_name, True)
                return
            
            # Calcular el sector inicial a borrar (alineado hacia abajo al límite de sector)
            start_sector = first_diff_addr // sector_size
            start_addr = start_sector * sector_size
            
            self.log_signal.emit(self.device.port_name, 
                f"Desde la dirección 0x{start_addr:08X} se inicia el borrado y la escritura...")
            
            # Borrar los sectores necesarios - hay que manejar segmentos de 32MB
            addr_end = file_size - 1
            total_sector_count = (addr_end // sector_size) + 1
            sector_count = total_sector_count - start_sector
            
            self.log_signal.emit(self.device.port_name, 
                f"Hay que borrar {sector_count} sectores (desde el sector {start_sector}/{total_sector_count})...")
            
            current_segment = 0
            for i in range(start_sector, total_sector_count):
                if not self.running:
                    self.log_signal.emit(self.device.port_name, "Borrado cancelado")
                    self.finished_signal.emit(self.device.port_name, False)
                    return
                
                addr = i * sector_size
                
                # Comprobar si hay que cambiar el mapeo de Flash
                new_segment = addr // segment_size
                if new_segment != current_segment:
                    current_segment = new_segment
                    mapping_offset = current_segment * 8
                    device_adapter.set_flashmapping([
                        0 + mapping_offset, 1 + mapping_offset, 2 + mapping_offset, 3 + mapping_offset,
                        4 + mapping_offset, 5 + mapping_offset, 6 + mapping_offset, 7 + mapping_offset
                    ])
                    self.log_signal.emit(self.device.port_name, f"Cambiando el mapeo al segmento {current_segment} (desplazamiento de mapeo: {mapping_offset})")
                
                # Calcular el desplazamiento dentro del segmento actual
                offset_in_segment = addr % segment_size
                device_adapter.eraseSector(offset_in_segment >> 1, sector_size >> 1)
                
                progress = 15 + int((i - start_sector + 1) / sector_count * 35)
                self.progress_signal.emit(self.device.port_name, progress)
                
                if ((i - start_sector + 1) % 10 == 0) or ((i - start_sector + 1) == sector_count):
                    self.log_signal.emit(self.device.port_name, 
                        f"Borrados {i - start_sector + 1}/{sector_count} sectores")
            
            self.log_signal.emit(self.device.port_name, "Borrado completado, iniciando escritura...")
            
            # Reconfigurar el modo de escritura y el mapeo (puede ser necesario tras borrar)
            device_adapter.set_sc_mode(sdram=0, sd_enable=0, write_enable=1)
            device_adapter.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])
            time.sleep(0.01)
            
            # Escribir datos - desde start_addr, cambiando el mapeo por segmentos de 32MB
            write_chunk_size = 2048
            written = start_addr
            current_segment = 0
            
            while written < file_size and self.running:
                # Comprobar si hay que cambiar el mapeo de Flash
                new_segment = written // segment_size
                if new_segment != current_segment:
                    current_segment = new_segment
                    mapping_offset = current_segment * 8
                    device_adapter.set_flashmapping([
                        0 + mapping_offset, 1 + mapping_offset, 2 + mapping_offset, 3 + mapping_offset,
                        4 + mapping_offset, 5 + mapping_offset, 6 + mapping_offset, 7 + mapping_offset
                    ])
                    self.log_signal.emit(self.device.port_name, f"Cambiando el mapeo al segmento {current_segment}")
                
                # Calcular la dirección de desplazamiento dentro del segmento actual
                offset_in_segment = written % segment_size
                
                # Preparar los datos a escribir
                chunk = rom_data[written:written + write_chunk_size]
                if len(chunk) < write_chunk_size:
                    chunk += b'\xff' * (write_chunk_size - len(chunk))
                
                # Llamar a programRom con dirección en bytes (el comando 0xf4 usa direcciones en bytes)
                result = device_adapter.programRom(offset_in_segment, chunk, buffer_size)
                if not result:
                    raise Exception(f"Falló la escritura en la dirección 0x{written:08X} (segmento {current_segment}, desplazamiento 0x{offset_in_segment:08X})")
                
                written += write_chunk_size
                
                # Registrar cada 64KB escritos
                if written % (64 * 1024) == 0 or written >= file_size:
                    self.log_signal.emit(self.device.port_name, 
                        f"Escritos {written}/{file_size} bytes ({written*100//file_size}%)")
                
                progress = 50 + int((written - start_addr) / (file_size - start_addr) * 40)
                self.progress_signal.emit(self.device.port_name, progress)
            
            if not self.running:
                self.log_signal.emit(self.device.port_name, "Producción cancelada")
                self.finished_signal.emit(self.device.port_name, False)
                return
            
            self.log_signal.emit(self.device.port_name, "Escritura completada, iniciando verificación...")
            
            # Verificación - desde start_addr, también con segmentos de 32MB
            device_adapter.set_flashmapping([0, 1, 2, 3, 4, 5, 6, 7])  # reiniciar el mapeo al inicio
            verify_chunk_size = 4096
            verified = start_addr
            current_segment = 0
            
            while verified < file_size and self.running:
                # Comprobar si hay que cambiar el mapeo de Flash
                new_segment = verified // segment_size
                if new_segment != current_segment:
                    current_segment = new_segment
                    mapping_offset = current_segment * 8
                    device_adapter.set_flashmapping([
                        0 + mapping_offset, 1 + mapping_offset, 2 + mapping_offset, 3 + mapping_offset,
                        4 + mapping_offset, 5 + mapping_offset, 6 + mapping_offset, 7 + mapping_offset
                    ])
                
                # Calcular el desplazamiento dentro del segmento actual
                offset_in_segment = verified % segment_size
                addr_word = offset_in_segment >> 1
                
                # Calcular la longitud de esta verificación
                length = min(verify_chunk_size, file_size - verified)
                expected = rom_data[verified:verified + length]
                
                # Leer y verificar
                actual = device_adapter.readRom(addr_word, length)
                if actual != expected:
                    raise Exception(f"Falló la verificación en la dirección 0x{verified:08X}")
                
                verified += length
                
                # Registrar cada 1MB verificado
                if verified % (1024 * 1024) == 0 or verified >= file_size:
                    progress = 90 + int((verified - start_addr) / (file_size - start_addr) * 10)
                    self.progress_signal.emit(self.device.port_name, progress)
                    self.log_signal.emit(self.device.port_name, 
                        f"Verificados {verified // (1024*1024)}MB / {file_size // (1024*1024)}MB")
            
            self.log_signal.emit(self.device.port_name, "Producción completada ✓")
            self.progress_signal.emit(self.device.port_name, 100)
            self.finished_signal.emit(self.device.port_name, True)
            
        except Exception as e:
            traceback.print_exc()
            self.log_signal.emit(self.device.port_name, f"Falló la producción: {e}")
            self.finished_signal.emit(self.device.port_name, False)


class MainWindow(QMainWindow):
    """Ventana principal"""
    
    def __init__(self):
        super().__init__()
        self.devices: Dict[str, DeviceInfo] = {}
        self.workers: Dict[str, QThread] = {}
        self.rom_file = ""
        self.quality_config = QualityCheckConfig()
        self.scanner = None
        
        self.init_ui()
        
        # Iniciar el escaneo de dispositivos
        self.scanner = DeviceScanner()
        self.scanner.devices_found.connect(self.on_devices_found)
        self.scanner.start()
    
    def init_ui(self):
        """Inicializar la interfaz"""
        self.setWindowTitle("SuperChis Herramienta de Producción Automática V2")
        self.setGeometry(100, 100, 1400, 800)
        
        # Diseño principal - usando un divisor
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Crear el divisor
        splitter = QSplitter(Qt.Horizontal)
        
        # Barra lateral izquierda - control de calidad
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Grupo de configuración de control de calidad
        config_group = QGroupBox("Control de calidad")
        config_layout = QVBoxLayout()
        
        
        self.check_ppb = QCheckBox("Desbloqueo PPB de Flash")
        self.check_ppb.setChecked(self.quality_config.enable_ppb_unlock)
        self.check_ppb.stateChanged.connect(self.on_ppb_changed)

        self.check_sram_basic = QCheckBox("Prueba básica de lectura/escritura SRAM")
        self.check_sram_basic.setChecked(self.quality_config.enable_sram_test)
        self.check_sram_basic.stateChanged.connect(self.on_sram_basic_changed)
        
        self.check_sram_full = QCheckBox("Prueba SRAM completa (128KB)")
        self.check_sram_full.setChecked(self.quality_config.enable_full_sram)
        self.check_sram_full.stateChanged.connect(self.on_sram_full_changed)
        
        self.check_flash_erase = QCheckBox("Borrado total de Flash y verificación")
        self.check_flash_erase.setChecked(self.quality_config.enable_flash_erase)
        self.check_flash_erase.stateChanged.connect(self.on_flash_erase_changed)
        
        self.check_flash_fast = QCheckBox("Control rápido de Flash (16MB)")
        self.check_flash_fast.setChecked(self.quality_config.enable_fast_flash)
        self.check_flash_fast.stateChanged.connect(self.on_flash_fast_changed)
        
        self.check_ram_flash = QCheckBox("Detección de Backup Flash")
        self.check_ram_flash.setChecked(self.quality_config.enable_ram_flash)
        self.check_ram_flash.stateChanged.connect(self.on_ram_flash_changed)
        
        config_layout.addWidget(self.check_ppb)
        config_layout.addWidget(self.check_sram_basic)
        config_layout.addWidget(self.check_sram_full)
        config_layout.addWidget(self.check_flash_erase)
        config_layout.addWidget(self.check_flash_fast)
        config_layout.addWidget(self.check_ram_flash)
        config_layout.addStretch()
        
        config_group.setLayout(config_layout)
        left_layout.addWidget(config_group)
        
        # Descripción del control de calidad
        desc_group = QGroupBox("Descripción de funciones")
        desc_layout = QVBoxLayout()
        desc_text = QTextEdit()
        desc_text.setReadOnly(True)
        desc_text.setMaximumHeight(200)
        desc_text.setHtml("""
        <b>SRAM básica:</b> prueba rápida de los primeros 4 bytes del banco 0<br>
        <b>SRAM completa:</b> prueba completa de los 128KB de SRAM<br>
        <b>Borrado total de Flash:</b> comprueba y borra toda la Flash<br>
        <b>Control rápido de Flash:</b> borra solo 4M iniciales y finales + 8M aleatorios (16MB)<br>
        <b>Desbloqueo PPB:</b> quita la protección contra escritura de Flash<br>
        <b>RAM Flash:</b> prueba el acceso a Flash por la interfaz RAM
        """)
        desc_layout.addWidget(desc_text)
        desc_group.setLayout(desc_layout)
        left_layout.addWidget(desc_group)
        
        left_panel.setMaximumWidth(340)
        
        # Panel principal derecho
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Zona de control superior
        control_group = QGroupBox("Panel de control")
        control_layout = QHBoxLayout()
        
        # Selección de archivo ROM
        self.file_label = QLabel("Ninguna ROM seleccionada")
        self.select_file_btn = QPushButton("Elegir ROM")
        self.select_file_btn.clicked.connect(self.select_rom_file)
        
        # Botones de acciones
        self.connect_all_btn = QPushButton("Conectar todos")
        self.connect_all_btn.clicked.connect(self.connect_all_devices)
        
        self.disconnect_all_btn = QPushButton("Desconectar todos")
        self.disconnect_all_btn.clicked.connect(self.disconnect_all_devices)
        
        self.quality_check_btn = QPushButton("Control en lote")
        self.quality_check_btn.clicked.connect(self.start_quality_check_all)
        
        self.production_btn = QPushButton("Producción en lote")
        self.production_btn.clicked.connect(self.start_production_all)
        self.production_btn.setEnabled(False)
        
        self.reset_nor_btn = QPushButton("Reiniciar juegos NOR")
        self.reset_nor_btn.clicked.connect(self.start_reset_nor_all)
        self.reset_nor_btn.setStyleSheet("QPushButton { background-color: #FF6B6B; color: white; font-weight: bold; }")
        
        self.backup_flash_btn = QPushButton("Respaldar Flash")
        self.backup_flash_btn.clicked.connect(self.start_backup_flash_all)
        self.backup_flash_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        control_layout.addWidget(self.select_file_btn)
        control_layout.addWidget(self.file_label)
        control_layout.addStretch()
        control_layout.addWidget(self.connect_all_btn)
        control_layout.addWidget(self.disconnect_all_btn)
        control_layout.addWidget(self.quality_check_btn)
        control_layout.addWidget(self.production_btn)
        control_layout.addWidget(self.reset_nor_btn)
        control_layout.addWidget(self.backup_flash_btn)
        
        control_group.setLayout(control_layout)
        right_layout.addWidget(control_group)
        
        # Lista de dispositivos
        device_group = QGroupBox("Lista de dispositivos")
        device_layout = QVBoxLayout()
        
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(5)
        self.device_table.setHorizontalHeaderLabels(["Puerto", "Estado", "Progreso", "Acciones", "Registro"])
        self.device_table.setColumnWidth(0, 120)
        self.device_table.setColumnWidth(1, 140)
        self.device_table.setColumnWidth(2, 160)
        self.device_table.setColumnWidth(3, 660)
        self.device_table.setColumnWidth(4, 450)
        
        device_layout.addWidget(self.device_table)
        device_group.setLayout(device_layout)
        right_layout.addWidget(device_group)
        
        # Registro global
        log_group = QGroupBox("Registro global")
        log_layout = QVBoxLayout()
        
        self.global_log = QTextEdit()
        self.global_log.setReadOnly(True)
        self.global_log.setMaximumHeight(150)
        
        log_layout.addWidget(self.global_log)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)
        
        # Añadir al divisor
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
    
    def on_sram_basic_changed(self, state):
        """Cambio de la opción de prueba básica de SRAM"""
        self.quality_config.enable_sram_test = (state == Qt.CheckState.Checked.value)
        self.log_global(f"Prueba básica de SRAM: {'activado' if self.quality_config.enable_sram_test else 'desactivado'}")
    
    def on_sram_full_changed(self, state):
        """Cambio de la opción de prueba completa de SRAM"""
        self.quality_config.enable_full_sram = (state == Qt.CheckState.Checked.value)
        self.log_global(f"Prueba completa de SRAM: {'activado' if self.quality_config.enable_full_sram else 'desactivado'}")
    
    def on_flash_erase_changed(self, state):
        """Cambio de la opción de borrado de Flash"""
        self.quality_config.enable_flash_erase = (state == Qt.CheckState.Checked.value)
        if self.quality_config.enable_flash_erase:
            self.quality_config.enable_fast_flash = False
            self.check_flash_fast.setChecked(False)
        self.log_global(f"Borrado total de Flash: {'activado' if self.quality_config.enable_flash_erase else 'desactivado'}")
    
    def on_flash_fast_changed(self, state):
        """Cambio de la opción de control rápido de Flash"""
        self.quality_config.enable_fast_flash = (state == Qt.CheckState.Checked.value)
        if self.quality_config.enable_fast_flash:
            self.quality_config.enable_flash_erase = False
            self.check_flash_erase.setChecked(False)
        self.log_global(f"Control rápido de Flash: {'activado' if self.quality_config.enable_fast_flash else 'desactivado'}")
    
    def on_ppb_changed(self, state):
        """Cambio de la opción de desbloqueo PPB"""
        self.quality_config.enable_ppb_unlock = (state == Qt.CheckState.Checked.value)
        self.log_global(f"Desbloqueo PPB: {'activado' if self.quality_config.enable_ppb_unlock else 'desactivado'}")
    
    def on_ram_flash_changed(self, state):
        """Cambio de la opción de detección de Backup Flash"""
        self.quality_config.enable_ram_flash = (state == Qt.CheckState.Checked.value)
        self.log_global(f"Detección de Backup Flash: {'activado' if self.quality_config.enable_ram_flash else 'desactivado'}")
    
    def select_rom_file(self):
        """Elegir archivo ROM"""
        file_name, _ = QFileDialog.getOpenFileName( #formato gba o bin
            self, "Elegir archivo ROM", "", "ROM Files (*.gba *.bin);;All Files (*)"
        )
        
        if file_name:
            self.rom_file = file_name
            self.file_label.setText(f"Seleccionado: {Path(file_name).name}")
            self.production_btn.setEnabled(True)
            self.log_global(f"ROM seleccionada: {file_name}")
    
    def on_devices_found(self, ports: List[str]):
        """Callback del escaneo de dispositivos"""
        # Quitar los dispositivos desconectados
        removed_ports = [p for p in self.devices.keys() if p not in ports]
        for port in removed_ports:
            self.devices[port].disconnect()
            del self.devices[port]
        
        # Añadir dispositivos nuevos
        new_device_added = False
        for port in ports:
            if port not in self.devices:
                self.devices[port] = DeviceInfo(port)
                self.log_global(f"Dispositivo nuevo encontrado: {port}")
                new_device_added = True
        
        # Cuando cambia la lista de dispositivos hay que reconstruir la tabla por completo
        self.update_device_table(full_rebuild=(len(removed_ports) > 0 or new_device_added))
    
    def update_device_table(self, full_rebuild=False):
        """Actualizar la tabla de dispositivos
        Args:
            full_rebuild: si se reconstruye la tabla por completo (incluidos los widgets)
        """
        # Guardar el valor actual de las barras de progreso
        progress_values = {}
        if not full_rebuild:
            for row in range(self.device_table.rowCount()):
                port_item = self.device_table.item(row, 0)
                if port_item:
                    port = port_item.text()
                    progress_bar = self.device_table.cellWidget(row, 2)
                    if progress_bar:
                        progress_values[port] = progress_bar.value()
        
        self.device_table.setRowCount(len(self.devices))
        
        for row, (port, device) in enumerate(self.devices.items()):
            # Puerto
            self.device_table.setItem(row, 0, QTableWidgetItem(port))
            
            # Estado
            status_item = QTableWidgetItem(device.status)
            if "Conectado" in device.status:
                status_item.setBackground(QColor(144, 238, 144))
            elif "fallida" in device.status:
                status_item.setBackground(QColor(255, 182, 193))
            self.device_table.setItem(row, 1, status_item)
            
            # Barra de progreso - solo se recrea cuando es necesario
            if full_rebuild or self.device_table.cellWidget(row, 2) is None:
                progress_bar = QProgressBar()
                progress_bar.setMinimum(0)
                progress_bar.setMaximum(100)
                # Restaurar el valor de progreso anterior
                progress_bar.setValue(progress_values.get(port, 0))
                self.device_table.setCellWidget(row, 2, progress_bar)
            
            # Botones de acciones - solo se recrean cuando es necesario (cada botón está ligado a un puerto concreto)
            if full_rebuild or self.device_table.cellWidget(row, 3) is None:
                button_widget = QWidget()
                button_layout = QHBoxLayout(button_widget)
                button_layout.setContentsMargins(2, 2, 2, 2)
                
                connect_btn = QPushButton("Conectar")
                connect_btn.clicked.connect(lambda checked, p=port: self.connect_device(p))
                
                disconnect_btn = QPushButton("Desconectar")
                disconnect_btn.clicked.connect(lambda checked, p=port: self.disconnect_device(p))
                
                quality_btn = QPushButton("Control")
                quality_btn.clicked.connect(lambda checked, p=port: self.start_quality_check(p))
                
                production_btn = QPushButton("Producir")
                production_btn.clicked.connect(lambda checked, p=port: self.start_production(p))
                
                reset_nor_btn = QPushButton("Reset NOR")
                reset_nor_btn.clicked.connect(lambda checked, p=port: self.start_reset_nor(p))
                reset_nor_btn.setStyleSheet("background-color: #FF6B6B; color: white;")
                
                backup_btn = QPushButton("Respaldo")
                backup_btn.clicked.connect(lambda checked, p=port: self.start_backup_flash(p))
                backup_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                
                button_layout.addWidget(connect_btn)
                button_layout.addWidget(disconnect_btn)
                button_layout.addWidget(quality_btn)
                button_layout.addWidget(production_btn)
                button_layout.addWidget(reset_nor_btn)
                button_layout.addWidget(backup_btn)
                
                self.device_table.setCellWidget(row, 3, button_widget)
            
            # Registro (usa la última operación)
            self.device_table.setItem(row, 4, QTableWidgetItem(device.last_operation))
    
    def connect_device(self, port: str):
        """Conectar un solo dispositivo"""
        device = self.devices.get(port)
        if device:
            if device.connect():
                self.log_global(f"{port} conexión exitosa")
            else:
                self.log_global(f"{port} Conexión fallida")
            self.update_device_table()
    
    def disconnect_device(self, port: str):
        """Desconectar un solo dispositivo"""
        device = self.devices.get(port)
        if device:
            device.disconnect()
            self.log_global(f"{port} desconectado")
            self.update_device_table()
    
    def connect_all_devices(self):
        """Conectar todos"""
        for port, device in self.devices.items():
            if not device.is_connected():
                self.connect_device(port)
    
    def disconnect_all_devices(self):
        """Desconectar todos"""
        for port in list(self.devices.keys()):
            self.disconnect_device(port)
    
    def start_quality_check(self, port: str):
        """Iniciar el control de calidad de un dispositivo"""
        device = self.devices.get(port)
        if not device or not device.is_connected():
            QMessageBox.warning(self, "Advertencia", f"{port} no está conectado")
            return
        
        # Si ya hay un hilo de trabajo en ejecución, detenerlo primero
        if port in self.workers and self.workers[port].isRunning():
            self.workers[port].stop()
            self.workers[port].wait(1000)
        
        worker = QualityCheckWorker(device, self.quality_config)
        worker.log_signal.connect(self.on_worker_log)
        worker.progress_signal.connect(self.on_worker_progress)
        worker.finished_signal.connect(self.on_worker_finished)
        # Asegurar que la limpieza se dispare cuando termine el hilo
        worker.finished.connect(lambda: self.cleanup_worker(port))
        
        self.workers[port] = worker
        worker.start()
    
    def start_quality_check_all(self):
        """Control en lote"""
        delay = 0
        for port, device in self.devices.items():
            if device.is_connected():
                # Usar QTimer para añadir un retraso aleatorio y evitar falta de alimentación USB
                QTimer.singleShot(int(delay * 1000), lambda p=port: self.start_quality_check(p))
                delay += random.uniform(0.5, 1.0)  # 0.5-1 s entre dispositivos
    
    def start_production(self, port: str):
        """Iniciar la producción de un dispositivo"""
        if not self.rom_file:
            QMessageBox.warning(self, "Advertencia", "Primero elija un archivo ROM")
            return
        
        device = self.devices.get(port)
        if not device or not device.is_connected():
            QMessageBox.warning(self, "Advertencia", f"{port} no está conectado")
            return
        
        # Si ya hay un hilo de trabajo en ejecución, detenerlo primero
        if port in self.workers and self.workers[port].isRunning():
            self.workers[port].stop()
            self.workers[port].wait(1000)
        
        worker = ProductionWorker(device, self.rom_file)
        worker.log_signal.connect(self.on_worker_log)
        worker.progress_signal.connect(self.on_worker_progress)
        worker.finished_signal.connect(self.on_worker_finished)
        # Asegurar que la limpieza se dispare cuando termine el hilo
        worker.finished.connect(lambda: self.cleanup_worker(port))
        
        self.workers[port] = worker
        worker.start()
    
    def start_production_all(self):
        """Producción en lote"""
        if not self.rom_file:
            QMessageBox.warning(self, "Advertencia", "Primero elija un archivo ROM")
            return
        
        delay = 0
        for port, device in self.devices.items():
            if device.is_connected():
                # Usar QTimer para añadir un retraso aleatorio y evitar falta de alimentación USB
                QTimer.singleShot(int(delay * 1000), lambda p=port: self.start_production(p))
                delay += random.uniform(0.5, 1.0)  # 0.5-1 s entre dispositivos
    
    def start_reset_nor(self, port: str):
        """Iniciar el reinicio de juegos NOR de un dispositivo"""
        device = self.devices.get(port)
        if not device or not device.is_connected():
            QMessageBox.warning(self, "Advertencia", f"{port} no está conectado")
            return
        
        # Confirmar operación
        reply = QMessageBox.question(
            self, "Confirmar operación",
            f"¿Seguro que desea reiniciar los juegos NOR de {port}?\n\nSe borrará la zona de metadatos de Flash (2MB). ¡La operación es irreversible!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Si ya hay un hilo de trabajo en ejecución, detenerlo primero
        if port in self.workers and self.workers[port].isRunning():
            self.workers[port].stop()
            self.workers[port].wait(1000)
        
        worker = ResetNorWorker(device)
        worker.log_signal.connect(self.on_worker_log)
        worker.progress_signal.connect(self.on_worker_progress)
        worker.finished_signal.connect(self.on_worker_finished)
        worker.finished.connect(lambda: self.cleanup_worker(port))
        
        self.workers[port] = worker
        worker.start()
    
    def start_reset_nor_all(self):
        """Reinicio en lote de juegos NOR"""
        # Confirmar operación
        reply = QMessageBox.question(
            self, "Confirmar operación",
            f"¿Seguro que desea reiniciar los juegos NOR de todos los dispositivos conectados?\n\nSe borrará la zona de metadatos de Flash (2MB) de todos los dispositivos. ¡La operación es irreversible!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        for port, device in self.devices.items():
            if device.is_connected():
                # Omitir el diálogo de confirmación y ejecutar directamente
                if port in self.workers and self.workers[port].isRunning():
                    self.workers[port].stop()
                    self.workers[port].wait(1000)
                
                worker = ResetNorWorker(device)
                worker.log_signal.connect(self.on_worker_log)
                worker.progress_signal.connect(self.on_worker_progress)
                worker.finished_signal.connect(self.on_worker_finished)
                worker.finished.connect(lambda p=port: self.cleanup_worker(p))
                
                self.workers[port] = worker
                worker.start()
    
    def start_backup_flash(self, port: str):
        """Iniciar el respaldo de Flash de un dispositivo"""
        device = self.devices.get(port)
        if not device or not device.is_connected():
            QMessageBox.warning(self, "Advertencia", f"{port} no está conectado")
            return
        
        # Elegir el archivo de destino
        default_name = f"flash_backup_{port.replace('/', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.bin"
        backup_file, _ = QFileDialog.getSaveFileName(
            self, "Guardar respaldo de Flash", default_name, "Binary Files (*.bin);;All Files (*)"
        )
        
        if not backup_file:
            return
        
        # Si ya hay un hilo de trabajo en ejecución, detenerlo primero
        if port in self.workers and self.workers[port].isRunning():
            self.workers[port].stop()
            self.workers[port].wait(1000)
        
        worker = BackupFlashWorker(device, backup_file)
        worker.log_signal.connect(self.on_worker_log)
        worker.progress_signal.connect(self.on_worker_progress)
        worker.finished_signal.connect(self.on_worker_finished)
        worker.finished.connect(lambda: self.cleanup_worker(port))
        
        self.workers[port] = worker
        worker.start()
    
    def start_backup_flash_all(self):
        """Respaldo de Flash en lote"""
        # Elegir el directorio de destino
        backup_dir = QFileDialog.getExistingDirectory(
            self, "Elegir directorio para los respaldos", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not backup_dir:
            return
        
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        
        for port, device in self.devices.items():
            if device.is_connected():
                # Generar el nombre del archivo de respaldo para cada dispositivo
                safe_port = port.replace('/', '_').replace('\\', '_')
                backup_file = os.path.join(backup_dir, f"flash_backup_{safe_port}_{timestamp}.bin")
                
                # Si ya hay un hilo de trabajo en ejecución, detenerlo primero
                if port in self.workers and self.workers[port].isRunning():
                    self.workers[port].stop()
                    self.workers[port].wait(1000)
                
                worker = BackupFlashWorker(device, backup_file)
                worker.log_signal.connect(self.on_worker_log)
                worker.progress_signal.connect(self.on_worker_progress)
                worker.finished_signal.connect(self.on_worker_finished)
                worker.finished.connect(lambda p=port: self.cleanup_worker(p))
                
                self.workers[port] = worker
                worker.start()
                
                self.log_global(f"Iniciando respaldo de {port} en {backup_file}")
    
    def on_worker_log(self, port: str, message: str):
        """Callback de registro del hilo de trabajo"""
        device = self.devices.get(port)
        if device:
            device.last_operation = message
            # Solo actualizar el texto, sin reconstruir el widget
            for row in range(self.device_table.rowCount()):
                if self.device_table.item(row, 0).text() == port:
                    self.device_table.setItem(row, 4, QTableWidgetItem(message))
                    break
        
        self.log_global(f"[{port}] {message}")
    
    def on_worker_progress(self, port: str, progress: int):
        """Callback de progreso del hilo de trabajo"""
        for row in range(self.device_table.rowCount()):
            if self.device_table.item(row, 0).text() == port:
                progress_bar = self.device_table.cellWidget(row, 2)
                if progress_bar:
                    progress_bar.setValue(progress)
                break
    
    def on_worker_finished(self, port: str, success: bool):
        """Callback de finalización del hilo de trabajo"""
        device = self.devices.get(port)
        if device:
            if success:
                device.status = "Operación exitosa"
            else:
                device.status = "Operación fallida"
                device.error_count += 1
            self.update_device_table()
    
    def cleanup_worker(self, port: str):
        """Limpiar los hilos de trabajo terminados"""
        if port in self.workers:
            worker = self.workers[port]
            # Asegurar que el hilo ya terminó
            if worker.isRunning():
                worker.wait(2000)  # esperar como máximo 2 s
                if worker.isRunning():
                    # Si sigue en ejecución, forzar la detención
                    worker.stop()
                    worker.wait(1000)
            
            # Desconectar todas las señales
            try:
                worker.log_signal.disconnect()
                worker.progress_signal.disconnect()
                worker.finished_signal.disconnect()
                worker.finished.disconnect()
            except:
                pass
            
            # Usar deleteLater para borrar de forma segura en lugar de del directo
            # Así Qt elimina el objeto en el momento adecuado y evita destruirlo mientras el hilo corre
            worker.deleteLater()
            
            # Quitar la referencia del diccionario
            del self.workers[port]
    
    def log_global(self, message: str):
        """Registro global"""
        timestamp = time.strftime("%H:%M:%S")
        self.global_log.append(f"[{timestamp}] {message}")
    
    def closeEvent(self, event):
        """Cerrar la ventana"""
        self.log_global("Cerrando el programa...")
        
        # Detener el hilo de escaneo
        if hasattr(self, 'scanner') and self.scanner:
            if self.scanner.isRunning():
                self.scanner.stop()
                self.scanner.wait(3000)
                if self.scanner.isRunning():
                    self.scanner.terminate()
                    self.scanner.wait(1000)
            self.scanner.deleteLater()
        
        # Detener todos los hilos de trabajo
        for port, worker in list(self.workers.items()):
            if worker.isRunning():
                worker.stop()
                worker.wait(3000)  # esperar como máximo 3 s
                if worker.isRunning():
                    self.log_global(f"Forzando el cierre del hilo de {port}")
                    worker.terminate()
                    worker.wait(1000)
            
            # Usar deleteLater para borrar de forma segura
            worker.deleteLater()
        
        # Vaciar el diccionario de hilos de trabajo
        self.workers.clear()
        
        # Desconectar todos
        for device in self.devices.values():
            if device.is_connected():
                device.disconnect()
        
        self.log_global("Programa cerrado")
        event.accept()


def main():
    """Función principal"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
