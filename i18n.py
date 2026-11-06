"""Internacionalización (i18n) de SuperChis Auto-Production Tool.

El código fuente conserva los textos originales en chino. Para otros idiomas,
`tr()` traduce el texto justo antes de mostrarlo (interfaz y registros).
Idiomas disponibles: zh (中文, por defecto) y es (Español).
"""
import re
import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
)

LANGUAGES = {"zh": "中文", "es": "Español"}
_lang = "zh"
_CJK = re.compile(r"[一-鿿]")
_FULLWIDTH = {"：": ": ", "，": ", ", "（": " (", "）": ")", "。": ".", "、": ", ", "；": "; "}

# Textos completos (coincidencia exacta)
EXACT = {
    '连接': 'Conectar',
    '断开': 'Desconectar',
    '质检': 'Control',
    '量产': 'Producir',
    '重置NOR': 'Reset NOR',
    '备份': 'Respaldo',
    '警告': 'Advertencia',
    '未连接': 'Desconectado',
    '已连接': 'Conectado',
    '操作成功': 'Operación exitosa',
    '操作失败': 'Operación fallida',
    '质检配置': 'Control de calidad',
    '选择ROM文件': 'Elegir ROM',
    '端口': 'Puerto',
    '状态': 'Estado',
    '进度': 'Progreso',
    '操作': 'Acciones',
    '日志': 'Registro',
}

# Fragmentos (se reemplazan de mayor a menor longitud dentro del texto)
FRAGMENTS = {
    '设置Flash映射': 'Configurar el mapeo de Flash',
    'SuperChis 自动量产工具 V2': 'SuperChis Herramienta de Producción Automática V2',
    '功能：': 'Funciones:',
    '1. 多设备管理（自动连接、断开、状态指示）': '1. Gestión de múltiples dispositivos (conexión/desconexión automática, indicador de estado)',
    '2. 可配置自动质检（SRAM读写、Flash擦除、PPB解锁、Backup Flash检测等）': '2. Control de calidad automático configurable (lectura/escritura SRAM, borrado de Flash, desbloqueo PPB, detección de Backup Flash, etc.)',
    '3. 选定文件自动量产（直接擦除和写入ROM）': '3. Producción automática con el archivo elegido (borrado y escritura directa de la ROM)',
    'Flash PPB解锁': 'Desbloqueo PPB de Flash',
    'Flash擦除查空': 'Borrado y verificación de Flash vacía',
    'Backup Flash检测通过': 'Detección de Backup Flash superada',
    'Backup Flash检测失败：无法读取Flash ID': 'Falló la detección de Backup Flash: no se pudo leer el ID de Flash',
    'Backup Flash检测: ': 'Detección de Backup Flash: ',
    'Backup Flash检测': 'Detección de Backup Flash',
    '连接设备': 'Conectar dispositivo',
    '开始质检...': 'Iniciando control de calidad...',
    '未启用任何测试项': 'No hay ninguna prueba habilitada',
    'PPB解锁完成': 'Desbloqueo PPB completado',
    'SRAM基础读写检测': 'Prueba básica de lectura/escritura SRAM',
    'SRAM基础测试失败': 'Fallo en la prueba básica de SRAM',
    'SRAM基础测试通过': 'Prueba básica de SRAM superada',
    'SRAM基础测试: ': 'Prueba básica de SRAM: ',
    '全量SRAM检测(128KB)': 'Prueba completa de SRAM (128KB)',
    '测试128KB': 'Probar 128KB',
    '切换到SRAM Bank ': 'Cambiando al banco SRAM ',
    'SRAM全量测试失败于地址 0x': 'Fallo en la prueba completa de SRAM en la dirección 0x',
    'SRAM全量测试通过(128KB)': 'Prueba completa de SRAM superada (128KB)',
    'SRAM全量测试: ': 'Prueba completa de SRAM: ',
    '快速Flash质检(首尾4M+随机8M)': 'Control rápido de Flash (4M iniciales y finales + 8M aleatorios)',
    '快速Flash质检通过(16MB)': 'Control rápido de Flash superado (16MB)',
    '尾4M': 'Últimos 4M',
    '已擦除 ': 'Borrados ',
    ' 个扇区 (从扇区 ': ' sectores (desde el sector ',
    '需要擦除 ': 'Hay que borrar ',
    '扇区大小: ': 'Tamaño de sector: ',
    ' 字节, Buffer大小: ': ' bytes, tamaño de buffer: ',
    ' 扇区': ' sectores',
    ' 字节': ' bytes',
    '验证擦除结果...': 'Verificando el resultado del borrado...',
    '验证擦除结果': 'Verificar el resultado del borrado',
    'Flash擦除验证失败于地址 0x': 'Falló la verificación del borrado de Flash en la dirección 0x',
    '全片擦除查空': 'Borrado total y verificación de vacío',
    'Flash不为空，执行全片擦除...': 'La Flash no está vacía, ejecutando borrado total...',
    'Flash擦除完成': 'Borrado de Flash completado',
    'Flash已为空': 'La Flash ya está vacía',
    '质检完成': 'Control de calidad completado',
    '质检失败: ': 'Falló el control de calidad: ',
    '开始重置NOR游戏...': 'Iniciando reinicio de juegos NOR...',
    '设置Flash映射完成': 'Mapeo de Flash configurado',
    '解锁Flash PPB保护...': 'Desbloqueando la protección PPB de Flash...',
    '正在擦除Flash元数据区域(2MB)...': 'Borrando la zona de metadatos de Flash (2MB)...',
    '擦除Flash元数据区域': 'Borrar la zona de metadatos de Flash',
    'Flash元数据区域擦除验证失败': 'Falló la verificación del borrado de la zona de metadatos de Flash',
    '重置NOR游戏完成': 'Reinicio de juegos NOR completado',
    '重置NOR游戏失败: ': 'Falló el reinicio de juegos NOR: ',
    '开始备份Flash...': 'Iniciando respaldo de Flash...',
    'Flash大小: ': 'Tamaño de Flash: ',
    '备份大小: ': 'Tamaño del respaldo: ',
    '切换映射到段 ': 'Cambiando el mapeo al segmento ',
    '已备份 ': 'Respaldados ',
    '备份已取消': 'Respaldo cancelado',
    '备份完成': 'Respaldo completado',
    '备份失败: ': 'Falló el respaldo: ',
    '开始量产...': 'Iniciando producción...',
    'ROM文件大小: ': 'Tamaño del archivo ROM: ',
    '检查Flash内容...': 'Comprobando el contenido de Flash...',
    '发现不一致位置: 0x': 'Diferencia encontrada en: 0x',
    '已检查 ': 'Comprobados ',
    '量产已取消': 'Producción cancelada',
    'Flash内容与ROM文件完全一致，跳过写入': 'El contenido de Flash es idéntico a la ROM, se omite la escritura',
    '从地址 0x': 'Desde la dirección 0x',
    ' 开始擦除写入...': ' se inicia el borrado y la escritura...',
    '擦除已取消': 'Borrado cancelado',
    ' (映射偏移: ': ' (desplazamiento de mapeo: ',
    '擦除完成，开始写入...': 'Borrado completado, iniciando escritura...',
    '写入失败于地址 0x': 'Falló la escritura en la dirección 0x',
    '(段': '(segmento ',
    ', 偏移0x': ', desplazamiento 0x',
    '已写入 ': 'Escritos ',
    '写入完成，开始校验...': 'Escritura completada, iniciando verificación...',
    '校验失败于地址 0x': 'Falló la verificación en la dirección 0x',
    '已校验 ': 'Verificados ',
    '量产完成': 'Producción completada',
    '量产失败: ': 'Falló la producción: ',
    'Flash全片擦除查空': 'Borrado total de Flash y verificación',
    'SRAM全量检测(128KB)': 'Prueba SRAM completa (128KB)',
    'Flash快速质检(16MB)': 'Control rápido de Flash (16MB)',
    '功能说明': 'Descripción de funciones',
    'SRAM基础：</b>快速测试SRAM Bank0前4字节': 'SRAM básica:</b> prueba rápida de los primeros 4 bytes del banco 0',
    'SRAM全量：</b>完整测试128KB SRAM': 'SRAM completa:</b> prueba completa de los 128KB de SRAM',
    'Flash全片擦除：</b>检查并擦除整个Flash': 'Borrado total de Flash:</b> comprueba y borra toda la Flash',
    'Flash快速质检：</b>仅擦除首尾4M+随机8M(共16MB)': 'Control rápido de Flash:</b> borra solo 4M iniciales y finales + 8M aleatorios (16MB)',
    'PPB解锁：</b>解除Flash写保护': 'Desbloqueo PPB:</b> quita la protección contra escritura de Flash',
    'RAM Flash：</b>测试RAM接口访问Flash': 'RAM Flash:</b> prueba el acceso a Flash por la interfaz RAM',
    '控制面板': 'Panel de control',
    '未选择ROM文件': 'Ninguna ROM seleccionada',
    '选择ROM文件': 'Elegir archivo ROM',
    '连接所有设备': 'Conectar todos',
    '断开所有设备': 'Desconectar todos',
    '批量质检': 'Control en lote',
    '批量量产': 'Producción en lote',
    '重置NOR游戏': 'Reiniciar juegos NOR',
    '备份Flash': 'Respaldar Flash',
    '设备列表': 'Lista de dispositivos',
    '全局日志': 'Registro global',
    'Flash全片擦除: ': 'Borrado total de Flash: ',
    'Flash快速质检: ': 'Control rápido de Flash: ',
    'PPB解锁: ': 'Desbloqueo PPB: ',
    '已选择ROM文件: ': 'ROM seleccionada: ',
    '已选择: ': 'Seleccionado: ',
    '发现新设备: ': 'Dispositivo nuevo encontrado: ',
    '是否完全重建表格（包括widget）': 'si se reconstruye la tabla por completo (incluidos los widgets)',
    '连接成功': 'conexión exitosa',
    '连接失败': 'Conexión fallida',
    ' 已断开': ' desconectado',
    ' 未连接': ' no está conectado',
    '请先选择ROM文件': 'Primero elija un archivo ROM',
    '确认操作': 'Confirmar operación',
    '确定要重置 ': '¿Seguro que desea reiniciar los juegos NOR de ',
    ' 的NOR游戏吗?\n\n这将擦除Flash元数据区域(2MB),操作不可逆!': '?\n\nSe borrará la zona de metadatos de Flash (2MB). ¡La operación es irreversible!',
    '确定要对所有已连接设备重置NOR游戏吗?\n\n这将擦除所有设备的Flash元数据区域(2MB),操作不可逆!': '¿Seguro que desea reiniciar los juegos NOR de todos los dispositivos conectados?\n\nSe borrará la zona de metadatos de Flash (2MB) de todos los dispositivos. ¡La operación es irreversible!',
    '保存Flash备份': 'Guardar respaldo de Flash',
    '选择备份保存目录': 'Elegir directorio para los respaldos',
    '开始备份 ': 'Iniciando respaldo de ',
    ' 到 {backup_file}': ' en {backup_file}',
    '正在关闭程序...': 'Cerrando el programa...',
    '强制终止 ': 'Forzando el cierre del hilo de ',
    ' 的线程': '',
    '程序已关闭': 'Programa cerrado',
    '启用': 'activado',
    '禁用': 'desactivado',
}

TABLES = {"es": (EXACT, FRAGMENTS)}


def set_language(lang: str):
    global _lang
    _lang = lang if lang in LANGUAGES else "zh"


def get_language() -> str:
    return _lang


def tr(text: str) -> str:
    """Traduce `text` (chino) al idioma activo. Si no hay traducción, lo devuelve igual."""
    if _lang == "zh" or not text or not _CJK.search(text):
        return text
    exact, fragments = TABLES[_lang]
    if text in exact:
        return exact[text]
    for key in sorted(fragments, key=len, reverse=True):
        if key in text:
            text = text.replace(key, fragments[key])
    for k, v in _FULLWIDTH.items():
        text = text.replace(k, v)
    return text


class LanguageDialog(QDialog):
    """Diálogo de selección de idioma al iniciar."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Language / 语言 / Idioma")
        self.selected = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select language / 选择语言 / Seleccione el idioma"))
        row = QHBoxLayout()
        for code, name in LANGUAGES.items():
            btn = QPushButton(name)
            btn.setMinimumHeight(40)
            btn.clicked.connect(lambda _=False, c=code: self._choose(c))
            row.addWidget(btn)
        layout.addLayout(row)
        self.remember = QCheckBox("Remember / 记住 / Recordar")
        self.remember.setChecked(True)
        layout.addWidget(self.remember)

    def _choose(self, code):
        self.selected = code
        self.accept()


def _settings() -> QSettings:
    return QSettings("chismaker", "chismaker")


def reset_saved_language():
    _settings().remove("language")


def init_language(argv=None) -> None:
    """Determina el idioma: --lang XX > preferencia guardada > diálogo de selección."""
    argv = sys.argv if argv is None else argv
    for i, arg in enumerate(argv):
        if arg.startswith("--lang="):
            set_language(arg.split("=", 1)[1])
            return
        if arg == "--lang" and i + 1 < len(argv):
            set_language(argv[i + 1])
            return
    saved = _settings().value("language")
    if saved in LANGUAGES:
        set_language(saved)
        return
    dlg = LanguageDialog()
    if dlg.exec() and dlg.selected:
        set_language(dlg.selected)
        if dlg.remember.isChecked():
            _settings().setValue("language", dlg.selected)
    else:
        set_language("zh")
