[app]
title = RebañoEjecutivo
package.name = rebanoejecutivo
package.domain = com.rebanoejecutivo.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,requests

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.arch = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
