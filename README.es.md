[English](README.md) | **Español** | [中文](README.zh.md)

# SuperChis – Herramienta de Grabación Automática

Aplicación de escritorio (Python + PySide6) para grabar cartuchos de Game Boy Advance en lote con grabadores SuperChis.

## Características

### 1. Gestión de múltiples dispositivos
- ✅ Escanea y detecta automáticamente los grabadores SuperChis por USB
- ✅ Conexión simultánea de varios dispositivos
- ✅ Indicador de estado en vivo (conectado / desconectado / ocupado)
- ✅ Conexión y desconexión en lote
- ✅ Control individual de cada dispositivo

### 2. Control de calidad automático
- ✅ **Prueba de lectura/escritura de SDRAM**
- ✅ **Prueba de lectura/escritura de SRAM** (cambio de banco y prueba completa de 128KB)
- ✅ **Borrado / verificación de Flash vacía** – borra automáticamente si la Flash no está vacía
- ✅ **Desbloqueo PPB de Flash** – comprueba y libera los bits de protección PPB

### 3. Grabación automática
- ✅ Elección del archivo ROM (`.gba`)
- ✅ Compara los primeros 4K de la Flash y escribe solo si los datos difieren
- ✅ Borrado automático de sectores
- ✅ Buffer Write para programar más rápido
- ✅ Verificación automática de lo escrito
- ✅ Progreso en vivo por dispositivo
- ✅ **Parche de guardado automático**: al elegir una ROM que guarda en SRAM/EEPROM, se convierte a guardado en Flash (necesario para cartuchos con memoria de guardado Flash, como ChisFlash "1M Flash"/Celebi). Se crea una copia parcheada `*_flash512.gba`; tu original no se modifica
- ✅ Botón **Leer info**: muestra el título y código del juego que hay en el cartucho

### 4. Interfaz
- ✅ Lista de dispositivos con barra de progreso independiente
- ✅ Registro en tiempo real
- ✅ Operaciones en lote
- ✅ Selector de idioma al iniciar (中文 / Español)

## Instalación

Requiere Python 3.9+ (se recomienda 3.12 o 3.13).

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```bash
python chismaker.py
```

Al iniciar podés elegir el idioma de la interfaz y, si querés, recordarlo. Para saltar el diálogo usá `--lang es` o `--lang zh`. El botón "Language" del panel izquierdo borra la elección guardada (reiniciá para aplicarlo).

1. **Conectar dispositivos** – la app escanea los puertos USB y lista los SuperChis. Pulsá "Conectar todos" o conectá cada uno por separado.
2. **Control de calidad (opcional pero recomendado)** – ejecutá el control en lote o en un solo dispositivo y verificá que todo pase.
3. **Grabar** – elegí un archivo `.gba` y ejecutá la grabación en lote o en un solo dispositivo.
4. **Seguimiento** – cada dispositivo tiene su barra de progreso; el registro muestra los detalles.

## Crear ejecutables independientes

```bash
pip install pyinstaller
pyinstaller --noconfirm chismaker.spec
```

Ejecutalo en cada sistema operativo de destino (PyInstaller no compila de forma cruzada): `.exe` en Windows, `.app` en macOS.

## Detalles técnicos

### Funciones de `device_adapter.py`
- `readRomID()` – lee el ID del chip Flash
- `getRomCFI()` – información CFI (capacidad, tamaño de sector, …)
- `getRomEraseTime()` – tiempos de espera de borrado
- `eraseChip()` / `eraseSector()` – borrado de chip y de sector
- `programRom()` – programación de ROM (con Buffer Write)
- `unlockPPB()` / `checkPPBLocked()` – protección PPB
- `verifyRom()` – verificación de datos

### Mecanismo de desbloqueo de SuperChis
Se desbloquea mediante una dirección mágica:
- Dirección mágica: `0x01FFFFFE` (espacio de direcciones GBA)
- Valor mágico: `0xA55A`
- Valor de mapeo de Flash: `0xA558`

Bits de configuración:
- Bit 0: cambio SDRAM / Flash
- Bit 1: habilitar tarjeta SD
- Bit 2: habilitar escritura
- Bit 3: selección de banco SRAM

### Arquitectura de hilos
- `DeviceScanner` – escaneo de dispositivos en segundo plano
- `QualityCheckWorker` – control de calidad
- `ProductionWorker` – grabación

Cada dispositivo trabaja en su propio hilo, así que las operaciones no se interfieren.

## Solución de problemas

- **Dispositivo no detectado:** revisá el cable USB, confirmá que el VID:PID sea `0x0483:0x0721` y volvé a conectarlo.
- **Falla el control de calidad:** SDRAM → revisá las conexiones; SRAM → revisá el chip; borrado de Flash → probá desbloquear el PPB a mano; desbloqueo PPB → revisá el modelo del chip Flash.
- **Falla la grabación:** asegurate de que el control de calidad pasó, verificá el archivo ROM y leé el registro detallado.

## Chips Flash compatibles

Chips compatibles con CFI, entre ellos S29GL256 (Spansion), JS28F256 (Intel), S29GL01 (Spansion), S70GL02 (Spansion), MX29GL256 (Macronix) y M29W256G (Micron).

## Plan de desarrollo

- [ ] Soporte para cartuchos GBC
- [ ] Respaldo / restauración de partidas guardadas
- [ ] Identificación automática del cartucho
- [ ] Informe estadístico de grabaciones
- [ ] Guardar / cargar configuración

## Licencia

MIT License

## Agradecimientos

Implementación del protocolo basada en el proyecto ChisFlashBurner.

## Notas sobre el parche de guardado

Algunos cartuchos (p. ej. ChisFlash *Celebi*, "1M Flash") guardan las partidas en un chip Flash y no en SRAM, así que los juegos con `SRAM_V`/`EEPROM_V` no pueden guardar sin parche. La app detecta el tipo de guardado y parchea automáticamente (opción: "Parche de guardado automático"). Los juegos que ya usan `FLASH_V`/`FLASH1M_V` no lo necesitan. El parche es un port a Python de [gba-flash-patcher](https://github.com/metroid-maniac/gba-flash-patcher) de Metroid Maniac (MIT). El resultado puede variar según el juego; probá que guarde antes de confiar en él.
