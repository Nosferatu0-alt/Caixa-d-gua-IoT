SELECT topic, json_decode(payload) AS reading
FROM "turma/g01/telemetria"
