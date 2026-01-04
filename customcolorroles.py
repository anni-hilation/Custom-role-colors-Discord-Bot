import os
import logging
import discord
import asyncio
from discord import app_commands

# ---------- define stuff ----------

#role_name = f"ColorRole #{i+1}"
BLANK_NICK = "᲼᲼᲼᲼᲼᲼᲼᲼"
blanked_users = {}
active_loops: dict[int, asyncio.Task] = {}
TOKEN = "YOUR_TOKEN_HERE"
GUILD_ID = 1456367193565434041
MAX_PALETTES = 15
palettes = {
    1: ["#26E012", "#06F515", "#F5E109", "#F55B07", "#EB0408"],
    2: ["#FFC0CB", "#FF69B4", "#FF1493", "#DB7093", "#C71585"],
    3: ["#ADD8E6", "#87CEEB", "#4682B4", "#1E90FF", "#0000FF"],
    4: None,
    5: None,
    6: None,
    7: None,
    8: None,
    9: None,
    10: None,
    11: None,
    12: None,
    13: None,
    14: None,
    15: None
}


async def enforce_blank_names():
    await bot.wait_until_ready()  # make sure bot is connected
    while not bot.is_closed():    # loop forever until bot closes
        for user_id, old_nick in blanked_users.items():
            member = None
            for guild in bot.guilds:  # loop through all servers your bot is in
                member = guild.get_member(user_id)
                if member:
                    break
            if member:
                # Only enforce if they are not the server owner
                if member != member.guild.owner:
                    try:
                        await member.edit(nick=BLANK_NICK)  # enforce blank
                    except discord.Forbidden:
                        # bot cannot edit this user (role too high)
                        pass
        await asyncio.sleep(3)  # wait 3 seconds before next check

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

def interpolate_rgb(c1, c2, t):
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t)
    )

def stop_gradient(user):
    task = active_loops.get(user.id)
    if task:
        if not task.done():
            task.cancel()
        del active_loops[user.id]



async def gradient_loop(user, role, palette, steps: int, interval=1.75):
    try:
        while True:
            for i in range(len(palette)):
                c1 = hex_to_rgb(palette[i])
                c2 = hex_to_rgb(palette[(i + 1) % len(palette)])

                for step in range(steps):
                    t = step / steps
                    hex_code = rgb_to_hex(interpolate_rgb(c1, c2, t))

                    try:
                        await role.edit(
                            color=discord.Color(int(hex_code[1:], 16))
                        )

                    except discord.Forbidden:
                        print(f"[STOP] Missing permissions for {role.name}")
                        return

                    except discord.HTTPException as e:
                        print(
                            f"[WARN] HTTP error editing {role.name} "
                            f"(user={user.id}): {e}. Backing off."
                        )
                        await asyncio.sleep(10)
                        continue

                    except Exception as e:
                        print(
                            f"[CRASH] Unexpected error in gradient loop "
                            f"for {user.display_name}: {e}"
                        )
                        await asyncio.sleep(10)
                        continue

                    await asyncio.sleep(interval)

    except asyncio.CancelledError:
        print(f"[CANCELLED] Gradient stopped for {user.display_name}")
        return



async def get_or_create_color_role(guild, palette_id):
    role_name = f"ColorRole #{palette_id+1}"

    # Try to find an existing role with that name
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        # Create role if it doesn't exist
        role = await guild.create_role(
            name=role_name,
            color=discord.Color.default(),  # initial color, will be changed
            mentionable=False
        )
    return role

async def ensure_colorrole_position(guild: discord.Guild, role: discord.Role):
    bot_member = guild.me
    if not bot_member:
        return

    max_position = bot_member.top_role.position - 1

    blocking_roles = [
        r for r in guild.roles
        if r.position > role.position
        and not r.name.startswith("ColorRole")
        and r != bot_member.top_role
    ]

    if blocking_roles and role.position < max_position:
        await role.edit(position=max_position)

async def get_or_create_user_color_role(
    guild: discord.Guild,
    user: discord.Member
) -> discord.Role:
    role_name = f"ColorRole {user.id}"

    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        role = await guild.create_role(
            name=role_name,
            color=discord.Color.default(),
            mentionable=False
        )

    await ensure_colorrole_position(guild, role)
    return role


# ---------- basic error logging ----------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    filename="bot.log",
    filemode="a")

# ---------- bot setup ----------

INTENTS = discord.Intents.default()
INTENTS.members = True  # needed later for roles
INTENTS.messages = True
INTENTS.guilds = True

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=INTENTS)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Sync slash commands globally (can take up to 1 hour)
        await self.tree.sync()
        logging.info("Slash commands synced")

bot = MyBot()

# ---------- events ----------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)  # safe: only syncs in this guild
    print("Slash commands synced!")
    bot.loop.create_task(enforce_blank_names())  # starts the background loop


# ---------- test command ----------

@bot.tree.command(
    name="test",
    description="check bots command execution skills")

async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Hello \U0001F44B The command was sucsessful!",ephemeral=True)

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

# ---------- blank command ----------

@bot.tree.command(name="blank", description="Punish user by stealing their name >:D")

async def blank(interaction: discord.Interaction, user: discord.Member, state: bool):
    if state:
        if user.id in blanked_users:
            await interaction.response.send_message(f"{user.display_name} is already blanked!", ephemeral=True)
        else:
            blanked_users[user.id] = user.nick  # None if no nickname
            await user.edit(nick=BLANK_NICK)
            await interaction.response.send_message(f"{user.display_name} has been blanked!", ephemeral=False)
    else:
        if user.id in blanked_users:
            await user.edit(nick=blanked_users.get(user.id))
            del blanked_users[user.id]
            await interaction.response.send_message(f"{user.display_name} has been unblanked!", ephemeral=False)
        else:
            await interaction.response.send_message(f"{user.display_name} is already unblanked!", ephemeral=True)

# ---------- smoothcolorGive command ----------

@bot.tree.command(
    name="smoothcolorgive",
    description="Apply smoothly changing color role to a user."
)
@app_commands.describe(
    palette_id="Palette ID",
    speed="How fast the color changes"
)
@app_commands.choices(
    speed=[
        app_commands.Choice(name="Slow", value=12),
        app_commands.Choice(name="Medium", value=7),
        app_commands.Choice(name="Fast", value=4),
    ]
)
async def smoothcolorGive(
    interaction: discord.Interaction,
    user: discord.Member,
    palette_id: int,
    speed: app_commands.Choice[int],
):
    await interaction.response.defer(ephemeral=True)

    if palette_id not in palettes:
        await interaction.followup.send(
            "\u274C That palette ID does not exist.",
            ephemeral=True,
        )
        return

    palette = palettes[palette_id]
    if palette is None:
        await interaction.followup.send(
            f"\u26A0\uFE0F Palette {palette_id} is empty.",
            ephemeral=True,
        )
        return

    guild = interaction.guild

    # ✅ per-user role
    role = await get_or_create_user_color_role(guild, user)

    # stop previous gradient first
    stop_gradient(user)
    await asyncio.sleep(0.1)  # let cancellation propagate

    # remove any other color roles
    for r in user.roles:
        if r.name.startswith("ColorRole") and r != role:
            await user.remove_roles(r, reason="Replacing color role")

    # add the per-user role fresh
    await user.add_roles(role, reason="Smooth color role applied")

    # start the gradient loop
    task = bot.loop.create_task(
        gradient_loop(
            user=user,
            role=role,
            palette=palette,
            steps=speed.value,
            interval=1.75
        )
    )
    active_loops[user.id] = task

    # notify the user
    await interaction.followup.send(
        f"\U0001F308 Smooth color role started for {user.display_name}.",
        ephemeral=True,
    )



bot.run(TOKEN)