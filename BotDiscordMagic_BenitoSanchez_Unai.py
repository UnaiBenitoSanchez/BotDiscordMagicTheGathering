import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import aiohttp
import json
import os
from datetime import datetime
from threading import Thread
from flask import Flask

# Config básica
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

bot_status = "starting"

# URLs de Scryfall
SCRYFALL_API = "https://api.scryfall.com/cards/named"
SCRYFALL_RANDOM = "https://api.scryfall.com/cards/random"

# Donde guardamos los favoritos
FAVORITOS_FILE = "./favoritos.json"

# Aquí van los favoritos de cada persona
favoritos_usuarios = {}

#KeepAlive con Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot de MTG está activo! 🎴", 200

@app.route('/health')
def health():
    return {
        "status": bot_status,
        "timestamp": datetime.now().isoformat()
    }, 200


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    server = Thread(target=run_flask)
    server.daemon = True
    server.start()
    print(f"✅ Servidor HTTP iniciado en puerto {os.environ.get('PORT', 5000)}")

# Funciones
def cargar_favoritos():
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
    try:
        with open(FAVORITOS_FILE, "w", encoding="utf-8") as f:
            json.dump(favoritos_usuarios, f, ensure_ascii=False, indent=2)
        print("💾 Favoritos guardados correctamente")
    except Exception as e:
        print(f"❌ Error al guardar favoritos: {e}")

def crear_embed_carta(data):
    nombre = data.get("name", "Sin nombre")
    embed = discord.Embed(
        title=nombre,
        url=data.get("scryfall_uri", ""),
        color=discord.Color.blue(),
    )

    if "image_uris" in data:
        embed.set_image(url=data["image_uris"]["normal"])
    elif "card_faces" in data and len(data["card_faces"]) > 0:
        if "image_uris" in data["card_faces"][0]:
            embed.set_image(url=data["card_faces"][0]["image_uris"]["normal"])

    if "type_line" in data:
        embed.add_field(name="Tipo", value=data["type_line"], inline=False)

    if "mana_cost" in data:
        embed.add_field(name="Coste de Maná", value=data["mana_cost"], inline=True)

    if "cmc" in data:
        embed.add_field(name="CMC", value=str(int(data["cmc"])), inline=True)

    if "oracle_text" in data:
        texto = data["oracle_text"]
        if len(texto) > 1024:
            texto = texto[:1021] + "..."
        embed.add_field(name="Habilidades", value=texto, inline=False)
    elif "card_faces" in data:
        for i, face in enumerate(data["card_faces"][:2], 1):
            if "oracle_text" in face:
                texto = face["oracle_text"]
                if len(texto) > 1024:
                    texto = texto[:1021] + "..."
                nombre_cara = face.get("name", f"Cara {i}")
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

    if "artist" in data:
        embed.set_footer(text=f"Ilustrado por: {data['artist']}")

    return embed


class CardView(View):
    def __init__(self, data, user_id):
        super().__init__(timeout=180)
        self.data = data
        self.user_id = user_id
        self.card_name = data.get("name", "")

    @discord.ui.button(
        label="Añadir a Favoritos", style=discord.ButtonStyle.success, emoji="⭐"
    )
    async def favorite_button(self, interaction: discord.Interaction, button: Button):
        user_id = str(interaction.user.id)

        if user_id not in favoritos_usuarios:
            favoritos_usuarios[user_id] = []

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
    global bot_status
    bot_status = "online"
    
    cargar_favoritos()

    if not auto_guardar.is_running():
        auto_guardar.start()

    print(f"{bot.user} está conectado y listo!")

@bot.event
async def on_disconnect():
    global bot_status
    bot_status = "offline"
    print("⚠️ El bot se desconectó")


@tasks.loop(minutes=5)
async def auto_guardar():
    guardar_favoritos()
    print(f"💾 Auto-guardado completado - {datetime.now().strftime('%H:%M:%S')}")


@auto_guardar.before_loop
async def before_auto_guardar():
    await bot.wait_until_ready()


@bot.command(
    name="random",
    aliases=["aleatoria", "carta_aleatoria"],
    help="Muestra una carta aleatoria",
)
async def carta_aleatoria(ctx):
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
    name="buscar",
    aliases=["carta", "search"],
    help="Busca una carta por nombre",
)
async def buscar_carta(ctx, *, nombre: str):
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
    user_id = str(ctx.author.id)

    if user_id not in favoritos_usuarios or not favoritos_usuarios[user_id]:
        await ctx.send(
            '⭐ No tienes cartas favoritas aún. Usa el botón "Añadir a Favoritos" en cualquier carta.'
        )
        return

    favoritos = favoritos_usuarios[user_id]

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

    index = 0
    embed = crear_embed_carta(cartas_data[index])
    embed.title = f"⭐ Favoritos ({index + 1}/{len(cartas_data)}): {embed.title}"

    mensaje = await ctx.send(embed=embed)

    await mensaje.add_reaction("⬅️")
    await mensaje.add_reaction("➡️")
    await mensaje.add_reaction("🗑️")

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == mensaje.id
            and str(reaction.emoji) in ["⬅️", "➡️", "🗑️"]
        )

    while True:
        try:
            reaction, user = await bot.wait_for(
                "reaction_add", timeout=120.0, check=check
            )

            try:
                await mensaje.remove_reaction(reaction.emoji, user)
            except discord.Forbidden:
                print("⚠️ El bot no tiene permisos para quitar reacciones")
            except Exception as e:
                print(f"Error quitando reacción: {e}")

            if str(reaction.emoji) == "➡️":
                index = (index + 1) % len(cartas_data)

            elif str(reaction.emoji) == "⬅️":
                index = (index - 1) % len(cartas_data)

            elif str(reaction.emoji) == "🗑️":
                carta_eliminada = cartas_data[index]["name"]
                favoritos_usuarios[user_id].remove(carta_eliminada)
                guardar_favoritos()
                cartas_data.pop(index)

                if not cartas_data:
                    await mensaje.edit(
                        content="✅ Ya no tienes cartas favoritas", embed=None
                    )
                    await mensaje.clear_reactions()
                    return

                if index >= len(cartas_data):
                    index = 0

                await ctx.send(
                    f"🗑️ **{carta_eliminada}** eliminada de favoritos", delete_after=3
                )

            embed = crear_embed_carta(cartas_data[index])
            embed.title = (
                f"⭐ Favoritos ({index + 1}/{len(cartas_data)}): {embed.title}"
            )
            await mensaje.edit(embed=embed)

        except Exception:
            try:
                await mensaje.clear_reactions()
            except:
                pass
            break


@bot.command(name="help", help="Muestra información sobre cómo usar el bot")
async def help_command(ctx):
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


@bot.event
async def on_command_error(ctx, error):
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


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")

    if not TOKEN:
        print("❌ Error: No hay TOKEN en las variables de entorno")
    else:
        # Iniciar servidor HTTP para keepalive
        keep_alive()
        
        # Iniciar el bot
        bot.run(TOKEN)