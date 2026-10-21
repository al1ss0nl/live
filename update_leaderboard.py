import os
import requests

# ============================================================
# CONFIGURAÇÕES
# ============================================================

CANAL = "al1ss0nl"

# Endpoint público do BotRix para o leaderboard de pontos
BOTRIX_URL = (
    "https://botrix.live/api/public/leaderboard"
    f"?user={CANAL}&platform=kick&mode=points"
)

# JSONbin
JSONBIN_BIN_ID = "6ad0da85ac6210605a33fee6"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# GitHub Actions Secrets necessários:
# JSONBIN_SECRET_KEY


def get_json(url, params=None):
    """Faz GET e retorna JSON, levantando erro se a resposta falhar."""
    cabecalhos = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json"
    }

    response = requests.get(
        url,
        headers=cabecalhos,
        params=params,
        timeout=30
    )

    if not response.ok:
        print(f"Erro HTTP {response.status_code} ao consultar: {url}")
        print(f"Resposta do servidor: {response.text[:1000]}")

    response.raise_for_status()
    return response.json()


def extrair_lista(data):
    """Aceita respostas que vêm diretamente como lista ou dentro de record/data."""
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for chave in ("record", "data", "users", "results"):
            valor = data.get(chave)
            if isinstance(valor, list):
                return valor

    raise ValueError(
        "Formato inesperado da API. Resposta recebida: "
        + str(data)[:1000]
    )


def normalizar_usuario(item):
    """Converte um registro da API do BotRix para o formato do site."""
    nome = (
        item.get("name")
        or item.get("username")
        or item.get("displayName")
        or item.get("display_name")
        or item.get("user")
    )

    pontos = (
        item.get("points")
        if item.get("points") is not None
        else item.get("current")
    )

    if pontos is None:
        pontos = item.get("score")

    if not nome or pontos is None:
        return None

    try:
        pontos = int(float(pontos))
    except (TypeError, ValueError):
        return None

    return {
        "name": str(nome),
        "points": pontos,
        "platform": "kick",
        "avatar": item.get("avatar") or item.get("profileImage") or ""
    }


def buscar_botrix():
    data = get_json(BOTRIX_URL)
    usuarios = extrair_lista(data)
    ranking = []

    for item in usuarios:
        usuario = normalizar_usuario(item)
        if usuario:
            ranking.append(usuario)

    print(f"BotRix: {len(ranking)} usuários encontrados")
    return ranking


def publicar_jsonbin(top5):
    secret = os.environ.get("JSONBIN_SECRET_KEY")

    if not secret:
        raise RuntimeError(
            "Secret JSONBIN_SECRET_KEY não configurado no GitHub."
        )

    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": secret
    }

    response = requests.put(
        JSONBIN_URL,
        headers=headers,
        json=top5,
        timeout=30
    )

    response.raise_for_status()
    print("JSONbin atualizado com sucesso.")


def main():
    ranking = buscar_botrix()

    # Maior pontuação primeiro
    ranking.sort(key=lambda usuario: usuario["points"], reverse=True)

    top5 = []
    for posicao, usuario in enumerate(ranking[:5], start=1):
        top5.append({
            "rank": posicao,
            "name": usuario["name"],
            "points": usuario["points"],
            "platform": usuario["platform"],
            "avatar": usuario.get("avatar", "")
        })

    print("Top 5 do BotRix:")
    for usuario in top5:
        print(
            f'{usuario["rank"]}. {usuario["name']} '
            f'- {usuario["points"]} pontos'
        )

    publicar_jsonbin(top5)


if __name__ == "__main__":
    main()
