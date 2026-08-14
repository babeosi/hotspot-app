[app]
title = HotspotSecure
package.name = hotspotsecure
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,conf
version = 1.0.0
requirements = python3,kivy,pyjnius,scapy,mitmproxy,cryptography,qrcode,pillow
orientation = portrait
fullscreen = 0
android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, CHANGE_WIFI_STATE, WRITE_SETTINGS, ACCESS_COARSE_LOCATION, ACCESS_FINE_LOCATION, READ_EXTERNAL_STORAGE
android.api = 30
android.minapi = 21
android.gradle_dependencies =
android.manifest.extra_android = <uses-feature android:name="android.hardware.wifi" android:required="true" />
[buildozer]
log_level = 2
warn_on_root = 0
