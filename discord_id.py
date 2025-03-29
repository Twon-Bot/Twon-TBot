from discord.ext import commands
from discord import Intents

# Create an instance of Intents
intents = Intents.default()
intents.messages = True  # Enable message intents
intents.guilds = True    # Enable guild intents
intents.message_content = True  # Enable the message content intent

# Create the bot instance with intents
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command()
async def get_user(ctx, user_id: int):
    user = await bot.fetch_user(user_id)
    await ctx.send(f'User ID: {user.id}, Username: {user.name}')

bot.run('MTMzOTczMjU5MzIxNzkwMDY3Ng.GbRH8Q.-9RcjaGxwE9-r5XURap55FNNYfE6KSx5pYZWAM')