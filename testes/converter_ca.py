"""Converte um certificado CA em DER/binário para PEM (texto).
Uso: python converter_ca.py emqx-ca.crt   -> imprime o bloco PEM para colar em ca_cert.py
Se o arquivo já for texto PEM, apenas o imprime."""
import sys, base64
dados = open(sys.argv[1], "rb").read()
if b"BEGIN CERTIFICATE" in dados:
    print(dados.decode().strip())
else:
    b64 = base64.encodebytes(dados).decode().replace("\n", "")
    linhas = [b64[i:i + 64] for i in range(0, len(b64), 64)]
    print("-----BEGIN CERTIFICATE-----")
    print("\n".join(linhas))
    print("-----END CERTIFICATE-----")
