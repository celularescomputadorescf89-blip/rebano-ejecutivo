import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.clock import Clock
from kivy.uix.spinner import Spinner
from kivy.uix.accordion import Accordion, AccordionItem
import smtplib
from email.mime.text import MIMEText
import requests
import json
from datetime import datetime, timedelta
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
import random
import re
import csv
from kivy.uix.anchorlayout import AnchorLayout
from kivy.storage.jsonstore import JsonStore
import hashlib
import webbrowser
from kivy.core.text import LabelBase
import threading

# ========================
# CONFIGURACIÓN DE FUENTE
# ========================
KIVY_FONT_FAMILY = None

# ========================
# 🙂 FUENTE PARA EMOJIS
# ========================
EMOJI_FONT_NAME = 'NotoEmoji'
EMOJI_FONT_AVAILABLE = os.path.exists('NotoEmoji-Regular.ttf')
if EMOJI_FONT_AVAILABLE:
    LabelBase.register(name=EMOJI_FONT_NAME, fn_regular='NotoEmoji-Regular.ttf')

def _split_emoji_prefix(texto):
    """Separa un emoji (o grupo de símbolos) al inicio del texto, si existe."""
    if not texto:
        return None, texto
    i = 0
    while i < len(texto) and ord(texto[i]) > 0x2000 and texto[i] != ' ':
        i += 1
    if i == 0:
        return None, texto
    return texto[:i], texto[i:].lstrip()

# ========================
# CONFIGURACIÓN VISUAL
# ========================
Window.clearcolor = get_color_from_hex('#000000')
Window.softinput_mode = 'below_target'
BLACK = '#000000'
WHITE = '#FFFFFF'
BLUE = '#1976D2'
DARK_BLUE = '#0D47A1'
LIGHT_BLUE = '#BBDEFB'
GRAY = '#757575'
RED = '#D32F2F'
GREEN = '#388E3C'
YELLOW = '#FFEB3B'
ORANGE = '#FF9800'

# ========================
# 🔥 CONFIGURACIÓN DE FIREBASE (TU PROYECTO)
# ========================
FIREBASE_URL = "https://redilejecutivo-d2bbc-default-rtdb.firebaseio.com"

# ========================
# 📧 CONFIGURACIÓN DE CORREO (PARA RECUPERAR CONTRASEÑA)
# Reemplaza estos dos valores con tu propia cuenta de Gmail
# y una "Contraseña de aplicación" generada en:
# https://myaccount.google.com/apppasswords
# ========================
SMTP_EMAIL = "redilejecutivo@gmail.com"
SMTP_PASSWORD = "pljd yuda gvrv gaqk"

def enviar_correo(destinatario, asunto, cuerpo, on_complete):
    def run():
        try:
            msg = MIMEText(cuerpo)
            msg['Subject'] = asunto
            msg['From'] = SMTP_EMAIL
            msg['To'] = destinatario

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.sendmail(SMTP_EMAIL, [destinatario], msg.as_string())
            Clock.schedule_once(lambda dt: on_complete(True, None), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: on_complete(False, str(e)), 0)
    threading.Thread(target=run).start()

# --- NUEVAS FUNCIONES PARA EL MANEJO DE LA CONEXIÓN Y LA CACHÉ ---
class NetworkStatus:
    _connected = True
    _last_check = None

    @staticmethod
    def check_connection():
        now = datetime.now()
        if NetworkStatus._last_check and (now - NetworkStatus._last_check).total_seconds() < 10:
            return NetworkStatus._connected
        try:
            requests.get("https://www.google.com", timeout=5)
            NetworkStatus._connected = True
        except requests.exceptions.RequestException:
            NetworkStatus._connected = False
        NetworkStatus._last_check = now
        return NetworkStatus._connected

class DataCache:
    def __init__(self):
        self.store = JsonStore('app_data.json')
        self.data = {
            'usuarios': {},
            'ovejas': {},
            'seguimientos': {},
            'chat': {},
            'offline_seguimientos': {}
        }
        self.load_from_storage()
        Clock.schedule_interval(self.sync_offline_data, 30)

    def load_from_storage(self):
        for key in self.data.keys():
            if self.store.exists(key):
                self.data[key] = self.store.get(key)['data']

    def save_to_storage(self):
        for key, value in self.data.items():
            self.store.put(key, data=value)

    def get(self, key):
        return self.data.get(key, {})

    def sync_all(self):
        if not NetworkStatus.check_connection():
            return False
        
        try:
            self.data['usuarios'] = requests.get(f"{FIREBASE_URL}/usuarios.json").json() or {}
            self.data['ovejas'] = requests.get(f"{FIREBASE_URL}/ovejas.json").json() or {}
            self.data['seguimientos'] = requests.get(f"{FIREBASE_URL}/seguimientos.json").json() or {}
            self.data['chat'] = requests.get(f"{FIREBASE_URL}/chat.json").json() or {}
            self.save_to_storage()
            self.sync_offline_data()
            return True
        except Exception as e:
            print(f"[ERROR] Sync failed: {e}")
            return False
            
    def save_offline_seguimiento(self, data):
        temp_id = str(random.randint(1000, 9999))
        self.data['offline_seguimientos'][temp_id] = data
        self.save_to_storage()
        return temp_id

    def sync_offline_data(self, dt=None):
        if not NetworkStatus.check_connection() or not self.data['offline_seguimientos']:
            return
        
        exitosos = []
        for temp_id, data in self.data['offline_seguimientos'].items():
            print(f"Intentando sincronizar seguimiento offline: {temp_id}")
            new_id = firebase_post_sync("seguimientos", data)
            if new_id:
                oveja_id = data.get('oveja_id')
                oveja_actual = self.get('ovejas').get(oveja_id)
                if oveja_actual:
                    oveja_actual['observaciones'] = data['contenido']
                    oveja_actual['fecha_ultimo_seguimiento'] = data['fecha_seguimiento']
                    firebase_put_sync(f"ovejas/{oveja_id}", oveja_actual)
                    self.data['ovejas'][oveja_id] = oveja_actual
                
                data['id'] = new_id
                self.data['seguimientos'][new_id] = data
                exitosos.append(temp_id)
            else:
                print(f"Falló la sincronización de {temp_id}.")

        for temp_id in exitosos:
            del self.data['offline_seguimientos'][temp_id]

        if exitosos:
            print("Sincronización offline completada.")
            self.save_to_storage()
            mostrar_popup_exito(f"✅ Se sincronizaron {len(exitosos)} seguimientos pendientes.")

class PushNotification:
    @staticmethod
    def send(user_id, title, message):
        print(f"Notificación enviada a {user_id}: {title} - {message}")

# --- Funciones de Firebase refactorizadas para usar threading y callbacks ---
def handle_firebase_request(method, path, data=None, on_success=None, on_error=None):
    def run_request():
        if not NetworkStatus.check_connection():
            if on_error:
                Clock.schedule_once(lambda dt: on_error("❌ No hay conexión a internet."), 0)
            return
        
        try:
            url = f"{FIREBASE_URL}/{path}.json"
            if method == "PUT":
                response = requests.put(url, data=json.dumps(data))
            elif method == "GET":
                response = requests.get(url)
            elif method == "POST":
                response = requests.post(url, data=json.dumps(data))
            elif method == "DELETE":
                response = requests.delete(url)
            else:
                if on_error:
                    Clock.schedule_once(lambda dt: on_error("Método no soportado."), 0)
                return

            if response.status_code == 200:
                if on_success:
                    Clock.schedule_once(lambda dt: on_success(response.json()), 0)
            else:
                print(f"[ERROR] Firebase {method} error: {response.text}")
                if on_error:
                    Clock.schedule_once(lambda dt: on_error(f"❌ Error en la comunicación con el servidor. Código: {response.status_code}"), 0)
        except Exception as e:
            print(f"[ERROR] Firebase {method}: {e}")
            if on_error:
                Clock.schedule_once(lambda dt: on_error("❌ Error en la comunicación con el servidor."), 0)

    threading.Thread(target=run_request).start()

def firebase_put(path, data, on_complete):
    handle_firebase_request("PUT", path, data, on_success=lambda res: on_complete(True, res), on_error=lambda err: on_complete(False, err))

def firebase_get(path, on_complete):
    handle_firebase_request("GET", path, on_success=lambda res: on_complete(True, res), on_error=lambda err: on_complete(False, err))

def firebase_post(path, data, on_complete):
    handle_firebase_request("POST", path, data, on_success=lambda res: on_complete(True, res), on_error=lambda err: on_complete(False, err))

def firebase_delete(path, on_complete):
    handle_firebase_request("DELETE", path, on_success=lambda res: on_complete(True, res), on_error=lambda err: on_complete(False, err))

# Versiones síncronas para uso específico (por ejemplo, en el sync offline)
def firebase_put_sync(path, data):
    try:
        requests.put(f"{FIREBASE_URL}/{path}.json", data=json.dumps(data)).raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

def firebase_post_sync(path, data):
    try:
        response = requests.post(f"{FIREBASE_URL}/{path}.json", data=json.dumps(data))
        response.raise_for_status()
        return response.json().get("name")
    except requests.exceptions.RequestException:
        return None

def firebase_get_sync(path):
    try:
        response = requests.get(f"{FIREBASE_URL}/{path}.json")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

def firebase_delete_sync(path):
    try:
        requests.delete(f"{FIREBASE_URL}/{path}.json").raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

# ========================
# GRUPOS Y OPCIONES
# ========================
GRUPOS_PEQUENOS = [
    "CASADOS", "Mujer Integral", "TMT (13-24 años)",
    "J+25 (25-34 años)", "Josués (35-55 años)",
    "Años Dorados", "Hombres de Bien", "Otros"
]
ROLES = ["lider", "director"]
GENEROS = ["hombre", "mujer"]
BAUTIZADO = ["sí", "no"]
PLANTILLAS = [
    "Oramos juntos por tu vida espiritual",
    "Hablamos de tu salud emocional",
    "Te animé en tu trabajo",
    "Te invite a la predica",
    "Oramos por tu familia",
    "compartimos palabra biblica",
    "Estamos orando por tu sanidad",
    "Gracias por tu fidelidad",
    "consegueria"
]

# ========================
# 🔆 BOXLAYOUT CON FONDO AJUSTADO A PANTALLA
# ========================
class BoxLayoutBG(BoxLayout):
    def __init__(self, bg_image=None, bg_color=None, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color or BLACK
        self.bg_image = bg_image
        
        with self.canvas.before:
            if self.bg_image and os.path.exists(self.bg_image):
                self.bg_rect = Rectangle(size=self.size, pos=self.pos, source=self.bg_image)
            else:
                Color(*get_color_from_hex(self.bg_color))
                self.bg_rect = Rectangle(pos=self.pos, size=self.size)

        self.bind(pos=self.update_bg, size=self.update_bg)

    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

# ========================
# FUNCIONES DE APOYO
# ========================
def crear_label(texto, **kwargs):
    if KIVY_FONT_FAMILY:
        kwargs['font_name'] = kwargs.get('font_name', KIVY_FONT_FAMILY)
    return Label(text=texto, **kwargs)

def crear_button(texto, **kwargs):
    if KIVY_FONT_FAMILY:
        kwargs['font_name'] = kwargs.get('font_name', KIVY_FONT_FAMILY)
    return Button(text=texto, **kwargs)

def crear_input(hint, password=False, multiline=False, text=None, input_filter=None):
    input_kwargs = {
        'hint_text': hint,
        'background_color': get_color_from_hex('#333333'),
        'foreground_color': get_color_from_hex(WHITE),
        'hint_text_color': get_color_from_hex('#AAAAAA'),
        'padding': dp(10),
        'password': password,
        'multiline': multiline,
        'size_hint_y': None,
        'height': dp(50) if not multiline else dp(100),
        'font_size': '14sp',
    }
    
    if KIVY_FONT_FAMILY:
        input_kwargs['font_name'] = KIVY_FONT_FAMILY
    
    if input_filter:
        input_kwargs['input_filter'] = input_filter

    input_field = TextInput(**input_kwargs)
    
    if text is not None:
        input_field.text = text
    return input_field
    
def mostrar_popup_exito(mensaje, on_dismiss=None, markup=False):
    content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
    content.add_widget(crear_label(mensaje, color=get_color_from_hex(WHITE), halign='center', markup=markup))
    btn = crear_boton("Aceptar", GREEN, size_hint_y=None, alpha=1)
    content.add_widget(btn)
    popup = Popup(title='Éxito', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.8, 0.4))
    if on_dismiss:
        popup.bind(on_dismiss=on_dismiss)
    btn.bind(on_press=popup.dismiss)
    popup.open()

def mostrar_popup_error(mensaje):
    content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
    content.add_widget(crear_label(mensaje, color=get_color_from_hex(WHITE), halign='center'))
    btn = crear_boton("✖ Cerrar", RED, size_hint_y=None, alpha=1)
    content.add_widget(btn)
    popup = Popup(title='Error', content=content, background_color=get_color_from_hex(RED), size_hint=(0.8, 0.4))
    btn.bind(on_press=popup.dismiss)
    popup.open()

def crear_titulo(texto, color=YELLOW):
    return crear_label(
        texto,
        color=get_color_from_hex(color),
        font_size='20sp',
        bold=True,
        size_hint_y=None,
        height=dp(40)
    )

class BotonRedondeado(Button):
    """Botón con esquinas totalmente redondeadas (forma ovalada/píldora)."""
    def __init__(self, rgba_color=(0.2, 0.4, 0.8, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.background_down = ''
        self.rgba_color = rgba_color
        with self.canvas.before:
            self.color_instr = Color(*self.rgba_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(24)])
        self.bind(pos=self._actualizar_rect, size=self._actualizar_rect)

    def _actualizar_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        self.rect.radius = [min(self.height, dp(30)) / 2]


def crear_boton(texto, color_hex, on_press=None, size_hint_y=None, alpha=1.0):
    """
    Crea un botón ovalado con color de fondo y transparencia personalizables.
    Si el texto empieza con un emoji y la fuente de emojis está disponible,
    el emoji se dibuja con esa fuente y el resto del texto con la fuente normal.
    """
    color = get_color_from_hex(color_hex)
    rgba_color = (color[0], color[1], color[2], alpha)

    emoji_char, texto_limpio = _split_emoji_prefix(texto)
    markup = False
    display_text = texto
    if emoji_char and EMOJI_FONT_AVAILABLE:
        display_text = f"[font={EMOJI_FONT_NAME}]{emoji_char}[/font] {texto_limpio}"
        markup = True
    elif emoji_char and not EMOJI_FONT_AVAILABLE:
        display_text = texto_limpio

    btn = BotonRedondeado(
        text=display_text,
        markup=markup,
        rgba_color=rgba_color,
        color=get_color_from_hex(WHITE),
        size_hint_y=size_hint_y or None,
        height=dp(45),
        font_size='14sp'
    )
    if on_press:
        btn.bind(on_press=on_press)
    return btn

# --- POPUP DE CALENDARIO REUTILIZABLE (con spinners seleccionables) ---
class CalendarPopup(Popup):
    def __init__(self, on_date_select, **kwargs):
        super().__init__(title='Selecciona una fecha', size_hint=(0.9, 0.7), **kwargs)
        self.on_date_select = on_date_select
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        anos = [str(a) for a in range(2025, 1899, -1)]
        meses = [f"{m:02d}" for m in range(1, 13)]
        dias = [f"{d:02d}" for d in range(1, 32)]

        content.add_widget(crear_label("Año", color=get_color_from_hex(WHITE), size_hint_y=None, height=dp(25)))
        self.spinner_year = Spinner(text=anos[0], values=anos, size_hint_y=None, height=dp(45))
        content.add_widget(self.spinner_year)

        content.add_widget(crear_label("Mes", color=get_color_from_hex(WHITE), size_hint_y=None, height=dp(25)))
        self.spinner_month = Spinner(text=meses[0], values=meses, size_hint_y=None, height=dp(45))
        content.add_widget(self.spinner_month)

        content.add_widget(crear_label("Día", color=get_color_from_hex(WHITE), size_hint_y=None, height=dp(25)))
        self.spinner_day = Spinner(text=dias[0], values=dias, size_hint_y=None, height=dp(45))
        content.add_widget(self.spinner_day)

        btn_guardar = crear_boton("💾 Guardar Fecha", GREEN, self.save_date)
        btn_cancel = crear_boton("✖ Cancelar", GRAY, self.dismiss)
        content.add_widget(btn_guardar)
        content.add_widget(btn_cancel)
        self.content = content

    def save_date(self, *args):
        try:
            y = int(self.spinner_year.text)
            m = int(self.spinner_month.text)
            d = int(self.spinner_day.text)
            self.on_date_select(f"{y:04d}-{m:02d}-{d:02d}")
            self.dismiss()
        except:
            mostrar_popup_error("Selecciona una fecha válida")

def abrir_cambiar_contrasena(*args):
    app = App.get_running_app()
    content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
    content.add_widget(crear_label("Cambiar Contraseña", bold=True, color=get_color_from_hex(WHITE)))
    input_actual = crear_input("Contraseña actual", password=True)
    input_nueva = crear_input("Nueva contraseña", password=True)
    input_confirmar = crear_input("Confirmar nueva contraseña", password=True)
    content.add_widget(input_actual)
    content.add_widget(input_nueva)
    content.add_widget(input_confirmar)

    def procesar(*a):
        actual = input_actual.text.strip()
        nueva = input_nueva.text.strip()
        confirmar = input_confirmar.text.strip()

        if not actual or not nueva or not confirmar:
            mostrar_popup_error("Completa todos los campos")
            return
        if len(nueva) < 6:
            mostrar_popup_error("La nueva contraseña debe tener al menos 6 caracteres")
            return
        if nueva != confirmar:
            mostrar_popup_error("Las contraseñas nuevas no coinciden")
            return

        def on_get(success, data):
            if not success:
                mostrar_popup_error(data)
                return
            user = (data or {}).get(app.user_id)
            if not user:
                mostrar_popup_error("Usuario no encontrado")
                return
            hash_actual = hashlib.sha256(actual.encode('utf-8')).hexdigest()
            if hash_actual != user.get('contraseña'):
                mostrar_popup_error("La contraseña actual no es correcta")
                return

            user['contraseña'] = hashlib.sha256(nueva.encode('utf-8')).hexdigest()

            def on_put(success2, response2):
                if success2:
                    popup.dismiss()
                    mostrar_popup_exito("✅ Contraseña actualizada correctamente")
                else:
                    mostrar_popup_error(f"❌ Error al actualizar: {response2}")

            firebase_put(f"usuarios/{app.user_id}", user, on_complete=on_put)

        firebase_get("usuarios", on_complete=on_get)

    btn_guardar = crear_boton("💾 Guardar", GREEN, procesar, alpha=0.8)
    btn_cancel = crear_boton("✖ Cancelar", GRAY, lambda x: popup.dismiss(), alpha=0.8)
    content.add_widget(btn_guardar)
    content.add_widget(btn_cancel)
    popup = Popup(title='Cambiar Contraseña', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.7))
    popup.open()


# ========================
# PANTALLAS
# ========================
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayoutBG(bg_image='login_background.png', orientation='vertical', padding=dp(30), spacing=dp(20))
        layout.add_widget(crear_label("RebañoEjecutivo", color=get_color_from_hex(YELLOW), font_size='28sp', bold=True, halign='center', size_hint_y=None, height=dp(50)))
        layout.add_widget(crear_label("Sistema de Pastoreo", color=get_color_from_hex(GRAY), font_size='16sp', halign='center', size_hint_y=None, height=dp(30)))
        self.username = crear_input("Nombre de usuario")
        self.password = crear_input("Contraseña", password=True)
        layout.add_widget(self.username)
        layout.add_widget(self.password)
        btn_login = crear_boton("🔐 Iniciar Sesión", BLUE, alpha=0.8)
        btn_login.bind(on_press=self.start_login)
        btn_register = crear_boton("📝 Crear Cuenta", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'register'), alpha=0.8)
        btn_recuperar = crear_boton("🔑 ¿Olvidaste tu contraseña?", GRAY, self.recuperar_contrasena, alpha=0.5)
        
        self.spinner = Spinner(text="Loading...", size_hint=(None, None), size=(dp(100), dp(50)), pos_hint={'center_x': 0.5}, opacity=0)
        
        layout.add_widget(btn_login)
        layout.add_widget(btn_register)
        layout.add_widget(btn_recuperar)
        layout.add_widget(self.spinner)
        self.add_widget(layout)
    
    def start_login(self, *args):
        self.spinner.opacity = 1
        username = self.username.text.strip()
        password = self.password.text.strip()
        if not username or not password:
            self.spinner.opacity = 0
            mostrar_popup_error("Completa todos los campos")
            return
        
        def on_login_complete(success, data):
            self.spinner.opacity = 0
            if success:
                for uid, user in data.items():
                    if user.get("nombre_usuario") == username:
                        hashed_input_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
                        if hashed_input_password == user.get("contraseña"):
                            app = App.get_running_app()
                            app.user_id = uid
                            app.nombre = user["nombre"]
                            app.rol = user["rol"]
                            app.store.put('user_session', id=uid, nombre=user["nombre"], rol=user["rol"])
                            self.manager.current = 'menu_principal'
                            app.data_cache.sync_all()
                            return
                mostrar_popup_error("Usuario o contraseña incorrectos")
            else:
                mostrar_popup_error(data)
        
        firebase_get("usuarios", on_complete=on_login_complete)

    def recuperar_contrasena(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label("Recuperar Contraseña", bold=True, color=get_color_from_hex(WHITE)))
        content.add_widget(crear_label("Ingresa tu nombre de usuario o correo", color=get_color_from_hex(GRAY)))
        input_recuperar = crear_input("Usuario o correo")
        content.add_widget(input_recuperar)

        estado = {"nueva_contrasena": None, "correo_destino": None}

        def correo_callback(success, error):
            if success:
                mostrar_popup_exito(f"✅ Hemos enviado tu nueva contraseña a:\n{estado['correo_destino']}\n\nRevisa tu bandeja de entrada (y la carpeta de spam).")
            else:
                mostrar_popup_error(f"❌ La contraseña se restableció pero no se pudo enviar el correo.\n\nDetalle: {error}")

        def reset_callback(success, response):
            if success:
                enviar_correo(
                    destinatario=estado['correo_destino'],
                    asunto="Recuperación de contraseña - RebañoEjecutivo",
                    cuerpo=f"Hola,\n\nTu nueva contraseña temporal es: {estado['nueva_contrasena']}\n\nPor favor inicia sesión con ella y considera cambiarla luego.\n\n- RebañoEjecutivo",
                    on_complete=correo_callback
                )
            else:
                mostrar_popup_error(f"❌ Error al restablecer la contraseña: {response}")

        def buscar_callback(success, data):
            if not success:
                popup.dismiss()
                mostrar_popup_error(data)
                return

            valor = input_recuperar.text.strip()
            for uid, user in data.items():
                if user.get("nombre_usuario") == valor or user.get("correo") == valor:
                    correo_usuario = user.get("correo")
                    if not correo_usuario:
                        popup.dismiss()
                        mostrar_popup_error("Este usuario no tiene un correo electrónico registrado.")
                        return
                    nueva = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
                    estado["nueva_contrasena"] = nueva
                    estado["correo_destino"] = correo_usuario
                    user['contraseña'] = hashlib.sha256(nueva.encode('utf-8')).hexdigest()
                    popup.dismiss()
                    firebase_put(f"usuarios/{uid}", user, on_complete=reset_callback)
                    return
            popup.dismiss()
            mostrar_popup_error("Usuario o correo no encontrado")

        def buscar_trigger(*args):
            valor = input_recuperar.text.strip()
            if not valor:
                mostrar_popup_error("Ingresa un usuario o correo")
                return
            firebase_get("usuarios", on_complete=buscar_callback)

        btn_buscar = crear_boton("🔄 Restablecer", GREEN, buscar_trigger, alpha=0.8)
        btn_cancel = crear_boton("✖ Cancelar", GRAY, lambda x: popup.dismiss(), alpha=0.8)
        content.add_widget(btn_buscar)
        content.add_widget(btn_cancel)
        popup = Popup(title='Recuperar Contraseña', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.6))
        self.popup_recuperar = popup
        popup.open()

class RegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.genero = None
        self.rol = None
        layout = BoxLayoutBG(bg_image='register_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        
        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll_layout = BoxLayout(orientation='vertical', padding=dp(0), spacing=dp(15), size_hint_y=None)
        scroll_layout.bind(minimum_height=scroll_layout.setter('height'))
        
        scroll_layout.add_widget(crear_titulo("Registro de Usuario"))
        self.username = crear_input("Nombre de usuario")
        self.email = crear_input("Correo electrónico")
        self.password = crear_input("Contraseña")
        self.confirm = crear_input("Confirmar contraseña")
        self.nombre = crear_input("Nombre")
        self.fecha = crear_input("Fecha nac. (AAAA-MM-DD)")
        self.tel = crear_input("Teléfono")
        self.cedula = crear_input("Cédula/ID")
        self.ministerio = crear_input("Ministerio")
        self.ministerio.text = "Ejecutivos"
        self.ministerio.readonly = True
        self.btn_genero = crear_boton("👤 Género: Seleccionar", LIGHT_BLUE, self.seleccionar_genero, alpha=0.5)
        self.btn_rol = crear_boton("🎭 Rol: Seleccionar", LIGHT_BLUE, self.seleccionar_rol, alpha=0.5)
        self.btn_fecha = crear_boton("📅 Elegir fecha de nacimiento", LIGHT_BLUE, self.abrir_calendario, alpha=0.5)

        for w in [self.username, self.email, self.password, self.confirm,
                  self.nombre, self.btn_fecha, self.tel, self.cedula, self.ministerio]:
            scroll_layout.add_widget(w)
        scroll_layout.add_widget(self.btn_genero)
        scroll_layout.add_widget(self.btn_rol)
        
        scroll_view.add_widget(scroll_layout)
        layout.add_widget(scroll_view)

        btn_reg = crear_boton("✅ Registrar", BLUE, self.registrar, alpha=0.8)
        btn_back = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'login'), alpha=0.8)
        layout.add_widget(btn_reg)
        layout.add_widget(btn_back)
        self.add_widget(layout)

    def seleccionar_genero(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("Selecciona el género", bold=True, color=get_color_from_hex(WHITE)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        for opcion in GENEROS:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_genero(op), alpha=0.8)
            grid.add_widget(btn)
        content.add_widget(grid)
        self.popup_genero_reg = Popup(title='Género', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_genero_reg.open()

    def set_genero(self, valor):
        self.genero = valor
        self.btn_genero.text = f"Género: {valor.upper()}"
        self.popup_genero_reg.dismiss()

    def seleccionar_rol(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("Selecciona el rol", bold=True, color=get_color_from_hex(WHITE)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        for opcion in ROLES:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_rol(op), alpha=0.8)
            grid.add_widget(btn)
        content.add_widget(grid)
        self.popup_rol = Popup(title='Rol', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_rol.open()

    def set_rol(self, valor):
        self.rol = valor
        self.btn_rol.text = f"Rol: {valor.upper()}"
        self.popup_rol.dismiss()


    def abrir_calendario(self, *args):
        popup = CalendarPopup(on_date_select=lambda date_str: setattr(self.fecha, 'text', date_str))
        popup.open()

    def registrar(self, *args):
        datos = {
            'nombre_usuario': self.username.text.strip(),
            'correo': self.email.text.strip(),
            'contraseña': self.password.text,
            'nombre': self.nombre.text.strip(),
            'fecha_nacimiento': self.fecha.text.strip(),
            'telefono': self.tel.text.strip(),
            'cedula': self.cedula.text.strip(),
            'ministerio': self.ministerio.text,
            'genero': self.genero,
            'rol': self.rol or "lider"
        }
        confirm = self.confirm.text
        errores = []
        if any(not v for v in [datos['nombre_usuario'], datos['correo'], datos['contraseña'], datos['nombre'], datos['fecha_nacimiento'], datos['telefono'], datos['cedula'], datos['ministerio']]):
            errores.append("Completa todos los campos obligatorios.")
        if datos['contraseña'] != confirm:
            errores.append("Las contraseñas no coinciden.")
        if len(datos['contraseña']) < 6:
            errores.append("La contraseña debe tener al menos 6 caracteres.")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", datos['correo']):
            errores.append("Formato de correo electrónico inválido.")
        if not datos['genero']:
            errores.append("Selecciona un género.")
        if not self.tel.text.isdigit() or not self.cedula.text.isdigit():
            errores.append("Teléfono y Cédula/ID deben ser numéricos.")
        if errores:
            mostrar_popup_error('\n'.join(errores))
            return
            
        datos['contraseña'] = hashlib.sha256(datos['contraseña'].encode('utf-8')).hexdigest()

        def on_register_complete(success, response):
            if success:
                mostrar_popup_exito("✅ Usuario registrado", on_dismiss=lambda x: setattr(self.manager, 'current', 'login'))
            else:
                mostrar_popup_error(f"❌ Error al registrar en Firebase: {response}")

        firebase_post("usuarios", datos, on_complete=on_register_complete)

class MenuPrincipalScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayoutBG(bg_image='menu_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        self.add_widget(self.layout)

    def construir_secciones(self, app):
        if app.rol == 'director':
            return [
                ("Ovejas", [
                    ("Registrar Oveja", 'registrar_oveja'),
                    ("Ver Todas las Ovejas", 'mis_ovejas'),
                    ("Reasignar Oveja", 'reasignar_oveja'),
                    ("Asignación Automática", 'asignacion_automatica'),
                    ("Importar Ovejas (CSV)", 'importar_ovejas'),
                ]),
                ("Seguimiento", [
                    ("Calendario de Seguimientos", 'calendario'),
                    ("Estadísticas", 'estadisticas'),
                    ("Hacer Seguimiento", 'seguimiento'),
                ]),
                ("Comunicación", [
                    ("Chat", 'chat'),
                ]),
                ("Administración", [
                    ("Gestionar Usuarios", 'gestionar_usuarios'),
                ]),
                ("Cuenta", [
                    ("Cambiar Contraseña", '__cambiar_password__'),
                ]),
            ]
        else:
            return [
                ("Ovejas", [
                    ("Registrar Oveja", 'registrar_oveja'),
                    ("Mis Ovejas", 'mis_ovejas'),
                ]),
                ("Seguimiento", [
                    ("Calendario", 'calendario'),
                    ("Estadísticas", 'estadisticas'),
                    ("Hacer Seguimiento", 'seguimiento'),
                ]),
                ("Comunicación", [
                    ("Chat", 'chat'),
                ]),
                ("Cuenta", [
                    ("Cambiar Contraseña", '__cambiar_password__'),
                ]),
            ]

    def on_enter(self):
        self.layout.clear_widgets()
        app = App.get_running_app()
        self.layout.add_widget(crear_titulo("Menú Principal"))

        accordion = Accordion(orientation='vertical', size_hint_y=1)

        secciones = self.construir_secciones(app)

        for titulo_seccion, opciones in secciones:
            item = AccordionItem(title=titulo_seccion)
            contenido = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8), size_hint_y=None)
            contenido.bind(minimum_height=contenido.setter('height'))
            for texto, destino in opciones:
                btn = crear_boton(texto, BLUE, alpha=0.8)
                if destino == '__cambiar_password__':
                    btn.bind(on_press=abrir_cambiar_contrasena)
                else:
                    btn.bind(on_press=lambda x, d=destino: setattr(self.manager, 'current', d))
                contenido.add_widget(btn)
            scroll = ScrollView()
            scroll.add_widget(contenido)
            item.add_widget(scroll)
            accordion.add_widget(item)

        self.layout.add_widget(accordion)

        btn_logout = crear_boton("🚪 Cerrar Sesión", DARK_BLUE, self.logout, alpha=0.8)
        self.layout.add_widget(btn_logout)

    def logout(self, instance):
        app = App.get_running_app()
        app.store.delete('user_session')
        app.user_id = None
        app.nombre = ""
        app.rol = ""
        self.manager.current = 'login'

class DashboardLiderScreen(Screen):
    def on_enter(self):
        self.clear_widgets()
        
        root_layout = AnchorLayout(anchor_x='center', anchor_y='center')
        content_layout = BoxLayoutBG(bg_image='dash_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        app = App.get_running_app()
        content_layout.add_widget(crear_titulo(f"Hola, {app.nombre}"))
        content_layout.add_widget(crear_titulo("Mi Dashboard", LIGHT_BLUE))
        
        ovejas_data = app.data_cache.get("ovejas")
        seguimientos_data = app.data_cache.get("seguimientos")
        lider_id = app.user_id
        
        mis_ovejas = [o for o in ovejas_data.values() if o.get('lider_id') == lider_id]
        
        num_ovejas = len(mis_ovejas)
        
        hoy = datetime.now().date()
        fecha_limite = hoy - timedelta(days=7)
        seguimientos_pendientes = 0
        for oveja in mis_ovejas:
            ultima_fecha_str = oveja.get("fecha_ultimo_seguimiento")
            if not ultima_fecha_str:
                seguimientos_pendientes += 1
                continue
            
            try:
                ultima_fecha = datetime.strptime(ultima_fecha_str, "%Y-%m-%d").date()
                if ultima_fecha < fecha_limite:
                    seguimientos_pendientes += 1
            except (ValueError, TypeError):
                seguimientos_pendientes += 1
                
        proximos_cumple = 0
        for oveja in mis_ovejas:
            try:
                fecha_nac_str = oveja.get('fecha_nacimiento')
                if fecha_nac_str:
                    fecha_nac = datetime.strptime(fecha_nac_str, "%Y-%m-%d").date()
                    cumple_este_año = fecha_nac.replace(year=hoy.year)
                    if cumple_este_año < hoy:
                        cumple_este_año = cumple_este_año.replace(year=hoy.year + 1)
                    
                    if timedelta(days=0) <= (cumple_este_año - hoy) <= timedelta(days=30):
                        proximos_cumple += 1
            except (ValueError, TypeError):
                pass
        
        content_layout.add_widget(self.crear_tarjeta_dashboard("Ovejas Asignadas", str(num_ovejas), WHITE, get_color_from_hex(YELLOW) + [0.5]))
        content_layout.add_widget(self.crear_tarjeta_dashboard("Seguimientos Pendientes", str(seguimientos_pendientes), WHITE, get_color_from_hex(RED) + [0.5]))
        content_layout.add_widget(self.crear_tarjeta_dashboard("Próximos Cumpleaños (30 días)", str(proximos_cumple), WHITE, get_color_from_hex(BLUE) + [0.5]))
        
        btn_volver_container = AnchorLayout(anchor_x='center', anchor_y='bottom', size_hint=(1, 0.1))
        btn_volver = crear_boton("Volver al Menú", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        btn_volver_container.add_widget(btn_volver)
        
        root_layout.add_widget(content_layout)
        root_layout.add_widget(btn_volver_container)
        
        self.add_widget(root_layout)
        
    def crear_tarjeta_dashboard(self, titulo, valor, color_texto, color_fondo):
        tarjeta = BoxLayout(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(5),
            size_hint_y=None,
            height=dp(150),
        )
        with tarjeta.canvas.before:
            Color(rgba=color_fondo)
            self.rect = Rectangle(pos=tarjeta.pos, size=tarjeta.size)
            tarjeta.bind(pos=self.update_rect, size=self.update_rect)
        
        tarjeta.add_widget(crear_label(titulo, color=get_color_from_hex(color_texto), font_size='18sp', bold=True))
        tarjeta.add_widget(crear_label(valor, color=get_color_from_hex(color_texto), font_size='48sp', bold=True))
        return tarjeta

    def update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

class RegistrarOvejaScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.genero = None
        self.bautizado = None
        self.grupo = None
        layout = BoxLayoutBG(bg_image='registrar_oveja_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        
        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll_layout = BoxLayout(orientation='vertical', padding=dp(0), spacing=dp(15), size_hint_y=None)
        scroll_layout.bind(minimum_height=scroll_layout.setter('height'))
        
        scroll_layout.add_widget(crear_titulo("Registrar Nueva Oveja"))
        self.nombre = crear_input("Nombre")
        self.fecha = crear_input("Fecha nac. (AAAA-MM-DD)")
        self.tel = crear_input("Teléfono")
        self.cedula = crear_input("Cédula/ID")
        self.tiempo = crear_input("Tiempo en la iglesia")
        self.empresa = crear_input("Empresa (opcional)")
        self.direccion = crear_input("Dirección (opcional)")
        self.btn_fecha = crear_boton("📅 Elegir fecha de nacimiento", LIGHT_BLUE, self.abrir_calendario, alpha=0.5)

        for w in [self.nombre, self.btn_fecha, self.tel, self.cedula, self.tiempo, self.empresa, self.direccion]:
            scroll_layout.add_widget(w)
            
        self.btn_genero = crear_boton("👤 Género: Seleccionar", LIGHT_BLUE, self.seleccionar_genero, alpha=0.5)
        self.btn_bautizado = crear_boton("✝ ¿Bautizado?: Seleccionar", LIGHT_BLUE, self.seleccionar_bautizado, alpha=0.5)
        self.btn_grupo = crear_boton("👥 Grupo pequeño: Seleccionar", LIGHT_BLUE, self.seleccionar_grupo, alpha=0.5)
        
        scroll_layout.add_widget(self.btn_genero)
        scroll_layout.add_widget(self.btn_bautizado)
        scroll_layout.add_widget(self.btn_grupo)
        
        btn_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(100), spacing=dp(10))
        btn_layout.add_widget(crear_boton("💾 Guardar", BLUE, self.guardar, alpha=0.8))
        btn_layout.add_widget(crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8))
        
        scroll_view.add_widget(scroll_layout)
        layout.add_widget(scroll_view)
        layout.add_widget(btn_layout)
        self.add_widget(layout)

    def abrir_calendario(self, *args):
        popup = CalendarPopup(on_date_select=lambda date_str: setattr(self.fecha, 'text', date_str))
        popup.open()

    def seleccionar_genero(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("Selecciona el género", bold=True, color=get_color_from_hex(WHITE)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        for opcion in GENEROS:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_genero(op), alpha=0.8)
            grid.add_widget(btn)
        content.add_widget(grid)
        self.popup_genero = Popup(title='Género', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_genero.open()

    def set_genero(self, valor):
        self.genero = valor
        self.btn_genero.text = f"Género: {valor.upper()}"
        self.popup_genero.dismiss()

    def seleccionar_bautizado(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("¿Está bautizado?", bold=True, color=get_color_from_hex(WHITE)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        for opcion in BAUTIZADO:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_bautizado(op), alpha=0.8)
            grid.add_widget(btn)
        content.add_widget(grid)
        self.popup_bautizado = Popup(title='¿Bautizado?', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_bautizado.open()

    def set_bautizado(self, valor):
        self.bautizado = valor
        self.btn_bautizado.text = f"¿Bautizado?: {valor.upper()}"
        self.popup_bautizado.dismiss()

    def seleccionar_grupo(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("Grupo Pequeño", bold=True, color=get_color_from_hex(WHITE)))
        
        scroll = ScrollView(size_hint_y=None, height=dp(300))
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
        grid.bind(minimum_height=grid.setter('height'))
        
        for opcion in GRUPOS_PEQUENOS:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_grupo(op), alpha=0.8)
            grid.add_widget(btn)
            
        scroll.add_widget(grid)
        content.add_widget(scroll)
        
        self.popup_grupo = Popup(title='Grupos', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_grupo.open()

    def set_grupo(self, valor):
        self.grupo = valor
        self.btn_grupo.text = f"Grupo: {valor}"
        self.popup_grupo.dismiss()

    def guardar(self, *args):
        app = App.get_running_app()
        if not all([self.nombre.text, self.fecha.text, self.tel.text, self.cedula.text, self.genero, self.bautizado, self.grupo]):
            mostrar_popup_error("Completa todos los campos obligatorios")
            return
        
        datos = {
            "nombre": self.nombre.text,
            "fecha_nacimiento": self.fecha.text,
            "telefono": self.tel.text,
            "cedula": self.cedula.text,
            "genero": self.genero,
            "tiempo_iglesia": self.tiempo.text,
            "bautizado": self.bautizado,
            "grupo_pequeno": self.grupo,
            "lider_id": app.user_id,
            "observaciones": "",
            "empresa": self.empresa.text,
            "direccion": self.direccion.text
        }
        
        def on_save_complete(success, response):
            if success and response:
                new_id = response.get("name")
                PushNotification.send(app.user_id, "Nueva Oveja Registrada", f"Has registrado a {self.nombre.text} en tu rebaño.")
                datos['id'] = new_id
                app.data_cache.get("ovejas")[new_id] = datos
                app.data_cache.save_to_storage()
                mostrar_popup_exito("✅ Oveja registrada", on_dismiss=lambda x: setattr(self.manager, 'current', 'menu_principal'))
            else:
                mostrar_popup_error(f"❌ Error al guardar en Firebase: {response}")

        firebase_post("ovejas", datos, on_complete=on_save_complete)

class MisOvejasScreen(Screen):
    oveja_a_editar_id = None
    popup_edit = None
    edit_nombre = None
    edit_tel = None
    edit_cedula = None
    edit_empresa = None
    edit_direccion = None
    edit_obs = None
    
    def on_enter(self):
        app = App.get_running_app()
        self.ovejas_data = app.data_cache.get("ovejas") or {}
        self.mostrar_ovejas()

    def mostrar_ovejas(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='mis_ovejas_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        
        app = App.get_running_app()
        
        self.mis_ovejas_items = []
        for oveja_id, oveja in self.ovejas_data.items():
            if app.rol == 'director' or oveja.get("lider_id") == app.user_id:
                oveja['id'] = oveja_id
                self.mis_ovejas_items.append(oveja)

        if app.rol == 'director':
            layout.add_widget(crear_titulo("Todas las Ovejas", color=LIGHT_BLUE))
        else:
            layout.add_widget(crear_titulo("Mis Ovejas"))
        
        self.search_input = crear_input("Buscar por nombre o cédula...")
        self.search_input.bind(text=self.schedule_filter)
        layout.add_widget(self.search_input)

        self.scroll = ScrollView()
        self.grid = GridLayout(cols=1, spacing=dp(15), size_hint_y=None, padding=dp(10))
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        layout.add_widget(self.scroll)

        self.actualizar_lista_ovejas(self.mis_ovejas_items)

        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

    def schedule_filter(self, instance, value):
        Clock.unschedule(self.filtrar_ovejas)
        Clock.schedule_once(lambda dt: self.filtrar_ovejas(instance, value), 0.5)

    def filtrar_ovejas(self, instance, value):
        filtro = value.lower()
        ovejas_filtradas = [
            o for o in self.mis_ovejas_items 
            if filtro in o['nombre'].lower() or filtro in o.get('cedula', '').lower()
        ]
        self.actualizar_lista_ovejas(ovejas_filtradas)

    def actualizar_lista_ovejas(self, ovejas):
        self.grid.clear_widgets()
        if not ovejas:
            self.grid.add_widget(crear_label("No se encontraron ovejas", color=get_color_from_hex(WHITE), size_hint_y=None, height=dp(50)))
        else:
            for o in ovejas:
                tarjeta = BoxLayoutBG(
                    orientation='vertical',
                    bg_color='#222222',
                    padding=dp(15),
                    spacing=dp(8),
                    size_hint_y=None,
                    height=dp(260)
                )
                header = BoxLayout(size_hint_y=None, height=dp(40))
                nombre_label = crear_label(
                    f" {o['nombre']}",
                    bold=True,
                    color=get_color_from_hex(WHITE),
                    size_hint=(0.8, 1),
                    halign='left',
                    valign='middle'
                )
                nombre_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
                header.add_widget(nombre_label)
                tarjeta.add_widget(header)
                tarjeta.add_widget(crear_label(f"Teléfono: {o.get('telefono', '')}", color=get_color_from_hex(GRAY), halign='left', font_size='13sp'))
                tarjeta.add_widget(crear_label(f"Cédula: {o.get('cedula', '')}", color=get_color_from_hex('#AAAAAA'), halign='left', font_size='12sp'))
                genero = "Hombre" if o.get('genero') == "hombre" else "Mujer"
                tarjeta.add_widget(crear_label(f"Género: {genero}", color=get_color_from_hex(BLUE), bold=True, halign='left', font_size='13sp'))
                tarjeta.add_widget(crear_label(
                    f"Empresa: {o.get('empresa', 'Sin empresa')}",
                    color=get_color_from_hex('#AAAAAA'),
                    halign='left',
                    font_size='12sp'
                ))
                tarjeta.add_widget(crear_label(
                    f"Dirección: {o.get('direccion', 'Sin dirección')}",
                    color=get_color_from_hex('#AAAAAA'),
                    halign='left',
                    font_size='12sp'
                ))
                obs = o.get('observaciones', '') or "Sin observaciones"
                obs_label = crear_label(
                    f"Observaciones: {obs}",
                    color=get_color_from_hex('#AAAAAA'),
                    halign='left',
                    valign='top',
                    font_size='12sp',
                    text_size=(dp(260), None),
                    size_hint_y=None,
                    height=dp(50)
                )
                tarjeta.add_widget(obs_label)
                btn_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
                btn_edit = crear_boton("✏ Editar", GREEN, lambda x, oveja_id=o['id'], oveja_data=o: self.editar_oveja(oveja_id, oveja_data), alpha=0.8)
                btn_del = crear_boton("🗑 Eliminar", RED, lambda x, oveja_id=o['id'], oveja_nombre=o['nombre']: self.confirmar_eliminar(oveja_id, oveja_nombre), alpha=0.8)
                btn_layout.add_widget(btn_edit)
                btn_layout.add_widget(btn_del)
                tarjeta.add_widget(btn_layout)
                self.grid.add_widget(tarjeta)

    def editar_oveja(self, oveja_id, oveja):
        self.oveja_a_editar_id = oveja_id
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label("Editar Oveja", bold=True, color=get_color_from_hex(WHITE)))
        
        self.edit_nombre = crear_input("Nombre", text=oveja.get('nombre', ''))
        self.edit_tel = crear_input("Teléfono", text=oveja.get('telefono', ''))
        self.edit_cedula = crear_input("Cédula/ID", text=oveja.get('cedula', ''))
        self.edit_empresa = crear_input("Empresa", text=oveja.get('empresa', ''))
        self.edit_direccion = crear_input("Dirección", text=oveja.get('direccion', ''))
        self.edit_obs = crear_input("Observaciones", multiline=True, text=oveja.get('observaciones', ''))
        
        for w in [self.edit_nombre, self.edit_tel, self.edit_cedula, self.edit_empresa, self.edit_direccion, self.edit_obs]:
            content.add_widget(w)
            
        btn_guardar = crear_boton("💾 Guardar", GREEN, self.guardar_cambios, alpha=0.8)
        btn_cancel = crear_boton("✖ Cancelar", GRAY, lambda x: self.popup_edit.dismiss(), alpha=0.8)
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_layout.add_widget(btn_guardar)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        
        self.popup_edit = Popup(title='Editar Oveja', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_edit.open()

    def guardar_cambios(self, *args):
        if not self.oveja_a_editar_id:
            mostrar_popup_error("Error: no se encontró la oveja a editar.")
            return

        oveja_actual = App.get_running_app().data_cache.get("ovejas").get(self.oveja_a_editar_id)
        if not oveja_actual:
            mostrar_popup_error("Error: no se pudo obtener la información actual de la oveja.")
            return

        datos_formulario = {
            "nombre": self.edit_nombre.text,
            "telefono": self.edit_tel.text,
            "cedula": self.edit_cedula.text,
            "empresa": self.edit_empresa.text,
            "direccion": self.edit_direccion.text,
            "observaciones": self.edit_obs.text
        }

        oveja_actual.update(datos_formulario)

        def on_update_complete(success, response):
            if success:
                self.popup_edit.dismiss()
                App.get_running_app().data_cache.get("ovejas")[self.oveja_a_editar_id] = oveja_actual
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito("✅ Oveja actualizada", on_dismiss=lambda x: self.on_enter())
            else:
                mostrar_popup_error(f"❌ Error al guardar los cambios en Firebase: {response}")

        firebase_put(f"ovejas/{self.oveja_a_editar_id}", oveja_actual, on_complete=on_update_complete)

    def confirmar_eliminar(self, oveja_id, oveja_nombre):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label(f"¿Estás seguro de eliminar a {oveja_nombre}?", color=get_color_from_hex(WHITE), halign='center'))
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_si = crear_boton("✅ Sí", RED, lambda x: self.eliminar_oveja(oveja_id), alpha=0.8)
        btn_no = crear_boton("✖ No", BLUE, lambda x: self.popup_confirmar.dismiss(), alpha=0.8)
        btn_layout.add_widget(btn_si)
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        self.popup_confirmar = Popup(title='Eliminar Oveja', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.8, 0.4))
        self.popup_confirmar.open()

    def eliminar_oveja(self, oveja_id):
        def on_delete_complete(success, response):
            if success:
                self.popup_confirmar.dismiss()
                App.get_running_app().data_cache.get("ovejas").pop(oveja_id, None)
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito("Oveja eliminada", on_dismiss=lambda x: self.on_enter())
            else:
                mostrar_popup_error(f"❌ Error al eliminar la oveja: {response}")
        
        firebase_delete(f"ovejas/{oveja_id}", on_complete=on_delete_complete)

class CalendarioScreen(Screen):
    def on_enter(self):
        self.cargar_seguimientos()

    def cargar_seguimientos(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='calendario_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        layout.add_widget(crear_titulo("Calendario de Seguimiento"))
        app = App.get_running_app()
        seguimientos = app.data_cache.get("seguimientos")
        ovejas_data = app.data_cache.get("ovejas")
        
        mis_seguimientos = []
        if seguimientos and ovejas_data:
            for seg in seguimientos.values():
                oveja_id = seg.get('oveja_id')
                oveja = ovejas_data.get(oveja_id)
                if oveja and (app.rol == 'director' or oveja.get("lider_id") == app.user_id):
                    seg["nombre_oveja"] = oveja["nombre"]
                    mis_seguimientos.append(seg)
        
        if not mis_seguimientos:
            layout.add_widget(crear_label("No hay seguimientos", color=get_color_from_hex(GRAY), halign='center'))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))
            for seg in mis_seguimientos:
                tarjeta = BoxLayoutBG(
                    orientation='vertical',
                    bg_color='#222222',
                    padding=dp(10),
                    spacing=dp(5),
                    size_hint_y=None,
                    height=dp(120)
                )
                tarjeta.add_widget(crear_label(f"Oveja: {seg.get('nombre_oveja', 'Desconocida')}", color=get_color_from_hex(WHITE), bold=True))
                tarjeta.add_widget(crear_label(f"Fecha: {seg.get('fecha_seguimiento', '')}", color=get_color_from_hex(YELLOW)))
                tarjeta.add_widget(crear_label(f"Tipo: {seg.get('tipo', 'Personalizado')}", color=get_color_from_hex(LIGHT_BLUE)))
                tarjeta.add_widget(crear_label(f"Contenido: {seg.get('contenido', '')[:50]}...", color=get_color_from_hex('#AAAAAA'), font_size='12sp'))
                grid.add_widget(tarjeta)
            scroll.add_widget(grid)
            layout.add_widget(scroll)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

class EstadisticasScreen(Screen):
    def on_enter(self):
        self.mostrar_estadisticas()

    def mostrar_estadisticas(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='estadisticas_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        layout.add_widget(crear_titulo("Estadísticas del Rebaño"))
        app = App.get_running_app()
        ovejas_data = app.data_cache.get("ovejas")
        
        if app.rol == 'director':
            ovejas_a_contar = list(ovejas_data.values()) if ovejas_data else []
        else:
            ovejas_a_contar = [o for o in ovejas_data.values() if o.get("lider_id") == app.user_id] if ovejas_data else []
        
        bautizadas = [o for o in ovejas_a_contar if o.get("bautizado") == "sí"]
        total = len(ovejas_a_contar)
        baut = len(bautizadas)
        pct = int(baut / total * 100) if total > 0 else 0
        layout.add_widget(crear_label(f"Total de ovejas: {total}", color=get_color_from_hex(WHITE)))
        layout.add_widget(crear_label(f"Bautizadas: {baut}", color=get_color_from_hex(GREEN)))
        layout.add_widget(crear_label(f"Porcentaje: {pct}%", color=get_color_from_hex(YELLOW)))

        # --- SECCIÓN AÑADIDA PARA MOSTRAR ASISTENCIAS ---
        layout.add_widget(crear_titulo("Asistencias Recientes", LIGHT_BLUE))
        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
        grid.bind(minimum_height=grid.setter('height'))

        for oveja in ovejas_a_contar:
            asistencias = oveja.get('asistencias', [])
            tarjeta = BoxLayoutBG(
                orientation='horizontal',
                bg_color='#222222',
                padding=dp(10),
                spacing=dp(5),
                size_hint_y=None,
                height=dp(60)
            )
            tarjeta.add_widget(crear_label(f"Nombre: {oveja.get('nombre', 'N/A')}", halign='left', color=get_color_from_hex(WHITE)))
            tarjeta.add_widget(crear_label(f"Asistencias: {len(asistencias)}", halign='right', color=get_color_from_hex(YELLOW)))
            grid.add_widget(tarjeta)

        scroll.add_widget(grid)
        layout.add_widget(scroll)
        # --- FIN SECCIÓN AÑADIDA ---

        if app.rol == 'director':
            btn_exportar = crear_boton("📤 Exportar Ovejas (CSV)", GREEN, self.exportar_a_csv, alpha=0.8)
            layout.add_widget(btn_exportar)

            btn_exportar_asistencias = crear_boton("📤 Exportar Asistencias", GREEN, self.exportar_asistencias_a_csv, alpha=0.8)
            layout.add_widget(btn_exportar_asistencias)

            btn_exportar_resumen = crear_boton("📊 Exportar Resumen", GREEN, self.exportar_resumen_a_csv, alpha=0.8)
            layout.add_widget(btn_exportar_resumen)

        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

    def _guardar_y_compartir_csv(self, filename, headers, filas):
        """Guarda un CSV en la carpeta privada de la app (sin necesitar permisos)
        y abre el diálogo de compartir/guardar de Android para que el usuario
        lo descargue donde quiera (Drive, Descargas, correo, WhatsApp, etc.)."""
        app = App.get_running_app()
        try:
            carpeta = app.user_data_dir
        except Exception:
            carpeta = "."
        path = os.path.join(carpeta, filename)

        with open(path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            for fila in filas:
                writer.writerow(fila)

        try:
            from plyer import share
            share.share(title="Guardar / Compartir archivo", filepath=path)
            mostrar_popup_exito(f"✅ Archivo generado: {filename}\n\nElige dónde guardarlo o compartirlo.")
        except Exception:
            mostrar_popup_exito(f"✅ Archivo generado en:\n{path}")

    def exportar_a_csv(self, *args):
        ovejas_data = App.get_running_app().data_cache.get("ovejas") or {}
        if not ovejas_data:
            mostrar_popup_error("No hay datos de ovejas para exportar.")
            return

        filename = f"ovejas_rebano_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        headers = ["nombre", "cedula", "telefono", "genero", "bautizado", "grupo_pequeno", "lider_id", "observaciones", "empresa", "direccion", "total_asistencias"]

        filas = []
        for oveja in ovejas_data.values():
            filas.append({
                "nombre": oveja.get("nombre", ""),
                "cedula": oveja.get("cedula", ""),
                "telefono": oveja.get("telefono", ""),
                "genero": oveja.get("genero", ""),
                "bautizado": oveja.get("bautizado", ""),
                "grupo_pequeno": oveja.get("grupo_pequeno", ""),
                "lider_id": oveja.get("lider_id", ""),
                "observaciones": oveja.get("observaciones", ""),
                "empresa": oveja.get("empresa", ""),
                "direccion": oveja.get("direccion", ""),
                "total_asistencias": len(oveja.get("asistencias", []))
            })

        self._guardar_y_compartir_csv(filename, headers, filas)

    def exportar_asistencias_a_csv(self, *args):
        ovejas_data = App.get_running_app().data_cache.get("ovejas") or {}
        if not ovejas_data:
            mostrar_popup_error("No hay datos de asistencias para exportar.")
            return

        filename = f"asistencias_rebano_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        headers = ["nombre", "fecha_asistencia", "evento"]

        filas = []
        for oveja in ovejas_data.values():
            for asistencia in oveja.get('asistencias', []):
                filas.append({
                    "nombre": oveja.get("nombre", ""),
                    "fecha_asistencia": asistencia.get("fecha", ""),
                    "evento": asistencia.get("evento", "")
                })

        if not filas:
            mostrar_popup_error("No hay asistencias registradas todavía.")
            return

        self._guardar_y_compartir_csv(filename, headers, filas)

    def exportar_resumen_a_csv(self, *args):
        ovejas_data = App.get_running_app().data_cache.get("ovejas") or {}
        if not ovejas_data:
            mostrar_popup_error("No hay datos para generar el resumen.")
            return

        ovejas = list(ovejas_data.values())
        total = len(ovejas)
        bautizadas = len([o for o in ovejas if o.get("bautizado") == "sí"])
        pct = int(bautizadas / total * 100) if total > 0 else 0
        total_asistencias = sum(len(o.get("asistencias", [])) for o in ovejas)

        filename = f"resumen_estadisticas_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        headers = ["indicador", "valor"]
        filas = [
            {"indicador": "Total de ovejas", "valor": total},
            {"indicador": "Bautizadas", "valor": bautizadas},
            {"indicador": "Porcentaje bautizadas", "valor": f"{pct}%"},
            {"indicador": "Total de asistencias registradas", "valor": total_asistencias},
        ]

        self._guardar_y_compartir_csv(filename, headers, filas)


class SeguimientoScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.oveja_a_seguir = None
        
    def on_enter(self):
        self.mostrar_ovejas()

    def mostrar_ovejas(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='seguimiento_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        layout.add_widget(crear_titulo("Hacer Seguimiento"))
        app = App.get_running_app()
        ovejas = app.data_cache.get("ovejas")
        mis_ovejas_con_id = []

        if ovejas:
            for oveja_id, oveja_data in ovejas.items():
                if app.rol == 'director' or oveja_data.get("lider_id") == app.user_id:
                    oveja_data['id'] = oveja_id
                    mis_ovejas_con_id.append(oveja_data)

        if not mis_ovejas_con_id:
            layout.add_widget(crear_label("No tienes ovejas asignadas", color=get_color_from_hex(RED), halign='center'))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))
            for o in mis_ovejas_con_id:
                btn = crear_boton(f"{o['nombre']}", BLUE, lambda x, oveja=o: self.abrir_seguimiento(oveja), alpha=0.8)
                grid.add_widget(btn)
            scroll.add_widget(grid)
            layout.add_widget(scroll)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

    def abrir_seguimiento(self, oveja):
        self.oveja_a_seguir = oveja
        
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label(f"Seguimiento a {oveja['nombre']}", bold=True, color=get_color_from_hex(WHITE)))
        self.menu = Popup(title="Plantillas", content=GridLayout(cols=1, spacing=dp(10)), size_hint=(0.9, 0.7))
        grid = self.menu.content
        for p in PLANTILLAS:
            btn = crear_boton(p, BLUE, lambda x, texto=p: usar_plantilla(texto), alpha=0.8)
            grid.add_widget(btn)
        btn_close = crear_boton("✖ Cerrar", GRAY, lambda x: self.menu.dismiss(), alpha=0.8)
        grid.add_widget(btn_close)

        def usar_plantilla(texto):
            self.obs_input.text = texto
            self.menu.dismiss()

        btn_plantilla = crear_boton("📋 Usar plantilla", YELLOW, lambda x: self.menu.open(), alpha=0.5)
        content.add_widget(btn_plantilla)
        
        obs_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(100), spacing=dp(5))
        self.obs_input = crear_input("Escribe lo que se habló...", multiline=True)
        obs_layout.add_widget(self.obs_input)
        
        btn_mic = Button(text="🎙️", size_hint_x=None, width=dp(50), font_size='25sp', background_color=get_color_from_hex(GRAY))
        obs_layout.add_widget(btn_mic)
        content.add_widget(obs_layout)

        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        
        # --- BOTÓN DE ASISTENCIA AÑADIDO ---
        btn_asistencia = crear_boton("✅ M Asist", ORANGE, lambda x: self.marcar_asistencia(), alpha=0.5)
        btn_layout.add_widget(btn_asistencia)
        # --- FIN BOTÓN DE ASISTENCIA AÑADIDO ---

        btn_guardar = crear_boton("💾 Guardar", GREEN, lambda x: self.guardar(), alpha=0.8)
        btn_llamar = crear_boton("📞 Llamar", DARK_BLUE, lambda x: mostrar_popup_error("Llamada no disponible"), alpha=0.8)
        btn_whatsapp = crear_boton("💬 WhatsApp", GREEN, lambda x: self.send_whatsapp_message(self.oveja_a_seguir.get('telefono')), alpha=0.8)
        
        btn_layout.add_widget(btn_guardar)
        btn_layout.add_widget(btn_llamar)
        btn_layout.add_widget(btn_whatsapp)
        content.add_widget(btn_layout)
        popup = Popup(title='Seguimiento', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.95, 0.8))
        self.popup_seguimiento = popup
        popup.open()

    def send_whatsapp_message(self, number):
        if not number:
            mostrar_popup_error("Número de teléfono no disponible.")
            return

        formatted_number = f"57{number.replace(' ', '').replace('-', '')}"
        webbrowser.open(f"https://wa.me/{formatted_number}")


    def guardar(self):
        texto = self.obs_input.text.strip()
        if not texto:
            mostrar_popup_error("Escribe lo que se habló")
            return
        
        app = App.get_running_app()
        datos_seguimiento = {
            "oveja_id": self.oveja_a_seguir['id'],
            "fecha_seguimiento": datetime.now().strftime("%Y-%m-%d"),
            "tipo": "Personalizado",
            "contenido": texto
        }
        
        if not NetworkStatus.check_connection():
            app.data_cache.save_offline_seguimiento(datos_seguimiento)
            self.popup_seguimiento.dismiss()
            mostrar_popup_exito("✅ Seguimiento guardado sin conexión. Se sincronizará automáticamente.", on_dismiss=lambda x: self.mostrar_ovejas())
            return
        
        def on_seguimiento_complete(success, response):
            if success and response:
                new_id_seg = response.get("name")
                oveja_actual = App.get_running_app().data_cache.get("ovejas").get(self.oveja_a_seguir['id'])
                
                def on_oveja_update_complete(success_update, response_update):
                    if success_update:
                        if oveja_actual:
                            app.data_cache.get("ovejas")[self.oveja_a_seguir['id']] = oveja_actual
                            datos_seguimiento['id'] = new_id_seg
                            app.data_cache.get("seguimientos")[new_id_seg] = datos_seguimiento
                            app.data_cache.save_to_storage()
                        
                        PushNotification.send(app.user_id, "Seguimiento Registrado", f"Has registrado un seguimiento para {oveja_actual['nombre']}.")
                        usuarios = app.data_cache.get('usuarios')
                        for uid, user in usuarios.items():
                            if user.get('rol') == 'director':
                                PushNotification.send(uid, "Nuevo Seguimiento", f"El líder {app.nombre} ha registrado un seguimiento para {oveja_actual['nombre']}.")

                        self.popup_seguimiento.dismiss()
                        mostrar_popup_exito("✅ Seguimiento y observaciones guardados", on_dismiss=lambda x: self.mostrar_ovejas())
                    else:
                        mostrar_popup_error(f"❌ Error al actualizar la oveja: {response_update}")

                if oveja_actual:
                    oveja_actual['observaciones'] = texto
                    oveja_actual['fecha_ultimo_seguimiento'] = datetime.now().strftime("%Y-%m-%d")
                    firebase_put(f"ovejas/{self.oveja_a_seguir['id']}", oveja_actual, on_complete=on_oveja_update_complete)
                else:
                    mostrar_popup_error("❌ Error al obtener los datos de la oveja.")

            else:
                mostrar_popup_error(f"❌ Error al guardar el seguimiento: {response}")

        firebase_post("seguimientos", datos_seguimiento, on_complete=on_seguimiento_complete)

    # --- MÉTODO PARA MARCAR ASISTENCIA CORREGIDO ---
    def marcar_asistencia(self):
        oveja_id = self.oveja_a_seguir['id']
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

        oveja_actual = App.get_running_app().data_cache.get("ovejas").get(oveja_id)
        if oveja_actual is None:
            mostrar_popup_error("Error: No se pudo encontrar la oveja para marcar asistencia.")
            return

        asistencias = oveja_actual.get("asistencias", [])
        
        if any(asist.get('fecha') == fecha_hoy for asist in asistencias):
            mostrar_popup_error("Ya se ha marcado la asistencia de esta oveja para hoy.")
            return
            
        nueva_asistencia = {
            "fecha": fecha_hoy,
            "asistio": True,
            "evento": "Servicio o reunión"
        }
        asistencias.append(nueva_asistencia)
        oveja_actual["asistencias"] = asistencias

        def on_asistencia_complete(success, response):
            if success:
                self.popup_seguimiento.dismiss()
                App.get_running_app().data_cache.get("ovejas")[oveja_id] = oveja_actual
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito("✅ Asistencia marcada con éxito.")
            else:
                mostrar_popup_error(f"❌ Error al marcar la asistencia: {response}")
        
        firebase_put(f"ovejas/{oveja_id}", oveja_actual, on_complete=on_asistencia_complete)
    # --- FIN MÉTODO CORREGIDO ---

class ChatScreen(Screen):
    def on_enter(self):
        self.mostrar_usuarios()

    def mostrar_usuarios(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='chat_background.png', orientation='vertical', padding=dp(15), spacing=dp(10))
        layout.add_widget(crear_titulo("Chat"))
        app = App.get_running_app()
        usuarios = app.data_cache.get("usuarios")
        otros = [u for u in usuarios.values() if u.get("id") != app.user_id]
        if not otros:
            layout.add_widget(crear_label("No hay usuarios", color=get_color_from_hex(GRAY), halign='center'))
        else:
            for otro in otros:
                btn = crear_boton(f"Chat con {otro['nombre']}", BLUE, lambda x, o=otro: self.abrir_chat_con(o), alpha=0.8)
                layout.add_widget(btn)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

    def abrir_chat_con(self, otro):
        app = App.get_running_app()
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label(f"Chat con {otro['nombre']}", bold=True, color=get_color_from_hex(WHITE)))
        scroll = ScrollView()
        self.mensajes_layout = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        self.mensajes_layout.bind(minimum_height=self.mensajes_layout.setter('height'))
        scroll.add_widget(self.mensajes_layout)
        content.add_widget(scroll)
        self.input_mensaje = crear_input("Escribe un mensaje...", multiline=False)
        content.add_widget(self.input_mensaje)
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_enviar = crear_boton("📨 Enviar", GREEN, self.enviar_mensaje, alpha=0.8)
        btn_enviar.bind(on_press=lambda x: setattr(self, 'destinatario_id', otro.get('id')))
        btn_volver = crear_boton("< Volver", GRAY, lambda x: popup.dismiss(), alpha=0.8)
        btn_layout.add_widget(btn_enviar)
        btn_layout.add_widget(btn_volver)
        content.add_widget(btn_layout)
        popup = Popup(title=f"Chat con {otro['nombre']}", content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.95, 0.9))
        self.popup_chat = popup
        self.destinatario_id = otro.get('id')
        self.cargar_mensajes(app.user_id, self.destinatario_id)
        popup.open()

    def cargar_mensajes(self, remitente, destinatario):
        self.mensajes_layout.clear_widgets()
        mensajes = App.get_running_app().data_cache.get("chat")
        for mid, m in mensajes.items():
            if (m.get("remitente_id") == remitente and m.get("destinatario_id") == destinatario) or \
               (m.get("remitente_id") == destinatario and m.get("destinatario_id") == remitente):
                self.mensajes_layout.add_widget(crear_label(
                    f"[b]{m.get('remitente_nombre', 'Anónimo')}:[/b] {m.get('mensaje', '')} \n[size=10][i]{m.get('fecha', '')}[/i][/size]",
                    markup=True,
                    color=get_color_from_hex(WHITE),
                    halign='left',
                    size_hint_y=None,
                    height=dp(50)
                ))

    def enviar_mensaje(self, *args):
        texto = self.input_mensaje.text.strip()
        if not texto:
            return
        app = App.get_running_app()
        datos = {
            "remitente_id": app.user_id,
            "remitente_nombre": app.nombre,
            "destinatario_id": self.destinatario_id,
            "mensaje": texto,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        def on_send_complete(success, response):
            if success and response:
                new_id = response.get("name")
                datos['id'] = new_id
                app.data_cache.get("chat")[new_id] = datos
                app.data_cache.save_to_storage()
                self.input_mensaje.text = ""
                self.cargar_mensajes(app.user_id, self.destinatario_id)
                PushNotification.send(self.destinatario_id, f"Nuevo Mensaje de {app.nombre}", texto)
            else:
                mostrar_popup_error(f"❌ Error al enviar el mensaje: {response}")

        firebase_post("chat", datos, on_complete=on_send_complete)

class GestionarUsuariosScreen(Screen):
    def on_enter(self):
        self.mostrar_usuarios()
        
    def mostrar_usuarios(self):
        self.clear_widgets()
        self.layout = BoxLayoutBG(bg_image='gestionar_usuarios_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        self.layout.add_widget(crear_titulo("Gestionar Usuarios"))

        app = App.get_running_app()
        usuarios = App.get_running_app().data_cache.get("usuarios")
        
        if not usuarios:
            self.layout.add_widget(crear_label("No hay usuarios registrados", color=get_color_from_hex(RED)))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(15), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))

            for uid, user_data in usuarios.items():
                if uid == app.user_id:
                    continue

                tarjeta = BoxLayoutBG(
                    orientation='vertical',
                    bg_color='#222222',
                    padding=dp(15),
                    spacing=dp(8),
                    size_hint_y=None,
                    height=dp(200)
                )

                tarjeta.add_widget(crear_label(f"Usuario: {user_data.get('nombre', 'Desconocido')}", color=get_color_from_hex(WHITE), bold=True))
                tarjeta.add_widget(crear_label(f"Correo: {user_data.get('correo', 'Sin correo')}", color=get_color_from_hex(GRAY), font_size='12sp'))
                
                rol_text = f"Rol: {user_data.get('rol', 'lider').upper()}"
                rol_color = GREEN if user_data.get('rol') == 'director' else LIGHT_BLUE
                tarjeta.add_widget(crear_label(rol_text, color=get_color_from_hex(rol_color), bold=True))
                
                btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
                
                btn_rol = crear_boton("🔄 Cambiar Rol", ORANGE, lambda x, user_id=uid, user_name=user_data.get('nombre'), current_rol=user_data.get('rol'): self.cambiar_rol(user_id, user_name, current_rol), alpha=0.8)
                btn_reset_pass = crear_boton("🔑 Reset Pass", YELLOW, lambda x, user_id=uid: self.reset_pass(user_id), alpha=0.8)
                btn_eliminar = crear_boton("🗑 Eliminar", RED, lambda x, user_id=uid, user_name=user_data.get('nombre'): self.confirmar_eliminar(user_id, user_name), alpha=0.8)
                
                btn_layout.add_widget(btn_rol)
                btn_layout.add_widget(btn_reset_pass)
                btn_layout.add_widget(btn_eliminar)

                tarjeta.add_widget(btn_layout)
                grid.add_widget(tarjeta)

            scroll.add_widget(grid)
            self.layout.add_widget(scroll)

        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def cambiar_rol(self, user_id, user_name, current_rol):
        nuevo_rol = "director" if current_rol == "lider" else "lider"
        user_data = App.get_running_app().data_cache.get("usuarios").get(user_id)
        if not user_data:
            mostrar_popup_error("Usuario no encontrado.")
            return
        
        user_data['rol'] = nuevo_rol
        
        def on_change_rol_complete(success, response):
            if success:
                App.get_running_app().data_cache.get("usuarios")[user_id] = user_data
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito(f"✅ Rol de {user_name} cambiado a {nuevo_rol.upper()}", on_dismiss=lambda x: self.mostrar_usuarios())
            else:
                mostrar_popup_error(f"❌ Error al cambiar el rol: {response}")

        firebase_put(f"usuarios/{user_id}", user_data, on_complete=on_change_rol_complete)

    def reset_pass(self, user_id):
        new_pass = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
        hashed_password = hashlib.sha256(new_pass.encode('utf-8')).hexdigest()
        
        user_data = App.get_running_app().data_cache.get("usuarios").get(user_id)
        if not user_data:
            mostrar_popup_error("Usuario no encontrado.")
            return
        
        user_data['contraseña'] = hashed_password

        def on_reset_complete(success, response):
            if success:
                App.get_running_app().data_cache.get("usuarios")[user_id] = user_data
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito(f"✅ La nueva contraseña temporal es: [b]{new_pass}[/b]\nPor favor, comunícala al usuario.", markup=True)
            else:
                mostrar_popup_error(f"❌ Error al resetear la contraseña: {response}")
        
        firebase_put(f"usuarios/{user_id}", user_data, on_complete=on_reset_complete)

    def confirmar_eliminar(self, user_id, user_name):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label(f"¿Estás seguro de eliminar a {user_name}?", color=get_color_from_hex(WHITE), halign='center'))
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_si = crear_boton("🗑 Sí, eliminar", RED, lambda x: self.eliminar_usuario(user_id), alpha=0.8)
        btn_no = crear_boton("✖ No, cancelar", BLUE, lambda x: self.popup_confirmar.dismiss(), alpha=0.8)
        btn_layout.add_widget(btn_si)
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        self.popup_confirmar = Popup(title='Eliminar Usuario', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.8, 0.4))
        self.popup_confirmar.open()

    def eliminar_usuario(self, user_id):
        ovejas = App.get_running_app().data_cache.get("ovejas")
        if ovejas:
            for oveja_id, oveja_data in ovejas.items():
                if oveja_data.get('lider_id') == user_id:
                    oveja_data['lider_id'] = None
                    firebase_put_sync(f"ovejas/{oveja_id}", oveja_data)

        def on_delete_complete(success, response):
            if success:
                self.popup_confirmar.dismiss()
                App.get_running_app().data_cache.get("usuarios").pop(user_id, None)
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito("Usuario eliminado", on_dismiss=lambda x: self.mostrar_usuarios())
            else:
                mostrar_popup_error(f"❌ Error al eliminar el usuario: {response}")
        
        firebase_delete(f"usuarios/{user_id}", on_complete=on_delete_complete)

class ReasignarOvejaScreen(Screen):
    def on_enter(self):
        self.mostrar_ovejas()

    def mostrar_ovejas(self):
        self.clear_widgets()
        self.layout = BoxLayoutBG(bg_image='reasignar_oveja_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        self.layout.add_widget(crear_titulo("Selecciona una Oveja"))

        ovejas = App.get_running_app().data_cache.get("ovejas")
        ovejas_list = []
        if ovejas:
            for oveja_id, oveja_data in ovejas.items():
                oveja_data['id'] = oveja_id
                ovejas_list.append(oveja_data)

        if not ovejas_list:
            self.layout.add_widget(crear_label("No hay ovejas registradas", color=get_color_from_hex(RED)))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))
            for o in ovejas_list:
                btn = crear_boton(f"{o['nombre']}", BLUE, lambda x, oveja=o: self.seleccionar_lider(oveja), alpha=0.8)
                grid.add_widget(btn)
            scroll.add_widget(grid)
            self.layout.add_widget(scroll)

        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def seleccionar_lider(self, oveja):
        self.clear_widgets()
        self.layout = BoxLayoutBG(bg_image='reasignar_oveja_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        self.layout.add_widget(crear_titulo(f"Asignar a {oveja['nombre']}"))
        
        usuarios = App.get_running_app().data_cache.get("usuarios")
        lideres = []
        if usuarios:
            for uid, user_data in usuarios.items():
                if user_data.get('rol') == 'lider':
                    user_data['id'] = uid
                    lideres.append(user_data)
        
        if not lideres:
            self.layout.add_widget(crear_label("No hay líderes disponibles", color=get_color_from_hex(RED)))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))
            for l in lideres:
                btn = crear_boton(f"{l['nombre']}", GREEN, lambda x, lider=l: self.confirmar_reasignacion(oveja, lider), alpha=0.8)
                grid.add_widget(btn)
            scroll.add_widget(grid)
            self.layout.add_widget(scroll)
        
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: self.mostrar_ovejas(), alpha=0.8)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def confirmar_reasignacion(self, oveja, lider):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label(f"¿Reasignar a {oveja['nombre']} a {lider['nombre']}?", color=get_color_from_hex(WHITE), halign='center'))
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_si = crear_boton("🔄 Sí, reasignar", RED, lambda x: self.reasignar(oveja, lider), alpha=0.8)
        btn_no = crear_boton("✖ No, cancelar", BLUE, lambda x: self.popup.dismiss(), alpha=0.8)
        btn_layout.add_widget(btn_si)
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        self.popup = Popup(title='Confirmar Reasignación', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.8, 0.4))
        self.popup.open()

    def reasignar(self, oveja, lider):
        oveja['lider_id'] = lider['id']
        
        def on_reasign_complete(success, response):
            if success:
                self.popup.dismiss()
                PushNotification.send(lider['id'], "Oveja Reasignada", f"Se te ha asignado una nueva oveja: {oveja['nombre']}.")
                App.get_running_app().data_cache.get("ovejas")[oveja['id']] = oveja
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito(f"✅ Oveja reasignada a {lider['nombre']}", on_dismiss=lambda x: setattr(self.manager, 'current', 'menu_principal'))
            else:
                mostrar_popup_error(f"❌ Error al reasignar la oveja: {response}")

        firebase_put(f"ovejas/{oveja['id']}", oveja, on_complete=on_reasign_complete)

class AsignacionAutomaticaScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayoutBG(bg_image='asignacion_automatica_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        
        self.layout.add_widget(crear_titulo("Asignación Automática"))
        self.layout.add_widget(crear_label("Esto asignará ovejas a líderes según su género, y las ovejas restantes se distribuirán equitativamente.",
                                     color=get_color_from_hex(GRAY), halign='center'))
        
        btn_iniciar = crear_boton("🔀 Iniciar Asignación", GREEN, self.iniciar_asignacion_automatica, alpha=0.8)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        
        self.layout.add_widget(btn_iniciar)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def iniciar_asignacion_automatica(self, *args):
        app = App.get_running_app()
        usuarios = app.data_cache.get("usuarios")
        ovejas_data = app.data_cache.get("ovejas")

        if not usuarios or not ovejas_data:
            mostrar_popup_error("No hay suficientes usuarios u ovejas para la asignación.")
            return

        lideres = {uid: user for uid, user in usuarios.items() if user.get('rol') == 'lider'}
        ovejas_no_asignadas = {uid: oveja for uid, oveja in ovejas_data.items() if not oveja.get('lider_id')}
        
        if not lideres or not ovejas_no_asignadas:
            mostrar_popup_exito("No hay ovejas sin asignar o líderes disponibles.")
            return

        lideres_hombres = [uid for uid, user in lideres.items() if user.get('genero') == 'hombre']
        lideres_mujeres = [uid for uid, user in lideres.items() if user.get('genero') == 'mujer']
        
        ovejas_hombres = [uid for uid, oveja in ovejas_no_asignadas.items() if oveja.get('genero') == 'hombre']
        ovejas_mujeres = [uid for uid, oveja in ovejas_no_asignadas.items() if oveja.get('genero') == 'mujer']
        
        ovejas_asignadas_count = 0

        # Asignar ovejas a líderes del mismo género
        for ovejas_list, lideres_list in [(ovejas_hombres, lideres_hombres), (ovejas_mujeres, lideres_mujeres)]:
            if not lideres_list:
                continue

            num_ovejas = len(ovejas_list)
            num_lideres = len(lideres_list)
            ovejas_por_lider = num_ovejas // num_lideres
            restantes = num_ovejas % num_lideres

            random.shuffle(ovejas_list)
            lider_idx = 0
            oveja_idx = 0
            while oveja_idx < num_ovejas:
                for _ in range(ovejas_por_lider):
                    oveja_id = ovejas_list[oveja_idx]
                    ovejas_data[oveja_id]['lider_id'] = lideres_list[lider_idx]
                    firebase_put_sync(f"ovejas/{oveja_id}", ovejas_data[oveja_id])
                    oveja_idx += 1
                    ovejas_asignadas_count += 1
                
                # Asignar las ovejas restantes
                if restantes > 0:
                    oveja_id = ovejas_list[oveja_idx]
                    ovejas_data[oveja_id]['lider_id'] = lideres_list[lider_idx]
                    firebase_put_sync(f"ovejas/{oveja_id}", ovejas_data[oveja_id])
                    oveja_idx += 1
                    ovejas_asignadas_count += 1
                    restantes -= 1

                lider_idx = (lider_idx + 1) % num_lideres
        
        app.data_cache.get("ovejas").update(ovejas_data)
        app.data_cache.save_to_storage()

        if ovejas_asignadas_count > 0:
            mostrar_popup_exito(f"✅ {ovejas_asignadas_count} ovejas han sido asignadas automáticamente.", on_dismiss=lambda x: setattr(self.manager, 'current', 'menu_principal'))
        else:
            mostrar_popup_error("No se pudo realizar la asignación. Verifica que haya ovejas y líderes del mismo género.")

class ImportarOvejasScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayoutBG(bg_image='registrar_oveja_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        self.layout.add_widget(crear_titulo("Importar Ovejas (CSV)"))
        self.layout.add_widget(crear_label("Selecciona un archivo CSV para importar ovejas. La primera fila debe ser la cabecera.", color=GRAY))

        self.import_log = crear_label("Esperando selección de archivo...", halign='left', valign='top', text_size=(None, None))
        scroll_log = ScrollView(size_hint_y=0.7)
        scroll_log.add_widget(self.import_log)
        self.layout.add_widget(scroll_log)
        
        btn_seleccionar = crear_boton("📁 Seleccionar Archivo CSV", GREEN, self.seleccionar_archivo, alpha=0.8)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        
        self.layout.add_widget(btn_seleccionar)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def seleccionar_archivo(self, *args):
        # Esta es una implementación de MOCK para que el código sea funcional.
        # En una aplicación real de Android/iOS, usarías algo como plyer.filechooser
        mock_file_path = "ovejas_ejemplo.csv"
        # Crea un archivo de ejemplo si no existe
        if not os.path.exists(mock_file_path):
            with open(mock_file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['nombre', 'fecha_nacimiento', 'telefono', 'cedula', 'genero', 'tiempo_iglesia', 'bautizado', 'grupo_pequeno', 'empresa', 'direccion'])
                writer.writerow(['Juan Perez', '1990-05-15', '1234567890', '12345', 'hombre', '1 año', 'sí', 'Josués (35-55 años)', 'Empresa A', 'Calle 1'])
                writer.writerow(['Maria Lopez', '1995-10-20', '0987654321', '67890', 'mujer', '2 años', 'no', 'Mujer Integral', 'Empresa B', 'Carrera 2'])
        
        self.on_file_selection([mock_file_path])


    def on_file_selection(self, selection):
        if not selection:
            self.import_log.text = "No se seleccionó ningún archivo."
            return

        file_path = selection[0]
        self.import_log.text = f"Archivo seleccionado: {file_path}\nIniciando importación..."
        threading.Thread(target=self.procesar_csv_thread, args=(file_path,)).start()

    def procesar_csv_thread(self, file_path):
        app = App.get_running_app()
        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    datos = {
                        "nombre": row.get("nombre", ""),
                        "fecha_nacimiento": row.get("fecha_nacimiento", ""),
                        "telefono": row.get("telefono", ""),
                        "cedula": row.get("cedula", ""),
                        "genero": row.get("genero", ""),
                        "tiempo_iglesia": row.get("tiempo_iglesia", ""),
                        "bautizado": row.get("bautizado", ""),
                        "grupo_pequeno": row.get("grupo_pequeno", ""),
                        "lider_id": app.user_id,
                        "observaciones": "",
                        "empresa": row.get("empresa", ""),
                        "direccion": row.get("direccion", "")
                    }
                    if all(datos.get(key) for key in ["nombre", "cedula", "telefono"]):
                        firebase_post("ovejas", datos, on_complete=lambda s, r: self.post_import_update(s, r, datos['nombre']))
                    else:
                        Clock.schedule_once(lambda dt: self.import_log.text_size(self.import_log.text + f"Fila incompleta, omitida: {row}\n"), 0)

        except FileNotFoundError:
            Clock.schedule_once(lambda dt: mostrar_popup_error("Archivo no encontrado."), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: mostrar_popup_error(f"Error al procesar el archivo: {e}"), 0)

    def post_import_update(self, success, response, nombre_oveja):
        if success:
            new_id = response.get("name")
            oveja_data = App.get_running_app().data_cache.get("ovejas")
            if oveja_data is not None:
                oveja_data[new_id] = {'nombre': nombre_oveja} # Esto es un placeholder, la data completa se debería guardar aquí.
                App.get_runn# ========================
KIVY_FONT_FAMILY = None

# ========================
# 🙂 FUENTE PARA EMOJIS
# ========================
EMOJI_FONT_NAME = 'NotoEmoji'
EMOJI_FONT_AVAILABLE = os.path.exists('NotoEmoji-Regular.ttf')
if EMOJI_FONT_AVAILABLE:
    LabelBase.register(name=EMOJI_FONT_NAME, fn_regular='NotoEmoji-Regular.ttf')

def _split_emoji_prefix(texto):
    """Separa un emoji (o grupo de símbolos) al inicio del texto, si existe."""
    if not texto:
        return None, texto
    i = 0
    while i < len(texto) and ord(texto[i]) > 0x2000 and texto[i] != ' ':
        i += 1
    if i == 0:
        return None, texto
    return texto[:i], texto[i:].lstrip()

# ========================
# CONFIGURACIÓN VISUAL
# ========================
Window.clearcolor = get_color_from_hex('#000000')
Window.softinput_mode = 'below_target'
BLACK = '#000000'
WHITE = '#FFFFFF'
BLUE = '#1976D2'
DARK_BLUE = '#0D47A1'
LIGHT_BLUE = '#BBDEFB'
GRAY = '#757575'
RED = '#D32F2F'
GREEN = '#388E3C'
YELLOW = '#FFEB3B'
ORANGE = '#FF9800'

# ========================
# 🔥 CONFIGURACIÓN DE FIREBASE (TU PROYECTO)
# ========================
FIREBASE_URL = "https://redilejecutivo-d2bbc-default-rtdb.firebaseio.com"

# ========================
# 📧 CONFIGURACIÓN DE CORREO (PARA RECUPERAR CONTRASEÑA)
# Reemplaza estos dos valores con tu propia cuenta de Gmail
# y una "Contraseña de aplicación" generada en:
# https://myaccount.google.com/apppasswords
# ========================
SMTP_EMAIL = "redilejecutivo@gmail.com"
SMTP_PASSWORD = "pljd yuda gvrv gaqk"

def enviar_correo(destinatario, asunto, cuerpo, on_complete):
    def run():
        try:
            msg = MIMEText(cuerpo)
            msg['Subject'] = asunto
            msg['From'] = SMTP_EMAIL
            msg['To'] = destinatario

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.sendmail(SMTP_EMAIL, [destinatario], msg.as_string())
            Clock.schedule_once(lambda dt: on_complete(True, None), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: on_complete(False, str(e)), 0)
    threading.Thread(target=run).start()

# --- NUEVAS FUNCIONES PARA EL MANEJO DE LA CONEXIÓN Y LA CACHÉ ---
class NetworkStatus:
    _connected = True
    _last_check = None

    @staticmethod
    def check_connection():
        now = datetime.now()
        if NetworkStatus._last_check and (now - NetworkStatus._last_check).total_seconds() < 10:
            return NetworkStatus._connected
        try:
            requests.get("https://www.google.com", timeout=5)
            NetworkStatus._connected = True
        except requests.exceptions.RequestException:
            NetworkStatus._connected = False
        NetworkStatus._last_check = now
        return NetworkStatus._connected

class DataCache:
    def __init__(self):
        self.store = JsonStore('app_data.json')
        self.data = {
            'usuarios': {},
            'ovejas': {},
            'seguimientos': {},
            'chat': {},
            'offline_seguimientos': {}
        }
        self.load_from_storage()
        Clock.schedule_interval(self.sync_offline_data, 30)

    def load_from_storage(self):
        for key in self.data.keys():
            if self.store.exists(key):
                self.data[key] = self.store.get(key)['data']

    def save_to_storage(self):
        for key, value in self.data.items():
            self.store.put(key, data=value)

    def get(self, key):
        return self.data.get(key, {})

    def sync_all(self):
        if not NetworkStatus.check_connection():
            return False
        
        try:
            self.data['usuarios'] = requests.get(f"{FIREBASE_URL}/usuarios.json").json() or {}
            self.data['ovejas'] = requests.get(f"{FIREBASE_URL}/ovejas.json").json() or {}
            self.data['seguimientos'] = requests.get(f"{FIREBASE_URL}/seguimientos.json").json() or {}
            self.data['chat'] = requests.get(f"{FIREBASE_URL}/chat.json").json() or {}
            self.save_to_storage()
            self.sync_offline_data()
            return True
        except Exception as e:
            print(f"[ERROR] Sync failed: {e}")
            return False
            
    def save_offline_seguimiento(self, data):
        temp_id = str(random.randint(1000, 9999))
        self.data['offline_seguimientos'][temp_id] = data
        self.save_to_storage()
        return temp_id

    def sync_offline_data(self, dt=None):
        if not NetworkStatus.check_connection() or not self.data['offline_seguimientos']:
            return
        
        exitosos = []
        for temp_id, data in self.data['offline_seguimientos'].items():
            print(f"Intentando sincronizar seguimiento offline: {temp_id}")
            new_id = firebase_post_sync("seguimientos", data)
            if new_id:
                oveja_id = data.get('oveja_id')
                oveja_actual = self.get('ovejas').get(oveja_id)
                if oveja_actual:
                    oveja_actual['observaciones'] = data['contenido']
                    oveja_actual['fecha_ultimo_seguimiento'] = data['fecha_seguimiento']
                    firebase_put_sync(f"ovejas/{oveja_id}", oveja_actual)
                    self.data['ovejas'][oveja_id] = oveja_actual
                
                data['id'] = new_id
                self.data['seguimientos'][new_id] = data
                exitosos.append(temp_id)
            else:
                print(f"Falló la sincronización de {temp_id}.")

        for temp_id in exitosos:
            del self.data['offline_seguimientos'][temp_id]

        if exitosos:
            print("Sincronización offline completada.")
            self.save_to_storage()
            mostrar_popup_exito(f"✅ Se sincronizaron {len(exitosos)} seguimientos pendientes.")

class PushNotification:
    @staticmethod
    def send(user_id, title, message):
        print(f"Notificación enviada a {user_id}: {title} - {message}")

# --- Funciones de Firebase refactorizadas para usar threading y callbacks ---
def handle_firebase_request(method, path, data=None, on_success=None, on_error=None):
    def run_request():
        if not NetworkStatus.check_connection():
            if on_error:
                Clock.schedule_once(lambda dt: on_error("❌ No hay conexión a internet."), 0)
            return
        
        try:
            url = f"{FIREBASE_URL}/{path}.json"
            if method == "PUT":
                response = requests.put(url, data=json.dumps(data))
            elif method == "GET":
                response = requests.get(url)
            elif method == "POST":
                response = requests.post(url, data=json.dumps(data))
            elif method == "DELETE":
                response = requests.delete(url)
            else:
                if on_error:
                    Clock.schedule_once(lambda dt: on_error("Método no soportado."), 0)
                return

            if response.status_code == 200:
                if on_success:
                    Clock.schedule_once(lambda dt: on_success(response.json()), 0)
            else:
                print(f"[ERROR] Firebase {method} error: {response.text}")
                if on_error:
                    Clock.schedule_once(lambda dt: on_error(f"❌ Error en la comunicación con el servidor. Código: {response.status_code}"), 0)
        except Exception as e:
            print(f"[ERROR] Firebase {method}: {e}")
            if on_error:
                Clock.schedule_once(lambda dt: on_error("❌ Error en la comunicación con el servidor."), 0)

    threading.Thread(target=run_request).start()

def firebase_put(path, data, on_complete):
    handle_firebase_request("PUT", path, data, on_success=lambda res: on_complete(True, res), on_error=lambda err: on_complete(False, err))

def firebase_get(path, on_complete):
    handle_firebase_request("GET", path, on_success=lambda res: on_complete(True, res), on_error=lambda err: on_complete(False, err))

def firebase_post(path, data, on_complete):
    handle_firebase_request("POST", path, data, on_success=lambda res: on_complete(True, res), on_error=lambda err: on_complete(False, err))

def firebase_delete(path, on_complete):
    handle_firebase_request("DELETE", path, on_success=lambda res: on_complete(True, res), on_error=lambda err: on_complete(False, err))

# Versiones síncronas para uso específico (por ejemplo, en el sync offline)
def firebase_put_sync(path, data):
    try:
        requests.put(f"{FIREBASE_URL}/{path}.json", data=json.dumps(data)).raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

def firebase_post_sync(path, data):
    try:
        response = requests.post(f"{FIREBASE_URL}/{path}.json", data=json.dumps(data))
        response.raise_for_status()
        return response.json().get("name")
    except requests.exceptions.RequestException:
        return None

def firebase_get_sync(path):
    try:
        response = requests.get(f"{FIREBASE_URL}/{path}.json")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

def firebase_delete_sync(path):
    try:
        requests.delete(f"{FIREBASE_URL}/{path}.json").raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

# ========================
# GRUPOS Y OPCIONES
# ========================
GRUPOS_PEQUENOS = [
    "CASADOS", "Mujer Integral", "TMT (13-24 años)",
    "J+25 (25-34 años)", "Josués (35-55 años)",
    "Años Dorados", "Hombres de Bien", "Otros"
]
ROLES = ["lider", "director"]
GENEROS = ["hombre", "mujer"]
BAUTIZADO = ["sí", "no"]
PLANTILLAS = [
    "Oramos juntos por tu vida espiritual",
    "Hablamos de tu salud emocional",
    "Te animé en tu trabajo",
    "Te invite a la predica",
    "Oramos por tu familia",
    "compartimos palabra biblica",
    "Estamos orando por tu sanidad",
    "Gracias por tu fidelidad",
    "consegueria"
]

# ========================
# 🔆 BOXLAYOUT CON FONDO AJUSTADO A PANTALLA
# ========================
class BoxLayoutBG(BoxLayout):
    def __init__(self, bg_image=None, bg_color=None, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color or BLACK
        self.bg_image = bg_image
        
        with self.canvas.before:
            if self.bg_image and os.path.exists(self.bg_image):
                self.bg_rect = Rectangle(size=self.size, pos=self.pos, source=self.bg_image)
            else:
                Color(*get_color_from_hex(self.bg_color))
                self.bg_rect = Rectangle(pos=self.pos, size=self.size)

        self.bind(pos=self.update_bg, size=self.update_bg)

    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

# ========================
# FUNCIONES DE APOYO
# ========================
def crear_label(texto, **kwargs):
    if KIVY_FONT_FAMILY:
        kwargs['font_name'] = kwargs.get('font_name', KIVY_FONT_FAMILY)
    return Label(text=texto, **kwargs)

def crear_button(texto, **kwargs):
    if KIVY_FONT_FAMILY:
        kwargs['font_name'] = kwargs.get('font_name', KIVY_FONT_FAMILY)
    return Button(text=texto, **kwargs)

def crear_input(hint, password=False, multiline=False, text=None, input_filter=None):
    input_kwargs = {
        'hint_text': hint,
        'background_color': get_color_from_hex('#333333'),
        'foreground_color': get_color_from_hex(WHITE),
        'hint_text_color': get_color_from_hex('#AAAAAA'),
        'padding': dp(10),
        'password': password,
        'multiline': multiline,
        'size_hint_y': None,
        'height': dp(50) if not multiline else dp(100),
        'font_size': '14sp',
    }
    
    if KIVY_FONT_FAMILY:
        input_kwargs['font_name'] = KIVY_FONT_FAMILY
    
    if input_filter:
        input_kwargs['input_filter'] = input_filter

    input_field = TextInput(**input_kwargs)
    
    if text is not None:
        input_field.text = text
    return input_field
    
def mostrar_popup_exito(mensaje, on_dismiss=None, markup=False):
    content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
    content.add_widget(crear_label(mensaje, color=get_color_from_hex(WHITE), halign='center', markup=markup))
    btn = crear_boton("Aceptar", GREEN, size_hint_y=None, alpha=1)
    content.add_widget(btn)
    popup = Popup(title='Éxito', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.8, 0.4))
    if on_dismiss:
        popup.bind(on_dismiss=on_dismiss)
    btn.bind(on_press=popup.dismiss)
    popup.open()

def mostrar_popup_error(mensaje):
    content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
    content.add_widget(crear_label(mensaje, color=get_color_from_hex(WHITE), halign='center'))
    btn = crear_boton("✖ Cerrar", RED, size_hint_y=None, alpha=1)
    content.add_widget(btn)
    popup = Popup(title='Error', content=content, background_color=get_color_from_hex(RED), size_hint=(0.8, 0.4))
    btn.bind(on_press=popup.dismiss)
    popup.open()

def crear_titulo(texto, color=YELLOW):
    return crear_label(
        texto,
        color=get_color_from_hex(color),
        font_size='20sp',
        bold=True,
        size_hint_y=None,
        height=dp(40)
    )

class BotonRedondeado(Button):
    """Botón con esquinas totalmente redondeadas (forma ovalada/píldora)."""
    def __init__(self, rgba_color=(0.2, 0.4, 0.8, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.background_down = ''
        self.rgba_color = rgba_color
        with self.canvas.before:
            self.color_instr = Color(*self.rgba_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(24)])
        self.bind(pos=self._actualizar_rect, size=self._actualizar_rect)

    def _actualizar_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        self.rect.radius = [min(self.height, dp(30)) / 2]


def crear_boton(texto, color_hex, on_press=None, size_hint_y=None, alpha=1.0):
    """
    Crea un botón ovalado con color de fondo y transparencia personalizables.
    Si el texto empieza con un emoji y la fuente de emojis está disponible,
    el emoji se dibuja con esa fuente y el resto del texto con la fuente normal.
    """
    color = get_color_from_hex(color_hex)
    rgba_color = (color[0], color[1], color[2], alpha)

    emoji_char, texto_limpio = _split_emoji_prefix(texto)
    markup = False
    display_text = texto
    if emoji_char and EMOJI_FONT_AVAILABLE:
        display_text = f"[font={EMOJI_FONT_NAME}]{emoji_char}[/font] {texto_limpio}"
        markup = True
    elif emoji_char and not EMOJI_FONT_AVAILABLE:
        display_text = texto_limpio

    btn = BotonRedondeado(
        text=display_text,
        markup=markup,
        rgba_color=rgba_color,
        color=get_color_from_hex(WHITE),
        size_hint_y=size_hint_y or None,
        height=dp(45),
        font_size='14sp'
    )
    if on_press:
        btn.bind(on_press=on_press)
    return btn

# --- POPUP DE CALENDARIO REUTILIZABLE (con spinners seleccionables) ---
class CalendarPopup(Popup):
    def __init__(self, on_date_select, **kwargs):
        super().__init__(title='Selecciona una fecha', size_hint=(0.9, 0.7), **kwargs)
        self.on_date_select = on_date_select
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        anos = [str(a) for a in range(2025, 1899, -1)]
        meses = [f"{m:02d}" for m in range(1, 13)]
        dias = [f"{d:02d}" for d in range(1, 32)]

        content.add_widget(crear_label("Año", color=get_color_from_hex(WHITE), size_hint_y=None, height=dp(25)))
        self.spinner_year = Spinner(text=anos[0], values=anos, size_hint_y=None, height=dp(45))
        content.add_widget(self.spinner_year)

        content.add_widget(crear_label("Mes", color=get_color_from_hex(WHITE), size_hint_y=None, height=dp(25)))
        self.spinner_month = Spinner(text=meses[0], values=meses, size_hint_y=None, height=dp(45))
        content.add_widget(self.spinner_month)

        content.add_widget(crear_label("Día", color=get_color_from_hex(WHITE), size_hint_y=None, height=dp(25)))
        self.spinner_day = Spinner(text=dias[0], values=dias, size_hint_y=None, height=dp(45))
        content.add_widget(self.spinner_day)

        btn_guardar = crear_boton("💾 Guardar Fecha", GREEN, self.save_date)
        btn_cancel = crear_boton("✖ Cancelar", GRAY, self.dismiss)
        content.add_widget(btn_guardar)
        content.add_widget(btn_cancel)
        self.content = content

    def save_date(self, *args):
        try:
            y = int(self.spinner_year.text)
            m = int(self.spinner_month.text)
            d = int(self.spinner_day.text)
            self.on_date_select(f"{y:04d}-{m:02d}-{d:02d}")
            self.dismiss()
        except:
            mostrar_popup_error("Selecciona una fecha válida")

# ========================
# PANTALLAS
# ========================
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayoutBG(bg_image='login_background.png', orientation='vertical', padding=dp(30), spacing=dp(20))
        layout.add_widget(crear_label("RebañoEjecutivo", color=get_color_from_hex(YELLOW), font_size='28sp', bold=True, halign='center', size_hint_y=None, height=dp(50)))
        layout.add_widget(crear_label("Sistema de Pastoreo", color=get_color_from_hex(GRAY), font_size='16sp', halign='center', size_hint_y=None, height=dp(30)))
        self.username = crear_input("Nombre de usuario")
        self.password = crear_input("Contraseña", password=True)
        layout.add_widget(self.username)
        layout.add_widget(self.password)
        btn_login = crear_boton("🔐 Iniciar Sesión", BLUE, alpha=0.8)
        btn_login.bind(on_press=self.start_login)
        btn_register = crear_boton("📝 Crear Cuenta", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'register'), alpha=0.8)
        btn_recuperar = crear_boton("🔑 ¿Olvidaste tu contraseña?", GRAY, self.recuperar_contrasena, alpha=0.5)
        
        self.spinner = Spinner(text="Loading...", size_hint=(None, None), size=(dp(100), dp(50)), pos_hint={'center_x': 0.5}, opacity=0)
        
        layout.add_widget(btn_login)
        layout.add_widget(btn_register)
        layout.add_widget(btn_recuperar)
        layout.add_widget(self.spinner)
        self.add_widget(layout)
    
    def start_login(self, *args):
        self.spinner.opacity = 1
        username = self.username.text.strip()
        password = self.password.text.strip()
        if not username or not password:
            self.spinner.opacity = 0
            mostrar_popup_error("Completa todos los campos")
            return
        
        def on_login_complete(success, data):
            self.spinner.opacity = 0
            if success:
                for uid, user in data.items():
                    if user.get("nombre_usuario") == username:
                        hashed_input_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
                        if hashed_input_password == user.get("contraseña"):
                            app = App.get_running_app()
                            app.user_id = uid
                            app.nombre = user["nombre"]
                            app.rol = user["rol"]
                            app.store.put('user_session', id=uid, nombre=user["nombre"], rol=user["rol"])
                            self.manager.current = 'menu_principal'
                            app.data_cache.sync_all()
                            return
                mostrar_popup_error("Usuario o contraseña incorrectos")
            else:
                mostrar_popup_error(data)
        
        firebase_get("usuarios", on_complete=on_login_complete)

    def recuperar_contrasena(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label("Recuperar Contraseña", bold=True, color=get_color_from_hex(WHITE)))
        content.add_widget(crear_label("Ingresa tu nombre de usuario o correo", color=get_color_from_hex(GRAY)))
        input_recuperar = crear_input("Usuario o correo")
        content.add_widget(input_recuperar)

        estado = {"nueva_contrasena": None, "correo_destino": None}

        def correo_callback(success, error):
            if success:
                mostrar_popup_exito(f"✅ Hemos enviado tu nueva contraseña a:\n{estado['correo_destino']}\n\nRevisa tu bandeja de entrada (y la carpeta de spam).")
            else:
                mostrar_popup_error(f"❌ La contraseña se restableció pero no se pudo enviar el correo.\n\nDetalle: {error}")

        def reset_callback(success, response):
            if success:
                enviar_correo(
                    destinatario=estado['correo_destino'],
                    asunto="Recuperación de contraseña - RebañoEjecutivo",
                    cuerpo=f"Hola,\n\nTu nueva contraseña temporal es: {estado['nueva_contrasena']}\n\nPor favor inicia sesión con ella y considera cambiarla luego.\n\n- RebañoEjecutivo",
                    on_complete=correo_callback
                )
            else:
                mostrar_popup_error(f"❌ Error al restablecer la contraseña: {response}")

        def buscar_callback(success, data):
            if not success:
                popup.dismiss()
                mostrar_popup_error(data)
                return

            valor = input_recuperar.text.strip()
            for uid, user in data.items():
                if user.get("nombre_usuario") == valor or user.get("correo") == valor:
                    correo_usuario = user.get("correo")
                    if not correo_usuario:
                        popup.dismiss()
                        mostrar_popup_error("Este usuario no tiene un correo electrónico registrado.")
                        return
                    nueva = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
                    estado["nueva_contrasena"] = nueva
                    estado["correo_destino"] = correo_usuario
                    user['contraseña'] = hashlib.sha256(nueva.encode('utf-8')).hexdigest()
                    popup.dismiss()
                    firebase_put(f"usuarios/{uid}", user, on_complete=reset_callback)
                    return
            popup.dismiss()
            mostrar_popup_error("Usuario o correo no encontrado")

        def buscar_trigger(*args):
            valor = input_recuperar.text.strip()
            if not valor:
                mostrar_popup_error("Ingresa un usuario o correo")
                return
            firebase_get("usuarios", on_complete=buscar_callback)

        btn_buscar = crear_boton("🔄 Restablecer", GREEN, buscar_trigger, alpha=0.8)
        btn_cancel = crear_boton("✖ Cancelar", GRAY, lambda x: popup.dismiss(), alpha=0.8)
        content.add_widget(btn_buscar)
        content.add_widget(btn_cancel)
        popup = Popup(title='Recuperar Contraseña', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.6))
        self.popup_recuperar = popup
        popup.open()

class RegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.genero = None
        self.rol = None
        layout = BoxLayoutBG(bg_image='register_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        
        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll_layout = BoxLayout(orientation='vertical', padding=dp(0), spacing=dp(15), size_hint_y=None)
        scroll_layout.bind(minimum_height=scroll_layout.setter('height'))
        
        scroll_layout.add_widget(crear_titulo("Registro de Usuario"))
        self.username = crear_input("Nombre de usuario")
        self.email = crear_input("Correo electrónico")
        self.password = crear_input("Contraseña")
        self.confirm = crear_input("Confirmar contraseña")
        self.nombre = crear_input("Nombre")
        self.fecha = crear_input("Fecha nac. (AAAA-MM-DD)")
        self.tel = crear_input("Teléfono")
        self.cedula = crear_input("Cédula/ID")
        self.ministerio = crear_input("Ministerio")
        self.ministerio.text = "Ejecutivos"
        self.ministerio.readonly = True
        self.btn_genero = crear_boton("👤 Género: Seleccionar", LIGHT_BLUE, self.seleccionar_genero, alpha=0.5)
        self.btn_rol = crear_boton("🎭 Rol: Seleccionar", LIGHT_BLUE, self.seleccionar_rol, alpha=0.5)
        self.btn_fecha = crear_boton("📅 Elegir fecha de nacimiento", LIGHT_BLUE, self.abrir_calendario, alpha=0.5)

        for w in [self.username, self.email, self.password, self.confirm,
                  self.nombre, self.btn_fecha, self.tel, self.cedula, self.ministerio]:
            scroll_layout.add_widget(w)
        scroll_layout.add_widget(self.btn_genero)
        scroll_layout.add_widget(self.btn_rol)
        
        scroll_view.add_widget(scroll_layout)
        layout.add_widget(scroll_view)

        btn_reg = crear_boton("✅ Registrar", BLUE, self.registrar, alpha=0.8)
        btn_back = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'login'), alpha=0.8)
        layout.add_widget(btn_reg)
        layout.add_widget(btn_back)
        self.add_widget(layout)

    def seleccionar_genero(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("Selecciona el género", bold=True, color=get_color_from_hex(WHITE)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        for opcion in GENEROS:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_genero(op), alpha=0.8)
            grid.add_widget(btn)
        content.add_widget(grid)
        self.popup_genero_reg = Popup(title='Género', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_genero_reg.open()

    def set_genero(self, valor):
        self.genero = valor
        self.btn_genero.text = f"Género: {valor.upper()}"
        self.popup_genero_reg.dismiss()

    def seleccionar_rol(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("Selecciona el rol", bold=True, color=get_color_from_hex(WHITE)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        for opcion in ROLES:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_rol(op), alpha=0.8)
            grid.add_widget(btn)
        content.add_widget(grid)
        self.popup_rol = Popup(title='Rol', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_rol.open()

    def set_rol(self, valor):
        self.rol = valor
        self.btn_rol.text = f"Rol: {valor.upper()}"
        self.popup_rol.dismiss()


    def abrir_calendario(self, *args):
        popup = CalendarPopup(on_date_select=lambda date_str: setattr(self.fecha, 'text', date_str))
        popup.open()

    def registrar(self, *args):
        datos = {
            'nombre_usuario': self.username.text.strip(),
            'correo': self.email.text.strip(),
            'contraseña': self.password.text,
            'nombre': self.nombre.text.strip(),
            'fecha_nacimiento': self.fecha.text.strip(),
            'telefono': self.tel.text.strip(),
            'cedula': self.cedula.text.strip(),
            'ministerio': self.ministerio.text,
            'genero': self.genero,
            'rol': self.rol or "lider"
        }
        confirm = self.confirm.text
        errores = []
        if any(not v for v in [datos['nombre_usuario'], datos['correo'], datos['contraseña'], datos['nombre'], datos['fecha_nacimiento'], datos['telefono'], datos['cedula'], datos['ministerio']]):
            errores.append("Completa todos los campos obligatorios.")
        if datos['contraseña'] != confirm:
            errores.append("Las contraseñas no coinciden.")
        if len(datos['contraseña']) < 6:
            errores.append("La contraseña debe tener al menos 6 caracteres.")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", datos['correo']):
            errores.append("Formato de correo electrónico inválido.")
        if not datos['genero']:
            errores.append("Selecciona un género.")
        if not self.tel.text.isdigit() or not self.cedula.text.isdigit():
            errores.append("Teléfono y Cédula/ID deben ser numéricos.")
        if errores:
            mostrar_popup_error('\n'.join(errores))
            return
            
        datos['contraseña'] = hashlib.sha256(datos['contraseña'].encode('utf-8')).hexdigest()

        def on_register_complete(success, response):
            if success:
                mostrar_popup_exito("✅ Usuario registrado", on_dismiss=lambda x: setattr(self.manager, 'current', 'login'))
            else:
                mostrar_popup_error(f"❌ Error al registrar en Firebase: {response}")

        firebase_post("usuarios", datos, on_complete=on_register_complete)

class MenuPrincipalScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayoutBG(bg_image='menu_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        self.add_widget(self.layout)

    def construir_secciones(self, app):
        if app.rol == 'director':
            return [
                ("Ovejas", [
                    ("Registrar Oveja", 'registrar_oveja'),
                    ("Ver Todas las Ovejas", 'mis_ovejas'),
                    ("Reasignar Oveja", 'reasignar_oveja'),
                    ("Asignación Automática", 'asignacion_automatica'),
                    ("Importar Ovejas (CSV)", 'importar_ovejas'),
                ]),
                ("Seguimiento", [
                    ("Calendario de Seguimientos", 'calendario'),
                    ("Estadísticas", 'estadisticas'),
                    ("Hacer Seguimiento", 'seguimiento'),
                ]),
                ("Comunicación", [
                    ("Chat", 'chat'),
                ]),
                ("Administración", [
                    ("Gestionar Usuarios", 'gestionar_usuarios'),
                ]),
            ]
        else:
            return [
                ("Ovejas", [
                    ("Registrar Oveja", 'registrar_oveja'),
                    ("Mis Ovejas", 'mis_ovejas'),
                ]),
                ("Seguimiento", [
                    ("Calendario", 'calendario'),
                    ("Estadísticas", 'estadisticas'),
                    ("Hacer Seguimiento", 'seguimiento'),
                ]),
                ("Comunicación", [
                    ("Chat", 'chat'),
                ]),
            ]

    def on_enter(self):
        self.layout.clear_widgets()
        app = App.get_running_app()
        self.layout.add_widget(crear_titulo("Menú Principal"))

        accordion = Accordion(orientation='vertical', size_hint_y=1)

        secciones = self.construir_secciones(app)

        for titulo_seccion, opciones in secciones:
            item = AccordionItem(title=titulo_seccion)
            contenido = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8), size_hint_y=None)
            contenido.bind(minimum_height=contenido.setter('height'))
            for texto, destino in opciones:
                btn = crear_boton(texto, BLUE, alpha=0.8)
                btn.bind(on_press=lambda x, d=destino: setattr(self.manager, 'current', d))
                contenido.add_widget(btn)
            scroll = ScrollView()
            scroll.add_widget(contenido)
            item.add_widget(scroll)
            accordion.add_widget(item)

        self.layout.add_widget(accordion)

        btn_logout = crear_boton("🚪 Cerrar Sesión", DARK_BLUE, self.logout, alpha=0.8)
        self.layout.add_widget(btn_logout)

    def logout(self, instance):
        app = App.get_running_app()
        app.store.delete('user_session')
        app.user_id = None
        app.nombre = ""
        app.rol = ""
        self.manager.current = 'login'

class DashboardLiderScreen(Screen):
    def on_enter(self):
        self.clear_widgets()
        
        root_layout = AnchorLayout(anchor_x='center', anchor_y='center')
        content_layout = BoxLayoutBG(bg_image='dash_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        app = App.get_running_app()
        content_layout.add_widget(crear_titulo(f"Hola, {app.nombre}"))
        content_layout.add_widget(crear_titulo("Mi Dashboard", LIGHT_BLUE))
        
        ovejas_data = app.data_cache.get("ovejas")
        seguimientos_data = app.data_cache.get("seguimientos")
        lider_id = app.user_id
        
        mis_ovejas = [o for o in ovejas_data.values() if o.get('lider_id') == lider_id]
        
        num_ovejas = len(mis_ovejas)
        
        hoy = datetime.now().date()
        fecha_limite = hoy - timedelta(days=7)
        seguimientos_pendientes = 0
        for oveja in mis_ovejas:
            ultima_fecha_str = oveja.get("fecha_ultimo_seguimiento")
            if not ultima_fecha_str:
                seguimientos_pendientes += 1
                continue
            
            try:
                ultima_fecha = datetime.strptime(ultima_fecha_str, "%Y-%m-%d").date()
                if ultima_fecha < fecha_limite:
                    seguimientos_pendientes += 1
            except (ValueError, TypeError):
                seguimientos_pendientes += 1
                
        proximos_cumple = 0
        for oveja in mis_ovejas:
            try:
                fecha_nac_str = oveja.get('fecha_nacimiento')
                if fecha_nac_str:
                    fecha_nac = datetime.strptime(fecha_nac_str, "%Y-%m-%d").date()
                    cumple_este_año = fecha_nac.replace(year=hoy.year)
                    if cumple_este_año < hoy:
                        cumple_este_año = cumple_este_año.replace(year=hoy.year + 1)
                    
                    if timedelta(days=0) <= (cumple_este_año - hoy) <= timedelta(days=30):
                        proximos_cumple += 1
            except (ValueError, TypeError):
                pass
        
        content_layout.add_widget(self.crear_tarjeta_dashboard("Ovejas Asignadas", str(num_ovejas), WHITE, get_color_from_hex(YELLOW) + [0.5]))
        content_layout.add_widget(self.crear_tarjeta_dashboard("Seguimientos Pendientes", str(seguimientos_pendientes), WHITE, get_color_from_hex(RED) + [0.5]))
        content_layout.add_widget(self.crear_tarjeta_dashboard("Próximos Cumpleaños (30 días)", str(proximos_cumple), WHITE, get_color_from_hex(BLUE) + [0.5]))
        
        btn_volver_container = AnchorLayout(anchor_x='center', anchor_y='bottom', size_hint=(1, 0.1))
        btn_volver = crear_boton("Volver al Menú", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        btn_volver_container.add_widget(btn_volver)
        
        root_layout.add_widget(content_layout)
        root_layout.add_widget(btn_volver_container)
        
        self.add_widget(root_layout)
        
    def crear_tarjeta_dashboard(self, titulo, valor, color_texto, color_fondo):
        tarjeta = BoxLayout(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(5),
            size_hint_y=None,
            height=dp(150),
        )
        with tarjeta.canvas.before:
            Color(rgba=color_fondo)
            self.rect = Rectangle(pos=tarjeta.pos, size=tarjeta.size)
            tarjeta.bind(pos=self.update_rect, size=self.update_rect)
        
        tarjeta.add_widget(crear_label(titulo, color=get_color_from_hex(color_texto), font_size='18sp', bold=True))
        tarjeta.add_widget(crear_label(valor, color=get_color_from_hex(color_texto), font_size='48sp', bold=True))
        return tarjeta

    def update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

class RegistrarOvejaScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.genero = None
        self.bautizado = None
        self.grupo = None
        layout = BoxLayoutBG(bg_image='registrar_oveja_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        
        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll_layout = BoxLayout(orientation='vertical', padding=dp(0), spacing=dp(15), size_hint_y=None)
        scroll_layout.bind(minimum_height=scroll_layout.setter('height'))
        
        scroll_layout.add_widget(crear_titulo("Registrar Nueva Oveja"))
        self.nombre = crear_input("Nombre")
        self.fecha = crear_input("Fecha nac. (AAAA-MM-DD)")
        self.tel = crear_input("Teléfono")
        self.cedula = crear_input("Cédula/ID")
        self.tiempo = crear_input("Tiempo en la iglesia")
        self.empresa = crear_input("Empresa (opcional)")
        self.direccion = crear_input("Dirección (opcional)")
        self.btn_fecha = crear_boton("📅 Elegir fecha de nacimiento", LIGHT_BLUE, self.abrir_calendario, alpha=0.5)

        for w in [self.nombre, self.btn_fecha, self.tel, self.cedula, self.tiempo, self.empresa, self.direccion]:
            scroll_layout.add_widget(w)
            
        self.btn_genero = crear_boton("👤 Género: Seleccionar", LIGHT_BLUE, self.seleccionar_genero, alpha=0.5)
        self.btn_bautizado = crear_boton("✝ ¿Bautizado?: Seleccionar", LIGHT_BLUE, self.seleccionar_bautizado, alpha=0.5)
        self.btn_grupo = crear_boton("👥 Grupo pequeño: Seleccionar", LIGHT_BLUE, self.seleccionar_grupo, alpha=0.5)
        
        scroll_layout.add_widget(self.btn_genero)
        scroll_layout.add_widget(self.btn_bautizado)
        scroll_layout.add_widget(self.btn_grupo)
        
        btn_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(100), spacing=dp(10))
        btn_layout.add_widget(crear_boton("💾 Guardar", BLUE, self.guardar, alpha=0.8))
        btn_layout.add_widget(crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8))
        
        scroll_view.add_widget(scroll_layout)
        layout.add_widget(scroll_view)
        layout.add_widget(btn_layout)
        self.add_widget(layout)

    def abrir_calendario(self, *args):
        popup = CalendarPopup(on_date_select=lambda date_str: setattr(self.fecha, 'text', date_str))
        popup.open()

    def seleccionar_genero(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("Selecciona el género", bold=True, color=get_color_from_hex(WHITE)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        for opcion in GENEROS:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_genero(op), alpha=0.8)
            grid.add_widget(btn)
        content.add_widget(grid)
        self.popup_genero = Popup(title='Género', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_genero.open()

    def set_genero(self, valor):
        self.genero = valor
        self.btn_genero.text = f"Género: {valor.upper()}"
        self.popup_genero.dismiss()

    def seleccionar_bautizado(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("¿Está bautizado?", bold=True, color=get_color_from_hex(WHITE)))
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        for opcion in BAUTIZADO:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_bautizado(op), alpha=0.8)
            grid.add_widget(btn)
        content.add_widget(grid)
        self.popup_bautizado = Popup(title='¿Bautizado?', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_bautizado.open()

    def set_bautizado(self, valor):
        self.bautizado = valor
        self.btn_bautizado.text = f"¿Bautizado?: {valor.upper()}"
        self.popup_bautizado.dismiss()

    def seleccionar_grupo(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label("Grupo Pequeño", bold=True, color=get_color_from_hex(WHITE)))
        
        scroll = ScrollView(size_hint_y=None, height=dp(300))
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
        grid.bind(minimum_height=grid.setter('height'))
        
        for opcion in GRUPOS_PEQUENOS:
            btn = crear_boton(opcion, BLUE, lambda x, op=opcion: self.set_grupo(op), alpha=0.8)
            grid.add_widget(btn)
            
        scroll.add_widget(grid)
        content.add_widget(scroll)
        
        self.popup_grupo = Popup(title='Grupos', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_grupo.open()

    def set_grupo(self, valor):
        self.grupo = valor
        self.btn_grupo.text = f"Grupo: {valor}"
        self.popup_grupo.dismiss()

    def guardar(self, *args):
        app = App.get_running_app()
        if not all([self.nombre.text, self.fecha.text, self.tel.text, self.cedula.text, self.genero, self.bautizado, self.grupo]):
            mostrar_popup_error("Completa todos los campos obligatorios")
            return
        
        datos = {
            "nombre": self.nombre.text,
            "fecha_nacimiento": self.fecha.text,
            "telefono": self.tel.text,
            "cedula": self.cedula.text,
            "genero": self.genero,
            "tiempo_iglesia": self.tiempo.text,
            "bautizado": self.bautizado,
            "grupo_pequeno": self.grupo,
            "lider_id": app.user_id,
            "observaciones": "",
            "empresa": self.empresa.text,
            "direccion": self.direccion.text
        }
        
        def on_save_complete(success, response):
            if success and response:
                new_id = response.get("name")
                PushNotification.send(app.user_id, "Nueva Oveja Registrada", f"Has registrado a {self.nombre.text} en tu rebaño.")
                datos['id'] = new_id
                app.data_cache.get("ovejas")[new_id] = datos
                app.data_cache.save_to_storage()
                mostrar_popup_exito("✅ Oveja registrada", on_dismiss=lambda x: setattr(self.manager, 'current', 'menu_principal'))
            else:
                mostrar_popup_error(f"❌ Error al guardar en Firebase: {response}")

        firebase_post("ovejas", datos, on_complete=on_save_complete)

class MisOvejasScreen(Screen):
    oveja_a_editar_id = None
    popup_edit = None
    edit_nombre = None
    edit_tel = None
    edit_cedula = None
    edit_empresa = None
    edit_direccion = None
    edit_obs = None
    
    def on_enter(self):
        app = App.get_running_app()
        self.ovejas_data = app.data_cache.get("ovejas") or {}
        self.mostrar_ovejas()

    def mostrar_ovejas(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='mis_ovejas_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        
        app = App.get_running_app()
        
        self.mis_ovejas_items = []
        for oveja_id, oveja in self.ovejas_data.items():
            if app.rol == 'director' or oveja.get("lider_id") == app.user_id:
                oveja['id'] = oveja_id
                self.mis_ovejas_items.append(oveja)

        if app.rol == 'director':
            layout.add_widget(crear_titulo("Todas las Ovejas", color=LIGHT_BLUE))
        else:
            layout.add_widget(crear_titulo("Mis Ovejas"))
        
        self.search_input = crear_input("Buscar por nombre o cédula...")
        self.search_input.bind(text=self.schedule_filter)
        layout.add_widget(self.search_input)

        self.scroll = ScrollView()
        self.grid = GridLayout(cols=1, spacing=dp(15), size_hint_y=None, padding=dp(10))
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        layout.add_widget(self.scroll)

        self.actualizar_lista_ovejas(self.mis_ovejas_items)

        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

    def schedule_filter(self, instance, value):
        Clock.unschedule(self.filtrar_ovejas)
        Clock.schedule_once(lambda dt: self.filtrar_ovejas(instance, value), 0.5)

    def filtrar_ovejas(self, instance, value):
        filtro = value.lower()
        ovejas_filtradas = [
            o for o in self.mis_ovejas_items 
            if filtro in o['nombre'].lower() or filtro in o.get('cedula', '').lower()
        ]
        self.actualizar_lista_ovejas(ovejas_filtradas)

    def actualizar_lista_ovejas(self, ovejas):
        self.grid.clear_widgets()
        if not ovejas:
            self.grid.add_widget(crear_label("No se encontraron ovejas", color=get_color_from_hex(WHITE), size_hint_y=None, height=dp(50)))
        else:
            for o in ovejas:
                tarjeta = BoxLayoutBG(
                    orientation='vertical',
                    bg_color='#222222',
                    padding=dp(15),
                    spacing=dp(8),
                    size_hint_y=None,
                    height=dp(260)
                )
                header = BoxLayout(size_hint_y=None, height=dp(40))
                nombre_label = crear_label(
                    f" {o['nombre']}",
                    bold=True,
                    color=get_color_from_hex(WHITE),
                    size_hint=(0.8, 1),
                    halign='left',
                    valign='middle'
                )
                nombre_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
                header.add_widget(nombre_label)
                tarjeta.add_widget(header)
                tarjeta.add_widget(crear_label(f"Teléfono: {o.get('telefono', '')}", color=get_color_from_hex(GRAY), halign='left', font_size='13sp'))
                tarjeta.add_widget(crear_label(f"Cédula: {o.get('cedula', '')}", color=get_color_from_hex('#AAAAAA'), halign='left', font_size='12sp'))
                genero = "Hombre" if o.get('genero') == "hombre" else "Mujer"
                tarjeta.add_widget(crear_label(f"Género: {genero}", color=get_color_from_hex(BLUE), bold=True, halign='left', font_size='13sp'))
                tarjeta.add_widget(crear_label(
                    f"Empresa: {o.get('empresa', 'Sin empresa')}",
                    color=get_color_from_hex('#AAAAAA'),
                    halign='left',
                    font_size='12sp'
                ))
                tarjeta.add_widget(crear_label(
                    f"Dirección: {o.get('direccion', 'Sin dirección')}",
                    color=get_color_from_hex('#AAAAAA'),
                    halign='left',
                    font_size='12sp'
                ))
                obs = o.get('observaciones', '') or "Sin observaciones"
                obs_label = crear_label(
                    f"Observaciones: {obs}",
                    color=get_color_from_hex('#AAAAAA'),
                    halign='left',
                    valign='top',
                    font_size='12sp',
                    text_size=(dp(260), None),
                    size_hint_y=None,
                    height=dp(50)
                )
                tarjeta.add_widget(obs_label)
                btn_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
                btn_edit = crear_boton("✏ Editar", GREEN, lambda x, oveja_id=o['id'], oveja_data=o: self.editar_oveja(oveja_id, oveja_data), alpha=0.8)
                btn_del = crear_boton("🗑 Eliminar", RED, lambda x, oveja_id=o['id'], oveja_nombre=o['nombre']: self.confirmar_eliminar(oveja_id, oveja_nombre), alpha=0.8)
                btn_layout.add_widget(btn_edit)
                btn_layout.add_widget(btn_del)
                tarjeta.add_widget(btn_layout)
                self.grid.add_widget(tarjeta)

    def editar_oveja(self, oveja_id, oveja):
        self.oveja_a_editar_id = oveja_id
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label("Editar Oveja", bold=True, color=get_color_from_hex(WHITE)))
        
        self.edit_nombre = crear_input("Nombre", text=oveja.get('nombre', ''))
        self.edit_tel = crear_input("Teléfono", text=oveja.get('telefono', ''))
        self.edit_cedula = crear_input("Cédula/ID", text=oveja.get('cedula', ''))
        self.edit_empresa = crear_input("Empresa", text=oveja.get('empresa', ''))
        self.edit_direccion = crear_input("Dirección", text=oveja.get('direccion', ''))
        self.edit_obs = crear_input("Observaciones", multiline=True, text=oveja.get('observaciones', ''))
        
        for w in [self.edit_nombre, self.edit_tel, self.edit_cedula, self.edit_empresa, self.edit_direccion, self.edit_obs]:
            content.add_widget(w)
            
        btn_guardar = crear_boton("💾 Guardar", GREEN, self.guardar_cambios, alpha=0.8)
        btn_cancel = crear_boton("✖ Cancelar", GRAY, lambda x: self.popup_edit.dismiss(), alpha=0.8)
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_layout.add_widget(btn_guardar)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        
        self.popup_edit = Popup(title='Editar Oveja', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.9, 0.8))
        self.popup_edit.open()

    def guardar_cambios(self, *args):
        if not self.oveja_a_editar_id:
            mostrar_popup_error("Error: no se encontró la oveja a editar.")
            return

        oveja_actual = App.get_running_app().data_cache.get("ovejas").get(self.oveja_a_editar_id)
        if not oveja_actual:
            mostrar_popup_error("Error: no se pudo obtener la información actual de la oveja.")
            return

        datos_formulario = {
            "nombre": self.edit_nombre.text,
            "telefono": self.edit_tel.text,
            "cedula": self.edit_cedula.text,
            "empresa": self.edit_empresa.text,
            "direccion": self.edit_direccion.text,
            "observaciones": self.edit_obs.text
        }

        oveja_actual.update(datos_formulario)

        def on_update_complete(success, response):
            if success:
                self.popup_edit.dismiss()
                App.get_running_app().data_cache.get("ovejas")[self.oveja_a_editar_id] = oveja_actual
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito("✅ Oveja actualizada", on_dismiss=lambda x: self.on_enter())
            else:
                mostrar_popup_error(f"❌ Error al guardar los cambios en Firebase: {response}")

        firebase_put(f"ovejas/{self.oveja_a_editar_id}", oveja_actual, on_complete=on_update_complete)

    def confirmar_eliminar(self, oveja_id, oveja_nombre):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label(f"¿Estás seguro de eliminar a {oveja_nombre}?", color=get_color_from_hex(WHITE), halign='center'))
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_si = crear_boton("✅ Sí", RED, lambda x: self.eliminar_oveja(oveja_id), alpha=0.8)
        btn_no = crear_boton("✖ No", BLUE, lambda x: self.popup_confirmar.dismiss(), alpha=0.8)
        btn_layout.add_widget(btn_si)
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        self.popup_confirmar = Popup(title='Eliminar Oveja', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.8, 0.4))
        self.popup_confirmar.open()

    def eliminar_oveja(self, oveja_id):
        def on_delete_complete(success, response):
            if success:
                self.popup_confirmar.dismiss()
                App.get_running_app().data_cache.get("ovejas").pop(oveja_id, None)
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito("Oveja eliminada", on_dismiss=lambda x: self.on_enter())
            else:
                mostrar_popup_error(f"❌ Error al eliminar la oveja: {response}")
        
        firebase_delete(f"ovejas/{oveja_id}", on_complete=on_delete_complete)

class CalendarioScreen(Screen):
    def on_enter(self):
        self.cargar_seguimientos()

    def cargar_seguimientos(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='calendario_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        layout.add_widget(crear_titulo("Calendario de Seguimiento"))
        app = App.get_running_app()
        seguimientos = app.data_cache.get("seguimientos")
        ovejas_data = app.data_cache.get("ovejas")
        
        mis_seguimientos = []
        if seguimientos and ovejas_data:
            for seg in seguimientos.values():
                oveja_id = seg.get('oveja_id')
                oveja = ovejas_data.get(oveja_id)
                if oveja and (app.rol == 'director' or oveja.get("lider_id") == app.user_id):
                    seg["nombre_oveja"] = oveja["nombre"]
                    mis_seguimientos.append(seg)
        
        if not mis_seguimientos:
            layout.add_widget(crear_label("No hay seguimientos", color=get_color_from_hex(GRAY), halign='center'))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))
            for seg in mis_seguimientos:
                tarjeta = BoxLayoutBG(
                    orientation='vertical',
                    bg_color='#222222',
                    padding=dp(10),
                    spacing=dp(5),
                    size_hint_y=None,
                    height=dp(120)
                )
                tarjeta.add_widget(crear_label(f"Oveja: {seg.get('nombre_oveja', 'Desconocida')}", color=get_color_from_hex(WHITE), bold=True))
                tarjeta.add_widget(crear_label(f"Fecha: {seg.get('fecha_seguimiento', '')}", color=get_color_from_hex(YELLOW)))
                tarjeta.add_widget(crear_label(f"Tipo: {seg.get('tipo', 'Personalizado')}", color=get_color_from_hex(LIGHT_BLUE)))
                tarjeta.add_widget(crear_label(f"Contenido: {seg.get('contenido', '')[:50]}...", color=get_color_from_hex('#AAAAAA'), font_size='12sp'))
                grid.add_widget(tarjeta)
            scroll.add_widget(grid)
            layout.add_widget(scroll)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

class EstadisticasScreen(Screen):
    def on_enter(self):
        self.mostrar_estadisticas()

    def mostrar_estadisticas(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='estadisticas_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        layout.add_widget(crear_titulo("Estadísticas del Rebaño"))
        app = App.get_running_app()
        ovejas_data = app.data_cache.get("ovejas")
        
        if app.rol == 'director':
            ovejas_a_contar = list(ovejas_data.values()) if ovejas_data else []
        else:
            ovejas_a_contar = [o for o in ovejas_data.values() if o.get("lider_id") == app.user_id] if ovejas_data else []
        
        bautizadas = [o for o in ovejas_a_contar if o.get("bautizado") == "sí"]
        total = len(ovejas_a_contar)
        baut = len(bautizadas)
        pct = int(baut / total * 100) if total > 0 else 0
        layout.add_widget(crear_label(f"Total de ovejas: {total}", color=get_color_from_hex(WHITE)))
        layout.add_widget(crear_label(f"Bautizadas: {baut}", color=get_color_from_hex(GREEN)))
        layout.add_widget(crear_label(f"Porcentaje: {pct}%", color=get_color_from_hex(YELLOW)))

        # --- SECCIÓN AÑADIDA PARA MOSTRAR ASISTENCIAS ---
        layout.add_widget(crear_titulo("Asistencias Recientes", LIGHT_BLUE))
        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
        grid.bind(minimum_height=grid.setter('height'))

        for oveja in ovejas_a_contar:
            asistencias = oveja.get('asistencias', [])
            tarjeta = BoxLayoutBG(
                orientation='horizontal',
                bg_color='#222222',
                padding=dp(10),
                spacing=dp(5),
                size_hint_y=None,
                height=dp(60)
            )
            tarjeta.add_widget(crear_label(f"Nombre: {oveja.get('nombre', 'N/A')}", halign='left', color=get_color_from_hex(WHITE)))
            tarjeta.add_widget(crear_label(f"Asistencias: {len(asistencias)}", halign='right', color=get_color_from_hex(YELLOW)))
            grid.add_widget(tarjeta)

        scroll.add_widget(grid)
        layout.add_widget(scroll)
        # --- FIN SECCIÓN AÑADIDA ---

        if app.rol == 'director':
            btn_exportar = crear_boton("📤 Exportar a CSV", GREEN, self.exportar_a_csv, alpha=0.8)
            layout.add_widget(btn_exportar)

            btn_exportar_asistencias = crear_boton("📤 Exportar Asistencias", GREEN, self.exportar_asistencias_a_csv, alpha=0.8)
            layout.add_widget(btn_exportar_asistencias)

        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

    def exportar_a_csv(self, *args):
        ovejas_data = App.get_running_app().data_cache.get("ovejas") or {}
        if not ovejas_data:
            mostrar_popup_error("No hay datos de ovejas para exportar.")
            return
        
        filename = f"ovejas_rebaño_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

        headers = ["nombre", "cedula", "telefono", "genero", "bautizado", "grupo_pequeno", "lider_id", "observaciones", "empresa", "direccion"]
        
        try:
            from android.storage import primary_external_storage_path
            path = os.path.join(primary_external_storage_path(), 'Download', filename)
        except ImportError:
            path = filename

        with open(path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            for oveja in ovejas_data.values():
                writer.writerow({
                    "nombre": oveja.get("nombre", ""),
                    "cedula": oveja.get("cedula", ""),
                    "telefono": oveja.get("telefono", ""),
                    "genero": oveja.get("genero", ""),
                    "bautizado": oveja.get("bautizado", ""),
                    "grupo_pequeno": oveja.get("grupo_pequeno", ""),
                    "lider_id": oveja.get("lider_id", ""),
                    "observaciones": oveja.get("observaciones", ""),
                    "empresa": oveja.get("empresa", ""),
                    "direccion": oveja.get("direccion", "")
                })

        mostrar_popup_exito(f"✅ Datos exportados a:\n{path}", on_dismiss=lambda x: self.on_enter())
    
    def exportar_asistencias_a_csv(self, *args):
        ovejas_data = App.get_running_app().data_cache.get("ovejas") or {}
        if not ovejas_data:
            mostrar_popup_error("No hay datos de asistencias para exportar.")
            return

        filename = f"asistencias_rebaño_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

        headers = ["nombre", "fecha_asistencia"]
        
        try:
            from android.storage import primary_external_storage_path
            path = os.path.join(primary_external_storage_path(), 'Download', filename)
        except ImportError:
            path = filename

        with open(path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            for oveja in ovejas_data.values():
                asistencias = oveja.get('asistencias', [])
                for asistencia in asistencias:
                    writer.writerow({
                        "nombre": oveja.get("nombre", ""),
                        "fecha_asistencia": asistencia.get("fecha", "")
                    })

        mostrar_popup_exito(f"✅ Asistencias exportadas a:\n{path}")


class SeguimientoScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.oveja_a_seguir = None
        
    def on_enter(self):
        self.mostrar_ovejas()

    def mostrar_ovejas(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='seguimiento_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        layout.add_widget(crear_titulo("Hacer Seguimiento"))
        app = App.get_running_app()
        ovejas = app.data_cache.get("ovejas")
        mis_ovejas_con_id = []

        if ovejas:
            for oveja_id, oveja_data in ovejas.items():
                if app.rol == 'director' or oveja_data.get("lider_id") == app.user_id:
                    oveja_data['id'] = oveja_id
                    mis_ovejas_con_id.append(oveja_data)

        if not mis_ovejas_con_id:
            layout.add_widget(crear_label("No tienes ovejas asignadas", color=get_color_from_hex(RED), halign='center'))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))
            for o in mis_ovejas_con_id:
                btn = crear_boton(f"{o['nombre']}", BLUE, lambda x, oveja=o: self.abrir_seguimiento(oveja), alpha=0.8)
                grid.add_widget(btn)
            scroll.add_widget(grid)
            layout.add_widget(scroll)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

    def abrir_seguimiento(self, oveja):
        self.oveja_a_seguir = oveja
        
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label(f"Seguimiento a {oveja['nombre']}", bold=True, color=get_color_from_hex(WHITE)))
        self.menu = Popup(title="Plantillas", content=GridLayout(cols=1, spacing=dp(10)), size_hint=(0.9, 0.7))
        grid = self.menu.content
        for p in PLANTILLAS:
            btn = crear_boton(p, BLUE, lambda x, texto=p: usar_plantilla(texto), alpha=0.8)
            grid.add_widget(btn)
        btn_close = crear_boton("✖ Cerrar", GRAY, lambda x: self.menu.dismiss(), alpha=0.8)
        grid.add_widget(btn_close)

        def usar_plantilla(texto):
            self.obs_input.text = texto
            self.menu.dismiss()

        btn_plantilla = crear_boton("📋 Usar plantilla", YELLOW, lambda x: self.menu.open(), alpha=0.5)
        content.add_widget(btn_plantilla)
        
        obs_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(100), spacing=dp(5))
        self.obs_input = crear_input("Escribe lo que se habló...", multiline=True)
        obs_layout.add_widget(self.obs_input)
        
        btn_mic = Button(text="🎙️", size_hint_x=None, width=dp(50), font_size='25sp', background_color=get_color_from_hex(GRAY))
        obs_layout.add_widget(btn_mic)
        content.add_widget(obs_layout)

        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        
        # --- BOTÓN DE ASISTENCIA AÑADIDO ---
        btn_asistencia = crear_boton("✅ M Asist", ORANGE, lambda x: self.marcar_asistencia(), alpha=0.5)
        btn_layout.add_widget(btn_asistencia)
        # --- FIN BOTÓN DE ASISTENCIA AÑADIDO ---

        btn_guardar = crear_boton("💾 Guardar", GREEN, lambda x: self.guardar(), alpha=0.8)
        btn_llamar = crear_boton("📞 Llamar", DARK_BLUE, lambda x: mostrar_popup_error("Llamada no disponible"), alpha=0.8)
        btn_whatsapp = crear_boton("💬 WhatsApp", GREEN, lambda x: self.send_whatsapp_message(self.oveja_a_seguir.get('telefono')), alpha=0.8)
        
        btn_layout.add_widget(btn_guardar)
        btn_layout.add_widget(btn_llamar)
        btn_layout.add_widget(btn_whatsapp)
        content.add_widget(btn_layout)
        popup = Popup(title='Seguimiento', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.95, 0.8))
        self.popup_seguimiento = popup
        popup.open()

    def send_whatsapp_message(self, number):
        if not number:
            mostrar_popup_error("Número de teléfono no disponible.")
            return

        formatted_number = f"57{number.replace(' ', '').replace('-', '')}"
        webbrowser.open(f"https://wa.me/{formatted_number}")


    def guardar(self):
        texto = self.obs_input.text.strip()
        if not texto:
            mostrar_popup_error("Escribe lo que se habló")
            return
        
        app = App.get_running_app()
        datos_seguimiento = {
            "oveja_id": self.oveja_a_seguir['id'],
            "fecha_seguimiento": datetime.now().strftime("%Y-%m-%d"),
            "tipo": "Personalizado",
            "contenido": texto
        }
        
        if not NetworkStatus.check_connection():
            app.data_cache.save_offline_seguimiento(datos_seguimiento)
            self.popup_seguimiento.dismiss()
            mostrar_popup_exito("✅ Seguimiento guardado sin conexión. Se sincronizará automáticamente.", on_dismiss=lambda x: self.mostrar_ovejas())
            return
        
        def on_seguimiento_complete(success, response):
            if success and response:
                new_id_seg = response.get("name")
                oveja_actual = App.get_running_app().data_cache.get("ovejas").get(self.oveja_a_seguir['id'])
                
                def on_oveja_update_complete(success_update, response_update):
                    if success_update:
                        if oveja_actual:
                            app.data_cache.get("ovejas")[self.oveja_a_seguir['id']] = oveja_actual
                            datos_seguimiento['id'] = new_id_seg
                            app.data_cache.get("seguimientos")[new_id_seg] = datos_seguimiento
                            app.data_cache.save_to_storage()
                        
                        PushNotification.send(app.user_id, "Seguimiento Registrado", f"Has registrado un seguimiento para {oveja_actual['nombre']}.")
                        usuarios = app.data_cache.get('usuarios')
                        for uid, user in usuarios.items():
                            if user.get('rol') == 'director':
                                PushNotification.send(uid, "Nuevo Seguimiento", f"El líder {app.nombre} ha registrado un seguimiento para {oveja_actual['nombre']}.")

                        self.popup_seguimiento.dismiss()
                        mostrar_popup_exito("✅ Seguimiento y observaciones guardados", on_dismiss=lambda x: self.mostrar_ovejas())
                    else:
                        mostrar_popup_error(f"❌ Error al actualizar la oveja: {response_update}")

                if oveja_actual:
                    oveja_actual['observaciones'] = texto
                    oveja_actual['fecha_ultimo_seguimiento'] = datetime.now().strftime("%Y-%m-%d")
                    firebase_put(f"ovejas/{self.oveja_a_seguir['id']}", oveja_actual, on_complete=on_oveja_update_complete)
                else:
                    mostrar_popup_error("❌ Error al obtener los datos de la oveja.")

            else:
                mostrar_popup_error(f"❌ Error al guardar el seguimiento: {response}")

        firebase_post("seguimientos", datos_seguimiento, on_complete=on_seguimiento_complete)

    # --- MÉTODO PARA MARCAR ASISTENCIA CORREGIDO ---
    def marcar_asistencia(self):
        oveja_id = self.oveja_a_seguir['id']
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

        oveja_actual = App.get_running_app().data_cache.get("ovejas").get(oveja_id)
        if oveja_actual is None:
            mostrar_popup_error("Error: No se pudo encontrar la oveja para marcar asistencia.")
            return

        asistencias = oveja_actual.get("asistencias", [])
        
        if any(asist.get('fecha') == fecha_hoy for asist in asistencias):
            mostrar_popup_error("Ya se ha marcado la asistencia de esta oveja para hoy.")
            return
            
        nueva_asistencia = {
            "fecha": fecha_hoy,
            "asistio": True,
            "evento": "Servicio o reunión"
        }
        asistencias.append(nueva_asistencia)
        oveja_actual["asistencias"] = asistencias

        def on_asistencia_complete(success, response):
            if success:
                self.popup_seguimiento.dismiss()
                App.get_running_app().data_cache.get("ovejas")[oveja_id] = oveja_actual
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito("✅ Asistencia marcada con éxito.")
            else:
                mostrar_popup_error(f"❌ Error al marcar la asistencia: {response}")
        
        firebase_put(f"ovejas/{oveja_id}", oveja_actual, on_complete=on_asistencia_complete)
    # --- FIN MÉTODO CORREGIDO ---

class ChatScreen(Screen):
    def on_enter(self):
        self.mostrar_usuarios()

    def mostrar_usuarios(self):
        self.clear_widgets()
        layout = BoxLayoutBG(bg_image='chat_background.png', orientation='vertical', padding=dp(15), spacing=dp(10))
        layout.add_widget(crear_titulo("Chat"))
        app = App.get_running_app()
        usuarios = app.data_cache.get("usuarios")
        otros = [u for u in usuarios.values() if u.get("id") != app.user_id]
        if not otros:
            layout.add_widget(crear_label("No hay usuarios", color=get_color_from_hex(GRAY), halign='center'))
        else:
            for otro in otros:
                btn = crear_boton(f"Chat con {otro['nombre']}", BLUE, lambda x, o=otro: self.abrir_chat_con(o), alpha=0.8)
                layout.add_widget(btn)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        layout.add_widget(btn_volver)
        self.add_widget(layout)

    def abrir_chat_con(self, otro):
        app = App.get_running_app()
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(crear_label(f"Chat con {otro['nombre']}", bold=True, color=get_color_from_hex(WHITE)))
        scroll = ScrollView()
        self.mensajes_layout = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        self.mensajes_layout.bind(minimum_height=self.mensajes_layout.setter('height'))
        scroll.add_widget(self.mensajes_layout)
        content.add_widget(scroll)
        self.input_mensaje = crear_input("Escribe un mensaje...", multiline=False)
        content.add_widget(self.input_mensaje)
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_enviar = crear_boton("📨 Enviar", GREEN, self.enviar_mensaje, alpha=0.8)
        btn_enviar.bind(on_press=lambda x: setattr(self, 'destinatario_id', otro.get('id')))
        btn_volver = crear_boton("< Volver", GRAY, lambda x: popup.dismiss(), alpha=0.8)
        btn_layout.add_widget(btn_enviar)
        btn_layout.add_widget(btn_volver)
        content.add_widget(btn_layout)
        popup = Popup(title=f"Chat con {otro['nombre']}", content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.95, 0.9))
        self.popup_chat = popup
        self.destinatario_id = otro.get('id')
        self.cargar_mensajes(app.user_id, self.destinatario_id)
        popup.open()

    def cargar_mensajes(self, remitente, destinatario):
        self.mensajes_layout.clear_widgets()
        mensajes = App.get_running_app().data_cache.get("chat")
        for mid, m in mensajes.items():
            if (m.get("remitente_id") == remitente and m.get("destinatario_id") == destinatario) or \
               (m.get("remitente_id") == destinatario and m.get("destinatario_id") == remitente):
                self.mensajes_layout.add_widget(crear_label(
                    f"[b]{m.get('remitente_nombre', 'Anónimo')}:[/b] {m.get('mensaje', '')} \n[size=10][i]{m.get('fecha', '')}[/i][/size]",
                    markup=True,
                    color=get_color_from_hex(WHITE),
                    halign='left',
                    size_hint_y=None,
                    height=dp(50)
                ))

    def enviar_mensaje(self, *args):
        texto = self.input_mensaje.text.strip()
        if not texto:
            return
        app = App.get_running_app()
        datos = {
            "remitente_id": app.user_id,
            "remitente_nombre": app.nombre,
            "destinatario_id": self.destinatario_id,
            "mensaje": texto,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        def on_send_complete(success, response):
            if success and response:
                new_id = response.get("name")
                datos['id'] = new_id
                app.data_cache.get("chat")[new_id] = datos
                app.data_cache.save_to_storage()
                self.input_mensaje.text = ""
                self.cargar_mensajes(app.user_id, self.destinatario_id)
                PushNotification.send(self.destinatario_id, f"Nuevo Mensaje de {app.nombre}", texto)
            else:
                mostrar_popup_error(f"❌ Error al enviar el mensaje: {response}")

        firebase_post("chat", datos, on_complete=on_send_complete)

class GestionarUsuariosScreen(Screen):
    def on_enter(self):
        self.mostrar_usuarios()
        
    def mostrar_usuarios(self):
        self.clear_widgets()
        self.layout = BoxLayoutBG(bg_image='gestionar_usuarios_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        self.layout.add_widget(crear_titulo("Gestionar Usuarios"))

        app = App.get_running_app()
        usuarios = App.get_running_app().data_cache.get("usuarios")
        
        if not usuarios:
            self.layout.add_widget(crear_label("No hay usuarios registrados", color=get_color_from_hex(RED)))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(15), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))

            for uid, user_data in usuarios.items():
                if uid == app.user_id:
                    continue

                tarjeta = BoxLayoutBG(
                    orientation='vertical',
                    bg_color='#222222',
                    padding=dp(15),
                    spacing=dp(8),
                    size_hint_y=None,
                    height=dp(200)
                )

                tarjeta.add_widget(crear_label(f"Usuario: {user_data.get('nombre', 'Desconocido')}", color=get_color_from_hex(WHITE), bold=True))
                tarjeta.add_widget(crear_label(f"Correo: {user_data.get('correo', 'Sin correo')}", color=get_color_from_hex(GRAY), font_size='12sp'))
                
                rol_text = f"Rol: {user_data.get('rol', 'lider').upper()}"
                rol_color = GREEN if user_data.get('rol') == 'director' else LIGHT_BLUE
                tarjeta.add_widget(crear_label(rol_text, color=get_color_from_hex(rol_color), bold=True))
                
                btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
                
                btn_rol = crear_boton("🔄 Cambiar Rol", ORANGE, lambda x, user_id=uid, user_name=user_data.get('nombre'), current_rol=user_data.get('rol'): self.cambiar_rol(user_id, user_name, current_rol), alpha=0.8)
                btn_reset_pass = crear_boton("🔑 Reset Pass", YELLOW, lambda x, user_id=uid: self.reset_pass(user_id), alpha=0.8)
                btn_eliminar = crear_boton("🗑 Eliminar", RED, lambda x, user_id=uid, user_name=user_data.get('nombre'): self.confirmar_eliminar(user_id, user_name), alpha=0.8)
                
                btn_layout.add_widget(btn_rol)
                btn_layout.add_widget(btn_reset_pass)
                btn_layout.add_widget(btn_eliminar)

                tarjeta.add_widget(btn_layout)
                grid.add_widget(tarjeta)

            scroll.add_widget(grid)
            self.layout.add_widget(scroll)

        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def cambiar_rol(self, user_id, user_name, current_rol):
        nuevo_rol = "director" if current_rol == "lider" else "lider"
        user_data = App.get_running_app().data_cache.get("usuarios").get(user_id)
        if not user_data:
            mostrar_popup_error("Usuario no encontrado.")
            return
        
        user_data['rol'] = nuevo_rol
        
        def on_change_rol_complete(success, response):
            if success:
                App.get_running_app().data_cache.get("usuarios")[user_id] = user_data
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito(f"✅ Rol de {user_name} cambiado a {nuevo_rol.upper()}", on_dismiss=lambda x: self.mostrar_usuarios())
            else:
                mostrar_popup_error(f"❌ Error al cambiar el rol: {response}")

        firebase_put(f"usuarios/{user_id}", user_data, on_complete=on_change_rol_complete)

    def reset_pass(self, user_id):
        new_pass = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
        hashed_password = hashlib.sha256(new_pass.encode('utf-8')).hexdigest()
        
        user_data = App.get_running_app().data_cache.get("usuarios").get(user_id)
        if not user_data:
            mostrar_popup_error("Usuario no encontrado.")
            return
        
        user_data['contraseña'] = hashed_password

        def on_reset_complete(success, response):
            if success:
                App.get_running_app().data_cache.get("usuarios")[user_id] = user_data
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito(f"✅ La nueva contraseña temporal es: [b]{new_pass}[/b]\nPor favor, comunícala al usuario.", markup=True)
            else:
                mostrar_popup_error(f"❌ Error al resetear la contraseña: {response}")
        
        firebase_put(f"usuarios/{user_id}", user_data, on_complete=on_reset_complete)

    def confirmar_eliminar(self, user_id, user_name):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label(f"¿Estás seguro de eliminar a {user_name}?", color=get_color_from_hex(WHITE), halign='center'))
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_si = crear_boton("🗑 Sí, eliminar", RED, lambda x: self.eliminar_usuario(user_id), alpha=0.8)
        btn_no = crear_boton("✖ No, cancelar", BLUE, lambda x: self.popup_confirmar.dismiss(), alpha=0.8)
        btn_layout.add_widget(btn_si)
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        self.popup_confirmar = Popup(title='Eliminar Usuario', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.8, 0.4))
        self.popup_confirmar.open()

    def eliminar_usuario(self, user_id):
        ovejas = App.get_running_app().data_cache.get("ovejas")
        if ovejas:
            for oveja_id, oveja_data in ovejas.items():
                if oveja_data.get('lider_id') == user_id:
                    oveja_data['lider_id'] = None
                    firebase_put_sync(f"ovejas/{oveja_id}", oveja_data)

        def on_delete_complete(success, response):
            if success:
                self.popup_confirmar.dismiss()
                App.get_running_app().data_cache.get("usuarios").pop(user_id, None)
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito("Usuario eliminado", on_dismiss=lambda x: self.mostrar_usuarios())
            else:
                mostrar_popup_error(f"❌ Error al eliminar el usuario: {response}")
        
        firebase_delete(f"usuarios/{user_id}", on_complete=on_delete_complete)

class ReasignarOvejaScreen(Screen):
    def on_enter(self):
        self.mostrar_ovejas()

    def mostrar_ovejas(self):
        self.clear_widgets()
        self.layout = BoxLayoutBG(bg_image='reasignar_oveja_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        self.layout.add_widget(crear_titulo("Selecciona una Oveja"))

        ovejas = App.get_running_app().data_cache.get("ovejas")
        ovejas_list = []
        if ovejas:
            for oveja_id, oveja_data in ovejas.items():
                oveja_data['id'] = oveja_id
                ovejas_list.append(oveja_data)

        if not ovejas_list:
            self.layout.add_widget(crear_label("No hay ovejas registradas", color=get_color_from_hex(RED)))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))
            for o in ovejas_list:
                btn = crear_boton(f"{o['nombre']}", BLUE, lambda x, oveja=o: self.seleccionar_lider(oveja), alpha=0.8)
                grid.add_widget(btn)
            scroll.add_widget(grid)
            self.layout.add_widget(scroll)

        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def seleccionar_lider(self, oveja):
        self.clear_widgets()
        self.layout = BoxLayoutBG(bg_image='reasignar_oveja_background.png', orientation='vertical', padding=dp(15), spacing=dp(15))
        self.layout.add_widget(crear_titulo(f"Asignar a {oveja['nombre']}"))
        
        usuarios = App.get_running_app().data_cache.get("usuarios")
        lideres = []
        if usuarios:
            for uid, user_data in usuarios.items():
                if user_data.get('rol') == 'lider':
                    user_data['id'] = uid
                    lideres.append(user_data)
        
        if not lideres:
            self.layout.add_widget(crear_label("No hay líderes disponibles", color=get_color_from_hex(RED)))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=dp(10))
            grid.bind(minimum_height=grid.setter('height'))
            for l in lideres:
                btn = crear_boton(f"{l['nombre']}", GREEN, lambda x, lider=l: self.confirmar_reasignacion(oveja, lider), alpha=0.8)
                grid.add_widget(btn)
            scroll.add_widget(grid)
            self.layout.add_widget(scroll)
        
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: self.mostrar_ovejas(), alpha=0.8)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def confirmar_reasignacion(self, oveja, lider):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        content.add_widget(crear_label(f"¿Reasignar a {oveja['nombre']} a {lider['nombre']}?", color=get_color_from_hex(WHITE), halign='center'))
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_si = crear_boton("🔄 Sí, reasignar", RED, lambda x: self.reasignar(oveja, lider), alpha=0.8)
        btn_no = crear_boton("✖ No, cancelar", BLUE, lambda x: self.popup.dismiss(), alpha=0.8)
        btn_layout.add_widget(btn_si)
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        self.popup = Popup(title='Confirmar Reasignación', content=content, background_color=get_color_from_hex(BLACK), size_hint=(0.8, 0.4))
        self.popup.open()

    def reasignar(self, oveja, lider):
        oveja['lider_id'] = lider['id']
        
        def on_reasign_complete(success, response):
            if success:
                self.popup.dismiss()
                PushNotification.send(lider['id'], "Oveja Reasignada", f"Se te ha asignado una nueva oveja: {oveja['nombre']}.")
                App.get_running_app().data_cache.get("ovejas")[oveja['id']] = oveja
                App.get_running_app().data_cache.save_to_storage()
                mostrar_popup_exito(f"✅ Oveja reasignada a {lider['nombre']}", on_dismiss=lambda x: setattr(self.manager, 'current', 'menu_principal'))
            else:
                mostrar_popup_error(f"❌ Error al reasignar la oveja: {response}")

        firebase_put(f"ovejas/{oveja['id']}", oveja, on_complete=on_reasign_complete)

class AsignacionAutomaticaScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayoutBG(bg_image='asignacion_automatica_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        
        self.layout.add_widget(crear_titulo("Asignación Automática"))
        self.layout.add_widget(crear_label("Esto asignará ovejas a líderes según su género, y las ovejas restantes se distribuirán equitativamente.",
                                     color=get_color_from_hex(GRAY), halign='center'))
        
        btn_iniciar = crear_boton("🔀 Iniciar Asignación", GREEN, self.iniciar_asignacion_automatica, alpha=0.8)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        
        self.layout.add_widget(btn_iniciar)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def iniciar_asignacion_automatica(self, *args):
        app = App.get_running_app()
        usuarios = app.data_cache.get("usuarios")
        ovejas_data = app.data_cache.get("ovejas")

        if not usuarios or not ovejas_data:
            mostrar_popup_error("No hay suficientes usuarios u ovejas para la asignación.")
            return

        lideres = {uid: user for uid, user in usuarios.items() if user.get('rol') == 'lider'}
        ovejas_no_asignadas = {uid: oveja for uid, oveja in ovejas_data.items() if not oveja.get('lider_id')}
        
        if not lideres or not ovejas_no_asignadas:
            mostrar_popup_exito("No hay ovejas sin asignar o líderes disponibles.")
            return

        lideres_hombres = [uid for uid, user in lideres.items() if user.get('genero') == 'hombre']
        lideres_mujeres = [uid for uid, user in lideres.items() if user.get('genero') == 'mujer']
        
        ovejas_hombres = [uid for uid, oveja in ovejas_no_asignadas.items() if oveja.get('genero') == 'hombre']
        ovejas_mujeres = [uid for uid, oveja in ovejas_no_asignadas.items() if oveja.get('genero') == 'mujer']
        
        ovejas_asignadas_count = 0

        # Asignar ovejas a líderes del mismo género
        for ovejas_list, lideres_list in [(ovejas_hombres, lideres_hombres), (ovejas_mujeres, lideres_mujeres)]:
            if not lideres_list:
                continue

            num_ovejas = len(ovejas_list)
            num_lideres = len(lideres_list)
            ovejas_por_lider = num_ovejas // num_lideres
            restantes = num_ovejas % num_lideres

            random.shuffle(ovejas_list)
            lider_idx = 0
            oveja_idx = 0
            while oveja_idx < num_ovejas:
                for _ in range(ovejas_por_lider):
                    oveja_id = ovejas_list[oveja_idx]
                    ovejas_data[oveja_id]['lider_id'] = lideres_list[lider_idx]
                    firebase_put_sync(f"ovejas/{oveja_id}", ovejas_data[oveja_id])
                    oveja_idx += 1
                    ovejas_asignadas_count += 1
                
                # Asignar las ovejas restantes
                if restantes > 0:
                    oveja_id = ovejas_list[oveja_idx]
                    ovejas_data[oveja_id]['lider_id'] = lideres_list[lider_idx]
                    firebase_put_sync(f"ovejas/{oveja_id}", ovejas_data[oveja_id])
                    oveja_idx += 1
                    ovejas_asignadas_count += 1
                    restantes -= 1

                lider_idx = (lider_idx + 1) % num_lideres
        
        app.data_cache.get("ovejas").update(ovejas_data)
        app.data_cache.save_to_storage()

        if ovejas_asignadas_count > 0:
            mostrar_popup_exito(f"✅ {ovejas_asignadas_count} ovejas han sido asignadas automáticamente.", on_dismiss=lambda x: setattr(self.manager, 'current', 'menu_principal'))
        else:
            mostrar_popup_error("No se pudo realizar la asignación. Verifica que haya ovejas y líderes del mismo género.")

class ImportarOvejasScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayoutBG(bg_image='registrar_oveja_background.png', orientation='vertical', padding=dp(20), spacing=dp(15))
        self.layout.add_widget(crear_titulo("Importar Ovejas (CSV)"))
        self.layout.add_widget(crear_label("Selecciona un archivo CSV para importar ovejas. La primera fila debe ser la cabecera.", color=GRAY))

        self.import_log = crear_label("Esperando selección de archivo...", halign='left', valign='top', text_size=(None, None))
        scroll_log = ScrollView(size_hint_y=0.7)
        scroll_log.add_widget(self.import_log)
        self.layout.add_widget(scroll_log)
        
        btn_seleccionar = crear_boton("📁 Seleccionar Archivo CSV", GREEN, self.seleccionar_archivo, alpha=0.8)
        btn_volver = crear_boton("< Volver", DARK_BLUE, lambda x: setattr(self.manager, 'current', 'menu_principal'), alpha=0.8)
        
        self.layout.add_widget(btn_seleccionar)
        self.layout.add_widget(btn_volver)
        self.add_widget(self.layout)

    def seleccionar_archivo(self, *args):
        # Esta es una implementación de MOCK para que el código sea funcional.
        # En una aplicación real de Android/iOS, usarías algo como plyer.filechooser
        mock_file_path = "ovejas_ejemplo.csv"
        # Crea un archivo de ejemplo si no existe
        if not os.path.exists(mock_file_path):
            with open(mock_file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['nombre', 'fecha_nacimiento', 'telefono', 'cedula', 'genero', 'tiempo_iglesia', 'bautizado', 'grupo_pequeno', 'empresa', 'direccion'])
                writer.writerow(['Juan Perez', '1990-05-15', '1234567890', '12345', 'hombre', '1 año', 'sí', 'Josués (35-55 años)', 'Empresa A', 'Calle 1'])
                writer.writerow(['Maria Lopez', '1995-10-20', '0987654321', '67890', 'mujer', '2 años', 'no', 'Mujer Integral', 'Empresa B', 'Carrera 2'])
        
        self.on_file_selection([mock_file_path])


    def on_file_selection(self, selection):
        if not selection:
            self.import_log.text = "No se seleccionó ningún archivo."
            return

        file_path = selection[0]
        self.import_log.text = f"Archivo seleccionado: {file_path}\nIniciando importación..."
        threading.Thread(target=self.procesar_csv_thread, args=(file_path,)).start()

    def procesar_csv_thread(self, file_path):
        app = App.get_running_app()
        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    datos = {
                        "nombre": row.get("nombre", ""),
                        "fecha_nacimiento": row.get("fecha_nacimiento", ""),
                        "telefono": row.get("telefono", ""),
                        "cedula": row.get("cedula", ""),
                        "genero": row.get("genero", ""),
                        "tiempo_iglesia": row.get("tiempo_iglesia", ""),
                        "bautizado": row.get("bautizado", ""),
                        "grupo_pequeno": row.get("grupo_pequeno", ""),
                        "lider_id": app.user_id,
                        "observaciones": "",
                        "empresa": row.get("empresa", ""),
                        "direccion": row.get("direccion", "")
                    }
                    if all(datos.get(key) for key in ["nombre", "cedula", "telefono"]):
                        firebase_post("ovejas", datos, on_complete=lambda s, r: self.post_import_update(s, r, datos['nombre']))
                    else:
                        Clock.schedule_once(lambda dt: self.import_log.text_size(self.import_log.text + f"Fila incompleta, omitida: {row}\n"), 0)

        except FileNotFoundError:
            Clock.schedule_once(lambda dt: mostrar_popup_error("Archivo no encontrado."), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: mostrar_popup_error(f"Error al procesar el archivo: {e}"), 0)

    def post_import_update(self, success, response, nombre_oveja):
        if success:
            new_id = response.get("name")
            oveja_data = App.get_running_app().data_cache.get("ovejas")
            if oveja_data is not None:
                oveja_data[new_id] = {'nombre': nombre_oveja} # Esto es un placeholder, la data completa se debería guardar aquí.
                App.get_running_app().data_cache.save_to_storage()
            Clock.schedule_once(lambda dt: setattr(self.import_log, 'text', self.import_log.text + f"✅ Oveja '{nombre_oveja}' importada con éxito.\n"), 0)
        else:
            Clock.schedule_once(lambda dt: setattr(self.import_log, 'text', self.import_log.text + f"❌ Error al importar a '{nombre_oveja}': {response}\n"), 0)


# ========================
# APP PRINCIPAL
# ========================
class RebañoApp(App):
    user_id = None
    nombre = ""
    rol = ""
    data_cache = None
    store = None

    def asegurar_usuario_admin(self):
        def check_callback(success, data):
            if not success:
                return
            data = data or {}
            existe = any(u.get('nombre_usuario') == 'admin' for u in data.values())
            if existe:
                return
            admin_data = {
                'nombre_usuario': 'admin',
                'correo': 'admin@rebanoejecutivo.com',
                'contraseña': hashlib.sha256('123456'.encode('utf-8')).hexdigest(),
                'nombre': 'Administrador',
                'fecha_nacimiento': '',
                'telefono': '0000000000',
                'cedula': '0000000000',
                'ministerio': 'Ejecutivos',
                'genero': 'hombre',
                'rol': 'director'
            }
            firebase_post('usuarios', admin_data, on_complete=lambda s, r: None)

        firebase_get('usuarios', on_complete=check_callback)

    def build(self):
        self.data_cache = DataCache()
        self.store = JsonStore('user_session.json')
        self.asegurar_usuario_admin()
        sm = ScreenManager()
        
        # Agrega todas las pantallas primero
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(RegisterScreen(name='register'))
        sm.add_widget(MenuPrincipalScreen(name='menu_principal'))
        sm.add_widget(RegistrarOvejaScreen(name='registrar_oveja'))
        sm.add_widget(MisOvejasScreen(name='mis_ovejas'))
        sm.add_widget(CalendarioScreen(name='calendario'))
        sm.add_widget(EstadisticasScreen(name='estadisticas'))
        sm.add_widget(SeguimientoScreen(name='seguimiento'))
        sm.add_widget(ChatScreen(name='chat'))
        sm.add_widget(ReasignarOvejaScreen(name='reasignar_oveja'))
        sm.add_widget(GestionarUsuariosScreen(name='gestionar_usuarios'))
        sm.add_widget(AsignacionAutomaticaScreen(name='asignacion_automatica'))
        sm.add_widget(DashboardLiderScreen(name='dashboard_lider'))
        sm.add_widget(ImportarOvejasScreen(name='importar_ovejas'))

        # Luego, determina qué pantalla mostrar al inicio
        if self.store.exists('user_session'):
            session_data = self.store.get('user_session')
            self.user_id = session_data['id']
            self.nombre = session_data['nombre']
            self.rol = session_data['rol']
            self.data_cache.sync_all()
            sm.current = 'menu_principal'
        else:
            sm.current = 'login'

        return sm

if __name__ == '__main__':
    RebañoApp().run()
