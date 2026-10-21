
import os
import requests

# ============================================================
# CONFIGURAÇÕES
# ============================================================

CANAL = "al1ss0nl"

BOTRIX_URL = (
    "https://botrix.live/api/public/leaderboard"
    "?user={canal}&platform=kick&mode=points"
)

# StreamElements - canal da Twitch
SE_CHANNEL_ID = "5ed12d4387ba786ed2abc3db"

# JSONbin
JSONBIN_BIN_ID = "6ad0da85ac6210605a33fee6"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# GitHub Actions Secrets:
# JSONBIN_SECRET_KEY
# STREAMELEMENTS_TWITCH_JWT



def get_json(url, headers=None, params=None):
    """Faz GET e retorna JSON, levantando erro se a resposta falhar."""

    cabecalhos = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json"
    }

    # Preserva os cabeçalhos específicos do StreamElements.
    if headers:
        cabecalhos.update(headers)

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


def normalizar_usuario(item, plataforma):
    """
    Converte um registro da API para o formato usado pelo site.
    Tenta reconhecer nomes e campos de pontos comuns.
    """
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
        "platform": plataforma,
        "avatar": item.get("avatar") or item.get("profileImage") or ""
    }


# ============================================================
# KICK: PONTOS PELO BOTRIX
# ============================================================

def buscar_kick():
    url = BOTRIX_URL.format(canal=CANAL)
    data = get_json(url)

    usuarios = extrair_lista(data)
    ranking = []

    for item in usuarios:
        usuario = normalizar_usuario(item, "kick")
        if usuario:
            # BotRix da Kick: manter sem avatar
            usuario["avatar"] = ""
            ranking.append(usuario)

    print(f"Kick/BotRix: {len(ranking)} usuários encontrados")
    return ranking


# ============================================================
# TWITCH: PONTOS PELO STREAMELEMENTS
# ============================================================

def buscar_twitch_pontos():
    jwt = os.environ.get("STREAMELEMENTS_TWITCH_JWT")

    if not jwt:
        raise RuntimeError(
            "Secret STREAMELEMENTS_TWITCH_JWT não configurado no GitHub."
        )

    headers = {
        "Authorization": f"Bearer {jwt}",
        "Accept": "application/json"
    }

    ranking = []
    limite = 100
    offset = 0

    # Pagina para buscar a lista de usuários do leaderboard.
    while True:
        url = (
            f"https://api.streamelements.com/kappa/v2/"
            f"points/{SE_CHANNEL_ID}/top"
        )

        data = get_json(
            url,
            headers=headers,
            params={"limit": limite, "offset": offset}
        )

        usuarios = extrair_lista(data)

        if not usuarios:
            break

        for item in usuarios:
            usuario = normalizar_usuario(item, "twitch")
            if usuario:
                ranking.append(usuario)

        if len(usuarios) < limite:
            break

        offset += limite

    print(f"Twitch/StreamElements: {len(ranking)} usuários encontrados")
    return ranking, headers


def buscar_avatares_twitch(headers):
    """
    Tenta obter avatares dos registros de atividade recentes.
    Atenção: atividades não são o leaderboard de pontos e podem
    não incluir todos os participantes.
    """
    url = (
        "https://api.streamelements.com/kappa/v2/"
        f"activities/{SE_CHANNEL_ID}"
    )

    try:
        data = get_json(url, headers=headers)
        atividades = extrair_lista(data)
    except Exception as erro:
        print(f"Não foi possível buscar avatares das atividades: {erro}")
        return {}

    avatares = {}

    for atividade in atividades:
        dados = atividade.get("data") or {}

        nome = (
            dados.get("username")
            or dados.get("displayName")
            or atividade.get("username")
            or atividade.get("name")
        )

        avatar = (
            dados.get("avatar")
            or dados.get("profileImage")
            or atividade.get("avatar")
        )

        if nome and avatar:
            avatares[str(nome).lower()] = avatar

    print(f"Avatares Twitch encontrados nas atividades: {len(avatares)}")
    return avatares


# ============================================================
# JUNTA, ORDENA E PUBLICA NO JSONBIN
# ============================================================

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
    kick = buscar_kick()

    twitch, se_headers = buscar_twitch_pontos()
    avatares = buscar_avatares_twitch(se_headers)

    # Aplica avatares da Twitch quando foi possível encontrá-los.
    for usuario in twitch:
        avatar = avatares.get(usuario["name"].lower())
        if avatar:
            usuario["avatar"] = avatar

    # Junta as plataformas em um ranking só.
    todos = kick + twitch

    # Se um usuário estiver duplicado, mantém o registro com mais pontos
    # (a deduplicação usa nome + plataforma).
    unicos = {}
    for usuario in todos:
        chave = (
            usuario["name"].strip().lower(),
            usuario["platform"]
        )

        atual = unicos.get(chave)
        if atual is None or usuario["points"] > atual["points"]:
            unicos[chave] = usuario

    todos = list(unicos.values())

    # Maior pontuação primeiro.
    todos.sort(key=lambda usuario: usuario["points"], reverse=True)

    top5 = []
    for posicao, usuario in enumerate(todos[:5], start=1):
        top5.append({
            "rank": posicao,
            "name": usuario["name"],
            "points": usuario["points"],
            "platform": usuario["platform"],
            "avatar": usuario.get("avatar", "")
        })

    print("Top 5 combinado:")
    for usuario in top5:
        print(
            f'{usuario["rank"]}. {usuario["name"]} '
            f'- {usuario["points"]} pontos '
            f'({usuario["platform"]})'
        )

    publicar_jsonbin(top5)


if __name__ == "__main__":
    main()
    
