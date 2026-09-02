[app]
title = RebañoEjecutivo
package.name = rebanoejecutivo
package.domain = com.rebanoejecutivo.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 1.0
icon.filename = %(source.dir)s/icon.png

# Se eliminaron las versiones fijas de python3/hostpython3
requirements = python3,kivy,requests

orientation = portrait
fullscreen = 0

# Permisos y APIs
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

# Permitir URLs HTTP no seguras si ejecutas consultas externas
android.uses_cleartext_traffic = true

[buildozer]
log_level = 2
warn_on_root = 1
