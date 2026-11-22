"""Caixa d'água IoT: ESP32 + HC-SR04 (MicroPython, dual core).

O sensor fica no TOPO da caixa e mede a distância até a superfície da água.
Tratamento no ESP32:
  1) 3 medições seguidas  2) validação (2 a 400 cm)  3) média das válidas
  4) conversão cm -> % (0 a 100)  5) comparação com o limite de alerta (20 %)
Leitura a cada 2 s, envio MQTT a cada 10 s. Sem fila offline.
No Serial, envie x + Enter para alternar a pausa da rede.
Dependências: config.py, ca_cert.py e mqtt_client.py (todos na raiz).
"""
from machine import Pin, time_pulse_us
import time
import network
import ntptime
import ssl
import json
import os
import binascii
import _thread
import sys
import select
from mqtt_client import MQTTClient
from ca_cert import ca_der
from config import (MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
                    DEVICE_ID, TOPIC, SEND_INTERVAL_MS, SAMPLE_INTERVAL_MS,
                    TANK_FULL_CM, TANK_EMPTY_CM, ALERT_LEVEL_PCT,
                    DIST_MIN_CM, DIST_MAX_CM)

BOOT_ID = binascii.hexlify(os.urandom(8)).decode()
CLIENT_ID = (DEVICE_ID + "-" + BOOT_ID).encode()
lock = _thread.allocate_lock()
estado = {"leitura": None, "pausa": False, "confirmada": False}
contador = 0

# ---------------------------------------------------------------- sensor ----
trig = Pin(5, Pin.OUT, value=0)    # GPIO5  -> TRIG do HC-SR04
echo = Pin(18, Pin.IN)             # GPIO18 <- ECHO do HC-SR04
led = Pin(19, Pin.OUT, value=0)    # GPIO19 -> LED de alerta (via 330 ohm)


def medir_distancia_cm():
    """Uma medição: pulso de 10 us no TRIG; o ECHO dura o tempo de ida e volta."""
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    duracao = time_pulse_us(echo, 1, 30000)   # timeout 30 ms (~5 m)
    if duracao < 0:
        return None                            # sem eco / timeout
    return duracao / 58.0                      # us -> cm (som ~343 m/s, ida e volta)


def medir_media_cm():
    """Média de 3 medições, descartando as inválidas (fora de 2..400 cm)."""
    validas = []
    for _ in range(3):
        d = medir_distancia_cm()
        if d is not None and DIST_MIN_CM <= d <= DIST_MAX_CM:
            validas.append(d)
        time.sleep_ms(60)
    if len(validas) < 2:                       # exige pelo menos 2 de 3 válidas
        return None
    return sum(validas) / len(validas)


def distancia_para_nivel(d_cm):
    """Converte distância (cm) em nível (%), limitado entre 0 e 100."""
    nivel = (TANK_EMPTY_CM - d_cm) / (TANK_EMPTY_CM - TANK_FULL_CM) * 100.0
    return max(0.0, min(100.0, nivel))


# ------------------------------------------------------------------ rede ----
def novo_id():
    global contador
    contador += 1
    return "%s-%s-%d" % (DEVICE_ID, BOOT_ID, contador)


def pausado():
    with lock:
        return estado["pausa"]


def esperar(ms):
    inicio = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), inicio) < ms:
        if pausado():
            return
        time.sleep_ms(100)


def fechar(cliente):
    if cliente is not None:
        try:
            cliente.sock.close()
        except Exception:
            pass


def sincronizar_relogio():
    """O TLS confere a validade do certificado, então a hora precisa estar certa.
    Tenta vários servidores NTP, 2 vezes cada, antes de desistir."""
    ntptime.timeout = 5
    for _ in range(2):
        for servidor in ("pool.ntp.org", "time.google.com",
                         "time.cloudflare.com", "a.ntp.br"):
            if pausado():
                raise OSError("Pausa solicitada")
            try:
                ntptime.host = servidor
                ntptime.settime()
                print("RELOGIO SINCRONIZADO", servidor, time.gmtime()[:6])
                return
            except Exception as erro:
                print("NTP falhou em", servidor, str(erro))
                time.sleep_ms(300)
    raise OSError("Nao foi possivel sincronizar o relogio (NTP)")


def conectar(wifi):
    wifi.active(True)
    if not wifi.isconnected():
        wifi.connect("Wokwi-GUEST", "")
    inicio = time.ticks_ms()
    while not wifi.isconnected():
        if pausado():
            raise OSError("Pausa solicitada")
        if time.ticks_diff(time.ticks_ms(), inicio) > 45000:
            raise OSError("Tempo de Wi-Fi excedido")
        time.sleep_ms(100)
    print("IP", wifi.ifconfig()[0])
    sincronizar_relogio()
    if pausado():
        raise OSError("Pausa solicitada")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(cadata=ca_der())
    print("MQTT_HOST =", repr(MQTT_HOST))
    cliente = MQTTClient(
        client_id=CLIENT_ID, server=MQTT_HOST, port=MQTT_PORT,
        user=MQTT_USER.encode(), password=MQTT_PASSWORD.encode(),
        keepalive=60, ssl=ctx)
    try:
        cliente.connect(timeout=5)
    except Exception:
        fechar(cliente)
        raise
    print("MQTT CONECTADO")
    return cliente


def tarefa_rede():
    wifi = network.WLAN(network.STA_IF)
    cliente = None
    ultimo_envio = None
    while True:
        try:
            if pausado():
                fechar(cliente)
                cliente = None
                if wifi.active():
                    wifi.active(False)
                with lock:
                    primeira = not estado["confirmada"]
                    estado["confirmada"] = True
                if primeira:
                    print("REDE PAUSADA: aquisicao local continua")
                time.sleep_ms(100)
                continue
            with lock:
                estado["confirmada"] = False
            if cliente is None or not wifi.isconnected():
                fechar(cliente)
                cliente = None
                cliente = conectar(wifi)
                ultimo_envio = None
            agora = time.ticks_ms()
            venceu = (ultimo_envio is None or
                      time.ticks_diff(agora, ultimo_envio) >= SEND_INTERVAL_MS)
            if venceu and not pausado():
                # Copiar rapidamente. Nenhuma operação de rede dentro do lock.
                with lock:
                    leitura = (dict(estado["leitura"])
                               if estado["leitura"] else None)
                if leitura is not None and not pausado():
                    payload = json.dumps(leitura).encode()
                    cliente.publish(TOPIC.encode(), payload,
                                    retain=False, qos=0)
                    print("PUBLICADO", leitura["message_id"],
                          "(nao comprova gravacao)")
                    ultimo_envio = time.ticks_ms()
            time.sleep_ms(100)
        except Exception as erro:
            print("FALHA REDE", type(erro).__name__, str(erro))
            fechar(cliente)
            cliente = None
            try:                       # reinicia o Wi-Fi para a próxima tentativa
                wifi.disconnect()
                wifi.active(False)
            except Exception:
                pass
            # Não conservar payload para reenvio. Só a leitura atual permanece.
            esperar(3000)


# ------------------------------------------------------------ programa ------
poll = select.poll()
poll.register(sys.stdin, select.POLLIN)
print("Caixa d'agua | alerta < %.0f %% | TRIG GPIO5 | ECHO GPIO18 | LED GPIO19"
      % ALERT_LEVEL_PCT)
print("Envie x + Enter para alternar pausa/retomada da rede")
_thread.start_new_thread(tarefa_rede, ())
ultimo = time.ticks_ms()
while True:
    if poll.poll(0):
        tecla = sys.stdin.read(1)
        if tecla.lower() == "x":
            with lock:
                estado["pausa"] = not estado["pausa"]
                pedido = estado["pausa"]
            print("PEDIDO", "PAUSA" if pedido else "RETOMADA")
    agora = time.ticks_ms()
    if time.ticks_diff(agora, ultimo) >= SAMPLE_INTERVAL_MS:
        intervalo = time.ticks_diff(agora, ultimo)
        ultimo = agora
        d = medir_media_cm()
        if d is None:
            # Política de falha: apagar LED e invalidar a leitura (nada é enviado).
            led.value(0)
            with lock:
                estado["leitura"] = None
            print("FALHA SENSOR: leituras invalidas (fora de 2-400 cm). "
                  "LED=0 nao indica nivel normal")
        else:
            nivel = distancia_para_nivel(d)
            alerta = nivel < ALERT_LEVEL_PCT
            led.value(1 if alerta else 0)
            leitura = {"device_id": DEVICE_ID, "message_id": novo_id(),
                       "metric": "water_level", "unit": "%",
                       "level_percent": round(nivel, 1),
                       "distance_cm": round(d, 1),
                       "alert": alerta}
            with lock:
                estado["leitura"] = leitura
            print("LOCAL dist", round(d, 1), "cm | nivel", round(nivel, 1),
                  "% | ALERTA" if alerta else "% | ok",
                  "| LED", led.value(), "| intervalo_ms", intervalo)
    time.sleep_ms(50)
