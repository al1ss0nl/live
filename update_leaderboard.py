import os
import requests

# ============================================================
# CONFIGURAÇÕES
# ============================================================

CANAL = "al1ss0nl"
BOTRIX_API_URL = "https://botrix.live/api/public/leaderboard"

JSONBIN_BIN_ID = "6ad0da85ac6210605a33fee6"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# GitHub Actions secret necessário:
# JSONBIN_SECRET_KEY


def get_json(url, params=None):
    """Faz GET e retorna JSON, levantando erro se a resposta falhar."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AL1SS0NL-Leaderboard/1.0)",
        "Accept": "application/json",
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    if not response.ok:
        print(f"Erro HTTP {response.status_code} ao consultar: {response.url}")
        print(f"Resposta do servidor: {response.text[:1000]}")

    response.raise_for_status()
    return response.json()


def extrair_lista(data):
    """Aceita listas diretas ou listas dentro dos envelopes comuns da API."""
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("record", "data", "users", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    raise ValueError(
        "Formato inesperado da API BotRix. Resposta recebida: "
        + str(data)[:1000]
    )


def normalizar_usuario(item):
    """Converte um participante da Kick para o formato do site."""
    if not isinstance(item, dict):
        return None

    nome = (
        item.get("name")
        or item.get("username")
        or item.get("displayName")
        or item.get("display_name")
        or item.get("user")
    )

    pontos = item.get("points")

    if pontos is None:
        pontos = item.get("current")

    if pontos is None:
        pontos = item.get("score")

    if not nome or pontos is None:
        return None

    try:
        pontos = int(float(pontos))
    except (TypeError, ValueError, OverflowError):
        return None

    return {
        "name": str(nome),
        "points": pontos,
        "platform": "kick",
        "avatar": (
            item.get("avatar")
            or item.get("profileImage")
            or ""
        ),
    }


def buscar_kick():
    """Busca somente o leaderboard da Kick no BotRix."""
    data = get_json(
        BOTRIX_API_URL,
        params={
            "user": CANAL,
            "platform": "kick",
            "mode": "points",
        },
    )

    usuarios = extrair_lista(data)
    ranking = []

    for item in usuarios:
        usuario = normalizar_usuario(item)

        if usuario:
            ranking.append(usuario)

    print(f"BotRix/Kick: {len(ranking)} usuários encontrados")

    if not ranking:
        raise RuntimeError(
            "A Kick retornou um ranking vazio. "
            "Publicação cancelada para preservar os dados atuais do site."
        )

    ranking.sort(
        key=lambda usuario: usuario["points"],
        reverse=True
    )

    return ranking


def publicar_jsonbin(top5):
    """Publica o Top 5 no JSONbin."""
    secret = os.environ.get("JSONBIN_SECRET_KEY")

    if not secret:
        raise RuntimeError(
            "Secret JSONBIN_SECRET_KEY não configurado no GitHub."
        )

    response = requests.put(
        JSONBIN_URL,
        headers={
            "Content-Type": "application/json",
            "X-Master-Key": secret,
        },
        json=top5,
        timeout=30,
    )

    if not response.ok:
        print(f"Erro ao atualizar JSONbin: HTTP {response.status_code}")
        print(response.text[:1000])

    response.raise_for_status()
    print("JSONbin atualizado com sucesso.")


def main():
    # Busca somente os participantes da Kick.
    kick = buscar_kick()

    # Monta o Top 5 global da Kick.
    top5 = []

    for posicao, usuario in enumerate(kick[:5], start=1):
        top5.append({
            "rank": posicao,
            "name": usuario["name"],
            "points": usuario["points"],
            "platform": "kick",
            "avatar": usuario.get("avatar", ""),
        })

    print("Top 5 da Kick:")

    for usuario in top5:
        print(
            f'{usuario["rank"]}. {usuario["name"]} '
            f'- {usuario["points"]} pontos (Kick)'
        )

    publicar_jsonbin(top5)


if __name__ == "__main__":
    main()