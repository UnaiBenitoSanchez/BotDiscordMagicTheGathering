import discord
from discord.ext import commands
from discord.ui import Button, View
import aiohttp
import random
import json
import os
from datetime import datetime

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# URL base de la API de Scryfall
SCRYFALL_API = "https://api.scryfall.com/cards/named"
SCRYFALL_SEARCH = "https://api.scryfall.com/cards/search"
SCRYFALL_RANDOM = "https://api.scryfall.com/cards/random"
SCRYFALL_SETS = "https://api.scryfall.com/sets"

# Archivos de persistencia
FAVORITOS_FILE = "./favoritos.json"
MAZOS_FILE = "./mazos.json"

# Diccionario para traducir tipos de carta
TRADUCCION_TIPOS = {
    "Creature": "Criatura",
    "Instant": "Instantáneo",
    "Sorcery": "Conjuro",
    "Enchantment": "Encantamiento",
    "Artifact": "Artefacto",
    "Planeswalker": "Planeswalker",
    "Land": "Tierra",
    "Legendary": "Legendario",
    "Tribal": "Tribal",
    "Basic": "Básico",
    "Snow": "Nieve",
    "Token": "Ficha",
    "Battle": "Batalla",
    "Human": "Humano",
    "Elf": "Elfo",
    "Goblin": "Trasgo",
    "Wizard": "Hechicero",
    "Warrior": "Guerrero",
    "Angel": "Ángel",
    "Demon": "Demonio",
    "Dragon": "Dragón",
    "Beast": "Bestia",
    "Soldier": "Soldado",
    "Knight": "Caballero",
    "Zombie": "Zombi",
    "Vampire": "Vampiro",
    "Spirit": "Espíritu",
    "Equipment": "Equipo",
    "Aura": "Aura",
    "Vehicle": "Vehículo",
}

# Almacenamiento de favoritos y mazos
favoritos_usuarios = {}
mazos_usuarios = {}  # user_id : { 'nombre_mazo': [lista de cartas] }


def cargar_favoritos():
    """Carga los favoritos desde el archivo JSON"""
    global favoritos_usuarios
    try:
        if os.path.exists(FAVORITOS_FILE):
            with open(FAVORITOS_FILE, "r", encoding="utf-8") as f:
                favoritos_usuarios = json.load(f)
            print(f"✅ Favoritos cargados: {len(favoritos_usuarios)} usuarios")
        else:
            favoritos_usuarios = {}
            print("📝 Archivo de favoritos no existe, creando uno nuevo")
    except Exception as e:
        print(f"❌ Error al cargar favoritos: {e}")
        favoritos_usuarios = {}


def guardar_favoritos():
    """Guarda los favoritos en el archivo JSON"""
    try:
        with open(FAVORITOS_FILE, "w", encoding="utf-8") as f:
            json.dump(favoritos_usuarios, f, ensure_ascii=False, indent=2)
        print("💾 Favoritos guardados correctamente")
    except Exception as e:
        print(f"❌ Error al guardar favoritos: {e}")


def cargar_mazos():
    """Carga los mazos desde el archivo JSON"""
    global mazos_usuarios
    try:
        if os.path.exists(MAZOS_FILE):
            with open(MAZOS_FILE, "r", encoding="utf-8") as f:
                mazos_usuarios = json.load(f)
            print(f"✅ Mazos cargados: {len(mazos_usuarios)} usuarios")
        else:
            mazos_usuarios = {}
            print("📝 Archivo de mazos no existe, creando uno nuevo")
    except Exception as e:
        print(f"❌ Error al cargar mazos: {e}")
        mazos_usuarios = {}


def guardar_mazos():
    """Guarda los mazos en el archivo JSON"""
    try:
        with open(MAZOS_FILE, "w", encoding="utf-8") as f:
            json.dump(mazos_usuarios, f, ensure_ascii=False, indent=2)
        print("💾 Mazos guardados correctamente")
    except Exception as e:
        print(f"❌ Error al guardar mazos: {e}")


def traducir_tipo(tipo_en_ingles):
    """Traduce el tipo de carta al español"""
    for ing, esp in TRADUCCION_TIPOS.items():
        tipo_en_ingles = tipo_en_ingles.replace(ing, esp)
    return tipo_en_ingles


def traducir_legalidad(legality):
    """Traduce el estado de legalidad"""
    traducciones = {
        "legal": "✅ Legal",
        "not_legal": "❌ No legal",
        "banned": "🚫 Baneada",
        "restricted": "⚠️ Restringida",
    }
    return traducciones.get(legality, legality)


async def buscar_carta_espanol(session, nombre_carta):
    """Busca la versión en español de una carta"""
    try:
        params_en = {"fuzzy": nombre_carta}
        async with session.get(SCRYFALL_API, params=params_en) as response:
            if response.status != 200:
                return None
            data_en = await response.json()

        card_name = data_en.get("name", "")
        query = f'!"{card_name}" lang:es'
        params_es = {"q": query, "unique": "prints"}

        async with session.get(SCRYFALL_SEARCH, params=params_es) as response:
            if response.status != 200:
                return data_en

            data_search = await response.json()
            if data_search.get("total_cards", 0) > 0:
                carta_es = data_search["data"][0]
                if "image_uris" in data_en and "image_uris" not in carta_es:
                    carta_es["image_uris"] = data_en["image_uris"]
                return carta_es
            else:
                return data_en
    except Exception as e:
        print(f"Error buscando versión en español: {e}")
        return None


def crear_embed_carta(data, mostrar_legalidad=False):
    """Crea un embed con la información de una carta"""
    idioma = data.get("lang", "en")
    es_espanol = idioma == "es"

    nombre_mostrar = data.get("printed_name", data.get("name", "Sin nombre"))
    embed = discord.Embed(
        title=nombre_mostrar,
        url=data.get("scryfall_uri", ""),
        color=discord.Color.blue(),
    )

    if not es_espanol and "name" in data:
        embed.add_field(name="🌐 Nombre original", value=data["name"], inline=False)

    if "image_uris" in data:
        embed.set_image(url=data["image_uris"]["normal"])
    elif "card_faces" in data and len(data["card_faces"]) > 0:
        if "image_uris" in data["card_faces"][0]:
            embed.set_image(url=data["card_faces"][0]["image_uris"]["normal"])

    if "printed_type_line" in data:
        embed.add_field(name="Tipo", value=data["printed_type_line"], inline=False)
    elif "type_line" in data:
        tipo_traducido = traducir_tipo(data["type_line"])
        embed.add_field(name="Tipo", value=tipo_traducido, inline=False)

    if "mana_cost" in data:
        embed.add_field(name="Coste de Maná", value=data["mana_cost"], inline=True)

    if "cmc" in data:
        embed.add_field(name="CMC", value=str(int(data["cmc"])), inline=True)

    if "printed_text" in data and data["printed_text"].strip():
        texto = data["printed_text"]
        if len(texto) > 1024:
            texto = texto[:1021] + "..."
        embed.add_field(name="Habilidades", value=texto, inline=False)
    elif "oracle_text" in data:
        texto = data["oracle_text"]
        if len(texto) > 1024:
            texto = texto[:1021] + "..."
        icono = "🇬🇧" if not es_espanol else ""
        embed.add_field(name=f"{icono} Habilidades", value=texto, inline=False)
        if not es_espanol:
            embed.add_field(
                name="ℹ️ Nota",
                value="Esta carta no tiene traducción oficial al español",
                inline=False,
            )
    elif "card_faces" in data:
        for i, face in enumerate(data["card_faces"][:2], 1):
            texto = None
            if "printed_text" in face and face["printed_text"].strip():
                texto = face["printed_text"]
            elif "oracle_text" in face:
                texto = face["oracle_text"]

            if texto:
                if len(texto) > 1024:
                    texto = texto[:1021] + "..."
                nombre_cara = face.get("printed_name", face.get("name", f"Cara {i}"))
                embed.add_field(
                    name=f"Habilidades - {nombre_cara}", value=texto, inline=False
                )

    if "power" in data and "toughness" in data:
        embed.add_field(
            name="Poder/Resistencia",
            value=f"{data['power']}/{data['toughness']}",
            inline=True,
        )

    if "loyalty" in data:
        embed.add_field(name="Lealtad", value=data["loyalty"], inline=True)

    if "rarity" in data:
        rareza_emoji = {"common": "⚪", "uncommon": "🔷", "rare": "🟡", "mythic": "🔴"}
        rareza_es = {
            "common": "Común",
            "uncommon": "Poco común",
            "rare": "Rara",
            "mythic": "Mítica",
        }
        rareza = rareza_es.get(data["rarity"], data["rarity"].capitalize())
        emoji = rareza_emoji.get(data["rarity"], "")
        embed.add_field(name="Rareza", value=f"{emoji} {rareza}", inline=True)

    if "set_name" in data:
        embed.add_field(name="Expansión", value=data["set_name"], inline=True)

    if mostrar_legalidad and "legalities" in data:
        formatos_principales = [
            "standard",
            "pioneer",
            "modern",
            "legacy",
            "vintage",
            "commander",
        ]
        legalidades = []
        for formato in formatos_principales:
            if formato in data["legalities"]:
                status = traducir_legalidad(data["legalities"][formato])
                legalidades.append(f"{formato.capitalize()}: {status}")

        if legalidades:
            embed.add_field(
                name="⚖️ Legalidad", value="\n".join(legalidades), inline=False
            )

    footer_text = ""
    if "artist" in data:
        footer_text = f"Ilustrado por: {data['artist']}"
    if es_espanol:
        footer_text += " 🇪🇸"

    if footer_text:
        embed.set_footer(text=footer_text)

    return embed


def agregar_precios_embed(embed, prices, purchase_uris=None):
    """Añade información de precios a un embed"""
    mostrado = False

    def add_price(label, value, symbol):
        nonlocal mostrado
        if value and value not in ["", "0.00", "0"]:
            embed.add_field(name=label, value=f"{symbol}{value}", inline=True)
            mostrado = True

    add_price("💵 USD (Normal)", prices.get("usd"), "$")
    add_price("✨ USD (Foil)", prices.get("usd_foil"), "$")
    add_price("💶 EUR", prices.get("eur"), "€")
    add_price("🎫 MTGO", prices.get("tix"), "")

    if not mostrado:
        embed.description = "⚠️ No hay precios disponibles actualmente."

    if purchase_uris:
        links = []
        if purchase_uris.get("tcgplayer"):
            links.append(f"[TCGPlayer]({purchase_uris['tcgplayer']})")
        if purchase_uris.get("cardmarket"):
            links.append(f"[Cardmarket]({purchase_uris['cardmarket']})")
        if purchase_uris.get("cardhoarder"):
            links.append(f"[Cardhoarder]({purchase_uris['cardhoarder']})")
        if links:
            embed.add_field(name="🔗 Comprar", value=" | ".join(links), inline=False)

    return embed


class CardView(View):
    """Vista con botones para interactuar con las cartas"""

    def __init__(self, data, user_id):
        super().__init__(timeout=180)
        self.data = data
        self.user_id = user_id
        self.card_name = data.get("name", "")

    @discord.ui.button(
        label="Ver Rulings", style=discord.ButtonStyle.primary, emoji="📖"
    )
    async def rulings_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "¡Este botón no es para ti!", ephemeral=True
            )
            return

        await interaction.response.defer()

        async with aiohttp.ClientSession() as session:
            rulings_url = self.data.get("rulings_uri", "")
            if rulings_url:
                async with session.get(rulings_url) as response:
                    if response.status == 200:
                        rulings_data = await response.json()
                        rulings = rulings_data.get("data", [])

                        if rulings:
                            embed = discord.Embed(
                                title=f"📖 Rulings - {self.card_name}",
                                color=discord.Color.green(),
                            )

                            for i, ruling in enumerate(rulings[:5], 1):
                                fecha = ruling.get("published_at", "N/A")
                                texto = ruling.get("comment", "Sin información")
                                if len(texto) > 200:
                                    texto = texto[:197] + "..."
                                embed.add_field(
                                    name=f"{i}. {fecha}", value=texto, inline=False
                                )

                            if len(rulings) > 5:
                                embed.set_footer(
                                    text=f"Mostrando 5 de {len(rulings)} rulings. Ver más en Scryfall."
                                )

                            await interaction.followup.send(embed=embed, ephemeral=True)
                        else:
                            await interaction.followup.send(
                                "No hay rulings disponibles para esta carta.",
                                ephemeral=True,
                            )
            else:
                await interaction.followup.send(
                    "No se encontró información de rulings.", ephemeral=True
                )

    @discord.ui.button(
        label="Añadir a Favoritos", style=discord.ButtonStyle.success, emoji="⭐"
    )
    async def favorite_button(self, interaction: discord.Interaction, button: Button):
        user_id = str(interaction.user.id)

        if user_id not in favoritos_usuarios:
            favoritos_usuarios[user_id] = []

        if self.card_name not in favoritos_usuarios[user_id]:
            favoritos_usuarios[user_id].append(self.card_name)
            guardar_favoritos()  # Guardar cambios
            await interaction.response.send_message(
                f"⭐ ¡{self.card_name} añadida a favoritos!", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Esta carta ya está en tus favoritos.", ephemeral=True
            )

    @discord.ui.button(
        label="Ver Precios", style=discord.ButtonStyle.secondary, emoji="💰"
    )
    async def price_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "¡Este botón no es para ti!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"💰 Precios - {self.card_name}", color=discord.Color.gold()
        )
        embed = agregar_precios_embed(
            embed, self.data.get("prices", {}), self.data.get("purchase_uris")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
    # Cargar datos guardados al iniciar
    cargar_favoritos()
    cargar_mazos()

    # Iniciar auto-guardado
    if not auto_guardar.is_running():
        auto_guardar.start()

    print(f"{bot.user} está conectado y listo!")
    print(f"📊 Usuarios con favoritos: {len(favoritos_usuarios)}")
    print(f"📊 Usuarios con mazos: {len(mazos_usuarios)}")
    print("------")


# Guardar automáticamente cada 5 minutos (opcional pero recomendado)
from discord.ext import tasks


@tasks.loop(minutes=5)
async def auto_guardar():
    """Guarda automáticamente los datos cada 5 minutos"""
    guardar_favoritos()
    guardar_mazos()
    print(f"💾 Auto-guardado completado - {datetime.now().strftime('%H:%M:%S')}")


@auto_guardar.before_loop
async def before_auto_guardar():
    await bot.wait_until_ready()


@bot.command(
    name="favoritos",
    aliases=["misfavoritas"],
    help="Muestra tus cartas favoritas con navegación",
)
async def ver_favoritos(ctx):
    """Muestra las cartas favoritas del usuario con navegación"""
    user_id = str(ctx.author.id)

    if user_id not in favoritos_usuarios or not favoritos_usuarios[user_id]:
        await ctx.send(
            '⭐ No tienes cartas favoritas aún. Usa el botón "Añadir a Favoritos" en cualquier carta.'
        )
        return

    favoritos = favoritos_usuarios[user_id]

    # Buscar datos completos de las cartas
    cartas_data = []
    async with aiohttp.ClientSession() as session:
        for nombre_carta in favoritos:
            try:
                params = {"fuzzy": nombre_carta}
                async with session.get(SCRYFALL_API, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        cartas_data.append(data)
            except Exception as e:
                print(f"Error buscando {nombre_carta}: {e}")

    if not cartas_data:
        await ctx.send("❌ Error al cargar favoritos")
        return

    # Mostrar primera carta
    index = 0
    embed = crear_embed_carta(cartas_data[index])
    embed.title = f"⭐ Favoritos ({index + 1}/{len(cartas_data)}): {embed.title}"

    mensaje = await ctx.send(embed=embed)

    # Añadir reacciones
    await mensaje.add_reaction("⬅️")
    await mensaje.add_reaction("➡️")
    await mensaje.add_reaction("🗑️")

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == mensaje.id
            and str(reaction.emoji) in ["⬅️", "➡️", "🗑️"]
        )

    # Loop de navegación
    while True:
        try:
            reaction, user = await bot.wait_for(
                "reaction_add", timeout=120.0, check=check
            )

            # Remover la reacción del usuario
            try:
                await mensaje.remove_reaction(reaction.emoji, user)
            except:
                pass

            # Navegación derecha
            if str(reaction.emoji) == "➡️":
                index = (index + 1) % len(cartas_data)

            # Navegación izquierda
            elif str(reaction.emoji) == "⬅️":
                index = (index - 1) % len(cartas_data)

            # Eliminar carta
            elif str(reaction.emoji) == "🗑️":
                carta_eliminada = cartas_data[index]["name"]
                favoritos_usuarios[user_id].remove(carta_eliminada)
                guardar_favoritos()  # Guardar cambios
                cartas_data.pop(index)

                if not cartas_data:
                    await mensaje.edit(
                        content="✅ Ya no tienes cartas favoritas", embed=None
                    )
                    await mensaje.clear_reactions()
                    return

                # Ajustar índice si es necesario
                if index >= len(cartas_data):
                    index = 0

                await ctx.send(
                    f"🗑️ **{carta_eliminada}** eliminada de favoritos", delete_after=3
                )

            # Actualizar embed
            embed = crear_embed_carta(cartas_data[index])
            embed.title = (
                f"⭐ Favoritos ({index + 1}/{len(cartas_data)}): {embed.title}"
            )
            await mensaje.edit(embed=embed)

        except Exception as e:
            # Timeout o error - limpiar reacciones y salir
            try:
                await mensaje.clear_reactions()
            except:
                pass
            break


# NOTA: Aquí irían todos los demás comandos (!carta, !legal, !random, etc.)
# Por brevidad, solo incluyo los más relevantes modificados


# NOTA: Aquí irían todos los demás comandos (!carta, !legal, !random, etc.)
# Por brevidad, solo incluyo los más relevantes modificados
@bot.command(name="carta", help="Busca una carta de Magic. Uso: !carta <nombre>")
async def buscar_carta(ctx, *, nombre_carta: str):
    """Busca una carta de Magic: The Gathering y muestra su información"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                data = await buscar_carta_espanol(session, nombre_carta)

                if not data:
                    await ctx.send(
                        f'❌ No se encontró ninguna carta con el nombre "{nombre_carta}"'
                    )
                    return

            embed = crear_embed_carta(data)
            view = CardView(data, ctx.author.id)

            await ctx.send(embed=embed, view=view)

        except aiohttp.ClientError as e:
            await ctx.send(f"❌ Error de conexión: {str(e)}")
        except Exception as e:
            await ctx.send(f"❌ Error inesperado: {str(e)}")
            print(f"Error detallado: {e}")


@bot.command(
    name="legal", help="Muestra la legalidad de una carta en diferentes formatos"
)
async def legalidad(ctx, *, nombre_carta: str):
    """Muestra en qué formatos es legal una carta"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                params = {"fuzzy": nombre_carta}
                async with session.get(SCRYFALL_API, params=params) as response:
                    if response.status != 200:
                        await ctx.send(
                            f'❌ No se encontró ninguna carta con el nombre "{nombre_carta}"'
                        )
                        return

                    data = await response.json()

            embed = discord.Embed(
                title=f"⚖️ Legalidad - {data['name']}", color=discord.Color.purple()
            )

            if "image_uris" in data:
                embed.set_thumbnail(url=data["image_uris"]["small"])

            legalities = data.get("legalities", {})
            formatos = {
                "Standard": "standard",
                "Pioneer": "pioneer",
                "Modern": "modern",
                "Legacy": "legacy",
                "Vintage": "vintage",
                "Commander": "commander",
                "Pauper": "pauper",
                "Historic": "historic",
            }

            for formato_nombre, formato_key in formatos.items():
                if formato_key in legalities:
                    status = traducir_legalidad(legalities[formato_key])
                    embed.add_field(name=formato_nombre, value=status, inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="random",
    aliases=["aleatoria", "carta_aleatoria"],
    help="Muestra una carta aleatoria",
)
async def carta_aleatoria(ctx):
    """Muestra una carta completamente aleatoria"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SCRYFALL_RANDOM) as response:
                    if response.status != 200:
                        await ctx.send("❌ Error al obtener carta aleatoria")
                        return

                    data = await response.json()

            embed = crear_embed_carta(data)
            embed.title = f"🎲 Carta Aleatoria: {embed.title}"
            view = CardView(data, ctx.author.id)

            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="buscar", help="Búsqueda avanzada. Ej: !buscar color:red type:creature cmc<=3"
)
async def buscar_avanzado(ctx, *, query: str):
    """Búsqueda avanzada de cartas usando sintaxis de Scryfall"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                params = {"q": query, "order": "name"}
                async with session.get(SCRYFALL_SEARCH, params=params) as response:
                    if response.status != 200:
                        await ctx.send(
                            f'❌ No se encontraron resultados para: "{query}"'
                        )
                        return

                    data = await response.json()

            total = data.get("total_cards", 0)
            cards = data.get("data", [])

            if total == 0:
                await ctx.send(f"❌ No se encontraron cartas con esos criterios")
                return

            embed = discord.Embed(
                title=f"🔍 Resultados de búsqueda",
                description=f"Se encontraron {total} cartas. Mostrando las primeras 10:",
                color=discord.Color.blue(),
            )

            for i, card in enumerate(cards[:10], 1):
                nombre = card.get("name", "Sin nombre")
                tipo = card.get("type_line", "N/A")
                mana = card.get("mana_cost", "")
                embed.add_field(name=f"{i}. {nombre} {mana}", value=tipo, inline=False)

            if total > 10:
                embed.set_footer(
                    text=f"Usa !carta <nombre> para ver detalles de una carta específica"
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name="precio", aliases=["price"], help="Muestra el precio de una carta")
async def ver_precio(ctx, *, nombre_carta: str):
    """Muestra los precios de una carta"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                params = {"fuzzy": nombre_carta}
                async with session.get(SCRYFALL_API, params=params) as response:
                    if response.status != 200:
                        await ctx.send(f'❌ No se encontró la carta "{nombre_carta}"')
                        return

                    data = await response.json()

            prices = data.get("prices", {})

            embed = discord.Embed(
                title=f"💰 Precios - {data['name']}", color=discord.Color.gold()
            )

            if "image_uris" in data:
                embed.set_thumbnail(url=data["image_uris"]["small"])

            if prices.get("usd"):
                embed.add_field(
                    name="💵 USD (Normal)", value=f"${prices['usd']}", inline=True
                )
            if prices.get("usd_foil"):
                embed.add_field(
                    name="✨ USD (Foil)", value=f"${prices['usd_foil']}", inline=True
                )
            if prices.get("eur"):
                embed.add_field(name="💶 EUR", value=f"€{prices['eur']}", inline=True)
            if prices.get("tix"):
                embed.add_field(
                    name="🎫 MTGO", value=f"{prices['tix']} tix", inline=True
                )

            if not any(prices.values()):
                embed.description = "No hay información de precios disponible."

            purchase_uris = data.get("purchase_uris", {})
            if purchase_uris:
                links = []
                if "tcgplayer" in purchase_uris:
                    links.append(f"[TCGPlayer]({purchase_uris['tcgplayer']})")
                if "cardmarket" in purchase_uris:
                    links.append(f"[Cardmarket]({purchase_uris['cardmarket']})")
                if "cardhoarder" in purchase_uris:
                    links.append(f"[Cardhoarder]({purchase_uris['cardhoarder']})")

                if links:
                    embed.add_field(
                        name="🔗 Comprar", value=" | ".join(links), inline=False
                    )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name="rulings", help="Muestra las aclaraciones oficiales de una carta")
async def ver_rulings(ctx, *, nombre_carta: str):
    """Muestra los rulings oficiales de una carta"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                params = {"fuzzy": nombre_carta}
                async with session.get(SCRYFALL_API, params=params) as response:
                    if response.status != 200:
                        await ctx.send(f'❌ No se encontró la carta "{nombre_carta}"')
                        return

                    data = await response.json()

                rulings_url = data.get("rulings_uri", "")
                if not rulings_url:
                    await ctx.send("❌ No hay rulings disponibles para esta carta")
                    return

                async with session.get(rulings_url) as response:
                    if response.status != 200:
                        await ctx.send("❌ Error al obtener rulings")
                        return

                    rulings_data = await response.json()

            rulings = rulings_data.get("data", [])

            if not rulings:
                await ctx.send(f'No hay rulings oficiales para {data["name"]}')
                return

            embed = discord.Embed(
                title=f"📖 Rulings - {data['name']}", color=discord.Color.green()
            )

            if "image_uris" in data:
                embed.set_thumbnail(url=data["image_uris"]["small"])

            for i, ruling in enumerate(rulings[:10], 1):
                fecha = ruling.get("published_at", "N/A")
                texto = ruling.get("comment", "Sin información")
                if len(texto) > 400:
                    texto = texto[:397] + "..."
                embed.add_field(name=f"{i}. {fecha}", value=texto, inline=False)

            if len(rulings) > 10:
                embed.set_footer(text=f"Mostrando 10 de {len(rulings)} rulings")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="comandante",
    aliases=["commander"],
    help="Busca comandantes por colores. Ej: !comandante UR",
)
async def buscar_comandante(ctx, colores: str = ""):
    """Busca comandantes aleatorios basados en colores"""
    async with ctx.typing():
        try:
            # Construir query para comandantes
            query = "is:commander"
            if colores:
                query += f" id:{colores.lower()}"

            async with aiohttp.ClientSession() as session:
                params = {"q": query, "order": "edhrec"}
                async with session.get(SCRYFALL_SEARCH, params=params) as response:
                    if response.status != 200:
                        await ctx.send(
                            "❌ No se encontraron comandantes con esos colores"
                        )
                        return

                    data = await response.json()

            cards = data.get("data", [])
            if not cards:
                await ctx.send("❌ No se encontraron comandantes")
                return

            # Mostrar los 10 más populares
            embed = discord.Embed(
                title=f"👑 Comandantes populares {colores.upper() if colores else ''}",
                description=f"Mostrando los más jugados (según EDHREC)",
                color=discord.Color.purple(),
            )

            for i, card in enumerate(cards[:10], 1):
                nombre = card.get("name", "Sin nombre")
                tipo = card.get("type_line", "")
                mana = card.get("mana_cost", "")

                texto = card.get("oracle_text", "")
                if len(texto) > 150:
                    texto = texto[:147] + "..."

                embed.add_field(
                    name=f"{i}. {nombre} {mana}",
                    value=f"{tipo}\n{texto}" if texto else tipo,
                    inline=False,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="comparar",
    aliases=["vs"],
    help="Compara dos cartas. Ej: !comparar Lightning Bolt | Shock",
)
async def comparar_cartas(ctx, *, cartas: str):
    """Compara dos cartas lado a lado"""
    if "|" not in cartas and " vs " not in cartas.lower():
        await ctx.send(
            "❌ Usa el formato: !comparar carta1 | carta2 o !comparar carta1 vs carta2"
        )
        return

    separador = "|" if "|" in cartas else " vs "
    nombres = [c.strip() for c in cartas.split(separador, 1)]

    if len(nombres) != 2:
        await ctx.send("❌ Debes especificar exactamente dos cartas")
        return

    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                # Buscar ambas cartas
                cartas_data = []
                for nombre in nombres:
                    params = {"fuzzy": nombre}
                    async with session.get(SCRYFALL_API, params=params) as response:
                        if response.status == 200:
                            cartas_data.append(await response.json())
                        else:
                            await ctx.send(f"❌ No se encontró: {nombre}")
                            return

            if len(cartas_data) != 2:
                return

            # Crear embed comparativo
            embed = discord.Embed(
                title="⚔️ Comparación de Cartas", color=discord.Color.orange()
            )

            for i, carta in enumerate(cartas_data, 1):
                nombre = carta.get("name", "Sin nombre")
                tipo = carta.get("type_line", "N/A")
                mana = carta.get("mana_cost", "N/A")
                cmc = carta.get("cmc", "N/A")

                info = f"**Tipo:** {tipo}\n**Maná:** {mana}\n**CMC:** {int(cmc) if isinstance(cmc, float) else cmc}"

                if "power" in carta and "toughness" in carta:
                    info += f"\n**P/R:** {carta['power']}/{carta['toughness']}"

                texto = carta.get("oracle_text", "")
                if texto:
                    if len(texto) > 200:
                        texto = texto[:197] + "..."
                    info += f"\n\n{texto}"

                embed.add_field(
                    name=f"{'1️⃣' if i == 1 else '2️⃣'} {nombre}", value=info, inline=True
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="set", aliases=["expansion"], help="Muestra información sobre una expansión"
)
async def info_set(ctx, *, nombre_set: str):
    """Muestra información sobre una expansión"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SCRYFALL_SETS) as response:
                    if response.status != 200:
                        await ctx.send("❌ Error al obtener información de sets")
                        return

                    data = await response.json()

            sets = data.get("data", [])

            # Buscar el set por nombre (fuzzy match)
            set_encontrado = None
            nombre_lower = nombre_set.lower()
            for s in sets:
                if (
                    nombre_lower in s.get("name", "").lower()
                    or nombre_lower == s.get("code", "").lower()
                ):
                    set_encontrado = s
                    break

            if not set_encontrado:
                await ctx.send(f'❌ No se encontró la expansión "{nombre_set}"')
                return

            embed = discord.Embed(
                title=f"📦 {set_encontrado['name']}",
                url=set_encontrado.get("scryfall_uri", ""),
                color=discord.Color.blue(),
            )

            if "icon_svg_uri" in set_encontrado:
                embed.set_thumbnail(url=set_encontrado["icon_svg_uri"])

            embed.add_field(
                name="Código",
                value=set_encontrado.get("code", "N/A").upper(),
                inline=True,
            )
            embed.add_field(
                name="Cartas",
                value=str(set_encontrado.get("card_count", "N/A")),
                inline=True,
            )

            fecha = set_encontrado.get("released_at", "N/A")
            embed.add_field(name="Fecha de lanzamiento", value=fecha, inline=True)

            tipo_set = set_encontrado.get("set_type", "").replace("_", " ").title()
            embed.add_field(name="Tipo", value=tipo_set, inline=True)

            if set_encontrado.get("digital"):
                embed.add_field(name="Digital", value="✅ Sí", inline=True)

            if set_encontrado.get("foil_only"):
                embed.add_field(name="Solo Foil", value="✨ Sí", inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="spoilers", aliases=["nuevas"], help="Muestra las últimas cartas reveladas"
)
async def ver_spoilers(ctx):
    """Muestra las cartas más recientes añadidas a Scryfall"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                # Buscar cartas ordenadas por fecha de adición
                params = {"q": "date>=2024-01-01", "order": "released", "dir": "desc"}
                async with session.get(SCRYFALL_SEARCH, params=params) as response:
                    if response.status != 200:
                        await ctx.send("❌ Error al obtener spoilers")
                        return

                    data = await response.json()

            cards = data.get("data", [])[:8]

            if not cards:
                await ctx.send("No hay spoilers recientes disponibles")
                return

            embed = discord.Embed(
                title="🆕 Cartas Recientes",
                description="Las últimas cartas añadidas a Scryfall",
                color=discord.Color.green(),
            )

            for i, card in enumerate(cards, 1):
                nombre = card.get("name", "Sin nombre")
                set_name = card.get("set_name", "Unknown")
                fecha = card.get("released_at", "N/A")
                mana = card.get("mana_cost", "")

                embed.add_field(
                    name=f"{i}. {nombre} {mana}",
                    value=f"*{set_name}* - {fecha}",
                    inline=False,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="artista",
    aliases=["artist"],
    help="Busca cartas de un artista. Ej: !artista Seb McKinnon",
)
async def buscar_artista(ctx, *, nombre_artista: str):
    """Busca cartas ilustradas por un artista específico"""
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                query = f'artist:"{nombre_artista}"'
                params = {"q": query, "order": "released"}
                async with session.get(SCRYFALL_SEARCH, params=params) as response:
                    if response.status != 200:
                        await ctx.send(
                            f'❌ No se encontraron cartas de "{nombre_artista}"'
                        )
                        return

                    data = await response.json()

            total = data.get("total_cards", 0)
            cards = data.get("data", [])[:10]

            embed = discord.Embed(
                title=f"🎨 Cartas de {nombre_artista}",
                description=f"Total de cartas ilustradas: {total}\nMostrando las 10 más recientes:",
                color=discord.Color.purple(),
            )

            for i, card in enumerate(cards, 1):
                nombre = card.get("name", "Sin nombre")
                set_name = card.get("set_name", "Unknown")
                mana = card.get("mana_cost", "")

                embed.add_field(
                    name=f"{i}. {nombre} {mana}", value=set_name, inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="color",
    aliases=["identidad"],
    help="Busca cartas de una identidad de color. Ej: !color UG",
)
async def buscar_color(ctx, colores: str, cantidad: int = 5):
    """Busca cartas populares de una identidad de color específica"""
    async with ctx.typing():
        try:
            # Validar colores
            colores_validos = set("WUBRG")
            colores_upper = colores.upper()

            if not all(c in colores_validos for c in colores_upper):
                await ctx.send(
                    "❌ Colores válidos: W (blanco), U (azul), B (negro), R (rojo), G (verde)"
                )
                return

            async with aiohttp.ClientSession() as session:
                query = f"id:{colores_upper}"
                params = {"q": query, "order": "edhrec"}
                async with session.get(SCRYFALL_SEARCH, params=params) as response:
                    if response.status != 200:
                        await ctx.send(f"❌ No se encontraron cartas con esos colores")
                        return

                    data = await response.json()

            cards = data.get("data", [])[:cantidad]

            colores_nombres = {
                "W": "Blanco",
                "U": "Azul",
                "B": "Negro",
                "R": "Rojo",
                "G": "Verde",
            }

            nombre_colores = " + ".join(
                [colores_nombres.get(c, c) for c in colores_upper]
            )

            embed = discord.Embed(
                title=f"🎨 Cartas populares - {nombre_colores}",
                description=f"Top {len(cards)} cartas más jugadas",
                color=discord.Color.blue(),
            )

            for i, card in enumerate(cards, 1):
                nombre = card.get("name", "Sin nombre")
                tipo = card.get("type_line", "N/A")
                mana = card.get("mana_cost", "")

                embed.add_field(name=f"{i}. {nombre} {mana}", value=tipo, inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name="stats", help="Muestra estadísticas del bot")
async def estadisticas(ctx):
    """Muestra estadísticas generales del bot"""
    embed = discord.Embed(title="📊 Estadísticas del Bot", color=discord.Color.blue())

    embed.add_field(name="Servidores", value=str(len(bot.guilds)), inline=True)

    total_usuarios = sum(g.member_count for g in bot.guilds)
    embed.add_field(name="Usuarios", value=str(total_usuarios), inline=True)

    total_favoritos = sum(len(favs) for favs in favoritos_usuarios.values())
    embed.add_field(name="Total Favoritos", value=str(total_favoritos), inline=True)

    usuarios_con_favs = len(favoritos_usuarios)
    embed.add_field(
        name="Usuarios con Favoritos", value=str(usuarios_con_favs), inline=True
    )

    comandos = len([c for c in bot.commands])
    embed.add_field(name="Comandos Disponibles", value=str(comandos), inline=True)

    embed.set_footer(text=f"Bot creado con discord.py | API de Scryfall")

    await ctx.send(embed=embed)


@bot.command(name="help_mtg", help="Muestra información sobre cómo usar el bot")
async def help_mtg(ctx):
    """Muestra información de ayuda sobre los comandos del bot"""
    embed = discord.Embed(
        title="🎴 Bot de Magic: The Gathering - Guía Completa",
        description="Bot para buscar y explorar cartas de Magic usando la API de Scryfall",
        color=discord.Color.purple(),
    )

    embed.add_field(
        name="🔍 Búsqueda Básica",
        value="`!carta <nombre>` - Busca una carta por nombre\n"
        "`!random` - Carta aleatoria\n"
        "`!precio <carta>` - Ver precios",
        inline=False,
    )

    embed.add_field(
        name="🔎 Búsqueda Avanzada",
        value="`!buscar <criterios>` - Búsqueda con filtros\n"
        "`!artista <nombre>` - Cartas de un artista\n"
        "`!color <colores>` - Cartas por identidad de color",
        inline=False,
    )

    embed.add_field(
        name="⚖️ Información Legal",
        value="`!legal <carta>` - Ver legalidad en formatos\n"
        "`!rulings <carta>` - Ver aclaraciones oficiales",
        inline=False,
    )

    embed.add_field(
        name="👑 Commander",
        value="`!comandante <colores>` - Buscar comandantes\n"
        "Ejemplo: `!comandante UR` (azul-rojo)",
        inline=False,
    )

    embed.add_field(
        name="⚔️ Comparación",
        value="`!comparar carta1 | carta2` - Compara dos cartas\n"
        "También: `!comparar carta1 vs carta2`",
        inline=False,
    )

    embed.add_field(
        name="📦 Expansiones",
        value="`!set <nombre>` - Info sobre una expansión\n"
        "`!spoilers` - Ver cartas recientes",
        inline=False,
    )

    embed.add_field(
        name="⭐ Favoritos",
        value="`!favoritos` - Ver tus cartas favoritas\n"
        "Usa el botón en cualquier carta para añadirla",
        inline=False,
    )

    embed.add_field(
        name="🧱 Mazos",
        value=(
            "`!mazo_crear <nombre_mazo>` → Te crea un mazo con el nombre indicado.\n"
            "`!mazo_add <nombre_mazo> <nombre_carta>` → Añade una carta a un mazo. "
            "Si el mazo no existe, se crea automáticamente.\n"
            "`!mazo_ver <nombre_mazo>` → Muestra las cartas del mazo con navegación por ⬅️ y ➡️.\n"
            "`!mazos` → Lista todos tus mazos creados.\n"
            "`!mazo_remover <nombre_mazo> | <nombre_carta>` → Quita una carta de un mazo.\n"
            "`!mazo_eliminar <nombre_mazo>` → Borra el mazo indicado.\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="📊 Otros",
        value="`!stats` - Estadísticas del bot\n" "`!help_mtg` - Ver esta ayuda",
        inline=False,
    )

    embed.add_field(
        name="💡 Ejemplos de Búsqueda Avanzada",
        value="`!buscar c:red t:creature cmc<=3` - Criaturas rojas CMC 3 o menos\n"
        "`!buscar t:instant c:blue` - Instantáneos azules\n"
        "`!buscar o:flying c:white` - Cartas blancas con volar",
        inline=False,
    )

    embed.add_field(
        name="💡 Ejemplos de Búsqueda Avanzada",
        value="`!buscar c:red t:creature cmc<=3` - Criaturas rojas CMC 3 o menos\n"
        "`!buscar t:instant c:blue` - Instantáneos azules\n"
        "`!buscar o:flying c:white` - Cartas blancas con volar",
        inline=False,
    )

    embed.set_footer(text="🌐 Sintaxis completa en: scryfall.com/docs/syntax")

    await ctx.send(embed=embed)


@bot.command(
    name="mazo_add",
    help="Añade una carta a uno de tus mazos. Ej: !mazo_add MiMazo Lightning Bolt",
)
async def mazo_add(ctx, nombre_mazo: str, *, nombre_carta: str):
    user_id = str(ctx.author.id)
    if user_id not in mazos_usuarios:
        mazos_usuarios[user_id] = {}

    if nombre_mazo not in mazos_usuarios[user_id]:
        mazos_usuarios[user_id][nombre_mazo] = []

    async with aiohttp.ClientSession() as session:
        params = {"fuzzy": nombre_carta}
        async with session.get(SCRYFALL_API, params=params) as response:
            if response.status != 200:
                await ctx.send(f'❌ No se encontró la carta "{nombre_carta}"')
                return
            data = await response.json()

    mazos_usuarios[user_id][nombre_mazo].append(data)
    guardar_mazos()  # ✅ <--- IMPORTANTE
    await ctx.send(f'✅ Añadida **{data["name"]}** al mazo **{nombre_mazo}**')


@bot.command(
    name="mazo_ver", help="Muestra un mazo carta por carta. Ej: !mazo_ver MiMazo"
)
async def mazo_ver(ctx, *, nombre_mazo: str):
    user_id = str(ctx.author.id)
    mazos = mazos_usuarios.get(user_id, {})
    if nombre_mazo not in mazos or not mazos[nombre_mazo]:
        await ctx.send(
            f'❌ No tienes cartas en el mazo "{nombre_mazo}". Usa `!mazo_add` para añadir.'
        )
        return

    cartas = mazos[nombre_mazo]
    index = 0
    mensaje = await ctx.send(embed=crear_embed_carta(cartas[index]))
    await mensaje.add_reaction("⬅️")
    await mensaje.add_reaction("➡️")

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == mensaje.id
            and str(reaction.emoji) in ["⬅️", "➡️"]
        )

    while True:
        try:
            reaction, user = await bot.wait_for(
                "reaction_add", timeout=120.0, check=check
            )
            await mensaje.remove_reaction(reaction.emoji, user)

            if str(reaction.emoji) == "➡️":
                index = (index + 1) % len(cartas)
            elif str(reaction.emoji) == "⬅️":
                index = (index - 1) % len(cartas)

            await mensaje.edit(embed=crear_embed_carta(cartas[index]))

        except Exception:
            break


@bot.command(name="mazo_crear", help="Crea un nuevo mazo. Uso: !mazo_crear <nombre>")
async def mazo_crear(ctx, *, nombre: str):
    """Crea un nuevo mazo vacío"""
    user_id = str(ctx.author.id)
    if user_id not in mazos_usuarios:
        mazos_usuarios[user_id] = {}

    if nombre in mazos_usuarios[user_id]:
        await ctx.send("⚠️ Ya tienes un mazo con ese nombre.")
        return

    mazos_usuarios[user_id][nombre] = []
    guardar_mazos()
    await ctx.send(f"✅ Mazo **{nombre}** creado correctamente.")

@bot.command(
    name="mazo_remover",
    help="Elimina una carta de un mazo. Uso: !mazo_remover <nombre_mazo> <nombre_carta>",
)
async def mazo_remover(ctx, nombre_mazo: str, *, nombre_carta: str):
    global mazos_usuarios  # ✅ usamos el nombre correcto

    usuario_id = str(ctx.author.id)

    # Verificamos que el usuario y el mazo existan
    if usuario_id not in mazos_usuarios or nombre_mazo not in mazos_usuarios[usuario_id]:
        await ctx.send(f"⚠️ No tienes un mazo llamado **{nombre_mazo}**.")
        return

    mazo = mazos_usuarios[usuario_id][nombre_mazo]

    # Buscar la carta (por nombre parcial, sin distinguir mayúsculas)
    carta_encontrada = None
    for carta in mazo:
        if nombre_carta.lower() in carta["name"].lower():
            carta_encontrada = carta
            break

    # Si se encuentra, eliminarla
    if carta_encontrada:
        mazo.remove(carta_encontrada)
        guardar_mazos()  # tu función de guardado
        await ctx.send(f"🗑️ Se ha eliminado **{nombre_carta}** del mazo **{nombre_mazo}**.")
    else:
        await ctx.send(f"⚠️ La carta **{nombre_carta}** no está en el mazo **{nombre_mazo}**.")

@bot.command(
    name="mazo_eliminar",
    help="Elimina un mazo completo. Uso: !mazo_eliminar <nombre_mazo>",
)
async def mazo_eliminar(ctx, *, nombre_mazo: str):
    """Elimina un mazo completo"""
    user_id = str(ctx.author.id)
    if user_id not in mazos_usuarios or nombre_mazo not in mazos_usuarios[user_id]:
        await ctx.send("❌ No tienes un mazo con ese nombre.")
        return

    del mazos_usuarios[user_id][nombre_mazo]
    guardar_mazos()
    await ctx.send(f"🗑️ Mazo **{nombre_mazo}** eliminado correctamente.")


@bot.command(name="mazos", help="Muestra todos tus mazos")
async def listar_mazos(ctx):
    """Muestra todos los mazos del usuario"""
    user_id = str(ctx.author.id)
    if user_id not in mazos_usuarios or not mazos_usuarios[user_id]:
        await ctx.send(
            "📭 No tienes mazos aún. Usa `!mazo_crear <nombre>` para crear uno."
        )
        return

    embed = discord.Embed(
        title=f"📚 Mazos de {ctx.author.display_name}", color=discord.Color.blurple()
    )

    for nombre, cartas in mazos_usuarios[user_id].items():
        embed.add_field(
            name=f"🧩 {nombre}", value=f"{len(cartas)} cartas", inline=False
        )

    await ctx.send(embed=embed)


# Manejo de errores
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Falta un argumento. Usa `!help_mtg` para ver la sintaxis correcta."
        )
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(
            f"❌ Comando no encontrado. Usa `!help_mtg` para ver los comandos disponibles."
        )
    else:
        await ctx.send(f"❌ Error: {str(error)}")
        print(f"Error: {error}")


# Mi token de bot de Discord
if __name__ == "__main__":
    TOKEN = "MTQzMzA1NTkxMDI1MDY4MDQzMQ.GxbUYi.dwn5w1OSCUMuDOzriYTQcmXk2i__tqI1XjS-QE"
    if not TOKEN:
        print("Error: TOKEN no añadida")
    else:
        bot.run(TOKEN)
