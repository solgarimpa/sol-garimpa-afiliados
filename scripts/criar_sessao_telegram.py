#!/usr/bin/env python3
"""Cria a sessao MTProto SOMENTE no seu computador.

O arquivo com a sessao permite acessar a conta Telegram: nao envie a ninguem,
nao suba ao GitHub e nao divulgue em capturas de tela.
"""
import getpass
import os
from pathlib import Path

from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def main():
    print("SOL GARIMPA - autorizacao local (nada e enviado ao GitHub)")
    api_id = int(input("API ID (my.telegram.org): ").strip())
    api_hash = getpass.getpass("API Hash (nao aparece ao digitar): ").strip()
    telefone = input("Telefone da conta Telegram, com DDI: ").strip()

    destino = Path.home() / "solgarimpa_sessao_telegram_PRIVADA.txt"
    if destino.exists():
        raise RuntimeError("Arquivo da sessao ja existe; confira antes de substituir.")
    cliente = TelegramClient(StringSession(), api_id, api_hash)
    try:
        cliente.start(
            phone=telefone,
            code_callback=lambda: input("Codigo recebido no Telegram: ").strip(),
            password=lambda: getpass.getpass("Senha 2FA, se solicitada: "),
        )
        sessao = cliente.session.save()
    finally:
        cliente.disconnect()
    with destino.open("x", encoding="utf-8") as arquivo:
        arquivo.write(sessao)
    try:
        os.chmod(destino, 0o600)
    except OSError:
        pass
    print("Sessao criada. Arquivo LOCAL:", destino)
    print("Nao publique, envie ou compartilhe o conteudo.")
    print("A proxima etapa sera adicionar a sessao como variavel secreta no servidor.")


if __name__ == "__main__":
    main()
