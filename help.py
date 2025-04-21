import discord
from discord.ext import commands
from discord.ui import View, Select
from discord import SelectOption

class HelpSelect(Select):
    def __init__(self, cog):
        options = [
            SelectOption(label="Announce", value="announce", description="Help with announcements"),
            SelectOption(label="Delay", value="delay", description="Delayed announcements"),
            SelectOption(label="Schedule", value="schedule", description="Schedule commands"),
            SelectOption(label="Timestamp", value="timestamp", description="Timestamp formats"),
            SelectOption(label="Time Zone", value="timezone", description="Time zone commands"),
            SelectOption(label="Permissions", value="permissions", description="Command role permissions"),
            SelectOption(label="Tracking Commands", value="tracking_commands", description="Tracking output functions"),
        ]
        super().__init__(placeholder="Select a command...", min_values=1, max_values=1, options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        # Use the cog to send the appropriate help
        await self.cog._send_help(interaction, value)

class HelpView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.add_item(HelpSelect(cog))

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='help', aliases=['h'])
    @commands.has_any_role('The BotFather', 'Moderator', 'Manager', 'Server Owner', 'Police')
    async def help(self, ctx, topic: str = None):
        """Show help for all commands or a specific topic."""
        if topic is None or topic.lower() in ['commands', 'com', 'comm']:
            embed = self._build_all_commands_embed()
            view = HelpView(self)
            await ctx.send(embed=embed, view=view)
        else:
            await self._send_help(ctx, topic.lower())

    async def _send_help(self, dest, topic: str):
        """Internal: send help embed for a specific topic. `dest` is ctx or interaction."""
        # Determine how to send (Context vs Interaction)
        is_inter = hasattr(dest, 'response')
        send = dest.response.send_message if is_inter else dest.send
        # Announce
        if topic in ['announce', 'ann', 'a']:
            await send(embed=await self._announce_help_embed(), ephemeral=is_inter)
        # Schedule
        elif topic in ['schedule', 'sch']:
            embed = discord.Embed(
                title="**Schedule Commands:**",
                description=(
                    "- `!!resetschedule` or `!!rsch` → Set a new schedule\n"
                    "- `!!currentschedule` or `!!csch` → View the current schedule\n"
                    "- `!!expire` → Calculate pack expiry time/date for rsch input"
                ),
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)
        # Timezone
        elif topic in ['timezone', 'time', 'tz']:
            embed = discord.Embed(
                title="**Time Zone Commands:**",
                description=(
                    "- `!!settimezone <timezone>` or `!!stz <timezone>` → Set your timezone (e.g., Europe/Berlin)\n"
                    "- `!!gettimezone` or `!!gtz` → Show your current timezone setting\n"
                    "- `!!time` → Display the current time in your set timezone"
                ),
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)
        # Delay
        elif topic in ['delay', 'd']:
            embed = discord.Embed(
                title="**Delay Commands:**",
                description=(
                    "- **Delaying an Announcement:**\nReact with ⏳ during `!!announce` to schedule it.\n"
                    "  Input delay date/time in `MM/DD HH:MM` format.\n"
                    "- `!!viewdelay` or `!!vdelay` → View pending announcements.\n"
                    "- `!!canceldelay <MM/DD HH:MM>` or `!!cdelay <MM/DD HH:MM>` → Cancel a delayed announcement."
                ),
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)
        # Timestamp
        elif topic in ['timestamp', 'ts']:
            embed = discord.Embed(
                title="**Timestamp Formats:**",
                description=(
                    "- `<t:###:F>` → Day, Month, Year at Time\n"
                    "- `<t:###:f>` → Month, Year at Time\n"
                    "- `<t:###:D>` → Month, Year\n"
                    "- `<t:###:d>` → MM/DD/YYYY\n"
                    "- `<t:###:t>` → Time (HH:MM)\n"
                    "- `<t:###:T>` → Time (HH:MM:SS)\n"
                    "- `<t:###:R>` → Relative time"
                ),
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)
        # Permissions
        elif topic in ['permissions', 'permission', 'p', 'perm']:
            embed = discord.Embed(
                title="**Command Permissions:**",
                description=(
                    "**The BotFather**: All commands\n"
                    "**Server Owner**: All commands except `aiart`\n"
                    "**Manager**: All except `aiart, write`\n"
                    "**Moderator**: All except `aiart, write`\n"
                    "**Police**: gtz, stz, time, expire, csch, poll, tony, help"
                ),
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)
        # Timezone
        elif topic in ['tracking_commands', 'tc', 'tcom', 'tcomm']:
            embed = discord.Embed(
                title="**Tracking Commands:**",
                description=(
                    "- `!!tracking` → Outputs the tracking format and saves it to the .json\n"
                    "- `!!tracking pack X` → Shows pack number X saved in the .json file\n"
                    "- `!!tracking packs` → Displays a list of all currently saved packs in the .json file\n"
                    "- `!!tracking clear` → Delets/Erases all currently saved tracking outputs from the .json"
                ),
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)
    

# Individual Commands
        elif topic in ['testannounce', 'testann', 'ta']:
            embed = discord.Embed(
                title="!!testannounce",
                description="Post an announcement to the **test announcement channel** instead of the real one.\nExample: `!!testannounce packdrop`",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['resetschedule', 'rsch', 'rs']:
            embed = discord.Embed(
                title="!!resetschedule",
                description="Create a brand new schedule and overwrite any current schedule.\nFollow the prompts in Discord after running this command.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['currentschedule', 'csch', 'cs']:
            embed = discord.Embed(
                title="!!currentschedule",
                description="View the currently active schedule set for announcements.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['settimezone', 'stz']:
            embed = discord.Embed(
                title="!!settimezone",
                description="Set your personal timezone.\nExample: `!!settimezone Europe/Berlin`",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['gettimezone', 'gtz']:
            embed = discord.Embed(
                title="!!gettimezone",
                description="Show your currently set timezone.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic == 'time':
            embed = discord.Embed(
                title="!!time",
                description="Display the current time based on your set timezone.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['viewdelay', 'vdelay', 'vd']:
            embed = discord.Embed(
                title="!!viewdelay",
                description="View all currently scheduled delayed announcements.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['canceldelay', 'cdelay', 'cd']:
            embed = discord.Embed(
                title="!!canceldelay",
                description="Cancel a scheduled delayed announcement.\nFormat: `!!canceldelay MM/DD HH:MM`",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic == 'poll':
            embed = discord.Embed(
                title="!!poll",
                description="Create a custom poll with options and reaction buttons.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['expire', 'expiry', 'e']:
            embed = discord.Embed(
                title="!!expire",
                description="Calculate when your Pokémon packs will expire based on their date.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['tracking', 'track', 't']:
            embed = discord.Embed(
                title="!!tracking",
                description=(
                    "- `!!tracking` → Outputs the tracking format and saves it to the .json\n"
                    "- `!!tracking pack X` → Shows pack number X saved in the .json file\n"
                    "- `!!tracking packs` → Displays a list of all currently saved packs in the .json file\n"
                    "- `!!tracking clear` → Delets/Erases all currently saved tracking outputs from the .json"
                ),
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['addingschedule', 'asch', 'as']:
            embed = discord.Embed(
                title="!!addingschedule",
                description="Add events into an existing schedule without wiping the old one.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['endcycle', 'endc', 'ec']:
            embed = discord.Embed(
                title="!!endcycle",
                description="Output the `End of Cycle X --- Start of Cycle Y` message in 6 channels.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic == 'export_votes':
            embed = discord.Embed(
                title="!!export_votes",
                description="**Outdated!** The old function to export a csv of poll results.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['write', 'w']:
            embed = discord.Embed(
                title="!!write",
                description="A fun little command for the Dev.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['del', 'delete']:
            embed = discord.Embed(
                title="!!del",
                description="Command to delete previous messages.\n`!!del → Deletes 1 message`\n`!!del X → deletes up to 10 messages`",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic == 'tony':
            embed = discord.Embed(
                title="!!tony",
                description="We like Tony. Hope you're doing well brother!",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['happytree', 'ht', 'haptree']:
            embed = discord.Embed(
                title="!!happytree",
                description="**Bonus Feature**\nThis command is a useless command that outputs an ASCII tree.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['aiart', 'ai', 'aa']:
            embed = discord.Embed(
                title="!!aiart",
                description="**Broken**\nThis command is meant to utilize ChatGPT to output an image based off of a prompt. It doesn't work *lol*.",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['help', 'h']:
            embed = discord.Embed(
                title="!!help",
                description="Show help menus for all available commands or a specific command.\nExample: `!!help poll`",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        elif topic in ['livepackowner', 'livepackowners', 'lpo']:
            embed = discord.Embed(
                title="!!livepackowner",
                description="Command to output the message for new Live Pack Owners.\n`!!lpo → Deletes your '!!lpo' input, then outputs the message.`",
                color=0xFFC107
            )
            await send(embed=embed, ephemeral=is_inter)

        else:
            embed = discord.Embed(
                title="**Unknown Help Topic**",
                description=f"No help available for `{topic}`. Use `!!help` to see all commands.",
                color=0xFF0000
            )
            await send(embed=embed, ephemeral=is_inter)

    def _build_all_commands_embed(self):
        return discord.Embed(
            title="**All Commands:**",
            description=(
                "- `!!announce`/`!!ann`\n"
                "- `!!testannounce`/`!!testann`\n"
                "- `!!resetschedule`/`!!rsch`\n"
                "- `!!currentschedule`/`!!csch`\n"
                "- `!!settimezone`/`!!stz`\n"
                "- `!!gettimezone`/`!!gtz`\n"
                "- `!!time`\n"
                "- `!!viewdelay`/`!!vdelay`\n"
                "- `!!canceldelay`/`!!cdelay`\n"
                "- `!!poll`\n"
                "- `!!expire`\n"
                "- `!!tracking`\n"
                "- `!!endcycle` or `!!endc`\n"
                "- `!!addingschedule`/`!!asch`\n"
                "- `!!timestamp`/`!!ts`\n"
                "- `!!help`/`!!h`\n"
                "- `!!help permissions`/`!!help p` → **Role Permissions/Privileges**\n"
                "- `!!export_votes` → ***Not in Use***\n"
                "- `!!write`  → ***Limited Access***\n"
                "- `!!del`  → ***Be Careful!***\n"
                "- `!!tony`\n"
                "- `!!happytree`\n"
                "- `!!aiart` → ***Broken***\n\n"
                "*Input **!!help <command>** for help with specific commands.*"
            ),
            color=0xFFC107
        )

    async def _announce_help_embed(self):
        # Reuse original announce help logic:
        try:
            with open('announcements.txt', 'r', encoding='utf-8') as f:
                content = f.read().split('===')
                titles = [sect.strip().splitlines()[0] for sect in content if sect.strip()]
            embed = discord.Embed(
                title="**Available Announcements:**",
                description="- " + "\n- ".join(titles) +
                            "\n\n**Input format:** `!!announce <name>`\n" +
                            "**Test:** `!!testannounce <name>`",
                color=0xFFC107
            )
        except Exception as e:
            embed = discord.Embed(
                title="Error reading announcements",
                description=str(e),
                color=0xFF0000
            )
        return embed

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
    print("Loaded HelpCog!")
