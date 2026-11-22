# Edite somente os valores indicados. Credenciais exclusivas do laboratório.
# NÃO publique a senha real no GitHub (no repositório fica o placeholder).
MQTT_HOST = "COLE_O_DOMINIO_EMQX_SEM_PROTOCOLO"
MQTT_PORT = 8883
MQTT_USER = "esp32_g01"
MQTT_PASSWORD = "COLE_A_SENHA_MQTT"
DEVICE_ID = "g01"
TOPIC = "turma/g01/telemetria"
SEND_INTERVAL_MS = 10000      # envio a cada 10 s
SAMPLE_INTERVAL_MS = 2000     # leitura (3 medições + média) a cada 2 s

# --- Calibração da caixa d'água (distância medida do sensor, no topo) ---
TANK_FULL_CM = 5.0            # distância sensor -> água quando está 100% cheia
TANK_EMPTY_CM = 100.0         # distância sensor -> fundo quando está 0% (vazia)
ALERT_LEVEL_PCT = 20.0        # abaixo disso entra em alerta
DIST_MIN_CM = 2.0             # faixa válida do HC-SR04
DIST_MAX_CM = 400.0
