import discord
from discord.ext import commands
from discord.ui import Button, View
import aiohttp
import json
import os
from datetime import datetime

# Config básica
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# URLs de Scryfall
SCRYFALL_API = "https://api.scryfall.com/cards/named"
SCRYFALL_RANDOM = "https://api.scryfall.com/cards/random"

# Donde guardamos los favoritos
FAVORITOS_FILE = "./favoritos.json"

# Aquí van los favoritos de cada persona
favoritos_usuarios = {}

def cargar_favoritos():
    # Lee los favoritos del archivo
    global favoritos_usuarios
    try:
        if os.path.exists(FAVORITOS_FILE):
            with open(FAVORITOS_FILE, "r", encoding="utf-8") as f:
                favoritos_usuarios = json.load(f)
            print(f"✅ Favoritos cargados: {len(favoritos_usuarios)} usuarios")
        else:
            favoritos_usuarios = {}
    except Exception as e:
        print(f"❌ Error al cargar favoritos: {e}")
        favoritos_usuarios = {}


def guardar_favoritos():
    # Escribe los favoritos en el archivo
    try:
        with open(FAVORITOS_FILE, "w", encoding="utf-8") as f:
            json.dump(favoritos_usuarios, f, ensure_ascii=False, indent=2)
        print("💾 Favoritos guardados correctamente")
    except Exception as e:
        print(f"❌ Error al guardar favoritos: {e}")

def crear_embed_carta(data):
    # Monta el embed con toda la info de la carta
    nombre = data.get("name", "Sin nombre")
    embed = discord.Embed(
        title=nombre,
        url=data.get("scryfall_uri", ""),
        color=discord.Color.blue(),
    )

    # Imagen de la carta
    if "image_uris" in data:
        embed.set_image(url=data["image_uris"]["normal"])
    elif "card_faces" in data and len(data["card_faces"]) > 0:
        if "image_uris" in data["card_faces"][0]:
            embed.set_image(url=data["card_faces"][0]["image_uris"]["normal"])

    # Tipo de carta
    if "type_line" in data:
        embed.add_field(name="Tipo", value=data["type_line"], inline=False)

    # El maná que cuesta
    if "mana_cost" in data:
        embed.add_field(name="Coste de Maná", value=data["mana_cost"], inline=True)

    # CMC
    if "cmc" in data:
        embed.add_field(name="CMC", value=str(int(data["cmc"])), inline=True)

    # Texto de la carta
    if "oracle_text" in data:
        texto = data["oracle_text"]
        if len(texto) > 1024:
            texto = texto[:1021] + "..."
        embed.add_field(name="Habilidades", value=texto, inline=False)
    elif "card_faces" in data:
        # Para las cartas de doble cara
        for i, face in enumerate(data["card_faces"][:2], 1):
            if "oracle_text" in face:
                texto = face["oracle_text"]
                if len(texto) > 1024:
                    texto = texto[:1021] + "..."
                nombre_cara = face.get("name", f"Cara {i}")
                embed.add_field(
                    name=f"Habilidades - {nombre_cara}", value=texto, inline=False
                )

    # Stats de criatura
    if "power" in data and "toughness" in data:
        embed.add_field(
            name="Poder/Resistencia",
            value=f"{data['power']}/{data['toughness']}",
            inline=True,
        )

    # Lealtad
    if "loyalty" in data:
        embed.add_field(name="Lealtad", value=data["loyalty"], inline=True)

    # Rareza
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

    # Set donde salió
    if "set_name" in data:
        embed.add_field(name="Expansión", value=data["set_name"], inline=True)

    # El artista
    if "artist" in data:
        embed.set_footer(text=f"Ilustrado por: {data['artist']}")

    return embed


class CardView(View):
    # Los botones que van debajo de cada carta

    def __init__(self, data, user_id):
        super().__init__(timeout=180)
        self.data = data
        self.user_id = user_id
        self.card_name = data.get("name", "")

    @discord.ui.button(
        label="Añadir a Favoritos", style=discord.ButtonStyle.success, emoji="⭐"
    )
    async def favorite_button(self, interaction: discord.Interaction, button: Button):
        # Cuando le das al botón de favoritos
        user_id = str(interaction.user.id)

        # Si es la primera vez que añade favoritos
        if user_id not in favoritos_usuarios:
            favoritos_usuarios[user_id] = []

        # Metemos la carta si no está ya
        if self.card_name not in favoritos_usuarios[user_id]:
            favoritos_usuarios[user_id].append(self.card_name)
            guardar_favoritos()
            await interaction.response.send_message(
                f"⭐ ¡{self.card_name} añadida a favoritos!", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Esta carta ya está en tus favoritos.", ephemeral=True
            )


@bot.event
async def on_ready():
    # Cuando el bot arranca
    cargar_favoritos()

    # Activamos el guardado automático
    if not auto_guardar.is_running():
        auto_guardar.start()

    print(f"{bot.user} está conectado y listo!")
    print(f"📊 Usuarios con favoritos: {len(favoritos_usuarios)}")
    print("------")


# Guardado cada 5 min para no perder datos
from discord.ext import tasks


@tasks.loop(minutes=5)
async def auto_guardar():
    # Guarda cada cierto tiempo para no perder datos
    guardar_favoritos()
    print(f"💾 Auto-guardado completado - {datetime.now().strftime('%H:%M:%S')}")


@auto_guardar.before_loop
async def before_auto_guardar():
    # Espera a que el bot esté preparado
    await bot.wait_until_ready()


@bot.command(
    name="random",
    aliases=["aleatoria", "carta_aleatoria"],
    help="Muestra una carta aleatoria",
)
async def carta_aleatoria(ctx):
    # Saca una carta random de toda la base de datos
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SCRYFALL_RANDOM) as response:
                    if response.status != 200:
                        await ctx.send("❌ Error al obtener carta aleatoria")
                        return

                    data = await response.json()

            # Montamos y enviamos
            embed = crear_embed_carta(data)
            embed.title = f"🎲 Carta Aleatoria: {embed.title}"
            view = CardView(data, ctx.author.id)

            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="buscar",
    aliases=["carta", "search"],
    help="Busca una carta por nombre",
)
async def buscar_carta(ctx, *, nombre: str):
    # Busca una carta específica por nombre
    async with ctx.typing():
        try:
            async with aiohttp.ClientSession() as session:
                params = {"fuzzy": nombre}
                async with session.get(SCRYFALL_API, params=params) as response:
                    if response.status == 404:
                        await ctx.send(f"❌ No se encontró ninguna carta con el nombre '{nombre}'")
                        return
                    elif response.status != 200:
                        await ctx.send("❌ Error al buscar la carta")
                        return

                    data = await response.json()

            # Montamos y enviamos
            embed = crear_embed_carta(data)
            embed.title = f"🔍 {embed.title}"
            view = CardView(data, ctx.author.id)

            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")


@bot.command(
    name="favoritos",
    aliases=["misfavoritas"],
    help="Muestra tus cartas favoritas con navegación",
)
async def ver_favoritos(ctx):
    # Muestra los favoritos del usuario
    user_id = str(ctx.author.id)

    # Si no tiene nada guardado
    if user_id not in favoritos_usuarios or not favoritos_usuarios[user_id]:
        await ctx.send(
            '⭐ No tienes cartas favoritas aún. Usa el botón "Añadir a Favoritos" en cualquier carta.'
        )
        return

    favoritos = favoritos_usuarios[user_id]

    # Vamos a buscar los datos completos de cada carta
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

    # Empezamos mostrando la primera
    index = 0
    embed = crear_embed_carta(cartas_data[index])
    embed.title = f"⭐ Favoritos ({index + 1}/{len(cartas_data)}): {embed.title}"

    mensaje = await ctx.send(embed=embed)

    # Ponemos las flechas para navegar entre cartas
    await mensaje.add_reaction("⬅️")
    await mensaje.add_reaction("➡️")
    await mensaje.add_reaction("🗑️")

    def check(reaction, user):
        # Solo el autor puede navegar
        return (
            user == ctx.author
            and reaction.message.id == mensaje.id
            and str(reaction.emoji) in ["⬅️", "➡️", "🗑️"]
        )

    # Loop de navegación
    while True:
        try:
            # Esperamos a que reaccione
            reaction, user = await bot.wait_for(
                "reaction_add", timeout=120.0, check=check
            )

            # Quitamos la reacción
            try:
                await mensaje.remove_reaction(reaction.emoji, user)
            except discord.Forbidden:
                print("⚠️ El bot no tiene permisos para quitar reacciones")
            except Exception as e:
                print(f"Error quitando reacción: {e}")

            # Siguiente carta
            if str(reaction.emoji) == "➡️":
                index = (index + 1) % len(cartas_data)

            # Carta anterior
            elif str(reaction.emoji) == "⬅️":
                index = (index - 1) % len(cartas_data)

            # Borrar carta
            elif str(reaction.emoji) == "🗑️":
                carta_eliminada = cartas_data[index]["name"]
                favoritos_usuarios[user_id].remove(carta_eliminada)
                guardar_favoritos()
                cartas_data.pop(index)

                # Si ya no quedan favoritos
                if not cartas_data:
                    await mensaje.edit(
                        content="✅ Ya no tienes cartas favoritas", embed=None
                    )
                    await mensaje.clear_reactions()
                    return

                # Si borramos la última, volvemos al principio
                if index >= len(cartas_data):
                    index = 0

                await ctx.send(
                    f"🗑️ **{carta_eliminada}** eliminada de favoritos", delete_after=3
                )

            # Actualizamos el embed
            embed = crear_embed_carta(cartas_data[index])
            embed.title = (
                f"⭐ Favoritos ({index + 1}/{len(cartas_data)}): {embed.title}"
            )
            await mensaje.edit(embed=embed)

        except Exception:
            # Se acabó el tiempo o hubo error
            try:
                await mensaje.clear_reactions()
            except:
                pass
            break


@bot.command(name="help", help="Muestra información sobre cómo usar el bot")
async def help_command(ctx):
    
    # COntenido del mensaje de ayuda
    embed = discord.Embed(
        title="🎴 Bot de Magic: The Gathering",
        description="Bot para explorar cartas de Magic the Gathering",
        color=discord.Color.purple(),
    )

    embed.add_field(
        name="🎲 Carta Aleatoria",
        value="`!random` - Muestra una carta aleatoria de Magic\n"
        "`!aleatoria` - Alias del comando anterior\n"
        "`!carta_aleatoria` - Otro alias disponible",
        inline=False,
    )

    embed.add_field(
        name="🔍 Buscar Cartas",
        value="`!buscar <nombre>` - Busca una carta por nombre\n"
        "`!carta <nombre>` - Alias del comando anterior\n"
        "`!search <nombre>` - Otro alias disponible\n\n"
        "Ejemplo: `!buscar Lightning Bolt`",
        inline=False,
    )

    embed.add_field(
        name="⭐ Favoritos",
        value="`!favoritos` - Ver tus cartas favoritas\n"
        "`!misfavoritas` - Alias del comando anterior\n\n"
        "Usa el botón **⭐ Añadir a Favoritos** en cualquier carta para guardarla",
        inline=False,
    )

    embed.add_field(
        name="🗂️ Navegación de Favoritos",
        value="⬅️ Carta anterior\n"
        "➡️ Carta siguiente\n"
        "🗑️ Eliminar carta de favoritos",
        inline=False,
    )

    embed.add_field(
        name="ℹ️ Información",
        value="`!help` - Muestra esta ayuda",
        inline=False,
    )

    embed.set_footer(text="🌐 Datos sacados de: Scryfall API")

    await ctx.send(embed=embed)


# Por si algo falla
@bot.event
async def on_command_error(ctx, error):
    # Manejo de errores básico
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Falta un argumento. Usa `!help` para ver la sintaxis correcta."
        )
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(
            f"❌ Comando no encontrado. Usa `!help` para ver los comandos disponibles."
        )
    else:
        await ctx.send(f"❌ Error: {str(error)}")
        print(f"Error: {error}")


# Aquí arranca todo
def cargar_token():
    try:
        with open("token.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print("❌ Error: No se encontró el archivo token.txt")
        return None

if __name__ == "__main__":
    TOKEN = cargar_token()
    if not TOKEN:
        print("❌ No se pudo cargar la token. Crea el archivo token.txt con tu token dentro.")
    else:
        bot.run(TOKEN)
