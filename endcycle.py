import discord
from discord.ext import commands

# Channels
PACK_TRACKING_CHANNEL_ID = 1335990119978766438
ACTIVITY_CHECK_CHANNEL_ID = 1349881473087438858
SCHEDULE_CHANNEL_ID = 1349879809445990560
PACK_RESULTS_CHANNEL_ID = 1337574067460640839
PACK_VERIFICATION_CHANNEL_ID = 1337574284586909798
PACK_VOTING_CHANNEL_ID = 1335186020358029333

class EndCycleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='endcycle', aliases=["endc"])
    @commands.has_any_role('Spreadsheet-Master', 'Server Owner', 'Manager', 'Moderator')
    async def endcycle(self, ctx, *, message: str = None):
        # Check if the cycle number was provided.
        if message is None:
            await ctx.send(
                'Error: Please input the ending cycle number with the command.\n'
                '*(e.g. **>endcycle 4** to start the 5th cycle).*'
            )
            return

        # Attempt to convert the provided argument to an integer.
        try:
            cycle_number = int(message.strip())
        except ValueError:
            await ctx.send(
                'Error: The cycle number must be an integer.\n'
                '*(e.g. **>endcycle 4** to start the 5th cycle).*'
            )
            return

        # Calculate the next cycle and prepare the formatted message.
        next_cycle = cycle_number + 1
        formatted_message = (
            f"# END OF CYCLE {cycle_number}\n"
            f"# --------------------------------------------------------------------------------\n"
            f"# START OF CYCLE {next_cycle}"
        )

        # List of channel IDs where the message should be sent.
        channel_ids = [
            PACK_TRACKING_CHANNEL_ID,
            ACTIVITY_CHECK_CHANNEL_ID,
            SCHEDULE_CHANNEL_ID,
            PACK_RESULTS_CHANNEL_ID,
            PACK_VERIFICATION_CHANNEL_ID,
            PACK_VOTING_CHANNEL_ID
        ]

        # Loop through each channel ID, get the channel and send the message.
        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(formatted_message)
            else:
                print(f"Channel with ID {channel_id} not found.")

# This is the new asynchronous setup function required for discord.py 2.0+.
async def setup(bot):
    await bot.add_cog(EndCycleCog(bot))
    print ("Loaded EndCycleCog!")
