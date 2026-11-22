# Caixa d'água IoT — monitoramento de nível

Sistema de monitoramento IoT simulado: um sensor ultrassônico **HC-SR04** fica no topo de uma caixa d'água, mede a distância até a superfície da água e o **ESP32** converte isso em **nível (%)**. Abaixo de **20 %** o sistema entra em **alerta** (LED no ESP32 e aviso no painel).

> Projeto da disciplina de Arquitetura de Computadores — Atividade IoT. Dados 100 % simulados.

## Arquitetura (Opção A — com MQTT)

```
Wokwi (ESP32 + HC-SR04 + LED)
   │  MQTT sobre TLS (porta 8883), tópico turma/g01/telemetria
   ▼
EMQX Serverless (broker) ── regra telemetria_g01 ── ação HTTP POST
   │  HTTPS + header x-ingest-key
   ▼
Supabase Edge Function "ingest" (API REST: valida e grava)
   ▼
Supabase Postgres  (tabela public.readings)
   ▲  GET /rest/v1/readings (HTTPS, chave publishable)
   │
Painel web no Cloudflare Pages (valor atual, histórico, alerta, dados desatualizados)
```

## Tratamento no ESP32 (`wokwi/main.py`)
1. 3 medições seguidas do HC-SR04 (pulso de 10 µs no TRIG; duração do ECHO ÷ 58 = cm).
2. Validação: só valem distâncias entre **2 e 400 cm** (precisam ser ≥ 2 de 3 válidas; senão "FALHA SENSOR" e nada é enviado).
3. Média das medições válidas.
4. Conversão: `nível% = (100 − d) / (100 − 5) × 100`, limitado a 0–100 (`TANK_EMPTY_CM=100`, `TANK_FULL_CM=5`).
5. Comparação: `alert = nível < 20`. O LED (GPIO19) acende em alerta.

Leitura a cada **2 s**; envio MQTT a cada **10 s**. Alerta começa em ≈ 81,5 cm de distância.

## Contrato JSON (MQTT → API)
```json
{"device_id":"g01","message_id":"g01-<boot>-<n>","metric":"water_level","unit":"%",
 "level_percent":54.9,"distance_cm":47.8,"alert":false}
```

## Banco de dados
Tabela `public.readings` (ver `supabase/schema.sql`): chave primária `(device_id, message_id)` (evita duplicatas), RLS habilitado, leitura pública (`anon`) e escrita só pela função `ingest`.

## Estrutura do repositório
| Pasta | Conteúdo |
|---|---|
| `wokwi/` | Firmware MicroPython, circuito (`diagram.json`), configuração |
| `emqx/` | Regra SQL, corpo da ação HTTP e configuração (sem segredos) |
| `supabase/` | `schema.sql`, `conferir.sql`, função `functions/ingest/index.ts` |
| `site/` | Painel (`index.html` + `config.js` público) publicado no Cloudflare Pages |
| `testes/` | JSONs de teste e roteiro de testes da API |
| `registros/` | Mapa do ambiente e evidências dos testes |

## Segredos (nada disso está no repositório)
- `INGEST_KEY` → Supabase (Edge Functions > Secrets) e header da ação no EMQX.
- Senha MQTT → EMQX e `wokwi/config.py` **apenas no projeto Wokwi** (aqui fica placeholder).
- Senha do banco → só no Supabase.
- O `site/config.js` contém apenas a URL e a chave **publishable** (pública por design).

## Como reproduzir
1. **Supabase:** criar projeto; rodar `supabase/schema.sql` no SQL Editor; criar o secret `INGEST_KEY`; criar a função `ingest` com `supabase/functions/ingest/index.ts` e **desligar Verify JWT**; testar com `testes/corpo_api.json`.
2. **EMQX Serverless:** criar deployment; usuário `esp32_g01`; autorização (Publish/Allow no tópico do grupo + Deny geral); conector HTTP para a URL do Supabase; regra `emqx/regra.sql`; ação POST `/functions/v1/ingest` com body `${.}` e header `x-ingest-key`.
3. **Wokwi:** novo projeto ESP32 MicroPython; copiar `wokwi/*`; preencher `config.py` e colar a CA do EMQX em `ca_cert.py`; executar.
4. **Cloudflare Pages:** preencher `site/config.js`; subir a pasta `site/` (Direct Upload ou conectar este repositório com *build output* = `site`).

## Testes realizados
Ver `registros/evidencias.csv`: alerta em < 20 %, duplicata (200/inserted false), pausa/retomada da transmissão (tecla `x` no Serial), painel mostra "dados desatualizados" e volta ao normal, gravação com o painel fechado.

## Limitações
- Sem fila offline: leituras durante a pausa de rede são perdidas (limitação didática).
- Estado "desatualizado" depende do relógio do navegador (diferença de fuso/relógio pode afetar).
- Credencial MQTT fica visível em quem abrir o projeto Wokwi (usuário só publica no próprio tópico).
- Leitura pública da tabela (dados sintéticos).

## Links
- Painel: _preencher_
- Wokwi: _preencher_
- Vídeo (YouTube, não listado): _preencher_

## Integrantes e contribuições
| Integrante | Contribuição |
|---|---|
| _Nome 1_ | _ex.: firmware/Wokwi_ |
| _Nome 2_ | _ex.: Supabase e função ingest_ |
| _Nome 3_ | _ex.: EMQX e painel_ |
