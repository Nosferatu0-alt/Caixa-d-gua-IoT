// Somente valores PÚBLICOS. Nunca coloque senha, INGEST_KEY ou sb_secret aqui.
window.LAB_CONFIG = {
  supabaseUrl:" ",
  publicKey: " ",
  deviceId: "g01",
  alertThreshold: 20,     // % (mesmo limite do ESP32)
  staleAfterSeconds: 30,  // envio a cada 10 s -> 3 envios perdidos = desatualizado
  refreshSeconds: 5,      // frequência de consulta à API
  historyLimit: 60        // leituras buscadas para o gráfico/tabela
};
